"""Explicit save-directory primitives; importing this module performs no I/O.

Call add_data_dir_argument/resolve_data_dir once at startup, then hold a
DataDirectoryLock for the entire application's database lifetime. All cooperating
writers must use that lock, including migration. Historical binaries that do not
know this protocol cannot be made to honor it by this module.

migrate_database copies one database into an ABSENT target. It does not merge
databases, upgrade an existing target in place, migrate a whole player directory,
or import browser localStorage. Callers must obtain authorization before using
it on real saves and quiesce legacy writers for a final migration snapshot.
Atomic publication uses a same-directory hard link and fails closed on filesystems
without that facility. Existing targets, even empty ones, are always conflicts.
"""

from __future__ import annotations

import argparse
from contextlib import closing, contextmanager, nullcontext
from dataclasses import dataclass
import math
import os
from pathlib import Path
import sqlite3
import tempfile
import time
from typing import Callable, Iterator, Mapping
import uuid

from default_paths import DefaultPathError, default_data_dir, legacy_candidates


class SaveDataError(RuntimeError):
    """An error whose message contains no database row values."""


class UnsupportedSchemaError(SaveDataError):
    pass


class DataDirectoryBusyError(SaveDataError):
    pass


class MigrationError(SaveDataError):
    def __init__(self, backup_path: Path | None):
        super().__init__("Shadow migration failed; source and target were preserved.")
        self.backup_path = backup_path


@dataclass(frozen=True)
class DatabaseInventory:
    path: Path
    integrity: str
    user_version: int
    table_counts: dict[str, int]


@dataclass(frozen=True)
class MigrationResult:
    status: str
    source: Path
    target: Path
    backup_path: Path | None = None
    reason: str = ""


def _absolute_path(value: str | os.PathLike[str]) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError("Save paths must be absolute and independent of cwd.")
    return Path(os.path.normpath(path))


def resolve_data_dir(
    data_dir: str | os.PathLike[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Resolve without creating anything; explicit --data-dir is the final root.

    Windows defaults use the configured Saved Games Known Folder, independent
    of LOCALAPPDATA, executable and cwd. An explicit environ is self-contained
    for tests; see default_paths.default_data_dir. Discovery is a separate step.
    """
    if data_dir is not None:
        return _absolute_path(data_dir)
    try:
        return default_data_dir(environ=environ)
    except DefaultPathError as error:
        raise SaveDataError(str(error)) from None


def add_data_dir_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--data-dir",
        type=resolve_data_dir,
        default=None,
        help="Absolute save directory; default: Windows Saved Games/EFTTaskAssistant (channel-aware)",
    )


def _version(value: int) -> int:
    if type(value) is not int or not 0 <= value <= 2147483647:
        raise ValueError("Schema versions must be nonnegative SQLite signed integers.")
    return value


def _duration(value: float) -> float:
    if not math.isfinite(value) or value < 0:
        raise ValueError("Timeout must be finite and nonnegative.")
    return value


@contextmanager
def _read_only(path: Path, timeout: float) -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=timeout)) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        yield connection


def _inspect(connection: sqlite3.Connection, path: Path) -> DatabaseInventory:
    checks = connection.execute("PRAGMA integrity_check").fetchall()
    integrity = "ok" if checks == [("ok",)] else "failed"
    user_version = connection.execute("PRAGMA user_version").fetchone()[0]
    names = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    counts = {}
    for (name,) in names:
        quoted_name = '"' + name.replace('"', '""') + '"'
        counts[name] = connection.execute("SELECT COUNT(*) FROM " + quoted_name).fetchone()[0]
    return DatabaseInventory(path, integrity, user_version, counts)


def inventory_database(path: str | os.PathLike[str], *, timeout: float = 10) -> DatabaseInventory:
    """Read a consistent snapshot in mode=ro; return counts, never row contents.

    Missing files are errors and are never created. Integrity errors are reduced
    to 'failed'; raw SQLite error strings and damaged row content are not exposed.
    """
    database_path = _absolute_path(path)
    try:
        with _read_only(database_path, _duration(timeout)) as connection:
            return _inspect(connection, database_path)
    except sqlite3.Error:
        raise SaveDataError("Read-only database inventory failed.") from None


def _check_supported(inventory: DatabaseInventory, supported_version: int) -> None:
    if inventory.integrity != "ok":
        raise SaveDataError("Database integrity check failed.")
    if inventory.user_version > _version(supported_version):
        raise UnsupportedSchemaError("Database schema is newer than this application supports.")


def ensure_supported_schema(path: str | os.PathLike[str], supported_version: int) -> DatabaseInventory:
    """Call before any writable application connection; never downgrades a DB."""
    _version(supported_version)
    inventory = inventory_database(path)
    _check_supported(inventory, supported_version)
    return inventory


class DataDirectoryLock:
    """Process-lifetime advisory lock; keep the lock file, even after release.

    The OS releases the byte/flock lock after process death. The persistent file
    contains only a fixed byte, never a session ID or token. It must not be
    deleted/replaced while another process might hold the lock.
    """

    def __init__(self, data_dir: str | os.PathLike[str], *, timeout: float = 0):
        self.data_dir = _absolute_path(data_dir)
        self.timeout = _duration(timeout)
        self._file = None

    @property
    def held(self) -> bool:
        return self._file is not None

    def acquire(self) -> DataDirectoryLock:
        if self.held:
            raise DataDirectoryBusyError("This lock object already holds a data directory.")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        lock_file = (self.data_dir / ".save-data.lock").open("a+b")
        try:
            if os.fstat(lock_file.fileno()).st_size == 0:
                lock_file.write(b"\0")
                lock_file.flush()
            deadline = time.monotonic() + self.timeout
            while True:
                try:
                    lock_file.seek(0)
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self._file = lock_file
                    return self
                except OSError:
                    if time.monotonic() >= deadline:
                        raise DataDirectoryBusyError("The save directory is locked or unavailable.") from None
                    time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        except BaseException:
            lock_file.close()
            raise

    def release(self) -> None:
        if self._file is None:
            return
        lock_file, self._file = self._file, None
        try:
            lock_file.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            lock_file.close()

    def __enter__(self) -> DataDirectoryLock:
        return self.acquire()

    def __exit__(self, *exception_info: object) -> None:
        self.release()


def _occupied(path: Path) -> bool:
    return any(os.path.lexists(str(path) + suffix) for suffix in ("", "-wal", "-shm", "-journal"))


def _temporary_database(parent: Path) -> Path:
    descriptor, filename = tempfile.mkstemp(prefix=".save-shadow-", suffix=".sqlite3", dir=parent)
    os.close(descriptor)
    return Path(filename)


def _remove_shadow(path: Path) -> None:
    for suffix in ("", "-wal", "-shm", "-journal"):
        Path(str(path) + suffix).unlink(missing_ok=True)


def _publish_absent(shadow: Path, target: Path) -> None:
    if _occupied(target):
        raise FileExistsError("Destination or its SQLite sidecars already exist.")
    with shadow.open("r+b") as database_file:
        os.fsync(database_file.fileno())
    os.link(shadow, target)


def online_backup(
    source: str | os.PathLike[str],
    destination: str | os.PathLike[str],
    *,
    supported_version: int | None = None,
    timeout: float = 10,
) -> DatabaseInventory:
    """SQLite online backup from mode=ro, atomically published without overwrite.

    Handles committed WAL pages via SQLite's backup API, never a raw file copy.
    A read transaction pins the checked source snapshot for the entire backup.
    Only an explicit call creates the destination's parent and temporary file.
    """
    source_path = _absolute_path(source)
    destination_path = _absolute_path(destination)
    _duration(timeout)
    if supported_version is not None:
        _version(supported_version)
    if source_path == destination_path or _occupied(destination_path):
        raise FileExistsError("Backup destination already exists.")
    shadow = None
    try:
        with _read_only(source_path, timeout) as source_connection:
            source_inventory = _inspect(source_connection, source_path)
            if source_inventory.integrity != "ok":
                raise SaveDataError("Source database integrity check failed.")
            if supported_version is not None:
                _check_supported(source_inventory, supported_version)
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shadow = _temporary_database(destination_path.parent)
            deadline = time.monotonic() + timeout

            def check_deadline(status: int, remaining: int, total: int) -> None:
                if status != sqlite3.SQLITE_DONE and time.monotonic() > deadline:
                    raise SaveDataError("Online database backup timed out.")

            with closing(sqlite3.connect(shadow)) as destination_connection:
                source_connection.backup(destination_connection, pages=128, progress=check_deadline, sleep=0.01)
                destination_connection.execute("PRAGMA journal_mode=DELETE")
            backup_inventory = inventory_database(shadow, timeout=timeout)
            if (
                backup_inventory.integrity != "ok"
                or backup_inventory.user_version != source_inventory.user_version
                or backup_inventory.table_counts != source_inventory.table_counts
            ):
                raise SaveDataError("Online database backup verification failed.")
            _publish_absent(shadow, destination_path)
            return DatabaseInventory(
                destination_path, backup_inventory.integrity,
                backup_inventory.user_version, backup_inventory.table_counts,
            )
    except sqlite3.Error:
        raise SaveDataError("Online database backup failed.") from None
    finally:
        if shadow is not None:
            _remove_shadow(shadow)


def migrate_database(
    source: str | os.PathLike[str],
    target: str | os.PathLike[str],
    *,
    supported_version: int,
    target_version: int,
    migrate: Callable[[sqlite3.Connection], None] | None = None,
    lock: DataDirectoryLock | None = None,
) -> MigrationResult:
    """Back up, transform a private shadow, verify, then publish to absent target.

    The backup is retained on success and failure. Callback/version/integrity or
    publication failures discard only the private shadow; they cannot mutate the
    source or an existing target. Callback exceptions are deliberately sanitized.
    This is atomic for ONE database, not for players.sqlite3 plus all player DBs.
    A trusted callback must preserve application data; no semantic merge is done.
    Pass the application's held root-directory lock to avoid acquiring it twice;
    databases in nested player directories may share that same root lock.
    """
    source_path, target_path = _absolute_path(source), _absolute_path(target)
    _version(supported_version)
    _version(target_version)
    if target_version > supported_version:
        raise UnsupportedSchemaError("Requested schema exceeds application support.")
    if source_path == target_path or _occupied(target_path):
        return MigrationResult("conflict", source_path, target_path, reason="target_exists")
    source_inventory = ensure_supported_schema(source_path, supported_version)
    if target_version < source_inventory.user_version:
        raise UnsupportedSchemaError("Schema downgrade is not supported.")
    if lock is not None and (not lock.held or not target_path.parent.is_relative_to(lock.data_dir)):
        raise ValueError("Migration requires the held lock for the target data directory.")
    directory_lock = nullcontext(lock) if lock is not None else DataDirectoryLock(target_path.parent)
    with directory_lock:
        if _occupied(target_path):
            return MigrationResult("conflict", source_path, target_path, reason="target_exists")
        backup_path = None
        shadow = None
        try:
            candidate_backup = target_path.parent / "save-backups" / (uuid.uuid4().hex + ".sqlite3")
            backup_inventory = online_backup(source_path, candidate_backup, supported_version=supported_version)
            backup_path = candidate_backup
            if target_version < backup_inventory.user_version:
                raise UnsupportedSchemaError("Schema downgrade is not supported.")
            shadow = _temporary_database(target_path.parent)
            with _read_only(backup_path, 10) as backup_connection:
                with closing(sqlite3.connect(shadow)) as shadow_connection:
                    backup_connection.backup(shadow_connection)
                    shadow_connection.execute("PRAGMA journal_mode=DELETE")
                    shadow_connection.execute("BEGIN IMMEDIATE")
                    try:
                        shadow_connection.execute("PRAGMA user_version=" + str(target_version))
                        if migrate is not None:
                            migrate(shadow_connection)
                        shadow_connection.commit()
                    except BaseException:
                        shadow_connection.rollback()
                        raise
                    shadow_connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    shadow_connection.execute("PRAGMA journal_mode=DELETE")
            migrated_inventory = ensure_supported_schema(shadow, supported_version)
            if migrated_inventory.user_version != target_version:
                raise SaveDataError("Shadow schema version verification failed.")
            try:
                _publish_absent(shadow, target_path)
            except FileExistsError:
                return MigrationResult("conflict", source_path, target_path, backup_path, "target_appeared")
            return MigrationResult("migrated", source_path, target_path, backup_path)
        except Exception:
            raise MigrationError(backup_path) from None
        finally:
            if shadow is not None:
                _remove_shadow(shadow)
