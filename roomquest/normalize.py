"""玩家答案正規化：把「三」「3 張」「３」「十二」等寫法轉成同一種形式再比對。"""

from __future__ import annotations

import re
import unicodedata

_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4,
           "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
# 只在「數字 + 量詞」的情況下移除量詞，避免誤刪一般文字答案裡的字。
_UNITS = "張個本號支台把盞片隻位次層"
_PUNCT = re.compile(r"[\s，,。．.、！!？?：:；;「」『』\"'（）()]+")


def chinese_to_int(text: str) -> int | None:
    """把 0–99 的中文數字轉成整數；無法轉換時回傳 None。"""
    if not text or any(ch not in _DIGITS and ch != "十" for ch in text):
        return None
    if "十" not in text:
        if len(text) == 1:
            return _DIGITS[text]
        # 「三七五」這種逐字念法，視為數字串。
        return int("".join(str(_DIGITS[ch]) for ch in text))
    tens, _, ones = text.partition("十")
    if len(tens) > 1 or len(ones) > 1 or "十" in ones:
        return None
    tens_value = _DIGITS[tens] if tens else 1
    ones_value = _DIGITS[ones] if ones else 0
    return tens_value * 10 + ones_value


def normalize_answer(value: object) -> str:
    """回傳用來比對的標準字串。"""
    text = unicodedata.normalize("NFKC", str(value)).strip().lower()  # 全形 → 半形
    text = _PUNCT.sub("", text)
    unit_match = re.fullmatch(rf"(.+?)[{_UNITS}]", text)
    if unit_match:
        core = unit_match.group(1)
        if core.isdigit() or chinese_to_int(core) is not None:
            text = core
    number = chinese_to_int(text)
    if number is not None:
        return str(number)
    if text.isdigit():
        return str(int(text)) if len(text) <= 2 else text  # 「07」→「7」，但密碼「0375」保留
    return text


def answers_match(player_input: object, expected: object) -> bool:
    return normalize_answer(player_input) == normalize_answer(expected)
