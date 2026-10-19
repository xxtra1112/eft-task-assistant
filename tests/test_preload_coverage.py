"""Stage4 contracts: temporary roots, synthetic media, and no network access."""
import io
import socket
import threading
import time

import pytest
from PIL import Image

import asset_cache
import catalog
import reemr_maps
import tarkov_dev_maps
from asset_cache import DiskAssetCache, FetchError, FetchResult
from data_sources import SourceAdapters
from map_preload import floor_asset_key


SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 10"/>'


def settled(adapters):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        status = adapters.cache_status()["preload"]
        if not status["running"]:
            return status
        time.sleep(0.005)
    raise AssertionError("Synthetic preload did not settle")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*arguments, **keywords):
        raise AssertionError("Coverage tests must never open a network connection")
    monkeypatch.setattr(socket.socket, "connect", denied)


@pytest.fixture
def world(tmp_path, monkeypatch):
    class World:
        def __init__(self):
            self.calls = []
            self.denied = {f"denied-{number}" for number in range(7)}
            self.image_error = None
            self.after_image = None
            stream = io.BytesIO()
            Image.new("RGB", (24, 16), "navy").save(stream, format="PNG")
            self.png = stream.getvalue()
            self.created = []

        def map_index(self):
            return [{"map_id": "factory"}, {"map_id": "customs"}]

        def map_data(self, map_id):
            keys = ["lower", "upper", *sorted(self.denied_keys)] if map_id == "factory" else ["original"]
            return {"map_id": map_id, "floors": [
                {"key": key, "version": "v1", "image_url": f"https://reemr.se/maps/{map_id}/{key}.png"}
                for key in keys]}

        @property
        def denied_keys(self):
            return {f"denied-{number}" for number in range(7)}

        def check_floor_access(self, map_id, floor):
            self.calls.append(("check", "reemr", map_id, floor))
            if floor in self.denied:
                raise reemr_maps.ReemrPolicyError("Synthetic license access restriction")
            return {"allowed": True}

        def floor_image(self, map_id, floor):
            self.calls.append(("image", "reemr", map_id, floor))
            if self.image_error is not None:
                raise self.image_error
            if self.after_image is not None:
                self.after_image(map_id, floor)
            return reemr_maps.FetchResponse(self.png, "image/png", "synthetic", {})

        def make(self, **options):
            adapters = SourceAdapters(root=tmp_path / str(len(self.created)), reemr_client=self, **options)
            self.created.append(adapters)
            return adapters

    state = World()

    def config(map_id, mode):
        return {"map_id": map_id, "floors": [
            {"key": key, "version": "v1", "src": f"{catalog.EFTARKOV_ROOT}/assets/maps/{map_id}/{key}.svg"}
            for key in ("lower", "upper")], "markers": []}

    def image(source):
        def fetch(map_id, floor, mode):
            state.calls.append(("image", source, map_id, floor))
            return SVG
        return fetch

    for module, prefix, source in ((tarkov_dev_maps, "tarkov_dev", "tarkov.dev"),
                                    (catalog, "eftarkov", "eftarkov")):
        monkeypatch.setattr(module, f"fetch_{prefix}_map_index", lambda mode: [
            {"map_id": "other"}, {"map_id": "factory"}])
        monkeypatch.setattr(module, f"fetch_{prefix}_map_data", config)
        monkeypatch.setattr(module, f"fetch_{prefix}_map_floor_image", image(source))
    yield state
    for adapters in state.created:
        adapters.close()


def test_default_all_sources_and_seven_policy_blocks_are_visible(world, monkeypatch):
    adapters = world.make()
    monkeypatch.setattr(adapters, "map_data", lambda *arguments: pytest.fail("Discovery entered display/media API"))
    submitted = []
    original = adapters.asset_cache.submit

    def submit(key, *arguments, **keywords):
        submitted.append(key)
        return original(key, *arguments, **keywords)

    monkeypatch.setattr(adapters.asset_cache, "submit", submit)
    adapters.preload("tarkov.dev", "pve", "factory")
    status = settled(adapters)
    assert status["scope"] == "all"
    assert set(status["sources"]) == {"tarkov.dev", "eftarkov", "reemr"}
    assert (status["total"], status["done"], status["blocked"], status["failed"]) == (18, 11, 7, 0)
    assert status["sources"]["reemr"]["discovered"] == 10
    assert status["sources"]["reemr"]["blocked"] == 7
    assert not status["all_complete"] and not status["excluded"]
    assert not any("denied-" in key for key in submitted)
    for position, call in enumerate(world.calls):
        if call[:2] == ("image", "reemr"):
            check = ("check", *call[1:])
            assert check in world.calls[:position] and check in world.calls[position + 1:]


@pytest.mark.parametrize("constructor,options,scope,total", [
    ({}, {"all_sources": False}, "current", 4),
    ({}, {"scope": "current", "all_sources": True}, "current", 4),
    ({"preload_all_sources": False}, {}, "current", 4),
    ({"preload_all_sources": False}, {"scope": "all", "all_sources": False}, "all", 18),
])
def test_explicit_scope_overrides_constructor_default(world, constructor, options, scope, total):
    adapters = world.make(**constructor)
    adapters.preload("tarkov.dev", "pve", "factory", **options)
    status = settled(adapters)
    assert (status["scope"], status["total"]) == (scope, total)
    assert not status["all_complete"]
    if scope == "current":
        assert status["scope_complete"]
        assert not any(call[1] == "reemr" for call in world.calls)


def test_completed_session_is_reused_and_force_skips_fresh_assets(world):
    world.denied.clear()
    adapters = world.make()
    adapters.preload("tarkov.dev", "pve", "factory")
    assert settled(adapters)["all_complete"]
    run = adapters.preloader._run
    calls = list(world.calls)
    adapters.preload("reemr", "pve", "customs")
    adapters.prioritize("reemr", "pve", "factory", "upper")
    assert adapters.preloader._run is run and world.calls == calls
    adapters.preload("reemr", "pve", "factory", force=True)
    status = settled(adapters)
    assert status["all_complete"] and status["cached"] == 18 and status["downloaded"] == 0
    assert sum(call[0] == "image" for call in world.calls) == 18


def test_prioritize_changes_queued_source_map_and_floor_without_restart(world, monkeypatch):
    adapters = world.make()
    started, release = threading.Event(), threading.Event()
    original = tarkov_dev_maps.fetch_tarkov_dev_map_floor_image

    def blocked(map_id, floor, mode):
        if map_id == "factory" and floor == "lower":
            started.set()
            release.wait(3)
        return original(map_id, floor, mode)

    monkeypatch.setattr(tarkov_dev_maps, "fetch_tarkov_dev_map_floor_image", blocked)
    try:
        adapters.preload("tarkov.dev", "pve", "factory")
        assert started.wait(1)
        deadline = time.monotonic() + 3
        while adapters.preloader.status()["discovering"] and time.monotonic() < deadline:
            time.sleep(0.005)
        run = adapters.preloader._run
        adapters.prioritize("reemr", "pve", "factory", "upper")
        assert adapters.preloader._run is run and not run.cancel.is_set()
        release.set()
        settled(adapters)
        images = [call for call in world.calls if call[0] == "image"]
        assert images[1] == ("image", "reemr", "factory", "upper")
    finally:
        release.set()


def test_one_new_asset_budget_checks_cached_floors_and_resumes(world):
    world.denied.clear()
    adapters = world.make(preload_max_assets=1, preload_max_bytes=512 * 1024 * 1024)
    adapters.floor_image("reemr", "factory", "lower", "pve")
    adapters.floor_image("reemr", "factory", "upper", "pve")
    before = sum(call[0] == "image" for call in world.calls)
    adapters.preload("reemr", "pve", "customs", preferred_floor="original")
    status = settled(adapters)
    assert status["paused_budget"] and not status["all_complete"]
    assert status["cached"] == 2 and status["downloaded"] == 1
    assert status["budget"]["pass_assets"] == 1
    assert sum(call[0] == "image" for call in world.calls) == before + 1
    assert [call for call in world.calls if call[0] == "image"][-1] == ("image", "reemr", "customs", "original")
    assert status["over_budget"] == 15
    adapters.preload("reemr", "pve", "customs")
    assert sum(call[0] == "image" for call in world.calls) == before + 1
    adapters.floor_image("tarkov.dev", "factory", "lower", "pve")
    assert sum(call[0] == "image" for call in world.calls) == before + 2
    for unused in range(20):
        if status["all_complete"]:
            break
        adapters.preload("reemr", "pve", "customs", resume=True)
        status = settled(adapters)
    assert status["all_complete"]
    assert sum(call[0] == "image" for call in world.calls) == 18


def test_unknown_size_overrun_is_reported_and_resume_skips_success(world):
    adapters = world.make(preload_max_bytes=1)
    adapters.preload("tarkov.dev", "pve", "factory", scope="current")
    status = settled(adapters)
    assert status["paused_budget"] and status["downloaded"] == 1
    assert status["budget"]["pass_bytes"] == len(SVG)
    assert status["budget"]["unknown_size_overrun_bytes"] == len(SVG) - 1
    adapters.preload("tarkov.dev", "pve", "factory", scope="current", resume=True)
    status = settled(adapters)
    assert status["done"] == 2 and status["budget"]["downloaded_bytes"] == 2 * len(SVG)


def test_disk_budget_pauses_without_background_eviction_or_churn(world):
    adapters = world.make(max_bytes=1100)
    adapters.preload("tarkov.dev", "pve", "factory", scope="current")
    status = settled(adapters)
    assets = adapters.cache_status()["assets"]
    assert status["paused_budget"] and status["over_budget"] > 0
    assert not assets["evicted"] and assets["bytes"] <= assets["max_bytes"]
    count = len(world.calls)
    adapters.preload("tarkov.dev", "pve", "other", scope="current")
    assert len(world.calls) == count


def test_foreground_eviction_invalidates_all_complete(world):
    world.denied.clear()
    adapters = world.make()
    adapters.preload("tarkov.dev", "pve", "factory")
    assert settled(adapters)["all_complete"]
    adapters.asset_cache.max_bytes = adapters.asset_cache.status()["bytes"] + 1
    adapters.asset_cache.get_or_fetch("foreground-extra", lambda: SVG)
    status = adapters.cache_status()
    assert status["assets"]["evicted_count"] > 0
    assert status["preload"]["evicted"] > 0 and not status["preload"]["all_complete"]


@pytest.mark.parametrize("error", [FetchError("HTTP 403", 403),
                                  reemr_maps.ReemrPolicyError("Synthetic changed license policy")])
def test_expired_cache_denial_becomes_blocked_without_retry_or_fallback(world, error):
    world.denied.clear()
    adapters = world.make(ttl=0)
    adapters.floor_image("reemr", "customs", "original", "pve")
    world.image_error = error
    before = len([call for call in world.calls if call[0] == "image"])
    adapters.preload("reemr", "pve", "customs", scope="current", preferred_floor="original")
    status = settled(adapters)
    assert status["blocked"] == 10 and status["done"] == 0 and status["failed"] == 0
    assert len([call for call in world.calls if call[0] == "image"]) == before + 10
    assert not status["all_complete"] and not status["scope_complete"]


def test_policy_change_after_media_is_checked_before_persistence(world):
    world.denied.clear()
    adapters = world.make()
    world.after_image = lambda map_id, floor: world.denied.add(floor)
    adapters.preload("reemr", "pve", "customs", scope="current")
    status = settled(adapters)
    assert status["blocked"] == 10 and status["done"] == 0
    assert adapters.cache_status()["assets"]["entries"] == 0


def test_resume_rechecks_blocked_floors_and_does_not_download_fresh_ones(world):
    adapters = world.make()
    adapters.preload("tarkov.dev", "pve", "factory")
    assert settled(adapters)["blocked"] == 7
    world.denied.clear()
    adapters.preload("tarkov.dev", "pve", "factory", resume=True)
    assert settled(adapters)["all_complete"]
    assert len([call for call in world.calls if call[0] == "image"]) == 18


def test_image_validation_has_a_shared_decode_guard(monkeypatch):
    active = 0
    peak = 0
    lock = threading.Lock()
    original = asset_cache._validate_image

    def inspect(*arguments, **keywords):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.02)
        try:
            return original(*arguments, **keywords)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(asset_cache, "_validate_image", inspect)
    threads = [threading.Thread(target=asset_cache.validate_image, args=(SVG,)) for unused in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(1)
    assert peak == 1 and not any(thread.is_alive() for thread in threads)


@pytest.mark.parametrize("error", [FetchError("denied", 403), PermissionError("PolicyError"),
                                  OSError("robots permission revoked")])
def test_generic_expired_cache_denial_never_falls_back(tmp_path, error):
    cache = DiskAssetCache(tmp_path / "assets", ttl=0)
    calls = []

    def denied():
        calls.append(1)
        raise error

    try:
        cache.get_or_fetch("same-key", lambda: SVG)
        with pytest.raises(type(error)):
            cache.get_or_fetch("same-key", denied)
        assert calls == [1]
        assert cache.entry_status(["same-key"])["same-key"]["present"]
        assert not cache.entry_status(["same-key"])["same-key"]["fresh"]
    finally:
        cache.close()


def test_generic_ordinary_offline_still_uses_same_key_stale_cache(tmp_path):
    cache = DiskAssetCache(tmp_path / "assets", ttl=0, retries=0)

    def offline():
        raise OSError("Synthetic network outage")

    try:
        cache.get_or_fetch("same-key", lambda: SVG)
        assert cache.get_or_fetch("same-key", offline) == SVG
        assert "Offline/stale" in cache.status()["warnings"]["same-key"]
        with pytest.raises(OSError):
            cache.get_or_fetch("another-key", offline)
    finally:
        cache.close()


def test_conditional_304_does_not_spend_new_asset_budget(world):
    adapters = world.make(preload_max_assets=1)
    config = adapters._raw_map_data("tarkov.dev", "factory", "pve")
    key = floor_asset_key("tarkov.dev", "pve", "factory", config["floors"][0], config)
    adapters.asset_cache.get_or_fetch(key, lambda: FetchResult(SVG, etag="synthetic-version"))
    adapters.asset_cache.ttl = 0

    def raw(source, map_id, floor, mode, etag=None, **validators):
        if etag is not None:
            return FetchResult(status=304)
        return SVG

    adapters.preloader._floor_image = raw
    adapters.preload("tarkov.dev", "pve", "factory", scope="current", preferred_floor="lower")
    status = settled(adapters)
    assert status["cached"] == 1 and status["downloaded"] == 1 and status["paused_budget"]
    assert status["budget"]["pass_assets"] == 1 and status["budget"]["pass_requests"] == 2


def test_blocked_background_transport_does_not_hold_decode_lock_or_foreground_slot(world, monkeypatch):
    adapters = world.make()
    started, release = threading.Event(), threading.Event()
    original = world.floor_image

    def transport(map_id, floor):
        started.set()
        release.wait(3)
        return original(map_id, floor)

    monkeypatch.setattr(world, "floor_image", transport)
    try:
        adapters.preload("reemr", "pve", "customs", preferred_floor="original")
        assert started.wait(1)
        beginning = time.perf_counter()
        assert adapters.floor_image("tarkov.dev", "factory", "upper", "pve") == SVG
        assert time.perf_counter() - beginning < 0.3
        assert not release.is_set()
        release.set()
        assert settled(adapters)["failed"] == 0
    finally:
        release.set()
