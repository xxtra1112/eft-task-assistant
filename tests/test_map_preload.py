import threading
import time
from collections import Counter

import pytest

from asset_cache import DiskAssetCache, FetchResult
from map_preload import MapPreloader, floor_asset_key


SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 10"/>'


def wait_until(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("Timed out waiting for fake loaders")


class FakeAdapters:
    def __init__(self):
        self.calls = []

    def map_index(self, source, mode):
        self.calls.append(("index", source, mode))
        return [{"map_id": "other"}, {"map_id": "preferred"}, {"map_id": "preferred"}]

    def map_data(self, source, map_id, mode):
        self.calls.append(("map", source, map_id, mode))
        return {"floors": [{"key": "1", "version": "v1"},
                           {"key": "1", "version": "v1"}, {"key": "2", "version": "v1"}]}

    def floor_image(self, source, map_id, floor, mode):
        self.calls.append(("floor", source, map_id, floor, mode))
        return SVG


def test_current_source_and_map_first_and_floor_dedup(tmp_path):
    cache = DiskAssetCache(tmp_path, workers=1)
    adapters = FakeAdapters()
    preload = MapPreloader(adapters, cache, sources=("secondary", "current"))
    try:
        preload.start("current", "pve", "preferred")
        wait_until(lambda: not preload.status()["running"])
        status = preload.status()
        assert (status["total"], status["done"], status["failed"]) == (8, 8, 0)
        indexes = [call for call in adapters.calls if call[0] == "index"]
        assert [call[1] for call in indexes] == ["current", "secondary"]
        maps = [call for call in adapters.calls if call[0] == "map"]
        assert maps[0] == ("map", "current", "preferred", "pve")
        floors = [call for call in adapters.calls if call[0] == "floor"]
        assert len(floors) == len(set(floors)) == 8
        assert floors[0][1:3] == ("current", "preferred")
        assert [call[1] for call in floors] == ["current"] * 4 + ["secondary"] * 4
    finally:
        preload.close()
        cache.close()


def test_default_only_current_and_reference_source_skipped(tmp_path):
    cache = DiskAssetCache(tmp_path)
    adapters = FakeAdapters()
    preload = MapPreloader(adapters, cache)
    try:
        preload.start("current", "pve")
        wait_until(lambda: not preload.status()["running"])
        assert {call[1] for call in adapters.calls} == {"current"}
        assert preload.status()["done"] == 4
    finally:
        preload.close()
    adapters.map_data = lambda *arguments: {"reference_only": True, "floors": [{"key": "1"}]}
    preload = MapPreloader(adapters, cache, sources=("reference",), allowed=lambda source, mode: True)
    try:
        preload.start("reference", "pve")
        wait_until(lambda: not preload.status()["running"])
        assert preload.status()["total"] == 0
    finally:
        preload.close()
        cache.close()


def test_nonblocking_start_and_bounded_close_during_stuck_index(tmp_path):
    cache = DiskAssetCache(tmp_path)
    adapters = FakeAdapters()
    release = threading.Event()
    started = threading.Event()

    def stuck(*arguments):
        started.set()
        release.wait(2)
        return []

    adapters.map_index = stuck
    preload = MapPreloader(adapters, cache, loader_timeout=1)
    try:
        beginning = time.perf_counter()
        preload.start("current", "pve")
        elapsed = time.perf_counter() - beginning
        assert elapsed < 0.1
        assert started.wait(0.5)
        assert preload.status()["current"] == "current/index"
        beginning = time.perf_counter()
        preload.close(timeout=0.2)
        close_elapsed = time.perf_counter() - beginning
        assert close_elapsed < 0.3
        print(f"preload start: {elapsed:.4f}s; close while loader blocked: {close_elapsed:.4f}s")
        assert preload.status()["cancelled"]
        with pytest.raises(RuntimeError):
            preload.start("current", "pve")
    finally:
        release.set()
        preload.close()
        cache.close()


def test_loader_failures_are_visible_and_not_retried_forever(tmp_path):
    cache = DiskAssetCache(tmp_path, retries=0)
    adapters = FakeAdapters()
    calls = Counter()

    def failing(source, mode):
        calls[source] += 1
        raise OSError("offline index")

    adapters.map_index = failing
    preload = MapPreloader(adapters, cache, sources=("current", "second"))
    try:
        preload.start("current", "pve")
        wait_until(lambda: not preload.status()["running"])
        assert preload.status()["total"] == preload.status()["failed"] == 2
        assert len(preload.status()["errors"]) == 2
        assert calls == {"current": 1, "second": 1}
    finally:
        preload.close()
        cache.close()


def test_shared_foreground_key_etag_and_restart_reuse(tmp_path):
    cache = DiskAssetCache(tmp_path, ttl=0)
    adapters = FakeAdapters()
    floor = {"key": "1", "version": "v1"}
    key = floor_asset_key("current", "pve", "preferred", floor)
    cache.get_or_fetch(key, lambda: FetchResult(SVG, etag='"original"'))
    seen = []

    def image(source, map_id, floor_id, mode, etag=None, timeout=None):
        seen.append((source, map_id, floor_id, etag, timeout))
        return FetchResult(status=304) if etag else SVG

    adapters.floor_image = image
    preload = MapPreloader(adapters, cache)
    try:
        preload.start("current", "pve", "preferred")
        wait_until(lambda: not preload.status()["running"])
        assert preload.status()["done"] == 4
        assert ("current", "preferred", "1", '"original"', 15) in seen
        assert floor_asset_key("current", "pve", "preferred", {**floor, "version": "v2"}) != key
    finally:
        preload.close()
        cache.close()
    cache = DiskAssetCache(tmp_path)
    preload = MapPreloader(FakeAdapters(), cache)
    try:
        preload.start("current", "pve", "preferred")
        wait_until(lambda: not preload.status()["running"])
        assert preload.status()["done"] == 4
        assert not any(call[0] == "floor" for call in preload.adapters.calls)
    finally:
        preload.close()
        cache.close()


def test_cancel_drops_background_queue_preserves_foreground_promotion(tmp_path):
    cache = DiskAssetCache(tmp_path, workers=1, fetch_timeout=2)
    adapters = FakeAdapters()
    release = threading.Event()
    started = threading.Event()

    def block(source, map_id, floor, mode):
        started.set()
        release.wait(2)
        return SVG

    adapters.floor_image = block
    preload = MapPreloader(adapters, cache)
    try:
        preload.start("current", "pve", "preferred")
        assert started.wait(0.5)
        wait_until(lambda: preload.status()["total"] == 4 and not preload.status()["discovering"])
        floor = {"key": "2", "version": "v1"}
        key = floor_asset_key("current", "pve", "other", floor)
        promoted = cache.submit(key, lambda: SVG, priority=0)
        preload.cancel()
        assert not promoted.cancelled()
        assert preload.status()["cancelled_count"] == 2
        release.set()
        assert promoted.result(1) == SVG
        wait_until(lambda: cache.status()["queued"] == 0 and not cache.status()["running"])
    finally:
        release.set()
        preload.close()
        cache.close()


def test_allowed_filter_and_timeout_bound_discovery(tmp_path):
    cache = DiskAssetCache(tmp_path)
    adapters = FakeAdapters()
    preload = MapPreloader(adapters, cache, sources=("current", "denied"),
                           allowed=lambda source, mode: source != "denied")
    try:
        preload.start("current", "pve")
        wait_until(lambda: not preload.status()["running"])
        assert not any(call[1] == "denied" for call in adapters.calls)
    finally:
        preload.close()
    release = threading.Event()
    adapters.map_index = lambda *arguments: release.wait(2) or []
    preload = MapPreloader(adapters, cache, loader_timeout=0.05)
    try:
        preload.start("current", "pve")
        wait_until(lambda: not preload.status()["running"], timeout=0.5)
        assert preload.status()["failed"] == 1
        assert "deadline" in str(preload.status()["errors"])
    finally:
        release.set()
        preload.close()
        cache.close()


def test_raw_loader_override_and_individual_floor_failure(tmp_path):
    cache = DiskAssetCache(tmp_path, retries=0)
    adapters = FakeAdapters()
    adapters.floor_image = lambda *arguments: pytest.fail("cached adapter must not recurse")
    calls = []

    def raw_image(source, map_id, floor, mode):
        calls.append((source, map_id, floor, mode))
        if map_id == "other" and floor == "2":
            raise OSError("missing floor")
        return SVG

    preload = MapPreloader(adapters, cache, floor_image=raw_image)
    try:
        preload.start("current", "pve", "preferred")
        wait_until(lambda: not preload.status()["running"])
        status = preload.status()
        assert (status["total"], status["done"], status["failed"]) == (4, 3, 1)
        assert "missing floor" in str(status["errors"])
        assert len(calls) == 4
    finally:
        preload.close()
        cache.close()


def test_switch_while_discovery_blocked_uses_latest_source_without_waiting(tmp_path):
    cache = DiskAssetCache(tmp_path)
    adapters = FakeAdapters()
    original = adapters.map_index
    release = threading.Event()
    started = threading.Event()

    def index(source, mode):
        if source == "old":
            started.set()
            release.wait(2)
            return []
        return original(source, mode)

    adapters.map_index = index
    preload = MapPreloader(adapters, cache, loader_timeout=0.2)
    try:
        preload.start("old", "pve")
        assert started.wait(0.5)
        beginning = time.monotonic()
        preload.start("new", "pve", "preferred")
        assert time.monotonic() - beginning < 0.1
        release.set()
        wait_until(lambda: not preload.status()["running"])
        assert preload.status()["source"] == "new"
        assert preload.status()["done"] == 4
        assert not any(call[0] == "floor" and call[1] == "old" for call in adapters.calls)
    finally:
        release.set()
        preload.close()
        cache.close()
