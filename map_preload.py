"""Resumable metadata-only discovery; focus changes never restart a session.

The adapter owns URL/access policy. Explicit sources define an all-source scope;
otherwise only the selected source is discovered. Force rediscovers; resume
retries unfinished records. Both still skip fresh assets and respect budgets.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import threading
from concurrent.futures import Future
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable

from asset_cache import (AssetBudgetError, BoundedCallbacks, DiskAssetCache,
                         FetchResult, make_asset_key, policy_denied)


def floor_asset_key(source: str, mode: str, map_id: str,
                    floor: dict[str, Any], config: dict[str, Any] | None = None) -> str:
    """Share the foreground resource version and URL digest."""
    config = config or {}
    version = next((floor.get(name) for name in ("asset_version", "version", "sha256", "updated_at")
                    if floor.get(name) is not None), None)
    if version is None:
        version = next((config.get(name) for name in ("asset_version", "version", "updated_at")
                        if config.get(name) is not None), None)
    location = next((floor.get(name) for name in ("image_url", "svg_url", "url", "file")
                     if floor.get(name)), None)
    if version is not None or location:
        version = hashlib.sha256(json.dumps([version, location], sort_keys=True,
                                  ensure_ascii=False).encode("utf-8")).hexdigest()
    else:
        version = "unversioned"
    return make_asset_key(source, mode, map_id, str(floor["key"]), version)


@dataclass
class _Run:
    source: str
    mode: str
    preferred_map_id: str | None
    sources: tuple[str, ...]
    scope: str
    preferred_floor: str | None = None
    cancel: threading.Event = field(default_factory=threading.Event)
    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    futures: dict[str, Future] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    metadata_errors: dict[str, str] = field(default_factory=dict)
    discovered_sources: set[str] = field(default_factory=set)
    excluded: dict[str, str] = field(default_factory=dict)
    discovering: bool = True
    current: str | None = None
    paused_budget: bool = False
    pass_bytes: int = 0
    pass_assets: int = 0
    pass_requests: int = 0
    pass_reserved: int = 0
    downloaded_bytes: int = 0
    passes: int = 1
    waiting: tuple[Future, ...] = ()


class MapPreloader:
    def __init__(self, adapters: Any, cache: DiskAssetCache, *,
                 sources: Iterable[str] | None = None,
                 allowed: Callable[[str, str], bool] | None = None,
                 check_floor: Callable | None = None,
                 floor_image: Callable | None = None,
                 loader_timeout: float = 100, close_timeout: float = 0.5,
                 max_preload_bytes: int | None = None,
                 max_preload_assets: int = 512) -> None:
        if loader_timeout <= 0 or close_timeout < 0 or max_preload_assets < 1:
            raise ValueError("Invalid preloader limits")
        self.adapters = adapters
        self.cache = cache
        self.sources = tuple(dict.fromkeys(sources)) if sources is not None else None
        self.allowed = allowed
        self.check_floor = check_floor
        self._floor_image = floor_image
        self.loader_timeout = loader_timeout
        self.close_timeout = close_timeout
        self.max_preload_bytes = cache.max_bytes if max_preload_bytes is None else max_preload_bytes
        if self.max_preload_bytes < 1:
            raise ValueError("Invalid preload byte budget")
        self.max_preload_assets = max_preload_assets
        self._condition = threading.Condition(threading.RLock())
        self._callbacks = BoundedCallbacks(1)
        self._closed = False
        self._run: _Run | None = None
        self._pending: _Run | None = None
        self._sessions: dict[tuple[str, tuple[str, ...]], _Run] = {}
        self._thread = threading.Thread(target=self._coordinate,
                                        name="map-preload-discovery", daemon=True)
        self._thread.start()

    def prioritize(self, source: str, mode: str, map_id: str | None,
                   floor: str | None = None) -> dict[str, Any]:
        """Change focus only; do not cancel, discover, or start a completed run."""
        with self._condition:
            run = self._run
            if run is not None and run.mode == mode:
                run.source = source
                run.preferred_map_id = map_id
                run.preferred_floor = None if floor is None else str(floor)
                self.cache.reprioritize({key: self._priority(run, record)
                                        for key, record in run.records.items()})
            return self.status()

    def start(self, source: str, mode: str, preferred_map_id: str | None = None, *,
              preferred_floor: str | None = None, force: bool = False,
              resume: bool = False) -> dict[str, Any]:
        """Return immediately; only explicit force/resume restarts discovery."""
        sources = tuple(sorted(self.sources)) if self.sources is not None else (source,)
        identity = (mode, sources)
        with self._condition:
            if self._closed:
                raise RuntimeError("Map preloader is closed")
            old = self._run
            existing = self._sessions.get(identity)
            if old is not None and old is not existing:
                self._cancel_run(old)
            if existing is not None and not force:
                self._run = existing
                self.prioritize(source, mode, preferred_map_id, preferred_floor)
                if not resume or (not existing.cancel.is_set() and (existing.discovering or existing.futures)):
                    return self.status()
                run = replace(existing, cancel=threading.Event(),
                              records={key: dict(record) for key, record in existing.records.items()},
                              futures={}, errors=dict(existing.errors),
                              metadata_errors=dict(existing.metadata_errors),
                              discovered_sources=set(existing.discovered_sources),
                              excluded=dict(existing.excluded), discovering=True,
                              paused_budget=False, current=None, pass_bytes=0, pass_assets=0,
                              pass_requests=0, pass_reserved=0,
                              passes=existing.passes + 1, waiting=tuple(existing.futures.values()))
                self._sessions[identity] = run
            else:
                if existing is not None:
                    self._cancel_run(existing)
                run = _Run(source, mode, preferred_map_id, sources,
                           "all" if self.sources is not None else "current", preferred_floor)
                if existing is not None:
                    run.waiting = tuple(existing.futures.values())
                self._sessions[identity] = run
            self._run = self._pending = run
            self._condition.notify_all()
        return self.status()

    def _priority(self, run: _Run, record: dict[str, Any]) -> int:
        if record["source"] != run.source:
            return 20
        if record["map_id"] != run.preferred_map_id:
            return 10
        return 1 if record["floor"] == run.preferred_floor else 2

    def _coordinate(self) -> None:
        while True:
            with self._condition:
                while self._pending is None and not self._closed:
                    self._condition.wait()
                if self._closed:
                    return
                run = self._pending
                self._pending = None
            try:
                with self._condition:
                    while any(not future.done() for future in run.waiting) and not run.cancel.is_set():
                        self._condition.wait(0.02)
                self._discover(run)
            except Exception as error:
                self._discovery_error(run, run.source, "discovery", error)
            finally:
                with self._condition:
                    run.discovering = False
                    if not run.futures:
                        run.current = None

    def _load(self, run: _Run, loader: Callable[[], Any]) -> Any:
        if run.cancel.is_set():
            raise RuntimeError("Preload cancelled")
        result = self._callbacks.call(loader, self.loader_timeout, run.cancel)
        if run.cancel.is_set():
            raise RuntimeError("Preload cancelled")
        return result

    def _discovery_error(self, run: _Run, source: str, location: str, error: Exception) -> None:
        with self._condition:
            if not run.cancel.is_set():
                run.metadata_errors[location] = source
                run.errors[location] = str(error)

    def _discover(self, run: _Run) -> None:
        sources = list(run.sources)
        while sources and not run.cancel.is_set():
            source = min(sources, key=lambda provider: provider != run.source)
            sources.remove(source)
            try:
                if self.allowed is not None and not self._load(
                        run, lambda source=source: self.allowed(source, run.mode)):
                    with self._condition:
                        run.excluded[source] = "Source excluded by adapter policy"
                    continue
                with self._condition:
                    run.current = f"{source}/index"
                index = self._load(run, lambda source=source: self.adapters.map_index(source, run.mode))
                maps = {str(item["map_id"]): item for item in index}
                with self._condition:
                    run.discovered_sources.add(source)
                    run.metadata_errors.pop(f"{source}/index", None)
                    run.errors.pop(f"{source}/index", None)
                    run.excluded.pop(source, None)
                    run.excluded.pop(f"{source}/index", None)
                    if not maps:
                        run.excluded[f"{source}/index"] = "Source index has no discovered maps"
            except Exception as error:
                self._discovery_error(run, source, f"{source}/index", error)
                continue
            while maps and not run.cancel.is_set():
                map_id = min(maps, key=lambda item: item != run.preferred_map_id)
                maps.pop(map_id)
                with self._condition:
                    run.current = f"{source}/{map_id}"
                try:
                    config = self._load(run, lambda source=source, map_id=map_id:
                                        self.adapters.map_data(source, map_id, run.mode))
                    location = f"{source}/{map_id}"
                    with self._condition:
                        run.metadata_errors.pop(location, None)
                        run.errors.pop(location, None)
                        run.excluded.pop(location, None)
                    if config.get("reference_only"):
                        with self._condition:
                            run.excluded[location] = "Reference-only map has no preloadable floors"
                        continue
                    floors = {str(floor["key"]): floor for floor in config.get("floors", [])}
                    if not floors:
                        with self._condition:
                            run.excluded[location] = "Map has no discovered floors"
                    while floors and not run.cancel.is_set():
                        floor_id = min(floors, key=lambda item: item != run.preferred_floor)
                        floor = floors.pop(floor_id)
                        key = floor_asset_key(source, run.mode, map_id, floor, config)
                        with self._condition:
                            record = run.records.setdefault(key, {"source": source, "map_id": map_id,
                                                                 "floor": floor_id, "state": "discovered"})
                        try:
                            if self.check_floor is not None:
                                access = self._load(run, lambda source=source, map_id=map_id,
                                                    floor_id=floor_id, config=config:
                                                    self.check_floor(source, map_id, floor_id, run.mode, config))
                                if access is False or (isinstance(access, dict) and access.get("allowed") is False):
                                    raise PermissionError("Floor access denied by adapter policy")
                        except Exception as error:
                            with self._condition:
                                record["state"] = "cancelled" if run.cancel.is_set() else "blocked"
                                run.errors[key] = str(error)
                            continue
                        self._submit(run, key, record, config)
                except Exception as error:
                    self._discovery_error(run, source, f"{source}/{map_id}", error)

    def _submit(self, run: _Run, key: str, record: dict[str, Any], config: dict[str, Any]) -> None:
        source, map_id, floor = record["source"], record["map_id"], record["floor"]
        received = {"bytes": 0}

        def fetch(**validators: Any) -> Any:
            with self._condition:
                if run.cancel.is_set():
                    raise RuntimeError("Preload cancelled")
                if (run.paused_budget or run.pass_bytes >= self.max_preload_bytes or
                        run.pass_assets + run.pass_reserved >= self.max_preload_assets):
                    run.paused_budget = True
                    raise AssetBudgetError("Preload pass budget exhausted; resume explicitly")
                run.pass_requests += 1
                run.pass_reserved += 1
            loader = self._floor_image or self.adapters.floor_image
            try:
                parameters = inspect.signature(loader).parameters
                accepts_keywords = any(parameter.kind == inspect.Parameter.VAR_KEYWORD
                                       for parameter in parameters.values())
                keywords = {name: value for name, value in validators.items()
                            if accepts_keywords or (name in parameters and
                            parameters[name].kind != inspect.Parameter.POSITIONAL_ONLY)}
            except (TypeError, ValueError):
                keywords = {}
            try:
                raw = loader(source, map_id, floor, run.mode, **keywords)
            except BaseException:
                with self._condition:
                    run.pass_reserved -= 1
                raise
            payload = raw.data if isinstance(raw, FetchResult) else raw.get("data", b"") if isinstance(raw, dict) else raw
            size = len(payload) if isinstance(payload, bytes) else 0
            with self._condition:
                run.pass_reserved -= 1
                run.pass_assets += int(size > 0)
                received["bytes"] += size
                record["downloaded_bytes"] = record.get("downloaded_bytes", 0) + size
                run.pass_bytes += size
                run.downloaded_bytes += size
            return raw

        with self._condition:
            if run.cancel.is_set():
                record["state"] = "cancelled"
                return
            if key in run.futures:
                return
            run.errors.pop(key, None)
            if self.cache.fresh_entry(key):
                if record["state"] != "downloaded":
                    record["state"] = "cached"
                return
            record["state"] = "queued"
            future = self.cache.submit(key, fetch, self._priority(run, record), allow_eviction=False)
            run.futures[key] = future

        def complete(result: Future) -> None:
            access_error = None
            if self.check_floor is not None and not run.cancel.is_set():
                try:
                    access = self._load(run, lambda: self.check_floor(source, map_id, floor, run.mode, config))
                    if access is False or (isinstance(access, dict) and access.get("allowed") is False):
                        raise PermissionError("Floor access denied after image load")
                except Exception as caught:
                    access_error = caught
            with self._condition:
                run.futures.pop(key, None)
                error = None if result.cancelled() else result.exception()
                if result.cancelled() or (run.cancel.is_set() and error is not None):
                    record["state"] = "cancelled"
                elif access_error is not None:
                    record["state"] = "blocked"
                    error = access_error
                elif isinstance(error, AssetBudgetError):
                    run.paused_budget = True
                    record["state"] = "over_budget"
                elif error is not None:
                    record["state"] = "blocked" if policy_denied(error) else "failed"
                else:
                    record["state"] = "downloaded" if received["bytes"] else "cached"
                if error is not None:
                    run.errors[key] = str(error)
                if not run.futures and not run.discovering:
                    run.current = None
                self._condition.notify_all()

        future.add_done_callback(complete)

    def status(self) -> dict[str, Any]:
        with self._condition:
            run = self._run
            if run is None:
                return {"total": 0, "done": 0, "failed": 0, "current": None,
                        "running": False, "cancelled": False, "cancelled_count": 0,
                        "errors": {}, "closed": self._closed, "sources": {},
                        "all_complete": False, "scope_complete": False, "paused_budget": False}
            entries = self.cache.entry_status(run.records)
            names = ("discovered", "cached", "downloaded", "blocked", "failed", "cancelled",
                     "over_budget", "evicted", "stale", "pending", "downloaded_bytes")
            providers = {source: dict.fromkeys(names, 0) for source in run.sources}
            for key, record in run.records.items():
                provider = providers[record["source"]]
                provider["discovered"] += 1
                provider["downloaded_bytes"] += record.get("downloaded_bytes", 0)
                state = record["state"]
                if state in ("cached", "downloaded"):
                    provider[state] += 1
                    if not entries[key]["present"]:
                        provider["evicted"] += 1
                    elif not entries[key]["fresh"]:
                        provider["stale"] += 1
                elif state in provider and state != "discovered":
                    provider[state] += 1
                else:
                    provider["pending"] += 1
            for source in run.metadata_errors.values():
                providers[source]["failed"] += 1
            totals = {name: sum(provider[name] for provider in providers.values()) for name in names}
            running = not run.cancel.is_set() and (run.discovering or bool(run.futures))
            scope_complete = (not running and not run.cancel.is_set() and not run.paused_budget and
                              bool(run.records) and not run.excluded and
                              run.discovered_sources == set(run.sources) and
                              not any(totals[name] for name in ("blocked", "failed", "cancelled",
                                                               "over_budget", "evicted", "stale", "pending")))
            current = next((key for key in self.cache.status()["running"] if key in run.futures), run.current)
            per_source = {source: {**counts,
                "total": counts["discovered"] + sum(value == source for value in run.metadata_errors.values()),
                "done": counts["cached"] + counts["downloaded"], "deferred": counts["over_budget"]}
                for source, counts in providers.items()}
            return {"source": run.source, "mode": run.mode, "preferred_map_id": run.preferred_map_id,
                    "preferred_floor": run.preferred_floor, "scope": run.scope,
                    "requested_sources": list(run.sources), "sources": providers,
                    "per_source": per_source, "deferred": totals["over_budget"],
                    "complete": not running and not run.cancel.is_set() and not run.paused_budget,
                    "coverage": {"scope_complete": scope_complete, "all_sources_complete": scope_complete and run.scope == "all"},
                    "total": len(run.records) + len(run.metadata_errors),
                    "done": totals["cached"] + totals["downloaded"], "failed": totals["failed"],
                    "blocked": totals["blocked"], "over_budget": totals["over_budget"],
                    "evicted": totals["evicted"], "cached": totals["cached"],
                    "downloaded": totals["downloaded"], "current": current,
                    "discovering": run.discovering, "running": running,
                    "cancelled": run.cancel.is_set(), "cancelled_count": totals["cancelled"],
                    "paused_budget": run.paused_budget, "scope_complete": scope_complete,
                    "all_complete": scope_complete and run.scope == "all",
                    "excluded": dict(run.excluded), "errors": dict(run.errors), "closed": self._closed,
                    "records": {key: dict(record) for key, record in run.records.items()},
                    "budget": {"max_bytes": self.max_preload_bytes, "max_assets": self.max_preload_assets,
                               "pass_bytes": run.pass_bytes, "pass_assets": run.pass_assets,
                               "pass_requests": run.pass_requests,
                               "downloaded_bytes": run.downloaded_bytes, "passes": run.passes,
                               "unknown_size_overrun_bytes": max(0, run.pass_bytes - self.max_preload_bytes)}}

    def _cancel_run(self, run: _Run) -> None:
        run.cancel.set()
        run.discovering = False
        run.current = None
        self.cache.cancel_pending(set(run.futures))

    def cancel(self) -> None:
        with self._condition:
            if self._run is not None:
                self._cancel_run(self._run)

    def close(self, timeout: float | None = None) -> None:
        self.cancel()
        self._callbacks.close()
        with self._condition:
            self._closed = True
            self._condition.notify_all()
        if self._thread is not threading.current_thread():
            self._thread.join(self.close_timeout if timeout is None else max(0, timeout))
