"""Source adapters. Coordinates never travel between providers.

RE3MR supplies original reference imagery, never another provider's task points.
"""
from __future__ import annotations

import hashlib
import copy
import json
import math
import re
import threading
import time
import uuid
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import catalog
import tarkov_dev_catalog
import tarkov_dev_maps
import reemr_maps
from asset_cache import DiskAssetCache, FetchResult, validate_image
from catalog import CatalogError
from map_preload import MapPreloader, floor_asset_key

DEFAULT_SOURCE = "tarkov.dev"
SOURCE_URLS = {"tarkov.dev": "https://json.tarkov.dev/", "eftarkov": catalog.EFTARKOV_ROOT + "/", "reemr": "https://reemr.se/"}
SOURCE_LABELS = {"tarkov.dev": "Tarkov.dev", "eftarkov": "EFTarkov", "reemr": "RE3MR"}
SOURCE_NOTICES = {
    "tarkov.dev": "任务/底图/坐标：Tarkov.dev；物品图标：assets.tarkov.dev。底图内中文随上游提供。",
    "eftarkov": "任务/底图/坐标：EFTarkov 公开页面；不访问 robots 禁用的 API、uploads 照片或图标。未核验开放再分发许可，不打包第三方资产。",
    "reemr": reemr_maps.NOTICE,
}


def validate_source(value: str) -> str:
    if value not in SOURCE_URLS:
        raise CatalogError("未知数据源。")
    return value


def snapshot_provider(task: dict[str, Any]) -> str:
    # Old snapshots have no provider column; only their stored, exact provenance
    # decides which adapter can read them. Empty legacy provenance is Tarkov.dev.
    return "eftarkov" if task.get("catalog_source_url", "").startswith(SOURCE_URLS["eftarkov"]) else DEFAULT_SOURCE


def capabilities(source: str, game_mode: str) -> dict[str, Any]:
    source = validate_source(source)
    tasks = source != "reemr" and not (source == "eftarkov" and game_mode == "pvp-season")
    return {"id": source, "label": SOURCE_LABELS[source], "url": SOURCE_URLS[source],
            "tasks": tasks, "maps": True, "points": source != "reemr",
            "reference_only": False, "reference_material": source == "reemr",
            "preload": True, "notice": SOURCE_NOTICES[source]}


def normalize_eft_point(point: dict[str, Any], floors: list[dict[str, Any]]) -> dict[str, Any] | None:
    """EFTarkov uses native SVG pixels, not game-world or Tarkov.dev units."""
    floor = next((f for f in floors if f["key"] == str(point.get("floor_key", ""))), None)
    if floor is None or not re.fullmatch(r"[0-9a-f]{24}", str(point.get("id", "")), re.I):
        return None
    try:
        x, y, w, h = (float(point["x"]), float(point["y"]), float(floor["width"]), float(floor["height"]))
    except (KeyError, ValueError, TypeError):
        return None
    if not all(math.isfinite(v) for v in (x, y, w, h)) or w <= 0 or h <= 0 or not (0 <= x <= w and 0 <= y <= h):
        return None
    page = f"{catalog.EFTARKOV_ROOT}/map/{point['map_id']}?marker={point['id']}"
    return {**point, "id": "eftarkov-" + str(point["id"]).lower(), "source_provider": "eftarkov",
            "x_percent": 100*x/w, "y_percent": 100*y/h, "coordinate_system": "eftarkov-svg-pixels",
            "floor_name": floor["name"], "floor_name_en": floor["name"],
            "source_url": page, "source_page_url": page, "source_image_urls": [], "source_image_url": "",
            "info_image_urls": [], "info_image_url": "", "icon_url": "",
            "image_notice": "照片路径被来源 robots 禁用；可在来源页面手动查看。"}


class SourceAdapters:
    """Own image/cache workers; cache_status returns assets, preload and warnings."""

    def __init__(self, cache_root: Path | None = None, *, root: Path | None = None,
                 max_bytes: int = 512 * 1024 * 1024, workers: int = 2,
                 ttl: float = 12 * 3600, fetch_timeout: float = 100,
                 preload_all_sources: bool = True,
                 preload_max_bytes: int = 512 * 1024 * 1024, preload_max_assets: int = 512,
                 pass_budget_bytes: int | None = None,
                 discovery_timeout: float = 180,
                 reemr_client: reemr_maps.ReemrMaps | None = None) -> None:
        if (cache_root is None) == (root is None):
            raise ValueError("Supply exactly one of cache_root or root")
        if workers not in (1, 2):
            raise ValueError("Source image concurrency must be one or two")
        self.root = Path(cache_root if cache_root is not None else root)
        self.lock = threading.RLock()
        self.ttl = ttl
        self._closed = False
        self._inflight: dict[tuple[str, str], Future] = {}
        self._asset_details: dict[str, dict[str, Any]] = {}
        self._preload_all_sources = preload_all_sources
        self.reemr = reemr_client if reemr_client is not None else reemr_maps.ReemrMaps(cache_root=self.root)
        self.warnings: dict[str, str] = {}
        self._warning_keys: dict[tuple[str, str], str] = {}
        self.asset_cache = DiskAssetCache(self.root / "assets", max_bytes=min(max_bytes, 512 * 1024 * 1024),
                                          workers=workers, ttl=ttl, fetch_timeout=fetch_timeout,
                                          max_pixels=reemr_maps.MAX_PIXELS)
        self._raw_map_dataproxy = SimpleNamespace(
            map_index=lambda source, mode: self.map_index(source, mode),
            map_data=lambda source, map_id, mode: self._raw_map_data(source, map_id, mode))
        self.preloader = MapPreloader(self._raw_map_dataproxy, self.asset_cache,
                                     check_floor=lambda source, map_id, floor, mode, config:
                                         self._floor_record(source, map_id, floor, config),
                                     floor_image=self.raw_floor_image,
                                     loader_timeout=discovery_timeout,
                                     max_preload_bytes=pass_budget_bytes if pass_budget_bytes is not None else preload_max_bytes,
                                     max_preload_assets=preload_max_assets)

    def _ensure_open(self) -> None:
        with self.lock:
            if self._closed:
                raise CatalogError("数据源缓存已关闭。")

    def _warning(self, source: str, key: str, message: str | None) -> None:
        with self.lock:
            if message:
                self._warning_keys[(source, key)] = message
            else:
                self._warning_keys.pop((source, key), None)
            remaining = [value for (provider, _), value in self._warning_keys.items() if provider == source]
            if remaining:
                self.warnings[source] = remaining[-1]
            else:
                self.warnings.pop(source, None)

    def _sync_asset_warnings(self) -> None:
        warnings = self.asset_cache.status()["warnings"]
        with self.lock:
            old = [(source, key) for source, key in self._warning_keys if key.startswith("asset:")]
        for source, key in old:
            if key[6:] not in warnings:
                self._warning(source, key, None)
        for key, message in warnings.items():
            try:
                source = json.loads(key)[0]
            except (ValueError, TypeError, IndexError):
                continue
            if source in SOURCE_URLS:
                self._warning(source, "asset:" + key, message)

    def cached(self, source: str, key: str, fetch: Callable[[], Any], binary: bool = False) -> Any:
        validate_source(source)
        self._ensure_open()
        if binary:
            asset_key = json.dumps([source, "legacy", key, "binary", "v1"], separators=(",", ":"))
            try:
                return self.asset_cache.get_or_fetch(asset_key, fetch)
            finally:
                self._sync_asset_warnings()
        identity = (source, key)
        with self.lock:
            if self._closed:
                raise CatalogError("数据源缓存已关闭。")
            future = self._inflight.get(identity)
            owner = future is None
            if owner:
                future = Future()
                self._inflight[identity] = future
        if not owner:
            return copy.deepcopy(future.result())
        try:
            result = self._cached_json(source, key, fetch)
        except BaseException as error:
            future.set_exception(error)
            raise
        else:
            future.set_result(result)
            return copy.deepcopy(result)
        finally:
            with self.lock:
                self._inflight.pop(identity, None)

    def _cached_json(self, source: str, key: str, fetch: Callable[[], Any]) -> Any:
        digest = hashlib.sha256(key.encode()).hexdigest()
        path = self.root / source / (digest + ".json")
        cached = None
        fresh = False
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            fresh = 0 <= time.time() - path.stat().st_mtime < self.ttl
        except (OSError, ValueError):
            pass
        try:
            if source == "eftarkov" and key.startswith(("index:", "map:")):
                urls = [catalog.EFTARKOV_ROOT + "/map"]
                if key.startswith("map:"):
                    urls.append(catalog.EFTARKOV_ROOT + "/map/" + key.split(":", 2)[2])
                self._check_eftarkov_access(urls)
            if fresh:
                return cached
            value = fetch()
        except (CatalogError, OSError) as error:
            if not reemr_maps.temporary_network_failure(error):
                path.unlink(missing_ok=True)
                error.asset_access_denied = True
                raise
            if cached is None:
                raise
            self._warning(source, key, f"离线缓存：{error}；当前显示该来源上次成功的数据。")
            return cached
        with self.lock:
            if self._closed:
                raise CatalogError("数据源缓存已关闭。")
        temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_bytes(json.dumps(value, ensure_ascii=False).encode("utf-8"))
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        self._warning(source, key, None)
        return value

    def _check_eftarkov_access(self, urls: list[str]) -> None:
        parser = catalog._robots_parser()
        if not parser.mtime() or not (parser.allow_all or parser.default_entry or parser.entries):
            raise reemr_maps.ReemrPolicyError("EFTarkov robots 无有效规则，禁止缓存回退。")
        for url in urls:
            catalog._assert_public_url_allowed(url)

    def map_index(self, source: str, mode: str) -> list[dict[str, Any]]:
        validate_source(source)
        self._ensure_open()
        if source == "reemr":
            return self.reemr.map_index()
        fetch = tarkov_dev_maps.fetch_tarkov_dev_map_index if source == DEFAULT_SOURCE else catalog.fetch_eftarkov_map_index
        return self.cached(source, f"index:{mode}", lambda: fetch(mode))

    def _raw_map_data(self, source: str, map_id: str, mode: str) -> dict[str, Any]:
        validate_source(source)
        self._ensure_open()
        if source == "reemr":
            config = self.reemr.map_data(map_id)
            config = {**config, "annotations": [], "markers": [], "reference_only": False,
                      "reference_material": True, "source_provider": source}
        else:
            loader = tarkov_dev_maps.fetch_tarkov_dev_map_data if source == DEFAULT_SOURCE else catalog.fetch_eftarkov_map_data
            config = self.cached(source, f"map:{mode}:{map_id}", lambda: loader(map_id, mode))
        return {**config, "floors": [
            {**floor, **({"image_url": floor.get("src") or config.get("svg_url")}
                        if not floor.get("image_url") and (floor.get("src") or config.get("svg_url")) else {})}
            for floor in config.get("floors", [])]}

    def map_data(self, source: str, map_id: str, mode: str) -> dict[str, Any]:
        config = self._raw_map_data(source, map_id, mode)
        if source == DEFAULT_SOURCE:
            # Source bounds are world/projection units. Display dimensions must
            # use the actual SVG so mobile markers do not drift in letterboxing.
            first = config["floors"][0]
            image = self.floor_image(source, map_id, first["key"], mode)
            dimensions = validate_image(image, max_pixels=reemr_maps.MAX_PIXELS)
            width, height = dimensions["width"], dimensions["height"]
            return {**config, "floors": [
                {**floor, "coordinate_width": floor["width"], "coordinate_height": floor["height"],
                 "width": width, "height": height, "dimensions_basis": "svg-viewBox"}
                for floor in config["floors"]]}
        if source == "reemr":
            floors = []
            failed_floors = []
            for floor in config["floors"]:
                key = floor_asset_key(source, mode, map_id, floor, config)
                with self.lock:
                    details = dict(self._asset_details.get(key, {}))
                if not details:
                    try:
                        width = float(floor.get("html_width_hint") or floor.get("width") or 1)
                        height = float(floor.get("html_height_hint") or floor.get("height") or 1)
                        if not all(math.isfinite(value) and value > 0 for value in (width, height)) or width * height > reemr_maps.MAX_PIXELS:
                            width, height = 1, 1
                    except (TypeError, ValueError):
                        width, height = 1, 1
                    details = {"width": width, "height": height, "dimensions_verified": False,
                               "dimensions_basis": "html-hint" if (width, height) != (1, 1) else "placeholder"}
                available = True
                try:
                    self._floor_record(source, map_id, floor["key"], config)
                except CatalogError as error:
                    available = False
                    failed_floors.append({"floor_key": floor["key"], "message": str(error)})
                    self._warning(source, f"policy:{mode}:{map_id}:{floor['key']}", str(error))
                else:
                    self._warning(source, f"policy:{mode}:{map_id}:{floor['key']}", None)
                floors.append({**floor, **details, "available": available})
            notices = [f"{item['floor_key']}: {item['message']}" for item in failed_floors]
            return {**config, "floors": floors, "failed_floors": failed_floors,
                    "floor_warnings": notices, "warnings": notices}
        raw = config
        annotations = []
        omitted = 0
        for point in raw["markers"]:
            if point.get("task_id"):
                continue
            category = str(point.get("category_path", "")).casefold()
            categories = ["location"] if point.get("marker_type") == "label" else ["transfer"] if "撤离点 - 转移点" in category else ["pmc-exit"] if "撤离点 - pmc" in category else ["scav-exit"] if "撤离点 - scav" in category else []
            if not categories:
                continue
            normalized = normalize_eft_point(point, raw["floors"])
            if normalized is None:
                omitted += 1
                continue
            annotations.append({**normalized, "categories": categories, "annotation_type": "location", "title_en": point["title"]})
        return {**raw, "name_en": raw["name"], "annotations": annotations,
                "unplaced_annotation_count": omitted, "map_author": "EFTarkov（详见来源页）",
                "map_author_url": raw["source_url"], "map_license": "未核验开放再分发许可 · 在线读取",
                "map_license_url": raw["source_url"]}

    def floor_image(self, source: str, map_id: str, floor: str, mode: str) -> bytes:
        config = self._raw_map_data(source, map_id, mode)
        record = self._floor_record(source, map_id, floor, config)
        key = floor_asset_key(source, mode, map_id, record, config)
        try:
            data = self.asset_cache.get_or_fetch(key, lambda **validators: self.raw_floor_image(
                source, map_id, floor, mode, **validators))
            if source in {"reemr", "eftarkov"}:
                self._floor_record(source, map_id, floor, config)
            return data
        except (OSError, ValueError, RuntimeError) as error:
            raise CatalogError(str(error)) from error
        finally:
            self._sync_asset_warnings()

    def _floor_denial_path(self, map_id: str, floor: str) -> Path:
        key = f"floor-denial:{map_id}:{floor}"
        return self.root / "eftarkov" / (hashlib.sha256(key.encode()).hexdigest() + ".json")

    def _floor_record(self, source: str, map_id: str, floor: str,
                      config: dict[str, Any], *, retry_denied: bool = False) -> dict[str, Any]:
        record = next((item for item in config["floors"] if str(item["key"]) == str(floor)), None)
        if record is None:
            raise CatalogError("该地图没有对应楼层底图。")
        if source == "reemr":
            try:
                access = self.reemr.check_floor_access(map_id, str(floor))
                if access is False or (isinstance(access, dict) and access.get("allowed") is False):
                    raise reemr_maps.ReemrPolicyError("RE3MR floor access denied by source policy")
                if any(re.search(r"\.psd(?:[?#]|$)", str(record.get(name, "")), re.I)
                       for name in ("image_url", "source_image_url", "url", "file")):
                    raise reemr_maps.ReemrPolicyError("RE3MR PSD files are not map-floor images")
            except CatalogError as error:
                error.asset_access_denied = True
                raise
        if source == "eftarkov":
            try:
                if not retry_denied and self._floor_denial_path(map_id, floor).exists():
                    raise reemr_maps.ReemrPolicyError("EFTarkov 原图先前被拒绝，禁止读取旧图片缓存。")
                expected = re.escape(catalog.EFTARKOV_ROOT) + rf"/assets/maps/{re.escape(map_id)}/[A-Za-z0-9_-]+\.svg"
                if not re.fullmatch(expected, record.get("src", "")):
                    raise reemr_maps.ReemrPolicyError("EFTarkov 仅允许公开 assets/maps SVG；禁止 API/uploads。")
                self._check_eftarkov_access([
                    catalog.EFTARKOV_ROOT + "/map", catalog.EFTARKOV_ROOT + "/map/" + map_id,
                    record["src"]])
            except (CatalogError, OSError) as error:
                error.asset_access_denied = True
                raise
        return record

    def raw_floor_image(self, source: str, map_id: str, floor: str, mode: str, *,
                        etag: str | None = None, last_modified: str | None = None,
                        timeout: float | None = None) -> bytes | FetchResult:
        """Uncached adapter callback; upstream loaders currently return full 200 bodies."""
        config = self._raw_map_data(source, map_id, mode)
        self._floor_record(source, map_id, floor, config, retry_denied=True)
        if source == "reemr":
            try:
                response = self.reemr.floor_image(map_id, str(floor))
            except (CatalogError, OSError) as error:
                if not reemr_maps.temporary_network_failure(error):
                    error.asset_access_denied = True
                raise
            finally:
                self._floor_record(source, map_id, floor, config)
            return FetchResult(response.body, response.content_type,
                               response.metadata.get("etag") or None,
                               response.metadata.get("last_modified") or None,
                               status=response.metadata.get("status", 200))
        fetch = tarkov_dev_maps.fetch_tarkov_dev_map_floor_image if source == DEFAULT_SOURCE else catalog.fetch_eftarkov_map_floor_image
        try:
            data = fetch(map_id, floor, mode)
        except (CatalogError, OSError) as error:
            if not reemr_maps.temporary_network_failure(error):
                error.asset_access_denied = True
                if source == "eftarkov":
                    self.cached(source, f"floor-denial:{map_id}:{floor}", lambda: {"denied": True})
            raise
        else:
            if source == "eftarkov":
                self._floor_denial_path(map_id, floor).unlink(missing_ok=True)
            return data
        finally:
            if source == "eftarkov":
                self._floor_record(source, map_id, floor, config)

    def floor_asset(self, source: str, map_id: str, floor: str, mode: str) -> dict[str, Any]:
        """Original encoded bytes plus verified MIME, dimensions and content hash."""
        data = self.floor_image(source, map_id, floor, mode)
        config = self._raw_map_data(source, map_id, mode)
        record = self._floor_record(source, map_id, floor, config)
        key = floor_asset_key(source, mode, map_id, record, config)
        digest = hashlib.sha256(data).hexdigest()
        with self.lock:
            details = dict(self._asset_details.get(key, {}))
        if details.get("sha256") != digest:
            details = {**validate_image(data, max_pixels=reemr_maps.MAX_PIXELS),
                       "sha256": digest, "byte_length": len(data), "dimensions_verified": True,
                       "dimensions_basis": "decoded-image", "modified": False}
            with self.lock:
                self._asset_details[key] = details
        return {"data": data, "source_provider": source, "map_id": map_id,
                "floor_key": str(floor), **details}

    def preload(self, source: str, mode: str, preferred_map_id: str | None = None, *,
                all_sources: bool | None = None, scope: str | None = None,
                force: bool = False, resume: bool = False,
                preferred_floor: str | None = None) -> dict[str, Any]:
        """Start asynchronously. Scope wins over the legacy all_sources flag.

        Omission follows preload_all_sources (True by default); explicit False
        or scope='current' stays selected-source-only. Completed sessions are
        reused until force/resume. Call prioritize for automatic view changes.
        """
        validate_source(source)
        self._ensure_open()
        if scope not in (None, "all", "current"):
            raise ValueError("Preload scope must be 'all' or 'current'")
        enabled = scope == "all" if scope is not None else (
            self._preload_all_sources if all_sources is None else all_sources)
        with self.lock:
            self.preloader.sources = tuple(SOURCE_URLS) if enabled else None
            return self.preloader.start(source, mode, preferred_map_id,
                                        preferred_floor=preferred_floor, force=force, resume=resume)

    def prioritize(self, source: str, mode: str, mapid: str | None,
                   floor: str | None = None) -> dict[str, Any]:
        """Update map-view focus without changing scope or restarting discovery."""
        validate_source(source)
        self._ensure_open()
        return self.preloader.prioritize(source, mode, mapid, floor)

    def cancel_preload(self) -> dict[str, Any]:
        self.preloader.cancel()
        return self.preloader.status()

    def cache_status(self) -> dict[str, Any]:
        self._sync_asset_warnings()
        with self.lock:
            warnings = dict(self.warnings)
        return {"assets": self.asset_cache.status(), "preload": self.preloader.status(), "warnings": warnings}

    def close(self, timeout: float = 0.5) -> None:
        with self.lock:
            self._closed = True
        deadline = time.monotonic() + max(0, timeout)
        self.preloader.close(timeout=max(0, deadline - time.monotonic()))
        self.asset_cache.close(timeout=max(0, deadline - time.monotonic()))

    def task_detail(self, source: str, task_id: str, mode: str) -> dict[str, Any]:
        self._ensure_open()
        if not capabilities(source, mode)["tasks"]:
            raise CatalogError("该来源没有已核验的当前模式任务数据。")
        if source == DEFAULT_SOURCE:
            return tarkov_dev_catalog.fetch_tarkov_dev_task_detail(task_id, mode)
        detail = catalog.fetch_eftarkov_task_detail(task_id, mode)
        def native_points(values):
            points = []
            for point in values:
                config = self.map_data(source, point["map_id"], mode)
                normalized = normalize_eft_point(point, config["floors"])
                if normalized:
                    points.append(normalized)
            return points
        keys = [{**key, "map_points": native_points(key.get("map_points", []))}
                for key in detail.get("key_requirements", [])]
        return {**detail, "map_points": native_points(detail.get("map_points", [])), "key_requirements": keys}

    def task_catalog(self, source: str, mode: str) -> catalog.CatalogBundle:
        self._ensure_open()
        if not capabilities(source, mode)["tasks"]:
            raise CatalogError("该来源没有已核验的当前模式任务目录。")
        return (tarkov_dev_catalog.fetch_tarkov_dev_catalog if source == DEFAULT_SOURCE else catalog.fetch_eftarkov_catalog)(mode)
