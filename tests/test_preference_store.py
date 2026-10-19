import copy
import importlib.util
import json
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import pytest

import preference_store
from preference_store import (
    LOCAL_ONLY_FIELDS,
    MAX_JSON_BYTES,
    PERSISTED_FIELDS,
    PreferenceConflict,
    PreferenceError,
    ProfilePreferences,
    validate_preferences,
)


def operation_id():
    return str(uuid.uuid4())


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "preferences.sqlite3"

    @contextmanager
    def connect():
        connection = sqlite3.connect(path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    with connect() as connection:
        connection.execute("CREATE TABLE profiles(id INTEGER PRIMARY KEY)")
        connection.executemany("INSERT INTO profiles VALUES (?)", [(1,), (2,)])
        connection.execute("CREATE TABLE sessions(token TEXT)")
        connection.execute("INSERT INTO sessions VALUES ('FIXTURE-SECRET-NEVER-EXPORT')")
    return path, connect


@pytest.fixture
def store(database):
    return ProfilePreferences(database[1])


def preferences():
    return {
        "version": 1,
        "selectedMapId": "old-map-alias",
        "selectedMapFloors": {"tarkov.dev:old-map": "upper"},
        "mapAnnotationVisibility": {"location": True, "unknown-exit": False},
        "taskTraderFilter": "Prapor", "taskMapFilter": "old-map-alias", "mapZoom": 2.5,
        "hiddenTaskIds": ["legacy-task", "same-name-different-id"], "showHiddenTasks": True,
        "hiddenMapPointIds": ["point-alias"], "hiddenKeyIds": ["门钥匙"],
        "keyFilterInitialized": True, "keyFilterKnownIds": ["old-key-alias"],
        "newKeyIds": ["new-key"], "keyOwnershipPendingIds": ["key-pending"],
        "keyOwnershipAnswers": {"old-key-alias": True, "new-key-id": False},
        "collapsedMapTaskGroups": ["trader:map"], "collapsedTaskIds": ["old-task"],
        "hideoutPlan": {"old-station-alias": {"enabled": True, "currentLevel": 1, "targetLevel": 3}},
        "hideoutOwnedMaterials": {"old-item-alias": 17},
        "operationHistory": [{"id": "history-1", "label": "保留旧名称", "type": "ui",
                              "time": "2026-10-19", "undone": False,
                              "data": {"before": {"hiddenKeyIds": ["old-key-alias"]}}}],
        "operationHistoryOpen": True, "hideoutPlannerOpen": False, "hideoutMaterialsOpen": True,
        "panels": {"addTask": True, "catalog": False, "diagnostics": True},
        "mapDrawings": {"old-map": [[[0.1, 0.2], [0.3, 0.4]]],
                        "tarkov.dev:old-map": [{"id": "line-1", "points": [[0, 0], [1, 1]],
                                                "color": "#Ab12Ef", "width": 6}]},
        "legacyRoutesImported": {"old-map": "fingerprint-123"},
        "routeStyle": {"color": "#Aa33Ff", "width": 4},
        "mobilePairingAddress": "192.168.1.8:8766",
    }


def stale(store, local=None, revision=0, identifier=None):
    with pytest.raises(PreferenceConflict) as caught:
        store.save(1, local or {"hiddenKeyIds": ["local-key"]}, revision, identifier or operation_id())
    return caught.value


def test_all_fields_roundtrip_reopen_and_profiles(store, database):
    data = preferences()
    assert set(data) == PERSISTED_FIELDS
    assert store.get(1) == {"profile_id": 1, "revision": 0, "data": {"version": 1}, "conflicts": []}
    result = store.save(1, data, 0, operation_id())
    assert result["data"] == data
    assert result["revision"] == 1
    reopened = ProfilePreferences(database[1])
    assert reopened.get(1)["data"] == data
    assert reopened.get(2)["revision"] == 0
    reopened.save(2, {"hiddenKeyIds": ["profile-2"]}, 0, operation_id())
    assert reopened.get(1)["data"] == data
    result["data"]["hiddenKeyIds"].append("caller-mutated")
    assert reopened.get(1)["data"] == data


def test_uses_taskstore_connection_context(database):
    from types import SimpleNamespace
    from storage import TaskStore

    path, _connect = database
    owner = SimpleNamespace(path=path)
    actual = ProfilePreferences(lambda: TaskStore._connect(owner))
    assert actual.save(1, {"hiddenTaskIds": ["saved"]}, 0, operation_id())["revision"] == 1


def test_import_has_no_io(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("import must perform no IO")

    spec = importlib.util.spec_from_file_location("preference_store_import_probe", preference_store.__file__)
    module = importlib.util.module_from_spec(spec)
    with monkeypatch.context() as context:
        context.setattr(sqlite3, "connect", forbidden)
        context.setattr(Path, "mkdir", forbidden)
        spec.loader.exec_module(module)


def test_save_is_full_snapshot_and_retains_previous_backup(store, database):
    store.save(1, preferences(), 0, operation_id())
    result = store.save(1, {"selectedMapId": "replacement"}, 1, operation_id())
    assert result["data"] == {"version": 1, "selectedMapId": "replacement"}
    with database[1]() as connection:
        backup_id = connection.execute("SELECT id FROM preference_backups WHERE kind='before_save'").fetchone()[0]
    assert store.get_backup(1, backup_id)["data"] == preferences()


def test_conflict_commits_both_originals_before_raise(store, database):
    original = preferences()
    local = {"hiddenKeyIds": ["different-local"], "mapDrawings": {"old-map": [[[0, 0], [1, 1]]]}}
    untouched = copy.deepcopy(local)
    store.save(1, original, 0, operation_id())
    error = stale(store, local)
    assert error.status == error.status_code == 409
    assert error.current["revision"] == error.revision == 1
    reopened = ProfilePreferences(database[1])
    assert reopened.get(1)["data"] == original
    assert reopened.get_backup(1, error.details["server_backup_id"])["data"] == original
    assert reopened.get_backup(1, error.details["local_backup_id"])["data"] == {"version": 1, **local}
    assert reopened.get(1)["conflicts"][0]["resolution"] is None
    assert local == untouched


def test_future_revision_is_also_backed_up(store):
    error = stale(store, revision=57)
    assert error.current["revision"] == 0
    assert store.get_backup(1, error.details["local_backup_id"])["revision"] == 57
    assert store.get(1)["revision"] == 0


def test_only_if_empty_import_never_overwrites_existing(store):
    first = store.save(1, {"hiddenKeyIds": ["first-browser"]}, 0, operation_id(), only_if_empty=True)
    with pytest.raises(PreferenceConflict) as caught:
        store.save(1, {"hiddenKeyIds": ["other-port"]}, first["revision"], operation_id(), only_if_empty=True)
    assert caught.value.details["reason"] == "server_not_empty"
    assert store.get(1)["data"] == first["data"]
    assert store.get_backup(1, caught.value.details["local_backup_id"])["data"]["hiddenKeyIds"] == ["other-port"]


def test_empty_saved_snapshot_is_initialized(store):
    store.save(1, {}, 0, operation_id())
    with pytest.raises(PreferenceConflict):
        store.save(1, preferences(), 1, operation_id(), only_if_empty=True)


def test_idempotent_save_returns_original_result_even_after_later_save(store, database):
    identifier = operation_id()
    first = store.save(1, preferences(), 0, identifier)
    store.save(1, {"hiddenKeyIds": []}, 1, operation_id())
    reopened = ProfilePreferences(database[1])
    assert reopened.save(1, dict(reversed(list(preferences().items()))), 0, identifier.upper()) == first
    assert reopened.get(1)["revision"] == 2
    with pytest.raises(PreferenceError) as caught:
        reopened.save(1, {"hiddenKeyIds": ["altered"]}, 0, identifier)
    assert caught.value.status == 409
    assert caught.value.details["error_code"] == "operation_id_reused"
    assert len(reopened.get(1)["conflicts"]) == 0


def test_conflict_retry_is_idempotent_after_reopen(store, database):
    store.save(1, {}, 0, operation_id())
    identifier = operation_id()
    first = stale(store, identifier=identifier)
    reopened = ProfilePreferences(database[1])
    second = stale(reopened, identifier=identifier)
    assert first.result == second.result
    assert len(reopened.get(1)["conflicts"]) == 1
    assert len(reopened.export_conflicts(1)["backups"]) == 2


@pytest.mark.parametrize("choice", ["server", "local"])
def test_explicit_resolution_backs_up_both_and_is_idempotent(store, database, choice):
    server = {"version": 1, "hiddenKeyIds": ["server"]}
    local = {"version": 1, "hiddenKeyIds": ["local"]}
    store.save(1, server, 0, operation_id())
    error = stale(store, local)
    identifier = operation_id()
    resolved = store.resolve(1, error.conflict_id, choice, 1, identifier)
    assert resolved["revision"] == 2
    assert resolved["data"] == (local if choice == "local" else server)
    assert resolved["conflicts"][0]["resolution"] == choice
    assert resolved["conflicts"][0]["resolved_revision"] == 2
    assert store.get_backup(1, error.details["server_backup_id"])["data"] == server
    assert store.get_backup(1, error.details["local_backup_id"])["data"] == local
    reopened = ProfilePreferences(database[1])
    assert reopened.resolve(1, error.conflict_id, choice, 1, identifier) == resolved
    assert reopened.get(1)["revision"] == 2


def test_resolution_cas_preserves_new_server_and_original_local(store):
    store.save(1, {"hiddenKeyIds": ["server-1"]}, 0, operation_id())
    original = stale(store)
    store.save(1, {"hiddenKeyIds": ["server-2"]}, 1, operation_id())
    with pytest.raises(PreferenceConflict) as caught:
        store.resolve(1, original.conflict_id, "local", 1, operation_id())
    assert caught.value.current["revision"] == 2
    assert store.get_backup(1, caught.value.details["local_backup_id"])["data"]["hiddenKeyIds"] == ["local-key"]
    assert store.get(1)["data"]["hiddenKeyIds"] == ["server-2"]
    assert store.get(1)["conflicts"][0]["resolution"] is None
    result = store.resolve(1, original.conflict_id, "server", 2, operation_id())
    assert result["data"]["hiddenKeyIds"] == ["server-2"]


def test_resolved_conflict_cannot_be_applied_twice_with_new_uuid(store):
    store.save(1, {}, 0, operation_id())
    original = stale(store)
    store.resolve(1, original.conflict_id, "server", 1, operation_id())
    with pytest.raises(PreferenceConflict) as caught:
        store.resolve(1, original.conflict_id, "local", 2, operation_id())
    assert caught.value.details["reason"] == "already_resolved"
    assert store.get(1)["revision"] == 2


@pytest.mark.parametrize("choice", [None, "merge", "LOCAL", {}, []])
def test_resolution_requires_explicit_choice(store, choice):
    with pytest.raises(PreferenceError):
        store.resolve(1, operation_id(), choice, 0, operation_id())


def test_profile_scoping_conflicts_backups_and_operations(store):
    identifier = operation_id()
    store.save(1, {"hiddenKeyIds": ["one"]}, 0, identifier)
    store.save(2, {"hiddenKeyIds": ["two"]}, 0, identifier)
    error = stale(store)
    assert store.export_conflicts(2) == {"profile_id": 2, "conflicts": [], "backups": []}
    with pytest.raises(PreferenceError) as caught:
        store.get_backup(2, error.details["local_backup_id"])
    assert caught.value.status == 404
    with pytest.raises(PreferenceError) as caught:
        store.resolve(2, error.conflict_id, "local", 1, operation_id())
    assert caught.value.status == 404


def test_many_concurrent_writers_have_one_winner_and_preserve_all_losers(store, database):
    barrier = threading.Barrier(8)

    def write(index):
        peer = ProfilePreferences(database[1])
        barrier.wait(timeout=15)
        try:
            return peer.save(1, {"hiddenKeyIds": [str(index)]}, 0, operation_id())
        except PreferenceConflict as error:
            return error

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(write, range(8)))
    winners = [result for result in results if isinstance(result, dict)]
    losers = [result for result in results if isinstance(result, PreferenceConflict)]
    assert len(winners) == 1
    assert len(losers) == 7
    assert store.get(1)["revision"] == 1
    preserved = {winners[0]["data"]["hiddenKeyIds"][0]}
    for error in losers:
        preserved.add(store.get_backup(1, error.details["local_backup_id"])["data"]["hiddenKeyIds"][0])
    assert preserved == {str(index) for index in range(8)}


def test_concurrent_identical_uuid_commits_once(store):
    barrier = threading.Barrier(4)
    identifier = operation_id()

    def write(_index):
        barrier.wait(timeout=10)
        return store.save(1, preferences(), 0, identifier)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(write, range(4)))
    assert all(result == results[0] for result in results)
    assert store.get(1)["revision"] == 1
    assert store.get(1)["conflicts"] == []


def test_concurrent_resolution_has_one_cas_winner(store):
    store.save(1, {"hiddenKeyIds": ["server"]}, 0, operation_id())
    original = stale(store)
    barrier = threading.Barrier(2)

    def resolve(choice):
        barrier.wait(timeout=10)
        try:
            return store.resolve(1, original.conflict_id, choice, 1, operation_id())
        except PreferenceConflict as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(resolve, ["server", "local"]))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert sum(isinstance(result, PreferenceConflict) for result in results) == 1
    assert store.get(1)["revision"] == 2
    assert len(store.export_conflicts(1)["conflicts"]) == 2
    assert store.get_backup(1, original.details["server_backup_id"])["data"]["hiddenKeyIds"] == ["server"]
    assert store.get_backup(1, original.details["local_backup_id"])["data"]["hiddenKeyIds"] == ["local-key"]


def test_legacy_aliases_and_all_lines_are_preserved_without_mapping(store):
    data = preferences()
    data["hiddenMapTaskIds"] = ["different-old-task"]
    data["keyOwnershipAnswers"]["token-looking-item-alias"] = True
    data["mapDrawings"]["legacy-no-source"] = [[[0, 0], [1, 1]]] * 50
    original = copy.deepcopy(data)
    assert store.save(1, data, 0, operation_id())["data"] == original
    assert data == original


@pytest.mark.parametrize("field", sorted(LOCAL_ONLY_FIELDS))
def test_local_route_queues_and_caches_never_cross_upload(store, field):
    data = {"version": 1, field: [{"operation_id": operation_id()}]}
    original = copy.deepcopy(data)
    with pytest.raises(PreferenceError):
        store.save(1, data, 0, operation_id())
    assert data == original
    assert store.get(1)["revision"] == 0
    assert store.export_conflicts(1)["backups"] == []


@pytest.mark.parametrize("data", [
    {"session": "secret"}, {"sessions": []}, {"password": "secret"}, {"token": "secret"},
    {"pass": "secret"}, {"unknown": True}, {"version": 2}, {"version": True},
    {"mapZoom": float("nan")}, {"mapZoom": float("inf")}, {"mapZoom": True},
    {"showHiddenTasks": "false"}, {"hiddenKeyIds": "key"}, {"hiddenKeyIds": [7]},
    {"keyOwnershipAnswers": {"key": "true"}}, {"hideoutOwnedMaterials": {"item": -1}},
    {"hideoutPlan": {"station": {"currentLevel": 21}}},
    {"hideoutPlan": {"station": {"session": "secret"}}},
    {"panels": {"token": True}}, {"routeStyle": {"width": True}},
    {"selectedMapFloors": {"map": []}}, {"legacyRoutesImported": {"map": {"token": "secret"}}},
    {"mapDrawings": {"old": [{"points": [[0, 0], [1, 1]], "token": "secret"}]}},
    {"mapDrawings": {"old": [[[0, 0], [float("nan"), 1]]]}},
    {"mapDrawings": {"old": [[[0, 0], [2, 1]]]}},
    {"mobilePairingAddress": "http://user:password@host"},
    {"mobilePairingAddress": "http://host/?token=secret"},
    {"selectedMapId": "\ud800"},
])
def test_invalid_data_rejected_without_mutation_or_writes(store, data):
    with pytest.raises(PreferenceError):
        store.save(1, data, 0, operation_id())
    assert store.get(1)["revision"] == 0
    assert store.export_conflicts(1)["backups"] == []


@pytest.mark.parametrize("payload", [
    {"before": {"session": "secret"}}, {"before": {"routePendingOperations": []}},
    {"before": {"operationHistory": []}},
])
def test_history_cannot_smuggle_auth_or_route_queue(store, payload):
    data = {"operationHistory": [{"id": "h", "label": "undo", "type": "ui", "data": payload}]}
    with pytest.raises(PreferenceError):
        store.save(1, data, 0, operation_id())


def test_history_all_existing_types_and_no_auth_in_export(store, database):
    task = {"id": 1, "profile_id": 1, "trader": "Prapor", "title": "Task", "objective": "",
            "item_name": "", "required_count": None, "current_count": 0, "state": "active",
            "source_task_id": "id", "source_url": "https://tarkov.dev/task/id", "source_version": "old",
            "requirements": [{"text": "Collect", "completed": False, "optional": True, "target_count": 2, "current_count": 1}]}
    entries = [("task", {"beforeTask": task, "afterTaskId": 1, "beforeUi": {"hiddenKeyIds": ["old"]}}),
               ("tasks", {"beforeTasks": [task], "beforeUi": {}}),
               ("map-drawing", {"mapId": "legacy", "strokes": [[[0, 0], [1, 1]]]}),
               ("map-visit", {"mapId": "legacy", "markerId": "point", "beforeVisited": False})]
    data = {"operationHistory": [{"id": str(index), "label": "undo", "type": kind, "data": detail}
                                 for index, (kind, detail) in enumerate(entries)]}
    assert store.save(1, data, 0, operation_id())["data"] == {"version": 1, **data}
    error = stale(store)
    assert "FIXTURE-SECRET" not in json.dumps(store.export_conflicts(1))
    assert "FIXTURE-SECRET" not in json.dumps(store.get_backup(1, error.details["server_backup_id"]))
    with database[1]() as connection:
        assert connection.execute("SELECT token FROM sessions").fetchone()[0] == "FIXTURE-SECRET-NEVER-EXPORT"
    task["token"] = "must-reject"
    with pytest.raises(PreferenceError):
        store.save(1, data, 1, operation_id())


@pytest.mark.parametrize("data", [
    {"hiddenTaskIds": ["id"] * 501},
    {"keyOwnershipAnswers": {str(index): True for index in range(301)}},
    {"mapDrawings": {"legacy": [[[0, 0], [1, 1]]] * 1001}},
])
def test_capacity_never_truncates_or_mutates_caller(store, data):
    original = copy.deepcopy(data)
    with pytest.raises(PreferenceError) as caught:
        store.save(1, data, 0, operation_id())
    assert caught.value.status == 413
    assert caught.value.details["error_code"] == "preference_capacity"
    assert data == original
    assert store.get(1)["revision"] == 0


def large_preferences(length):
    return {"version": 1, "operationHistory": [
        {"id": str(index), "label": "undo", "type": "task", "data": {"beforeTask": {"objective": "汉" * length}}}
        for index in range(12)]}


def test_two_megabyte_utf8_limit_and_large_idempotent_request(store):
    data = large_preferences(55000)
    assert len(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) < MAX_JSON_BYTES
    identifier = operation_id()
    accepted = store.save(1, data, 0, identifier)
    assert accepted["data"] == data
    assert store.save(1, data, 0, identifier) == accepted
    excessive = large_preferences(60000)
    original = copy.deepcopy(excessive)
    assert len(json.dumps(excessive, ensure_ascii=False).encode("utf-8")) > MAX_JSON_BYTES
    with pytest.raises(PreferenceError) as caught:
        store.save(1, excessive, 1, operation_id())
    assert caught.value.status == 413
    assert excessive == original
    assert store.get(1)["revision"] == 1


def test_json_escaping_near_limit_and_exact_byte_boundary(monkeypatch):
    sample = {"version": 1, "selectedMapId": "\"\\汉"}
    size = len(json.dumps(sample, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    monkeypatch.setattr(preference_store, "MAX_JSON_BYTES", size)
    assert validate_preferences(sample) == sample
    monkeypatch.setattr(preference_store, "MAX_JSON_BYTES", size - 1)
    with pytest.raises(PreferenceError) as caught:
        validate_preferences(sample)
    assert caught.value.status == 413


def test_string_expansion_is_stopped_before_materializing_full_json():
    chunk = "x" * 50000
    repeated = {"mapDrawings": {str(index): chunk for index in range(1000)}}
    with pytest.raises(PreferenceError) as caught:
        preference_store._json(repeated)
    assert caught.value.status == 413


def test_depth_nodes_and_non_json_types_are_bounded():
    nested = []
    for _index in range(30):
        nested = [nested]
    cyclic = []
    cyclic.append(cyclic)
    for data in ({"mapDrawings": {"map": nested}}, {"hiddenKeyIds": cyclic},
                 {"hiddenKeyIds": ("tuple",)}, {"selectedMapId": object()}):
        with pytest.raises(PreferenceError):
            validate_preferences(data)


@pytest.mark.parametrize("profile_id,revision,identifier", [
    (True, 0, None), (0, 0, None), (999, 0, None),
    (1, True, None), (1, -1, None), (1, 2**63, None), (1, 0, "not-a-uuid"),
])
def test_request_identifiers_and_revisions(store, profile_id, revision, identifier):
    with pytest.raises(PreferenceError):
        store.save(profile_id, {}, revision, identifier or operation_id())
    assert store.get(1)["revision"] == 0


def test_transaction_failure_rolls_back_conflict_backup_and_operation(store, database):
    store.save(1, {}, 0, operation_id())
    with database[1]() as connection:
        connection.execute("""CREATE TRIGGER fail_preference_operation BEFORE INSERT ON preference_operations
            BEGIN SELECT RAISE(ABORT, 'fixture failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        store.save(1, {"hiddenKeyIds": ["caller-still-has-this"]}, 0, operation_id())
    assert store.get(1)["conflicts"] == []
    with database[1]() as connection:
        assert connection.execute("SELECT count(*) FROM preference_backups").fetchone()[0] == 0
    assert store.get(1)["revision"] == 1


def test_success_path_failure_also_rolls_back_state_and_backups(store, database):
    store.save(1, {"hiddenKeyIds": ["original"]}, 0, operation_id())
    with database[1]() as connection:
        connection.execute("""CREATE TRIGGER fail_preference_operation BEFORE INSERT ON preference_operations
            BEGIN SELECT RAISE(ABORT, 'fixture failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        store.save(1, {"hiddenKeyIds": ["new"]}, 1, operation_id())
    assert store.get(1)["revision"] == 1
    assert store.get(1)["data"]["hiddenKeyIds"] == ["original"]
    with database[1]() as connection:
        assert connection.execute("SELECT count(*) FROM preference_backups").fetchone()[0] == 0


def test_resolution_preserves_and_exports_server_changed_since_conflict(store, database):
    store.save(1, {"hiddenKeyIds": ["original-server"]}, 0, operation_id())
    original = stale(store)
    store.save(1, {"hiddenKeyIds": ["new-server"]}, 1, operation_id())
    result = store.resolve(1, original.conflict_id, "local", 2, operation_id())
    assert store.get(1)["data"]["hiddenKeyIds"] == ["local-key"]
    assert store.get_backup(1, result["server_backup_id"])["data"]["hiddenKeyIds"] == ["new-server"]
    assert store.get_backup(1, result["local_backup_id"])["data"]["hiddenKeyIds"] == ["local-key"]
    exported = ProfilePreferences(database[1]).export_conflicts(1)
    snapshots = {tuple(backup["data"].get("hiddenKeyIds", [])) for backup in exported["backups"]}
    assert snapshots == {("original-server",), ("new-server",), ("local-key",)}
