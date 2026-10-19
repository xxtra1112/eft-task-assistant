import json
import shutil
import threading
import uuid
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from urllib.parse import quote

import pytest

import web_server
from save_runtime import MANIFEST_NAME


MAP = "55f2d3fd4bdc2d5f408b4567"


def scope_header(root, dataset="unmanaged"):
    return quote("dataset-v1:" + json.dumps([str(root), dataset], ensure_ascii=False, separators=(",", ":")),
                 safe="~()*!.'-")


def call(server, path, payload, scope=None, **headers):
    if scope is not None:
        headers["X-EFT-Save-Scope"] = scope
    headers["Content-Type"] = "application/json"
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        connection.request("POST", path, body=json.dumps(payload), headers=headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def drawing(profile_id, operation="append"):
    payload = {"profile_id": profile_id, "source": "tarkov.dev", "map_id": MAP,
               "floor_key": "ground", "operation_id": str(uuid.uuid4()), "operation": operation}
    if operation == "append":
        payload["stroke"] = {"id": "saved-line", "points": [[0, 0], [1, 1]]}
    return payload


def preferences(profile_id, revision=0):
    return {"profile_id": profile_id, "base_revision": revision, "operation_id": str(uuid.uuid4()),
            "data": {"version": 1, "hiddenTaskIds": ["new-task"]}}


def database_snapshot(manager, assistant):
    with manager.auth._connect() as connection:
        auth = tuple(connection.iterdump())
    with assistant.store._connect() as connection:
        tasks = tuple(connection.iterdump())
    return auth, tasks, assistant.profile_name_required, assistant.selected_profile_id


@pytest.fixture
def services(tmp_path, monkeypatch):
    monkeypatch.setattr(web_server, "log_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(web_server.AssistantState, "request_catalog_refresh", lambda *_args: None)
    monkeypatch.setattr(web_server.SourceAdapters, "map_data", lambda *_args: {
        "map_id": MAP, "floors": [{"key": "ground"}]})

    def unexpected(*_args, **_kwargs):
        pytest.fail("Scope validation must not inventory datasets or access the network")

    monkeypatch.setattr(web_server, "export_runtime_status", unexpected)
    monkeypatch.setattr(web_server.SourceAdapters, "task_catalog", unexpected)
    instances = []

    def start(root, runtime_root=None, clone_from=None, mobile_only=False):
        if clone_from is not None:
            root.mkdir(parents=True)
            shutil.copy2(clone_from.auth.path, root / "players.sqlite3")
        manager = web_server.PlayerStateManager(root, runtime_root=runtime_root)
        assistant = manager.state_for(manager.local_player)
        server = ThreadingHTTPServer(("127.0.0.1", 0), web_server._make_handler(manager, mobile_only=mobile_only))
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        instances.append((manager, server, thread))
        thread.start()
        return manager, assistant, server

    yield start
    for manager, server, thread in reversed(instances):
        server.shutdown()
        server.server_close()
        thread.join(3)
        manager.close()


@pytest.mark.parametrize("managed", [True, False])
def test_old_dataset_header_rejected_with_identical_player_and_profile_ids(services, tmp_path, managed, monkeypatch):
    root = tmp_path / "存档 + %Q 😀"
    first_id, second_id = str(uuid.uuid4()), str(uuid.uuid4())
    first_root = root / "datasets" / first_id if managed else root / "A"
    second_root = root / "datasets" / second_id if managed else root / "B"
    first, first_assistant, _first_server = services(first_root, root if managed else None)
    second, assistant, server = services(second_root, root if managed else None, clone_from=first)
    assert first.local_player.id == second.local_player.id
    assert first_assistant.selected_profile_id == assistant.selected_profile_id
    profile_id = assistant.selected_profile_id
    assistant.store.add_task("Prapor", "Synthetic saved task", profile_id=profile_id)
    assistant.preferences.save(profile_id, {"version": 1, "hiddenTaskIds": ["saved-task"]}, 0, str(uuid.uuid4()))
    assistant.set_map_drawings(drawing(profile_id))
    before = database_snapshot(second, assistant)
    old_header = scope_header(root, first_id) if managed else scope_header(first_root)

    with monkeypatch.context() as guard:
        guard.setattr(second, "state_for", lambda *_args: pytest.fail("Stale POST must fail before opening player state"))
        for path, payload in (
            ("/api/profiles/name", {"name": "Must not rename B"}),
            ("/api/preferences", preferences(profile_id, 1)),
            ("/api/map/drawings", drawing(profile_id, "clear")),
        ):
            status, result = call(server, path, payload, old_header)
            assert status == 409, (path, result)
            assert "刷新" in result["error"]
            assert database_snapshot(second, assistant) == before


@pytest.mark.parametrize("managed", [True, False])
@pytest.mark.parametrize("with_header", [True, False])
def test_correct_unicode_scope_and_legacy_missing_header_allow_writes(services, tmp_path, managed, with_header):
    root = tmp_path / "存档 + %Q 😀"
    dataset_id = str(uuid.uuid4())
    data_root = root / "datasets" / dataset_id if managed else root
    manager, assistant, server = services(data_root, root if managed else None)
    header = (scope_header(root, dataset_id) if managed else scope_header(root)) if with_header else None
    profile_id = assistant.selected_profile_id
    status, result = call(server, "/api/profiles/name", {"name": "合成测试档案"}, header)
    assert status == 200
    assert result["profile"]["name"] == "合成测试档案"
    assert call(server, "/api/preferences", preferences(profile_id), header)[0] == 200
    assert assistant.preferences.get(profile_id)["data"]["hiddenTaskIds"] == ["new-task"]
    status, result = call(server, "/api/map/drawings", drawing(profile_id), header)
    assert status == 200
    assert result["revision"] == 1
    assert assistant.store.routes.read(profile_id, "tarkov.dev", MAP, "ground")["strokes"][0]["id"] == "saved-line"


def test_scope_stays_bound_when_manifest_selects_next_dataset(services, tmp_path):
    root = tmp_path / "runtime"
    bound_id, selected_id = str(uuid.uuid4()), str(uuid.uuid4())
    _manager, assistant, server = services(root / "datasets" / bound_id, root)
    (root / MANIFEST_NAME).write_text(json.dumps({"version": 1, "generation": 2,
        "active_dataset": selected_id, "previous_dataset": bound_id}), encoding="utf-8")
    payload = preferences(assistant.selected_profile_id)
    assert call(server, "/api/preferences", payload, scope_header(root, selected_id))[0] == 409
    assert call(server, "/api/preferences", payload, scope_header(root, bound_id))[0] == 200


@pytest.mark.parametrize("invalid", ["empty", "percent", "nonhex", "utf8", "overlong", "double_encoded",
                                       "whitespace", "wrong_root", "json_spacing", "nonascii"])
def test_invalid_scope_fails_closed_without_mutation(services, tmp_path, invalid):
    root = tmp_path / "存档 %Q"
    manager, assistant, server = services(root)
    valid = scope_header(root)
    headers = {
        "empty": "",
        "percent": valid + "%",
        "nonhex": valid.replace("%25Q", "%Q"),
        "utf8": valid + "%FF",
        "overlong": "x" * 16_385,
        "double_encoded": quote(valid, safe=""),
        "whitespace": valid + "%20",
        "wrong_root": scope_header(root.parent),
        "json_spacing": quote("dataset-v1:" + json.dumps([str(root), "unmanaged"], ensure_ascii=False)),
        "nonascii": "é",
    }
    before = database_snapshot(manager, assistant)
    status, result = call(server, "/api/profiles/name", {"name": "Must not write"}, headers[invalid])
    assert status == 409
    assert "刷新" in result["error"]
    assert database_snapshot(manager, assistant) == before


def test_duplicate_scope_headers_fail_closed(services, tmp_path):
    root = tmp_path / "app"
    manager, assistant, server = services(root)
    before = database_snapshot(manager, assistant)
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    body = json.dumps({"name": "Must not write"}).encode("utf-8")
    try:
        connection.putrequest("POST", "/api/profiles/name")
        for _index in range(2):
            connection.putheader("X-EFT-Save-Scope", scope_header(root))
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", str(len(body)))
        connection.endheaders(body)
        response = connection.getresponse()
        assert response.status == 409
        response.read()
    finally:
        connection.close()
    assert database_snapshot(manager, assistant) == before


def test_scope_guard_precedes_capture_body_and_player_state(services, tmp_path, monkeypatch):
    manager, assistant, server = services(tmp_path / "app")
    before = database_snapshot(manager, assistant)
    monkeypatch.setattr(manager, "state_for", lambda *_args: pytest.fail("Stale capture must not open player state"))
    assert call(server, "/api/capture/upload", {}, scope_header(tmp_path / "old"))[0] == 409
    assert database_snapshot(manager, assistant) == before


@pytest.mark.parametrize("mobile_only", [True, False])
def test_correct_scope_does_not_bypass_mobile_or_origin_boundaries(services, tmp_path, mobile_only):
    root = tmp_path / "app"
    manager, assistant, server = services(root, mobile_only=mobile_only)
    token, _expires = manager.auth.create_mobile_pairing_token(manager.local_player.id)
    status, pairing = call(server, "/api/auth/mobile-pair", {"token": token})
    assert status == 200
    assert pairing["player"]["id"] == manager.local_player.id
    token, _expires = manager.auth.create_mobile_pairing_token(manager.local_player.id)
    paired = manager.auth.consume_mobile_pairing_token(token)
    cookie = "eft_player_session=" + paired[1]
    before = database_snapshot(manager, assistant)
    for path, payload in (("/api/profiles/name", {"name": "Must not write"}),
                          ("/api/preferences", preferences(assistant.selected_profile_id)),
                          ("/api/map/drawings", drawing(assistant.selected_profile_id))):
        assert call(server, path, payload, scope_header(root), Cookie=cookie)[0] == 403
    assert call(server, "/api/profiles/name", {"name": "Must not write"}, scope_header(root),
                Origin="https://evil.invalid")[0] == 403
    assert database_snapshot(manager, assistant) == before
