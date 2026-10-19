import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

import app_paths
import save_runtime
from app_paths import configure_paths, current_paths, public_cache_root
from players import PlayerAuthStore
from save_data import DataDirectoryBusyError, DataDirectoryLock, UnsupportedSchemaError, inventory_database
from save_runtime import (
    MANIFEST_NAME,
    RuntimePreparationError,
    export_runtime_status,
    prepare_runtime,
    rollback_dataset,
    select_dataset,
)
from storage import TaskStore


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(app_paths, "_configured_paths", None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "windows-user"))


def seed_root(root, *, player_database=True, schema=0):
    store = TaskStore(root / "tasks.sqlite3")
    with store._connect() as connection:
        connection.execute("""INSERT INTO tasks(profile_id,trader,title,created_at,updated_at)
            SELECT id,'fixture','FIXTURE-TASK-ROW-SECRET','now','now' FROM profiles LIMIT 1""")
    auth = PlayerAuthStore(root)
    player = auth.local_player()
    with auth._connect() as connection:
        connection.execute("UPDATE players SET username='FIXTURE-USER-ROW-SECRET'")
        connection.execute("INSERT INTO sessions(token_hash,player_id,expires_at) VALUES (?,?,?)",
                           ("FIXTURE-SESSION-ROW-SECRET", player.id, 9999999999))
    if player_database:
        path = root / "players" / "fixture-player.sqlite3"
        private = TaskStore(path)
        with private._connect() as connection:
            connection.execute("""INSERT INTO tasks(profile_id,title,created_at,updated_at)
                SELECT id,'FIXTURE-PRIVATE-ROW-SECRET','now','now' FROM profiles LIMIT 1""")
    for path in [root / "tasks.sqlite3", root / "players.sqlite3", *sorted((root / "players").glob("*.sqlite3"))]:
        with sqlite3.connect(path) as connection:
            connection.execute("PRAGMA user_version=" + str(schema))
    return root


def digests(root):
    paths = [root / "tasks.sqlite3", root / "players.sqlite3", *sorted((root / "players").glob("*.sqlite3"))]
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths if path.exists()}


def active(root):
    return json.loads((root / MANIFEST_NAME).read_bytes())["active_dataset"]


def test_new_root_ready_reopen_and_main_retains_lock(tmp_path):
    root = tmp_path / "shared"
    assert export_runtime_status(root)["status"] == "empty"
    assert not root.exists()
    with DataDirectoryLock(root) as lock:
        first = prepare_runtime(root, lock=lock)
        assert first.status == "ready"
        assert first.reason == "created"
        assert first.paths.data_dir == root / "datasets" / first.dataset_id
        assert not (root / "tasks.sqlite3").exists()
        assert not (root / "players.sqlite3").exists()
        assert active(root) == first.dataset_id
        assert lock.held
        with pytest.raises(DataDirectoryBusyError):
            DataDirectoryLock(root).acquire()
        again = prepare_runtime(root, lock=lock)
        assert again.dataset_id == first.dataset_id
        assert again.manifest_generation == 1
        configure_paths(first.paths)
        assert TaskStore().path == first.paths.tasks_database
        assert PlayerAuthStore().path == first.paths.players_database
    with DataDirectoryLock(root) as lock:
        assert prepare_runtime(root, lock=lock).dataset_id == first.dataset_id


def test_discovery_of_nonempty_legacy_requires_confirmation_and_preserves_bytes(tmp_path):
    root = seed_root(tmp_path / "legacy")
    original = digests(root)
    with DataDirectoryLock(root) as lock:
        result = prepare_runtime(root, lock=lock)
        assert result.status == "legacy_import_required"
        assert result.paths is None
        assert result.public_data()["requires_confirmation"]
        assert len(result.databases) == 3
        assert not (root / MANIFEST_NAME).exists()
        assert not (root / "datasets").exists()
        assert not (root / "backups").exists()
    assert digests(root) == original


def test_full_shadow_import_retains_all_originals_backups_and_profiles(tmp_path):
    root = seed_root(tmp_path / "legacy")
    original = digests(root)
    with DataDirectoryLock(root) as lock:
        result = prepare_runtime(root, migrate=True, lock=lock)
        assert result.status == "ready"
        assert result.reason == "imported"
        assert result.backup_dir == root / "backups" / result.dataset_id
        assert digests(root) == original
        assert set(digests(result.backup_dir)) == set(original)
        for relative in original:
            backup = inventory_database(result.backup_dir / relative)
            source = inventory_database(root / relative)
            copied = inventory_database(result.paths.data_dir / relative)
            assert backup.table_counts == source.table_counts
            assert backup.user_version == 0
            assert copied.user_version == 1
            assert copied.table_counts.get("tasks", 0) == source.table_counts.get("tasks", 0)
        assert TaskStore(result.paths.tasks_database).list_tasks()[0].title == "FIXTURE-TASK-ROW-SECRET"
        assert TaskStore(result.paths.player_directory / "fixture-player.sqlite3").list_tasks()[0].title == "FIXTURE-PRIVATE-ROW-SECRET"
        assert prepare_runtime(root, lock=lock).dataset_id == result.dataset_id
        assert len(tuple((root / "datasets").iterdir())) == 1


def test_wal_commits_are_included_without_checkpointing_source(tmp_path):
    source = seed_root(tmp_path / "source", player_database=False)
    destination = tmp_path / "target"
    connection = sqlite3.connect(source / "tasks.sqlite3")
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("UPDATE tasks SET title='FIXTURE-WAL-COMMITTED'")
        connection.commit()
        assert (source / "tasks.sqlite3-wal").stat().st_size > 0
        original = digests(source)
        original_wal = (source / "tasks.sqlite3-wal").read_bytes()
        with DataDirectoryLock(destination) as lock:
            result = prepare_runtime(destination, migrate=True, source_root=source, lock=lock)
        assert TaskStore(result.paths.tasks_database).list_tasks()[0].title == "FIXTURE-WAL-COMMITTED"
        assert digests(source) == original
        assert (source / "tasks.sqlite3-wal").read_bytes() == original_wal
    finally:
        connection.close()


def test_external_import_is_independent_and_does_not_merge_existing_dataset(tmp_path):
    source = seed_root(tmp_path / "foreign")
    target = tmp_path / "target"
    with DataDirectoryLock(target) as lock:
        original = prepare_runtime(target, lock=lock)
        old_digest = digests(original.paths.data_dir)
        imported = prepare_runtime(target, source_root=source, migrate=True, lock=lock)
        assert imported.dataset_id != original.dataset_id
        assert imported.paths.data_dir.parent == original.paths.data_dir.parent
        assert digests(original.paths.data_dir) == old_digest
        assert TaskStore(original.paths.tasks_database).list_tasks() == []
        assert len(TaskStore(imported.paths.tasks_database).list_tasks()) == 1
        assert json.loads((target / MANIFEST_NAME).read_bytes())["previous_dataset"] == original.dataset_id


def test_external_import_without_activation_preserves_pointer_until_explicit_selection(tmp_path):
    source = seed_root(tmp_path / "foreign")
    root = tmp_path / "target"
    with DataDirectoryLock(root) as lock:
        first = prepare_runtime(root, lock=lock)
        configure_paths(first.paths)
        original_manifest = (root / MANIFEST_NAME).read_bytes()
        imported = prepare_runtime(root, source_root=source, migrate=True, activate=False, lock=lock)
        assert imported.status == "imported"
        assert imported.paths is not None
        assert imported.dataset_id != first.dataset_id
        assert (root / MANIFEST_NAME).read_bytes() == original_manifest
        assert current_paths() == first.paths
        assert TaskStore().list_tasks() == []
        assert len(TaskStore(imported.paths.tasks_database).list_tasks()) == 1
        assert imported.dataset_id in export_runtime_status(root)["datasets"]
        assert select_dataset(root, imported.dataset_id, lock=lock)["effective"] == "next_startup"
        assert active(root) == imported.dataset_id
        assert current_paths() == first.paths
        assert TaskStore().list_tasks() == []
        assert export_runtime_status(root)["pending_restart"]
        configure_paths(None)
        restarted = prepare_runtime(root, lock=lock)
        configure_paths(restarted.paths)
        assert len(TaskStore().list_tasks()) == 1
        assert public_cache_root() == root / "public-data"


def test_unactivated_import_to_root_without_manifest_does_not_create_one(tmp_path):
    source = seed_root(tmp_path / "foreign")
    target = tmp_path / "target"
    with DataDirectoryLock(target) as lock:
        imported = prepare_runtime(target, source_root=source, migrate=True, activate=False, lock=lock)
        assert imported.status == "imported"
        assert imported.manifest_generation == 0
        assert not (target / MANIFEST_NAME).exists()
        assert export_runtime_status(target)["status"] == "legacy_import_required"
        assert export_runtime_status(target)["reason"] == "existing_datasets_require_selection"
        assert prepare_runtime(target, lock=lock).status == "legacy_import_required"
        select_dataset(target, imported.dataset_id, lock=lock)
        assert active(target) == imported.dataset_id


def test_external_discovery_requires_explicit_confirmation_even_when_active_exists(tmp_path):
    source = seed_root(tmp_path / "foreign")
    target = tmp_path / "target"
    with DataDirectoryLock(target) as lock:
        first = prepare_runtime(target, lock=lock)
        raw = (target / MANIFEST_NAME).read_bytes()
        status = prepare_runtime(target, source_root=source, lock=lock, activate=False)
        assert status.status == "legacy_import_required"
        assert (target / MANIFEST_NAME).read_bytes() == raw
        assert active(target) == first.dataset_id
        assert len(tuple((target / "datasets").iterdir())) == 1


def test_selection_and_rollback_are_next_startup_only_and_archive_exact_manifests(tmp_path):
    source = seed_root(tmp_path / "foreign")
    target = tmp_path / "target"
    with DataDirectoryLock(target) as lock:
        first = prepare_runtime(target, lock=lock)
        configure_paths(first.paths)
        original_manifest = (target / MANIFEST_NAME).read_bytes()
        second = prepare_runtime(target, source_root=source, migrate=True, lock=lock)
        assert current_paths() == first.paths
        second_manifest = (target / MANIFEST_NAME).read_bytes()
        rollback = rollback_dataset(target, lock=lock)
        assert rollback["effective"] == "next_startup"
        assert active(target) == first.dataset_id
        backups = [path.read_bytes() for path in (target / "manifest-backups").glob("*.json")]
        assert original_manifest in backups
        assert second_manifest in backups
        assert current_paths() == first.paths
        selected = select_dataset(target, second.dataset_id, lock=lock)
        assert selected["effective"] == "next_startup"
        assert current_paths() == first.paths
        assert public_cache_root(second.paths.data_dir) == target / "public-data"


def test_source_managed_root_imports_only_its_active_collection(tmp_path):
    source = tmp_path / "managed-source"
    target = tmp_path / "target"
    with DataDirectoryLock(source) as lock:
        prepared = prepare_runtime(source, lock=lock)
    auth = PlayerAuthStore(prepared.paths.data_dir)
    auth.local_player()
    with DataDirectoryLock(target) as lock:
        result = prepare_runtime(target, source_root=source, migrate=True, lock=lock)
    assert result.dataset_id != prepared.dataset_id
    assert inventory_database(result.paths.players_database).table_counts["players"] == 1


@pytest.mark.parametrize("relative", ["tasks.sqlite3", "players.sqlite3", "players/fixture-player.sqlite3"])
def test_future_schema_in_any_source_is_rejected_before_destination_write(tmp_path, monkeypatch, relative):
    source = seed_root(tmp_path / "source")
    with sqlite3.connect(source / relative) as connection:
        connection.execute("PRAGMA user_version=2")
    target = tmp_path / "target"
    real_connect = sqlite3.connect
    calls = []

    def readonly_only(path, *args, **kwargs):
        calls.append(str(path))
        assert kwargs.get("uri") and str(path).endswith("?mode=ro")
        return real_connect(path, *args, **kwargs)

    with DataDirectoryLock(target) as lock:
        monkeypatch.setattr(sqlite3, "connect", readonly_only)
        with pytest.raises(UnsupportedSchemaError):
            prepare_runtime(target, source_root=source, migrate=True, lock=lock)
        assert calls
        assert not (target / "datasets").exists()
        assert not (target / MANIFEST_NAME).exists()


@pytest.mark.parametrize("mutation", ["existing", "new_player", "wal"])
def test_observed_source_writes_abort_import_and_keep_original_manifest_and_backups(tmp_path, monkeypatch, mutation):
    source = seed_root(tmp_path / "foreign")
    target = tmp_path / "target"
    real_backup = save_runtime.online_backup
    changed = False
    writer = None

    def copy_and_change(origin, destination, **kwargs):
        nonlocal changed, writer
        result = real_backup(origin, destination, **kwargs)
        if not changed and Path(origin).parent == source:
            changed = True
            if mutation == "new_player":
                TaskStore(source / "players" / "new-player.sqlite3")
            else:
                writer = sqlite3.connect(source / "tasks.sqlite3")
                if mutation == "wal":
                    writer.execute("PRAGMA journal_mode=WAL")
                writer.execute("UPDATE tasks SET title='changed-during-copy'")
                writer.commit()
        return result

    try:
        with DataDirectoryLock(target) as lock:
            first = prepare_runtime(target, lock=lock)
            original_manifest = (target / MANIFEST_NAME).read_bytes()
            monkeypatch.setattr(save_runtime, "online_backup", copy_and_change)
            with pytest.raises(RuntimePreparationError) as caught:
                prepare_runtime(target, source_root=source, migrate=True, lock=lock)
            assert caught.value.status == "source_changed"
            assert caught.value.backup_dir.is_dir()
            assert list(caught.value.backup_dir.rglob("*.sqlite3"))
            assert (target / MANIFEST_NAME).read_bytes() == original_manifest
            assert active(target) == first.dataset_id
    finally:
        if writer is not None:
            writer.close()


def test_shadow_schema_failure_keeps_source_backups_and_manifest(tmp_path, monkeypatch):
    source = seed_root(tmp_path / "source")
    original = digests(source)
    target = tmp_path / "target"
    with DataDirectoryLock(target) as lock:
        prepare_runtime(target, lock=lock)
        raw = (target / MANIFEST_NAME).read_bytes()

        def fail(_paths):
            raise ValueError("FIXTURE-SENSITIVE-ROW-IN-ERROR")

        monkeypatch.setattr(save_runtime, "_initialize_dataset", fail)
        with pytest.raises(RuntimePreparationError) as caught:
            prepare_runtime(target, source_root=source, migrate=True, lock=lock)
        assert caught.value.status == "shadow_import_failed"
        assert "FIXTURE-SENSITIVE" not in str(caught.value)
        assert caught.value.backup_dir.is_dir()
        assert digests(source) == original
        assert (target / MANIFEST_NAME).read_bytes() == raw


def test_atomic_manifest_replace_failure_retains_original_bytes_and_recoverable_dataset(tmp_path, monkeypatch):
    source = seed_root(tmp_path / "source")
    target = tmp_path / "target"
    with DataDirectoryLock(target) as lock:
        prepare_runtime(target, lock=lock)
        original = (target / MANIFEST_NAME).read_bytes()

        def fail_replace(*_args):
            raise OSError("fixture replace failure")

        with monkeypatch.context() as context:
            context.setattr(save_runtime.os, "replace", fail_replace)
            with pytest.raises(RuntimePreparationError) as caught:
                prepare_runtime(target, source_root=source, migrate=True, lock=lock)
        assert (target / MANIFEST_NAME).read_bytes() == original
        assert original in [path.read_bytes() for path in (target / "manifest-backups").glob("*.json")]
        recovered = caught.value.dataset_id
        assert (target / "datasets" / recovered / "dataset.json").is_file()
        select_dataset(target, recovered, lock=lock)
        assert active(target) == recovered


def test_status_exports_only_metadata_and_counts_never_row_values(tmp_path):
    root = seed_root(tmp_path / "legacy")
    before = digests(root)
    status = export_runtime_status(root)
    serialized = json.dumps(status)
    assert "FIXTURE-" not in serialized
    assert any(item["counts"].get("sessions") == 1 for item in status["databases"])
    assert digests(root) == before
    with DataDirectoryLock(root) as lock:
        runtime = prepare_runtime(root, migrate=True, lock=lock)
        assert "FIXTURE-" not in json.dumps(runtime.public_data())
        assert "FIXTURE-" not in json.dumps(export_runtime_status(root))


def test_mutations_require_main_owned_correct_lock(tmp_path):
    target = tmp_path / "target"
    with pytest.raises(ValueError):
        prepare_runtime(target)
    assert not target.exists()
    with DataDirectoryLock(tmp_path / "wrong") as wrong:
        with pytest.raises(ValueError):
            prepare_runtime(target, lock=wrong)
    with DataDirectoryLock(target) as released:
        result = prepare_runtime(target, lock=released)
    with pytest.raises(ValueError):
        select_dataset(target, result.dataset_id, lock=released)


def test_invalid_manifest_never_resets_or_creates_another_dataset(tmp_path):
    root = tmp_path / "target"
    with DataDirectoryLock(root) as lock:
        prepare_runtime(root, lock=lock)
        manifest = root / MANIFEST_NAME
        manifest.write_bytes(b'{"broken":true}')
        before = tuple((root / "datasets").iterdir())
        with pytest.raises(RuntimePreparationError):
            prepare_runtime(root, lock=lock)
        assert manifest.read_bytes() == b'{"broken":true}'
        assert tuple((root / "datasets").iterdir()) == before


def test_incomplete_selected_dataset_fails_without_replacing_manifest(tmp_path):
    root = tmp_path / "target"
    with DataDirectoryLock(root) as lock:
        runtime = prepare_runtime(root, lock=lock)
        original = (root / MANIFEST_NAME).read_bytes()
        runtime.paths.players_database.unlink()
        with pytest.raises(RuntimePreparationError):
            prepare_runtime(root, lock=lock)
        assert (root / MANIFEST_NAME).read_bytes() == original


@pytest.mark.parametrize("operation", ["rollback", "invalid_selection", "inactive_without_source", "nonbool_migrate"])
def test_invalid_operations_leave_manifest_unchanged(tmp_path, operation):
    root = tmp_path / "target"
    with DataDirectoryLock(root) as lock:
        prepare_runtime(root, lock=lock)
        original = (root / MANIFEST_NAME).read_bytes()
        with pytest.raises((RuntimePreparationError, ValueError, TypeError)):
            if operation == "rollback":
                rollback_dataset(root, lock=lock)
            elif operation == "invalid_selection":
                select_dataset(root, "../outside", lock=lock)
            elif operation == "inactive_without_source":
                prepare_runtime(root, activate=False, lock=lock)
            else:
                prepare_runtime(root, migrate="yes", lock=lock)
        assert (root / MANIFEST_NAME).read_bytes() == original


def test_manifest_temporary_collision_is_not_deleted(tmp_path, monkeypatch):
    root = tmp_path / "target"
    identifier = "00000000-0000-4000-8000-000000000001"
    with DataDirectoryLock(root):
        temporary = root / (".active-dataset-" + identifier + ".tmp")
        temporary.write_bytes(b"unrelated-existing-file")
        monkeypatch.setattr(save_runtime.uuid, "uuid4", lambda: identifier)
        with pytest.raises(FileExistsError):
            save_runtime._publish_manifest(root, {"version": 1}, None)
        assert temporary.read_bytes() == b"unrelated-existing-file"
        assert not (root / MANIFEST_NAME).exists()


def test_managed_future_schema_does_not_rewrite_manifest_or_create_dataset(tmp_path):
    root = tmp_path / "target"
    with DataDirectoryLock(root) as lock:
        result = prepare_runtime(root, lock=lock)
        raw = (root / MANIFEST_NAME).read_bytes()
        with sqlite3.connect(result.paths.players_database) as connection:
            connection.execute("PRAGMA user_version=2")
        original_database = result.paths.players_database.read_bytes()
        with pytest.raises(UnsupportedSchemaError):
            prepare_runtime(root, migrate=True, lock=lock)
        assert (root / MANIFEST_NAME).read_bytes() == raw
        assert result.paths.players_database.read_bytes() == original_database
        assert len(tuple((root / "datasets").iterdir())) == 1
