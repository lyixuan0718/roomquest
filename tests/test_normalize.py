import pytest

from roomquest.normalize import answers_match, chinese_to_int, normalize_answer


@pytest.mark.parametrize("player, expected", [
    ("3", "3"), (" 3 ", "3"), ("３", "3"), ("三", "3"), ("3張", "3"), ("三張", "3"),
    ("十二", "12"), ("12", "12"), ("二十", "20"), ("二十三", "23"), ("兩個", "2"),
    ("07", "7"), ("375", "375"), ("三七五", "375"), ("B305", "b305"), ("紅色。", "紅色"),
])
def test_equivalent_answers(player, expected):
    assert answers_match(player, expected)


@pytest.mark.parametrize("player, expected", [
    ("4", "3"), ("37", "375"), ("0375", "375"), ("書本", "書"), ("", "3"),
])
def test_different_answers(player, expected):
    assert not answers_match(player, expected)


def test_units_only_removed_after_numbers():
    assert normalize_answer("日本") == "日本"
    assert normalize_answer("三本") == "3"


def test_chinese_numbers():
    assert chinese_to_int("十") == 10
    assert chinese_to_int("九十九") == 99
    assert chinese_to_int("一百") is None
