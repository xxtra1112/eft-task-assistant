import json
import io
import os
import sqlite3
import time
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PIL import Image

from catalog import CatalogError
from data_sources import SourceAdapters, capabilities, normalize_eft_point, snapshot_provider
from storage import TaskStore
from web_server import APIError, AssistantState
import reemr_maps

MAP = "55f2d3fd4bdc2d5f408b4567"
POINT = "6a9d3f263c15252c7b116001"
TASK = "59675ea386f77414b32bded2"


@pytest.fixture(autouse=True)
def synthetic_reemr_and_adapter_cleanup(monkeypatch):
    stream = io.BytesIO()
    Image.new("RGB", (24, 16), "blue").save(stream, format="PNG")
    image = stream.getvalue()

    class LocalReemr:
        def __init__(self, **options):
            pass

        def map_index(self):
            return [{"map_id": slug, "name": names[0], "name_en": names[1],
                     "source_url": reemr_maps.ROOT + slug + "/"} for slug, names in reemr_maps.MAPS.items()]

        def map_data(self, map_id):
            entry = next(item for item in self.map_index() if item["map_id"] == map_id)
            return {**entry, "floors": [{"key": "original", "version": "synthetic-v1",
                                        "html_width_hint": 24, "html_height_hint": 16,
                                        "source_image_url": "https://reemr.se/maps/Factory/test.png",
                                        "image_url": "https://reemr.se/maps/Factory/test.png"}],
                    "annotations": [], "reference_only": False, "reference_material": True,
                    "map_license": "CC BY-NC-SA 4.0"}

        def check_floor_access(self, map_id, floor):
            return {"allowed": True}

        def floor_image(self, map_id, floor):
            return reemr_maps.FetchResponse(image, "image/png", "synthetic", {})

    monkeypatch.setattr(reemr_maps, "ReemrMaps", LocalReemr)
    original = SourceAdapters.__init__
    created = []

    def initialize(self, *arguments, **keywords):
        original(self, *arguments, **keywords)
        created.append(self)

    monkeypatch.setattr(SourceAdapters, "__init__", initialize)
    yield
    for adapters in created:
        adapters.close()


def add_catalog(store, provider, title):
    eft = provider == "eftarkov"
    snapshot = store.add_catalog_snapshot(
        source="eftarkov.com" if eft else "Tarkov.dev community JSON API",
        source_url="https://www.eftarkov.com/task" if eft else "https://json.tarkov.dev/pve/tasks",
        game_mode="pve", content_sha256=provider + title, metadata={"provider": provider},
    )
    store.save_catalog_tasks(snapshot, [{"source_task_id": TASK, "trader": "Prapor", "title": title}])
    return snapshot


def test_catalog_isolation_when_other_provider_has_newer_snapshot(tmp_path):
    store = TaskStore(tmp_path / "test.sqlite3")
    dev = add_catalog(store, "tarkov.dev", "Dev quest")
    eft = add_catalog(store, "eftarkov", "EFT quest")
    assert store.latest_catalog_snapshot("pve", "tarkov.dev")["id"] == dev
    assert store.latest_catalog_snapshot("pve", "eftarkov")["id"] == eft
    assert store.search_catalog_tasks("pve", provider="tarkov.dev")[0]["title"] == "Dev quest"
    assert store.search_catalog_tasks("pve", provider="eftarkov")[0]["title"] == "EFT quest"
    assert store.search_catalog_tasks("pve", provider="reemr") == []
    assert snapshot_provider(store.get_catalog_task(eft, TASK)) == "eftarkov"


def test_legacy_visit_copy_preserves_backup_and_unvisit_after_restart(tmp_path):
    path = tmp_path / "test.sqlite3"
    store = TaskStore(path)
    profile = store.default_profile_id()
    dev = "tarkovdev-" + POINT
    eft = "eftarkov-" + POINT
    store.set_map_marker_visited(profile, MAP, dev, True)
    store.set_map_marker_visited(profile, MAP, eft, True)
    store.set_map_marker_visited(profile, MAP, "unknown-legacy", True)
    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM source_migrations")
    store = TaskStore(path)
    assert store.list_map_marker_visits(profile, "tarkov.dev:" + MAP) == {dev}
    assert store.list_map_marker_visits(profile, "eftarkov:" + MAP) == {eft}
    assert store.list_map_marker_visits(profile, MAP) == {dev, eft, "unknown-legacy"}
    store.set_map_marker_visited(profile, "tarkov.dev:" + MAP, dev, False)
    store = TaskStore(path)
    assert store.list_map_marker_visits(profile, "tarkov.dev:" + MAP) == set()
    assert store.list_map_marker_visits(profile, "eftarkov:" + MAP) == {eft}


def test_native_pixel_coordinates_use_correct_floor_and_reject_bad_bounds():
    floors = [{"key": "1", "name": "一层", "width": 1600, "height": 800}]
    point = {"id": POINT, "map_id": MAP, "floor_key": "1", "x": 400, "y": 400,
             "info_image_urls": ["https://www.eftarkov.com/uploads/infoImg/a.webp"]}
    result = normalize_eft_point(point, floors)
    assert (result["x_percent"], result["y_percent"]) == (25, 50)
    assert result["id"] == "eftarkov-" + POINT
    assert result["source_image_urls"] == []  # robots-disallowed photos not requested
    assert normalize_eft_point({**point, "x": float("nan")}, floors) is None
    assert normalize_eft_point({**point, "y": 801}, floors) is None
    assert normalize_eft_point({**point, "floor_key": "2"}, floors) is None


def test_cache_is_provider_scoped_and_offline_never_silently_substitutes(tmp_path):
    adapters = SourceAdapters(tmp_path)
    assert adapters.cached("tarkov.dev", "map", lambda: {"map": "dev"}) == {"map": "dev"}
    files = list(tmp_path.rglob("*.json"))
    for f in files:
        os.utime(f, (1, 1))
    def fail():
        raise reemr_maps.ReemrNetworkError("offline")
    assert adapters.cached("tarkov.dev", "map", fail) == {"map": "dev"}
    assert "离线缓存" in adapters.warnings["tarkov.dev"]
    with pytest.raises(CatalogError):
        adapters.cached("eftarkov", "map", fail)
    assert len(list(tmp_path.rglob("*.json"))) == 1


def test_reemr_original_has_no_borrowed_tasks_or_points(tmp_path):
    adapters = SourceAdapters(tmp_path)
    maps = adapters.map_index("reemr", "pve")
    assert len(maps) == 13
    factory = adapters.map_data("reemr", "factory", "pve")
    assert not factory["reference_only"] and factory["reference_material"]
    assert len(factory["floors"]) == 1
    assert factory["annotations"] == factory["markers"] == []
    assert factory["floors"][0]["width"] == 24
    assert factory["floors"][0]["height"] == 16
    assert factory["source_url"] == "https://reemr.se/factory/"
    assert factory["map_license"] == "CC BY-NC-SA 4.0"
    assert not capabilities("reemr", "pve")["tasks"]
    assert capabilities("reemr", "pve")["maps"]
    assert not capabilities("reemr", "pve")["points"]
    assert not capabilities("eftarkov", "pvp-season")["tasks"]
    with pytest.raises(CatalogError):
        adapters.task_catalog("reemr", "pve")
    asset = adapters.floor_asset("reemr", "factory", "original", "pve")
    assert asset["data"].startswith(b"\x89PNG")
    assert asset["content_type"] == "image/png"
    with pytest.raises(CatalogError):
        adapters.task_detail("reemr", TASK, "pve")


def state_for(store):
    # Avoid automatic networking in tests, while exercising the real state/store.
    with patch.object(AssistantState, "request_catalog_refresh"):
        return AssistantState(store)


def test_switch_roundtrip_preserves_task_progress_key_fields_and_visits(tmp_path):
    store = TaskStore(tmp_path / "test.sqlite3")
    profile = store.default_profile_id()
    store.add_task("Prapor", "Quest", "需要钥匙：测试钥匙", required_count=2, profile_id=profile,
                   source_task_id=TASK, source_url="https://tarkov.dev/task/postman-pat-part-1",
                   requirements=[{"text": "寻找物品", "target_count": 2, "current_count": 1},
                                 {"text": "需要钥匙：测试钥匙", "completed": False}])
    original = store.list_tasks(profile)
    add_catalog(store, "tarkov.dev", "Dev quest")
    state = state_for(store)
    try:
        state.set_map_marker_visited({"map_id": MAP, "marker_id": "tarkovdev-" + POINT, "visited": True})
        state.select_data_source("eftarkov")
        with pytest.raises(APIError):
            state.set_map_marker_visited({"map_id": MAP, "marker_id": "tarkovdev-" + POINT, "visited": True})
        state.set_map_marker_visited({"map_id": MAP, "marker_id": "eftarkov-" + POINT, "visited": True})
        state.select_data_source("reemr")
        assert state.catalog_tasks() == []
        assert state.map_view("factory")["markers"] == []
        with pytest.raises(APIError):
            state.request_catalog_refresh()
        state.select_data_source("tarkov.dev")
        assert store.list_tasks(profile) == original
        assert store.list_map_marker_visits(profile, "tarkov.dev:" + MAP) == {"tarkovdev-" + POINT}
        assert store.list_map_marker_visits(profile, "eftarkov:" + MAP) == {"eftarkov-" + POINT}
    finally:
        state.close()
    state = state_for(TaskStore(store.path))
    try:
        assert state.source_for_profile() == "tarkov.dev"
        assert state.store.list_tasks(profile) == original
    finally:
        state.close()


def test_source_preference_is_per_profile_and_invalid_source_rejected(tmp_path):
    store = TaskStore(tmp_path / "test.sqlite3")
    state = state_for(store)
    try:
        first = state.selected_profile_id
        state.select_data_source("eftarkov")
        second = store.create_profile("Other", "pve")
        state.select_profile(second.id)
        assert state.source_for_profile() == "tarkov.dev"
        state.select_profile(first)
        assert state.source_for_profile() == "eftarkov"
        with pytest.raises(APIError):
            state.select_data_source("https://untrusted.example")
    finally:
        state.close()


def test_unrelated_cache_success_does_not_erase_offline_warning(tmp_path):
    adapters = SourceAdapters(tmp_path)
    adapters.cached("tarkov.dev", "old-map", lambda: {"map": "cached"})
    for path in tmp_path.rglob("*.json"):
        os.utime(path, (1, 1))
    def fail():
        raise reemr_maps.ReemrNetworkError("offline old-map")
    adapters.cached("tarkov.dev", "old-map", fail)
    adapters.cached("tarkov.dev", "other-map", lambda: {"map": "new"})
    assert "离线缓存" in adapters.warnings["tarkov.dev"]


def test_display_dimensions_come_from_svg_not_world_extent(tmp_path, monkeypatch):
    import tarkov_dev_maps
    adapters = SourceAdapters(tmp_path)
    raw = {"map_id": MAP, "name": "Map", "floors": [
        {"key": "ground", "width": 256, "height": 130}]}
    monkeypatch.setattr(tarkov_dev_maps, "fetch_tarkov_dev_map_data", lambda *_: raw)
    monkeypatch.setattr(adapters, "floor_image", lambda *_: b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1062.48 535.17"/>')
    config = adapters.map_data("tarkov.dev", MAP, "pve")
    assert config["floors"][0]["width"] == 1062.48
    assert config["floors"][0]["height"] == 535.17
    assert config["floors"][0]["coordinate_width"] == 256


def test_missing_map_details_load_without_blocking_or_duplicate_jobs(tmp_path, monkeypatch):
    store = TaskStore(tmp_path / "test.sqlite3")
    snapshot = add_catalog(store, "tarkov.dev", "Quest")
    task = store.add_task("Prapor", "Quest", "Find an item", source_task_id=TASK)
    state = state_for(store)
    entered, release = threading.Event(), threading.Event()
    calls = []
    def load(*args, **kwargs):
        calls.append(args)
        entered.set()
        assert release.wait(3)
        store.update_catalog_task_details(snapshot, TASK, [{"text": "Find an item"}], [], [], [])
        return store.get_catalog_task(snapshot, TASK)
    monkeypatch.setattr(state, "load_catalog_task_details", load)
    try:
        start = time.monotonic()
        values, warnings = state._map_catalog_tasks("pve", [task])
        assert time.monotonic() - start < .3
        assert values == {} and warnings == ["Quest"]
        assert entered.wait(1)
        state._map_catalog_tasks("pve", [task])
        assert len(calls) == 1
        release.set()
        deadline = time.monotonic() + 2
        while state.map_detail_loading and time.monotonic() < deadline:
            time.sleep(.01)
        assert state.map_data_revision == 1
        assert not state.map_detail_loading
    finally:
        release.set()
        state.close()
