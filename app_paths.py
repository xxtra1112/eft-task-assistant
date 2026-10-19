"""Explicit process paths. Importing never discovers, creates or migrates saves.

The startup owner prepares a runtime while holding its directory lock, then calls
configure_paths(result.paths) before accessing default databases. Configured
paths are pinned for this process; changing the manifest cannot switch open DBs.
Explicit database paths remain available for isolated tools and tests.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import uuid

from save_data import SaveDataError, UnsupportedSchemaError, resolve_data_dir


SUPPORTED_SCHEMA_VERSION = 1


class RuntimeNotPreparedError(SaveDataError):
    pass


@dataclass(frozen=True)
class AppPaths:
    root: Path
    dataset_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", resolve_data_dir(self.root))
        try:
            canonical = str(uuid.UUID(self.dataset_id))
        except (ValueError, TypeError, AttributeError):
            raise ValueError("Dataset ID must be a canonical UUID.") from None
        if canonical != self.dataset_id:
            raise ValueError("Dataset ID must be a canonical UUID.")

    @property
    def data_dir(self) -> Path:
        return self.root / "datasets" / self.dataset_id

    @property
    def tasks_database(self) -> Path:
        return self.data_dir / "tasks.sqlite3"

    @property
    def players_database(self) -> Path:
        return self.data_dir / "players.sqlite3"

    @property
    def player_directory(self) -> Path:
        return self.data_dir / "players"

    @property
    def log_file(self) -> Path:
        return self.root / "logs" / "app.log"


_configured_paths: AppPaths | None = None


def configure_paths(paths: AppPaths | None) -> None:
    """Bind once per startup; passing None resets an isolated test/application."""
    if paths is not None and not isinstance(paths, AppPaths):
        raise TypeError("Expected prepared AppPaths.")
    global _configured_paths
    if _configured_paths is not None and paths is not None and paths != _configured_paths:
        raise RuntimeNotPreparedError("A running process cannot switch datasets; restart first.")
    _configured_paths = paths


def current_paths() -> AppPaths:
    if _configured_paths is None:
        raise RuntimeNotPreparedError("Prepare the runtime and configure_paths before opening default databases.")
    return _configured_paths


def default_database_path() -> Path:
    return _configured_paths.tasks_database if _configured_paths is not None else resolve_data_dir() / "tasks.sqlite3"


def default_player_root() -> Path:
    return _configured_paths.data_dir if _configured_paths is not None else resolve_data_dir()


def diagnostic_log_path() -> Path:
    root = _configured_paths.root if _configured_paths is not None else resolve_data_dir()
    return root / "logs" / "app.log"


def public_cache_root(fallback: Path | None = None) -> Path:
    if _configured_paths is not None:
        root = _configured_paths.root
    elif fallback is not None:
        root = Path(fallback)
    else:
        root = resolve_data_dir()
    return root / "public-data"


def check_database_schema(path: Path) -> None:
    """Check schema in mode=ro before any writable connection, even on reopen."""
    database = Path(path).absolute()
    if not database.exists():
        return
    try:
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
            connection.execute("PRAGMA query_only=ON")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
    except sqlite3.Error:
        raise SaveDataError("Read-only database schema check failed.") from None
    if version > SUPPORTED_SCHEMA_VERSION:
        raise UnsupportedSchemaError("Database schema is newer than this application supports.")
