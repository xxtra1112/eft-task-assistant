"""RE3MR original raster maps for personal, local, noncommercial viewing.

No image assets are written here. An explicit cache root enables persistent
directory, robots, failure and local-import records. The application owns images.
"""
from __future__ import annotations

import copy
import errno
import hashlib
import io
import json
import math
import os
import re
import threading
import time
import warnings
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from PIL import Image, UnidentifiedImageError

from catalog import CatalogError
from asset_cache import IMAGE_DECODE_LOCK


ROOT = "https://reemr.se/"
FAQ_URL = ROOT + "about/"
LICENSE_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/"
USER_AGENT = "EFTTaskAssistant/1.2 (personal local noncommercial RE3MR viewer)"
MAX_IMAGE_BYTES = 50_000_000
MAX_PIXELS = 160_000_000
MAX_HTML_BYTES = 2_000_000
MAX_ROBOTS_BYTES = 256_000
DOCUMENT_TTL = 12 * 3600
ROBOTS_TTL = 3600
CACHE_SCHEMA = 1
MAX_STATE_BYTES = 40_000_000
HOSTS = frozenset({"reemr.se", "www.reemr.se", "maps.reemr.se", "re3mr.com", "www.re3mr.com"})
ASSET_DIRECTORIES = frozenset({
    "customs", "factory", "groundzero", "icebreaker", "interchange", "labyrinth",
    "lighthouse", "reserve", "shoreline", "streets", "terminal", "transit", "woods",
})
MAPS = {
    "customs": ("海关", "Customs"), "factory": ("工厂", "Factory"),
    "ground-zero": ("中心区", "Ground Zero"), "icebreaker": ("破冰船", "Icebreaker"),
    "interchange": ("立交桥", "Interchange"), "labyrinth": ("迷宫", "Labyrinth"),
    "lighthouse": ("灯塔", "Lighthouse"), "reserve": ("储备站", "Reserve"),
    "shoreline": ("海岸线", "Shoreline"), "streetsoftarkov": ("塔科夫街区", "Streets of Tarkov"),
    "terminal": ("码头", "Terminal"), "transit": ("转移路线", "Transit"),
    "woods": ("森林", "Woods"),
}
NOTICE = (
    "RE3MR 原始底图，仅供本地个人非商业查看；保留原图署名，不含经校准的任务点。"
    "官网标示 CC BY-NC-SA 4.0，部分页面另链 2.0，详见 license_evidence。"
    "FAQ 对上传至网站或应用另有联系提示；本模块不表示已获得作者单独授权，"
    "不用于随包分发、公共再托管或商业用途。"
)


@dataclass(frozen=True)
class FetchResponse:
    body: bytes
    content_type: str
    source_url: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ReemrPolicyError(CatalogError):
    """A caller must not fall back to cached image bytes after this rejection."""

    asset_access_denied = True


class ReemrNetworkError(CatalogError):
    pass


class ReemrFetchError(CatalogError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def _error_chain(error: BaseException):
    visited = set()
    pending = [error]
    while pending:
        error = pending.pop()
        if error is None or id(error) in visited:
            continue
        visited.add(id(error))
        yield error
        pending.extend((error.__cause__, error.__context__))
        if isinstance(error, URLError) and isinstance(error.reason, BaseException):
            pending.append(error.reason)


def _network_error(error: BaseException) -> bool:
    return ((isinstance(error, (ReemrNetworkError, TimeoutError, ConnectionError, URLError))
             and not isinstance(error, HTTPError))
            or (isinstance(error, OSError) and getattr(error, "errno", None) in {
                errno.ETIMEDOUT, errno.EHOSTUNREACH, errno.ENETUNREACH, errno.ECONNRESET,
                errno.ECONNABORTED, errno.ECONNREFUSED, errno.ENETDOWN,
                10050, 10051, 10052, 10053, 10054, 10060, 10061, 10064, 10065}))


def access_denied(error: BaseException) -> bool:
    chain = tuple(_error_chain(error))
    for error in chain:
        if (isinstance(error, (ReemrPolicyError, PermissionError))
                or getattr(error, "asset_access_denied", False)
                or (getattr(error, "status", None) or getattr(error, "code", None)) in {401, 403}
                or re.search(r"\b(?:401|403)\b", str(error))):
            return True
    if any(_network_error(error) for error in chain):
        return False
    return any(re.search(r"robots|forbidden|policy|access denied|permission denied|unauthori[sz]ed|拒绝|禁止|不允许",
                         str(error).casefold()) for error in chain)


def temporary_network_failure(error: BaseException) -> bool:
    if access_denied(error):
        return False
    return any(_network_error(error) for error in _error_chain(error))


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_url(url: str, kind: str) -> None:
    parsed = urlsplit(url)
    path = unquote(parsed.path)
    if (
        parsed.scheme != "https" or parsed.hostname not in HOSTS
        or parsed.netloc != parsed.hostname or parsed.query or parsed.fragment
        or any(character in url for character in ("\\", "\r", "\n", "\x00"))
        or any(part in {".", ".."} for part in path.split("/"))
        or "%" in path
    ):
        raise CatalogError("RE3MR URL 不在安全白名单内。")
    if kind == "robots" and path == "/robots.txt":
        return
    if kind == "html" and parsed.hostname in {"reemr.se", "www.reemr.se"}:
        if path.casefold() in {"/", "/about/", *(f"/{slug}{ending}" for slug in MAPS for ending in ("", "/"))}:
            return
    if kind == "image":
        parts = path.strip("/").split("/")
        allowed_path = len(parts) >= 3 and parts[0] == "maps" and parts[1].casefold() in ASSET_DIRECTORIES
        if parsed.hostname == "maps.reemr.se":
            allowed_path = len(parts) >= 2 and parts[0].casefold() in ASSET_DIRECTORIES
        if allowed_path and re.fullmatch(r"/[A-Za-z0-9_./ ()-]+\.(?:png|jpe?g|webp)", path, re.I):
            return
    raise CatalogError("RE3MR 只读取官网目录、robots 及明确链接的 PNG/JPEG/WebP 原图。")


def _transport(url: str, limit: int, accept: str) -> FetchResponse:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    try:
        with build_opener(_NoRedirect()).open(request, timeout=35) as response:
            declared = response.headers.get("Content-Length")
            if declared and (not declared.isdecimal() or int(declared) > limit):
                raise CatalogError("RE3MR 响应声明长度超过限制或无效。")
            body = response.read(limit + 1)
            if len(body) > limit:
                raise CatalogError("RE3MR 响应超过大小限制。")
            return FetchResponse(body, response.headers.get_content_type(), response.geturl(), {
                "status": response.status, "etag": response.headers.get("ETag", ""),
                "last_modified": response.headers.get("Last-Modified", ""),
                "fetched_at": _utc_now(),
            })
    except HTTPError as error:
        if error.code in {301, 302, 303, 307, 308}:
            result = FetchResponse(b"", "", url, {"status": error.code, "location": error.headers.get("Location", "")})
            error.close()
            return result
        code = error.code
        error.close()
        if code in {404, 410} and urlsplit(url).path == "/robots.txt":
            return FetchResponse(b"", "text/plain", url, {"status": code})
        raise ReemrFetchError(f"RE3MR 返回 HTTP {code}；不重试绕过访问限制。", code) from error
    except (URLError, TimeoutError, OSError) as error:
        raise ReemrNetworkError(f"无法读取 RE3MR：{error}") from error


def _robots_allows(text: str, url: str) -> bool:
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    agents: list[str] = []
    rules: list[tuple[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.casefold()
        if key == "user-agent":
            if rules:
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(value.casefold())
        elif agents and key in {"allow", "disallow"}:
            rules.append((key, value))
    groups.append((agents, rules))
    selected: list[tuple[int, list[tuple[str, str]]]] = []
    for group_agents, group_rules in groups:
        ranks = [0 if agent == "*" else len(agent) for agent in group_agents
                 if agent == "*" or agent and agent in USER_AGENT.casefold()]
        if ranks:
            selected.append((max(ranks), group_rules))
    best_agent = max((rank for rank, _ in selected), default=-1)
    matches: list[tuple[int, bool]] = []
    path = unquote(urlsplit(url).path)
    for rank, group_rules in selected:
        if rank != best_agent:
            continue
        for directive, pattern in group_rules:
            if not pattern:
                continue
            pattern = unquote(pattern)
            expression = re.escape(pattern.rstrip("$")).replace(r"\*", ".*")
            if re.match("^" + expression + ("$" if pattern.endswith("$") else ""), path):
                matches.append((len(pattern.replace("*", "").rstrip("$")), directive == "allow"))
    return max(matches, default=(0, True))[1]


class _Directory(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[dict[str, Any]] = []
        self.licenses: list[str] = []
        self._anchor: dict[str, Any] | None = None
        self._heading: list[str] | None = None
        self._last_heading = ""
        self._ignored: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        href = attributes.get("href") or ""
        if tag == "a" and not any(ignored in {"script", "style", "svg", "iframe", "object"} for ignored in self._ignored):
            if re.fullmatch(r"https://creativecommons\.org/licenses/by-nc-sa/(?:2\.0|4\.0)/(?:legalcode(?:\.en)?|deed\.en)?/?", href):
                if href not in self.licenses:
                    self.licenses.append(href)
        if tag in {"script", "style", "svg", "iframe", "object", "nav", "header", "footer"}:
            self._ignored.append(tag)
        if self._ignored:
            return
        if re.fullmatch(r"h[1-6]", tag):
            self._heading = []
        if tag == "a":
            self._anchor = {"href": attributes.get("href") or "", "text": [],
                            "heading": self._last_heading, "attrs": attributes}

    def handle_endtag(self, tag: str) -> None:
        if self._ignored:
            if self._ignored[-1] == tag:
                self._ignored.pop()
            return
        if tag == "a" and self._anchor is not None:
            self._anchor["text"] = " ".join(" ".join(self._anchor["text"]).split())
            self.anchors.append(self._anchor)
            self._anchor = None
        if re.fullmatch(r"h[1-6]", tag) and self._heading is not None:
            self._last_heading = " ".join(" ".join(self._heading).split())
            self._heading = None

    def handle_data(self, data: str) -> None:
        if not self._ignored:
            if self._anchor is not None:
                self._anchor["text"].append(data)
            if self._heading is not None:
                self._heading.append(data)


def _parse_document(body: bytes) -> _Directory:
    try:
        document = body.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CatalogError("RE3MR 页面不是有效 UTF-8 HTML。") from error
    parser = _Directory()
    parser.feed(document)
    parser.close()
    return parser


def validate_image(body: bytes, content_type: str | None = None) -> dict[str, Any]:
    with IMAGE_DECODE_LOCK:
        return _decode_image(body, content_type)


def _decode_image(body: bytes, content_type: str | None = None) -> dict[str, Any]:
    """Fully decode a bounded raster, preserving the original encoded bytes."""
    if not body or len(body) > MAX_IMAGE_BYTES:
        raise CatalogError("RE3MR 图片为空或超过 50 MB。")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(body), formats=["PNG", "JPEG", "WEBP"]) as image:
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
                    raise CatalogError("RE3MR 图片超过 160 MP 像素限制。")
                if getattr(image, "n_frames", 1) != 1:
                    raise CatalogError("RE3MR 只接受静态底图。")
                image_format = image.format
                image.verify()
            with Image.open(io.BytesIO(body), formats=["PNG", "JPEG", "WEBP"]) as image:
                image.load()
        mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[image_format]
        if content_type and content_type.split(";", 1)[0].strip().lower() != mime:
            raise CatalogError("RE3MR 图片 MIME 与实际解码格式不一致。")
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError) as error:
        raise CatalogError("RE3MR 图片无法完整解码或格式不安全。") from error
    return {"width": width, "height": height, "content_type": mime, "format": image_format,
            "byte_length": len(body), "sha256": hashlib.sha256(body).hexdigest(),
            "dimensions_verified": True, "dimensions_basis": "pillow-full-decode", "modified": False}


class ReemrMaps:
    def __init__(self, *, cache_root: Path | None = None, usage: str = "personal-local",
                 fetcher: Callable[..., FetchResponse] | None = None) -> None:
        if usage != "personal-local":
            raise CatalogError("RE3MR 自动读取仅实现本地个人非商业运行；再分发/再托管未启用。")
        self._fetcher = fetcher or _transport
        self._lock = threading.RLock()
        self._key_locks: dict[str, threading.Lock] = {}
        self.cache_path = Path(cache_root).resolve() / "reemr" / "directory-v1.json" if cache_root is not None else None
        self._state: dict[str, Any] = {"schema_version": CACHE_SCHEMA, "source_provider": "reemr",
                                      "usage_scope": "personal-local-noncommercial", "documents": {},
                                      "directories": {}, "robots": {}, "operations": {}, "imports": {}}
        self._load_state()
        self._documents: dict[str, tuple[float, FetchResponse]] = {}
        self._document_retry_after: dict[str, float] = {}
        self._robots: dict[str, dict[str, Any]] = self._state["robots"]
        self._metadata: dict[str, dict[str, Any]] = {}
        self._imports: dict[str, dict[str, dict[str, Any]]] = {}
        for map_id, records in self._state["imports"].items():
            if map_id not in MAPS or not isinstance(records, dict):
                continue
            for key, record in records.items():
                if not isinstance(record, dict):
                    continue
                evidence, floor = record.get("license_evidence", {}), record.get("floor", {})
                if (isinstance(evidence, dict) and evidence.get("user_rights_confirmed") is True
                        and evidence.get("usage_scope") == "personal-local-noncommercial"
                        and isinstance(evidence.get("user_evidence"), str) and evidence["user_evidence"].strip()
                        and isinstance(floor, dict) and floor.get("key") == key
                        and isinstance(record.get("path"), str)):
                    self._imports.setdefault(map_id, {})[key] = {**record, "path": Path(record["path"])}

    def _load_state(self) -> None:
        if self.cache_path is None or not self.cache_path.exists():
            return
        try:
            if self.cache_path.stat().st_size > MAX_STATE_BYTES:
                raise ValueError("directory JSON exceeds limit")
            state = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if (not isinstance(state, dict) or state.get("schema_version") != CACHE_SCHEMA
                    or state.get("source_provider") != "reemr"
                    or state.get("usage_scope") != "personal-local-noncommercial"
                    or any(not isinstance(state.get(key), dict) for key in (
                        "documents", "directories", "robots", "operations", "imports"))):
                raise ValueError("directory JSON schema/provider mismatch")
            self._state = state
        except (OSError, ValueError, TypeError) as error:
            self._state["operations"]["cache-read"] = {
                "state": "failed", "last_failure": {"at": _utc_now(), "message": str(error)},
            }

    def _write_state(self) -> None:
        if self.cache_path is None:
            return
        with self._lock:
            body = json.dumps(self._state, ensure_ascii=False, allow_nan=False).encode("utf-8")
            if len(body) > MAX_STATE_BYTES:
                raise CatalogError("RE3MR 目录 JSON 超过大小限制。")
            temporary = self.cache_path.with_name(self.cache_path.name + "." + uuid.uuid4().hex + ".tmp")
            try:
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                with temporary.open("xb") as stream:
                    stream.write(body)
                    stream.flush()
                    os.fsync(stream.fileno())
                temporary.replace(self.cache_path)
            except OSError as error:
                raise CatalogError(f"RE3MR 目录状态无法写入指定缓存：{error}") from error
            finally:
                temporary.unlink(missing_ok=True)

    def _operation(self, key: str, error: Exception | None = None) -> None:
        with self._lock:
            record = self._state["operations"].setdefault(key, {})
            record["state"] = "failed" if error is not None else "ok"
            record["last_attempt_at"] = _utc_now()
            if error is not None:
                record["last_failure"] = {"at": record["last_attempt_at"], "message": str(error),
                                          "error_type": type(error).__name__, "http_status": getattr(error, "status", None)}
            else:
                record["last_success_at"] = record["last_attempt_at"]
            self._write_state()

    def _cached_document(self, url: str) -> tuple[float, FetchResponse] | None:
        cached = self._documents.get(url)
        if cached is not None or self.cache_path is None:
            return cached
        try:
            record = self._state["documents"][url]
            body = record["body_utf8"].encode("utf-8")
            checked = float(record["checked_at"])
            if (len(body) > MAX_HTML_BYTES or not math.isfinite(checked) or checked > time.time() + 60
                    or record["sha256"] != hashlib.sha256(body).hexdigest()
                    or record["content_type"].split(";", 1)[0] != "text/html"
                    or not isinstance(record["metadata"], dict)):
                return None
            _validate_url(record["source_url"], "html")
            cached = (time.monotonic() - max(0, time.time() - checked),
                      FetchResponse(body, record["content_type"], record["source_url"], record["metadata"]))
            self._documents[url] = cached
            return cached
        except (KeyError, TypeError, ValueError, AttributeError, CatalogError):
            return None

    def _document_status(self, url: str, response: FetchResponse, *, state: str, stale: bool) -> FetchResponse:
        operation = self._state["operations"].get("document:" + url, {})
        return FetchResponse(response.body, response.content_type, response.source_url, {
            **response.metadata, "cache_status": {"state": state, "stale": stale,
                "source_provider": "reemr", "last_failure": copy.deepcopy(operation.get("last_failure")),
                "source_fetched_at": response.metadata.get("fetched_at"),
                "last_attempt_at": operation.get("last_attempt_at")},
        })

    def _snapshot(self, key: str, payload: Any) -> None:
        with self._lock:
            self._state["directories"][key] = {"source_provider": "reemr", "updated_at": _utc_now(),
                                               "payload": copy.deepcopy(payload)}
            self._write_state()

    def _key_lock(self, key: str) -> threading.Lock:
        with self._lock:
            return self._key_locks.setdefault(key, threading.Lock())

    def _request(self, url: str, kind: str) -> FetchResponse:
        limit, accept = {
            "html": (MAX_HTML_BYTES, "text/html"),
            "robots": (MAX_ROBOTS_BYTES, "text/plain"),
            "image": (MAX_IMAGE_BYTES, "image/png,image/jpeg,image/webp"),
        }[kind]
        for _ in range(6):
            try:
                _validate_url(url, kind)
            except CatalogError as error:
                if kind == "robots":
                    raise CatalogError("RE3MR robots 地址或重定向目标无效；停止该域名图片读取。") from error
                raise
            if kind != "robots":
                self._check_robots(url)
            response = self._fetcher(url, limit, accept)
            if response.source_url != url:
                raise CatalogError("RE3MR 传输层不得自动跟随未经检查的重定向。")
            status = response.metadata.get("status", 200)
            if status in {301, 302, 303, 307, 308}:
                location = response.metadata.get("location")
                if not location:
                    raise CatalogError("RE3MR 重定向缺少目标。")
                url = urljoin(url, location)
                continue
            if status != 200 and not (kind == "robots" and status in {404, 410}):
                raise ReemrFetchError(f"RE3MR 返回 HTTP {status}。", status)
            if len(response.body) > limit:
                raise CatalogError("RE3MR 响应超过大小限制。")
            if kind == "html" and response.content_type.split(";", 1)[0] != "text/html":
                raise CatalogError("RE3MR 目录响应不是 HTML。")
            return response
        raise CatalogError("RE3MR 重定向次数超过限制。")

    def _check_robots(self, url: str) -> None:
        parsed = urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        with self._key_lock("robots:" + origin):
            cached = self._robots.get(origin)
            try:
                fresh = (isinstance(cached, dict) and math.isfinite(float(cached["checked_at"]))
                         and 0 <= time.time() - float(cached["checked_at"]) < ROBOTS_TTL)
                if fresh and cached.get("state") == "valid":
                    text = cached.get("text")
                    fresh = (isinstance(text, str) and len(text.encode("utf-8")) <= MAX_ROBOTS_BYTES
                             and cached.get("sha256") == hashlib.sha256(text.encode("utf-8")).hexdigest()
                             and (cached.get("http_status") in {404, 410}
                                  or re.search(r"(?im)^\s*user-agent\s*:\s*[^#\s]+", text))
                             and "<html" not in text.casefold() and "<!doctype" not in text.casefold())
            except (KeyError, TypeError, ValueError):
                fresh = False
            if not fresh:
                try:
                    response = self._request(origin + "/robots.txt", "robots")
                    if response.content_type.split(";", 1)[0] != "text/plain":
                        raise ReemrPolicyError("RE3MR robots 未返回纯文本；停止读取该域名资源。")
                    text = response.body.decode("utf-8-sig")
                    if "<html" in text.casefold() or "<!doctype" in text.casefold():
                        raise ReemrPolicyError("RE3MR robots 返回 HTML；停止读取该域名资源。")
                    if (response.metadata.get("status", 200) not in {404, 410}
                            and not re.search(r"(?im)^\s*user-agent\s*:\s*[^#\s]+", text)):
                        raise ReemrPolicyError("RE3MR robots 缺少有效 User-agent 规则；停止读取该域名资源。")
                    cached = {"state": "valid", "text": text, "checked_at": time.time(),
                              "checked_at_utc": _utc_now(), "source_url": response.source_url,
                              "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                              "http_status": response.metadata.get("status", 200)}
                except (CatalogError, OSError, UnicodeError) as error:
                    unavailable = temporary_network_failure(error)
                    with self._lock:
                        self._robots[origin] = {"state": "unavailable" if unavailable else "blocked", "checked_at": time.time(),
                            "checked_at_utc": _utc_now(), "source_url": origin + "/robots.txt",
                            "reason": str(error), "http_status": getattr(error, "status", None)}
                        self._operation("robots:" + origin, error)
                    if unavailable:
                        raise ReemrNetworkError(f"RE3MR 暂时无法核查来源规则：{error}") from error
                    raise ReemrPolicyError(f"RE3MR robots 未获有效允许，停止读取：{error}") from error
                with self._lock:
                    self._robots[origin] = cached
                    self._operation("robots:" + origin)
            if cached.get("state") == "unavailable":
                raise ReemrNetworkError("RE3MR 暂时无法核查来源规则：" + str(cached.get("reason", "")))
            if cached.get("state") != "valid" or not isinstance(cached.get("text"), str):
                raise ReemrPolicyError("RE3MR robots 先前核查被拒绝或无效：" + str(cached.get("reason", "")))
            if not _robots_allows(cached["text"], url):
                error = ReemrPolicyError("RE3MR robots 禁止此资源；不下载、不读取图片缓存。")
                self._operation("robots-resource:" + url, error)
                raise error

    def _robots_status(self, url: str) -> dict[str, Any]:
        parsed = urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        record = self._robots.get(origin, {})
        if not isinstance(record, dict):
            record = {}
        valid = record.get("state") == "valid" and isinstance(record.get("text"), str)
        allowed = valid and _robots_allows(record["text"], url)
        return {"state": ("allowed" if allowed else "blocked") if record else "unchecked",
                "source_url": origin + "/robots.txt", "checked_at": record.get("checked_at_utc"),
                "sha256": record.get("sha256"), "reason": record.get("reason", ""),
                "http_status": record.get("http_status")}

    def _document(self, url: str) -> FetchResponse:
        with self._key_lock("html:" + url):
            cached = self._cached_document(url)
            try:
                self._check_robots(url)
                if cached is not None and time.monotonic() - cached[0] < DOCUMENT_TTL:
                    return self._document_status(url, cached[1], state="cached", stale=False)
                if cached is not None and time.monotonic() < self._document_retry_after.get(url, 0):
                    return self._document_status(url, cached[1], state="offline", stale=True)
                response = self._request(url, "html")
                _parse_document(response.body)
            except (CatalogError, OSError) as error:
                if not temporary_network_failure(error):
                    with self._lock:
                        self._documents.pop(url, None)
                        self._state["documents"].pop(url, None)
                        self._document_retry_after.pop(url, None)
                    self._operation("document:" + url, error)
                    raise
                self._operation("document:" + url, error)
                if cached is None:
                    raise
                self._document_retry_after[url] = time.monotonic() + 30
                return self._document_status(url, cached[1], state="offline", stale=True)
            self._documents[url] = (time.monotonic(), response)
            with self._lock:
                self._state["documents"][url] = {"body_utf8": response.body.decode("utf-8"),
                    "sha256": hashlib.sha256(response.body).hexdigest(), "source_url": response.source_url,
                    "content_type": response.content_type, "metadata": response.metadata, "checked_at": time.time()}
                self._operation("document:" + url)
            return self._document_status(url, response, state="live", stale=False)

    def _site_permission(self) -> FetchResponse:
        response = self._document(ROOT)
        page = _parse_document(response.body)
        if not any("/by-nc-sa/4.0/" in href for href in page.licenses):
            error = ReemrPolicyError("官网当前没有可核验的 CC BY-NC-SA 4.0 声明；请使用有权使用的本地导入。")
            self._operation("license:" + ROOT, error)
            raise error
        return response

    def map_index(self, *, local_only: bool = False) -> list[dict[str, Any]]:
        if local_only:
            with self._lock:
                return [{"map_id": slug, "name": MAPS[slug][0], "name_en": MAPS[slug][1],
                         "source_url": ROOT + slug + "/", "local_import": True} for slug in self._imports]
        response = self._document(ROOT)
        page = _parse_document(response.body)
        found: dict[str, dict[str, Any]] = {}
        for anchor in page.anchors:
            url = urljoin(ROOT, anchor["href"])
            parsed = urlsplit(url)
            slug = parsed.path.strip("/").casefold()
            if slug in MAPS and parsed.hostname == "reemr.se":
                try:
                    _validate_url(url, "html")
                except CatalogError:
                    continue
                found.setdefault(slug, {"map_id": slug, "name": MAPS[slug][0],
                                        "name_en": MAPS[slug][1], "source_url": url,
                                        "cache_status": copy.deepcopy(response.metadata["cache_status"])})
        if not found:
            raise CatalogError("RE3MR 官网目录结构变化，未发现已支持的地图页。")
        result = list(found.values())
        self._snapshot("index", result)
        return result

    def _remote_config(self, map_id: str) -> dict[str, Any]:
        home_response = self._site_permission()
        entry = next((entry for entry in self.map_index() if entry["map_id"] == map_id), None)
        if entry is None:
            raise CatalogError("RE3MR 实时目录中没有此地图。")
        response = self._document(entry["source_url"])
        entry = {**entry, "source_url": response.source_url}
        page = _parse_document(response.body)
        if not page.licenses:
            error = ReemrPolicyError("此 RE3MR 页面缺少明确许可链接；不下载图片。")
            self._operation("license:" + entry["source_url"], error)
            raise error
        floors: dict[str, dict[str, Any]] = {}
        unmatched_versions: list[str] = []
        for anchor in page.anchors:
            url = urljoin(entry["source_url"], anchor["href"])
            try:
                _validate_url(url, "image")
            except CatalogError:
                continue
            label = anchor["text"]
            if not label or not re.search(r"[A-Za-z]", label):
                continue
            if re.match(r"version\b", label, re.I):
                if url in floors:
                    floors[url]["version"] = label
                else:
                    unmatched_versions.append(url)
                continue
            attributes = anchor["attrs"]
            if not all(str(attributes.get(key, "")).isdecimal() for key in ("data-lbwps-width", "data-lbwps-height")):
                continue
            key = "image-" + hashlib.sha256(url.encode()).hexdigest()[:20]
            floors.setdefault(url, {
                "key": key, "name": label, "name_en": label,
                "width": None, "height": None, "dimensions_verified": False,
                "image_url": url, "source_image_url": url, "source_page_url": entry["source_url"],
                "html_width_hint": int(attributes["data-lbwps-width"]),
                "html_height_hint": int(attributes["data-lbwps-height"]),
                "version": "", "deprecated": bool(re.search(r"\bOLD\b", label, re.I)),
                "variant_kind": "source-page-image", "requires_local_image_endpoint": True,
            })
        if not floors:
            raise CatalogError("RE3MR 页面没有可验证的原图目录；不猜测文件名。")
        page_sha = hashlib.sha256(response.body).hexdigest()
        evidence = {"site_license_url": LICENSE_URL, "page_license_urls": page.licenses,
                    "source_page_url": entry["source_url"], "source_page_sha256": page_sha,
                    "checked_at": response.metadata.get("fetched_at", _utc_now()),
                    "faq_url": FAQ_URL, "separate_author_permission": False,
                    "usage_scope": "personal-local-noncommercial", "redistribution_enabled": False}
        return {**entry, "floors": list(floors.values()), "annotations": [], "reference_only": False,
                "reference_material": True, "map_author": "re3mr", "map_author_url": ROOT,
                "map_license": "CC BY-NC-SA 4.0 (page may also link 2.0)",
                "map_license_url": LICENSE_URL, "license_evidence": evidence, "notice": NOTICE,
                "cache_status": {"stale": any(item["stale"] for item in (
                    home_response.metadata["cache_status"], response.metadata["cache_status"])),
                    "source_provider": "reemr", "documents": [
                        home_response.metadata["cache_status"], response.metadata["cache_status"]]},
                "unmatched_version_links": [url for url in unmatched_versions if url not in floors]}

    def map_data(self, map_id: str) -> dict[str, Any]:
        if map_id not in MAPS:
            raise CatalogError("未知 RE3MR 地图 ID。")
        with self._lock:
            imported = copy.deepcopy(self._imports.get(map_id, {}))
        if imported:
            config = {"map_id": map_id, "name": MAPS[map_id][0], "name_en": MAPS[map_id][1],
                      "source_url": ROOT + map_id + "/", "reference_only": False,
                      "reference_material": True, "annotations": [], "map_author": "re3mr",
                      "map_author_url": ROOT, "map_license": "See individual imported image evidence",
                      "map_license_url": "", "notice": NOTICE,
                      "floors": [record["floor"] for record in imported.values()]}
        else:
            config = self._remote_config(map_id)
        with self._lock:
            for floor in config["floors"]:
                metadata = self._metadata.get(floor["image_url"], {})
                page_sha = config.get("license_evidence", {}).get("source_page_sha256")
                if floor.get("local_import") or metadata.get("source_page_sha256") == page_sha:
                    floor.update(copy.deepcopy(metadata))
                if not floor.get("local_import"):
                    floor["robots"] = self._robots_status(floor["source_image_url"])
        self._snapshot("map:" + map_id, config)
        return config

    def _authorize_floor(self, config: dict[str, Any], floor: dict[str, Any]) -> dict[str, Any]:
        if floor.get("local_import"):
            record = self._imports[config["map_id"]][floor["key"]]
            evidence = record["license_evidence"]
            if evidence.get("user_rights_confirmed") is not True or not evidence.get("user_evidence", "").strip():
                raise ReemrPolicyError("本地底图缺少明确个人使用权确认与来源说明。")
            return {"allowed": True, "local_import": True, "license_evidence": copy.deepcopy(evidence)}
        try:
            self._check_robots(ROOT)
            self._check_robots(config["source_url"])
            self._check_robots(floor["source_image_url"])
        except (CatalogError, OSError) as error:
            self._operation("image:" + floor["source_image_url"], error)
            raise ReemrPolicyError(f"RE3MR 图片访问未通过规则核查，禁止缓存回退：{error}") from error
        return {"allowed": True, "local_import": False,
                "robots": self._robots_status(floor["source_image_url"]),
                "license_evidence": copy.deepcopy(config["license_evidence"])}

    def check_floor_access(self, map_id: str, floor_key: str) -> dict[str, Any]:
        """Call before external image-cache reads; denial must never trigger fallback."""
        try:
            config = self.map_data(map_id)
            floor = next((item for item in config["floors"] if item["key"] == floor_key), None)
            if floor is None:
                raise ReemrPolicyError("RE3MR 目录中没有此图片版本。")
            access = self._authorize_floor(config, floor)
            operation = self._state["operations"].get("image:" + floor["image_url"], {})
            if (operation.get("state") == "failed"
                    and operation.get("last_failure", {}).get("http_status") in {401, 403}):
                raise ReemrPolicyError("RE3MR 原图最近返回 401/403，禁止通过旧图片缓存回退。")
            return access
        except ReemrPolicyError:
            raise
        except (CatalogError, OSError) as error:
            raise ReemrPolicyError(f"RE3MR 来源或许可无法核查，禁止图片缓存回退：{error}") from error

    def floor_image(self, map_id: str, floor_key: str) -> FetchResponse:
        config = self.map_data(map_id)
        floor = next((floor for floor in config["floors"] if floor["key"] == floor_key), None)
        if floor is None:
            raise CatalogError("RE3MR 页面或本地导入中没有此图片版本。")
        started = time.monotonic()
        with self._key_lock("image:" + floor["image_url"]):
            access = self._authorize_floor(config, floor)
            if floor.get("local_import"):
                with self._lock:
                    record = copy.deepcopy(self._imports[map_id][floor_key])
                path = record["path"]
                if path.stat().st_size > MAX_IMAGE_BYTES:
                    raise CatalogError("本地底图超过 50 MB。")
                with path.open("rb") as stream:
                    body = stream.read(MAX_IMAGE_BYTES + 1)
                image_metadata = validate_image(body)
                if image_metadata["sha256"] != record["floor"]["sha256"]:
                    raise CatalogError("本地底图已改变，请重新导入确认。")
                response = FetchResponse(body, image_metadata["content_type"], floor["image_url"])
                evidence = record["license_evidence"]
            else:
                try:
                    response = self._request(floor["source_image_url"], "image")
                    image_metadata = validate_image(response.body, response.content_type)
                except (CatalogError, OSError) as error:
                    self._operation("image:" + floor["source_image_url"], error)
                    raise
                evidence = config["license_evidence"]
            metadata = {**response.metadata, **image_metadata, "map_id": map_id, "floor_key": floor_key,
                        "source_page_url": config["source_url"], "source_image_url": floor["image_url"],
                        "resolved_image_url": response.source_url, "map_author": "re3mr",
                        "map_author_url": ROOT, "map_license": config["map_license"],
                        "map_license_url": config["map_license_url"], "version": floor.get("version", ""),
                        "license_evidence": evidence, "cache_scope": "local-user-only",
                        "robots": access.get("robots"),
                        "directory_cache_status": config.get("cache_status", {"state": "local-import"}),
                        "fetched_at": response.metadata.get("fetched_at", _utc_now()),
                        "elapsed_seconds": round(time.monotonic() - started, 3), "notice": NOTICE}
            with self._lock:
                self._metadata[floor["image_url"]] = {
                    **image_metadata, "source_page_sha256": evidence.get("source_page_sha256"),
                }
            self._operation("image:" + floor["image_url"])
            self._snapshot("image:" + floor["image_url"], metadata)
            return FetchResponse(response.body, image_metadata["content_type"], response.source_url, metadata)

    def import_image(self, map_id: str, path: Path, *, name: str, rights_confirmed: bool,
                     license_evidence: str) -> dict[str, Any]:
        """Register an explicitly selected local file; never scan directories."""
        if map_id not in MAPS or rights_confirmed is not True or not license_evidence.strip() or not name.strip():
            raise CatalogError("本地导入需要有效地图、名称、个人使用权确认及许可来源说明。")
        path = Path(path).resolve(strict=True)
        if not path.is_file() or path.suffix.casefold() not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise CatalogError("本地导入只接受 PNG/JPEG/WebP 文件。")
        if path.stat().st_size > MAX_IMAGE_BYTES:
            raise CatalogError("本地底图超过 50 MB。")
        with path.open("rb") as stream:
            metadata = validate_image(stream.read(MAX_IMAGE_BYTES + 1))
        key = "local-" + metadata["sha256"][:20]
        image_url = f"local-import:{map_id}:{key}"
        floor = {"key": key, "name": name.strip(), "name_en": name.strip(), "image_url": image_url,
                 "source_page_url": ROOT + map_id + "/", "local_import": True,
                 "requires_local_image_endpoint": True, "version": "user-imported", **metadata}
        evidence = {"user_rights_confirmed": True, "user_evidence": license_evidence.strip(),
                    "usage_scope": "personal-local-noncommercial", "redistribution_enabled": False,
                    "separate_author_permission": False, "confirmed_at": _utc_now()}
        floor["license_evidence"] = copy.deepcopy(evidence)
        with self._lock:
            self._imports.setdefault(map_id, {})[key] = {"path": path, "floor": floor, "license_evidence": evidence}
            self._state["imports"].setdefault(map_id, {})[key] = {
                "path": str(path), "floor": copy.deepcopy(floor), "license_evidence": copy.deepcopy(evidence),
            }
            self._write_state()
        return copy.deepcopy(floor)


_DEFAULT = ReemrMaps()


def map_index() -> list[dict[str, Any]]:
    return _DEFAULT.map_index()


def map_data(map_id: str) -> dict[str, Any]:
    return _DEFAULT.map_data(map_id)


def floor_image(map_id: str, floor_key: str) -> FetchResponse:
    return _DEFAULT.floor_image(map_id, floor_key)


def check_floor_access(map_id: str, floor_key: str) -> dict[str, Any]:
    return _DEFAULT.check_floor_access(map_id, floor_key)
