"""Regression tests for reviewed supplements, not fuzzy task/photo matching."""
from copy import deepcopy
import threading
from types import SimpleNamespace

import pytest

import point_images as photos
import web_server


@pytest.fixture
def record():
    return photos.VERIFIED_POINT_PHOTOS[0]


def current_point(record, **overrides):
    return {
        "id": record["point_id"], "map_id": record["map_id"],
        "zone_id": record["zone_id"], "floor_key": record["floor_key"],
        "x_percent": record["position_percent"][0], "y_percent": record["position_percent"][1],
        "source_provider": "tarkov.dev", "source_image_urls": [],
        "title": "A translated objective is not a matching key", **overrides,
    }


def source_config(record):
    return {"map_id": record["map_id"], "markers": [{
        "id": record["legacy_marker_id"], "map_id": record["map_id"],
        "task_id": record["task_id"], "floor_key": record["legacy_floor_key"],
        "x": record["legacy_position"][0], "y": record["legacy_position"][1],
        "description": record["legacy_description"], "info_image_urls": list(record["image_urls"]),
    }]}


def test_only_exact_waypoint_enriched_without_mutating_or_importing_points(monkeypatch, record):
    monkeypatch.setattr(photos, "_source_map", lambda *_: source_config(record))
    points = [current_point(record), current_point(record, id="another-point", zone_id="possible-0-1")]
    before = deepcopy(points)
    result = photos.supplement_verified_point_images(record["task_id"], points)
    assert points == before
    assert len(result) == len(points)
    assert result[0]["source_image_urls"] == list(record["image_urls"])
    assert result[0]["source_provider"] == "tarkov.dev"
    assert result[0]["source_image_marker_id"] == record["legacy_marker_id"]
    assert result[1] == before[1]  # Other spawn of the SAME task stays empty.
    for old, new in zip(points, result):
        assert {k: v for k, v in new.items() if not k.startswith("source_image_")} == {
            k: v for k, v in old.items() if not k.startswith("source_image_")}


@pytest.mark.parametrize("change", [
    {"id": "different-stable-id"}, {"map_id": "59fc81d786f774390775787e"},
    {"floor_key": "Second_Floor"}, {"zone_id": "possible-0-1"},
    {"x_percent": 1}, {"y_percent": float("nan")}, {"source_provider": "eftarkov.com"},
])
def test_changed_current_point_is_not_matched_or_fetched(monkeypatch, record, change):
    def forbidden(*_):
        pytest.fail("Unverified current point must not fetch a legacy source")
    monkeypatch.setattr(photos, "_source_map", forbidden)
    point = current_point(record, **change)
    assert not photos.supplement_verified_point_images(record["task_id"], [point])[0]["source_image_urls"]


@pytest.mark.parametrize("field,value", [
    ("task_id", "unrelated-task"), ("map_id", "unrelated-map"),
    ("floor_key", "3"), ("x", 1), ("description", "Different location"),
    ("info_image_urls", []), ("info_image_urls", ["https://evil.example/photo.webp"]),
])
def test_missing_changed_or_unsafe_source_is_left_empty(monkeypatch, record, field, value):
    config = source_config(record);config["markers"][0][field] = value
    monkeypatch.setattr(photos, "_source_map", lambda *_: config)
    point = current_point(record)
    assert photos.supplement_verified_point_images(record["task_id"], [point]) == [point]


def test_ambiguous_legacy_marker_is_not_used(monkeypatch, record):
    config = source_config(record);config["markers"].append(deepcopy(config["markers"][0]))
    monkeypatch.setattr(photos, "_source_map", lambda *_: config)
    point = current_point(record)
    assert photos.supplement_verified_point_images(record["task_id"], [point]) == [point]


@pytest.mark.parametrize("mode", ["regular", "pvp-season"])
def test_unreviewed_game_modes_and_unknown_tasks_do_not_fetch(monkeypatch, record, mode):
    monkeypatch.setattr(photos, "_source_map", lambda *_: pytest.fail("Unexpected source fetch"))
    point = current_point(record)
    assert photos.supplement_verified_point_images(record["task_id"], [point], mode) == [point]
    assert photos.supplement_verified_point_images("another-task", [point]) == [point]


def test_existing_upstream_photo_is_preserved(monkeypatch, record):
    monkeypatch.setattr(photos, "_source_map", lambda *_: pytest.fail("Unexpected source fetch"))
    point = current_point(record, source_image_urls=["https://assets.tarkov.dev/real-waypoint.webp"])
    assert photos.supplement_verified_point_images(record["task_id"], [point]) == [point]


def test_denied_source_is_cached_without_repeated_automatic_requests(monkeypatch, record):
    calls = []
    def denied(*args):
        calls.append(args)
        raise photos.CatalogError("robots.txt denies this map")
    photos._source_map.cache_clear()
    monkeypatch.setattr(photos, "fetch_eftarkov_map_data", denied)
    try:
        point = current_point(record)
        for _ in range(2):
            assert photos.supplement_verified_point_images(record["task_id"], [point]) == [point]
        assert len(calls) == 1
    finally:
        photos._source_map.cache_clear()


@pytest.mark.parametrize("url", [
    "http://www.eftarkov.com/uploads/infoImg/1.webp",
    "https://www.eftarkov.com.evil.example/uploads/infoImg/1.webp",
    "https://user:pass@www.eftarkov.com/uploads/infoImg/1.webp",
    "https://www.eftarkov.com:8443/uploads/infoImg/1.webp",
    "https://www.eftarkov.com/uploads/infoImg/1.webp?next=evil",
    "https://www.eftarkov.com/uploads/infoImg/1.webp#fragment",
    "https://www.eftarkov.com/uploads/mapIcon/quest.png",
    "https://www.eftarkov.com/uploads/infoImg/../photo.webp",
    "https://www.eftarkov.com/uploads/infoImg/1.svg",
])
def test_source_url_restrictions(url):
    assert not photos._safe_photo_url(url)


def test_cached_details_are_enriched_on_read_without_database_update(monkeypatch, record):
    monkeypatch.setattr(photos, "_source_map", lambda *_: source_config(record))
    cached = {"details_loaded": True, "game_mode": "pve", "map_points": [current_point(record)]}
    state = object.__new__(web_server.AssistantState)
    monkeypatch.setattr(state, "_catalog_task", lambda *_: deepcopy(cached))
    state.store = SimpleNamespace(update_catalog_task_details=lambda *_: pytest.fail("Unexpected database write"))
    result = state.load_catalog_task_details(1, record["task_id"])
    assert result["map_points"][0]["source_image_urls"]
    assert not cached["map_points"][0]["source_image_urls"]


def test_map_selection_floor_changes_and_visits_keep_current_point_identity(monkeypatch, record):
    monkeypatch.setattr(photos, "_source_map", lambda *_: source_config(record))
    point = photos.supplement_verified_point_images(record["task_id"], [current_point(record)])[0]
    other_map = "56f40101d2720b2a4d8b45d6"
    other_point = {**point, "id": "another-map-point", "map_id": other_map, "source_image_urls": []}
    task = SimpleNamespace(id=1, title="Quest", trader="Trader", state="active")
    state = object.__new__(web_server.AssistantState)
    state.lock = threading.RLock();state.selected_profile_id = 1
    state.profiles = lambda: [SimpleNamespace(id=1, game_mode="pve")]
    legacy_visit = "eftarkov-" + record["legacy_marker_id"]
    visits = {legacy_visit}  # Never guess old-provider visits onto new coordinates.
    state.store = SimpleNamespace(
        list_tasks=lambda _: [task], list_map_marker_visits=lambda *_: visits,
        set_map_marker_visited=lambda _p, _m, key, value: visits.add(key) if value else visits.discard(key),
    )
    state._map_catalog_tasks = lambda *_: ({1: {"map_points": [point, other_point]}}, [])
    def config(map_id, _mode):
        return {
            "map_id": map_id, "name": "Map", "name_en": "Map",
            "map_author": "Author", "map_author_url": "", "map_license": "CC BY-NC-SA 4.0", "map_license_url": "",
            "floors": [{"key": "Ground_Floor", "name": "Ground", "is_default": True},
                       {"key": "Second_Floor", "name": "Upper"}],
            "annotations": [], "source_url": "https://tarkov.dev/map/factory-3d",
        }
    monkeypatch.setattr(web_server, "fetch_tarkov_dev_map_data", config)
    monkeypatch.setattr(web_server, "log_event", lambda *_a, **_k: None)
    ground = state.map_view(record["map_id"], "Ground_Floor")
    upper = state.map_view(record["map_id"], "Second_Floor")
    assert ground["markers"] == upper["markers"]  # Floor switches background, not task markers.
    assert len(ground["markers"]) == 1
    assert ground["markers"][0]["id"] == record["point_id"]
    assert ground["markers"][0]["source_image_urls"] == list(record["image_urls"])
    assert not ground["markers"][0]["visited"]
    state.set_map_marker_visited({"map_id": record["map_id"], "marker_id": record["point_id"], "visited": True})
    after = state.map_view(record["map_id"])["markers"][0]
    assert after["visited"] and after["source_image_urls"] == ground["markers"][0]["source_image_urls"]
    assert legacy_visit in visits  # Existing stored progress is preserved.
    assert state.map_view(other_map)["markers"][0]["id"] == "another-map-point"
    assert not state.map_view(other_map)["markers"][0]["source_image_urls"]
