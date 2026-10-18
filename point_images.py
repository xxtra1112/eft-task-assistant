"""Small, reviewed photo supplements; Tarkov.dev remains the coordinate source.

No name matching, nearest-neighbour matching or legacy point imports. New records
require checking the task, exact waypoint, floor and actual photo contents.
"""
from __future__ import annotations

import math
import re
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit

from catalog import CatalogError, fetch_eftarkov_map_data


_FACTORY = "55f2d3fd4bdc2d5f408b4567"
_PHOTO_ROOT = "https://www.eftarkov.com/uploads/infoImg/"
VERIFIED_POINT_PHOTOS = (
    {
        # Postman Pat 1: ground-floor messenger hut, including the dead messenger.
        # Source marker description exactly agrees with the current objective;
        # three reviewed photos show approach, hut entrance and body/letter site.
        "task_id": "59675ea386f77414b32bded2",
        "map_id": _FACTORY,
        "point_id": "tarkovdev-f039b124e11ed79a035a19c5",
        "zone_id": "possible-0-0",
        "floor_key": "Ground_Floor",
        "position_percent": (34.46322767247915, 68.04280863157895),
        "legacy_marker_id": "6aa19485e1d74518213b9f01",
        "legacy_floor_key": "1",
        "legacy_position": (583.804, 1058.623),
        "legacy_description": "在工厂找到死去的信使，并获取信件",
        "image_urls": tuple(_PHOTO_ROOT + name + ".webp" for name in (
            "202609100116201877", "202609100116255129", "202609100116285511",
        )),
        "reviewed_at": "2026-10-18",
    },
    {
        # Delivery from the Past: Gate 3 second-floor metal break-room approach.
        # This is the Factory stash, not the Customs package collection point.
        "task_id": "59674eb386f774539f14813a",
        "map_id": _FACTORY,
        "point_id": "tarkovdev-71f5e214041bba81a3b71b76",
        "zone_id": "zone-case_extraction",
        "floor_key": "Second_Floor",
        "position_percent": (20.151630022744506, 24.74385964912281),
        "legacy_marker_id": "6aa18caf3903cea64b3edd01",
        "legacy_floor_key": "2",
        "legacy_position": (394.556, 426.520),
        "legacy_description": "将包裹藏匿在工厂 3 号门旁的二层铁皮休息室内",
        "image_urls": (_PHOTO_ROOT + "202609100043125347.webp",),
        "reviewed_at": "2026-10-18",
    },
)


def _same_position(actual: tuple[Any, Any], expected: tuple[float, float]) -> bool:
    try:
        return all(math.isfinite(float(a)) and abs(float(a) - b) <= 0.000001
                   for a, b in zip(actual, expected))
    except (TypeError, ValueError, OverflowError):
        return False


def _safe_photo_url(value: Any) -> bool:
    try:
        url = urlsplit(str(value))
        return (
            url.scheme == "https" and url.netloc == "www.eftarkov.com"
            and not url.query and not url.fragment
            and bool(re.fullmatch(r"/uploads/infoImg/[A-Za-z0-9_-]+\.(?:webp|png|jpe?g)", url.path, re.I))
        )
    except ValueError:
        return False


@lru_cache(maxsize=8)
def _source_map(map_id: str, game_mode: str) -> dict[str, Any] | None:
    # Use the existing HTTPS/robots checks. Cache failure too: a denied/unavailable
    # source is not repeatedly requested by automatic UI polling in this process.
    try:
        return fetch_eftarkov_map_data(map_id, game_mode)
    except CatalogError:
        return None


def supplement_verified_point_images(
    task_id: str, points: list[dict[str, Any]], game_mode: str = "pve",
) -> list[dict[str, Any]]:
    """Return supplemental images without changing IDs, coordinates or inputs.

    Only PvE has been checked. Unknown modes/points, changed coordinates, missing
    source markers and unavailable photos stay empty; upstream photos win if any.
    """
    records = [r for r in VERIFIED_POINT_PHOTOS if r["task_id"] == task_id]
    if game_mode != "pve" or not records:
        return points
    result = []
    for point in points:
        if point.get("source_provider") != "tarkov.dev" or point.get("source_image_urls"):
            result.append(point)
            continue
        matches = [r for r in records if (
            point.get("id") == r["point_id"] and point.get("map_id") == r["map_id"]
            and point.get("zone_id") == r["zone_id"] and point.get("floor_key") == r["floor_key"]
            and _same_position((point.get("x_percent"), point.get("y_percent")), r["position_percent"])
        )]
        if len(matches) != 1:
            result.append(point)
            continue
        record = matches[0]
        config = _source_map(record["map_id"], game_mode)
        source_markers = [m for m in (config or {}).get("markers", [])
                          if m.get("id") == record["legacy_marker_id"]]
        if not config or config.get("map_id") != record["map_id"] or len(source_markers) != 1:
            result.append(point)
            continue
        marker = source_markers[0]
        if (marker.get("task_id") != task_id or marker.get("map_id") != record["map_id"]
                or marker.get("floor_key") != record["legacy_floor_key"]
                or marker.get("description") != record["legacy_description"]
                or not _same_position((marker.get("x"), marker.get("y")), record["legacy_position"])):
            result.append(point)
            continue
        current_urls = marker.get("info_image_urls") or []
        images = [url for url in record["image_urls"] if _safe_photo_url(url) and url in current_urls]
        if not images:
            result.append(point)
            continue
        result.append({
            **point,
            "source_image_urls": images,
            "source_image_provider": "eftarkov.com",
            "source_image_page_url": f"https://www.eftarkov.com/map/{record['map_id']}?marker={record['legacy_marker_id']}",
            "source_image_marker_id": record["legacy_marker_id"],
            "source_image_reviewed_at": record["reviewed_at"],
        })
    return result
