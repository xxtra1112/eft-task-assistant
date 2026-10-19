import argparse
from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

import save_data
from save_data import (
    DataDirectoryBusyError,
    DataDirectoryLock,
    MigrationError,
    SaveDataError,
    UnsupportedSchemaError,
    add_data_dir_argument,
    ensure_supported_schema,
    inventory_database,
    migrate_database,
    online_backup,
    resolve_data_dir,
)


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "legacy" / "tasks.sqlite3"
    path.parent.mkdir()
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(
            "PRAGMA user_version=1;"
            "CREATE TABLE tasks(id INTEGER PRIMARY KEY, title TEXT);"
            "INSERT INTO tasks VALUES(1, 'fixture task');"
            "CREATE TABLE keys(id TEXT PRIMARY KEY, owned INTEGER);"
            "INSERT INTO keys VALUES('fixture-key', 1);"
            "CREATE TABLE routes(id INTEGER PRIMARY KEY, points TEXT);"
            "INSERT INTO routes VALUES(1, '[[0.1,0.2],[0.3,0.4]]');"
            "CREATE TABLE visits(id TEXT PRIMARY KEY);"
            "INSERT INTO visits VALUES('fixture-visit');"
            "CREATE TABLE sessions(token TEXT);"
            "INSERT INTO sessions VALUES('FIXTURE-SECRET-NEVER-IN-INVENTORY');"
        )
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def migration(source, target, **kwargs):
    return migrate_database(source, target, supported_version=2, target_version=2, **kwargs)


def test_resolver_is_stable_when_executable_and_cwd_move(tmp_path, monkeypatch):
    local = tmp_path / "windows-user" / "Local"
    profile = tmp_path / "windows-user"
    expected = profile / "Saved Games" / "EFTTaskAssistant"
    explicit = tmp_path / "isolated saves"
    for index in range(2):
        location = tmp_path / str(index)
        location.mkdir()
        monkeypatch.chdir(location)
        monkeypatch.setattr(sys, "executable", str(location / "moved.exe"))
        assert resolve_data_dir(environ={"LOCALAPPDATA": str(local), "USERPROFILE": str(profile)}) == expected
        parser = argparse.ArgumentParser()
        add_data_dir_argument(parser)
        assert resolve_data_dir(parser.parse_args(["--data-dir", str(explicit)]).data_dir) == explicit
    assert not local.exists()
    assert not explicit.exists()


def test_resolver_default_and_bad_relative_inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert resolve_data_dir(environ={"USERPROFILE": str(tmp_path)}) == tmp_path / "Saved Games" / "EFTTaskAssistant"
    with pytest.raises(SaveDataError):
        resolve_data_dir(environ={})
    for value in ("relative", "", "../save"):
        with pytest.raises(ValueError):
            resolve_data_dir(value)
        with pytest.raises(SaveDataError):
            resolve_data_dir(environ={"USERPROFILE": value or "relative"})


def test_resolver_keeps_declared_root_without_filesystem_canonicalization(tmp_path, monkeypatch):
    def must_not_resolve(self, *args, **kwargs):
        pytest.fail("Root selection must not depend on filesystem redirection or existence")

    monkeypatch.setattr(Path, "resolve", must_not_resolve)
    assert resolve_data_dir(environ={"USERPROFILE": str(tmp_path)}) == tmp_path / "Saved Games" / "EFTTaskAssistant"


def test_import_and_path_resolution_do_not_create_files(tmp_path):
    environment = dict(os.environ, LOCALAPPDATA=str(tmp_path / "unused"), PYTHONDONTWRITEBYTECODE="1")
    script = (
        "import importlib.util, sys; from pathlib import Path; sys.path.insert(0, str(Path(sys.argv[1]).parent)); "
        "spec=importlib.util.spec_from_file_location('save_data', sys.argv[1]); "
        "module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; "
        "spec.loader.exec_module(module); module.resolve_data_dir(environ={'USERPROFILE': sys.argv[2]})"
    )
    subprocess.run([sys.executable, "-B", "-c", script, save_data.__file__, str(tmp_path / "profile")], cwd=tmp_path,
                   env=environment, check=True, capture_output=True, timeout=15)
    assert list(tmp_path.iterdir()) == []


def test_inventory_is_readonly_and_exposes_only_counts(source):
    before = digest(source)
    inventory = inventory_database(source)
    assert inventory.integrity == "ok"
    assert inventory.user_version == 1
    assert inventory.table_counts == {"keys": 1, "routes": 1, "sessions": 1, "tasks": 1, "visits": 1}
    assert "FIXTURE-SECRET" not in repr(inventory)
    assert digest(source) == before
    assert not Path(str(source) + "-journal").exists()


def test_readonly_connection_rejects_writes(source):
    with save_data._read_only(source, 1) as connection:
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("DELETE FROM tasks")


def test_inventory_missing_or_corrupt_file_never_creates_database(tmp_path):
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(SaveDataError):
        inventory_database(missing)
    assert not missing.exists()
    corrupt = tmp_path / "corrupt.sqlite3"
    corrupt.write_bytes(b"FIXTURE-SECRET not a database")
    with pytest.raises(SaveDataError) as error:
        inventory_database(corrupt)
    assert "FIXTURE-SECRET" not in str(error.value)


def test_backup_online_wal_includes_committed_and_excludes_uncommitted(source, tmp_path):
    target = tmp_path / "backups" / "online.sqlite3"
    with closing(sqlite3.connect(source)) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("INSERT INTO tasks VALUES(2, 'committed WAL fixture')")
        writer.commit()
        assert Path(str(source) + "-wal").stat().st_size > 0
        writer.execute("INSERT INTO tasks VALUES(3, 'uncommitted fixture')")
        source_before = digest(source)
        wal_before = digest(Path(str(source) + "-wal"))
        result = online_backup(source, target, supported_version=2)
        assert result.table_counts["tasks"] == 2
        assert result.user_version == 1
        assert digest(source) == source_before
        assert digest(Path(str(source) + "-wal")) == wal_before
        writer.rollback()
    assert inventory_database(target).integrity == "ok"
    assert not Path(str(target) + "-wal").exists()
    assert not list(target.parent.glob(".save-shadow-*"))


def test_backup_rejects_existing_destination(source, tmp_path):
    before = digest(source)
    with pytest.raises(FileExistsError):
        online_backup(source, source)
    target = tmp_path / "backup.sqlite3"
    target.write_bytes(b"preserve")
    with pytest.raises(FileExistsError):
        online_backup(source, target)
    assert target.read_bytes() == b"preserve"
    assert digest(source) == before


def test_backup_future_schema_rejected_without_destination_writes(source, tmp_path):
    target = tmp_path / "absent" / "backup.sqlite3"
    with pytest.raises(UnsupportedSchemaError):
        online_backup(source, target, supported_version=0)
    assert not target.parent.exists()


def test_atomic_migration_preserves_all_fixture_data_and_backup(source, tmp_path):
    before = digest(source)
    target = tmp_path / "unified" / "tasks.sqlite3"

    def upgrade(connection):
        assert not target.exists()
        backups = list((target.parent / "save-backups").glob("*.sqlite3"))
        assert len(backups) == 1
        assert inventory_database(backups[0]).user_version == 1
        connection.execute("ALTER TABLE tasks ADD COLUMN migrated INTEGER DEFAULT 1")

    result = migration(source, target, migrate=upgrade)
    assert result.status == "migrated"
    assert result.backup_path.exists()
    assert inventory_database(target).user_version == 2
    assert inventory_database(target).table_counts == inventory_database(source).table_counts
    assert inventory_database(result.backup_path).user_version == 1
    assert digest(source) == before
    with closing(sqlite3.connect(target)) as connection:
        assert connection.execute("SELECT migrated FROM tasks").fetchone() == (1,)
        assert connection.execute("SELECT owned FROM keys").fetchone() == (1,)
        assert connection.execute("SELECT points FROM routes").fetchone() == ('[[0.1,0.2],[0.3,0.4]]',)
        assert connection.execute("SELECT id FROM visits").fetchone() == ("fixture-visit",)
    assert not list(target.parent.glob(".save-shadow-*"))


def test_migration_callback_failure_rolls_back_and_retains_backup(source, tmp_path):
    target = tmp_path / "unified" / "tasks.sqlite3"
    before = digest(source)

    def fail(connection):
        connection.execute("DELETE FROM tasks")
        raise RuntimeError("FIXTURE-SECRET from callback")

    with pytest.raises(MigrationError) as error:
        migration(source, target, migrate=fail)
    assert "FIXTURE-SECRET" not in str(error.value)
    assert inventory_database(error.value.backup_path).table_counts["tasks"] == 1
    assert not target.exists()
    assert digest(source) == before
    assert not list(target.parent.glob(".save-shadow-*"))
    with DataDirectoryLock(target.parent):
        pass


@pytest.mark.parametrize("bad_version", [0, 3])
def test_migration_version_mismatch_rolls_back(source, tmp_path, bad_version):
    target = tmp_path / "unified" / "tasks.sqlite3"
    before = digest(source)
    with pytest.raises(MigrationError):
        migration(source, target, migrate=lambda connection: connection.execute(
            "PRAGMA user_version=" + str(bad_version)))
    assert not target.exists()
    assert digest(source) == before


def test_migration_corrupt_shadow_is_never_published(source, tmp_path):
    target = tmp_path / "unified" / "tasks.sqlite3"
    before = digest(source)

    def corrupt(connection):
        connection.execute("PRAGMA writable_schema=ON")
        connection.execute("UPDATE sqlite_master SET rootpage=999999 WHERE name='tasks'")

    with pytest.raises(MigrationError) as error:
        migration(source, target, migrate=corrupt)
    assert inventory_database(error.value.backup_path).integrity == "ok"
    assert not target.exists()
    assert digest(source) == before


@pytest.mark.parametrize("contents", [b"", b"existing real target fixture"])
def test_conflict_preserves_both_sides_without_callback(source, tmp_path, contents):
    target = tmp_path / "target.sqlite3"
    target.write_bytes(contents)
    before = digest(source), digest(target)

    def must_not_run(connection):
        pytest.fail("Conflicting target must never invoke migration")

    result = migration(source, target, migrate=must_not_run)
    assert result.status == "conflict"
    assert result.backup_path is None
    assert (digest(source), digest(target)) == before
    assert not (tmp_path / "save-backups").exists()
    assert not (tmp_path / ".save-data.lock").exists()


def test_conflict_for_existing_sqlite_and_same_source(source, tmp_path):
    target = tmp_path / "target.sqlite3"
    online_backup(source, target)
    before = digest(source), digest(target)
    assert migration(source, target).status == "conflict"
    assert migration(source, source).status == "conflict"
    assert (digest(source), digest(target)) == before


def test_target_appearing_during_migration_is_not_overwritten(source, tmp_path):
    target = tmp_path / "unified" / "tasks.sqlite3"

    def simulate_legacy_writer(connection):
        target.write_bytes(b"legacy writer fixture")

    result = migration(source, target, migrate=simulate_legacy_writer)
    assert result.status == "conflict"
    assert result.reason == "target_appeared"
    assert target.read_bytes() == b"legacy writer fixture"
    assert result.backup_path.exists()


def test_publish_race_uses_no_overwrite_primitive(source, tmp_path, monkeypatch):
    target = tmp_path / "backup.sqlite3"
    original_link = os.link

    def competing_link(shadow, destination):
        target.write_bytes(b"race winner")
        return original_link(shadow, destination)

    monkeypatch.setattr(save_data.os, "link", competing_link)
    with pytest.raises(FileExistsError):
        online_backup(source, target)
    assert target.read_bytes() == b"race winner"
    assert not list(tmp_path.glob(".save-shadow-*"))


def test_failed_atomic_publication_preserves_source(source, tmp_path, monkeypatch):
    target = tmp_path / "unified" / "tasks.sqlite3"
    before = digest(source)
    original_link = os.link

    def failing_link(shadow, destination):
        if Path(destination) == target:
            raise OSError("fixture unsupported hard links")
        return original_link(shadow, destination)

    monkeypatch.setattr(save_data.os, "link", failing_link)
    with pytest.raises(MigrationError) as error:
        migration(source, target)
    assert inventory_database(error.value.backup_path).integrity == "ok"
    assert not target.exists()
    assert digest(source) == before


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_orphan_target_sidecars_are_conflicts(source, tmp_path, suffix):
    target = tmp_path / "target.sqlite3"
    sidecar = Path(str(target) + suffix)
    sidecar.write_bytes(b"preserve orphan")
    assert migration(source, target).status == "conflict"
    assert sidecar.read_bytes() == b"preserve orphan"
    assert not target.exists()


def test_future_schema_and_downgrade_rejected_before_writes(source, tmp_path):
    target = tmp_path / "unified" / "tasks.sqlite3"
    before = digest(source)
    with pytest.raises(UnsupportedSchemaError):
        ensure_supported_schema(source, 0)
    with pytest.raises(UnsupportedSchemaError):
        migrate_database(source, target, supported_version=0, target_version=0)
    with pytest.raises(UnsupportedSchemaError):
        migrate_database(source, target, supported_version=2, target_version=0)
    with pytest.raises(UnsupportedSchemaError):
        migrate_database(source, target, supported_version=2, target_version=3)
    assert not target.parent.exists()
    assert digest(source) == before


def test_lock_contention_and_independent_directories(tmp_path):
    root = tmp_path / "data"
    with DataDirectoryLock(root):
        with pytest.raises(DataDirectoryBusyError):
            DataDirectoryLock(root, timeout=0.05).acquire()
        with DataDirectoryLock(tmp_path / "other"):
            pass
    with DataDirectoryLock(root):
        pass
    assert (root / ".save-data.lock").exists()


def test_lock_cross_process_exclusion_and_process_exit_release(tmp_path):
    root = tmp_path / "data"
    script = (
        "import importlib.util, sys; "
        "spec=importlib.util.spec_from_file_location('save_data', sys.argv[1]); "
        "module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; "
        "spec.loader.exec_module(module); "
        "lock=module.DataDirectoryLock(sys.argv[2]); lock.acquire(); "
        "print('LOCKED', flush=True); sys.stdin.readline()"
    )
    child = subprocess.Popen([sys.executable, "-B", "-u", "-c", script, save_data.__file__, str(root)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "LOCKED"
        with pytest.raises(DataDirectoryBusyError):
            DataDirectoryLock(root).acquire()
        child.stdin.write("exit\n")
        child.stdin.flush()
        child.wait(timeout=15)
        assert child.returncode == 0
        with DataDirectoryLock(root):
            pass
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=15)
        child.stdin.close()
        child.stdout.close()
        child.stderr.close()


def test_migration_uses_held_directory_lock_and_rejects_wrong_lock(source, tmp_path):
    target = tmp_path / "unified" / "tasks.sqlite3"
    with DataDirectoryLock(target.parent) as lock:
        assert migration(source, target, lock=lock).status == "migrated"
        with pytest.raises(DataDirectoryBusyError):
            DataDirectoryLock(target.parent).acquire()
    with DataDirectoryLock(tmp_path / "wrong") as lock:
        with pytest.raises(ValueError):
            migration(source, target.parent / "other.sqlite3", lock=lock)


def test_migration_contention_prevents_target_writes(source, tmp_path):
    target = tmp_path / "unified" / "tasks.sqlite3"
    before = digest(source)
    with DataDirectoryLock(target.parent):
        with pytest.raises(DataDirectoryBusyError):
            migration(source, target)
    assert not target.exists()
    assert not (target.parent / "save-backups").exists()
    assert digest(source) == before


def test_player_database_migration_can_use_application_root_lock(source, tmp_path):
    root = tmp_path / "unified"
    target = root / "players" / "fixture-player.sqlite3"
    with DataDirectoryLock(root) as lock:
        assert migration(source, target, lock=lock).status == "migrated"
        with pytest.raises(DataDirectoryBusyError):
            DataDirectoryLock(root).acquire()
    assert inventory_database(target).table_counts["visits"] == 1


@pytest.mark.parametrize("version", [-1, True, 1.5, 2147483648])
def test_invalid_versions_rejected_without_writes(source, tmp_path, version):
    target = tmp_path / "unified" / "tasks.sqlite3"
    with pytest.raises(ValueError):
        migrate_database(source, target, supported_version=version, target_version=1)
    assert not target.parent.exists()
