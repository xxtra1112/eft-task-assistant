"""Adapter/cache wiring uses temporary roots, synthetic images and fake loaders."""
import io
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.robotparser import RobotFileParser

import pytest
from PIL import Image

import catalog
import reemr_maps
import tarkov_dev_maps
from catalog import CatalogError
from data_sources import SourceAdapters, capabilities
from map_preload import floor_asset_key


MAP = "55f2d3fd4bdc2d5f408b4567"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"/>'
LICENSE = '<a href="https://creativecommons.org/licenses/by-nc-sa/4.0/">License</a>'
IMAGE_URL = "https://www.re3mr.com/maps/Factory/synthetic-original.png"


def wait_until(predicate, timeout=3):
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("Timed out waiting for synthetic loader")


class ReemrHTTP:
    def __init__(self):
        stream = io.BytesIO()
        Image.new("RGB", (2048, 1024), "navy").save(stream, format="PNG")
        self.original = stream.getvalue()
        self.requests = []
        self.denied = False

    def __call__(self, url, limit, accept):
        self.requests.append(url)
        if url.endswith("/robots.txt"):
            body = b"User-agent: *\nDisallow: /maps/" if self.denied and "re3mr.com" in url else b"User-agent: *\nDisallow:\n"
            mime = "text/plain"
        elif url == reemr_maps.ROOT:
            body = ('<a href="/factory/">Factory</a>' + LICENSE).encode()
            mime = "text/html"
        elif url == reemr_maps.ROOT + "factory/":
            body = (f'<a href="{IMAGE_URL}" data-lbwps-width="12000" data-lbwps-height="8000">TOP-DOWN</a>' + LICENSE).encode()
            mime = "text/html"
        elif url == IMAGE_URL:
            assert not self.denied, "Denied original must never be requested"
            body, mime = self.original, "image/png"
        else:
            raise AssertionError("Unexpected synthetic URL: " + url)
        return reemr_maps.FetchResponse(body, mime, url, {"status": 200, "etag": '"fixture-v1"'})


@pytest.fixture
def adapters_factory(tmp_path):
    created = []

    def create(**options):
        root = options.pop("root", tmp_path / "cache")
        adapters = SourceAdapters(root=root, **options)
        created.append(adapters)
        return adapters

    yield create
    for adapters in created:
        adapters.close()


@pytest.fixture
def source_loaders(monkeypatch):
    calls = []
    robots = RobotFileParser()
    robots.parse(["User-agent: *", "Disallow:"])
    monkeypatch.setattr(catalog, "_robots_parser", lambda: robots)

    def index(source):
        def load(mode):
            calls.append(("index", source, mode))
            return [{"map_id": MAP, "name": "Synthetic", "name_en": "Synthetic"}]
        return load

    def config(source):
        def load(map_id, mode):
            calls.append(("map", source, map_id, mode))
            floors = [{"key": str(number), "width": 10, "height": 5,
                       "name": str(number), "version": "v1",
                       "src": f"{catalog.EFTARKOV_ROOT}/assets/maps/{map_id}/{number}.svg"}
                      for number in (1, 2)]
            return {"map_id": map_id, "name": "Synthetic", "name_en": "Synthetic",
                    "floors": floors, "markers": [], "annotations": [],
                    "source_url": catalog.EFTARKOV_ROOT + "/map/" + map_id,
                    "svg_url": "https://assets.tarkov.dev/synthetic.svg"}
        return load

    def image(source):
        def load(map_id, floor, mode):
            calls.append(("image", source, map_id, floor, mode))
            return SVG
        return load

    monkeypatch.setattr(tarkov_dev_maps, "fetch_tarkov_dev_map_index", index("tarkov.dev"))
    monkeypatch.setattr(tarkov_dev_maps, "fetch_tarkov_dev_map_data", config("tarkov.dev"))
    monkeypatch.setattr(tarkov_dev_maps, "fetch_tarkov_dev_map_floor_image", image("tarkov.dev"))
    monkeypatch.setattr(catalog, "fetch_eftarkov_map_index", index("eftarkov"))
    monkeypatch.setattr(catalog, "fetch_eftarkov_map_data", config("eftarkov"))
    monkeypatch.setattr(catalog, "fetch_eftarkov_map_floor_image", image("eftarkov"))
    return calls


def test_root_alias_and_owned_resources(tmp_path):
    for options in ({"cache_root": tmp_path / "old"}, {"root": tmp_path / "new"}):
        adapters = SourceAdapters(**options)
        try:
            assert adapters.asset_cache.root == adapters.root / "assets"
            status = adapters.cache_status()
            assert status["assets"]["max_bytes"] == 512 * 1024 * 1024
            assert not status["preload"]["running"]
        finally:
            adapters.close()
        assert adapters.cache_status()["assets"]["closed"]
        with pytest.raises(CatalogError, match="关闭"):
            adapters.map_index("reemr", "pve")
    with pytest.raises(ValueError):
        SourceAdapters()
    with pytest.raises(ValueError):
        SourceAdapters(tmp_path, root=tmp_path)


def test_json_same_key_inflight_is_shared(adapters_factory):
    adapters = adapters_factory()
    started, release = threading.Event(), threading.Event()
    calls = []

    def load():
        calls.append(1)
        started.set()
        assert release.wait(2)
        return {"value": "shared"}

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            first = pool.submit(adapters.cached, "tarkov.dev", "one", load)
            assert started.wait(0.5)
            others = [pool.submit(adapters.cached, "tarkov.dev", "one", load) for _ in range(3)]
            time.sleep(0.03)
            assert calls == [1]
            release.set()
            assert [future.result(1) for future in [first, *others]] == [{"value": "shared"}] * 4
    finally:
        release.set()


def test_json_different_keys_fetch_concurrently_without_global_lock(adapters_factory):
    adapters = adapters_factory()
    barrier = threading.Barrier(2)
    intervals = []

    def fetch():
        beginning = time.perf_counter()
        barrier.wait(1)
        time.sleep(0.05)
        intervals.append((beginning, time.perf_counter()))
        return {"ok": True}

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(adapters.cached, "tarkov.dev", key, fetch) for key in ("one", "two")]
        assert all(future.result(2) == {"ok": True} for future in futures)
    overlap = min(end for _, end in intervals) - max(start for start, _ in intervals)
    assert overlap >= 0.045
    print(f"SourceAdapters JSON fetch overlap: {overlap:.4f}s")


def test_selected_preload_reuses_foreground_key_without_recursion(adapters_factory, source_loaders):
    http = ReemrHTTP()
    adapters = adapters_factory(reemr_client=reemr_maps.ReemrMaps(fetcher=http))
    beginning = time.perf_counter()
    adapters.preload("tarkov.dev", "pve", MAP, all_sources=False)
    assert time.perf_counter() - beginning < 0.1
    wait_until(lambda: not adapters.cache_status()["preload"]["running"])
    status = adapters.cache_status()
    assert status["preload"]["done"] == 2
    config = adapters.map_data("tarkov.dev", MAP, "pve")
    floor = config["floors"][0]
    key = floor_asset_key("tarkov.dev", "pve", MAP, floor, config)
    manifests = [json.loads(path.read_text()) for path in adapters.asset_cache.root.glob("*.json")]
    assert key in {item["key"] for item in manifests}
    assert adapters.floor_image("tarkov.dev", MAP, "1", "pve") == SVG
    assert len([call for call in source_loaders if call[0] == "image" and call[1] == "tarkov.dev"]) == 2
    assert not any(call[1] == "eftarkov" for call in source_loaders)
    assert http.requests == []
    adapters.preload("tarkov.dev", "pve", MAP, all_sources=True)
    wait_until(lambda: not adapters.cache_status()["preload"]["running"])
    assert adapters.cache_status()["preload"]["done"] == 5
    assert len([call for call in source_loaders if call[0] == "image" and call[1] == "eftarkov"]) == 2
    assert http.requests.count(IMAGE_URL) == 1


def test_reemr_config_is_metadata_only_and_asset_preserves_original(adapters_factory):
    http = ReemrHTTP()
    adapters = adapters_factory(reemr_client=reemr_maps.ReemrMaps(fetcher=http))
    assert adapters.map_index("reemr", "pve")[0]["map_id"] == "factory"
    config = adapters.map_data("reemr", "factory", "pve")
    floor = config["floors"][0]
    assert config["reference_material"] and not config["reference_only"]
    assert config["annotations"] == config["markers"] == []
    assert floor["width"] == 12000 and floor["height"] == 8000
    assert not floor["dimensions_verified"]
    assert config["license_evidence"]["site_license_url"] == reemr_maps.LICENSE_URL
    assert IMAGE_URL not in http.requests
    asset = adapters.floor_asset("reemr", "factory", floor["key"], "pve")
    assert asset["data"] == http.original
    assert (asset["width"], asset["height"], asset["content_type"]) == (2048, 1024, "image/png")
    assert asset["dimensions_verified"] and not asset["modified"]
    assert adapters.floor_image("reemr", "factory", floor["key"], "pve") == http.original
    assert http.requests.count(IMAGE_URL) == 1
    updated = adapters.map_data("reemr", "factory", "pve")["floors"][0]
    assert updated["width"] == 2048 and updated["height"] == 1024
    assert not capabilities("reemr", "pve")["points"]
    for load in (adapters.task_catalog, lambda source, mode: adapters.task_detail(source, "task", mode)):
        with pytest.raises(CatalogError):
            load("reemr", "pve")


def test_reemr_robots_denial_warns_without_download_and_cannot_use_cached_original(adapters_factory):
    http = ReemrHTTP()
    client = reemr_maps.ReemrMaps(fetcher=http)
    adapters = adapters_factory(reemr_client=client)
    config = adapters.map_data("reemr", "factory", "pve")
    key = config["floors"][0]["key"]
    adapters.floor_image("reemr", "factory", key, "pve")
    http.denied = True
    client._robots.clear()
    before = http.requests.count(IMAGE_URL)
    config = adapters.map_data("reemr", "factory", "pve")
    assert not config["floors"][0]["available"]
    assert "robots" in str(config["floor_warnings"])
    with pytest.raises(CatalogError, match="robots"):
        adapters.floor_image("reemr", "factory", key, "pve")
    assert http.requests.count(IMAGE_URL) == before


def test_reemr_participates_in_selected_and_all_source_preload(adapters_factory, source_loaders):
    http = ReemrHTTP()
    adapters = adapters_factory(reemr_client=reemr_maps.ReemrMaps(fetcher=http))
    adapters.preload("reemr", "pve", "factory", all_sources=False)
    wait_until(lambda: not adapters.cache_status()["preload"]["running"])
    assert adapters.cache_status()["preload"]["total"] == 1
    adapters.preload("reemr", "pve", "factory", all_sources=True)
    wait_until(lambda: not adapters.cache_status()["preload"]["running"])
    assert adapters.cache_status()["preload"]["done"] == 5
    assert http.requests.count(IMAGE_URL) == 1


@pytest.mark.parametrize("path", ["/api/map/test", "/uploads/test.svg", "https://attacker.example/image.svg"])
def test_eft_disallowed_asset_cannot_reach_raw_loader(adapters_factory, source_loaders, monkeypatch, path):
    adapters = adapters_factory()
    bad = path if path.startswith("https:") else catalog.EFTARKOV_ROOT + path
    monkeypatch.setattr(catalog, "fetch_eftarkov_map_data", lambda *_: {
        "map_id": MAP, "floors": [{"key": "1", "width": 10, "height": 5, "src": bad}], "markers": []})
    with pytest.raises(CatalogError, match="API/uploads"):
        adapters.floor_image("eftarkov", MAP, "1", "pve")
    assert not any(call[0] == "image" for call in source_loaders)


def test_image_cache_restart_offline_fallback_remains_provider_scoped(adapters_factory, source_loaders, monkeypatch):
    adapters = adapters_factory()
    assert adapters.floor_image("tarkov.dev", MAP, "1", "pve") == SVG
    adapters.close()
    adapters = adapters_factory(ttl=0)

    def offline(*arguments):
        raise reemr_maps.ReemrNetworkError("synthetic offline")

    monkeypatch.setattr(tarkov_dev_maps, "fetch_tarkov_dev_map_data", offline)
    monkeypatch.setattr(tarkov_dev_maps, "fetch_tarkov_dev_map_floor_image", offline)
    assert adapters.floor_image("tarkov.dev", MAP, "1", "pve") == SVG
    assert "tarkov.dev" in adapters.cache_status()["warnings"]
    monkeypatch.setattr(catalog, "fetch_eftarkov_map_floor_image", offline)
    with pytest.raises(CatalogError):
        adapters.floor_image("eftarkov", MAP, "1", "pve")


def test_cancel_contract_and_bounded_close_during_metadata_fetch(adapters_factory, monkeypatch):
    adapters = adapters_factory(fetch_timeout=0.2)
    started, release = threading.Event(), threading.Event()

    def index(mode):
        started.set()
        release.wait(2)
        return []

    monkeypatch.setattr(tarkov_dev_maps, "fetch_tarkov_dev_map_index", index)
    try:
        adapters.preload("tarkov.dev", "pve", all_sources=False)
        assert started.wait(0.5)
        assert adapters.cancel_preload()["cancelled"]
        beginning = time.perf_counter()
        adapters.close(timeout=0.2)
        elapsed = time.perf_counter() - beginning
        assert elapsed < 0.3
        assert adapters.cache_status()["assets"]["closed"]
        print(f"SourceAdapters close while metadata blocked: {elapsed:.4f}s")
    finally:
        release.set()


def test_preload_discovery_does_not_consume_reserved_foreground_slot(adapters_factory, source_loaders, monkeypatch):
    adapters = adapters_factory(fetch_timeout=2)
    started, release = threading.Event(), threading.Event()

    def image(map_id, floor, mode):
        if str(floor) == "1":
            started.set()
            release.wait(2)
        return SVG

    monkeypatch.setattr(tarkov_dev_maps, "fetch_tarkov_dev_map_floor_image", image)
    try:
        adapters.preload("tarkov.dev", "pve", MAP, all_sources=False)
        assert started.wait(0.5)
        wait_until(lambda: adapters.cache_status()["preload"]["total"] == 2)
        beginning = time.perf_counter()
        assert adapters.floor_image("tarkov.dev", MAP, "2", "pve") == SVG
        elapsed = time.perf_counter() - beginning
        assert elapsed < 0.3
        assert not release.is_set()
        print(f"wired foreground while preload image blocked: {elapsed:.4f}s")
        release.set()
        wait_until(lambda: not adapters.cache_status()["preload"]["running"])
        assert adapters.cache_status()["preload"]["done"] == 2
    finally:
        release.set()


@pytest.mark.parametrize("width,height", [("nan", 50), (-1, 50), ("bad", 50), (99999999, 99999999)])
def test_untrusted_reemr_dimensions_fall_back_safely_without_media(adapters_factory, monkeypatch, width, height):
    http = ReemrHTTP()
    client = reemr_maps.ReemrMaps(fetcher=http)
    original = client.map_data

    def config(map_id):
        value = original(map_id)
        value["floors"][0].update(html_width_hint=width, html_height_hint=height)
        return value

    monkeypatch.setattr(client, "map_data", config)
    adapters = adapters_factory(reemr_client=client)
    floor = adapters.map_data("reemr", "factory", "pve")["floors"][0]
    assert (floor["width"], floor["height"]) == (1, 1)
    assert not floor["dimensions_verified"]
    assert IMAGE_URL not in http.requests
