import hashlib
import json
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from save_data import DataDirectoryLock
from save_runtime import prepare_runtime
from save_setup import run_save_setup
from storage import TaskStore
from web_server import AssistantState, main


def test_startup_confirmation_is_read_only_until_explicit_same_origin_request(tmp_path):
    root = tmp_path / "save-root"
    store = TaskStore(root / "tasks.sqlite3")
    original = hashlib.sha256(store.path.read_bytes()).hexdigest()
    servers = []
    results = []
    ready = threading.Event()

    def bind(_state, handler, port=None):
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        servers.append(server)
        ready.set()
        return server

    def request(path, data=None, origin=None):
        connection = HTTPConnection("127.0.0.1", servers[0].server_port, timeout=10)
        try:
            headers = {"Content-Type": "application/json"}
            if origin:
                headers["Origin"] = origin
            connection.request("POST" if data is not None else "GET", path,
                               json.dumps(data) if data is not None else None, headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    with DataDirectoryLock(root) as lock:
        initial = prepare_runtime(root, lock=lock)
        assert initial.status == "legacy_import_required"
        thread = threading.Thread(target=lambda: results.append(run_save_setup(
            root, lock, initial, bind=bind, no_browser=True)), daemon=True)
        thread.start()
        assert ready.wait(5)
        status, inventory = request("/api/save-setup")
        assert status == 200
        assert not (root / "active-dataset.json").exists()
        assert request("/api/save-setup", {"confirmed": False})[0] == 409
        payload = {"confirmed": True, "token": inventory["token"], "action": "migrate"}
        assert request("/api/save-setup", payload, "https://example.com")[0] == 409
        assert not (root / "active-dataset.json").exists()
        assert request("/api/save-setup", payload)[0] == 200
        thread.join(15)
        assert not thread.is_alive()
        assert results[0][0].status == "ready"
        assert results[0][0].paths.tasks_database != store.path
        assert hashlib.sha256(store.path.read_bytes()).hexdigest() == original
        assert (root / "backups" / results[0][0].dataset_id / "tasks.sqlite3").exists()


def test_main_list_saves_never_creates_data_or_opens_default_root(tmp_path, capsys):
    root = tmp_path / "missing"
    assert main(["--data-dir", str(root), "--list-saves"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "empty"
    assert not root.exists()


def test_main_refuses_second_instance_even_on_another_port(tmp_path, capsys):
    root = tmp_path / "save-root"
    with DataDirectoryLock(root):
        assert main(["--data-dir", str(root), "--port", "0", "--no-browser"]) == 2
        assert "存档启动已安全停止" in capsys.readouterr().err
        assert not (root / "active-dataset.json").exists()


def test_reference_provider_selected_before_restart_does_not_request_unsupported_catalog(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr("web_server.log_event", lambda *_args, **_kwargs: None)
    store = TaskStore(tmp_path / "save" / "tasks.sqlite3")
    profile_id = store.default_profile_id()
    store.add_task("Prapor", "Retained across reference-provider restart", profile_id=profile_id)
    store.set_app_setting(f"data_source:{profile_id}", "reemr")
    assistant = AssistantState(TaskStore(store.path))
    try:
        assert assistant.source_for_profile() == "reemr"
        assert not assistant.catalog_busy
        assert "参考地图" in assistant.catalog_status
        assert assistant.snapshot()["tasks"][0]["title"] == "Retained across reference-provider restart"
    finally:
        assistant.close()
