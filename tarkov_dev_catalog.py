from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from catalog import (
    CatalogBundle,
    CatalogError,
)
from task_requirements import normalize_objective
from tarkov_dev_maps import fetch_tarkov_dev_task_map_points


TARKOV_DEV_JSON_ROOT = "https://json.tarkov.dev"
TARKOV_DEV_SOURCE = "Tarkov.dev community JSON API"
SUPPORTED_GAME_MODES = {"pve", "regular", "pvp-season"}
USER_AGENT = "EFTTaskAssistant/1.1 (local task catalog client)"
MAX_RESPONSE_BYTES = 30_000_000
CACHE_TTL_SECONDS = 12 * 60 * 60
TASK_ID_PATTERN = re.compile(r"^[0-9a-f]{24}$", re.IGNORECASE)
_DOCUMENT_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_DOCUMENT_CACHE_LOCK = threading.RLock()
_OBJECTIVE_FALLBACKS = {
    "buildWeapon": "组装指定武器",
    "dialogue": "与商人对话",
    "experience": "获得指定经验",
    "extract": "从指定撤离点撤离",
    "findItem": "找到指定物品",
    "findQuestItem": "找到指定任务物品",
    "giveItem": "上交指定物品",
    "giveQuestItem": "上交指定任务物品",
    "globalVariable": "完成指定任务目标",
    "mark": "标记指定目标",
    "plantItem": "放置指定物品",
    "plantQuestItem": "放置指定任务物品",
    "sellItem": "出售指定物品",
    "shoot": "击杀指定目标",
    "skill": "提升指定技能",
    "taskStatus": "完成指定任务",
    "traderLevel": "提升商人等级",
    "traderStanding": "提升商人声望",
    "useItem": "使用指定物品",
    "visit": "前往指定地点",
}


def _request_json_document(path: str) -> dict[str, Any]:
    if not re.fullmatch(
        r"(?:pve|regular|pvp-season)/(?:tasks|tasks_zh|tasks_en|traders|traders_zh|traders_en|items|items_zh|items_en|barters)",
        path,
    ):
        raise CatalogError("Tarkov.dev JSON API 路径无效。")
    request = Request(
        f"{TARKOV_DEV_JSON_ROOT}/{path}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        raise CatalogError(f"Tarkov.dev JSON API 返回 HTTP {error.code}：{path}") from error
    except (URLError, TimeoutError, OSError) as error:
        raise CatalogError(f"无法连接 Tarkov.dev JSON API：{error}") from error
    if len(body) > MAX_RESPONSE_BYTES:
        raise CatalogError(f"Tarkov.dev JSON 数据超过大小限制：{path}")
    try:
        result = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CatalogError(f"Tarkov.dev JSON 数据格式无效：{path}") from error
    if not isinstance(result, dict) or not isinstance(result.get("data"), (dict, list)):
        raise CatalogError(f"Tarkov.dev JSON 数据结构无效：{path}")
    return result


def _document(path: str, *, force_refresh: bool = False) -> dict[str, Any]:
    now = time.monotonic()
    with _DOCUMENT_CACHE_LOCK:
        cached = _DOCUMENT_CACHE.get(path)
        if not force_refresh and cached and now - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]
    result = _request_json_document(path)
    with _DOCUMENT_CACHE_LOCK:
        _DOCUMENT_CACHE[path] = (time.monotonic(), result)
    return result


def _data(document: dict[str, Any], key: str | None = None) -> Any:
    payload = document.get("data")
    if key is not None and isinstance(payload, dict):
        return payload.get(key)
    return payload


def _localized(value: Any, chinese: dict[str, Any], english: dict[str, Any], fallback: str = "") -> str:
    key = str(value or "").strip()
    if not key:
        return fallback.strip()
    for translations in (chinese, english):
        translated = translations.get(key)
        if isinstance(translated, str) and translated.strip() and translated.strip() != key:
            return translated.strip()
    if re.fullmatch(r"[0-9a-f]{24}(?:\s+(?:name|shortname))?", key, re.IGNORECASE):
        return fallback.strip()
    return key


def _pretty_name(value: Any, fallback: str) -> str:
    name = re.sub(r"[-_]+", " ", str(value or "")).strip()
    return name.title() if name else fallback


def _trader_names(
    traders: dict[str, Any],
    chinese: dict[str, Any],
    english: dict[str, Any],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for trader_id, trader in traders.items():
        if not isinstance(trader, dict):
            continue
        name = _localized(
            trader.get("name"),
            chinese,
            english,
            _pretty_name(trader.get("normalizedName"), str(trader_id)),
        )
        if name:
            result[str(trader_id)] = name
    return result


def _catalog_bundle(
    game_mode: str,
    tasks: dict[str, Any],
    task_names_zh: dict[str, Any],
    task_names_en: dict[str, Any],
    traders: dict[str, Any],
    trader_names_zh: dict[str, Any],
    trader_names_en: dict[str, Any],
) -> CatalogBundle:
    records: list[dict[str, Any]] = []
    trader_name_map = _trader_names(traders, trader_names_zh, trader_names_en)
    for task_id, raw_task in tasks.items():
        if not TASK_ID_PATTERN.fullmatch(str(task_id)) or not isinstance(raw_task, dict):
            continue
        title = _localized(
            raw_task.get("name"),
            task_names_zh,
            task_names_en,
            _pretty_name(raw_task.get("normalizedName"), str(task_id)),
        )
        trader_id = str(raw_task.get("trader") or "")
        trader = trader_name_map.get(trader_id)
        if not trader:
            trader = _pretty_name(raw_task.get("factionName"), "未知商人")
        if not title:
            continue
        normalized = str(raw_task.get("normalizedName") or "").strip()
        records.append(
            {
                "source_task_id": str(task_id).lower(),
                "trader": trader,
                "title": title,
                "source_url": f"https://tarkov.dev/task/{task_id}",
                "objectives": [],
                "prerequisites": [],
                "normalized_name": normalized,
            }
        )
    canonical = json.dumps(
        {"detail_schema": "tarkov-dev-task-zones-and-locations-v3", "tasks": records},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    metadata = {
        "provider": "tarkov.dev",
        "source_task_count": len(records),
        "source_version_label": None,
        "source_version_basis": "Tarkov.dev JSON API 未提供对应的游戏补丁版本标签",
        "game_build": None,
        "game_patch_coverage": "unknown",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "api_mode": game_mode,
        "task_endpoint": f"{TARKOV_DEV_JSON_ROOT}/{game_mode}/tasks",
        "translations_endpoint": f"{TARKOV_DEV_JSON_ROOT}/{game_mode}/tasks_zh",
        "warning": "社区资料未标注具体游戏补丁覆盖；请以游戏内任务为准。",
    }
    return CatalogBundle(
        game_mode=game_mode,
        source_version="",
        content_sha256=digest,
        tasks=records,
        metadata=metadata,
    )


def fetch_tarkov_dev_catalog(game_mode: str) -> CatalogBundle:
    if game_mode not in SUPPORTED_GAME_MODES:
        raise CatalogError("Tarkov.dev 不支持该游戏模式的任务目录。")
    documents = {
        name: _document(f"{game_mode}/{name}", force_refresh=True)
        for name in ("tasks", "tasks_zh", "tasks_en", "traders", "traders_zh", "traders_en")
    }
    tasks = _data(documents["tasks"], "tasks")
    traders = _data(documents["traders"])
    if not isinstance(tasks, dict) or not isinstance(traders, dict):
        raise CatalogError("Tarkov.dev 返回的任务或商人目录结构无效。")
    bundle = _catalog_bundle(
        game_mode,
        tasks,
        _data(documents["tasks_zh"]) or {},
        _data(documents["tasks_en"]) or {},
        traders,
        _data(documents["traders_zh"]) or {},
        _data(documents["traders_en"]) or {},
    )
    if len(bundle.tasks) < 50:
        raise CatalogError(
            f"Tarkov.dev 只返回 {len(bundle.tasks)} 条有效任务；旧任务目录保持不变。"
        )
    return bundle


def _key_ids(raw_task: dict[str, Any]) -> dict[str, set[str]]:
    keys_by_id: dict[str, set[str]] = {}
    needed_keys = raw_task.get("neededKeys")
    if isinstance(needed_keys, list):
        for entry in needed_keys:
            if not isinstance(entry, dict):
                continue
            map_id = str(entry.get("map") or "").strip().lower()
            for item_id in entry.get("keys", []) if isinstance(entry.get("keys"), list) else []:
                item_id = str(item_id).strip().lower()
                if TASK_ID_PATTERN.fullmatch(item_id):
                    keys_by_id.setdefault(item_id, set()).update({map_id} if map_id else set())
    if not keys_by_id:
        for objective in raw_task.get("objectives", []) if isinstance(raw_task.get("objectives"), list) else []:
            if not isinstance(objective, dict):
                continue
            map_ids = {
                str(map_id).strip().lower()
                for map_id in objective.get("maps", [])
                if TASK_ID_PATTERN.fullmatch(str(map_id).strip())
            } if isinstance(objective.get("maps"), list) else set()
            key_groups = objective.get("requiredKeys", [])
            if not isinstance(key_groups, list):
                continue
            for group in key_groups:
                values = group if isinstance(group, list) else [group]
                for item_id in values:
                    item_id = str(item_id).strip().lower()
                    if TASK_ID_PATTERN.fullmatch(item_id):
                        keys_by_id.setdefault(item_id, set()).update(map_ids)
    return keys_by_id


def _item_name(item_id: str, item: dict[str, Any], translations_zh: dict[str, Any], translations_en: dict[str, Any]) -> str:
    return _localized(
        item.get("name") or f"{item_id} Name",
        translations_zh,
        translations_en,
        str(item.get("normalizedName") or f"未知钥匙（{item_id}）"),
    )


def _format_count(count: Any) -> str:
    try:
        value = float(count)
    except (TypeError, ValueError):
        return str(count)
    return str(int(value)) if value.is_integer() else f"{value:g}"


def _acquisition_methods(
    item_id: str,
    item: dict[str, Any],
    items: dict[str, Any],
    item_names_zh: dict[str, Any],
    item_names_en: dict[str, Any],
    trader_names: dict[str, str],
    barters: list[Any],
    task_names: dict[str, str],
) -> list[dict[str, str]]:
    methods: list[dict[str, str]] = []
    offers = item.get("buyFromTrader")
    if isinstance(offers, list):
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            trader = trader_names.get(str(offer.get("trader") or ""), "")
            if not trader:
                continue
            currency_id = str(offer.get("currencyItem") or "")
            currency = ""
            if currency_id:
                currency_item = items.get(currency_id, {})
                if isinstance(currency_item, dict):
                    currency = _item_name(currency_id, currency_item, item_names_zh, item_names_en)
            price = offer.get("priceRUB", offer.get("price"))
            requirements = f"购买 {price:,} {currency}".strip() if isinstance(price, (int, float)) and currency else ""
            level = offer.get("minTraderLevel")
            methods.append(
                {
                    "type": "purchase",
                    "trader": trader,
                    "loyalty_level": f"LL {level}" if level else "",
                    "requirements": requirements,
                }
            )
    for barter in barters:
        if not isinstance(barter, dict) or len(methods) >= 8:
            continue
        offered = barter.get("offeredItem")
        if not isinstance(offered, dict) or str(offered.get("item") or "") != item_id:
            continue
        trader = trader_names.get(str(barter.get("trader") or ""), "")
        if not trader:
            continue
        requirements: list[str] = []
        for required in barter.get("requiredItems", []) if isinstance(barter.get("requiredItems"), list) else []:
            if not isinstance(required, dict):
                continue
            required_id = str(required.get("item") or "")
            required_item = items.get(required_id, {})
            if not isinstance(required_item, dict):
                continue
            required_name = _item_name(required_id, required_item, item_names_zh, item_names_en)
            requirements.append(f"{_format_count(required.get('count', 1))} × {required_name}")
        unlock = str(barter.get("taskUnlock") or "")
        if unlock and unlock in task_names:
            requirements.append(f"完成任务：{task_names[unlock]}")
        level = barter.get("minTraderLevel")
        methods.append(
            {
                "type": "barter",
                "trader": trader,
                "loyalty_level": f"LL {level}" if level else "",
                "requirements": "交换 " + "、".join(requirements) if requirements else "",
            }
        )
    return methods[:8]


def _task_details(
    raw_task: dict[str, Any],
    task_names_zh: dict[str, Any],
    task_names_en: dict[str, Any],
    tasks: dict[str, Any],
    traders: dict[str, Any],
    trader_names_zh: dict[str, Any],
    trader_names_en: dict[str, Any],
    items: dict[str, Any],
    item_names_zh: dict[str, Any],
    item_names_en: dict[str, Any],
    barters: list[Any],
    map_points: list[dict[str, Any]],
) -> dict[str, Any]:
    objectives: list[dict[str, Any]] = []
    raw_objectives = raw_task.get("objectives")
    if isinstance(raw_objectives, list):
        for raw_objective in raw_objectives:
            if not isinstance(raw_objective, dict):
                continue
            fallback = _OBJECTIVE_FALLBACKS.get(str(raw_objective.get("type") or ""), "完成指定目标")
            text = _localized(raw_objective.get("description"), task_names_zh, task_names_en, fallback)
            normalized = normalize_objective(text)
            if not normalized["text"]:
                continue
            objective: dict[str, Any] = {
                "text": normalized["text"],
                "optional": bool(raw_objective.get("optional")) or bool(normalized["optional"]),
            }
            try:
                count = int(raw_objective.get("count") or normalized.get("target_count") or 0)
            except (TypeError, ValueError):
                count = 0
            if count > 1:
                objective["target_count"] = count
            objectives.append(objective)
    if not objectives:
        raise CatalogError("Tarkov.dev 没有为该任务提供可用目标。")

    trader_names = _trader_names(traders, trader_names_zh, trader_names_en)
    task_names: dict[str, str] = {}
    for task_id, task in tasks.items():
        if isinstance(task, dict):
            task_names[str(task_id)] = _localized(
                task.get("name"),
                task_names_zh,
                task_names_en,
                _pretty_name(task.get("normalizedName"), str(task_id)),
            )

    key_requirements: list[dict[str, Any]] = []
    for item_id, map_ids in _key_ids(raw_task).items():
        item = items.get(item_id, {})
        if not isinstance(item, dict):
            item = {}
        item_types = item.get("types")
        if isinstance(item_types, list) and item_types and "keys" not in item_types:
            continue
        name = _item_name(item_id, item, item_names_zh, item_names_en)
        if not name or name.startswith("未知钥匙"):
            continue
        methods = _acquisition_methods(
            item_id,
            item,
            items,
            item_names_zh,
            item_names_en,
            trader_names,
            barters,
            task_names,
        )
        key_requirements.append(
            {
                "name": name,
                "item_id": item_id,
                "item_kind": "key",
                "map_ids": sorted(map_ids),
                "source_url": f"https://tarkov.dev/item/{item_id}",
                "image_url": str(item.get("iconLink") or f"https://assets.tarkov.dev/{item_id}-icon.webp"),
                "acquisition_methods": methods,
                "map_points": [],
            }
        )

    prerequisites: list[dict[str, Any]] = []
    raw_requirements = raw_task.get("taskRequirements")
    if isinstance(raw_requirements, list):
        for requirement in raw_requirements:
            if not isinstance(requirement, dict):
                continue
            required_task_id = str(requirement.get("task") or "")
            if required_task_id:
                prerequisites.append(
                    {
                        "task_id": required_task_id,
                        "text": task_names.get(required_task_id, f"前置任务 {required_task_id}"),
                    }
                )

    task_id = str(raw_task.get("id") or "")
    return {
        "objectives": objectives,
        "prerequisites": prerequisites,
        "key_requirements": key_requirements,
        "map_points": map_points,
        "source_url": f"https://tarkov.dev/task/{task_id}" if TASK_ID_PATTERN.fullmatch(task_id) else "",
        "map_ids": sorted({str(map_id).lower() for objective in raw_objectives or []
                           if isinstance(objective, dict)
                           for map_id in (objective.get("maps") or [])
                           if isinstance(map_id, str) and TASK_ID_PATTERN.fullmatch(map_id)}),
    }


def fetch_tarkov_dev_task_detail(source_task_id: str, game_mode: str = "pve") -> dict[str, Any]:
    if game_mode not in SUPPORTED_GAME_MODES:
        raise CatalogError("Tarkov.dev 不支持该游戏模式的任务详情。")
    if not TASK_ID_PATTERN.fullmatch(source_task_id):
        raise CatalogError("任务 ID 格式无效。")
    source_task_id = source_task_id.lower()
    names = ("tasks", "tasks_zh", "tasks_en", "traders", "traders_zh", "traders_en", "items", "items_zh", "items_en", "barters")
    documents = {name: _document(f"{game_mode}/{name}") for name in names}
    tasks = _data(documents["tasks"], "tasks")
    traders = _data(documents["traders"])
    items = _data(documents["items"], "items")
    barters = _data(documents["barters"])
    if not isinstance(tasks, dict) or not isinstance(traders, dict) or not isinstance(items, dict):
        raise CatalogError("Tarkov.dev 返回的任务详情依赖数据结构无效。")
    raw_task = tasks.get(source_task_id)
    if not isinstance(raw_task, dict):
        raise CatalogError("Tarkov.dev 任务目录中找不到该任务。")
    map_points: list[dict[str, Any]] = []
    try:
        map_points = fetch_tarkov_dev_task_map_points(
            raw_task,
            _data(documents["tasks_zh"]) or {},
            _data(documents["tasks_en"]) or {},
            game_mode,
        )
    except CatalogError:
        map_points = []
    result = _task_details(
        raw_task,
        _data(documents["tasks_zh"]) or {},
        _data(documents["tasks_en"]) or {},
        tasks,
        traders,
        _data(documents["traders_zh"]) or {},
        _data(documents["traders_en"]) or {},
        items,
        _data(documents["items_zh"]) or {},
        _data(documents["items_en"]) or {},
        barters if isinstance(barters, list) else [],
        map_points,
    )
    if not result["objectives"]:
        raise CatalogError("Tarkov.dev 没有为该任务提供可用目标。")
    return result
