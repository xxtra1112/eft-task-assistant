from __future__ import annotations

import hashlib
import html
import json
import re
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser
from typing import Any

from task_requirements import normalize_objective


EFTARKOV_ROOT = "https://www.eftarkov.com"
EFTARKOV_SOURCE = "eftarkov.com"
EFTARKOV_MODE = {"pve": "pve", "regular": "pvp"}
USER_AGENT = "EFTTaskAssistant/0.1 (local offline-first task catalog)"
MAX_PAGE_COUNT = 100
MAX_RESPONSE_BYTES = 1_500_000
PAGE_DELAY_SECONDS = 0.25
TASK_ID_PATTERN = re.compile(r"^[0-9a-f]{24}$", re.IGNORECASE)
KEY_ITEM_NAME_PATTERN = re.compile(r"(?:钥匙|(?<![A-Za-z])key(?:[\s-]?card)?(?![A-Za-z]))", re.IGNORECASE)
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
_PUBLIC_DATA_LOCK = threading.RLock()


def is_key_item_name(name: str) -> bool:
    return bool(KEY_ITEM_NAME_PATTERN.search(str(name or "")))


class CatalogError(RuntimeError):
    pass


@dataclass(frozen=True)
class CatalogBundle:
    game_mode: str
    source_version: str
    content_sha256: str
    tasks: list[dict[str, Any]]
    metadata: dict[str, Any]


@lru_cache(maxsize=1)
def _robots_parser() -> RobotFileParser:
    robots_url = urljoin(EFTARKOV_ROOT, "/robots.txt")
    body, _ = _request(robots_url)
    parser = RobotFileParser(robots_url)
    parser.parse(body.decode("utf-8", "replace").splitlines())
    return parser


def _assert_public_url_allowed(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "www.eftarkov.com":
        raise CatalogError("只允许读取 EFTarkov 的 HTTPS 公开页面。")
    if parsed.path == "/robots.txt":
        return
    if not _robots_parser().can_fetch(USER_AGENT, url):
        raise CatalogError(f"EFTarkov robots.txt 不允许读取此页面：{parsed.path}")


def _request(
    url: str,
    game_mode: str | None = None,
    *,
    max_response_bytes: int = MAX_RESPONSE_BYTES,
    accept: str = "text/html",
) -> tuple[bytes, dict[str, str]]:
    if urlparse(url).path != "/robots.txt":
        _assert_public_url_allowed(url)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": accept,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if game_mode in {"pve", "regular"}:
        headers["Cookie"] = f"tarkov_mode={'pve' if game_mode == 'pve' else 'pvp'}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=20) as response:
            body = response.read(max_response_bytes + 1)
            if len(body) > max_response_bytes:
                raise CatalogError("EFTarkov 页面超过大小限制，未导入。")
            return body, dict(response.headers.items())
    except HTTPError as error:
        raise CatalogError(f"EFTarkov 返回 HTTP {error.code}：{urljoin(EFTARKOV_ROOT, error.url)}") from error
    except (URLError, TimeoutError, OSError) as error:
        raise CatalogError(f"无法连接 EFTarkov：{error}") from error


def _check_robots(mode: str) -> None:
    parser = _robots_parser()
    paths = [
        urljoin(EFTARKOV_ROOT, "/changes"),
        urljoin(EFTARKOV_ROOT, f"/task?mode={mode}&page=1"),
    ]
    if any(not parser.can_fetch(USER_AGENT, target) for target in paths):
        raise CatalogError("EFTarkov robots.txt 不允许读取任务目录；未发送任务请求。")


def _plain_text(markup: str) -> str:
    value = re.sub(r"<[^>]*>", " ", markup)
    return " ".join(html.unescape(value).split())


def _extract_source_version(markup: str) -> str:
    markup = re.sub(r"<!--.*?-->|<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>", " ", markup, flags=re.I | re.S)
    plain = _plain_text(markup)
    match = re.search(r"当前版本\s*[：:]?\s*(\d+(?:\.\d+){2,3})", plain)
    return match.group(1) if match else ""


def _extract_page_count(markup: str) -> int:
    values = [int(value) for value in re.findall(r"[?&]page=(\d+)", html.unescape(markup), flags=re.I)]
    page_count = max(values, default=1)
    if page_count > MAX_PAGE_COUNT:
        raise CatalogError(f"EFTarkov 目录页数异常：{page_count}，超过安全上限。")
    return max(1, page_count)


def _parse_task_rows(markup: str, expected_mode: str) -> list[dict[str, Any]]:
    row_pattern = re.compile(
        r'<div\b(?=[^>]*\bdata-task-list-row\b)(?=[^>]*\bdata-task-id="([^"]+)")[^>]*>(.*?)(?=<div\b[^>]*\bdata-task-list-row\b|$)',
        re.I | re.S,
    )
    records: list[dict[str, Any]] = []
    for row_match in row_pattern.finditer(markup):
        task_id, row = row_match.groups()
        if not TASK_ID_PATTERN.fullmatch(task_id):
            continue
        mode_match = re.search(r'\bdata-mode="([^"]+)"', row, flags=re.I)
        if not mode_match or mode_match.group(1).casefold() != expected_mode:
            continue
        title_match = re.search(
            r'<[^>]*\bclass="[^"]*\btask-list-title\b[^"]*"[^>]*>(.*?)</',
            row,
            flags=re.I | re.S,
        )
        trader_match = re.search(r'<img\b[^>]*\balt="([^"]+)"', row, flags=re.I | re.S)
        title = _plain_text(title_match.group(1)) if title_match else ""
        trader = html.unescape(trader_match.group(1)).strip() if trader_match else ""
        if not title or not trader:
            continue
        records.append(
            {
                "source_task_id": task_id.lower(),
                "trader": trader,
                "title": title,
                "source_url": urljoin(EFTARKOV_ROOT, f"/task/{task_id.lower()}"),
                "objectives": [],
                "prerequisites": [],
            }
        )
    return records


def fetch_eftarkov_catalog(game_mode: str) -> CatalogBundle:
    if game_mode not in EFTARKOV_MODE:
        raise CatalogError("EFTarkov 当前只提供 PvE 与常规 PvP 目录；赛季 PvP 不会套用常规 PvP 数据。")
    mode = EFTARKOV_MODE[game_mode]
    _check_robots(mode)
    changes_body, _ = _request(urljoin(EFTARKOV_ROOT, "/changes"))
    source_version = _extract_source_version(changes_body.decode("utf-8", "replace"))

    first_url = urljoin(EFTARKOV_ROOT, f"/task?mode={mode}&page=1")
    first_body, _ = _request(first_url, game_mode)
    first_markup = first_body.decode("utf-8", "replace")
    page_count = _extract_page_count(first_markup)
    tasks = _parse_task_rows(first_markup, mode)
    for page_number in range(2, page_count + 1):
        time.sleep(PAGE_DELAY_SECONDS)
        page_url = urljoin(EFTARKOV_ROOT, f"/task?mode={mode}&page={page_number}")
        body, _ = _request(page_url, game_mode)
        tasks.extend(_parse_task_rows(body.decode("utf-8", "replace"), mode))

    unique_tasks: dict[str, dict[str, Any]] = {}
    for task in tasks:
        existing = unique_tasks.get(task["source_task_id"])
        if existing and (existing["title"] != task["title"] or existing["trader"] != task["trader"]):
            raise CatalogError(f"同一任务 ID 出现冲突资料：{task['source_task_id']}")
        unique_tasks[task["source_task_id"]] = task
    tasks = list(unique_tasks.values())
    if len(tasks) < 50:
        raise CatalogError(f"只解析到 {len(tasks)} 条任务，页面结构或模式可能已变化；旧目录保持不变。")

    canonical = json.dumps(tasks, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    content_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    metadata = {
        "source_page_count": page_count,
        "source_task_count": len(tasks),
        "source_version_label": source_version or None,
        "game_build": None,
        "game_patch_coverage": "unknown",
        "robots_checked": True,
        "source_version_basis": "EFTarkov /changes 页面显示的当前资料版本",
        "warning": "来源页面当前标注版本不等于玩家客户端版本；未核实是否覆盖更晚的游戏补丁。",
    }
    return CatalogBundle(
        game_mode=game_mode,
        source_version=source_version,
        content_sha256=content_sha256,
        tasks=tasks,
        metadata=metadata,
    )


class _TaskDetailParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self._heading_parts: list[str] = []
        self._reading_heading = False
        self._section = ""
        self._objective_parts: list[str] | None = None
        self._objective_depth = 0
        self.objectives: list[dict[str, Any]] = []
        self._required_item: dict[str, Any] | None = None
        self._required_item_depth = 0
        self._active_required_link: dict[str, Any] | None = None
        self.key_requirements: list[dict[str, str]] = []
        self.map_marker_refs: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag in {"script", "style"}:
            self._ignored_depth += 1
        if self._ignored_depth:
            return
        if tag == "a" and attributes.get("href"):
            marker_ref = _map_marker_ref(attributes["href"])
            if marker_ref and marker_ref not in self.map_marker_refs:
                self.map_marker_refs.append(marker_ref)
        if (
            self._required_item is None
            and tag == "div"
            and "task-required-item" in (attributes.get("class") or "").split()
            and "data-task-required-item" not in attributes
        ):
            self._required_item = {"text": [], "links": []}
            self._required_item_depth = 1
        elif self._required_item is not None:
            if tag not in VOID_TAGS:
                self._required_item_depth += 1
            if tag == "a":
                self._active_required_link = {"href": attributes.get("href", ""), "text": []}
                self._required_item["links"].append(self._active_required_link)
        if tag in {"h2", "h3"}:
            self._heading_parts = []
            self._reading_heading = True
        if tag == "li" and self._is_objective_section() and self._objective_parts is None:
            self._objective_parts = []
            self._objective_depth = 1
        elif tag == "li" and self._objective_parts is not None:
            self._objective_depth += 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        if self._required_item is not None:
            self._required_item["text"].append(data)
            if self._active_required_link is not None:
                self._active_required_link["text"].append(data)
        if self._reading_heading:
            self._heading_parts.append(data)
        if self._objective_parts is not None:
            self._objective_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1
        if self._ignored_depth:
            return
        if tag == "a":
            self._active_required_link = None
        if self._required_item is not None:
            self._required_item_depth -= 1
            if self._required_item_depth == 0:
                links = self._required_item["links"]
                item_links = [
                    link
                    for link in links
                    if re.fullmatch(r"/item/[0-9a-f]{24}", urlparse(link["href"]).path, re.I)
                ]
                if item_links:
                    item_link = next(
                        (link for link in item_links if " ".join(link["text"]).strip()),
                        item_links[0],
                    )
                    item_id = urlparse(item_link["href"]).path.rsplit("/", 1)[-1].lower()
                    name = " ".join(" ".join(item_link["text"]).split())
                    if not name:
                        name = " ".join(" ".join(self._required_item["text"]).split())
                    name = re.split(
                        r"任务需要用到此钥匙|任务需要用到这把钥匙|key is required for the task",
                        name,
                        maxsplit=1,
                        flags=re.I,
                    )[0].strip(" ：:，,·-—")
                    self.key_requirements.append(
                        {
                            "item_id": item_id,
                            "name": name,
                            "item_kind": "key" if is_key_item_name(name) else "item",
                            "source_url": urljoin(EFTARKOV_ROOT, f"/item/{item_id}"),
                        }
                    )
                self._required_item = None
        if tag in {"h2", "h3"} and self._reading_heading:
            self._section = " ".join(" ".join(self._heading_parts).split())
            self._reading_heading = False
        if tag == "li" and self._objective_parts is not None:
            self._objective_depth -= 1
            if self._objective_depth == 0:
                description = " ".join(" ".join(self._objective_parts).split())
                if description:
                    self.objectives.append(normalize_objective(description))
                self._objective_parts = None

    def _is_objective_section(self) -> bool:
        section = self._section.casefold()
        return "任务目标" in section or "目標" in section or "objective" in section


def _map_marker_ref(href: str) -> dict[str, str] | None:
    parsed = urlparse(html.unescape(href))
    if parsed.netloc and parsed.netloc != "www.eftarkov.com":
        return None
    match = re.fullmatch(r"/map/([0-9a-f]{24})", parsed.path, re.I)
    marker_id = parse_qs(parsed.query).get("marker", [""])[0]
    if not match or not TASK_ID_PATTERN.fullmatch(marker_id):
        return None
    return {"map_id": match.group(1).lower(), "marker_id": marker_id.lower()}


class _MapIndexParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._current: dict[str, Any] | None = None
        self.maps: list[dict[str, str]] = []
        self._seen: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attributes = dict(attrs)
        match = re.fullmatch(r"/map/([0-9a-f]{24})", attributes.get("href", ""), re.I)
        if match:
            self._current = {"map_id": match.group(1).lower(), "parts": []}

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            self._current["parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._current is None:
            return
        map_id = self._current["map_id"]
        name = " ".join(" ".join(self._current["parts"]).split())
        if map_id not in self._seen:
            self.maps.append({"map_id": map_id, "name": name or map_id})
            self._seen.add(map_id)
        self._current = None


class _MapConfigParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._capture = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and dict(attrs).get("id") == "map-config":
            self._capture = True

    def handle_data(self, data: str) -> None:
        if self._capture:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._capture:
            self._capture = False


class _ItemDetailParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._table_kind = ""
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._cell_tag = ""
        self.barter_rows: list[list[str]] = []
        self.map_marker_refs: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "a" and attributes.get("href"):
            marker_ref = _map_marker_ref(attributes["href"])
            if marker_ref and marker_ref not in self.map_marker_refs:
                self.map_marker_refs.append(marker_ref)
        if tag == "table":
            classes = (attributes.get("class") or "").split()
            self._table_kind = "barter" if "item-recipe-table" in classes and "is-barter" in classes else ""
        elif self._table_kind == "barter" and tag == "tr":
            self._row = []
        elif self._table_kind == "barter" and tag in {"td", "th"} and self._row is not None:
            self._cell = []
            self._cell_tag = tag

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and tag == self._cell_tag:
            if self._cell_tag == "td" and self._row is not None:
                self._row.append(" ".join(" ".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.barter_rows.append(self._row)
            self._row = None
        elif tag == "table":
            self._table_kind = ""


@lru_cache(maxsize=3)
def _fetch_eftarkov_map_index(game_mode: str) -> list[dict[str, str]]:
    if game_mode not in {"pve", "regular", "pvp-season"}:
        raise CatalogError("未知游戏模式，无法读取地图目录。")
    body, _ = _request(urljoin(EFTARKOV_ROOT, "/map"), game_mode)
    parser = _MapIndexParser()
    parser.feed(body.decode("utf-8", "replace"))
    if not parser.maps:
        raise CatalogError("没有从 EFTarkov 地图目录读取到地图列表。")
    return parser.maps


def fetch_eftarkov_map_index(game_mode: str = "pve") -> list[dict[str, str]]:
    with _PUBLIC_DATA_LOCK:
        return _fetch_eftarkov_map_index(game_mode)


@lru_cache(maxsize=32)
def _fetch_eftarkov_map_data(map_id: str, game_mode: str) -> dict[str, Any]:
    if not TASK_ID_PATTERN.fullmatch(map_id):
        raise CatalogError("地图 ID 格式无效。")
    map_id = map_id.lower()
    maps = fetch_eftarkov_map_index(game_mode)
    map_entry = next((entry for entry in maps if entry["map_id"] == map_id), None)
    if map_entry is None:
        raise CatalogError("该地图不在 EFTarkov 公开地图目录中。")
    page_url = urljoin(EFTARKOV_ROOT, f"/map/{map_id}")
    body, _ = _request(page_url, game_mode)
    parser = _MapConfigParser()
    parser.feed(body.decode("utf-8", "replace"))
    try:
        config = json.loads("".join(parser.parts))
    except json.JSONDecodeError as error:
        raise CatalogError("无法解析 EFTarkov 地图页配置。") from error
    floors: list[dict[str, Any]] = []
    for floor in config.get("floors", []):
        key = str(floor.get("key", ""))
        src = str(floor.get("src", ""))
        if not key or not re.fullmatch(rf"/assets/maps/{map_id}/[A-Za-z0-9_-]+\.svg", src):
            continue
        try:
            width = float(floor.get("width", 0))
            height = float(floor.get("height", 0))
        except (TypeError, ValueError):
            continue
        if width <= 0 or height <= 0:
            continue
        floors.append(
            {
                "key": key,
                "name": str(floor.get("name", key)),
                "src": urljoin(EFTARKOV_ROOT, src),
                "width": width,
                "height": height,
            }
        )
    markers: list[dict[str, Any]] = []
    for marker in config.get("markers", []):
        try:
            x = float(marker.get("x"))
            y = float(marker.get("y"))
        except (TypeError, ValueError):
            continue
        raw_image_urls: list[Any] = []
        for image_field in ("image_urls", "info_image_urls", "images"):
            image_values = marker.get(image_field)
            if isinstance(image_values, list):
                raw_image_urls.extend(image_values)
            elif isinstance(image_values, str) and image_values:
                raw_image_urls.append(image_values)
        for image_field in ("image_url", "info_image_url", "image"):
            image_value = marker.get(image_field)
            if image_value:
                raw_image_urls.append(image_value)
        info_image_urls: list[str] = []
        for raw_image_value in raw_image_urls[:48]:
            if isinstance(raw_image_value, dict):
                raw_image_value = (
                    raw_image_value.get("url")
                    or raw_image_value.get("src")
                    or raw_image_value.get("image_url")
                    or ""
                )
            marker_image = urlparse(urljoin(EFTARKOV_ROOT, str(raw_image_value or "")))
            if (
                marker_image.scheme == "https"
                and marker_image.netloc == "www.eftarkov.com"
                and re.fullmatch(r"/uploads/infoImg/[A-Za-z0-9._-]+\.(?:webp|png|jpe?g)", marker_image.path, re.I)
                and marker_image.geturl() not in info_image_urls
            ):
                info_image_urls.append(marker_image.geturl())
        image_url = info_image_urls[0] if info_image_urls else ""
        task_id = str(marker.get("task_id") or "").lower()
        if task_id and not TASK_ID_PATTERN.fullmatch(task_id):
            task_id = ""
        markers.append(
            {
                "id": str(marker.get("id", "")),
                "map_id": map_id,
                "floor_key": str(marker.get("floor_key", "")),
                "title": str(marker.get("title", "")),
                "description": str(marker.get("description", "")),
                "marker_type": str(marker.get("marker_type", "point")),
                "info_image_url": image_url,
                "info_image_urls": info_image_urls,
                "x": x,
                "y": y,
                "task_id": task_id,
                "key_item_id": str(marker.get("key_item_id") or ""),
            }
        )
    return {
        "map_id": map_id,
        "name": map_entry["name"],
        "floors": floors,
        "markers": markers,
        "source_url": page_url,
    }


def fetch_eftarkov_map_data(map_id: str, game_mode: str = "pve") -> dict[str, Any]:
    with _PUBLIC_DATA_LOCK:
        return _fetch_eftarkov_map_data(map_id.lower(), game_mode)


@lru_cache(maxsize=8)
def _fetch_eftarkov_map_floor_image(map_id: str, floor_key: str, game_mode: str) -> bytes:
    config = fetch_eftarkov_map_data(map_id, game_mode)
    floor = next((item for item in config["floors"] if item["key"] == floor_key), None)
    if floor is None:
        raise CatalogError("该地图没有对应楼层底图。")
    body, headers = _request(
        floor["src"],
        game_mode,
        max_response_bytes=20_000_000,
        accept="image/svg+xml",
    )
    content_type = headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if content_type != "image/svg+xml" or not re.search(rb"<svg\b", body[:8192], re.IGNORECASE):
        raise CatalogError("EFTarkov 返回的地图底图不是有效 SVG。")
    return body


def fetch_eftarkov_map_floor_image(map_id: str, floor_key: str, game_mode: str = "pve") -> bytes:
    if not TASK_ID_PATTERN.fullmatch(map_id):
        raise CatalogError("地图 ID 格式无效。")
    with _PUBLIC_DATA_LOCK:
        return _fetch_eftarkov_map_floor_image(map_id.lower(), floor_key, game_mode)


def fetch_eftarkov_map_marker_points(
    marker_refs: list[dict[str, str]], game_mode: str = "pve", point_kind: str = "objective"
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    configs: dict[str, dict[str, Any]] = {}
    for marker_ref in marker_refs:
        map_id = str(marker_ref.get("map_id", "")).lower()
        marker_id = str(marker_ref.get("marker_id", "")).lower()
        if not TASK_ID_PATTERN.fullmatch(map_id) or not TASK_ID_PATTERN.fullmatch(marker_id):
            continue
        try:
            config = configs.setdefault(map_id, fetch_eftarkov_map_data(map_id, game_mode))
        except CatalogError:
            continue
        marker = next((entry for entry in config["markers"] if entry["id"].lower() == marker_id), None)
        if marker is None:
            continue
        floor = next((entry for entry in config["floors"] if entry["key"] == marker["floor_key"]), None)
        if floor is None:
            continue
        result.append(
            {
                **marker,
                "map_name": config["name"],
                "floor_name": floor["name"],
                "width": floor["width"],
                "height": floor["height"],
                "image_url": floor["src"],
                "point_kind": point_kind,
                "source_image_url": marker["info_image_url"],
                "source_image_urls": marker["info_image_urls"],
                "source_url": marker["info_image_url"] or f"{config['source_url']}?marker={marker_id}",
                "source_page_url": f"{config['source_url']}?marker={marker_id}",
            }
        )
    return result


@lru_cache(maxsize=256)
def _fetch_eftarkov_item_detail_cached(item_id: str, game_mode: str) -> dict[str, Any]:
    if not TASK_ID_PATTERN.fullmatch(item_id):
        raise CatalogError("任务所需物品 ID 格式无效。")
    item_id = item_id.lower()
    item_url = urljoin(EFTARKOV_ROOT, f"/item/{item_id}")
    body, _ = _request(item_url, game_mode)
    parser = _ItemDetailParser()
    parser.feed(body.decode("utf-8", "replace"))
    methods: list[dict[str, str]] = []
    for row in parser.barter_rows:
        if len(row) < 4 or not row[1] or not row[2]:
            continue
        methods.append(
            {
                "type": "barter",
                "trader": row[2],
                "loyalty_level": row[3],
                "requirements": row[1],
            }
        )
    return {
        "source_url": item_url,
        "acquisition_methods": methods,
        "map_marker_refs": parser.map_marker_refs,
    }


def _fetch_eftarkov_item_detail(item_id: str, game_mode: str) -> dict[str, Any]:
    with _PUBLIC_DATA_LOCK:
        return _fetch_eftarkov_item_detail_cached(item_id, game_mode)


def fetch_eftarkov_task_detail(source_task_id: str, game_mode: str = "pve") -> dict[str, Any]:
    if not TASK_ID_PATTERN.fullmatch(source_task_id):
        raise CatalogError("任务 ID 格式无效。")
    url = urljoin(EFTARKOV_ROOT, f"/task/{source_task_id.lower()}")
    body, _ = _request(url, game_mode)
    parser = _TaskDetailParser()
    parser.feed(body.decode("utf-8", "replace"))
    if not parser.objectives:
        raise CatalogError("没有从公开任务详情页提取到目标；未导入任务。")
    keys: list[dict[str, Any]] = []
    for required_key in parser.key_requirements:
        key = dict(required_key)
        try:
            item_detail = _fetch_eftarkov_item_detail(key["item_id"], game_mode)
            key["acquisition_methods"] = item_detail["acquisition_methods"]
            key["map_points"] = fetch_eftarkov_map_marker_points(
                item_detail["map_marker_refs"], game_mode, "key-use"
            )
        except CatalogError as error:
            key["acquisition_methods"] = []
            key["map_points"] = []
            key["acquisition_error"] = str(error)
        keys.append(key)
    return {
        "objectives": parser.objectives,
        "key_requirements": keys,
        "map_points": fetch_eftarkov_map_marker_points(parser.map_marker_refs, game_mode),
        "source_url": url,
    }
