import hashlib
import json
import os
import shutil
import sqlite3
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import web_server
from storage import TaskStore
from tarkov_dev_catalog import _task_details


FACTORY = "55f2d3fd4bdc2d5f408b4567"
CUSTOMS = "56f40101d2720b2a4d8b45d6"
TASK = "59675ea386f77414b32bded2"
OTHER_TASK = "59674eb386f774539f14813a"
KEY = "5937ee6486f77408994ba448"
OTHER_KEY = "5938144586f77473c2087145"


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local-data"))
    monkeypatch.setattr(web_server, "log_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(web_server.AssistantState, "request_catalog_refresh", lambda *_args: None)


@pytest.fixture
def state(tmp_path):
    assistant = web_server.AssistantState(TaskStore(tmp_path / "tasks.sqlite3"))
    yield assistant
    assistant.close()


def catalog(store, provider="tarkov.dev", task_id=TASK, mode="pve", **details):
    snapshot = store.add_catalog_snapshot(
        source="Tarkov.dev community JSON API" if provider == "tarkov.dev" else "eftarkov.com",
        source_url="https://www.eftarkov.com/task", game_mode=mode,
        metadata={"provider": provider},
    )
    store.save_catalog_tasks(snapshot, [{"source_task_id": task_id, "title": "Quest",
                                          "trader": "Prapor", "details_loaded": True, **details}])
    return snapshot


def task(store, task_id=TASK, objective="Find item", **kwargs):
    return store.add_task("Prapor", task_id or "Manual quest", objective, source_task_id=task_id, **kwargs)


def key(item_id=KEY, name="办公室钥匙", **kwargs):
    return {"item_id": item_id, "name": name, "item_kind": "key", **kwargs}


def map_config(map_id):
    return {"map_id": map_id, "name": "Map", "name_en": "Map", "map_author": "Author",
            "map_author_url": "", "map_license": "", "map_license_url": "",
            "source_url": "https://tarkov.dev/map/factory", "annotations": [],
            "floors": [{"key": "ground", "name": "Ground", "is_default": True}]}


def point(map_id=FACTORY, **kwargs):
    return {"map_id": map_id, "source_provider": "tarkov.dev", "id": "tarkovdev-point",
            "floor_key": "ground", "x_percent": 25, "y_percent": 50, **kwargs}


def test_provenance_uses_task_id_mode_and_catalog_origin_instead_of_reference_url(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    original = task(store)
    snapshot = catalog(store)
    catalog(store, "eftarkov", mode="regular")
    catalog(store, "eftarkov", task_id=OTHER_TASK)
    assert store.task_data_provider(original.id) == "tarkov.dev"
    assert store.latest_catalog_snapshot("pve", "tarkov.dev")["id"] == snapshot
    assert store.get_catalog_task(snapshot, TASK)["data_provider"] == "tarkov.dev"
    reopened = TaskStore(store.path)
    assert reopened.task_data_provider(original.id) == "tarkov.dev"
    assert reopened.list_tasks(original.profile_id) == [original]


def test_ambiguous_or_url_only_provenance_is_not_guessed(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    original = task(store)
    catalog(store)
    catalog(store, "eftarkov")
    assert store.task_data_provider(original.id) == ""
    snapshot = store.add_catalog_snapshot(source="unknown", source_url="https://json.tarkov.dev/pve/tasks", game_mode="pve")
    store.save_catalog_tasks(snapshot, [{"source_task_id": OTHER_TASK, "title": "Quest"}])
    unknown = task(store, OTHER_TASK)
    assert store.task_data_provider(unknown.id) == ""
    assert store.get_catalog_task(snapshot, OTHER_TASK)["data_provider"] == ""
    with pytest.raises(web_server.APIError, match="来源未确认"):
        web_server._catalog_provider(store.get_catalog_task(snapshot, OTHER_TASK))


@pytest.mark.parametrize("mode,provider,source_task", [
    ("regular", "tarkov.dev", TASK), ("pve", "eftarkov", TASK),
    ("pve", "tarkov.dev", OTHER_TASK),
])
def test_explicit_provenance_rejects_wrong_mode_provider_and_task(tmp_path, mode, provider, source_task):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    original = task(store)
    snapshot = catalog(store, provider, source_task, mode)
    with pytest.raises(ValueError, match="稳定任务 ID"):
        store.record_task_data_provider(original.id, "tarkov.dev", snapshot)


@pytest.mark.parametrize("status", ["matched", "no_points", "loading", "catalog_unavailable", "unmatched"])
def test_normal_map_returns_original_ids_and_contexts_without_mutating_requirements(state, monkeypatch, status):
    original = task(state.store, requirements=[{"text": "Collect three", "target_count": 3, "current_count": 2}])
    original_snapshot = catalog(state.store, map_ids=[FACTORY], map_points=[point()] if status == "matched" else [])
    state.store.record_task_data_provider(original.id, "tarkov.dev", original_snapshot)
    selected_provider = "eftarkov" if status in {"catalog_unavailable", "unmatched"} else "tarkov.dev"
    if status == "unmatched":
        catalog(state.store, "eftarkov", OTHER_TASK)
    cached = state.store.get_catalog_task(original_snapshot, TASK)
    monkeypatch.setattr(state.sources, "map_data", lambda *_args: map_config(FACTORY))
    monkeypatch.setattr(state, "_map_catalog_tasks", lambda *_args: ({original.id: cached} if status in {"matched", "no_points"} else {}, []))
    view = state.map_view(FACTORY, provider=selected_provider)
    assert [entry["id"] for entry in view["tasks"]] == [original.id]
    context = view["task_contexts"][0]
    assert context["id"] == original.id
    assert context["point_status"] == status
    assert context["map_relevant"] is True
    assert context["known_map_ids"] == [FACTORY]
    assert context["data_provider"] == "tarkov.dev"
    assert state.store.list_tasks(original.profile_id) == [original]
    assert state.snapshot()["tasks"][0]["requirements"] == original.requirements


def test_other_map_excluded_and_unknown_association_explicit(state, monkeypatch):
    original = task(state.store)
    catalog(state.store, map_ids=[CUSTOMS])
    unknown = task(state.store, "", objective="Unconfirmed map")
    monkeypatch.setattr(state.sources, "map_data", lambda *_args: map_config(FACTORY))
    monkeypatch.setattr(state, "_map_catalog_tasks", lambda *_args: ({}, []))
    view = state.map_view(FACTORY, provider="eftarkov")
    contexts = {entry["id"]: entry for entry in view["task_contexts"]}
    assert contexts[original.id]["map_relevant"] is False
    assert contexts[original.id]["point_status"] == "other_map"
    assert contexts[unknown.id]["map_relevant"] is None
    assert "尚未确认" in contexts[unknown.id]["point_message"]
    assert {entry["id"] for entry in view["tasks"]} == {original.id, unknown.id}


@pytest.mark.parametrize("slug,map_id", [
    ("factory", FACTORY), ("factory", "59fc81d786f774390775787e"),
    ("ground-zero", "653e6760052c01c1c805532f"),
    ("ground-zero", "65b8d6f5cdde2479cb2a3125"),
])
def test_reemr_uses_explicit_map_ids_and_excludes_known_other_maps(state, monkeypatch, slug, map_id):
    def reference_map(_source, identifier, _mode):
        return {"map_id": identifier, "name": identifier, "name_en": identifier,
                "source_url": "https://reemr.se/" + identifier + "/", "reference_material": True,
                "reference_only": False, "floors": [{"key": "original", "width": 24, "height": 16}]}

    monkeypatch.setattr(state.sources, "map_data", reference_map)
    original = task(state.store)
    catalog(state.store, map_ids=[map_id])
    view = state.map_view(slug, provider="reemr")
    assert view["markers"] == []
    assert view["task_contexts"][0]["point_status"] == "reference_only"
    assert view["task_contexts"][0]["map_relevant"] is True
    assert view["tasks"][0]["id"] == original.id
    assert view["image_url"].startswith("/api/map/image?")
    customs = state.map_view("customs", provider="reemr")["task_contexts"][0]
    assert customs["map_relevant"] is False
    assert customs["point_status"] == "other_map"
    terminal = state.map_view("terminal", provider="reemr")["task_contexts"][0]
    assert terminal["map_relevant"] is None
    assert "尚未确认" in terminal["point_message"]


@pytest.mark.parametrize("bad_point", [point(floor_key="missing"), point(x_percent=float("nan"))])
def test_unrenderable_points_are_no_points_not_matched(state, monkeypatch, bad_point):
    original = task(state.store)
    snapshot = catalog(state.store, map_points=[bad_point])
    monkeypatch.setattr(state.sources, "map_data", lambda *_args: map_config(FACTORY))
    monkeypatch.setattr(state, "_map_catalog_tasks", lambda *_args: ({original.id: state.store.get_catalog_task(snapshot, TASK)}, []))
    view = state.map_view(FACTORY)
    assert view["markers"] == []
    assert view["task_contexts"][0]["point_status"] == "no_points"


def test_key_identity_aliases_and_progress_survive_provider_switch_and_catalog_replacement(state):
    original = task(state.store, objective="需要钥匙：办公室钥匙", requirements=[{"text": "Find", "completed": True}])
    snapshot = catalog(state.store, key_requirements=[key(id="legacy-office-key")])
    state.store.record_task_data_provider(original.id, "tarkov.dev", snapshot)
    catalog(state.store, task_id=OTHER_TASK)
    catalog(state.store, "eftarkov", key_requirements=[key(OTHER_KEY)])
    state.select_data_source("eftarkov")
    payload = state.snapshot()["tasks"][0]
    canonical = payload["key_requirements"][0]
    assert canonical["item_id"] == KEY
    assert canonical["image_url"] == f"https://assets.tarkov.dev/{KEY}-icon.webp"
    assert canonical["preference_aliases"] == ["legacy-office-key", "办公室钥匙"]
    assert payload["requirements"] == original.requirements
    assert state.store.list_tasks(original.profile_id) == [original]


def test_ambiguous_same_name_aliases_are_preserved_without_migration(state):
    first = task(state.store, objective="需要钥匙：办公室钥匙")
    snapshot = catalog(state.store, key_requirements=[key()])
    state.store.record_task_data_provider(first.id, "tarkov.dev", snapshot)
    second = task(state.store, OTHER_TASK, objective="需要钥匙：办公室钥匙")
    other_snapshot = catalog(state.store, task_id=OTHER_TASK, key_requirements=[key(OTHER_KEY)])
    state.store.record_task_data_provider(second.id, "tarkov.dev", other_snapshot)
    for payload in state.snapshot()["tasks"]:
        canonical = payload["key_requirements"][0]
        assert canonical["preference_aliases"] == []
        assert "未自动迁移" in canonical["preference_message"]


def test_objective_key_without_original_catalog_item_id_does_not_use_same_name_from_other_task(state):
    original = task(state.store, objective="需要钥匙：办公室钥匙")
    catalog(state.store, task_id=OTHER_TASK, key_requirements=[key()])
    payload = state.snapshot()["tasks"][0]
    assert payload["id"] == original.id
    unresolved = payload["key_requirements"][0]
    assert unresolved["item_id"] == unresolved["image_url"] == ""
    assert unresolved["preference_aliases"] == []


@pytest.mark.parametrize("text", ["在海关穿戴指定装备消灭 PMC", "Eliminate PMCs on Customs"])
def test_explicit_legacy_objective_map_is_retained_without_inventing_points(state, text):
    task(state.store, requirements=[{"text": text, "target_count": 8}])
    factory_context = state.map_view("factory", provider="reemr")["task_contexts"][0]
    customs_context = state.map_view("customs", provider="reemr")["task_contexts"][0]
    assert factory_context["map_relevant"] is False
    assert factory_context["point_status"] == "other_map"
    assert customs_context["map_relevant"] is True
    assert customs_context["point_status"] == "reference_only"
    assert state.map_view("customs", provider="reemr")["markers"] == []


@pytest.mark.parametrize("text, expected", [
    ("在森林伐木场码头寻找实验室日志", {"5704e3c2d2720bac5b8b4567"}),
    ("Find the lab log on Shoreline", {"5704e554d2720bac5b8b456e"}),
    ("找到实验室日志", set()),
    ("找到伐木场码头", set()),
])
def test_map_inference_does_not_use_item_names_or_generic_pier_locations(state, text, expected):
    saved = task(state.store, requirements=[{"text": text}])
    assert state._task_declared_map_ids(saved) == expected


def test_task_details_keep_map_ids_without_coordinates_and_canonical_key_id(state):
    raw = {"id": TASK, "objectives": [{"description": "Find", "maps": [FACTORY], "type": "visit"}],
           "neededKeys": [{"map": FACTORY, "keys": [KEY]}]}
    details = _task_details(raw, {}, {}, {TASK: raw}, {}, {}, {},
                            {KEY: {"id": KEY, "name": "办公室钥匙", "types": ["keys"]}}, {}, {}, [], [])
    assert details["map_ids"] == [FACTORY]
    assert details["key_requirements"][0]["item_id"] == KEY
    snapshot = catalog(state.store)
    state.store.update_catalog_task_details(snapshot, TASK, details["objectives"],
                                           key_requirements=details["key_requirements"], map_ids=details["map_ids"])
    assert state.store.get_catalog_task(snapshot, TASK)["map_ids"] == [FACTORY]
    copy_store = TaskStore(state.store.path.parent / "copy.sqlite3")
    copy_store.sync_catalog_from(state.store.path)
    assert copy_store.search_catalog_tasks("pve")[0]["map_ids"] == [FACTORY]


@pytest.mark.parametrize("url", [
    "https://www.eftarkov.com/uploads/infoImg/a.webp",
    "https://eftarkov.com/api/image/a.png", "https://www.eftarkov.com/assets/icon.png",
    "https://images.weserv.nl/?url=www.eftarkov.com/uploads/a.webp",
    "https://assets.tarkov.dev.evil.example/a.webp", "https://user@assets.tarkov.dev/a.webp",
    "https://assets.tarkov.dev:443/a.webp", "http://assets.tarkov.dev/a.webp",
    "https://assets.tarkov.dev/../a.webp", "https://assets.tarkov.dev/%2e%2e/a.webp",
    "https://assets.tarkov.dev/a.webp?url=https://www.eftarkov.com/api/a",
])
def test_restricted_images_removed_at_backend_boundary(url):
    assert web_server._safe_image_url(url) == ""
    raw = {"key_requirements": [key(image_url=url, map_points=[{"info_image_urls": [url]}])],
           "map_points": [{"source_image_urls": [url], "source_image_url": url}]}
    cleaned = web_server._catalog_images(raw)
    assert cleaned["key_requirements"][0]["image_url"] == ""
    assert cleaned["map_points"][0]["source_image_urls"] == []
    assert cleaned["key_requirements"][0]["map_points"][0]["info_image_urls"] == []
    assert raw["map_points"][0]["source_image_urls"] == [url]


def test_assets_images_are_allowed_in_detail_list_snapshot_and_map(state, monkeypatch):
    image = f"https://assets.tarkov.dev/{KEY}-icon.webp"
    original = task(state.store)
    snapshot = catalog(state.store, key_requirements=[key(image_url=image)], map_points=[point(source_image_urls=[image])])
    state.store.record_task_data_provider(original.id, "tarkov.dev", snapshot)
    monkeypatch.setattr(web_server, "supplement_verified_point_images", lambda _task, points, _mode: points)
    assert state.load_catalog_task_details(snapshot, TASK)["map_points"][0]["source_image_urls"] == [image]
    assert state.catalog_tasks()[0]["key_requirements"][0]["image_url"] == image
    assert state.snapshot()["tasks"][0]["key_requirements"][0]["image_url"] == image
    monkeypatch.setattr(state.sources, "map_data", lambda *_args: map_config(FACTORY))
    monkeypatch.setattr(state, "_map_catalog_tasks", lambda *_args: ({original.id: state.store.get_catalog_task(snapshot, TASK)}, []))
    assert state.map_view(FACTORY)["markers"][0]["source_image_urls"] == [image]


def test_item_image_route_is_not_an_open_proxy(state, monkeypatch):
    manager = SimpleNamespace(local_player=object(), state_for=lambda _player: state,
                              auth=SimpleNamespace(session_scope=lambda _token: None, authenticate=lambda _token: None))
    handler = web_server._make_handler(manager)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with patch("urllib.request.urlopen", side_effect=AssertionError("No image requests allowed")):
            for target in ("https://www.eftarkov.com/api/a", "https://www.eftarkov.com/uploads/a.webp",
                           "https://images.weserv.nl/?url=www.eftarkov.com/uploads/a.webp"):
                connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                try:
                    connection.request("GET", "/api/item-image?" + web_server.urlencode({"url": target}))
                    response = connection.getresponse()
                    assert response.status == 404
                    assert json.loads(response.read())["error"] == "路径不存在。"
                finally:
                    connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_private_backup_copy_preserves_real_task_rows_and_requirements(tmp_path):
    backup_name = os.environ.get("EFT_BACKEND_BACKUP_DB")
    if not backup_name:
        pytest.skip("Private backup fixture is opt-in and never distributed")
    backup = Path(backup_name)
    assert backup.parent.name == "private-backups"
    digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    copied = tmp_path / "backup-copy.sqlite3"
    shutil.copy2(backup, copied)
    with sqlite3.connect(copied) as connection:
        baseline = connection.execute("SELECT * FROM tasks ORDER BY id").fetchall()
    store = TaskStore(copied)
    profile = store.default_profile_id()
    originals = store.list_tasks(profile)
    with store._connect() as connection:
        assert [tuple(row) for row in connection.execute("SELECT * FROM tasks ORDER BY id")] == baseline
    with patch.object(web_server.AssistantState, "request_catalog_refresh"):
        assistant = web_server.AssistantState(store)
    try:
        snapshot = assistant.snapshot()
        assert len(snapshot["tasks"]) == 30
        keys = [key for entry in snapshot["tasks"] for key in entry["key_requirements"]]
        assert len(keys) == 8
        assert all(key["item_id"] and key["image_url"].startswith("https://assets.tarkov.dev/") for key in keys)
        assert all(key["preference_aliases"] for key in keys)
        assert {entry["id"] for entry in snapshot["tasks"]} == {entry.id for entry in originals}
        for slug in ("factory", "customs", "ground-zero", "terminal"):
            view = assistant.map_view(slug, provider="reemr")
            expected = {entry.id for entry in originals if entry.state != "complete"}
            assert {entry["id"] for entry in view["tasks"]} == expected
            assert {entry["id"] for entry in view["task_contexts"]} == expected
            if slug == "factory":
                assert sum(entry["map_relevant"] is True for entry in view["task_contexts"]) == 5
        assert store.list_tasks(profile) == originals
        with store._connect() as connection:
            assert [tuple(row) for row in connection.execute("SELECT * FROM tasks ORDER BY id")] == baseline
    finally:
        assistant.close()
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == digest
