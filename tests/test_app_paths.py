import importlib.util
import logging
from pathlib import Path
import sqlite3
import sys
import uuid

import pytest

import app_paths
import diagnostics
from app_paths import (
    AppPaths,
    RuntimeNotPreparedError,
    configure_paths,
    current_paths,
    default_database_path,
    default_player_root,
    public_cache_root,
    resolve_data_dir,
)
from players import Player, PlayerAuthStore
from save_data import UnsupportedSchemaError
from storage import TaskStore


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(app_paths, "_configured_paths", None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "windows-user"))
    yield
    logger = logging.getLogger(diagnostics.LOGGER_NAME)
    for handler in list(logger.handlers):
        if str(getattr(handler, "baseFilename", "")).startswith(str(tmp_path)):
            handler.close()
            logger.removeHandler(handler)


def test_unconfigured_path_getters_are_pure_and_stable(tmp_path, monkeypatch):
    root = tmp_path / "windows-user" / "Saved Games" / "EFTTaskAssistant"
    for suffix in ("old-exe", "new-exe"):
        directory = tmp_path / suffix
        directory.mkdir()
        monkeypatch.chdir(directory)
        assert resolve_data_dir() == root
        assert default_database_path() == root / "tasks.sqlite3"
        assert default_player_root() == root
        assert diagnostics.log_path() == root / "logs" / "app.log"
        assert public_cache_root() == root / "public-data"
    assert not root.exists()


def test_default_store_constructors_require_preparation(tmp_path):
    with pytest.raises(RuntimeNotPreparedError):
        TaskStore()
    with pytest.raises(RuntimeNotPreparedError):
        PlayerAuthStore()
    assert not (tmp_path / "windows-user").exists()


def test_explicit_stores_and_diagnostics_work_without_configuration(tmp_path):
    root = tmp_path / "explicit"
    tasks = TaskStore(root / "tasks.sqlite3")
    auth = PlayerAuthStore(root)
    assert tasks.list_profiles()
    assert auth.database_path(Player("local", "local", True)) == tasks.path
    assert auth.database_path(Player("fixture", "remote", False)) == root / "players" / "fixture.sqlite3"
    assert diagnostics.configure_logging() == diagnostics.log_path()
    assert diagnostics.log_path().is_file()


def test_configured_paths_pin_databases_logs_and_shared_public_cache(tmp_path, monkeypatch):
    root = tmp_path / "shared"
    paths = AppPaths(root, str(uuid.uuid4()))
    configure_paths(paths)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "changed-env"))
    assert current_paths() == paths
    assert TaskStore().path == paths.tasks_database
    assert PlayerAuthStore().path == paths.players_database
    assert diagnostics.log_path() == root / "logs" / "app.log"
    assert public_cache_root(tmp_path / "explicit-other") == root / "public-data"
    assert paths.player_directory == paths.data_dir / "players"
    assert paths.log_file == diagnostics.log_path()
    configure_paths(paths)
    with pytest.raises(RuntimeNotPreparedError):
        configure_paths(AppPaths(root, str(uuid.uuid4())))


def test_public_cache_explicit_fallback_is_pure(tmp_path):
    explicit = tmp_path / "explicit"
    assert public_cache_root(explicit) == explicit / "public-data"
    assert not explicit.exists()


@pytest.mark.parametrize("identifier", ["../outside", "dataset", "", None, 1])
def test_dataset_ids_reject_invalid_paths(tmp_path, identifier):
    with pytest.raises(ValueError):
        AppPaths(tmp_path, identifier)


def test_relative_root_is_rejected():
    with pytest.raises(ValueError):
        resolve_data_dir("relative")


@pytest.mark.parametrize("store_type", ["tasks", "players"])
def test_future_schema_rejected_before_any_writable_connection(tmp_path, monkeypatch, store_type):
    root = tmp_path / store_type
    root.mkdir()
    path = root / ("tasks.sqlite3" if store_type == "tasks" else "players.sqlite3")
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version=2")
        connection.execute("CREATE TABLE sentinel(value TEXT)")
    original = path.read_bytes()
    actual_connect = sqlite3.connect
    calls = []

    def readonly_only(database, *args, **kwargs):
        calls.append(str(database))
        assert kwargs.get("uri") and str(database).endswith("?mode=ro")
        return actual_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", readonly_only)
    with pytest.raises(UnsupportedSchemaError):
        TaskStore(path) if store_type == "tasks" else PlayerAuthStore(root)
    assert calls
    assert path.read_bytes() == original


@pytest.mark.parametrize("store_type", ["tasks", "players"])
def test_guard_is_rechecked_on_later_connections(tmp_path, store_type):
    root = tmp_path / store_type
    instance = TaskStore(root / "tasks.sqlite3") if store_type == "tasks" else PlayerAuthStore(root)
    with sqlite3.connect(instance.path) as connection:
        connection.execute("PRAGMA user_version=2")
    before = instance.path.read_bytes()
    with pytest.raises(UnsupportedSchemaError):
        with instance._connect():
            pytest.fail("Future schema must fail before yielding a writer")
    assert instance.path.read_bytes() == before


def test_schema_zero_upgrades_and_reopens_as_supported_one(tmp_path):
    path = tmp_path / "tasks.sqlite3"
    TaskStore(path)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version=0")
    TaskStore(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    assert TaskStore(path).list_profiles()


@pytest.mark.parametrize("module_name", ["app_paths", "save_runtime"])
def test_module_import_has_no_database_or_directory_io(module_name, monkeypatch):
    module_path = Path(app_paths.__file__).with_name(module_name + ".py")
    probe_name = module_name + "_import_probe"
    specification = importlib.util.spec_from_file_location(probe_name, module_path)
    module = importlib.util.module_from_spec(specification)
    monkeypatch.setitem(sys.modules, probe_name, module)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Module import must perform no IO")

    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    specification.loader.exec_module(module)
