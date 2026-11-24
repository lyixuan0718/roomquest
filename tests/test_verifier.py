"""每一種錯誤都用「改壞一個地方」的方式測試，確認驗證器真的抓得到。"""

import copy
from pathlib import Path

import pytest

from roomquest.verifier import load_json, verify

SCENE_DIR = Path(__file__).resolve().parents[1] / "data" / "scenes" / "classroom-b305"
SCENE = load_json(SCENE_DIR / "scene.json")
GAME = load_json(SCENE_DIR / "game.json")


def fresh():
    return copy.deepcopy(SCENE), copy.deepcopy(GAME)


def error_codes(report):
    return [issue.code for issue in report.errors]


def test_sample_game_passes():
    report = verify(SCENE, GAME)
    assert report.passed, report.to_text()
    assert set(report.codes()) <= {"MOVABLE_OBJECT", "NAME_LEAK"}


def test_ambiguous_red_object_is_rejected():
    """「窗邊的紅色東西」同時指向水壺與書包。"""
    scene, game = fresh()
    game["levels"][1]["references"][1]["constraints"] = {"region": "窗邊", "color": "紅色"}
    report = verify(scene, game)
    assert "AMBIGUOUS_TARGET" in error_codes(report)
    issue = next(i for i in report.errors if i.code == "AMBIGUOUS_TARGET")
    assert set(issue.detail["candidates"]) == {"obj_03", "obj_04"}
    assert report.failed_steps() == [2]


def test_adding_use_makes_it_unique_again():
    scene, game = fresh()
    game["levels"][1]["references"][1]["constraints"] = {"region": "窗邊", "color": "紅色", "use": "裝水"}
    assert verify(scene, game).passed


def test_clock_hand_cannot_be_answer():
    scene, game = fresh()
    level = game["levels"][0]
    level["references"] = [{"object_id": "obj_06", "constraints": {"category": "時鐘"}}]
    level["answer_source"] = {"object_id": "obj_06", "field": "attributes.hour_hand", "transform": "identity"}
    assert "DYNAMIC_ANSWER" in error_codes(verify(scene, game))


def test_unknown_object():
    scene, game = fresh()
    game["levels"][0]["references"][0]["object_id"] = "obj_99"
    assert "UNKNOWN_OBJECT" in error_codes(verify(scene, game))


def test_unconfirmed_object():
    scene, game = fresh()
    scene["objects"][0]["confirmed"] = False
    assert "UNCONFIRMED_OBJECT" in error_codes(verify(scene, game))


def test_using_a_future_answer_is_a_dependency_error():
    scene, game = fresh()
    game["levels"][1]["references"][0]["constraints"]["count"] = "$step3"
    assert "BAD_DEPENDENCY" in error_codes(verify(scene, game))


def test_previous_answer_must_actually_match_the_scene():
    """第 2 關說椅子數量等於第 1 關答案；若第 1 關答案改成 4，就找不到符合的椅子。"""
    scene, game = fresh()
    scene["objects"][0]["attributes"]["paper_count"] = 4
    game["levels"][0]["answer"] = "4"
    game["final_code"] = "475"
    assert "NO_MATCH" in error_codes(verify(scene, game))


def test_answer_must_come_from_scene_data():
    scene, game = fresh()
    game["levels"][2]["answer"] = "3"
    codes = error_codes(verify(scene, game))
    assert "ANSWER_MISMATCH" in codes
    assert "FINAL_CODE_MISMATCH" in codes


def test_answer_object_must_be_referenced():
    scene, game = fresh()
    game["levels"][0]["answer_source"]["object_id"] = "obj_07"
    assert "ANSWER_SOURCE_NOT_REFERENCED" in error_codes(verify(scene, game))


@pytest.mark.parametrize("actions, expected", [
    (["move"], "UNSAFE_ACTION"),          # 不在白名單
    (["observe", "touch"], "UNSAFE_ACTION"),  # 公告欄標記為不可碰
])
def test_unsafe_actions(actions, expected):
    scene, game = fresh()
    game["levels"][0]["actions"] = actions
    assert expected in error_codes(verify(scene, game))


def test_touch_is_allowed_when_host_marks_object_touchable():
    scene, game = fresh()
    scene["objects"][0]["touchable"] = True
    game["levels"][0]["actions"] = ["observe", "touch"]
    assert verify(scene, game).passed


def test_missing_hints_is_schema_error():
    scene, game = fresh()
    game["levels"][0]["hints"] = []
    assert "SCHEMA_ERROR" in error_codes(verify(scene, game))


def test_steps_must_be_consecutive():
    scene, game = fresh()
    game["levels"][2]["step"] = 5
    assert "BAD_DEPENDENCY" in error_codes(verify(scene, game))


def test_wrong_target():
    scene, game = fresh()
    game["levels"][2]["references"][0]["constraints"] = {"category": "公告欄"}
    assert "WRONG_TARGET" in error_codes(verify(scene, game))


def test_name_leak_is_only_a_warning():
    scene, game = fresh()
    game["levels"][0]["clue"] = "數一數軟木公告欄上釘了幾張紙。"
    report = verify(scene, game)
    assert report.passed
    assert "NAME_LEAK" in [w.code for w in report.warnings if w.step == 1]


def test_feedback_lists_only_failed_levels():
    scene, game = fresh()
    game["levels"][1]["references"][1]["constraints"] = {"region": "窗邊", "color": "紅色"}
    feedback = verify(scene, game).to_feedback()
    assert "第 2 關" in feedback and "AMBIGUOUS_TARGET" in feedback
    assert "第 1 關" not in feedback
