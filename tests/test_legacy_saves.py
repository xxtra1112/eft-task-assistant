import hashlib
import json
import sqlite3
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from legacy_saves import discover_legacy_saves
from save_data import DataDirectoryLock
from save_runtime import prepare_runtime
from save_setup import run_save_setup
from storage import TaskStore


def seed(path, title):
    store = TaskStore(path / "tasks.sqlite3")
    store.add_task("Prapor", title)
    return store.path


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_two_previous_nonempty_roots_require_explicit_selection_and_preserve_both(tmp_path):
    first = seed(tmp_path / "old-normal", "first source")
    second = seed(tmp_path / "old-package", "second source")
    hashes = {path: checksum(path) for path in (first, second)}
    target = tmp_path / "stable-new-root"
    status = discover_legacy_saves(target, [first.parent, second.parent, first.parent])
    assert status.status == "legacy_import_required"
    assert len(status.legacy_roots) == 2
    assert all(entry["counts"]["tasks"] == 1 for entry in status.legacy_roots)
    assert not target.exists()
    servers = []
    results = []
    started = threading.Event()

    def bind(_state, handler, port=None):
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        servers.append(server)
        started.set()
        return server

    def request(data=None):
        connection = HTTPConnection("127.0.0.1", servers[0].server_port, timeout=15)
        try:
            connection.request("POST" if data is not None else "GET", "/api/save-setup",
                               json.dumps(data) if data is not None else None, {"Content-Type": "application/json"})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    with DataDirectoryLock(target) as lock:
        thread = threading.Thread(target=lambda: results.append(run_save_setup(target, lock, status, bind=bind, no_browser=True)), daemon=True)
        thread.start()
        assert started.wait(5)
        payload = {"action": "migrate", "confirmed": True, "token": request()[1]["token"]}
        assert request(payload)[0] == 409
        assert not (target / "active-dataset.json").exists()
        assert request({**payload, "source_root": str(tmp_path / "not-in-candidates")})[0] == 409
        assert request({**payload, "source_root": str(second.parent)})[0] == 200
        thread.join(15)
        assert not thread.is_alive()
        migrated = results[0][0]
        assert migrated.status == "ready"
        assert TaskStore(migrated.paths.tasks_database).list_tasks(1)[0].title == "second source"
        assert discover_legacy_saves(target, [first.parent, second.parent]) is None
    assert {path: checksum(path) for path in (first, second)} == hashes


def test_future_or_damaged_legacy_remains_visible_unavailable_without_writing(tmp_path):
    path = seed(tmp_path / "future", "future data")
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version=99")
    original = checksum(path)
    target = tmp_path / "new"
    status = discover_legacy_saves(target, [path.parent])
    assert status.legacy_roots[0]["available"] is False
    assert checksum(path) == original
    assert not target.exists()


def test_preexisting_managed_or_legacy_target_is_never_replaced_by_discovery(tmp_path):
    foreign = seed(tmp_path / "foreign", "do not merge")
    local = seed(tmp_path / "local", "keep current")
    assert discover_legacy_saves(local.parent, [foreign.parent]) is None
    with DataDirectoryLock(local.parent) as lock:
        managed = prepare_runtime(local.parent, migrate=True, lock=lock)
        manifest = (local.parent / "active-dataset.json").read_bytes()
        assert discover_legacy_saves(local.parent, [foreign.parent]) is None
        assert (local.parent / "active-dataset.json").read_bytes() == manifest
        assert TaskStore(managed.paths.tasks_database).list_tasks(1)[0].title == "keep current"
