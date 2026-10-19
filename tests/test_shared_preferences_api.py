import io
import json
import threading
import uuid
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

import pytest
from PIL import Image

from web_server import AssistantState, PlayerStateManager, _make_handler


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(AssistantState, "request_catalog_refresh", lambda *_args: None)
    manager = PlayerStateManager(tmp_path / "app")
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(manager))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield manager, server
    server.shutdown()
    server.server_close()
    thread.join(3)
    manager.close()


def call(server, path, data=None, method=None):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        connection.request(method or ("POST" if data is not None else "GET"), path,
                           body=json.dumps(data) if data is not None else None,
                           headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        body = response.read()
        content_type = response.getheader("Content-Type", "")
        return response.status, json.loads(body) if "json" in content_type else body, content_type
    finally:
        connection.close()


def command(profile_id, data, revision=0, **changes):
    return {"profile_id": profile_id, "data": data, "base_revision": revision,
            "operation_id": str(uuid.uuid4()), **changes}


def test_preferences_initial_migration_idempotence_conflict_resolution_and_restart(service):
    manager, server = service
    assistant = manager.state_for(manager.local_player)
    profile_id = assistant.selected_profile_id
    path = f"/api/preferences?profile_id={profile_id}"
    assert call(server, path)[1]["revision"] == 0
    original = {"version": 1, "hiddenTaskIds": ["task-1"], "keyOwnershipAnswers": {"key-1": False},
                "hideoutOwnedMaterials": {"bolts": 7}, "hideoutPlannerOpen": False}
    migration = command(profile_id, original, only_if_empty=True)
    assert call(server, "/api/preferences", migration)[:2] == call(server, "/api/preferences", migration)[:2]
    assert call(server, path)[1]["data"] == original
    local = {"version": 1, "hiddenTaskIds": ["task-2"]}
    status, conflict, _ = call(server, "/api/preferences", command(profile_id, local, only_if_empty=True))
    assert status == 409
    assert conflict["current"]["data"] == original
    exported = call(server, f"/api/preferences/conflicts?profile_id={profile_id}")[1]
    assert len(exported["conflicts"]) == 1
    assert {json.dumps(entry["data"], sort_keys=True) for entry in exported["backups"]} >= {
        json.dumps(original, sort_keys=True), json.dumps(local, sort_keys=True)}
    resolution = {"profile_id": profile_id, "conflict_id": conflict["conflict_id"], "choice": "local",
                  "base_revision": 1, "operation_id": str(uuid.uuid4())}
    assert call(server, "/api/preferences/resolve", resolution)[1]["data"] == local
    assert call(server, "/api/preferences/resolve", resolution)[1]["revision"] == 2
    reopened = PlayerStateManager(manager.auth.root)
    try:
        assert reopened.state_for(reopened.local_player).preferences.get(profile_id)["data"] == local
    finally:
        reopened.close()


@pytest.mark.parametrize("field", ["routePendingOperations", "routeCaches", "routeCacheRevisions", "password"])
def test_preferences_refuse_local_only_and_sensitive_fields(service, field):
    manager, server = service
    profile_id = manager.state_for(manager.local_player).selected_profile_id
    status, _, _ = call(server, "/api/preferences", command(profile_id, {field: []}))
    assert status == 400
    assert call(server, f"/api/preferences?profile_id={profile_id}")[1]["revision"] == 0


def test_preferences_selected_profile_guard_and_mobile_denial(service):
    manager, server = service
    assistant = manager.state_for(manager.local_player)
    assert call(server, "/api/preferences?profile_id=9999")[0] == 409
    assert call(server, "/api/preferences", command(9999, {"version": 1}))[0] == 409
    assert assistant.preferences.get(assistant.selected_profile_id)["revision"] == 0
    mobile = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(manager, mobile_only=True))
    thread = threading.Thread(target=mobile.serve_forever, daemon=True)
    thread.start()
    try:
        assert call(mobile, f"/api/preferences?profile_id={assistant.selected_profile_id}")[0] == 403
        assert call(mobile, "/api/preferences", command(assistant.selected_profile_id, {"version": 1}))[0] == 403
        assert call(mobile, "/api/save-data")[0] == 403
    finally:
        mobile.shutdown()
        mobile.server_close()
        thread.join(3)


def test_reference_image_inside_app_without_tasks_and_real_png_mime(service, monkeypatch):
    manager, server = service
    assistant = manager.state_for(manager.local_player)
    config = {"map_id": "factory", "name": "工厂", "name_en": "Factory", "reference_material": True,
              "reference_only": False, "source_url": "https://reemr.se/factory/",
              "floors": [{"key": "original", "name": "Original", "width": 24, "height": 16}], "annotations": []}
    monkeypatch.setattr(assistant.sources, "map_data", lambda *_args: config)
    stream = io.BytesIO()
    Image.new("RGB", (24, 16)).save(stream, format="PNG")
    monkeypatch.setattr(assistant.sources, "floor_image", lambda *_args: stream.getvalue())
    status, result, _ = call(server, "/api/map?source=reemr&map_id=factory")
    assert status == 200
    assert result["reference_material"] is True
    assert result["markers"] == []
    assert result["image_url"].startswith("/api/map/image?")
    status, body, content_type = call(server, result["image_url"])
    assert (status, content_type) == (200, "image/png")
    assert Image.open(io.BytesIO(body)).size == (24, 16)


def test_blocked_reference_floor_is_explicit_and_keeps_tasks_without_image_request(service, monkeypatch):
    manager, server = service
    assistant = manager.state_for(manager.local_player)
    assistant.store.add_task("Prapor", "Synthetic task retained", profile_id=assistant.selected_profile_id)
    monkeypatch.setattr(assistant.sources, "map_data", lambda *_args: {
        "map_id": "factory", "name": "工厂", "name_en": "Factory", "reference_material": True,
        "source_url": "https://reemr.se/factory/", "warnings": ["robots 返回 HTML，禁止读取"],
        "floors": [{"key": "blocked", "available": False}]})
    monkeypatch.setattr(assistant.sources, "floor_image", lambda *_args: pytest.fail("Blocked image must not be fetched"))
    status, result, _ = call(server, "/api/map?source=reemr&map_id=factory")
    assert status == 200
    assert result["reference_only"] is True
    assert "robots" in result["availability_notice"]
    assert result["image_url"] == ""
    assert result["markers"] == []
    assert result["tasks"][0]["title"] == "Synthetic task retained"
