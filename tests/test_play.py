import json
from pathlib import Path

import pytest

from roomquest.play import GameNotApproved, PlayLogger, load_approved_game, new_state, reveal_hint, submit, view

SCENE_DIR = Path(__file__).resolve().parents[1] / "data" / "scenes" / "classroom-b305"
GAME = load_approved_game(SCENE_DIR / "scene.json", SCENE_DIR / "game.json")


def test_full_playthrough_with_hints_and_mistakes(tmp_path):
    logger = PlayLogger(tmp_path)
    state = new_state()
    state, msg, ok = submit(GAME, state, "9", logger)
    assert not ok and state["wrong_total"] == 1
    state = reveal_hint(GAME, state, logger)
    assert view(GAME, state)["hints"] == [GAME["levels"][0]["hints"][0]]
    for answer in ["三張", "7", "五"]:
        state, msg, ok = submit(GAME, state, answer, logger)
        assert ok, msg
    assert state["phase"] == "final" and state["collected"] == ["3", "7", "5"]
    state, msg, ok = submit(GAME, state, "357", logger)
    assert not ok
    state, msg, ok = submit(GAME, state, "375", logger)
    assert ok and state["phase"] == "done"

    summary = view(GAME, state)
    assert summary["hint_total"] == 1 and summary["wrong_total"] == 2
    events = [json.loads(line)["event"] for line in (tmp_path / "classroom-b305-demo.jsonl").read_text().splitlines()]
    assert events[0] == "answer" and events[-1] == "complete"


def test_view_never_contains_unsolved_answers():
    state = new_state()
    for index, level in enumerate(GAME["levels"]):
        shown = json.dumps(view(GAME, state), ensure_ascii=False)
        for later in GAME["levels"][index:]:
            assert f'"{later["answer"]}"' not in shown
        assert GAME["final_code"] not in shown
        state, _, _ = submit(GAME, state, level["answer"])


def test_hint_button_stops_at_last_hint():
    state = new_state()
    for _ in range(10):
        state = reveal_hint(GAME, state)
    assert state["hints"] == len(GAME["levels"][0]["hints"])
    assert view(GAME, state)["hints_left"] == 0


def test_player_refuses_unverified_game(tmp_path):
    bad = json.loads((SCENE_DIR / "game.json").read_text(encoding="utf-8"))
    bad["levels"][2]["answer"] = "9"
    bad_path = tmp_path / "game.json"
    bad_path.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(GameNotApproved):
        load_approved_game(SCENE_DIR / "scene.json", bad_path)
