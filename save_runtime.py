"""Managed save startup and explicit, non-merging imports.

Main owns DataDirectoryLock(root) for the entire lifetime of all open stores.
prepare_runtime never acquires/releases it and never binds process paths. Only
after status == 'ready' should main call configure_paths(result.paths). Default
legacy discovery is read-only and requires an explicit migrate=True retry.

Imports retain original files, immutable online backups and failed datasets.
The main DB, WAL and rollback-journal stat signatures and DB filename set must
remain stable throughout copying and schema initialization. SHM reader locks are
excluded because read-only SQLite connections can update that coordination file.
Legacy writers must be stopped for import: stat comparison detects observed
writes, but cannot prevent a historical, non-cooperating writer from resuming
after the final check. Never interpret the lock as protection from such binaries.

Selection/rollback change only the next startup pointer, never configured paths.
No function inspects real saves until explicitly called. Status and exceptions
contain metadata/counts only; database rows and SQLite diagnostic text stay local.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
from typing import Any
import uuid

from app_paths import AppPaths, SUPPORTED_SCHEMA_VERSION, RuntimeNotPreparedError, current_paths, resolve_data_dir
from save_data import DataDirectoryLock, SaveDataError, UnsupportedSchemaError, ensure_supported_schema, online_backup


MANIFEST_NAME = "active-dataset.json"
MANIFEST_VERSION = 1


class RuntimePreparationError(SaveDataError):
    def __init__(self, status: str, *, dataset_id: str | None = None, backup_dir: Path | None = None):
        super().__init__("Save runtime preparation failed: " + status + "; original databases and manifest were preserved.")
        self.status = status
        self.dataset_id = dataset_id
        self.backup_dir = backup_dir


@dataclass(frozen=True)
class RuntimeStatus:
    status: str
    root: Path
    paths: AppPaths | None = None
    reason: str = ""
    databases: tuple[dict[str, Any], ...] = ()
    datasets: tuple[str, ...] = ()
    backup_dir: Path | None = None
    manifest_generation: int = 0
    legacy_roots: tuple[dict[str, Any], ...] = ()

    @property
    def dataset_id(self) -> str | None:
        return self.paths.dataset_id if self.paths is not None else None

    def public_data(self) -> dict[str, Any]:
        return {
            "status": self.status, "root": str(self.root), "dataset_id": self.dataset_id,
            "data_dir": str(self.paths.data_dir) if self.paths else None,
            "tasks_database": str(self.paths.tasks_database) if self.paths else None,
            "players_database": str(self.paths.players_database) if self.paths else None,
            "reason": self.reason, "databases": list(self.databases), "datasets": list(self.datasets),
            "backup_dir": str(self.backup_dir) if self.backup_dir else None,
            "manifest_generation": self.manifest_generation,
            "requires_confirmation": self.status == "legacy_import_required",
            "legacy_roots": list(self.legacy_roots),
        }


def _plain(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        raise RuntimePreparationError("linked_save_path")


def _root(value: str | os.PathLike[str] | None) -> Path:
    root = resolve_data_dir(value)
    _plain(root)
    return root


def _held(root: Path, lock: DataDirectoryLock | None) -> None:
    if not isinstance(lock, DataDirectoryLock) or not lock.held or lock.data_dir.resolve() != root.resolve():
        raise ValueError("Main must hold DataDirectoryLock for this root for the entire runtime lifetime.")


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    _plain(path)
    if path.stat().st_size > 65536:
        raise RuntimePreparationError("invalid_manifest")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError):
        raise RuntimePreparationError("invalid_manifest") from None
    if type(value) is not dict:
        raise RuntimePreparationError("invalid_manifest")
    return value, raw


def _manifest(root: Path) -> tuple[dict[str, Any], bytes] | None:
    path = root / MANIFEST_NAME
    _plain(path)
    if not path.exists():
        return None
    value, raw = _read_json(path)
    if type(value.get("version")) is int and value["version"] > MANIFEST_VERSION:
        raise UnsupportedSchemaError("Save manifest is newer than this application supports.")
    if set(value) != {"version", "generation", "active_dataset", "previous_dataset"}:
        raise RuntimePreparationError("invalid_manifest")
    if type(value["version"]) is not int or value["version"] != MANIFEST_VERSION:
        raise RuntimePreparationError("invalid_manifest")
    if type(value["generation"]) is not int or not 1 <= value["generation"] <= 2**63 - 1:
        raise RuntimePreparationError("invalid_manifest")
    try:
        AppPaths(root, value["active_dataset"])
        if value["previous_dataset"] is not None:
            AppPaths(root, value["previous_dataset"])
    except ValueError:
        raise RuntimePreparationError("invalid_manifest") from None
    return value, raw


def _collection(directory: Path) -> tuple[Path, ...]:
    _plain(directory)
    players = directory / "players"
    _plain(players)
    result = []
    candidates = [directory / "tasks.sqlite3", directory / "players.sqlite3"]
    if players.is_dir():
        candidates.extend(sorted(players.glob("*.sqlite3")))
    for candidate in candidates:
        _plain(candidate)
        for suffix in ("-wal", "-shm", "-journal"):
            _plain(Path(str(candidate) + suffix))
        if candidate.exists():
            if not candidate.is_file():
                raise RuntimePreparationError("invalid_database_path")
            result.append(candidate.relative_to(directory))
        elif any(Path(str(candidate) + suffix).exists() for suffix in ("-wal", "-journal")):
            raise RuntimePreparationError("orphan_database_sidecar")
    return tuple(result)


def _signature(directory: Path) -> dict[str, tuple[int, ...]]:
    result = {}
    for relative in _collection(directory):
        for suffix in ("", "-wal", "-journal"):
            path = directory / (str(relative) + suffix)
            try:
                info = path.stat()
            except FileNotFoundError:
                if not suffix:
                    raise RuntimePreparationError("source_changed") from None
                continue
            result[str(relative) + suffix] = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    return result


def _inventories(directory: Path) -> tuple[dict[str, Any], ...]:
    result = []
    for relative in _collection(directory):
        inventory = ensure_supported_schema(directory / relative, SUPPORTED_SCHEMA_VERSION)
        result.append({"database": relative.as_posix(), "integrity": inventory.integrity,
                       "schema_version": inventory.user_version, "counts": inventory.table_counts})
    return tuple(result)


def _dataset_ids(root: Path) -> tuple[str, ...]:
    directory = root / "datasets"
    _plain(directory)
    if not directory.exists():
        return ()
    result = []
    for child in sorted(directory.iterdir()):
        _plain(child)
        try:
            AppPaths(root, child.name)
        except ValueError:
            continue
        if child.is_dir() and (child / "dataset.json").is_file():
            result.append(child.name)
    return tuple(result)


def _dataset(paths: AppPaths) -> tuple[dict[str, Any], ...]:
    _plain(paths.root / "datasets")
    _plain(paths.data_dir)
    try:
        metadata, _raw = _read_json(paths.data_dir / "dataset.json")
    except OSError:
        raise RuntimePreparationError("dataset_incomplete") from None
    version = metadata.get("schema_version")
    if type(version) is int and version > SUPPORTED_SCHEMA_VERSION:
        raise UnsupportedSchemaError("Dataset schema is newer than this application supports.")
    if (type(metadata.get("version")) is not int or metadata["version"] != 1
            or metadata.get("dataset_id") != paths.dataset_id or metadata.get("status") != "ready"
            or type(version) is not int or version != SUPPORTED_SCHEMA_VERSION):
        raise RuntimePreparationError("dataset_incomplete")
    inventories = _inventories(paths.data_dir)
    names = {entry["database"] for entry in inventories}
    if not {"tasks.sqlite3", "players.sqlite3"} <= names:
        raise RuntimePreparationError("dataset_incomplete")
    return inventories


def _write_new(path: Path, raw: bytes) -> None:
    _plain(path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as output:
        output.write(raw)
        output.flush()
        os.fsync(output.fileno())


def _encoded(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _publish_manifest(root: Path, value: dict[str, Any], expected: bytes | None) -> None:
    path = root / MANIFEST_NAME
    _plain(path)
    actual = path.read_bytes() if path.exists() else None
    if actual != expected:
        raise RuntimePreparationError("manifest_changed")
    if expected is not None:
        _write_new(root / "manifest-backups" / (str(uuid.uuid4()) + ".json"), expected)
    temporary = root / (".active-dataset-" + str(uuid.uuid4()) + ".tmp")
    created = False
    try:
        _write_new(temporary, _encoded(value))
        created = True
        actual = path.read_bytes() if path.exists() else None
        if actual != expected:
            raise RuntimePreparationError("manifest_changed")
        os.replace(temporary, path)
    finally:
        if created:
            temporary.unlink(missing_ok=True)


def _next_manifest(dataset_id: str, previous: dict[str, Any] | None) -> dict[str, Any]:
    if previous is not None and previous["generation"] >= 2**63 - 1:
        raise RuntimePreparationError("manifest_generation_exhausted")
    return {"version": MANIFEST_VERSION, "generation": previous["generation"] + 1 if previous else 1,
            "active_dataset": dataset_id, "previous_dataset": previous["active_dataset"] if previous else None}


def _initialize_dataset(paths: AppPaths) -> None:
    from players import PlayerAuthStore
    from storage import TaskStore

    TaskStore(paths.tasks_database)
    PlayerAuthStore(paths.data_dir)
    if paths.player_directory.is_dir():
        for path in sorted(paths.player_directory.glob("*.sqlite3")):
            TaskStore(path)


def _source_directory(root: Path) -> Path:
    manifest = _manifest(root)
    if manifest is None:
        return root
    paths = AppPaths(root, manifest[0]["active_dataset"])
    _dataset(paths)
    return paths.data_dir


def _ready(root: Path, manifest: dict[str, Any], *, reason: str = "", backup_dir: Path | None = None) -> RuntimeStatus:
    paths = AppPaths(root, manifest["active_dataset"])
    inventories = _dataset(paths)
    return RuntimeStatus("ready", root, paths, reason, inventories, _dataset_ids(root), backup_dir, manifest["generation"])


def prepare_runtime(root: str | os.PathLike[str] | None = None, *, migrate: bool = False,
                    source_root: str | os.PathLike[str] | None = None,
                    lock: DataDirectoryLock | None = None, activate: bool = True) -> RuntimeStatus:
    """Create a new dataset or explicitly import the complete SQLite collection.

    source_root imports either an external legacy root or its active managed
    dataset into a fresh independent UUID; there is never a merge. Supplying it
    without migrate=True returns confirmation status. Existing manifests are
    preferred over retained root-level legacy DBs. Incomplete/orphan managed
    directories require explicit selection/recovery, never an automatic reset.
    Failures raise RuntimePreparationError with retained dataset/backup locations.
    UnsupportedSchemaError is raised before any destination DB is opened to write.
    activate=False requires source_root, returns status='imported' and preserves
    the active manifest byte-for-byte until a later explicit select_dataset call.
    """
    target_root = _root(root)
    _held(target_root, lock)
    if type(migrate) is not bool:
        raise TypeError("migrate must be an explicit boolean confirmation.")
    if type(activate) is not bool:
        raise TypeError("activate must be a boolean.")
    if not activate and source_root is None:
        raise ValueError("activate=False requires an explicit source_root.")
    previous = _manifest(target_root)
    if previous is not None and source_root is None:
        return _ready(target_root, previous[0])
    source = _source_directory(_root(source_root)) if source_root is not None else target_root
    before = _signature(source)
    inventories = _inventories(source)
    source_files = _collection(source)
    if source_root is not None and not source_files:
        raise RuntimePreparationError("source_has_no_databases")
    if source_files and not migrate:
        return RuntimeStatus("legacy_import_required", target_root, reason="explicit_import_confirmation_required",
                             databases=inventories, datasets=_dataset_ids(target_root),
                             manifest_generation=previous[0]["generation"] if previous else 0)
    datasets_directory = target_root / "datasets"
    _plain(datasets_directory)
    if not source_files and datasets_directory.exists() and any(datasets_directory.iterdir()):
        return RuntimeStatus("legacy_import_required", target_root, reason="existing_datasets_require_selection",
                             datasets=_dataset_ids(target_root))
    if _signature(source) != before:
        raise RuntimePreparationError("source_changed")
    dataset_id = str(uuid.uuid4())
    paths = AppPaths(target_root, dataset_id)
    backups = target_root / "backups" / dataset_id if source_files else None
    _plain(target_root / "backups")
    try:
        paths.data_dir.mkdir(parents=True, exist_ok=False)
        if source_files:
            for relative in source_files:
                online_backup(source / relative, backups / relative, supported_version=SUPPORTED_SCHEMA_VERSION)
            if _signature(source) != before:
                raise RuntimePreparationError("source_changed")
            for relative in source_files:
                online_backup(backups / relative, paths.data_dir / relative, supported_version=SUPPORTED_SCHEMA_VERSION)
        _initialize_dataset(paths)
        prepared_inventories = _inventories(paths.data_dir)
        if _signature(source) != before:
            raise RuntimePreparationError("source_changed")
        metadata = {"version": 1, "dataset_id": dataset_id, "schema_version": SUPPORTED_SCHEMA_VERSION,
                    "status": "ready", "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        _write_new(paths.data_dir / "dataset.json", _encoded(metadata))
        manifest = _next_manifest(dataset_id, previous[0] if previous else None) if activate else None
        generation = manifest["generation"] if manifest else previous[0]["generation"] if previous else 0
        prepared = RuntimeStatus("ready" if activate else "imported", target_root, paths,
                                 "imported" if source_files else "created", prepared_inventories,
                                 _dataset_ids(target_root), backups, generation)
        if activate:
            _publish_manifest(target_root, manifest, previous[1] if previous else None)
    except UnsupportedSchemaError:
        raise
    except Exception as error:
        reason = error.status if isinstance(error, RuntimePreparationError) else "shadow_import_failed"
        raise RuntimePreparationError(reason, dataset_id=dataset_id, backup_dir=backups) from None
    return prepared


def select_dataset(root: str | os.PathLike[str], dataset_id: str, *, lock: DataDirectoryLock | None = None) -> dict[str, Any]:
    """Schedule a complete compatible dataset for next startup; current IO stays pinned."""
    target_root = _root(root)
    _held(target_root, lock)
    paths = AppPaths(target_root, dataset_id)
    _dataset(paths)
    previous = _manifest(target_root)
    if previous is not None and previous[0]["active_dataset"] == dataset_id:
        return {"status": "scheduled", "dataset_id": dataset_id, "effective": "next_startup",
                "manifest_generation": previous[0]["generation"]}
    manifest = _next_manifest(dataset_id, previous[0] if previous else None)
    try:
        _publish_manifest(target_root, manifest, previous[1] if previous else None)
    except RuntimePreparationError:
        raise
    except OSError:
        raise RuntimePreparationError("manifest_publish_failed") from None
    return {"status": "scheduled", "dataset_id": dataset_id, "effective": "next_startup",
            "manifest_generation": manifest["generation"]}


def rollback_dataset(root: str | os.PathLike[str], *, lock: DataDirectoryLock | None = None) -> dict[str, Any]:
    target_root = _root(root)
    _held(target_root, lock)
    manifest = _manifest(target_root)
    if manifest is None or manifest[0]["previous_dataset"] is None:
        raise RuntimePreparationError("no_previous_dataset")
    return select_dataset(target_root, manifest[0]["previous_dataset"], lock=lock)


def export_runtime_status(root: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Read-only status; no rows, sessions, token values or implicit preparation."""
    target_root = _root(root)
    manifest = _manifest(target_root)
    if manifest is not None:
        result = _ready(target_root, manifest[0]).public_data()
    else:
        inventories = _inventories(target_root)
        datasets = _dataset_ids(target_root)
        reason = "explicit_import_confirmation_required" if inventories else "existing_datasets_require_selection" if datasets else ""
        result = RuntimeStatus("legacy_import_required" if inventories or datasets else "empty", target_root,
            reason=reason, databases=inventories, datasets=datasets).public_data()
    try:
        configured = current_paths()
    except RuntimeNotPreparedError:
        configured = None
    bound_id = configured.dataset_id if configured is not None and configured.root == target_root else None
    result["current_dataset_id"] = bound_id
    result["pending_restart"] = bound_id is not None and bound_id != result["dataset_id"]
    return result
