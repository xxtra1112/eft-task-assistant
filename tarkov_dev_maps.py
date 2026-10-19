from __future__ import annotations

import hashlib
import json
import math
import re
import threading
import time
import xml.etree.ElementTree as ET
from functools import lru_cache
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from catalog import CatalogError


TARKOV_DEV_JSON_ROOT = "https://json.tarkov.dev"
TARKOV_DEV_SITE_ROOT = "https://tarkov.dev"
TARKOV_DEV_MAP_CONFIG_URL = "https://raw.githubusercontent.com/the-hideout/tarkov-dev/main/src/data/maps.json"
TARKOV_DEV_SOURCE = "Tarkov.dev JSON API and map data"
USER_AGENT = "EFTTaskAssistant/1.1 (local map data client)"
SUPPORTED_GAME_MODES = {"pve", "regular", "pvp-season"}
MAX_JSON_BYTES = 30_000_000
MAX_SVG_BYTES = 20_000_000
CACHE_TTL_SECONDS = 12 * 60 * 60
MAP_ID_PATTERN = re.compile(r"^[0-9a-f]{24}$", re.IGNORECASE)
SVG_PATH_PATTERN = re.compile(r"^/maps/svg/[A-Za-z0-9_.-]+\.svg$")
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_LOCK = threading.RLock()
_SVG_NAMESPACE = "http://www.w3.org/2000/svg"

_FLOOR_NAMES_ZH = {
    "Basement": "地下室",
    "Bunkers": "地下掩体",
    "First_Floor": "一层",
    "First_Level": "一层",
    "Fourth_Floor": "四层",
    "Ground_Floor": "地面层",
    "Ground_Level": "地面层",
    "Second_Floor": "二层",
    "Second_Level": "二层",
    "Third_Floor": "三层",
    "Third_Level": "三层",
    "Fifth_Floor": "五层",
    "Underground_Level": "地下层",
    "Technical_Level": "技术层",
}


def _request_bytes(url: str, max_response_bytes: int, accept: str) -> bytes:
    parsed = urlparse(url)
    allowed = (
        parsed.scheme == "https"
        and (
            parsed.hostname == "json.tarkov.dev"
            and re.fullmatch(r"/(?:pve|regular|pvp-season)/maps(?:_(?:zh|en))?", parsed.path)
            or parsed.hostname == "raw.githubusercontent.com"
            and parsed.path == "/the-hideout/tarkov-dev/main/src/data/maps.json"
            or parsed.hostname == "assets.tarkov.dev"
            and SVG_PATH_PATTERN.fullmatch(parsed.path)
        )
    )
    if not allowed:
        raise CatalogError("Tarkov.dev 地图资源 URL 无效。")
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    try:
        with urlopen(request, timeout=35) as response:
            final_url = urlparse(response.geturl())
            if final_url.scheme != "https" or final_url.hostname != parsed.hostname:
                raise CatalogError("Tarkov.dev 地图资源发生了不安全的重定向。")
            body = response.read(max_response_bytes + 1)
    except HTTPError as error:
        raise CatalogError(f"Tarkov.dev 地图服务返回 HTTP {error.code}。") from error
    except (URLError, TimeoutError, OSError) as error:
        raise CatalogError(f"无法连接 Tarkov.dev 地图服务：{error}") from error
    if len(body) > max_response_bytes:
        raise CatalogError("Tarkov.dev 地图资源超过大小限制。")
    return body


def _cached_json(url: str) -> Any:
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(url)
        if cached and now - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]
    body = _request_bytes(url, MAX_JSON_BYTES, "application/json")
    try:
        document = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CatalogError("Tarkov.dev 地图 JSON 格式无效。") from error
    with _CACHE_LOCK:
        _CACHE[url] = (time.monotonic(), document)
    return document


@lru_cache(maxsize=3)
def _map_context(game_mode: str) -> dict[str, Any]:
    if game_mode not in SUPPORTED_GAME_MODES:
        raise CatalogError("Tarkov.dev 不支持该游戏模式的地图目录。")
    base_url = f"{TARKOV_DEV_JSON_ROOT}/{game_mode}"
    maps_document = _cached_json(f"{base_url}/maps")
    translations_zh = _cached_json(f"{base_url}/maps_zh")
    translations_en = _cached_json(f"{base_url}/maps_en")
    maps_payload = maps_document.get("data", {}).get("maps") if isinstance(maps_document, dict) else None
    translations_zh = translations_zh.get("data") if isinstance(translations_zh, dict) else None
    translations_en = translations_en.get("data") if isinstance(translations_en, dict) else None
    if not isinstance(maps_payload, dict) or not isinstance(translations_zh, dict):
        raise CatalogError("Tarkov.dev 返回的地图目录结构无效。")
    if not isinstance(translations_en, dict):
        translations_en = {}

    map_config = _cached_json(TARKOV_DEV_MAP_CONFIG_URL)
    if not isinstance(map_config, list) or not map_config:
        raise CatalogError("Tarkov.dev 地图元数据结构无效。")
    configs_by_name: dict[str, dict[str, Any]] = {}
    for entry in map_config:
        if not isinstance(entry, dict) or not isinstance(entry.get("normalizedName"), str):
            continue
        for viewer in entry.get("maps", []):
            if not isinstance(viewer, dict) or viewer.get("projection") != "interactive":
                continue
            for normalized_name in [entry["normalizedName"], *viewer.get("altMaps", [])]:
                if isinstance(normalized_name, str):
                    configs_by_name[normalized_name.casefold()] = {"entry": entry, "viewer": viewer}

    maps_by_id: dict[str, dict[str, Any]] = {}
    entries: list[dict[str, Any]] = []
    for map_id, raw_map in maps_payload.items():
        if not MAP_ID_PATTERN.fullmatch(str(map_id)) or not isinstance(raw_map, dict):
            continue
        normalized_name = str(raw_map.get("normalizedName") or "").strip().casefold()
        metadata = configs_by_name.get(normalized_name)
        if not metadata:
            continue
        viewer = metadata["viewer"]
        svg_path = urlparse(str(viewer.get("svgPath") or ""))
        if (
            svg_path.scheme != "https"
            or svg_path.hostname != "assets.tarkov.dev"
            or not SVG_PATH_PATTERN.fullmatch(svg_path.path)
        ):
            continue
        localized_name = _localized(raw_map.get("name"), translations_zh, translations_en)
        if not localized_name:
            localized_name = str(raw_map.get("normalizedName") or map_id).replace("-", " ").title()
        english_name = _localized(raw_map.get("name"), {}, translations_en) or localized_name
        path = str(metadata["entry"].get("primaryPath") or f"/map/{normalized_name}")
        if not path.startswith("/map/"):
            path = f"/map/{normalized_name}"
        record = {
            "map_id": str(map_id).lower(),
            "name": localized_name,
            "name_en": english_name,
            "normalized_name": normalized_name,
            "source_url": f"{TARKOV_DEV_SITE_ROOT}{path}",
            "map_author": str(viewer.get("author") or ""),
            "map_author_url": str(viewer.get("authorLink") or ""),
            "map_license": "CC BY-NC-SA 4.0",
            "map_license_url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
        }
        maps_by_id[record["map_id"]] = {
            "raw": raw_map,
            "metadata": metadata,
            "index": record,
        }
        entries.append(record)
    if not entries:
        raise CatalogError("Tarkov.dev 没有返回可显示的交互地图。")
    return {
        "maps_by_id": maps_by_id,
        "map_index": entries,
        "translations_zh": translations_zh,
        "translations_en": translations_en,
    }


def _localized(value: Any, translations_zh: dict[str, Any], translations_en: dict[str, Any]) -> str:
    key = str(value or "").strip()
    if not key:
        return ""
    for translations in (translations_zh, translations_en):
        translated = translations.get(key)
        if isinstance(translated, str) and translated.strip() and translated.strip() != key:
            return translated.strip()
    return key


def _localized_pair(
    value: Any, translations_zh: dict[str, Any], translations_en: dict[str, Any]
) -> tuple[str, str]:
    return (
        _localized(value, translations_zh, {}),
        _localized(value, {}, translations_en),
    )


def fetch_tarkov_dev_map_index(game_mode: str = "pve") -> list[dict[str, Any]]:
    context = _map_context(game_mode)
    return [dict(entry) for entry in context["map_index"]]


def _map_bounds(viewer: dict[str, Any]) -> list[list[float]]:
    bounds = viewer.get("svgBounds") or viewer.get("bounds")
    if (
        not isinstance(bounds, list)
        or len(bounds) != 2
        or any(not isinstance(corner, list) or len(corner) < 2 for corner in bounds)
    ):
        raise CatalogError("Tarkov.dev 地图没有有效的 SVG 地理边界。")
    try:
        parsed = [[float(corner[0]), float(corner[1])] for corner in bounds]
    except (TypeError, ValueError) as error:
        raise CatalogError("Tarkov.dev 地图边界坐标无效。") from error
    if not all(math.isfinite(value) for corner in parsed for value in corner):
        raise CatalogError("Tarkov.dev 地图边界坐标无效。")
    return parsed


def _rotation(viewer: dict[str, Any]) -> float:
    try:
        rotation = float(viewer.get("coordinateRotation") or 0)
    except (TypeError, ValueError):
        return 0.0
    return rotation if math.isfinite(rotation) else 0.0


def _transform(viewer: dict[str, Any]) -> tuple[float, float, float, float]:
    values = viewer.get("transform")
    if not isinstance(values, list) or len(values) < 4:
        return (1.0, 0.0, 1.0, 0.0)
    try:
        parsed = tuple(float(value) for value in values[:4])
    except (TypeError, ValueError):
        return (1.0, 0.0, 1.0, 0.0)
    if not all(math.isfinite(value) for value in parsed) or parsed[0] == 0 or parsed[2] == 0:
        return (1.0, 0.0, 1.0, 0.0)
    return parsed


def _project_xy(x: float, z: float, viewer: dict[str, Any]) -> tuple[float, float]:
    angle = math.radians(_rotation(viewer))
    rotated_x = x * math.cos(angle) - z * math.sin(angle)
    rotated_z = x * math.sin(angle) + z * math.cos(angle)
    scale_x, offset_x, scale_z, offset_z = _transform(viewer)
    return scale_x * rotated_x + offset_x, -scale_z * rotated_z + offset_z


def _projected_bounds(viewer: dict[str, Any]) -> tuple[float, float, float, float]:
    bounds = _map_bounds(viewer)
    corners = [
        _project_xy(x, z, viewer)
        for x in (bounds[0][0], bounds[1][0])
        for z in (bounds[0][1], bounds[1][1])
    ]
    min_x = min(point[0] for point in corners)
    max_x = max(point[0] for point in corners)
    min_y = min(point[1] for point in corners)
    max_y = max(point[1] for point in corners)
    if max_x <= min_x or max_y <= min_y:
        raise CatalogError("Tarkov.dev 地图投影边界无效。")
    return min_x, min_y, max_x, max_y


def project_map_position(position: dict[str, Any], viewer: dict[str, Any]) -> tuple[float, float] | None:
    if not isinstance(position, dict):
        return None
    try:
        x = float(position["x"])
        z = float(position["z"])
    except (KeyError, TypeError, ValueError):
        return None
    if not math.isfinite(x) or not math.isfinite(z):
        return None
    min_x, min_y, max_x, max_y = _projected_bounds(viewer)
    point_x, point_y = _project_xy(x, z, viewer)
    return ((point_x - min_x) / (max_x - min_x) * 100, (point_y - min_y) / (max_y - min_y) * 100)


def _position_in_extent_bounds(x: float, z: float, bounds: Any) -> bool:
    if not isinstance(bounds, list):
        return False
    for area in bounds:
        if not isinstance(area, list) or len(area) < 2:
            continue
        first, second = area[0], area[1]
        if not isinstance(first, list) or not isinstance(second, list) or len(first) < 2 or len(second) < 2:
            continue
        try:
            x_min, x_max = sorted((float(first[0]), float(second[0])))
            z_min, z_max = sorted((float(first[1]), float(second[1])))
        except (TypeError, ValueError):
            continue
        if x_min <= x <= x_max and z_min <= z <= z_max:
            return True
    return False


def _floor_for_position(
    viewer: dict[str, Any],
    floors: list[dict[str, Any]],
    position: dict[str, Any],
    top: Any = None,
    bottom: Any = None,
) -> dict[str, Any]:
    base_floor = floors[0]
    try:
        height = float(position.get("y", 0))
        marker_top = float(top) if top is not None else height
        marker_bottom = float(bottom) if bottom is not None else height
        x = float(position.get("x"))
        z = float(position.get("z"))
    except (TypeError, ValueError):
        return base_floor
    for layer in viewer.get("layers", []):
        if not isinstance(layer, dict) or not layer.get("svgLayer"):
            continue
        floor = next((entry for entry in floors if entry["key"] == layer["svgLayer"]), None)
        if floor is None:
            continue
        for extent in layer.get("extents", []):
            if not isinstance(extent, dict):
                continue
            height_range = extent.get("height")
            if not isinstance(height_range, list) or len(height_range) < 2:
                continue
            try:
                lower, upper = float(height_range[0]), float(height_range[1])
            except (TypeError, ValueError):
                continue
            if marker_top < lower or marker_bottom >= upper:
                continue
            extent_bounds = extent.get("bounds")
            if extent_bounds is not None and not _position_in_extent_bounds(x, z, extent_bounds):
                continue
            return floor
    return base_floor


def _floor_display_name(layer_id: str, layer_name: str, english: bool) -> str:
    if english:
        return layer_name or layer_id.replace("_", " ")
    localized = _FLOOR_NAMES_ZH.get(layer_id)
    if localized:
        return localized
    normalized_name = re.sub(r"\s+", " ", layer_name).strip().casefold()
    known_names = {
        "ground floor": "地面层",
        "ground level": "地面层",
        "first floor": "一层",
        "first level": "一层",
        "second floor": "二层",
        "second level": "二层",
        "third floor": "三层",
        "third level": "三层",
        "fourth floor": "四层",
        "fifth floor": "五层",
        "basement": "地下室",
        "underground": "地下层",
        "bunkers": "地下掩体",
    }
    if normalized_name in known_names:
        return known_names[normalized_name]
    ordinal_floor = re.fullmatch(r"(\d+)(?:st|nd|rd|th) floor", normalized_name)
    if ordinal_floor:
        number = int(ordinal_floor.group(1))
        return f"第{number}层"
    return layer_name or layer_id.replace("_", " ")


def _floor_records(viewer: dict[str, Any]) -> list[dict[str, Any]]:
    min_x, min_y, max_x, max_y = _projected_bounds(viewer)
    width = max_x - min_x
    height = max_y - min_y
    svg_url = str(viewer["svgPath"])
    base_layer_id = str(viewer.get("svgLayer") or "")
    if not base_layer_id:
        raise CatalogError("Tarkov.dev 地图没有默认 SVG 楼层。")
    layers = [
        {
            "key": base_layer_id,
            "name": _floor_display_name(base_layer_id, "", False),
            "name_en": _floor_display_name(base_layer_id, "", True),
            "svg_layer": base_layer_id,
            "src": svg_url,
            "width": width,
            "height": height,
            "is_default": True,
        }
    ]
    seen = {base_layer_id}
    for layer in viewer.get("layers", []):
        if not isinstance(layer, dict):
            continue
        layer_id = str(layer.get("svgLayer") or "")
        if not layer_id or layer_id in seen:
            continue
        seen.add(layer_id)
        layer_name = str(layer.get("name") or "")
        layers.append(
            {
                "key": layer_id,
                "name": _floor_display_name(layer_id, layer_name, False),
                "name_en": _floor_display_name(layer_id, layer_name, True),
                "svg_layer": layer_id,
                "src": svg_url,
                "width": width,
                "height": height,
                "is_default": False,
            }
        )
    return layers


def _annotation_labels() -> dict[str, str]:
    return {
        "location": "地图地点",
        "pmc-exit": "PMC撤离点",
        "scav-exit": "SCAV撤离点",
        "unknown-exit": "阵营未确认的撤离点",
        "transfer": "转移点",
    }


def _annotation_labels_en() -> dict[str, str]:
    return {
        "location": "Map location",
        "pmc-exit": "PMC extract",
        "scav-exit": "Scav extract",
        "unknown-exit": "Faction unconfirmed extract",
        "transfer": "Transit point",
    }


def _stable_id(*parts: Any) -> str:
    content = "\0".join(str(part) for part in parts)
    return "tarkovdev-" + hashlib.sha256(content.encode("utf-8")).hexdigest()[:24]


def _make_annotation(
    map_record: dict[str, Any],
    viewer: dict[str, Any],
    floors: list[dict[str, Any]],
    title: str,
    title_en: str,
    position: dict[str, Any],
    categories: list[str],
    source_id: str,
    description: str = "",
    description_en: str = "",
    top: Any = None,
    bottom: Any = None,
) -> dict[str, Any] | None:
    coordinates = project_map_position(position, viewer)
    if coordinates is None or not all(0 <= value <= 100 for value in coordinates):
        return None
    floor = _floor_for_position(viewer, floors, position, top, bottom)
    labels = _annotation_labels()
    categories = [category for category in categories if category in labels]
    if not categories:
        return None
    category_labels = {category: labels[category] for category in categories}
    category_labels_en = {category: _annotation_labels_en()[category] for category in categories}
    if "pmc-exit" in categories and "scav-exit" in categories:
        annotation_label = "PMC / SCAV撤离点"
    else:
        annotation_label = labels[categories[0]]
    return {
        "id": _stable_id(map_record["map_id"], "annotation", source_id, title, *coordinates),
        "categories": categories,
        "category_labels": category_labels,
        "category_labels_en": category_labels_en,
        "icon_urls": {},
        "title": title,
        "title_en": title_en,
        "floor_key": floor["key"],
        "floor_name": floor["name"],
        "floor_name_en": floor["name_en"],
        "description": description,
        "description_en": description_en,
        "annotation_label_en": (
            "PMC / Scav extract"
            if "pmc-exit" in categories and "scav-exit" in categories
            else category_labels_en[categories[0]]
        ),
        "x_percent": coordinates[0],
        "y_percent": coordinates[1],
        "source_url": map_record["source_url"],
        "source_page_url": map_record["source_url"],
        "source_page_urls": [map_record["source_url"]],
        "source_image_urls": [],
        "display_title": True,
    }


def _map_annotations(
    raw_map: dict[str, Any],
    metadata: dict[str, Any],
    map_record: dict[str, Any],
    floors: list[dict[str, Any]],
    translations_zh: dict[str, Any],
    translations_en: dict[str, Any],
) -> tuple[list[dict[str, Any]], int]:
    viewer = metadata["viewer"]
    annotations: list[dict[str, Any]] = []
    out_of_bounds = 0
    labels = viewer.get("labels", [])
    for index, label in enumerate(labels):
        if not isinstance(label, dict) or not isinstance(label.get("position"), list) or len(label["position"]) < 2:
            continue
        try:
            x, z = float(label["position"][0]), float(label["position"][1])
            if len(label["position"]) > 2:
                y = float(label["position"][2])
            elif label.get("top") is not None and label.get("bottom") is not None:
                y = (float(label["top"]) + float(label["bottom"])) / 2
            else:
                base_range = viewer.get("heightRange")
                y = sum(float(value) for value in base_range) / 2 if isinstance(base_range, list) and len(base_range) >= 2 else 0.0
        except (TypeError, ValueError):
            continue
        position = {"x": x, "y": y, "z": z}
        title, title_en = _localized_pair(label.get("text"), translations_zh, translations_en)
        if not title and not title_en:
            continue
        coordinates = project_map_position(position, viewer)
        if coordinates is None:
            continue
        if not all(0 <= value <= 100 for value in coordinates):
            out_of_bounds += 1
            continue
        annotation = _make_annotation(
            map_record,
            viewer,
            floors,
            title,
            title_en,
            position,
            ["location"],
            f"label-{index}",
            top=label.get("top"),
            bottom=label.get("bottom"),
        )
        if annotation:
            annotations.append(annotation)

    merged_exits: dict[tuple[Any, ...], dict[str, Any]] = {}
    for index, extract in enumerate(raw_map.get("extracts", [])):
        if not isinstance(extract, dict) or not isinstance(extract.get("position"), dict):
            continue
        faction = str(extract.get("faction") or "").strip().casefold()
        if faction in {"pmc", "usec", "bear"}:
            categories = ["pmc-exit"]
        elif faction in {"scav", "scavenger"}:
            categories = ["scav-exit"]
        elif faction in {"shared", "both", "all"}:
            categories = ["pmc-exit", "scav-exit"]
        else:
            categories = ["unknown-exit"]
        title, title_en = _localized_pair(extract.get("name"), translations_zh, translations_en)
        if not title and not title_en:
            continue
        coordinates = project_map_position(extract["position"], viewer)
        if coordinates is None:
            continue
        if not all(0 <= value <= 100 for value in coordinates):
            out_of_bounds += 1
            continue
        floor = _floor_for_position(viewer, floors, extract["position"], extract.get("top"), extract.get("bottom"))
        key = (floor["key"], re.sub(r"\s+", " ", title).casefold(), round(coordinates[0], 2), round(coordinates[1], 2))
        annotation = merged_exits.get(key)
        if annotation is None:
            annotation = _make_annotation(
                map_record,
                viewer,
                floors,
                title,
                title_en,
                extract["position"],
                categories,
                f"extract-{extract.get('id') or index}",
                _localized_pair(extract.get("description"), translations_zh, translations_en)[0],
                _localized_pair(extract.get("description"), translations_zh, translations_en)[1],
                extract.get("top"),
                extract.get("bottom"),
            )
            if annotation is None:
                continue
            merged_exits[key] = annotation
        else:
            annotation["categories"] = sorted(set(annotation["categories"] + categories))
            annotation["category_labels"] = {category: _annotation_labels()[category] for category in annotation["categories"]}
            annotation["category_labels_en"] = {
                category: _annotation_labels_en()[category] for category in annotation["categories"]
            }
            annotation["annotation_label"] = (
                "PMC / SCAV撤离点"
                if "pmc-exit" in annotation["categories"] and "scav-exit" in annotation["categories"]
                else _annotation_labels()[annotation["categories"][0]]
            )
            annotation["annotation_label_en"] = (
                "PMC / Scav extract"
                if "pmc-exit" in annotation["categories"] and "scav-exit" in annotation["categories"]
                else _annotation_labels_en()[annotation["categories"][0]]
            )
    annotations.extend(merged_exits.values())

    for index, transit in enumerate(raw_map.get("transits", [])):
        if not isinstance(transit, dict) or not isinstance(transit.get("position"), dict):
            continue
        coordinates = project_map_position(transit["position"], viewer)
        if coordinates is None:
            continue
        if not all(0 <= value <= 100 for value in coordinates):
            out_of_bounds += 1
            continue
        title, title_en = _localized_pair(transit.get("description"), translations_zh, translations_en)
        if not title and not title_en:
            destination = str(transit.get("map") or "")
            destination_zh = _localized(f"{destination} Name", translations_zh, {}) if destination else ""
            destination_en = _localized(f"{destination} Name", {}, translations_en) if destination else ""
            title = f"转移至 {destination_zh or destination}" if destination else "转移点"
            title_en = f"Transit to {destination_en or destination}" if destination else "Transit point"
        annotation = _make_annotation(
            map_record,
            viewer,
            floors,
            title,
            title_en,
            transit["position"],
            ["transfer"],
            f"transit-{transit.get('id') or index}",
            top=transit.get("top"),
            bottom=transit.get("bottom"),
        )
        if annotation:
            annotations.append(annotation)
    for annotation in annotations:
        if "annotation_label" not in annotation:
            annotation["annotation_label"] = (
                "PMC / SCAV撤离点"
                if "pmc-exit" in annotation["categories"] and "scav-exit" in annotation["categories"]
                else _annotation_labels()[annotation["categories"][0]]
            )
        if "annotation_label_en" not in annotation:
            annotation["annotation_label_en"] = (
                "PMC / Scav extract"
                if "pmc-exit" in annotation["categories"] and "scav-exit" in annotation["categories"]
                else _annotation_labels_en()[annotation["categories"][0]]
            )
    return annotations, out_of_bounds


def fetch_tarkov_dev_map_data(map_id: str, game_mode: str = "pve") -> dict[str, Any]:
    if not MAP_ID_PATTERN.fullmatch(map_id):
        raise CatalogError("地图 ID 格式无效。")
    context = _map_context(game_mode)
    record = context["maps_by_id"].get(map_id.lower())
    if record is None:
        raise CatalogError("该地图不在 Tarkov.dev 交互地图目录中。")
    floors = _floor_records(record["metadata"]["viewer"])
    annotations, unplaced_annotation_count = _map_annotations(
        record["raw"],
        record["metadata"],
        record["index"],
        floors,
        context["translations_zh"],
        context["translations_en"],
    )
    return {
        "map_id": map_id.lower(),
        "name": record["index"]["name"],
        "name_en": record["index"]["name_en"],
        "normalized_name": record["index"]["normalized_name"],
        "map_author": record["index"]["map_author"],
        "map_author_url": record["index"]["map_author_url"],
        "map_license": record["index"]["map_license"],
        "map_license_url": record["index"]["map_license_url"],
        "floors": floors,
        "markers": [],
        "annotations": annotations,
        "unplaced_annotation_count": unplaced_annotation_count,
        "source_url": record["index"]["source_url"],
        "svg_url": str(record["metadata"]["viewer"]["svgPath"]),
        "svg_layer": str(record["metadata"]["viewer"].get("svgLayer") or ""),
        "viewer": record["metadata"]["viewer"],
        "raw": record["raw"],
    }


def _localized_objective(
    value: Any, task_names_zh: dict[str, Any], task_names_en: dict[str, Any]
) -> tuple[str, str]:
    key = str(value or "").strip()
    if not key:
        return "完成指定地点目标", "Complete the location objective"
    return _localized_pair(key, task_names_zh, task_names_en)


def fetch_tarkov_dev_task_map_points(
    raw_task: dict[str, Any],
    task_names_zh: dict[str, Any],
    task_names_en: dict[str, Any],
    game_mode: str = "pve",
) -> list[dict[str, Any]]:
    context = _map_context(game_mode)
    task_id = str(raw_task.get("id") or "").lower()
    if not MAP_ID_PATTERN.fullmatch(task_id):
        return []
    normalized_task = str(raw_task.get("normalizedName") or "").strip()
    points: list[dict[str, Any]] = []
    for objective_index, objective in enumerate(raw_task.get("objectives", [])):
        if not isinstance(objective, dict):
            continue
        objective_text, objective_text_en = _localized_objective(
            objective.get("description"), task_names_zh, task_names_en
        )
        objective_id = str(objective.get("id") or objective_index)
        locations: list[tuple[str, dict[str, Any], Any, Any, str]] = []
        for zone_index, zone in enumerate(objective.get("zones", [])):
            if isinstance(zone, dict) and isinstance(zone.get("position"), dict):
                locations.append((
                    str(zone.get("map") or "").lower(),
                    zone["position"],
                    zone.get("top"),
                    zone.get("bottom"),
                    f"zone-{zone.get('id') or zone_index}",
                ))
        for location_index, location in enumerate(objective.get("possibleLocations", [])):
            if not isinstance(location, dict):
                continue
            map_id = str(location.get("map") or "").lower()
            positions = location.get("positions", [])
            if isinstance(location.get("position"), dict):
                positions = [location["position"]]
            if isinstance(positions, dict):
                positions = [positions]
            if not isinstance(positions, list):
                continue
            for position_index, position in enumerate(positions):
                if isinstance(position, dict):
                    locations.append((
                        map_id,
                        position,
                        location.get("top"),
                        location.get("bottom"),
                        f"possible-{location_index}-{position_index}",
                    ))
        seen_points: set[tuple[Any, ...]] = set()
        for map_id, position, top, bottom, location_id in locations:
            map_record = context["maps_by_id"].get(map_id)
            if map_record is None:
                continue
            viewer = map_record["metadata"]["viewer"]
            coordinates = project_map_position(position, viewer)
            if coordinates is None or not all(0 <= value <= 100 for value in coordinates):
                continue
            try:
                coordinate_key = (
                    map_id,
                    round(float(position["x"]), 3),
                    round(float(position["y"]), 3),
                    round(float(position["z"]), 3),
                )
            except (KeyError, TypeError, ValueError):
                continue
            if coordinate_key in seen_points:
                continue
            seen_points.add(coordinate_key)
            floors = _floor_records(viewer)
            floor = _floor_for_position(viewer, floors, position, top, bottom)
            points.append(
                {
                    "id": _stable_id(task_id, objective_id, location_id, map_id, *coordinate_key[1:]),
                    "map_id": map_id,
                    "map_name": map_record["index"]["name"],
                    "map_name_en": map_record["index"]["name_en"],
                    "floor_key": floor["key"],
                    "floor_name": floor["name"],
                    "floor_name_en": floor["name_en"],
                    "width": floor["width"],
                    "height": floor["height"],
                    "x_percent": coordinates[0],
                    "y_percent": coordinates[1],
                    "title": objective_text,
                    "title_en": objective_text_en,
                    "description": objective_text,
                    "description_en": objective_text_en,
                    "zone_id": location_id,
                    "source_url": map_record["index"]["source_url"],
                    "source_page_url": f"{TARKOV_DEV_SITE_ROOT}/task/{normalized_task}" if normalized_task else f"{TARKOV_DEV_SITE_ROOT}/tasks/",
                    "source_image_urls": [],
                    "source_provider": "tarkov.dev",
                    "task_normalized_name": normalized_task,
                }
            )
    return points


def _viewbox_dimensions(root: ET.Element) -> tuple[float, float]:
    view_box = root.get("viewBox") or root.get("viewbox")
    if not view_box:
        nested = next((child for child in root if child.tag.rsplit("}", 1)[-1] == "svg"), None)
        view_box = nested.get("viewBox") if nested is not None else None
    try:
        values = [float(value) for value in re.split(r"[\s,]+", str(view_box or "").strip())]
    except ValueError as error:
        raise CatalogError("Tarkov.dev SVG 地图没有有效的 viewBox。") from error
    if len(values) != 4 or values[2] <= 0 or values[3] <= 0 or not all(math.isfinite(value) for value in values):
        raise CatalogError("Tarkov.dev SVG 地图的 viewBox 无效。")
    return values[2], values[3]


def _selected_floor_svg(svg_bytes: bytes, map_data: dict[str, Any], floor: dict[str, Any]) -> bytes:
    try:
        root = ET.fromstring(svg_bytes)
    except ET.ParseError as error:
        raise CatalogError("Tarkov.dev 返回的地图 SVG 格式无效。") from error
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise CatalogError("Tarkov.dev 返回的资源不是 SVG 地图。")
    width, height = _viewbox_dimensions(root)
    root.set("width", f"{width:g}")
    root.set("height", f"{height:g}")
    root.set("preserveAspectRatio", "none")
    viewer = map_data["viewer"]
    base_layer = map_data["svg_layer"]
    active_layer = str(floor["svg_layer"])
    visible_layers = {base_layer, active_layer}
    for child in list(root):
        if child.tag.rsplit("}", 1)[-1] != "g" or not child.get("id"):
            continue
        group_id = child.get("id", "")
        keep_with = child.get("data-keep-with-group") or child.get("data-keepWithGroup")
        if group_id in visible_layers or keep_with in visible_layers:
            if active_layer != base_layer and group_id == base_layer:
                child.set("opacity", "0.32")
            continue
        root.remove(child)

    parent_by_child = {child: parent for parent in root.iter() for child in list(parent)}
    for element in list(root.iter()):
        name = element.tag.rsplit("}", 1)[-1].casefold()
        if name in {"script", "foreignobject"}:
            parent = parent_by_child.get(element)
            if parent is not None:
                parent.remove(element)
            continue
        for attribute in list(element.attrib):
            lowered = attribute.rsplit("}", 1)[-1].casefold()
            if lowered.startswith("on"):
                del element.attrib[attribute]
            elif lowered in {"href", "src"}:
                value = element.attrib[attribute].strip()
                if value and not value.startswith(("#", "data:image/")):
                    del element.attrib[attribute]
    ET.register_namespace("", _SVG_NAMESPACE)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


@lru_cache(maxsize=24)
def _fetch_tarkov_dev_map_floor_image(map_id: str, floor_key: str, game_mode: str) -> bytes:
    map_data = fetch_tarkov_dev_map_data(map_id, game_mode)
    floor = next((item for item in map_data["floors"] if item["key"] == floor_key), None)
    if floor is None:
        raise CatalogError("该地图没有对应的 Tarkov.dev 楼层。")
    svg_bytes = _request_bytes(map_data["svg_url"], MAX_SVG_BYTES, "image/svg+xml")
    return _selected_floor_svg(svg_bytes, map_data, floor)


def fetch_tarkov_dev_map_floor_image(map_id: str, floor_key: str, game_mode: str = "pve") -> bytes:
    if not MAP_ID_PATTERN.fullmatch(map_id):
        raise CatalogError("地图 ID 格式无效。")
    return _fetch_tarkov_dev_map_floor_image(map_id.lower(), str(floor_key), game_mode)
