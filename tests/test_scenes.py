"""data/scenes/ 底下的每個場景都必須通過驗證；另用 B0203 真實場景測幾個關鍵情境。"""

import copy
from pathlib import Path

import pytest

from roomquest.verifier import load_json, verify

SCENES = Path(__file__).resolve().parents[1] / "data" / "scenes"
SCENE_DIRS = sorted(p for p in SCENES.iterdir() if (p / "game.json").exists())


@pytest.mark.parametrize("scene_dir", SCENE_DIRS, ids=lambda p: p.name)
def test_every_scene_passes(scene_dir):
    report = verify(load_json(scene_dir / "scene.json"), load_json(scene_dir / "game.json"))
    assert report.passed, report.to_text()


B0203 = SCENES / "classroom-b0203"


def load_b0203():
    return load_json(B0203 / "scene.json"), load_json(B0203 / "game.json")


def test_b0203_white_wall_things_are_ambiguous():
    """只寫「白色的東西」時，鐵箱、板擦機、基地台、布幕盒……都符合。"""
    scene, game = load_b0203()
    game["levels"][1]["references"][0]["constraints"] = {"color": "白色"}
    issue = next(i for i in verify(scene, game).errors if i.code == "AMBIGUOUS_TARGET")
    assert {"obj_02", "obj_03", "obj_04", "obj_10"} <= set(issue.detail["candidates"])


def test_b0203_photo_reading_would_be_caught():
    """照片判讀的 14 條通風孔若沒經過主持人修正，答案 16 會和場景資料對不上。"""
    scene, game = load_b0203()
    vent_box = next(o for o in scene["objects"] if o["id"] == "obj_02")
    vent_box["attributes"]["vertical_vents"] = 14
    assert "ANSWER_MISMATCH" in [i.code for i in verify(scene, game).errors]


def test_b0203_unconfirmed_windows_cannot_be_used():
    scene, game = load_b0203()
    game["levels"][1]["references"] = [{"object_id": "obj_16", "constraints": {"category": "窗戶"}}]
    game["levels"][1]["answer_source"] = {"object_id": "obj_16", "field": "count", "transform": "identity"}
    game["levels"][1]["answer"] = "5"
    assert "UNCONFIRMED_OBJECT" in [i.code for i in verify(scene, game).errors]


def test_b0203_course_schedule_is_dynamic():
    scene, game = load_b0203()
    game["levels"][2]["references"] = [{"object_id": "obj_08", "constraints": {"category": "課程表"}}]
    game["levels"][2]["answer_source"] = {"object_id": "obj_08", "field": "text", "transform": "identity"}
    assert "DYNAMIC_ANSWER" in [i.code for i in verify(scene, game).errors]
