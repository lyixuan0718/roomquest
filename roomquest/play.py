"""玩家端的遊戲邏輯（與介面分開，方便測試）。

設計原則：
- 答案只存在伺服器端的 game dict，view() 回傳給介面的資料不含答案。
- 遊玩過程不呼叫 AI；只做 Python 比對與狀態更新。
- 每個動作寫一行 JSONL 紀錄，之後當作報告的遊玩數據。
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .normalize import answers_match
from .verifier import load_json, verify


class GameNotApproved(Exception):
    """game.json 未通過驗證，玩家端拒絕載入。"""


def load_approved_game(scene_path: str | Path, game_path: str | Path) -> dict[str, Any]:
    scene, game = load_json(scene_path), load_json(game_path)
    report = verify(scene, game)
    if not report.passed:
        raise GameNotApproved(report.to_text())
    return game


def new_state() -> dict[str, Any]:
    return {
        "session": uuid.uuid4().hex[:8],
        "phase": "level",          # level → final → done
        "index": 0,                # 目前第幾關（從 0 開始）
        "hints": 0,                # 本關已打開幾則提示
        "attempts": 0,             # 本關已作答次數
        "hint_total": 0,
        "wrong_total": 0,
        "collected": [],           # 玩家已解出的答案（自己找到的，可以顯示）
        "started": time.time(),
        "finished": None,
    }


def view(game: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """給介面顯示用的資料；刻意不放任何尚未解出的答案。"""
    levels = game["levels"]
    total = len(levels)
    base = {"title": game["title"], "story": game.get("story", ""), "phase": state["phase"],
            "collected": list(state["collected"]), "total": total}
    if state["phase"] == "level":
        level = levels[state["index"]]
        return {**base, "step": level["step"], "progress": state["index"] / (total + 1),
                "clue": level["clue"], "hints": level["hints"][: state["hints"]],
                "hints_left": len(level["hints"]) - state["hints"]}
    if state["phase"] == "final":
        return {**base, "step": None, "progress": total / (total + 1),
                "clue": "所有關卡都完成了！把取得的數字依序組合，輸入最終密碼。",
                "hints": [], "hints_left": 0}
    elapsed = int((state["finished"] or time.time()) - state["started"])
    return {**base, "step": None, "progress": 1.0, "clue": "", "hints": [], "hints_left": 0,
            "elapsed": elapsed, "hint_total": state["hint_total"], "wrong_total": state["wrong_total"]}


@dataclass
class PlayLogger:
    log_dir: Path | None = None

    def write(self, game: dict[str, Any], state: dict[str, Any], event: str, **data: Any) -> None:
        if self.log_dir is None:
            return
        self.log_dir.mkdir(parents=True, exist_ok=True)
        record = {"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "game_id": game["game_id"],
                  "session": state["session"], "event": event,
                  "elapsed_s": round(time.time() - state["started"], 1), **data}
        path = self.log_dir / f"{game['game_id']}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def reveal_hint(game: dict[str, Any], state: dict[str, Any], logger: PlayLogger | None = None) -> dict[str, Any]:
    if state["phase"] != "level":
        return state
    level = game["levels"][state["index"]]
    if state["hints"] < len(level["hints"]):
        state = {**state, "hints": state["hints"] + 1, "hint_total": state["hint_total"] + 1}
        if logger:
            logger.write(game, state, "hint", step=level["step"], hint_level=state["hints"])
    return state


def submit(game: dict[str, Any], state: dict[str, Any], text: str,
           logger: PlayLogger | None = None) -> tuple[dict[str, Any], str, bool]:
    """回傳（新狀態, 給玩家的回饋, 是否答對）。"""
    text = (text or "").strip()
    if not text:
        return state, "請先輸入答案。", False

    if state["phase"] == "level":
        level = game["levels"][state["index"]]
        correct = answers_match(text, level["answer"])
        attempt = state["attempts"] + 1
        if logger:
            logger.write(game, state, "answer", step=level["step"], attempt=attempt,
                         correct=correct, hints_used=state["hints"], input=text[:30])
        if not correct:
            return ({**state, "attempts": attempt, "wrong_total": state["wrong_total"] + 1},
                    "答案還不對。再觀察一次現場，或打開一層提示。", False)
        collected = state["collected"] + [level["answer"]]
        last = state["index"] == len(game["levels"]) - 1
        next_state = {**state, "collected": collected, "hints": 0, "attempts": 0,
                      "index": state["index"] if last else state["index"] + 1,
                      "phase": "final" if last else "level"}
        return next_state, f"答對了！第 {level['step']} 關取得「{level['answer']}」。", True

    if state["phase"] == "final":
        correct = answers_match(text, game["final_code"])
        if logger:
            logger.write(game, state, "final", correct=correct, input=text[:30])
        if not correct:
            return ({**state, "wrong_total": state["wrong_total"] + 1},
                    "密碼不對。檢查一下數字的順序。", False)
        done = {**state, "phase": "done", "finished": time.time()}
        if logger:
            logger.write(game, done, "complete", hint_total=done["hint_total"], wrong_total=done["wrong_total"])
        return done, "密碼正確，挑戰完成！", True

    return state, "遊戲已經完成，可以按「重新開始」再玩一次。", False
