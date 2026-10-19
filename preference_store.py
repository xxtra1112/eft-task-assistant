"""Profile-scoped UI snapshots; import performs no database or filesystem IO.

Pass TaskStore._connect (a committing/rolling-back connection context factory).
Callers must retain their local snapshot until save/resolve succeeds. Saves replace
the whole snapshot, never merge aliases or infer item identities. Local route
queues/caches must be removed by the caller before upload. Errors never mutate
the supplied object. A 409 is raised only after its conflict backups commit.
UUIDs are scoped to a profile across both save and resolve; retries reproduce the
original response, including an original conflict. Reusing a UUID for a different
request raises PreferenceError(status=409, error_code='operation_id_reused').
All backup/export methods require the owning profile; HTTP authorization belongs
to the integrating caller. No session/authentication tables are read or exported.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import uuid
from typing import Any, Callable, ContextManager
from urllib.parse import urlsplit


MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_DEPTH = 24
MAX_NODES = 200000
MAX_COLLECTION_ITEMS = 10000
MAX_REVISION = 2**63 - 1
LOCAL_ONLY_FIELDS = frozenset({"routePendingOperations", "routeCaches", "routeCacheRevisions"})
LIST_LIMITS = {
    "hiddenTaskIds": 500, "hiddenMapPointIds": 1000, "hiddenKeyIds": 300,
    "keyFilterKnownIds": 300, "newKeyIds": 300, "keyOwnershipPendingIds": 300,
    "collapsedMapTaskGroups": 1000, "collapsedTaskIds": 500,
}
BOOL_FIELDS = frozenset({
    "showHiddenTasks", "keyFilterInitialized", "operationHistoryOpen",
    "hideoutPlannerOpen", "hideoutMaterialsOpen",
})
STRING_FIELDS = frozenset({"selectedMapId", "taskTraderFilter", "taskMapFilter", "mobilePairingAddress"})
PERSISTED_FIELDS = frozenset(LIST_LIMITS) | BOOL_FIELDS | STRING_FIELDS | frozenset({
    "version", "selectedMapFloors", "mapAnnotationVisibility", "mapZoom",
    "keyOwnershipAnswers", "hideoutPlan", "hideoutOwnedMaterials", "operationHistory",
    "panels", "mapDrawings", "legacyRoutesImported", "routeStyle",
})
LEGACY_FIELD_ALIASES = {"hiddenMapTaskIds": "hiddenTaskIds"}


class PreferenceError(ValueError):
    def __init__(self, message: str, status: int = 400, **details: Any) -> None:
        super().__init__(message)
        self.status = status
        self.status_code = status
        self.details = details


class PreferenceConflict(PreferenceError):
    def __init__(self, result: dict[str, Any]) -> None:
        super().__init__("偏好版本冲突；本地副本与服务器副本已备份。", 409, **result)
        self.current = result["current"]
        self.revision = self.current["revision"]
        self.conflict_id = result["conflict_id"]
        self.result = result


def _require(condition: bool, message: str = "偏好字段类型或值无效。") -> None:
    if not condition:
        raise PreferenceError(message)


def _capacity(condition: bool) -> None:
    if not condition:
        raise PreferenceError("偏好超过容量限制；请保留本地原副本。", 413, error_code="preference_capacity")


def _integer(value: Any, minimum: int = 0) -> int:
    _require(type(value) is int and minimum <= value <= MAX_REVISION)
    return value


def _identifier(value: Any) -> str:
    _require(isinstance(value, str) and bool(re.fullmatch(r"[0-9a-fA-F-]{36}", value)), "操作/备份 ID 必须为 UUID。")
    try:
        return str(uuid.UUID(value))
    except ValueError as error:
        raise PreferenceError("操作/备份 ID 必须为 UUID。") from error


def _object(value: Any, fields: set[str] | frozenset[str] | None = None, limit: int = 10000) -> None:
    _require(type(value) is dict)
    _capacity(len(value) <= limit)
    if fields is not None:
        _require(not set(value) - fields, "偏好包含未知字段。")


def _string(value: Any, limit: int = 512) -> None:
    _require(type(value) is str)
    _capacity(len(value) <= limit)


def _number(value: Any, minimum: float = 0, maximum: float = 1000000) -> None:
    _require(type(value) in {int, float} and minimum <= value <= maximum and math.isfinite(value))


def _tree(value: Any, depth: int = 0, budget: list[int] | None = None) -> None:
    if budget is None:
        budget = [MAX_NODES]
    budget[0] -= 1
    _capacity(depth <= MAX_DEPTH and budget[0] >= 0)
    if type(value) is dict:
        _capacity(len(value) <= MAX_COLLECTION_ITEMS)
        for key, child in value.items():
            _string(key, 512)
            _tree(child, depth + 1, budget)
    elif type(value) is list:
        _capacity(len(value) <= MAX_COLLECTION_ITEMS)
        for child in value:
            _tree(child, depth + 1, budget)
    elif type(value) is str:
        _string(value, MAX_JSON_BYTES)
    elif type(value) is float:
        _require(math.isfinite(value), "偏好不接受 NaN 或 Infinity。")
    elif type(value) is int:
        _require(-MAX_REVISION <= value <= MAX_REVISION)
    else:
        _require(value is None or type(value) is bool, "偏好必须为 JSON 数据。")


def _json(value: Any) -> str:
    try:
        parts = []
        byte_count = 0
        encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
        for part in encoder.iterencode(value):
            byte_count += len(part.encode("utf-8"))
            _capacity(byte_count <= MAX_JSON_BYTES)
            parts.append(part)
        return "".join(parts)
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, PreferenceError):
            raise
        raise PreferenceError("偏好不是有效 UTF-8 JSON。") from error


def _strokes(strokes: Any) -> None:
    _require(type(strokes) is list)
    _capacity(len(strokes) <= 1000)
    for stroke in strokes:
        if type(stroke) is dict:
            _object(stroke, {"id", "points", "color", "width"})
            if "id" in stroke:
                _string(stroke["id"], 128)
            if "color" in stroke:
                _require(type(stroke["color"]) is str and bool(re.fullmatch(r"#[0-9a-fA-F]{6}", stroke["color"])))
            if "width" in stroke:
                _require(type(stroke["width"]) in {int, float} and stroke["width"] in {2, 4, 6})
            points = stroke.get("points")
        else:
            points = stroke
        _require(type(points) is list and len(points) >= 2)
        _capacity(len(points) <= 10000)
        for point in points:
            _require(type(point) is list and len(point) == 2)
            for coordinate in point:
                _number(coordinate, 0, 1)


def _task(value: Any) -> None:
    strings = {"trader", "title", "objective", "item_name", "state", "source_task_id", "source_url", "source_version"}
    numbers = {"id", "profile_id", "current_count", "required_count"}
    _object(value, strings | numbers | {"requirements"})
    for key, child in value.items():
        if key in strings:
            _string(child, 65536)
        elif key in numbers:
            if key != "required_count" or child is not None:
                _integer(child)
        else:
            _require(type(child) is list)
            _capacity(len(child) <= 1000)
            for requirement in child:
                _object(requirement, {"text", "optional", "completed", "target_count", "current_count"})
                for name, part in requirement.items():
                    if name == "text":
                        _string(part, 65536)
                    elif name in {"optional", "completed"}:
                        _require(type(part) is bool)
                    else:
                        _integer(part)


def _history(value: Any) -> None:
    _require(type(value) is list)
    _capacity(len(value) <= 40)
    data_fields = {
        "ui": {"before"}, "task": {"beforeTask", "afterTaskId", "beforeUi"},
        "tasks": {"beforeTasks", "beforeUi"}, "map-drawing": {"mapId", "strokes"},
        "map-visit": {"mapId", "markerId", "beforeVisited"},
    }
    for entry in value:
        _object(entry, {"id", "label", "type", "time", "data", "undone"})
        for name, limit in (("id", 100), ("label", 500), ("type", 40)):
            _string(entry.get(name), limit)
        if "time" in entry:
            _string(entry["time"], 40)
        if "undone" in entry:
            _require(type(entry["undone"]) is bool)
        _require(entry["type"] in data_fields)
        data = entry.get("data")
        _object(data, data_fields[entry["type"]])
        for name, child in data.items():
            if name in {"before", "beforeUi"}:
                _object(child, PERSISTED_FIELDS - {"operationHistory"} | set(LEGACY_FIELD_ALIASES))
                _fields(child)
            elif name == "beforeTask":
                if child is not None:
                    _task(child)
            elif name == "beforeTasks":
                _require(type(child) is list)
                _capacity(len(child) <= 1000)
                for task in child:
                    _task(task)
            elif name == "afterTaskId":
                _integer(child, 1)
            elif name == "strokes":
                _strokes(child)
            elif name == "beforeVisited":
                _require(type(child) is bool)
            else:
                _string(child)


def _fields(data: dict[str, Any]) -> None:
    for field, value in data.items():
        canonical = LEGACY_FIELD_ALIASES.get(field, field)
        if canonical == "version":
            _require(type(value) is int and value == 1, "仅支持 version=1 的 UI 偏好。")
        elif canonical in STRING_FIELDS:
            _string(value)
            if canonical == "mobilePairingAddress" and value:
                try:
                    address = urlsplit(value if "://" in value else "http://" + value)
                    _require(address.scheme in {"http", "https"} and bool(address.hostname)
                             and address.username is None and address.password is None
                             and not address.query and not address.fragment and address.path in {"", "/"})
                    _require(address.port is None or 0 < address.port <= 65535)
                except ValueError as error:
                    raise PreferenceError("手机配对地址必须为无凭据的主机地址。") from error
        elif canonical in BOOL_FIELDS:
            _require(type(value) is bool)
        elif canonical in LIST_LIMITS:
            _require(type(value) is list)
            _capacity(len(value) <= LIST_LIMITS[canonical])
            for identifier in value:
                _string(identifier)
        elif canonical == "mapZoom":
            _number(value, 0.01, 100)
        elif canonical == "operationHistory":
            _history(value)
        elif canonical == "routeStyle":
            _object(value, {"color", "width"})
            if "color" in value:
                _require(type(value["color"]) is str and bool(re.fullmatch(r"#[0-9a-fA-F]{6}", value["color"])))
            if "width" in value:
                _require(type(value["width"]) in {int, float} and value["width"] in {2, 4, 6})
        else:
            limits = {"selectedMapFloors": 100, "hideoutPlan": 100, "hideoutOwnedMaterials": 500,
                      "keyOwnershipAnswers": 300, "mapDrawings": 100}
            _object(value, limit=limits.get(canonical, 1000))
            if canonical == "panels":
                _object(value, {"addTask", "catalog", "diagnostics"})
            if canonical == "mapAnnotationVisibility":
                _object(value, {"location", "pmc-exit", "scav-exit", "unknown-exit", "transfer"})
            for child in value.values():
                if canonical in {"keyOwnershipAnswers", "panels", "mapAnnotationVisibility"}:
                    _require(type(child) is bool)
                elif canonical in {"selectedMapFloors", "legacyRoutesImported"}:
                    _string(child)
                elif canonical == "hideoutOwnedMaterials":
                    _number(child)
                elif canonical == "mapDrawings":
                    _strokes(child)
                elif canonical == "hideoutPlan":
                    _object(child, {"enabled", "currentLevel", "targetLevel"})
                    for name, part in child.items():
                        if name == "enabled":
                            _require(type(part) is bool)
                        else:
                            _number(part, 0, 20)


def validate_preferences(data: Any) -> dict[str, Any]:
    """Return a detached snapshot, preserving aliases, order of arrays and strokes.

    Accept partial version-1 snapshots (missing version defaults to 1); no field
    defaults, truncation, deduplication, item matching or alias rewriting occurs.
    Unknown and local-only fields are errors, including inside history snapshots.
    """
    _object(data, PERSISTED_FIELDS | set(LEGACY_FIELD_ALIASES))
    _tree(data)
    _fields(data)
    return json.loads(_json({"version": 1, **data}))


class ProfilePreferences:
    def __init__(self, connect: Callable[[], ContextManager[sqlite3.Connection]]) -> None:
        self.connect = connect
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for statement in (
                """CREATE TABLE IF NOT EXISTS profile_preferences (
                    profile_id INTEGER PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
                    revision INTEGER NOT NULL CHECK(revision > 0), data_json TEXT NOT NULL)""",
                """CREATE TABLE IF NOT EXISTS preference_backups (
                    id TEXT PRIMARY KEY, profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                    revision INTEGER NOT NULL, kind TEXT NOT NULL, data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))""",
                """CREATE TABLE IF NOT EXISTS preference_conflicts (
                    id TEXT PRIMARY KEY, profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                    operation_id TEXT NOT NULL, base_revision INTEGER NOT NULL, server_revision INTEGER NOT NULL,
                    reason TEXT NOT NULL, server_backup_id TEXT NOT NULL REFERENCES preference_backups(id),
                    local_backup_id TEXT NOT NULL REFERENCES preference_backups(id),
                    resolution TEXT, resolved_revision INTEGER,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))""",
                """CREATE TABLE IF NOT EXISTS preference_operations (
                    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                    operation_id TEXT NOT NULL, request_hash TEXT NOT NULL,
                    is_conflict INTEGER NOT NULL, result_json TEXT NOT NULL,
                    PRIMARY KEY(profile_id, operation_id))""",
                "CREATE INDEX IF NOT EXISTS preference_conflicts_profile ON preference_conflicts(profile_id)",
                "CREATE INDEX IF NOT EXISTS preference_backups_profile ON preference_backups(profile_id)",
            ):
                connection.execute(statement)

    @staticmethod
    def _profile(connection: sqlite3.Connection, profile_id: int) -> None:
        _integer(profile_id, 1)
        if not connection.execute("SELECT 1 FROM profiles WHERE id=?", (profile_id,)).fetchone():
            raise PreferenceError("存档不存在。", 404)

    @staticmethod
    def _state(connection: sqlite3.Connection, profile_id: int) -> dict[str, Any]:
        row = connection.execute("SELECT revision, data_json FROM profile_preferences WHERE profile_id=?", (profile_id,)).fetchone()
        conflicts = connection.execute("""SELECT id, base_revision, server_revision, reason,
            server_backup_id, local_backup_id, resolution, resolved_revision, created_at
            FROM preference_conflicts WHERE profile_id=? ORDER BY rowid""", (profile_id,)).fetchall()
        names = ("conflict_id", "base_revision", "server_revision", "reason", "server_backup_id",
                 "local_backup_id", "resolution", "resolved_revision", "created_at")
        return {"profile_id": profile_id, "revision": row[0] if row else 0,
                "data": json.loads(row[1]) if row else {"version": 1},
                "conflicts": [dict(zip(names, conflict)) for conflict in conflicts]}

    @staticmethod
    def _backup(connection: sqlite3.Connection, profile_id: int, revision: int, kind: str, blob: str) -> str:
        identifier = str(uuid.uuid4())
        connection.execute("INSERT INTO preference_backups(id,profile_id,revision,kind,data_json) VALUES (?,?,?,?,?)",
                           (identifier, profile_id, revision, kind, blob))
        return identifier

    def get(self, profile_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute("BEGIN")
            self._profile(connection, profile_id)
            return self._state(connection, profile_id)

    @staticmethod
    def _replay(connection: sqlite3.Connection, profile_id: int, operation_id: str, fingerprint: str) -> tuple[dict[str, Any], bool] | None:
        row = connection.execute("""SELECT request_hash,result_json,is_conflict FROM preference_operations
            WHERE profile_id=? AND operation_id=?""", (profile_id, operation_id)).fetchone()
        if not row:
            return None
        if row[0] != fingerprint:
            raise PreferenceError("operation_id 已用于不同请求；请保留本地副本并使用新 UUID。", 409,
                                  error_code="operation_id_reused")
        return json.loads(row[1]), bool(row[2])

    def _apply(self, connection: sqlite3.Connection, profile_id: int, blob: str,
               base_revision: int, operation_id: str, only_if_empty: bool = False,
               conflict: tuple[Any, ...] | None = None, choice: str | None = None) -> tuple[dict[str, Any], bool]:
        current = self._state(connection, profile_id)
        revision = current["revision"]
        reason = ""
        if base_revision != revision:
            reason = "revision_mismatch"
        elif only_if_empty and revision > 0:
            reason = "server_not_empty"
        elif conflict and conflict[1] is not None:
            reason = "already_resolved"
        if reason:
            server_backup = self._backup(connection, profile_id, revision, "conflict_server", _json(current["data"]))
            local_backup = self._backup(connection, profile_id, base_revision, "conflict_local", blob)
            conflict_id = str(uuid.uuid4())
            connection.execute("""INSERT INTO preference_conflicts
                (id,profile_id,operation_id,base_revision,server_revision,reason,server_backup_id,local_backup_id)
                VALUES (?,?,?,?,?,?,?,?)""", (conflict_id, profile_id, operation_id, base_revision,
                revision, reason, server_backup, local_backup))
            return {"conflict_id": conflict_id, "current": self._state(connection, profile_id),
                    "server_backup_id": server_backup, "local_backup_id": local_backup,
                    "reason": reason, "operation_id": operation_id}, True
        _capacity(revision < MAX_REVISION)
        server_backup = None
        local_backup = None
        if revision > 0:
            server_backup = self._backup(connection, profile_id, revision, "before_resolution" if conflict else "before_save", _json(current["data"]))
        if conflict:
            local_backup = self._backup(connection, profile_id, base_revision, "resolution_local", conflict[0])
        connection.execute("""INSERT INTO profile_preferences(profile_id,revision,data_json) VALUES (?,?,?)
            ON CONFLICT(profile_id) DO UPDATE SET revision=excluded.revision,data_json=excluded.data_json""",
            (profile_id, revision + 1, blob))
        if conflict:
            connection.execute("UPDATE preference_conflicts SET resolution=?,resolved_revision=? WHERE id=? AND profile_id=?",
                               (choice, revision + 1, conflict[2], profile_id))
        result = self._state(connection, profile_id)
        result["operation_id"] = operation_id
        if conflict:
            result["resolved_conflict_id"] = conflict[2]
            result["server_backup_id"] = server_backup
            result["local_backup_id"] = local_backup
        return result, False

    def _operate(self, profile_id: int, operation_id: str, request: dict[str, Any]) -> dict[str, Any]:
        _integer(profile_id, 1)
        operation_id = _identifier(operation_id)
        _integer(request["base_revision"])
        fingerprint = hashlib.sha256(json.dumps(request, ensure_ascii=False, allow_nan=False,
            sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._profile(connection, profile_id)
            outcome = self._replay(connection, profile_id, operation_id, fingerprint)
            if outcome is None:
                conflict = None
                if request["kind"] == "resolve":
                    row = connection.execute("""SELECT b.data_json,c.resolution,c.id FROM preference_conflicts c
                        JOIN preference_backups b ON b.id=c.local_backup_id
                        WHERE c.id=? AND c.profile_id=? AND b.profile_id=?""",
                        (request["conflict_id"], profile_id, profile_id)).fetchone()
                    if row is None:
                        raise PreferenceError("冲突不存在。", 404)
                    conflict = tuple(row)
                    blob = row[0] if request["choice"] == "local" else _json(self._state(connection, profile_id)["data"])
                else:
                    blob = request["blob"]
                outcome = self._apply(connection, profile_id, blob, request["base_revision"], operation_id,
                                      request.get("only_if_empty", False), conflict, request.get("choice"))
                connection.execute("INSERT INTO preference_operations VALUES (?,?,?,?,?)",
                                   (profile_id, operation_id, fingerprint, int(outcome[1]), json.dumps(outcome[0], ensure_ascii=False, allow_nan=False)))
        result, is_conflict = outcome
        if is_conflict:
            raise PreferenceConflict(result)
        return result

    def save(self, profile_id: int, data: Any, base_revision: int, operation_id: str,
             only_if_empty: bool = False) -> dict[str, Any]:
        _require(type(only_if_empty) is bool)
        blob = _json(validate_preferences(data))
        return self._operate(profile_id, operation_id, {"kind": "save", "blob": blob,
            "base_revision": base_revision, "only_if_empty": only_if_empty})

    def resolve(self, profile_id: int, conflict_id: str, choice: str, base_revision: int,
                operation_id: str) -> dict[str, Any]:
        """Choose current server state or the conflict's original local snapshot.

        Both choices require current CAS revision and advance revision, including
        choosing server. Stale resolution creates another durable conflict.
        """
        _require(type(choice) is str and choice in {"server", "local"}, "必须显式选择 server 或 local。")
        return self._operate(profile_id, operation_id, {"kind": "resolve", "conflict_id": _identifier(conflict_id),
            "choice": choice, "base_revision": base_revision})

    def get_backup(self, profile_id: int, backup_id: str) -> dict[str, Any]:
        backup_id = _identifier(backup_id)
        with self.connect() as connection:
            self._profile(connection, profile_id)
            row = connection.execute("""SELECT id,revision,kind,data_json,created_at FROM preference_backups
                WHERE id=? AND profile_id=?""", (backup_id, profile_id)).fetchone()
            if row is None:
                raise PreferenceError("偏好备份不存在。", 404)
            return {"backup_id": row[0], "profile_id": profile_id, "revision": row[1],
                    "kind": row[2], "data": json.loads(row[3]), "created_at": row[4]}

    def export_conflicts(self, profile_id: int) -> dict[str, Any]:
        """Export conflicts and retained UI backups, including later resolutions."""
        with self.connect() as connection:
            connection.execute("BEGIN")
            self._profile(connection, profile_id)
            state = self._state(connection, profile_id)
            rows = connection.execute("""SELECT id,revision,kind,data_json,created_at
                FROM preference_backups WHERE profile_id=? ORDER BY rowid""", (profile_id,)).fetchall()
            return {"profile_id": profile_id, "conflicts": state["conflicts"], "backups": [
                {"backup_id": row[0], "revision": row[1], "kind": row[2], "data": json.loads(row[3]), "created_at": row[4]}
                for row in rows]}
