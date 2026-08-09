"""
AI出力内の数値表現を、元の発言ログと機械的に照合する。
一致しない場合は [要確認：数値未照合] を付記する。
"""

from __future__ import annotations

import copy
import re
from typing import Any

# 数字を含む短い表現を拾う（日付・時刻・社数・金額など）
_NUM_EXPR = re.compile(
    r"[^\s　、。．，,・\n]{0,12}"
    r"[0-9０-９]"
    r"[^\s　、。．，,・\n]{0,20}"
)

_TAG = "[要確認：数値未照合]"


def _extract_numeric_exprs(text: str) -> list[str]:
    if not text:
        return []
    found = []
    for m in _NUM_EXPR.finditer(text):
        expr = m.group(0).strip("「」『』（）()[]【】")
        if expr and expr not in found:
            found.append(expr)
    return found


def _flag_if_needed(text: str, transcript: str) -> str:
    if not text or _TAG in text:
        return text
    for expr in _extract_numeric_exprs(text):
        if expr not in transcript:
            return text.rstrip() + _TAG
    return text


def apply_number_check(minutes_data: dict, transcript: str) -> dict:
    """
    議事録JSONを走査し、発言ログに無い数値表現へタグを付与したコピーを返す。
    """
    data = copy.deepcopy(minutes_data)
    source = transcript or ""

    for topic in data.get("議題", []) or []:
        topic["見出し"] = _flag_if_needed(topic.get("見出し", ""), source)
        for sub in topic.get("小項目", []) or []:
            sub["見出し"] = _flag_if_needed(sub.get("見出し", ""), source)
            sub["説明"] = _flag_if_needed(sub.get("説明", ""), source)
            for qa in sub.get("質疑", []) or []:
                qa["質問"] = _flag_if_needed(qa.get("質問", ""), source)
                qa["回答"] = _flag_if_needed(qa.get("回答", ""), source)

    data["次回打合せ"] = _flag_if_needed(data.get("次回打合せ", ""), source)
    return data


def collect_confirmation_tags(minutes_data: dict) -> list[str]:
    """プレビュー用に、要確認を含む文をフラットに集める。"""
    hits: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            if "[要確認" in value:
                hits.append(value)
        elif isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)

    walk(minutes_data)
    return hits
