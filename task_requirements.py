from __future__ import annotations

import re
from typing import Any


_NUMBERED_PREFIX = re.compile(r"^\s*\d+\s*(?:[.、)]\s*|(?=[\u4e00-\u9fff]))")
_OPTIONAL_PREFIX = re.compile(
    r"^\s*(?:[\(\[（【]\s*(?:可选(?:项)?|optional(?:\s+objective)?|необязательно|необязательный)\s*[\)\]）】]\s*"
    r"|(?:可选(?:项)?|optional)\s*[:：—-]\s*)",
    re.IGNORECASE,
)
_CHINESE_QUANTITY_SUFFIX = re.compile(
    r"(?P<count>\d+)\s*(?:个|瓶|件|枚|把|张|份|组|支|桶|只|条|颗|块|包|根|台|片|本)\s*$"
)
_ENGLISH_QUANTITY = re.compile(
    r"(?<![\w])(?P<count>\d+)\s*(?:x\s*)?(?:items?|pieces?|bottles?|cans?|packs?|sets?|units?|pcs)\b",
    re.IGNORECASE,
)
_ASSAULT_WEAPON_CATEGORY_KILL = re.compile(
    r"使用[^。！？\r\n]{0,100}(?:突击步枪|突击卡宾枪)[^。！？\r\n]{0,100}"
    r"(?:消灭|击杀|击败|杀死)",
    re.IGNORECASE,
)
_KEY_ITEM_NAME = re.compile(r"钥匙|(?<![A-Za-z])key(?:[\s-]?card)?(?![A-Za-z])", re.IGNORECASE)


def uses_assault_weapon_category_for_kills(objectives: list[Any] | str) -> bool:
    if isinstance(objectives, str):
        text = objectives
    else:
        text = "\n".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item)
            for item in objectives
        )
    return bool(_ASSAULT_WEAPON_CATEGORY_KILL.search(text))


def filter_assault_weapon_items(
    objectives: list[Any] | str, items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not uses_assault_weapon_category_for_kills(objectives):
        return items
    return [
        item
        for item in items
        if _KEY_ITEM_NAME.search(str(item.get("name", "")))
    ]


def _target_count(text: str) -> int | None:
    match = _CHINESE_QUANTITY_SUFFIX.search(text) or _ENGLISH_QUANTITY.search(text)
    if not match:
        return None
    try:
        count = int(match.group("count"))
    except (TypeError, ValueError):
        return None
    return count if count > 1 else None


def normalize_objective(text: str) -> dict[str, Any]:
    normalized_text = _NUMBERED_PREFIX.sub("", str(text or "")).strip()
    optional_match = _OPTIONAL_PREFIX.match(normalized_text)
    optional = optional_match is not None
    if optional_match:
        normalized_text = normalized_text[optional_match.end():].strip()
    objective: dict[str, Any] = {"text": normalized_text, "optional": optional}
    count = _target_count(normalized_text)
    if count is not None:
        objective["target_count"] = count
    return objective


def normalize_requirement(item: dict[str, Any]) -> dict[str, Any]:
    objective = normalize_objective(str(item.get("text", "")))
    optional = bool(item.get("optional", False)) or bool(objective["optional"])
    normalized: dict[str, Any] = {
        "text": objective["text"],
        "optional": optional,
    }
    try:
        target_count = int(item.get("target_count") or objective.get("target_count") or 0)
    except (TypeError, ValueError):
        target_count = 0
    completed = bool(item.get("completed", False))
    if target_count > 1:
        try:
            current_count = int(item.get("current_count", target_count if completed else 0))
        except (TypeError, ValueError):
            current_count = 0
        current_count = min(max(current_count, 0), target_count)
        normalized["target_count"] = target_count
        normalized["current_count"] = current_count
        normalized["completed"] = current_count >= target_count
    else:
        normalized["completed"] = completed
    return normalized
