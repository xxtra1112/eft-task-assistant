from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from task_requirements import normalize_requirement
from route_storage import MapDrawingStore
from app_paths import SUPPORTED_SCHEMA_VERSION, check_database_schema, current_paths
from app_paths import default_database_path as managed_database_path


GAME_MODES = {"pve", "regular", "pvp-season"}
CATALOG_PROVIDERS = {"Tarkov.dev community JSON API": "tarkov.dev", "eftarkov.com": "eftarkov"}


def catalog_data_provider(source: str, metadata: dict[str, Any]) -> str:
    provider = metadata.get("provider")
    if provider is not None:
        return provider if isinstance(provider, str) and provider in {"tarkov.dev", "eftarkov"} else ""
    return CATALOG_PROVIDERS.get(source, "")


MP133_GUNSMITH_TASK_ID = "5ac23c6186f7741247042bad"
MP133_GUNSMITH_REQUIREMENTS = (
    "改装配件颜色符合任务要求",
    "武器耐久度大于 60",
    "枪膛与弹匣均不装任何子弹",
)


@dataclass(frozen=True)
class Profile:
    id: int
    name: str
    game_mode: str
    season_id: str | None


@dataclass(frozen=True)
class Task:
    id: int
    profile_id: int
    trader: str
    title: str
    objective: str
    item_name: str
    required_count: int | None
    current_count: int
    state: str
    source_task_id: str
    source_url: str
    source_version: str
    requirements: list[dict[str, Any]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_database_path() -> Path:
    return managed_database_path()


def normalize_text(value: str) -> str:
    return "".join(character.casefold() for character in value if character.isalnum())


def _is_mp133_gunsmith_task(source_task_id: str, title: str) -> bool:
    if source_task_id.strip().casefold() == MP133_GUNSMITH_TASK_ID:
        return True
    normalized_title = normalize_text(title)
    is_mp133 = "mp133" in normalized_title
    is_gunsmith = "枪匠" in title.casefold() or "gunsmith" in title.casefold()
    return is_mp133 and is_gunsmith


def _expand_mp133_requirements(
    source_task_id: str,
    title: str,
    requirements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not _is_mp133_gunsmith_task(source_task_id, title) or len(requirements) != 1:
        return requirements
    completed = bool(requirements[0].get("completed", False))
    return [
        normalize_requirement({"text": text, "completed": completed})
        for text in MP133_GUNSMITH_REQUIREMENTS
    ]


def _json_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class TaskStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else current_paths().tasks_database
        check_database_schema(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        self.routes = MapDrawingStore(self._connect)
        self._migrate_source_visits()
        self._restore_tasks_completed_by_screenshot()

    def _migrate_source_visits(self) -> None:
        # Copy, never rewrite legacy rows. The one-time ledger makes unvisiting
        # persistent; reopening must not resurrect a legacy visit.
        with self._connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS source_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
            if connection.execute("SELECT 1 FROM source_migrations WHERE name = 'map-visits-v1'").fetchone():
                return
            for prefix, provider in (("tarkovdev-", "tarkov.dev"), ("eftarkov-", "eftarkov")):
                connection.execute("""INSERT OR IGNORE INTO map_marker_visits (profile_id, map_id, marker_id, visited_at)
                    SELECT profile_id, ? || ':' || map_id, marker_id, visited_at FROM map_marker_visits
                    WHERE instr(map_id, ':') = 0 AND marker_id LIKE ?""", (provider, prefix + "%"))
            connection.execute("INSERT INTO source_migrations VALUES ('map-visits-v1', ?)", (_now(),))

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        check_database_schema(self.path)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _table_names(connection: sqlite3.Connection) -> set[str]:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        return {row[0] for row in rows}

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA foreign_keys = OFF")
            tables = self._table_names(connection)
            if "tasks" in tables:
                columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
                }
                if "profile_id" not in columns:
                    self._migrate_legacy(connection, tables)
                else:
                    self._create_schema(connection)
                    self._ensure_default_profile(connection)
            else:
                self._create_schema(connection)
                self._ensure_default_profile(connection)
            self._ensure_task_source_columns(connection)
            self._ensure_task_requirement_columns(connection)
            self._ensure_catalog_task_columns(connection)
            self._ensure_task_provenance(connection)
            connection.execute("PRAGMA user_version=" + str(SUPPORTED_SCHEMA_VERSION))
            connection.execute("PRAGMA foreign_keys = ON")

    @staticmethod
    def _ensure_task_provenance(connection: sqlite3.Connection) -> None:
        connection.execute("""CREATE TABLE IF NOT EXISTS task_data_provenance (
            task_id INTEGER PRIMARY KEY, provider TEXT NOT NULL,
            snapshot_id INTEGER, evidence TEXT NOT NULL)""")
        rows = connection.execute("""SELECT t.id, t.source_task_id, p.game_mode
            FROM tasks t JOIN profiles p ON p.id=t.profile_id
            LEFT JOIN task_data_provenance d ON d.task_id=t.id
            WHERE d.task_id IS NULL AND t.source_task_id!=''""").fetchall()
        for task in rows:
            candidates = connection.execute("""SELECT cs.id, cs.source, cs.metadata_json
                FROM catalog_tasks ct JOIN catalog_snapshots cs ON cs.id=ct.snapshot_id
                WHERE ct.source_task_id=? AND cs.game_mode=? ORDER BY cs.id DESC""",
                (task["source_task_id"], task["game_mode"])).fetchall()
            origins = {}
            for candidate in candidates:
                provider = catalog_data_provider(candidate["source"], json.loads(candidate["metadata_json"] or "{}"))
                if provider:
                    origins.setdefault(provider, candidate["id"])
            if len(origins) == 1:
                provider, snapshot = next(iter(origins.items()))
                connection.execute("INSERT INTO task_data_provenance VALUES (?,?,?,?)",
                    (task["id"], provider, snapshot, "exact task ID and mode; sole catalog provider"))

    def task_data_provider(self, task_id: int) -> str:
        with self._connect() as connection:
            self._ensure_task_provenance(connection)
            row = connection.execute("SELECT provider FROM task_data_provenance WHERE task_id=?", (task_id,)).fetchone()
        return str(row["provider"]) if row else ""

    def task_catalog_history(self, task_id: int) -> list[dict[str, Any]]:
        provider = self.task_data_provider(task_id)
        if not provider:
            return []
        clause, parameters = self._catalog_source_clause(provider)
        with self._connect() as connection:
            task = connection.execute("""SELECT t.source_task_id, p.game_mode, d.snapshot_id
                FROM tasks t JOIN profiles p ON p.id=t.profile_id
                JOIN task_data_provenance d ON d.task_id=t.id WHERE t.id=?""", (task_id,)).fetchone()
            if task is None:
                return []
            snapshots = connection.execute(
                "SELECT id FROM catalog_snapshots WHERE game_mode=?" + clause +
                " ORDER BY (id=?) DESC, id DESC", (task["game_mode"], *parameters, task["snapshot_id"]),
            ).fetchall()
        return [entry for snapshot in snapshots
                if (entry := self.get_catalog_task(snapshot["id"], task["source_task_id"])) is not None]

    def record_task_data_provider(self, task_id: int, provider: str, snapshot_id: int) -> None:
        if provider not in {"tarkov.dev", "eftarkov"}:
            raise ValueError("未知任务资料来源。")
        with self._connect() as connection:
            task = connection.execute("""SELECT t.source_task_id, p.game_mode FROM tasks t
                JOIN profiles p ON p.id=t.profile_id WHERE t.id=?""", (task_id,)).fetchone()
            snapshot = connection.execute("SELECT source, metadata_json, game_mode FROM catalog_snapshots WHERE id=?", (snapshot_id,)).fetchone()
            canonical = connection.execute("SELECT 1 FROM catalog_tasks WHERE snapshot_id=? AND source_task_id=?",
                                           (snapshot_id, task["source_task_id"] if task else "")).fetchone()
            if (not task or not snapshot or not canonical or task["game_mode"] != snapshot["game_mode"]
                    or catalog_data_provider(snapshot["source"], json.loads(snapshot["metadata_json"] or "{}")) != provider):
                raise ValueError("任务来源必须与稳定任务 ID、模式和目录一致。")
            connection.execute("""INSERT INTO task_data_provenance VALUES (?,?,?,?)
                ON CONFLICT(task_id) DO UPDATE SET provider=excluded.provider,
                snapshot_id=excluded.snapshot_id,evidence=excluded.evidence""",
                (task_id, provider, snapshot_id, "explicit catalog import"))

    def _restore_tasks_completed_by_screenshot(self) -> None:
        now = _now()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT task.id, task.title
                FROM tasks AS task
                WHERE task.state = 'complete'
                    AND (
                        SELECT event.event_type
                        FROM events AS event
                        WHERE event.task_id = task.id
                            AND event.event_type IN (
                                'marked_complete',
                                'task_completed_by_screenshot',
                                'task_seen_again',
                                'count_incremented'
                            )
                        ORDER BY event.id DESC
                        LIMIT 1
                    ) = 'task_completed_by_screenshot'
                """
            ).fetchall()
            for row in rows:
                connection.execute(
                    "UPDATE tasks SET state = 'active', updated_at = ? WHERE id = ?",
                    (now, row["id"]),
                )
                connection.execute(
                    "INSERT INTO events (task_id, event_type, detail, created_at) VALUES (?, 'task_restored_after_screenshot_policy_change', ?, ?)",
                    (row["id"], row["title"], now),
                )

    def _create_schema(self, connection: sqlite3.Connection) -> None:
        statements = (
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                game_mode TEXT NOT NULL CHECK (game_mode IN ('pve', 'regular', 'pvp-season')),
                season_id TEXT,
                created_at TEXT NOT NULL,
                UNIQUE (name, game_mode, season_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                trader TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                objective TEXT NOT NULL DEFAULT '',
                item_name TEXT NOT NULL DEFAULT '',
                required_count INTEGER,
                current_count INTEGER NOT NULL DEFAULT 0,
                state TEXT NOT NULL DEFAULT 'active'
                    CHECK (state IN ('active', 'missing_review', 'complete')),
                source_task_id TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                source_version TEXT NOT NULL DEFAULT '',
                requirements_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (profile_id, trader, title)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
                event_type TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS catalog_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_url TEXT NOT NULL DEFAULT '',
                game_mode TEXT NOT NULL CHECK (game_mode IN ('pve', 'regular', 'pvp-season')),
                source_version TEXT NOT NULL DEFAULT '',
                game_build TEXT,
                verification_status TEXT NOT NULL DEFAULT 'unverified'
                    CHECK (verification_status IN ('unverified', 'verified', 'stale')),
                source_updated_at TEXT,
                fetched_at TEXT NOT NULL,
                content_sha256 TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}'
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS catalog_tasks (
                snapshot_id INTEGER NOT NULL REFERENCES catalog_snapshots(id) ON DELETE CASCADE,
                source_task_id TEXT NOT NULL,
                trader TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                source_url TEXT NOT NULL DEFAULT '',
                objectives_json TEXT NOT NULL DEFAULT '[]',
                prerequisites_json TEXT NOT NULL DEFAULT '[]',
                key_requirements_json TEXT NOT NULL DEFAULT '[]',
                map_points_json TEXT NOT NULL DEFAULT '[]',
                details_loaded INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (snapshot_id, source_task_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS map_waypoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                map_id TEXT NOT NULL,
                floor_key TEXT NOT NULL,
                x REAL NOT NULL,
                y REAL NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                key_name TEXT NOT NULL DEFAULT '',
                key_acquisition TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS map_marker_visits (
                profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                map_id TEXT NOT NULL,
                marker_id TEXT NOT NULL,
                visited_at TEXT NOT NULL,
                PRIMARY KEY (profile_id, map_id, marker_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS capture_records (
                capture_id TEXT PRIMARY KEY,
                profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                source TEXT NOT NULL DEFAULT 'web',
                created_at TEXT NOT NULL,
                state TEXT NOT NULL,
                error TEXT NOT NULL DEFAULT '',
                jpeg BLOB,
                resolution_json TEXT NOT NULL DEFAULT '{}',
                analysis_json TEXT,
                task_candidates_json TEXT NOT NULL DEFAULT '[]'
            )
            """,
            "CREATE INDEX IF NOT EXISTS capture_records_created_idx ON capture_records(created_at)",
            """
            CREATE TABLE IF NOT EXISTS pending_task_candidates (
                profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                source_task_id TEXT NOT NULL,
                candidate_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (profile_id, source_task_id)
            )
            """,
        )
        for statement in statements:
            connection.execute(statement)

    @staticmethod
    def _ensure_task_source_columns(connection: sqlite3.Connection) -> None:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(tasks)").fetchall()}
        for name in ("source_task_id", "source_url", "source_version"):
            if name not in columns:
                connection.execute(
                    f"ALTER TABLE tasks ADD COLUMN {name} TEXT NOT NULL DEFAULT ''"
                )

    @staticmethod
    def _ensure_task_requirement_columns(connection: sqlite3.Connection) -> None:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(tasks)").fetchall()}
        if "requirements_json" not in columns:
            connection.execute(
                "ALTER TABLE tasks ADD COLUMN requirements_json TEXT NOT NULL DEFAULT '[]'"
            )
        rows = connection.execute(
            "SELECT id, title, source_task_id, objective, required_count, current_count, requirements_json FROM tasks"
        ).fetchall()
        for row in rows:
            try:
                stored_requirements = json.loads(row["requirements_json"] or "[]")
            except (TypeError, json.JSONDecodeError):
                stored_requirements = []
            existing = stored_requirements
            if not isinstance(existing, list):
                existing = []
            if not existing:
                lines = [line.strip() for line in str(row["objective"] or "").splitlines() if line.strip()]
                required = row["required_count"]
                if required is not None:
                    if required <= 0 or len(lines) < required:
                        lines = []
                    else:
                        lines = lines[:required]
                completed_count = min(max(int(row["current_count"] or 0), 0), len(lines))
                existing = [
                    normalize_requirement({"text": line, "completed": index < completed_count})
                    for index, line in enumerate(lines)
                ]
                if not existing and _is_mp133_gunsmith_task(row["source_task_id"], row["title"]):
                    existing = [normalize_requirement({
                        "text": "MP-133 枪匠规格",
                        "completed": bool(row["current_count"]),
                    })]

            requirements = _expand_mp133_requirements(
                row["source_task_id"], row["title"], existing
            )
            requirements = [normalize_requirement(item) for item in requirements if isinstance(item, dict)]
            if requirements:
                required_count = sum(not item.get("optional", False) for item in requirements)
                completed_count = sum(
                    bool(item.get("completed")) and not item.get("optional", False)
                    for item in requirements
                )
                if (
                    requirements != stored_requirements
                    or row["required_count"] != required_count
                    or row["current_count"] != completed_count
                ):
                    connection.execute(
                        "UPDATE tasks SET requirements_json = ?, required_count = ?, current_count = ? WHERE id = ?",
                        (_json_value(requirements), required_count, completed_count, row["id"]),
                    )

    @staticmethod
    def _ensure_catalog_task_columns(connection: sqlite3.Connection) -> None:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(catalog_tasks)").fetchall()}
        definitions = {
            "key_requirements_json": "TEXT NOT NULL DEFAULT '[]'",
            "map_points_json": "TEXT NOT NULL DEFAULT '[]'",
            "map_ids_json": "TEXT NOT NULL DEFAULT '[]'",
            "details_loaded": "INTEGER NOT NULL DEFAULT 0",
        }
        for name, definition in definitions.items():
            if name not in columns:
                connection.execute(f"ALTER TABLE catalog_tasks ADD COLUMN {name} {definition}")

    def _migrate_legacy(self, connection: sqlite3.Connection, tables: set[str]) -> None:
        connection.execute("BEGIN IMMEDIATE")
        try:
            if "events" in tables:
                connection.execute("ALTER TABLE events RENAME TO _legacy_events")
            connection.execute("ALTER TABLE tasks RENAME TO _legacy_tasks")
            self._create_schema(connection)
            profile_id = self._ensure_default_profile(connection)
            connection.execute(
                """
                INSERT INTO tasks (
                    id, profile_id, trader, title, objective, item_name,
                    required_count, current_count, state, created_at, updated_at
                )
                SELECT id, ?, trader, title, objective, item_name,
                       required_count, current_count, state, created_at, updated_at
                FROM _legacy_tasks
                """,
                (profile_id,),
            )
            if "events" in tables:
                connection.execute(
                    """
                    INSERT INTO events (id, task_id, event_type, detail, created_at)
                    SELECT id, task_id, event_type, detail, created_at FROM _legacy_events
                    """
                )
                connection.execute("DROP TABLE _legacy_events")
            connection.execute("DROP TABLE _legacy_tasks")
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    @staticmethod
    def _ensure_default_profile(connection: sqlite3.Connection) -> int:
        row = connection.execute(
            "SELECT id FROM profiles WHERE game_mode = 'pve' ORDER BY id LIMIT 1"
        ).fetchone()
        if row:
            return int(row["id"])
        now = _now()
        cursor = connection.execute(
            "INSERT INTO profiles (name, game_mode, season_id, created_at) VALUES (?, 'pve', NULL, ?)",
            ("PvE 默认档", now),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _profile(row: sqlite3.Row) -> Profile:
        return Profile(
            id=row["id"],
            name=row["name"],
            game_mode=row["game_mode"],
            season_id=row["season_id"],
        )

    @staticmethod
    def _task(row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"],
            profile_id=row["profile_id"],
            trader=row["trader"],
            title=row["title"],
            objective=row["objective"],
            item_name=row["item_name"],
            required_count=row["required_count"],
            current_count=row["current_count"],
            state=row["state"],
            source_task_id=row["source_task_id"],
            source_url=row["source_url"],
            source_version=row["source_version"],
            requirements=json.loads(row["requirements_json"] or "[]"),
        )

    def list_profiles(self) -> list[Profile]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM profiles ORDER BY CASE game_mode WHEN 'pve' THEN 0 WHEN 'regular' THEN 1 ELSE 2 END, name"
            ).fetchall()
        return [self._profile(row) for row in rows]

    def get_app_setting(self, key: str, default: str | None = None) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT setting_value FROM app_settings WHERE setting_key = ?", (key,)
            ).fetchone()
        return str(row["setting_value"]) if row is not None else default

    def set_app_setting(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?)
                ON CONFLICT (setting_key) DO UPDATE SET setting_value = excluded.setting_value
                """,
                (key, str(value)),
            )

    def save_capture_record(self, capture: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO capture_records (
                    capture_id, profile_id, source, created_at, state, error, jpeg,
                    resolution_json, analysis_json, task_candidates_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (capture_id) DO UPDATE SET
                    profile_id = excluded.profile_id,
                    source = excluded.source,
                    created_at = excluded.created_at,
                    state = excluded.state,
                    error = excluded.error,
                    jpeg = excluded.jpeg,
                    resolution_json = excluded.resolution_json,
                    analysis_json = excluded.analysis_json,
                    task_candidates_json = excluded.task_candidates_json
                """,
                (
                    str(capture["id"]),
                    int(capture["profile_id"]),
                    str(capture.get("source", "web")),
                    str(capture["created_at"]),
                    str(capture["state"]),
                    str(capture.get("error", "")),
                    capture.get("jpeg"),
                    _json_value(capture.get("resolution") or {}),
                    _json_value(capture["analysis"]) if capture.get("analysis") is not None else None,
                    _json_value(capture.get("task_candidates") or []),
                ),
            )

    def save_pending_task_candidates(self, candidates: list[dict[str, Any]]) -> None:
        now = _now()
        with self._connect() as connection:
            for candidate in candidates:
                profile_id = int(candidate.get("profile_id", 0))
                source_task_id = str(candidate.get("source_task_id", ""))
                if profile_id <= 0 or not source_task_id:
                    continue
                row = connection.execute(
                    "SELECT candidate_json FROM pending_task_candidates WHERE profile_id = ? AND source_task_id = ?",
                    (profile_id, source_task_id),
                ).fetchone()
                should_refresh = row is None
                if row is not None:
                    try:
                        existing = json.loads(row["candidate_json"])
                    except (TypeError, json.JSONDecodeError):
                        existing = {}
                    should_refresh = existing.get("details_status") == "error"
                if should_refresh:
                    connection.execute(
                        """
                        INSERT INTO pending_task_candidates (
                            profile_id, source_task_id, candidate_json, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT (profile_id, source_task_id) DO UPDATE SET
                            candidate_json = excluded.candidate_json,
                            updated_at = excluded.updated_at
                        """,
                        (profile_id, source_task_id, _json_value(candidate), now, now),
                    )

    def list_pending_task_candidates(self, profile_id: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT source_task_id, candidate_json FROM pending_task_candidates
                WHERE profile_id = ? ORDER BY created_at DESC, source_task_id
                """,
                (profile_id,),
            ).fetchall()
        candidates = []
        for row in rows:
            try:
                candidate = json.loads(row["candidate_json"])
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(candidate, dict):
                continue
            candidate.setdefault("profile_id", profile_id)
            candidate.setdefault("source_task_id", str(row["source_task_id"]))
            candidates.append(candidate)
        return candidates

    def update_pending_task_candidate(
        self, profile_id: int, source_task_id: str, updates: dict[str, Any]
    ) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT candidate_json FROM pending_task_candidates WHERE profile_id = ? AND source_task_id = ?",
                (profile_id, source_task_id),
            ).fetchone()
            if row is None:
                return False
            try:
                candidate = json.loads(row["candidate_json"])
            except (TypeError, json.JSONDecodeError):
                candidate = {}
            if not isinstance(candidate, dict):
                candidate = {}
            candidate.update(updates)
            connection.execute(
                """
                UPDATE pending_task_candidates SET candidate_json = ?, updated_at = ?
                WHERE profile_id = ? AND source_task_id = ?
                """,
                (_json_value(candidate), _now(), profile_id, source_task_id),
            )
        return True

    def delete_pending_task_candidate(self, profile_id: int, source_task_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM pending_task_candidates WHERE profile_id = ? AND source_task_id = ?",
                (profile_id, source_task_id),
            )
        return cursor.rowcount > 0

    def list_capture_records(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM capture_records
                ORDER BY created_at DESC, capture_id DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()

        records = []
        for row in reversed(rows):
            try:
                resolution = json.loads(row["resolution_json"] or "{}")
            except (TypeError, json.JSONDecodeError):
                resolution = {}
            try:
                analysis = json.loads(row["analysis_json"]) if row["analysis_json"] else None
            except (TypeError, json.JSONDecodeError):
                analysis = None
            try:
                task_candidates = json.loads(row["task_candidates_json"] or "[]")
            except (TypeError, json.JSONDecodeError):
                task_candidates = []
            records.append(
                {
                    "id": str(row["capture_id"]),
                    "profile_id": int(row["profile_id"]),
                    "source": str(row["source"]),
                    "created_at": str(row["created_at"]),
                    "state": str(row["state"]),
                    "error": str(row["error"]),
                    "jpeg": bytes(row["jpeg"]) if row["jpeg"] is not None else None,
                    "resolution": resolution if isinstance(resolution, dict) else {},
                    "analysis": analysis if isinstance(analysis, dict) else None,
                    "task_candidates": task_candidates if isinstance(task_candidates, list) else [],
                }
            )
        return records

    def delete_capture_record(self, capture_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM capture_records WHERE capture_id = ?", (capture_id,)
            )
        return cursor.rowcount > 0

    def prune_capture_records(self, limit: int = 10) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM capture_records
                WHERE capture_id NOT IN (
                    SELECT capture_id FROM capture_records
                    ORDER BY created_at DESC, capture_id DESC
                    LIMIT ?
                )
                """,
                (max(1, int(limit)),),
            )
        return cursor.rowcount

    def default_profile_id(self) -> int:
        with self._connect() as connection:
            return self._ensure_default_profile(connection)

    def create_profile(self, name: str, game_mode: str, season_id: str = "") -> Profile:
        name = name.strip()
        season_id = season_id.strip() or None
        if not name:
            raise ValueError("档案名称不能为空")
        if game_mode not in GAME_MODES:
            raise ValueError("未知游戏模式")
        if game_mode == "pvp-season" and not season_id:
            raise ValueError("赛季模式需要填写赛季编号")
        if game_mode != "pvp-season":
            season_id = None
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO profiles (name, game_mode, season_id, created_at) VALUES (?, ?, ?, ?)",
                (name, game_mode, season_id, _now()),
            )
            row = connection.execute(
                "SELECT * FROM profiles WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return self._profile(row)

    def rename_profile(self, profile_id: int, name: str) -> Profile:
        normalized_name = name.strip()
        if not normalized_name or len(normalized_name) > 48:
            raise ValueError("档案名称需为 1–48 个字符。")
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE profiles SET name = ? WHERE id = ?",
                (normalized_name, profile_id),
            )
            if not cursor.rowcount:
                raise ValueError("找不到要命名的档案。")
            row = connection.execute(
                "SELECT * FROM profiles WHERE id = ?", (profile_id,)
            ).fetchone()
        return self._profile(row)

    def list_tasks(self, profile_id: int | None = None) -> list[Task]:
        with self._connect() as connection:
            if profile_id is None:
                rows = connection.execute(
                    "SELECT * FROM tasks ORDER BY CASE state WHEN 'active' THEN 0 WHEN 'missing_review' THEN 1 ELSE 2 END, trader, title"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM tasks WHERE profile_id = ? ORDER BY CASE state WHEN 'active' THEN 0 WHEN 'missing_review' THEN 1 ELSE 2 END, trader, title",
                    (profile_id,),
                ).fetchall()
        return [self._task(row) for row in rows]

    def restore_task_snapshots(
        self, snapshots: list[dict[str, Any]], profile_id: int
    ) -> list[Task]:
        if len(snapshots) > 1000:
            raise ValueError("一次最多撤回 1000 个任务。")
        prepared: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        seen_names: set[tuple[str, str]] = set()
        for snapshot in snapshots:
            if not isinstance(snapshot, dict):
                raise ValueError("任务撤回数据无效。")
            try:
                task_id = int(snapshot.get("id"))
                required_count = snapshot.get("required_count")
                required_count = None if required_count is None else int(required_count)
                current_count = int(snapshot.get("current_count", 0))
            except (TypeError, ValueError) as error:
                raise ValueError("任务撤回数据中的编号或进度无效。") from error
            trader = str(snapshot.get("trader", "")).strip()
            title = str(snapshot.get("title", "")).strip()
            task_state = str(snapshot.get("state", "active"))
            requirements = snapshot.get("requirements", [])
            if (
                task_id <= 0
                or not title
                or len(title) > 500
                or len(trader) > 200
                or task_state not in {"active", "missing_review", "complete"}
                or required_count is not None and not 0 <= required_count <= 1000000
                or not 0 <= current_count <= 1000000
                or not isinstance(requirements, list)
                or len(requirements) > 250
            ):
                raise ValueError("任务撤回数据超出允许范围。")
            if any(
                not isinstance(requirement, dict)
                or not str(requirement.get("text", "")).strip()
                or len(str(requirement.get("text", ""))) > 2000
                for requirement in requirements
            ):
                raise ValueError("任务要求的撤回数据无效。")
            name_key = (trader.casefold(), title.casefold())
            if task_id in seen_ids or name_key in seen_names:
                raise ValueError("任务撤回数据包含重复任务。")
            seen_ids.add(task_id)
            seen_names.add(name_key)
            prepared.append(
                {
                    "id": task_id,
                    "profile_id": profile_id,
                    "trader": trader,
                    "title": title,
                    "objective": str(snapshot.get("objective", ""))[:20000],
                    "item_name": str(snapshot.get("item_name", ""))[:2000],
                    "required_count": required_count,
                    "current_count": current_count,
                    "state": task_state,
                    "source_task_id": str(snapshot.get("source_task_id", ""))[:120],
                    "source_url": str(snapshot.get("source_url", ""))[:2000],
                    "source_version": str(snapshot.get("source_version", ""))[:120],
                    "requirements_json": _json_value(requirements),
                }
            )

        restored: list[Task] = []
        now = _now()
        with self._connect() as connection:
            for snapshot in prepared:
                existing_id = connection.execute(
                    "SELECT profile_id FROM tasks WHERE id = ?", (snapshot["id"],)
                ).fetchone()
                if existing_id is not None and int(existing_id["profile_id"]) != profile_id:
                    raise ValueError("任务属于其他档案，无法撤回。")
                duplicate = connection.execute(
                    "SELECT id FROM tasks WHERE profile_id = ? AND trader = ? AND title = ? AND id <> ?",
                    (profile_id, snapshot["trader"], snapshot["title"], snapshot["id"]),
                ).fetchone()
                if duplicate is not None:
                    raise ValueError(f"“{snapshot['title']}”已存在，无法撤回此记录。")
                connection.execute(
                    """
                    INSERT INTO tasks (
                        id, profile_id, trader, title, objective, item_name, required_count,
                        current_count, state, source_task_id, source_url, source_version,
                        requirements_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        profile_id = excluded.profile_id,
                        trader = excluded.trader,
                        title = excluded.title,
                        objective = excluded.objective,
                        item_name = excluded.item_name,
                        required_count = excluded.required_count,
                        current_count = excluded.current_count,
                        state = excluded.state,
                        source_task_id = excluded.source_task_id,
                        source_url = excluded.source_url,
                        source_version = excluded.source_version,
                        requirements_json = excluded.requirements_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        snapshot["id"], snapshot["profile_id"], snapshot["trader"], snapshot["title"],
                        snapshot["objective"], snapshot["item_name"], snapshot["required_count"],
                        snapshot["current_count"], snapshot["state"], snapshot["source_task_id"],
                        snapshot["source_url"], snapshot["source_version"], snapshot["requirements_json"],
                        now, now,
                    ),
                )
                connection.execute(
                    "INSERT INTO events (task_id, event_type, detail, created_at) VALUES (?, 'task_restored', ?, ?)",
                    (snapshot["id"], snapshot["title"], now),
                )
                row = connection.execute(
                    "SELECT * FROM tasks WHERE id = ? AND profile_id = ?",
                    (snapshot["id"], profile_id),
                ).fetchone()
                restored.append(self._task(row))
        return restored

    def add_task(
        self,
        trader: str,
        title: str,
        objective: str = "",
        item_name: str = "",
        required_count: int | None = None,
        profile_id: int | None = None,
        source_task_id: str = "",
        source_url: str = "",
        source_version: str = "",
        requirements: list[dict[str, Any]] | None = None,
    ) -> Task:
        title = title.strip()
        trader = trader.strip()
        if not title:
            raise ValueError("任务名称不能为空")
        if requirements is None:
            requirement_lines = [line.strip() for line in objective.splitlines() if line.strip()]
            if required_count is None:
                requirements = [{"text": line, "completed": False} for line in requirement_lines]
            elif 0 < required_count <= len(requirement_lines):
                requirements = [
                    {"text": line, "completed": False}
                    for line in requirement_lines[:required_count]
                ]
            else:
                requirements = []
        normalized_requirements = [
            normalize_requirement(item)
            for item in requirements
            if isinstance(item, dict) and str(item.get("text", "")).strip()
        ]
        normalized_requirements = _expand_mp133_requirements(
            source_task_id, title, normalized_requirements
        )
        if normalized_requirements:
            required_count = sum(not item.get("optional", False) for item in normalized_requirements)
        profile_id = profile_id or self.default_profile_id()
        now = _now()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT current_count, requirements_json FROM tasks WHERE profile_id = ? AND trader = ? AND title = ?",
                (profile_id, trader, title),
            ).fetchone()
            previous_requirements = []
            if existing is not None:
                try:
                    previous_requirements = json.loads(existing["requirements_json"] or "[]")
                except (TypeError, json.JSONDecodeError):
                    previous_requirements = []
            if not isinstance(previous_requirements, list):
                previous_requirements = []
            previous_requirements = [
                normalize_requirement(item)
                for item in previous_requirements
                if isinstance(item, dict) and str(item.get("text", "")).strip()
            ]
            previous_requirements = _expand_mp133_requirements(
                source_task_id, title, previous_requirements
            )
            if normalized_requirements:
                previous_by_text = {
                    str(item.get("text", "")).strip(): item
                    for item in previous_requirements
                    if isinstance(item, dict)
                }
                previous_count = (
                    min(max(int(existing["current_count"] or 0), 0), len(normalized_requirements))
                    if existing is not None and not previous_requirements
                    else 0
                )
                required_index = 0
                for index, item in enumerate(normalized_requirements):
                    previous = previous_by_text.get(item["text"])
                    if previous is not None:
                        if item.get("target_count"):
                            target_count = int(item["target_count"])
                            previous_count_for_item = previous.get(
                                "current_count", target_count if previous.get("completed") else 0
                            )
                            item["current_count"] = min(max(int(previous_count_for_item), 0), target_count)
                            item["completed"] = item["current_count"] >= target_count
                        else:
                            item["completed"] = bool(previous.get("completed", False))
                    elif not item.get("optional", False) and required_index < previous_count:
                        item["completed"] = True
                        if item.get("target_count"):
                            item["current_count"] = int(item["target_count"])
                    if not item.get("optional", False):
                        required_index += 1
                current_count = sum(
                    bool(item["completed"]) and not item.get("optional", False)
                    for item in normalized_requirements
                )
            else:
                current_count = int(existing["current_count"] or 0) if existing is not None else 0
            connection.execute(
                """
                INSERT INTO tasks (
                    profile_id, trader, title, objective, item_name, required_count,
                    current_count, requirements_json, source_task_id, source_url, source_version,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (profile_id, trader, title) DO UPDATE SET
                    objective = excluded.objective,
                    item_name = excluded.item_name,
                    required_count = excluded.required_count,
                    current_count = excluded.current_count,
                    requirements_json = excluded.requirements_json,
                    source_task_id = CASE WHEN excluded.source_task_id != '' THEN excluded.source_task_id ELSE tasks.source_task_id END,
                    source_url = CASE WHEN excluded.source_url != '' THEN excluded.source_url ELSE tasks.source_url END,
                    source_version = CASE WHEN excluded.source_version != '' THEN excluded.source_version ELSE tasks.source_version END,
                    updated_at = excluded.updated_at
                """,
                (
                    profile_id,
                    trader,
                    title,
                    objective.strip(),
                    item_name.strip(),
                    required_count,
                    current_count,
                    _json_value(normalized_requirements),
                    source_task_id.strip(),
                    source_url.strip(),
                    source_version.strip(),
                    now,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM tasks WHERE profile_id = ? AND trader = ? AND title = ?",
                (profile_id, trader, title),
            ).fetchone()
            connection.execute(
                "INSERT INTO events (task_id, event_type, detail, created_at) VALUES (?, 'task_saved', ?, ?)",
                (row["id"], title, now),
            )
        return self._task(row)

    def set_requirement(
        self, task_id: int, profile_id: int, requirement_index: int, completed: bool
    ) -> Task:
        now = _now()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ? AND profile_id = ?", (task_id, profile_id)
            ).fetchone()
            if row is None:
                raise ValueError("找不到任务")
            requirements = json.loads(row["requirements_json"] or "[]")
            if requirement_index < 0 or requirement_index >= len(requirements):
                raise ValueError("找不到该任务要求")
            if requirements[requirement_index].get("target_count"):
                raise ValueError("该目标需要使用数量计数器。")
            requirements[requirement_index]["completed"] = completed
            required_count = sum(not item.get("optional", False) for item in requirements)
            current_count = sum(
                bool(item.get("completed")) and not item.get("optional", False)
                for item in requirements
            )
            auto_completed = row["state"] != "complete" and required_count > 0 and current_count >= required_count
            task_state = "complete" if row["state"] == "complete" or auto_completed else "active"
            connection.execute(
                "UPDATE tasks SET requirements_json = ?, required_count = ?, current_count = ?, state = ?, updated_at = ? WHERE id = ? AND profile_id = ?",
                (_json_value(requirements), required_count, current_count, task_state, now, task_id, profile_id),
            )
            detail = f"{requirement_index + 1}/{len(requirements)} {'完成' if completed else '取消'}"
            connection.execute(
                "INSERT INTO events (task_id, event_type, detail, created_at) VALUES (?, 'requirement_progress_changed', ?, ?)",
                (task_id, detail, now),
            )
            if auto_completed:
                connection.execute(
                    "INSERT INTO events (task_id, event_type, detail, created_at) VALUES (?, 'task_auto_completed', ?, ?)",
                    (task_id, row["title"], now),
                )
            updated = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._task(updated)

    def set_requirement_count(
        self, task_id: int, profile_id: int, requirement_index: int, current_count: int
    ) -> Task:
        now = _now()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ? AND profile_id = ?", (task_id, profile_id)
            ).fetchone()
            if row is None:
                raise ValueError("找不到任务")
            requirements = json.loads(row["requirements_json"] or "[]")
            if requirement_index < 0 or requirement_index >= len(requirements):
                raise ValueError("找不到该任务要求")
            requirement = requirements[requirement_index]
            try:
                target_count = int(requirement.get("target_count", 0))
                current_count = int(current_count)
            except (TypeError, ValueError) as error:
                raise ValueError("目标数量无效") from error
            if target_count <= 1:
                raise ValueError("该目标不是数量型要求")
            current_count = min(max(current_count, 0), target_count)
            requirement["current_count"] = current_count
            requirement["completed"] = current_count >= target_count
            required_count = sum(not item.get("optional", False) for item in requirements)
            task_current_count = sum(
                bool(item.get("completed")) and not item.get("optional", False)
                for item in requirements
            )
            auto_completed = row["state"] != "complete" and required_count > 0 and task_current_count >= required_count
            task_state = "complete" if row["state"] == "complete" or auto_completed else "active"
            connection.execute(
                "UPDATE tasks SET requirements_json = ?, required_count = ?, current_count = ?, state = ?, updated_at = ? WHERE id = ? AND profile_id = ?",
                (_json_value(requirements), required_count, task_current_count, task_state, now, task_id, profile_id),
            )
            connection.execute(
                "INSERT INTO events (task_id, event_type, detail, created_at) VALUES (?, 'requirement_count_changed', ?, ?)",
                (task_id, f"{requirement_index + 1}/{len(requirements)} {current_count}/{target_count}", now),
            )
            if auto_completed:
                connection.execute(
                    "INSERT INTO events (task_id, event_type, detail, created_at) VALUES (?, 'task_auto_completed', ?, ?)",
                    (task_id, row["title"], now),
                )
            updated = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._task(updated)

    def increment(self, task_id: int, profile_id: int) -> Task:
        now = _now()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ? AND profile_id = ?", (task_id, profile_id)
            ).fetchone()
            if row is None:
                raise ValueError("找不到任务")
            count = row["current_count"] + 1
            required = row["required_count"]
            state = "complete" if required is not None and count >= required else "active"
            connection.execute(
                "UPDATE tasks SET current_count = ?, state = ?, updated_at = ? WHERE id = ? AND profile_id = ?",
                (count, state, now, task_id, profile_id),
            )
            connection.execute(
                "INSERT INTO events (task_id, event_type, detail, created_at) VALUES (?, 'count_incremented', ?, ?)",
                (task_id, f"{count}/{required}" if required is not None else str(count), now),
            )
            updated = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._task(updated)

    def mark_complete(self, task_id: int, profile_id: int) -> Task:
        now = _now()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ? AND profile_id = ?", (task_id, profile_id)
            ).fetchone()
            if row is None:
                raise ValueError("找不到当前档案中的任务")
            connection.execute(
                "UPDATE tasks SET state = 'complete', updated_at = ? WHERE id = ? AND profile_id = ?",
                (now, task_id, profile_id),
            )
            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ? AND profile_id = ?", (task_id, profile_id)
            ).fetchone()
            connection.execute(
                "INSERT INTO events (task_id, event_type, detail, created_at) VALUES (?, 'marked_complete', ?, ?)",
                (task_id, row["title"], now),
            )
        return self._task(row)

    def delete_task(self, task_id: int, profile_id: int) -> Task:
        now = _now()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ? AND profile_id = ?",
                (task_id, profile_id),
            ).fetchone()
            if row is None:
                raise ValueError("找不到当前档案中的任务")
            task = self._task(row)
            connection.execute(
                "INSERT INTO events (task_id, event_type, detail, created_at) VALUES (?, 'task_deleted', ?, ?)",
                (task_id, task.title, now),
            )
            connection.execute(
                "DELETE FROM tasks WHERE id = ? AND profile_id = ?",
                (task_id, profile_id),
            )
        return task

    def clear_tasks(self, profile_id: int) -> int:
        now = _now()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, title FROM tasks WHERE profile_id = ?",
                (profile_id,),
            ).fetchall()
            if not rows:
                return 0
            connection.executemany(
                "INSERT INTO events (task_id, event_type, detail, created_at) VALUES (?, 'task_deleted', ?, ?)",
                [(row["id"], row["title"], now) for row in rows],
            )
            connection.execute("DELETE FROM tasks WHERE profile_id = ?", (profile_id,))
        return len(rows)

    def add_catalog_snapshot(
        self,
        source: str,
        game_mode: str,
        source_url: str = "",
        source_version: str = "",
        game_build: str | None = None,
        verification_status: str = "unverified",
        source_updated_at: str | None = None,
        content_sha256: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        if game_mode not in GAME_MODES:
            raise ValueError("任务资料快照必须指定有效游戏模式")
        if verification_status not in {"unverified", "verified", "stale"}:
            raise ValueError("未知资料核验状态")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO catalog_snapshots (
                    source, source_url, game_mode, source_version, game_build,
                    verification_status, source_updated_at, fetched_at, content_sha256, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source,
                    source_url,
                    game_mode,
                    source_version,
                    game_build,
                    verification_status,
                    source_updated_at,
                    _now(),
                    content_sha256,
                    _json_value(metadata or {}),
                ),
            )
            return int(cursor.lastrowid)

    def save_catalog_tasks(self, snapshot_id: int, tasks: list[dict[str, Any]]) -> None:
        with self._connect() as connection:
            snapshot = connection.execute(
                "SELECT id FROM catalog_snapshots WHERE id = ?", (snapshot_id,)
            ).fetchone()
            if snapshot is None:
                raise ValueError("找不到任务资料快照")
            for task in tasks:
                source_task_id = str(task.get("source_task_id", "")).strip()
                title = str(task.get("title", "")).strip()
                if not source_task_id or not title:
                    raise ValueError("目录任务缺少稳定 ID 或任务名称")
                connection.execute(
                    """
                    INSERT INTO catalog_tasks (
                        snapshot_id, source_task_id, trader, title, source_url,
                        objectives_json, prerequisites_json, key_requirements_json,
                        map_points_json, details_loaded, map_ids_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (snapshot_id, source_task_id) DO UPDATE SET
                        trader = excluded.trader,
                        title = excluded.title,
                        source_url = excluded.source_url,
                        objectives_json = excluded.objectives_json,
                        prerequisites_json = excluded.prerequisites_json,
                        key_requirements_json = excluded.key_requirements_json,
                        map_points_json = excluded.map_points_json,
                        details_loaded = excluded.details_loaded,
                        map_ids_json = excluded.map_ids_json
                    """,
                    (
                        snapshot_id,
                        source_task_id,
                        str(task.get("trader", "")),
                        title,
                        str(task.get("source_url", "")),
                        _json_value(task.get("objectives", [])),
                        _json_value(task.get("prerequisites", [])),
                        _json_value(task.get("key_requirements", [])),
                        _json_value(task.get("map_points", [])),
                        int(bool(task.get("details_loaded", False))),
                        _json_value(task.get("map_ids", [])),
                    ),
                )

    def sync_catalog_from(
        self, source_path: Path, game_mode: str | None = None
    ) -> list[dict[str, Any]]:
        source_path = Path(source_path)
        if not source_path.is_file() or source_path.resolve() == self.path.resolve():
            return []

        source_connection = sqlite3.connect(
            f"{source_path.resolve().as_uri()}?mode=ro", uri=True, timeout=10
        )
        source_connection.row_factory = sqlite3.Row
        try:
            if game_mode:
                source_snapshots = source_connection.execute(
                    "SELECT * FROM catalog_snapshots WHERE game_mode = ? ORDER BY id DESC LIMIT 1",
                    (game_mode,),
                ).fetchall()
            else:
                source_snapshots = source_connection.execute(
                    """
                    SELECT snapshot.* FROM catalog_snapshots AS snapshot
                    WHERE snapshot.id = (
                        SELECT MAX(latest.id) FROM catalog_snapshots AS latest
                        WHERE latest.game_mode = snapshot.game_mode
                    )
                    ORDER BY snapshot.id
                    """
                ).fetchall()

            snapshot_data = []
            source_columns = {row[1] for row in source_connection.execute("PRAGMA table_info(catalog_tasks)").fetchall()}
            for snapshot in source_snapshots:
                tasks = source_connection.execute(
                    """
                    SELECT source_task_id, trader, title, source_url, objectives_json,
                           prerequisites_json, key_requirements_json, map_points_json, details_loaded,
                    """ + ("map_ids_json" if "map_ids_json" in source_columns else "'[]' AS map_ids_json") + """
                    FROM catalog_tasks WHERE snapshot_id = ? ORDER BY source_task_id
                    """,
                    (snapshot["id"],),
                ).fetchall()
                snapshot_data.append((dict(snapshot), [dict(task) for task in tasks]))
        finally:
            source_connection.close()

        imported = []
        with self._connect() as connection:
            for snapshot, tasks in snapshot_data:
                local_latest = connection.execute(
                    "SELECT * FROM catalog_snapshots WHERE game_mode = ? ORDER BY id DESC LIMIT 1",
                    (snapshot["game_mode"],),
                ).fetchone()
                if local_latest is not None:
                    same_content = (
                        str(local_latest["content_sha256"] or "")
                        and str(local_latest["content_sha256"] or "")
                        == str(snapshot["content_sha256"] or "")
                    )
                    local_task_count = connection.execute(
                        "SELECT COUNT(*) FROM catalog_tasks WHERE snapshot_id = ?",
                        (local_latest["id"],),
                    ).fetchone()[0]
                    if same_content and local_task_count == len(tasks):
                        continue
                    if str(local_latest["fetched_at"] or "") > str(snapshot["fetched_at"] or ""):
                        continue

                cursor = connection.execute(
                    """
                    INSERT INTO catalog_snapshots (
                        source, source_url, game_mode, source_version, game_build,
                        verification_status, source_updated_at, fetched_at, content_sha256, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot["source"],
                        snapshot["source_url"],
                        snapshot["game_mode"],
                        snapshot["source_version"],
                        snapshot["game_build"],
                        snapshot["verification_status"],
                        snapshot["source_updated_at"],
                        snapshot["fetched_at"],
                        snapshot["content_sha256"],
                        snapshot["metadata_json"],
                    ),
                )
                local_snapshot_id = int(cursor.lastrowid)
                connection.executemany(
                    """
                    INSERT INTO catalog_tasks (
                        snapshot_id, source_task_id, trader, title, source_url,
                        objectives_json, prerequisites_json, key_requirements_json,
                        map_points_json, details_loaded, map_ids_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            local_snapshot_id,
                            task["source_task_id"],
                            task["trader"],
                            task["title"],
                            task["source_url"],
                            task["objectives_json"],
                            task["prerequisites_json"],
                            task["key_requirements_json"],
                            task["map_points_json"],
                            task["details_loaded"],
                            task["map_ids_json"],
                        )
                        for task in tasks
                    ],
                )
                imported.append(
                    {
                        "game_mode": str(snapshot["game_mode"]),
                        "snapshot_id": local_snapshot_id,
                        "source_version": str(snapshot["source_version"] or ""),
                        "task_count": len(tasks),
                    }
                )
        return imported

    @staticmethod
    def _catalog_source_clause(provider: str | None) -> tuple[str, tuple[str, ...]]:
        if provider is None:
            return "", ()
        if provider in {"tarkov.dev", "eftarkov"}:
            return """ AND (CASE WHEN json_extract(metadata_json, '$.provider') IS NOT NULL
                THEN json_extract(metadata_json, '$.provider')
                WHEN source = 'Tarkov.dev community JSON API' THEN 'tarkov.dev'
                WHEN source = 'eftarkov.com' THEN 'eftarkov' ELSE '' END) = ?""", (provider,)
        return " AND 0", ()

    def latest_catalog_snapshot(self, game_mode: str, provider: str | None = None) -> dict[str, Any] | None:
        clause, parameters = self._catalog_source_clause(provider)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM catalog_snapshots WHERE game_mode = ?" + clause + " ORDER BY id DESC LIMIT 1",
                (game_mode, *parameters),
            ).fetchone()
            if row is None:
                return None
            task_count = connection.execute(
                "SELECT COUNT(*) FROM catalog_tasks WHERE snapshot_id = ?", (row["id"],)
            ).fetchone()[0]
        result = dict(row)
        result["metadata"] = json.loads(result.pop("metadata_json") or "{}")
        result["task_count"] = int(task_count)
        return result

    def search_catalog_tasks(
        self, game_mode: str, query: str = "", trader: str = "", limit: int = 60, provider: str | None = None
    ) -> list[dict[str, Any]]:
        query = query.strip()
        trader = trader.strip()
        limit = max(1, min(int(limit), 200))
        snapshot = self.latest_catalog_snapshot(game_mode, provider)
        if snapshot is None:
            return []
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT ct.snapshot_id, ct.source_task_id, ct.trader, ct.title, ct.source_url,
                       ct.objectives_json, ct.prerequisites_json, ct.key_requirements_json,
                       ct.map_points_json, ct.map_ids_json, ct.details_loaded, cs.source_version,
                       cs.verification_status
                FROM catalog_tasks AS ct
                JOIN catalog_snapshots AS cs ON cs.id = ct.snapshot_id
                WHERE cs.game_mode = ?
                  AND cs.id = ?
                  AND (? = '' OR ct.title LIKE ? OR ct.trader LIKE ?)
                  AND (? = '' OR ct.trader = ?)
                ORDER BY ct.trader, ct.title
                LIMIT ?
                """,
                (
                    game_mode,
                    snapshot["id"],
                    query,
                    f"%{query}%",
                    f"%{query}%",
                    trader,
                    trader,
                    limit,
                ),
            ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["objectives"] = json.loads(item.pop("objectives_json") or "[]")
            item["prerequisites"] = json.loads(item.pop("prerequisites_json") or "[]")
            item["key_requirements"] = json.loads(item.pop("key_requirements_json") or "[]")
            item["map_points"] = json.loads(item.pop("map_points_json") or "[]")
            item["map_ids"] = json.loads(item.pop("map_ids_json") or "[]")
            item["details_loaded"] = bool(item.get("details_loaded"))
            results.append(item)
        return results

    def get_catalog_task(self, snapshot_id: int, source_task_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT ct.snapshot_id, ct.source_task_id, ct.trader, ct.title, ct.source_url,
                       ct.objectives_json, ct.prerequisites_json, ct.key_requirements_json,
                       ct.map_points_json, ct.map_ids_json, ct.details_loaded, cs.game_mode,
                       cs.source_version, cs.verification_status, cs.source_url AS catalog_source_url,
                       cs.source AS catalog_source, cs.metadata_json AS catalog_metadata_json
                FROM catalog_tasks AS ct
                JOIN catalog_snapshots AS cs ON cs.id = ct.snapshot_id
                WHERE ct.snapshot_id = ? AND ct.source_task_id = ?
                """,
                (snapshot_id, source_task_id),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["data_provider"] = catalog_data_provider(result.pop("catalog_source"), json.loads(result.pop("catalog_metadata_json") or "{}"))
        result["objectives"] = json.loads(result.pop("objectives_json") or "[]")
        result["prerequisites"] = json.loads(result.pop("prerequisites_json") or "[]")
        result["key_requirements"] = json.loads(result.pop("key_requirements_json") or "[]")
        result["map_points"] = json.loads(result.pop("map_points_json") or "[]")
        result["map_ids"] = json.loads(result.pop("map_ids_json") or "[]")
        result["details_loaded"] = bool(result.get("details_loaded"))
        return result

    def update_catalog_task_details(
        self,
        snapshot_id: int,
        source_task_id: str,
        objectives: list[dict[str, Any]],
        prerequisites: list[dict[str, Any]] | None = None,
        key_requirements: list[dict[str, Any]] | None = None,
        map_points: list[dict[str, Any]] | None = None,
        map_ids: list[str] | None = None,
    ) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE catalog_tasks
                SET objectives_json = ?, prerequisites_json = ?, key_requirements_json = ?,
                    map_points_json = ?, map_ids_json = COALESCE(?, map_ids_json), details_loaded = 1
                WHERE snapshot_id = ? AND source_task_id = ?
                """,
                (
                    _json_value(objectives),
                    _json_value(prerequisites or []),
                    _json_value(key_requirements or []),
                    _json_value(map_points or []),
                    _json_value(map_ids) if map_ids is not None else None,
                    snapshot_id,
                    source_task_id,
                ),
            )
            if cursor.rowcount == 0:
                raise ValueError("找不到任务资料")

    def list_map_waypoints(self, profile_id: int, map_id: str, floor_key: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT w.*, t.title AS task_title, t.source_task_id
                FROM map_waypoints AS w
                JOIN tasks AS t ON t.id = w.task_id
                WHERE w.profile_id = ? AND w.map_id = ? AND w.floor_key = ?
                  AND t.state <> 'complete'
                ORDER BY w.id
                """,
                (profile_id, map_id, floor_key),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_map_waypoint_counts(self, profile_id: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT w.map_id, w.task_id, COUNT(*) AS point_count
                FROM map_waypoints AS w
                JOIN tasks AS t ON t.id = w.task_id
                WHERE w.profile_id = ? AND t.state <> 'complete'
                GROUP BY w.map_id, w.task_id
                """,
                (profile_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_map_waypoint(
        self,
        profile_id: int,
        task_id: int,
        map_id: str,
        floor_key: str,
        x: float,
        y: float,
        label: str = "",
        key_name: str = "",
        key_acquisition: str = "",
    ) -> dict[str, Any]:
        with self._connect() as connection:
            task = connection.execute(
                "SELECT id FROM tasks WHERE id = ? AND profile_id = ?",
                (task_id, profile_id),
            ).fetchone()
            if task is None:
                raise ValueError("所选任务不属于当前档案")
            cursor = connection.execute(
                """
                INSERT INTO map_waypoints (
                    profile_id, task_id, map_id, floor_key, x, y, label,
                    key_name, key_acquisition, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_id,
                    task_id,
                    map_id,
                    floor_key,
                    x,
                    y,
                    label.strip(),
                    key_name.strip(),
                    key_acquisition.strip(),
                    _now(),
                ),
            )
            row = connection.execute(
                """
                SELECT w.*, t.title AS task_title, t.source_task_id
                FROM map_waypoints AS w JOIN tasks AS t ON t.id = w.task_id
                WHERE w.id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        return dict(row)

    def delete_map_waypoint(self, profile_id: int, waypoint_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM map_waypoints WHERE id = ? AND profile_id = ?",
                (waypoint_id, profile_id),
            )
        return cursor.rowcount > 0

    def list_map_marker_visits(self, profile_id: int, map_id: str) -> set[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT marker_id FROM map_marker_visits WHERE profile_id = ? AND map_id = ?",
                (profile_id, map_id),
            ).fetchall()
        return {str(row["marker_id"]) for row in rows}

    def set_map_marker_visited(
        self, profile_id: int, map_id: str, marker_id: str, visited: bool
    ) -> bool:
        with self._connect() as connection:
            if visited:
                connection.execute(
                    """
                    INSERT INTO map_marker_visits (profile_id, map_id, marker_id, visited_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (profile_id, map_id, marker_id)
                    DO UPDATE SET visited_at = excluded.visited_at
                    """,
                    (profile_id, map_id, marker_id, _now()),
                )
            else:
                connection.execute(
                    "DELETE FROM map_marker_visits WHERE profile_id = ? AND map_id = ? AND marker_id = ?",
                    (profile_id, map_id, marker_id),
                )
        return visited
