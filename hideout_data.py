from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from diagnostics import log_event
from storage import default_database_path


SOURCE_ROOT = "https://json.tarkov.dev/pve"
SOURCE_URL = f"{SOURCE_ROOT}/hideout"
CACHE_TTL = timedelta(hours=12)
HIDEOUT_CACHE_SCHEMA_VERSION = 2
MAX_RESPONSE_BYTES = 24_000_000
USER_AGENT = "EFTTaskAssistant/0.1 (local hideout planner)"
_CACHE_LOCK = threading.Lock()


def _cache_path() -> Path:
    return default_database_path().parent / "public-data" / "hideout-pve.json"


def _request_json(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=25) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise RuntimeError(f"无法读取藏身处资料：{error}") from error
    if len(body) > MAX_RESPONSE_BYTES:
        raise RuntimeError("藏身处资料超过大小限制。")
    try:
        result = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("藏身处资料格式无效。") from error
    if not isinstance(result, dict):
        raise RuntimeError("藏身处资料结构无效。")
    return result


def _item_name(item_id: str, items: dict[str, Any]) -> str:
    localized = items.get(f"{item_id} Name")
    if isinstance(localized, str) and localized.strip():
        return localized.strip()
    return f"未知物品（{item_id}）"


def _found_in_raid(attributes: Any) -> bool:
    if isinstance(attributes, dict):
        return bool(attributes.get("foundInRaid", False))
    return bool(re.search(r"foundInRaid\s*[=:]\s*true", str(attributes), re.IGNORECASE))


def _normalize_catalog(
    hideout_payload: dict[str, Any],
    names_payload: dict[str, Any],
    items_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    stations = hideout_payload.get("data")
    translations = names_payload.get("data")
    items = items_payload.get("data")
    if not isinstance(stations, dict) or not isinstance(translations, dict) or not isinstance(items, dict):
        raise RuntimeError("藏身处数据缺少 PvE 升级、简中名称或物品信息。")

    result: list[dict[str, Any]] = []
    for station_id, station in stations.items():
        if not isinstance(station, dict):
            continue
        raw_levels = station.get("levels", [])
        if not isinstance(raw_levels, list):
            continue
        levels: list[dict[str, Any]] = []
        for raw_level in raw_levels:
            if not isinstance(raw_level, dict):
                continue
            try:
                level = int(raw_level.get("level", 0))
            except (TypeError, ValueError):
                continue
            if level <= 0:
                continue
            requirements = raw_level.get("itemRequirements", [])
            costs: list[dict[str, Any]] = []
            if isinstance(requirements, list):
                for requirement in requirements:
                    if not isinstance(requirement, dict):
                        continue
                    item_id = str(requirement.get("item", "")).strip()
                    try:
                        count = int(requirement.get("count", 0))
                    except (TypeError, ValueError):
                        continue
                    if not item_id or count <= 0:
                        continue
                    costs.append(
                        {
                            "item_id": item_id,
                            "name": _item_name(item_id, items),
                            "count": count,
                            "found_in_raid": _found_in_raid(requirement.get("attributes")),
                        }
                    )
            station_requirements: list[dict[str, Any]] = []
            raw_station_requirements = raw_level.get("stationLevelRequirements", [])
            if isinstance(raw_station_requirements, list):
                for requirement in raw_station_requirements:
                    if not isinstance(requirement, dict):
                        continue
                    required_station_id = str(requirement.get("station", "")).strip()
                    try:
                        required_level = int(requirement.get("level", 0))
                    except (TypeError, ValueError):
                        continue
                    if required_station_id and required_level > 0:
                        station_requirements.append(
                            {"station_id": required_station_id, "level": required_level}
                        )
            levels.append(
                {"level": level, "items": costs, "station_requirements": station_requirements}
            )
        if not levels:
            continue
        station_name_key = str(station.get("name", ""))
        station_name = translations.get(station_name_key)
        if not isinstance(station_name, str) or not station_name.strip():
            station_name = str(station.get("normalizedName", station_id)).replace("-", " ").title()
        result.append(
            {
                "id": str(station_id),
                "name": station_name.strip(),
                "image_url": str(station.get("imageLink", "")),
                "levels": sorted(levels, key=lambda entry: entry["level"]),
            }
        )
    if not result:
        raise RuntimeError("PvE 藏身处目录中没有有效设施。")
    return sorted(result, key=lambda station: (station["name"], station["id"]))


def _read_cache(path: Path) -> dict[str, Any] | None:
    try:
        cache = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    if not isinstance(cache, dict) or not isinstance(cache.get("stations"), list):
        return None
    return cache


def _fresh_enough(cache: dict[str, Any]) -> bool:
    if cache.get("schema_version") != HIDEOUT_CACHE_SCHEMA_VERSION:
        return False
    try:
        fetched_at = datetime.fromisoformat(str(cache.get("fetched_at", "")))
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return datetime.now(timezone.utc) - fetched_at < CACHE_TTL


def get_hideout_catalog(force_refresh: bool = False) -> dict[str, Any]:
    with _CACHE_LOCK:
        cache_path = _cache_path()
        cached = _read_cache(cache_path)
        if cached and _fresh_enough(cached) and not force_refresh:
            return {**cached, "cache_status": "fresh", "source_url": SOURCE_URL}
        try:
            hideout_payload = _request_json(f"{SOURCE_ROOT}/hideout")
            names_payload = _request_json(f"{SOURCE_ROOT}/hideout_zh")
            items_payload = _request_json(f"{SOURCE_ROOT}/items_zh")
            catalog = {
                "schema_version": HIDEOUT_CACHE_SCHEMA_VERSION,
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "stations": _normalize_catalog(hideout_payload, names_payload, items_payload),
            }
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = cache_path.with_suffix(".tmp")
            temporary_path.write_text(
                json.dumps(catalog, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            temporary_path.replace(cache_path)
            log_event("hideout_catalog_refreshed", station_count=len(catalog["stations"]))
            return {**catalog, "cache_status": "fresh", "source_url": SOURCE_URL}
        except (RuntimeError, OSError) as error:
            if cached:
                log_event(
                    "hideout_catalog_refresh_failed",
                    level=logging.WARNING,
                    error=str(error),
                    using_cached_data=True,
                )
                return {
                    **cached,
                    "cache_status": "stale",
                    "source_url": SOURCE_URL,
                    "warning": "在线数据暂不可用，当前显示上次缓存的 PvE 资料。",
                }
            raise RuntimeError(str(error)) from error
