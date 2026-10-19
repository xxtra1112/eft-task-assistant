import hashlib
import json
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

import catalog
import tarkov_dev_catalog
import tarkov_dev_maps
import web_server
from route_storage import DrawingError, MAX_SCOPE_POINTS, normalize_operation
from storage import TaskStore


MAP = "55f2d3fd4bdc2d5f408b4567"
OTHER_MAP = "56f40101d2720b2a4d8b45d6"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local-app-data"))
    monkeypatch.setattr(web_server, "log_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(web_server.AssistantState, "request_catalog_refresh", lambda *_args: None)

    def no_network(*_args, **_kwargs):
        raise AssertionError("Route tests must not fetch external data")

    for module in (catalog, tarkov_dev_catalog, tarkov_dev_maps):
        monkeypatch.setattr(module, "urlopen", no_network)
    monkeypatch.setattr(web_server.SourceAdapters, "map_data", offline_map)


def offline_map(_self, source, map_id, _mode):
    if map_id not in {MAP, OTHER_MAP}:
        raise catalog.CatalogError("未知测试地图")
    return {"map_id": map_id, "floors": [] if source == "reemr" else [{"key": "ground"}, {"key": "upper"}]}


@pytest.fixture
def state(tmp_path):
    assistant = web_server.AssistantState(TaskStore(tmp_path / "tasks.sqlite3"))
    yield assistant
    assistant.close()


def stroke(identifier="line-1", count=2, **overrides):
    return {"id": identifier, "points": [[0, 0], *([[0.5, 1]] * (count - 1))], **overrides}


def command(state, operation="append", **overrides):
    payload = {"profile_id": state.selected_profile_id, "source": "tarkov.dev", "map_id": MAP,
               "floor_key": "ground", "operation_id": str(uuid.uuid4()), "operation": operation}
    if operation == "append":
        payload["stroke"] = stroke()
    if operation in ("replace", "import_legacy"):
        payload["strokes"] = [stroke()]
    return {**payload, **overrides}


def read(state, floor="ground", source="tarkov.dev", map_id=MAP, **kwargs):
    return state.map_drawings(source, map_id, floor, **kwargs)


def test_roundtrip_styles_defaults_poll_and_restart(state):
    assert read(state)["revision"] == 0
    assert read(state)["strokes"] == []
    result = state.set_map_drawings(command(state, stroke=stroke(color="#12ABef", width=6), base_revision=0))
    assert result["scope"] == {"source": "tarkov.dev", "map_id": MAP, "floor_key": "ground"}
    assert result["profile_id"] == state.selected_profile_id
    assert result["strokes"][0]["color"] == "#12abef"
    assert result["strokes"][0]["width"] == 6
    assert result["revision"] == 1
    assert read(state, since=0)["strokes"] == result["strokes"]
    unchanged = read(state, since=1)
    assert unchanged["unchanged"] is True
    assert "strokes" not in unchanged
    assert unchanged["legacy_count"] == unchanged["legacy_revision"] == 0
    state.set_map_drawings(command(state, stroke=stroke("default"), base_revision=1))
    reopened = TaskStore(state.store.path)
    restored = reopened.routes.read(state.selected_profile_id, "tarkov.dev", MAP, "ground")
    assert restored["revision"] == 2
    assert restored["strokes"][1]["color"] == "#e5484d"
    assert restored["strokes"][1]["width"] == 4
    assert state.snapshot()["map_drawings_revision"] == 2


def test_operation_retry_uses_current_snapshot_without_reapplying(state):
    append = command(state, base_revision=0)
    first = state.set_map_drawings(append)
    retried = state.set_map_drawings(append)
    assert retried["replayed"] is True
    assert retried["strokes"] == first["strokes"]
    undo = command(state, "undo", base_revision=1)
    state.set_map_drawings(undo)
    state.set_map_drawings(command(state, stroke=stroke("later")))
    retried = state.set_map_drawings(undo)
    assert retried["revision"] == 3
    assert retried["strokes"][0]["id"] == "later"
    assert state.store.routes.profile_revision(state.selected_profile_id) == 3
    with pytest.raises(DrawingError) as error:
        state.set_map_drawings({**append, "stroke": stroke("different")})
    assert error.value.status == 409
    assert error.value.details["error_code"] == "operation_id_conflict"


def test_revision_conflict_retry_with_same_uuid_and_changed_base(state):
    stale = command(state, stroke=stroke("retry"), base_revision=0)
    state.set_map_drawings(command(state, base_revision=0))
    with pytest.raises(DrawingError) as error:
        state.set_map_drawings(stale)
    assert error.value.status == 409
    assert error.value.details["revision"] == 1
    assert len(error.value.details["strokes"]) == 1
    assert error.value.details["error_code"] == "revision_conflict"
    assert state.set_map_drawings({**stale, "base_revision": 1})["revision"] == 2
    assert state.set_map_drawings(stale)["replayed"] is True


def test_lost_ack_lookup_is_scoped_persistent_and_survives_later_changes(state):
    appended = command(state)
    state.set_map_drawings(appended)
    cleared = command(state, "clear", base_revision=1)
    state.set_map_drawings(cleared)
    state.set_map_drawings(command(state, stroke=stroke("later")))
    confirmed = read(state, since=3, operation_id=cleared["operation_id"])
    assert confirmed["operation_applied"] is True
    assert confirmed["unchanged"] is True
    assert "strokes" not in confirmed
    assert read(state, operation_id=appended["operation_id"])["operation_applied"] is True
    assert read(state, "upper", operation_id=cleared["operation_id"])["operation_applied"] is False
    assert read(state, map_id=OTHER_MAP, operation_id=cleared["operation_id"])["operation_applied"] is False
    assert read(state, source="eftarkov", operation_id=cleared["operation_id"])["operation_applied"] is False
    assert read(state, operation_id=str(uuid.uuid4()))["operation_applied"] is False
    reopened = TaskStore(state.store.path)
    assert reopened.routes.read(state.selected_profile_id, "tarkov.dev", MAP, "ground",
                                operation_id=cleared["operation_id"])["operation_applied"] is True
    state.create_profile("Other", "regular")
    assert read(state, operation_id=cleared["operation_id"])["operation_applied"] is False


def test_failed_and_noop_operations_acknowledged_correctly(state):
    applied = command(state, "undo", base_revision=0)
    state.set_map_drawings(applied)
    assert read(state, since=0, operation_id=applied["operation_id"])["operation_applied"] is True
    conflicted = command(state, base_revision=1)
    with pytest.raises(DrawingError):
        state.set_map_drawings(conflicted)
    assert read(state, operation_id=conflicted["operation_id"])["operation_applied"] is False


def test_undo_clear_replace_noops_and_revisions(state):
    assert state.set_map_drawings(command(state, "undo"))["revision"] == 0
    assert state.set_map_drawings(command(state, "clear"))["revision"] == 0
    state.set_map_drawings(command(state, "replace", strokes=[stroke("one"), stroke("two")]))
    assert [line["id"] for line in state.set_map_drawings(command(state, "undo"))["strokes"]] == ["one"]
    cleared = state.set_map_drawings(command(state, "clear"))
    assert cleared["revision"] == 3
    assert cleared["strokes"] == []
    assert state.set_map_drawings(command(state, "replace", strokes=[]))["revision"] == 3


def test_profile_provider_map_and_floor_isolation(state):
    state.set_map_drawings(command(state))
    state.set_map_drawings(command(state, floor_key="upper", stroke=stroke("up")))
    state.set_map_drawings(command(state, map_id=OTHER_MAP, stroke=stroke("other-map")))
    state.select_data_source("eftarkov")
    assert read(state, source="eftarkov")["strokes"] == []
    state.set_map_drawings(command(state, source="eftarkov", stroke=stroke("eft")))
    assert read(state)["strokes"][0]["id"] == "line-1"
    assert read(state, "upper")["strokes"][0]["id"] == "up"
    assert read(state, map_id=OTHER_MAP)["strokes"][0]["id"] == "other-map"
    original_profile = state.selected_profile_id
    other = state.create_profile("Other", "regular")
    assert read(state)["strokes"] == []
    assert state.snapshot()["map_drawings_revision"] == 0
    state.set_map_drawings(command(state, stroke=stroke("other-profile")))
    assert other.id != original_profile
    state.select_profile(original_profile)
    assert read(state, source="eftarkov")["strokes"][0]["id"] == "eft"
    assert state.snapshot()["map_drawings_revision"] == 4


def test_negative_upstream_floor_key_roundtrips(state, monkeypatch):
    monkeypatch.setattr(state.sources, "map_data", lambda source, map_id, mode: {"map_id": map_id, "floors": [{"key": "-1"}]})
    state.select_data_source("eftarkov")
    result = state.set_map_drawings(command(state, source="eftarkov", floor_key="-1"))
    assert result["scope"]["floor_key"] == "-1"
    assert read(state, "-1", "eftarkov")["strokes"][0]["id"] == "line-1"


def test_source_change_during_map_validation_cannot_commit_late_stroke(state, monkeypatch):
    monkeypatch.setattr(state, "_validate_drawing_map", lambda scope, mode: state.select_data_source("eftarkov"))
    with pytest.raises(DrawingError) as error:
        state.set_map_drawings(command(state))
    assert error.value.status == 409
    assert state.store.routes.read(state.selected_profile_id, "tarkov.dev", MAP, "ground")["strokes"] == []


def test_late_profile_and_source_rejected_before_catalog_load(state, monkeypatch):
    late = command(state)
    other = state.create_profile("Other", "regular")

    def unexpected(*_args):
        pytest.fail("Stale writes must fail before map loading")

    monkeypatch.setattr(state.sources, "map_data", unexpected)
    with pytest.raises(DrawingError) as error:
        state.set_map_drawings(late)
    assert error.value.status == 409
    assert error.value.details["profile_id"] == other.id
    with pytest.raises(DrawingError) as error:
        read(state, profile_id=late["profile_id"])
    assert error.value.status == 409
    state.select_profile(late["profile_id"])
    state.select_data_source("eftarkov")
    with pytest.raises(DrawingError) as error:
        state.set_map_drawings(late)
    assert error.value.details["error_code"] == "source_changed"


@pytest.mark.parametrize("change", ["profile", "source", "stored_profile", "stored_source"])
def test_selection_rechecked_after_map_load_and_inside_transaction(state, monkeypatch, change):
    original = state.selected_profile_id
    other = state.store.create_profile("Other", "regular")

    def switch(source, map_id, mode):
        if change == "profile":
            state.select_profile(other.id)
        elif change == "source":
            state.select_data_source("eftarkov")
        elif change == "stored_profile":
            state.store.set_app_setting("selected_profile_id", str(other.id))
        else:
            state.store.set_app_setting(f"data_source:{original}", "eftarkov")
        return offline_map(None, source, map_id, mode)

    monkeypatch.setattr(state.sources, "map_data", switch)
    with pytest.raises(DrawingError) as error:
        state.set_map_drawings(command(state))
    assert error.value.status == 409
    assert state.store.routes.read(original, "tarkov.dev", MAP, "ground")["strokes"] == []


def test_legacy_import_assign_preserves_existing_and_does_not_resurrect(state):
    state.set_map_drawings(command(state, stroke=stroke("server")))
    imported = command(state, "import_legacy", floor_key="", strokes=[stroke("old")], base_revision=0)
    first = state.set_map_drawings(imported)
    assert first["scope"]["floor_key"] == ""
    assert first["revision"] == first["legacy_revision"] == first["legacy_count"] == 1
    banner = read(state, since=1)
    assert banner["unchanged"] is True
    assert banner["legacy_count"] == banner["legacy_revision"] == 1
    assert state.set_map_drawings(imported)["replayed"] is True
    different_id = {**imported, "operation_id": str(uuid.uuid4()), "strokes": [stroke("overwrite")], "base_revision": 1}
    assert state.set_map_drawings(different_id)["strokes"][0]["id"] == "old"
    state.set_map_drawings(command(state, "import_legacy", map_id=OTHER_MAP, floor_key="", strokes=[stroke("elsewhere")]))
    assigned_op = command(state, "assign_legacy", base_revision=1)
    assigned = state.set_map_drawings(assigned_op)
    assert assigned["revision"] == 2
    assert [line["id"] for line in assigned["strokes"]] == ["server", "old"]
    assert assigned["legacy_count"] == 0
    assert assigned["legacy_revision"] == 2
    assert read(state, "upper")["strokes"] == []
    assert read(state, "", map_id=OTHER_MAP)["legacy_count"] == 1
    assert state.set_map_drawings(assigned_op)["replayed"] is True
    assert state.set_map_drawings({**imported, "operation_id": str(uuid.uuid4()), "base_revision": 2})["strokes"] == []
    state.set_map_drawings(command(state, "clear"))
    assert state.set_map_drawings(command(state, "assign_legacy"))["strokes"] == []
    assert read(state, "")["revision"] == 2


def test_legacy_undo_and_provider_isolation(state):
    state.set_map_drawings(command(state, "import_legacy", floor_key="", strokes=[stroke("one"), stroke("two")]))
    state.set_map_drawings(command(state, "undo", floor_key=""))
    assert read(state, "")["legacy_count"] == 1
    state.select_data_source("eftarkov")
    assert state.set_map_drawings(command(state, "assign_legacy", source="eftarkov"))["strokes"] == []
    assert read(state, "")["legacy_count"] == 1


@pytest.mark.parametrize("reason", ["count", "points", "id"])
def test_assign_legacy_conflict_is_atomic(state, reason):
    current = [stroke(f"server-{number}") for number in range(40)] if reason == "count" else (
        [stroke(f"server-{number}", count=1000) for number in range(12)] if reason == "points" else [stroke("old")])
    state.set_map_drawings(command(state, "replace", strokes=current))
    state.set_map_drawings(command(state, "import_legacy", floor_key="", strokes=[stroke("old")]))
    revision = state.store.routes.profile_revision(state.selected_profile_id)
    with pytest.raises(DrawingError):
        state.set_map_drawings(command(state, "assign_legacy"))
    assert len(read(state)["strokes"]) == len(current)
    assert read(state, "")["legacy_count"] == 1
    assert state.store.routes.profile_revision(state.selected_profile_id) == revision


def test_capacity_rejects_without_truncating_saved_lines(state):
    original = [stroke(f"line-{number}") for number in range(40)]
    state.set_map_drawings(command(state, "replace", strokes=original))
    before = read(state)
    with pytest.raises(DrawingError) as error:
        state.set_map_drawings(command(state, stroke=stroke("forty-first")))
    assert error.value.details["error_code"] == "drawing_capacity"
    assert read(state) == before
    points = [stroke(f"long-{number}", count=1000) for number in range(12)]
    state.set_map_drawings(command(state, "replace", strokes=points))
    assert sum(len(line["points"]) for line in read(state)["strokes"]) == MAX_SCOPE_POINTS
    with pytest.raises(DrawingError):
        state.set_map_drawings(command(state, stroke=stroke("over-points")))
    assert len(read(state)["strokes"]) == 12
    with pytest.raises(DrawingError):
        state.set_map_drawings(command(state, "replace", strokes=[stroke(count=1001)]))
    assert len(read(state)["strokes"]) == 12


@pytest.mark.parametrize("override", [
    {"points": [[float("nan"), 0], [1, 1]]}, {"points": [[float("inf"), 0], [1, 1]]},
    {"points": [[-float("inf"), 0], [1, 1]]}, {"points": [[-0.01, 0], [1, 1]]},
    {"points": [[1.01, 0], [1, 1]]}, {"points": [[True, 0], [1, 1]]},
    {"points": [["0.5", 0], [1, 1]]}, {"points": [[None, 0], [1, 1]]},
    {"points": [[0, 0, 0], [1, 1]]}, {"points": [[0, 0]]}, {"points": []},
    {"points": "attack"}, {"color": "red"}, {"color": "#fff;url(javascript:alert(1))"},
    {"color": "#123"}, {"color": "#12345678"}, {"color": None},
    {"width": True}, {"width": 4.0}, {"width": 3}, {"width": "4"},
    {"id": "../line"}, {"id": "<script>"}, {"id": ""}, {"extra": "attack"},
])
def test_bad_stroke_inputs_are_rejected(state, override):
    with pytest.raises(DrawingError):
        state.set_map_drawings(command(state, stroke=stroke(**override)))
    assert read(state)["strokes"] == []


@pytest.mark.parametrize("override", [
    {"source": "unknown"}, {"source": []}, {"map_id": "../db"}, {"map_id": []},
    {"floor_key": "../upper"}, {"floor_key": None}, {"profile_id": True}, {"profile_id": 0},
    {"profile_id": "1"}, {"operation_id": "invalid"}, {"operation_id": None},
    {"operation": []}, {"operation": "attack"}, {"base_revision": -1},
    {"base_revision": True}, {"base_revision": 1.5}, {"base_revision": None},
    {"base_revision": 2**63}, {"extra": "attack"}, {"strokes": []},
])
def test_bad_operation_parameters_are_rejected(state, override):
    with pytest.raises(DrawingError):
        normalize_operation(command(state, **override))


@pytest.mark.parametrize("field", ["profile_id", "source", "map_id", "floor_key", "operation_id", "operation", "stroke"])
def test_required_write_fields(state, field):
    payload = command(state)
    del payload[field]
    with pytest.raises(DrawingError):
        state.set_map_drawings(payload)


@pytest.mark.parametrize("operation", ["append", "clear", "replace", "assign_legacy"])
def test_empty_floor_restricted_to_import_and_legacy_undo(state, operation):
    with pytest.raises(DrawingError):
        state.set_map_drawings(command(state, operation, floor_key=""))


def test_unknown_map_floor_and_reference_floor_rejected(state):
    for changes in ({"map_id": "unknown"}, {"floor_key": "unknown"}):
        with pytest.raises(DrawingError):
            state.set_map_drawings(command(state, **changes))
    with pytest.raises(DrawingError):
        state.set_map_drawings(command(state, "import_legacy", floor_key="ground"))
    state.select_data_source("reemr")
    with pytest.raises(DrawingError):
        state.set_map_drawings(command(state, source="reemr"))


def test_repeated_poll_uses_validated_directory_cache(state, monkeypatch):
    calls = []

    def counted(source, map_id, mode):
        calls.append((source, map_id, mode))
        return offline_map(None, source, map_id, mode)

    monkeypatch.setattr(state.sources, "map_data", counted)
    for _index in range(10):
        assert read(state, since=0)["unchanged"] is True
    assert len(calls) == 1


@pytest.mark.parametrize("mode", ["distinct", "duplicate", "same_base"])
def test_concurrent_transactions_across_independent_stores(state, mode):
    stores = [TaskStore(state.store.path) for _index in range(8)]
    shared_id = str(uuid.uuid4())
    payloads = [command(state, operation_id=shared_id if mode == "duplicate" else str(uuid.uuid4()),
                        stroke=stroke("shared" if mode == "duplicate" else f"line-{index}"),
                        **({"base_revision": 0} if mode == "same_base" else {})) for index in range(8)]
    barrier = threading.Barrier(8)

    def execute(index):
        barrier.wait(timeout=5)
        try:
            return stores[index].routes.apply(payloads[index])
        except DrawingError as error:
            return error

    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes = list(executor.map(execute, range(8)))
    result = read(state)
    expected = 8 if mode == "distinct" else 1
    assert result["revision"] == len(result["strokes"]) == expected
    assert state.store.routes.profile_revision(state.selected_profile_id) == expected
    if mode == "same_base":
        assert sum(isinstance(outcome, DrawingError) and outcome.status == 409 for outcome in outcomes) == 7
    else:
        assert all(isinstance(outcome, dict) for outcome in outcomes)
    if mode == "duplicate":
        assert sum(outcome["replayed"] for outcome in outcomes) == 7


@pytest.fixture
def servers(tmp_path):
    manager = web_server.PlayerStateManager(tmp_path / "app-data")
    assistant = manager.state_for(manager.local_player)
    instances = []
    for mobile in (False, True):
        server = ThreadingHTTPServer(("127.0.0.1", 0), web_server._make_handler(manager, {}, mobile_only=mobile))
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        instances.append((server, thread))
    yield manager, assistant, instances[0][0], instances[1][0]
    for server, thread in instances:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    manager.close()


def request(server, method, path, payload=None, cookie=None, **headers):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    if cookie:
        headers["Cookie"] = cookie
    if payload is not None:
        headers["Content-Type"] = "application/json"
    try:
        connection.request(method, path, body=None if payload is None else json.dumps(payload), headers=headers)
        response = connection.getresponse()
        body = response.read()
        parsed = json.loads(body) if "application/json" in response.getheader("Content-Type", "") else body
        return response.status, parsed, response.getheader("Set-Cookie")
    finally:
        connection.close()


def pair(manager, server):
    token, _expires = manager.auth.create_mobile_pairing_token(manager.local_player.id)
    status, _result, cookie = request(server, "POST", "/api/auth/mobile-pair", {"token": token})
    assert status == 200
    return cookie.split(";", 1)[0]


def test_http_mobile_read_only_sync_and_revisions(servers):
    manager, state, desktop, mobile = servers
    path = f"/api/map/drawings?source=tarkov.dev&map_id={MAP}&floor=ground&profile_id={state.selected_profile_id}"
    assert request(mobile, "GET", path)[0] == 401
    cookie = pair(manager, mobile)
    styled = stroke(color="#99Ff01", width=2)
    assert request(desktop, "POST", "/api/map/drawings", command(state, stroke=styled, base_revision=0))[0] == 200
    mobile_stroke = request(mobile, "GET", path, cookie=cookie)[1]["strokes"][0]
    assert mobile_stroke["color"] == "#99ff01"
    assert mobile_stroke["width"] == 2
    status, result, _cookie = request(mobile, "GET", path + "&since=1", cookie=cookie)
    assert status == 200 and result["unchanged"] is True and "strokes" not in result
    for server in (desktop, mobile):
        assert request(server, "POST", "/api/map/drawings", command(state, "clear"), cookie=cookie)[0] == 403
    assert request(desktop, "POST", "/api/map/drawings", command(state, "clear", base_revision=0))[0] == 409
    assert request(desktop, "POST", "/api/map/drawings", command(state, "clear"), Origin="https://evil.invalid")[0] == 403
    assert request(mobile, "GET", "/api/mobile/state", cookie=cookie)[1]["map_drawings_revision"] == 1
    assert request(desktop, "GET", "/api/state")[1]["map_drawings_revision"] == 1
    state.set_map_drawings(command(state, "import_legacy", floor_key=""))
    assert request(mobile, "GET", path + "&since=1", cookie=cookie)[1]["legacy_count"] == 1


def test_http_operation_ack_lookup_and_scope_guards(servers):
    manager, state, desktop, mobile = servers
    pending = command(state)
    assert request(desktop, "POST", "/api/map/drawings", pending)[0] == 200
    state.set_map_drawings(command(state, "clear"))
    cookie = pair(manager, mobile)
    path = f"/api/map/drawings?source=tarkov.dev&map_id={MAP}&floor=ground&profile_id={state.selected_profile_id}"
    path += f"&operation_id={pending['operation_id']}&since=2"
    status, result, _cookie = request(mobile, "GET", path, cookie=cookie)
    assert status == 200
    assert result["operation_applied"] is True and result["unchanged"] is True
    assert request(mobile, "GET", path.replace("floor=ground", "floor=upper"), cookie=cookie)[1]["operation_applied"] is False
    state.create_profile("Other", "regular")
    assert request(mobile, "GET", path, cookie=cookie)[0] == 409


@pytest.mark.parametrize("query", [
    "since=", "since=-1", "since=NaN", "since=Infinity", "since=1.5", "since=9223372036854775808",
    "since=0&since=1", "profile_id=0", "profile_id=true", "profile_id=1&profile_id=2", "attack=1",
    "operation_id=", "operation_id=bad", "operation_id[]=attack",
])
def test_http_bad_query(servers, query):
    _manager, _state, desktop, _mobile = servers
    path = f"/api/map/drawings?source=tarkov.dev&map_id={MAP}&floor=ground&{query}"
    assert request(desktop, "GET", path)[0] == 400


def test_http_stale_profile_and_nonfinite_json(servers):
    _manager, state, desktop, _mobile = servers
    payload = command(state)
    state.create_profile("Other", "regular")
    assert request(desktop, "POST", "/api/map/drawings", payload)[0] == 409
    path = f"/api/map/drawings?source=tarkov.dev&map_id={MAP}&floor=ground&profile_id={payload['profile_id']}"
    assert request(desktop, "GET", path)[0] == 409
    payload = command(state, stroke=stroke(points=[[float("nan"), 0], [1, 1]]))
    assert request(desktop, "POST", "/api/map/drawings", payload)[0] == 400


def test_shared_route_script_served_on_both_listeners(servers, tmp_path, monkeypatch):
    _manager, _state, desktop, mobile = servers
    web = tmp_path / "web"
    web.mkdir()
    web.joinpath("route_tools.js").write_text("window.routeTools = {};", encoding="utf-8")
    monkeypatch.setattr(web_server, "WEB_ROOT", web)
    for server in (desktop, mobile):
        status, body, _cookie = request(server, "GET", "/assets/route_tools.js")
        assert status == 200
        assert body == b"window.routeTools = {};"


def test_private_backup_copy_additive_migration_and_user_rows(tmp_path):
    backup = Path("E:/Document/codex/2026-10-18/task/eft-software-handoff-20261019T094431Z/private-backups/tasks.sqlite3")
    if not backup.is_file():
        pytest.skip("Local handoff backup is unavailable")
    digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    copied = tmp_path / "backup-copy.sqlite3"
    with sqlite3.connect(backup.as_uri() + "?mode=ro", uri=True) as source:
        with sqlite3.connect(copied) as destination:
            source.backup(destination)
    with sqlite3.connect(copied) as connection:
        baseline = {table: connection.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
                    for table in ("tasks", "profiles", "catalog_snapshots")}
    store = TaskStore(copied)
    profile_id = store.default_profile_id()
    store.set_app_setting("selected_profile_id", str(profile_id))
    store.set_app_setting(f"data_source:{profile_id}", "tarkov.dev")
    result = store.routes.apply({"profile_id": profile_id, "source": "tarkov.dev", "map_id": MAP,
                                "floor_key": "ground", "operation_id": str(uuid.uuid4()),
                                "operation": "append", "stroke": stroke()})
    assert result["revision"] == 1
    with sqlite3.connect(copied) as connection:
        for table, rows in baseline.items():
            assert connection.execute(f"SELECT * FROM {table} ORDER BY id").fetchall() == rows
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == digest
