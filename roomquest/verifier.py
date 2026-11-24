"""RoomQuest Verifier：用 Python 規則檢查關卡，不呼叫任何 AI。

檢查範圍只涵蓋 scene.json 中主持人已確認（confirmed=true）的物品；
照片沒拍到的東西不在檢查範圍內，這個限制必須在報告中誠實說明。

用法：
    python -m roomquest.verifier data/scenes/classroom-b305/scene.json data/scenes/classroom-b305/game.json
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .normalize import answers_match, normalize_answer

# ---- 規則常數 -------------------------------------------------------------
SAFE_ACTIONS = {"observe", "count", "read"}            # 永遠允許
TOUCH_ACTIONS = {"touch", "open"}                      # 只有全部物品 touchable 才允許
HAZARD_CATEGORIES = {"插座", "延長線", "電器", "電源", "窗戶", "滅火器"}
RELATION_KEYS = {"on", "in", "under", "next_to"}
SYMMETRIC_RELATIONS = {"next_to"}
PLAIN_KEYS = {"name", "category", "color", "region", "count", "text", "use"}
ANSWER_TYPES = {"number", "choice", "short_text"}
TRANSFORMS = {"identity", "last_digit", "digits"}
OBJECT_FIELDS = {
    "id": str, "name": str, "category": str, "use": list, "color": str, "region": str,
    "touchable": bool, "movable": bool, "dynamic": bool, "confirmed": bool,
}
LEVEL_FIELDS = {
    "step": int, "clue": str, "references": list, "actions": list,
    "answer_type": str, "answer": str, "answer_source": dict, "hints": list,
}
STEP_REF = re.compile(r"^\$step(\d+)$")


# ---- 報告格式 -------------------------------------------------------------
@dataclass
class Issue:
    code: str
    severity: str  # "error" 會擋下關卡；"warning" 交給主持人判斷
    message: str
    step: int | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class Report:
    issues: list[Issue] = field(default_factory=list)

    def add(self, code: str, message: str, step: int | None = None,
            severity: str = "error", **detail: Any) -> None:
        self.issues.append(Issue(code, severity, message, step, detail))

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def passed(self) -> bool:
        return not self.errors

    def failed_steps(self) -> list[int]:
        return sorted({i.step for i in self.errors if i.step is not None})

    def codes(self) -> list[str]:
        return [i.code for i in self.issues]

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "failed_steps": self.failed_steps(),
                "issues": [asdict(i) for i in self.issues]}

    def to_text(self) -> str:
        head = "通過" if self.passed else f"不通過（{len(self.errors)} 個錯誤）"
        lines = [f"驗證結果：{head}，警告 {len(self.warnings)} 個"]
        for issue in self.issues:
            where = f"第 {issue.step} 關" if issue.step else "全域"
            mark = "✗" if issue.severity == "error" else "△"
            lines.append(f"  {mark} [{issue.code}] {where}：{issue.message}")
        lines.append("  ※ 唯一性只涵蓋主持人已確認的物品，照片外的相似物品需現場確認。")
        return "\n".join(lines)

    def to_feedback(self) -> str:
        """給 Planner 的修改指示：只列錯誤，指出關卡、原因與要修正的方向。"""
        if self.passed:
            return "全部關卡通過驗證，不需要修改。"
        lines = ["以下關卡未通過 Python 驗證，請只修改這些關卡，其他關卡保持不變："]
        for issue in self.errors:
            lines.append(f"- 第 {issue.step} 關 [{issue.code}]：{issue.message}")
        return "\n".join(lines)


# ---- 工具函式 -------------------------------------------------------------
def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def get_field(obj: dict[str, Any], path: str) -> Any:
    value: Any = obj
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def apply_transform(value: Any, transform: str) -> str | None:
    text = str(value)
    if transform == "identity":
        return text
    digits = re.findall(r"\d", text)
    if transform == "last_digit":
        return digits[-1] if digits else None
    if transform == "digits":
        return "".join(digits) or None
    return None


def has_relation(obj: dict, rel_type: str, target_id: str, objects: dict[str, dict]) -> bool:
    if any(r.get("type") == rel_type and r.get("object") == target_id for r in obj.get("relations", [])):
        return True
    if rel_type in SYMMETRIC_RELATIONS and target_id in objects:
        return any(r.get("type") == rel_type and r.get("object") == obj["id"]
                   for r in objects[target_id].get("relations", []))
    return False


def object_matches(obj: dict, key: str, value: Any, objects: dict[str, dict]) -> bool:
    if key in RELATION_KEYS:
        return has_relation(obj, key, str(value), objects)
    if key == "use":
        return any(normalize_answer(u) == normalize_answer(value) for u in obj.get("use", []))
    actual = get_field(obj, key)
    return actual is not None and normalize_answer(actual) == normalize_answer(value)


def is_known_key(key: str) -> bool:
    return key in PLAIN_KEYS or key in RELATION_KEYS or key.startswith("attributes.")


# ---- 場景檢查 -------------------------------------------------------------
def check_scene(scene: Any, report: Report) -> dict[str, dict]:
    if not isinstance(scene, dict) or not isinstance(scene.get("objects"), list):
        report.add("SCHEMA_ERROR", "scene.json 必須是物件，且包含 objects 陣列。")
        return {}
    objects: dict[str, dict] = {}
    for index, obj in enumerate(scene["objects"], start=1):
        if not isinstance(obj, dict):
            report.add("SCHEMA_ERROR", f"第 {index} 個物品不是物件。")
            continue
        for name, kind in OBJECT_FIELDS.items():
            if not isinstance(obj.get(name), kind):
                report.add("SCHEMA_ERROR", f"物品 {obj.get('id', index)} 的 {name} 缺少或型別錯誤（需要 {kind.__name__}）。")
        obj_id = obj.get("id")
        if isinstance(obj_id, str):
            if obj_id in objects:
                report.add("SCHEMA_ERROR", f"物品 ID 重複：{obj_id}。")
            objects[obj_id] = obj
    for obj in objects.values():
        for rel in obj.get("relations", []) or []:
            if rel.get("type") not in RELATION_KEYS:
                report.add("SCHEMA_ERROR", f"物品 {obj['id']} 的關係類型 {rel.get('type')!r} 不在允許清單。")
            if rel.get("object") not in objects:
                report.add("UNKNOWN_OBJECT", f"物品 {obj['id']} 的關係指向不存在的物品 {rel.get('object')!r}。")
    return objects


# ---- 關卡檢查 -------------------------------------------------------------
def check_level_schema(level: Any, index: int, report: Report) -> bool:
    if not isinstance(level, dict):
        report.add("SCHEMA_ERROR", f"第 {index} 個關卡不是物件。", step=index)
        return False
    ok = True
    for name, kind in LEVEL_FIELDS.items():
        if not isinstance(level.get(name), kind) or isinstance(level.get(name), bool) and kind is int:
            report.add("SCHEMA_ERROR", f"欄位 {name} 缺少或型別錯誤（需要 {kind.__name__}）。", step=index)
            ok = False
    if not ok:
        return False
    if not level["clue"].strip():
        report.add("SCHEMA_ERROR", "線索文字是空的。", step=index)
    hints = level["hints"]
    if not 1 <= len(hints) <= 3 or not all(isinstance(h, str) and h.strip() for h in hints):
        report.add("SCHEMA_ERROR", "分層提示需要 1–3 則非空白文字。", step=index)
    if not level["references"]:
        report.add("SCHEMA_ERROR", "references 至少要有一個物品。", step=index)
        return False
    return True


def resolve_value(value: Any, step: int, answers: dict[int, str], report: Report) -> tuple[bool, Any]:
    """把 "$step1" 換成第 1 關答案；引用自己或之後的關卡屬於依賴錯誤。"""
    if not isinstance(value, str):
        return True, value
    match = STEP_REF.match(value)
    if not match:
        return True, value
    ref_step = int(match.group(1))
    if ref_step >= step or ref_step not in answers:
        report.add("BAD_DEPENDENCY", f"使用了第 {ref_step} 關的答案，但玩家在第 {step} 關時還拿不到。",
                   step=step, ref_step=ref_step)
        return False, None
    return True, answers[ref_step]


def check_references(level: dict, step: int, objects: dict[str, dict],
                     answers: dict[int, str], report: Report) -> None:
    confirmed = [o for o in objects.values() if o.get("confirmed")]
    warned_movable: set[str] = set()
    for ref in level["references"]:
        obj_id = ref.get("object_id") if isinstance(ref, dict) else None
        constraints = ref.get("constraints") if isinstance(ref, dict) else None
        if obj_id not in objects:
            report.add("UNKNOWN_OBJECT", f"引用了場景中不存在的物品 {obj_id!r}。", step=step, object_id=obj_id)
            continue
        obj = objects[obj_id]
        if not obj.get("confirmed"):
            report.add("UNCONFIRMED_OBJECT", f"「{obj['name']}」尚未經主持人確認，不能出題。", step=step, object_id=obj_id)
            continue
        if not isinstance(constraints, dict) or not constraints:
            report.add("SCHEMA_ERROR", f"指向「{obj['name']}」的條件是空的，玩家無從判斷。", step=step, object_id=obj_id)
            continue

        resolved: dict[str, Any] = {}
        usable = True
        for key, raw in constraints.items():
            if not is_known_key(key):
                report.add("SCHEMA_ERROR", f"不認得的條件欄位 {key!r}。", step=step, key=key)
                usable = False
                continue
            ok, value = resolve_value(raw, step, answers, report)
            if not ok:
                usable = False
                continue
            if key in RELATION_KEYS and value not in objects:
                report.add("UNKNOWN_OBJECT", f"關係條件 {key} 指向不存在的物品 {value!r}。", step=step)
                usable = False
                continue
            resolved[key] = value
        if not usable:
            continue

        matches = [o for o in confirmed
                   if all(object_matches(o, k, v, objects) for k, v in resolved.items())]
        shown = "、".join(f"{k}={v}" for k, v in resolved.items())
        if not matches:
            report.add("NO_MATCH", f"條件（{shown}）在場景中找不到任何物品。", step=step, object_id=obj_id)
        elif len(matches) > 1:
            names = "、".join(f"{o['name']}({o['id']})" for o in matches)
            report.add("AMBIGUOUS_TARGET", f"條件（{shown}）同時符合 {len(matches)} 個物品：{names}。請加入能區分它們的條件。",
                       step=step, object_id=obj_id, candidates=[o["id"] for o in matches])
        elif matches[0]["id"] != obj_id:
            report.add("WRONG_TARGET", f"條件（{shown}）指向「{matches[0]['name']}」，不是預期的「{obj['name']}」。",
                       step=step, object_id=obj_id, matched=matches[0]["id"])

        if obj.get("movable") and obj_id not in warned_movable:
            warned_movable.add(obj_id)
            report.add("MOVABLE_OBJECT", f"「{obj['name']}」可能被移動，遊戲開始前請確認位置。",
                       step=step, severity="warning", object_id=obj_id)


def check_answer(level: dict, step: int, objects: dict[str, dict], report: Report) -> None:
    source = level["answer_source"]
    obj_id = source.get("object_id")
    referenced = {r.get("object_id") for r in level["references"] if isinstance(r, dict)}
    if obj_id not in objects:
        report.add("UNKNOWN_OBJECT", f"答案來源指向不存在的物品 {obj_id!r}。", step=step)
        return
    obj = objects[obj_id]
    if obj_id not in referenced:
        report.add("ANSWER_SOURCE_NOT_REFERENCED", f"答案來自「{obj['name']}」，但線索沒有帶玩家找到它。", step=step)
    if obj.get("dynamic"):
        report.add("DYNAMIC_ANSWER", f"「{obj['name']}」的內容會隨時間改變，不能當答案來源。", step=step, object_id=obj_id)
        return
    transform = source.get("transform", "identity")
    if transform not in TRANSFORMS:
        report.add("SCHEMA_ERROR", f"不支援的答案轉換 {transform!r}。", step=step)
        return
    raw = get_field(obj, str(source.get("field", "")))
    derived = apply_transform(raw, transform) if raw is not None else None
    if derived is None:
        report.add("ANSWER_SOURCE_INVALID", f"「{obj['name']}」沒有欄位 {source.get('field')!r}，或無法取出答案。", step=step)
        return
    if not answers_match(derived, level["answer"]):
        report.add("ANSWER_MISMATCH", f"關卡答案寫 {level['answer']!r}，但依場景資料算出來是 {derived!r}。",
                   step=step, expected=derived)

    answer_type = level["answer_type"]
    if answer_type not in ANSWER_TYPES:
        report.add("SCHEMA_ERROR", f"答案類型 {answer_type!r} 不在允許清單。", step=step)
    elif answer_type == "number" and not normalize_answer(level["answer"]).isdigit():
        report.add("SCHEMA_ERROR", "答案類型是數字，但答案不是數字。", step=step)
    elif answer_type == "short_text" and len(level["answer"]) > 10:
        report.add("SCHEMA_ERROR", "短詞答案超過 10 個字。", step=step)
    elif answer_type == "choice" and level["answer"] not in level.get("options", []):
        report.add("SCHEMA_ERROR", "選擇題答案不在 options 裡。", step=step)


def check_safety(level: dict, step: int, objects: dict[str, dict], report: Report) -> None:
    actions = set(level["actions"])
    unknown = actions - SAFE_ACTIONS - TOUCH_ACTIONS
    if unknown:
        report.add("UNSAFE_ACTION", f"動作 {sorted(unknown)} 不在允許清單（只允許觀察、計數、閱讀；碰觸需主持人允許）。", step=step)
    if actions & TOUCH_ACTIONS:
        for ref in level["references"]:
            obj = objects.get(ref.get("object_id")) if isinstance(ref, dict) else None
            if obj is None:
                continue
            if not obj.get("touchable"):
                report.add("UNSAFE_ACTION", f"要求碰觸「{obj['name']}」，但主持人標記為只能觀察。", step=step, object_id=obj["id"])
            if obj.get("category") in HAZARD_CATEGORIES:
                report.add("UNSAFE_ACTION", f"「{obj['name']}」屬於危險類別，不允許碰觸。", step=step, object_id=obj["id"])


def check_wording(level: dict, step: int, objects: dict[str, dict], report: Report) -> None:
    clue = level["clue"]
    for ref in level["references"]:
        obj = objects.get(ref.get("object_id")) if isinstance(ref, dict) else None
        if obj is None:
            continue
        for word in {obj["name"], obj["category"]}:
            if len(word) >= 2 and word in clue:
                report.add("NAME_LEAK", f"線索直接寫出「{word}」，難度可能太低；若這關的重點是閱讀而非尋找，可以保留。",
                           step=step, severity="warning", word=word)
    answer = str(level["answer"]).strip()
    if answer and answer in clue:
        report.add("ANSWER_IN_CLUE", f"線索文字裡出現答案「{answer}」。", step=step, severity="warning")


# ---- 主程式 ---------------------------------------------------------------
def verify(scene: Any, game: Any) -> Report:
    report = Report()
    objects = check_scene(scene, report)
    if not isinstance(game, dict) or not isinstance(game.get("levels"), list) or not game["levels"]:
        report.add("SCHEMA_ERROR", "game.json 必須包含非空的 levels 陣列。")
        return report
    if game.get("scene_id") != (scene or {}).get("scene_id"):
        report.add("SCHEMA_ERROR", "game.json 的 scene_id 與 scene.json 不一致。")

    steps = [lv.get("step") if isinstance(lv, dict) else None for lv in game["levels"]]
    if steps != list(range(1, len(steps) + 1)):
        report.add("BAD_DEPENDENCY", f"關卡編號必須從 1 開始連續，目前是 {steps}。")

    answers: dict[int, str] = {}
    for index, level in enumerate(game["levels"], start=1):
        if not check_level_schema(level, index, report):
            continue
        step = level["step"]
        check_references(level, step, objects, answers, report)
        check_answer(level, step, objects, report)
        check_safety(level, step, objects, report)
        check_wording(level, step, objects, report)
        answers[step] = level["answer"]

    code_from = game.get("final_code_from")
    final_code = game.get("final_code")
    if not isinstance(code_from, list) or not isinstance(final_code, str):
        report.add("SCHEMA_ERROR", "需要 final_code（文字）與 final_code_from（關卡編號陣列）。")
    elif any(s not in answers for s in code_from):
        report.add("BAD_DEPENDENCY", f"最終密碼引用了不存在或未通過格式檢查的關卡：{code_from}。")
    else:
        combined = "".join(normalize_answer(answers[s]) for s in code_from)
        if combined != normalize_answer(final_code):
            report.add("FINAL_CODE_MISMATCH", f"各關答案依序組合是 {combined!r}，但 final_code 寫 {final_code!r}。")
    return report


def verify_files(scene_path: str | Path, game_path: str | Path) -> Report:
    return verify(load_json(scene_path), load_json(game_path))


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("用法：python -m roomquest.verifier <scene.json> <game.json>")
        return 2
    report = verify_files(argv[1], argv[2])
    print(report.to_text())
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
