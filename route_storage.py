from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import uuid
from typing import Any, Callable, ContextManager


MAX_STROKES = 40
MAX_STROKE_POINTS = 1000
MAX_SCOPE_POINTS = 12000
MAX_REVISION = 2**63 - 1
PROVIDERS = {"tarkov.dev", "eftarkov", "reemr"}
OPERATIONS = {"append", "undo", "clear", "replace", "import_legacy", "assign_legacy"}


class DrawingError(ValueError):
    def __init__(self, message: str, status: int = 400, **details: Any) -> None:
        super().__init__(message)
        self.status = status
        self.details = details


def drawing_scope(source: Any, map_id: Any, floor_key: Any) -> dict[str, str]:
    if not isinstance(source, str) or source not in PROVIDERS:
        raise DrawingError("未知路线数据源。")
    if not isinstance(map_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", map_id):
        raise DrawingError("路线地图 ID 无效。")
    if not isinstance(floor_key, str) or (floor_key and not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.: -]{0,127}", floor_key)):
        raise DrawingError("路线楼层 ID 无效。")
    return {"source": source, "map_id": map_id, "floor_key": floor_key}


def revision_number(value: Any, name: str = "revision") -> int:
    if type(value) is not int or not 0 <= value <= MAX_REVISION:
        raise DrawingError(f"{name} 必须是非负整数。")
    return value


def profile_number(value: Any) -> int:
    if type(value) is not int or not 0 < value <= MAX_REVISION:
        raise DrawingError("profile_id 必须是正整数。")
    return value


def operation_uuid(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F-]{36}", value):
        raise DrawingError("operation_id 必须为 UUID。")
    try:
        return str(uuid.UUID(value))
    except ValueError as error:
        raise DrawingError("operation_id 必须为 UUID。") from error


def normalize_strokes(strokes: Any) -> list[dict[str, Any]]:
    if not isinstance(strokes, list):
        raise DrawingError("strokes 必须是数组。")
    if len(strokes) > MAX_STROKES:
        raise DrawingError("每个楼层最多保存 40 条路线。", 400, error_code="drawing_capacity")
    result = []
    identifiers = set()
    total_points = 0
    for stroke in strokes:
        if not isinstance(stroke, dict) or set(stroke) - {"id", "points", "color", "width"}:
            raise DrawingError("路线必须包含有效的 id、points、color 和 width。")
        identifier = stroke.get("id")
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", identifier):
            raise DrawingError("路线 ID 无效。")
        if identifier in identifiers:
            raise DrawingError("路线 ID 不能重复。", 409, error_code="stroke_id_conflict")
        identifiers.add(identifier)
        color = stroke.get("color", "#e5484d")
        width = stroke.get("width", 4)
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise DrawingError("路线颜色必须为 #RRGGBB。")
        if type(width) is not int or width not in {2, 4, 6}:
            raise DrawingError("路线宽度必须是 2、4 或 6。")
        points = stroke.get("points")
        if not isinstance(points, list) or not 2 <= len(points) <= MAX_STROKE_POINTS:
            raise DrawingError("每条路线必须包含 2 到 1000 个坐标点。", 400, error_code="drawing_capacity")
        total_points += len(points)
        if total_points > MAX_SCOPE_POINTS:
            raise DrawingError("每个楼层最多保存 12000 个坐标点。", 400, error_code="drawing_capacity")
        for point in points:
            if not isinstance(point, list) or len(point) != 2:
                raise DrawingError("坐标点必须是 [x,y]。")
            if any(type(coordinate) not in {int, float} or not 0 <= coordinate <= 1
                   or not math.isfinite(coordinate) for coordinate in point):
                raise DrawingError("路线坐标必须是 0 到 1 之间的有限数值。")
        result.append({"id": identifier, "points": points, "color": color.lower(), "width": width})
    return result


def normalize_operation(payload: Any) -> dict[str, Any]:
    fields = {"profile_id", "source", "map_id", "floor_key", "operation_id", "operation", "stroke", "strokes", "base_revision"}
    if not isinstance(payload, dict) or set(payload) - fields:
        raise DrawingError("路线操作包含未知参数。")
    scope = drawing_scope(payload.get("source"), payload.get("map_id"), payload.get("floor_key"))
    operation = payload.get("operation")
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise DrawingError("未知路线操作。")
    if not scope["floor_key"] and operation not in {"import_legacy", "undo"}:
        raise DrawingError("请选择明确楼层后修改路线。")
    if scope["floor_key"] and operation == "import_legacy":
        raise DrawingError("旧路线只能导入未分配楼层。")
    identifier = operation_uuid(payload.get("operation_id"))
    result = {**scope, "profile_id": profile_number(payload.get("profile_id")),
              "operation": operation, "operation_id": identifier}
    if "base_revision" in payload:
        result["base_revision"] = revision_number(payload["base_revision"], "base_revision")
    if operation == "append":
        if "strokes" in payload:
            raise DrawingError("append 仅接受 stroke。")
        result["stroke"] = normalize_strokes([payload.get("stroke")])[0]
    elif operation in {"replace", "import_legacy"}:
        if "stroke" in payload:
            raise DrawingError("此操作仅接受 strokes。")
        result["strokes"] = normalize_strokes(payload.get("strokes"))
    elif "stroke" in payload or "strokes" in payload:
        raise DrawingError("此操作不接受路线数据。")
    return result


class MapDrawingStore:
    def __init__(self, connect: Callable[[], ContextManager[sqlite3.Connection]]) -> None:
        self.connect = connect
        with self.connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS map_drawing_scopes (
                profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                provider TEXT NOT NULL, map_id TEXT NOT NULL, floor_key TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 0 CHECK(revision >= 0),
                strokes_json TEXT NOT NULL DEFAULT '[]',
                legacy_imported INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(profile_id, provider, map_id, floor_key))""")
            connection.execute("""CREATE TABLE IF NOT EXISTS map_drawing_operations (
                profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                operation_id TEXT NOT NULL, request_hash TEXT NOT NULL,
                provider TEXT NOT NULL, map_id TEXT NOT NULL, floor_key TEXT NOT NULL,
                PRIMARY KEY(profile_id, operation_id))""")
            connection.execute("""CREATE TABLE IF NOT EXISTS map_drawing_profile_revisions (
                profile_id INTEGER PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
                revision INTEGER NOT NULL DEFAULT 0 CHECK(revision >= 0))""")

    @staticmethod
    def _row(connection: sqlite3.Connection, profile_id: int, scope: dict[str, str]) -> dict[str, Any]:
        row = connection.execute("""SELECT revision, strokes_json, legacy_imported FROM map_drawing_scopes
            WHERE profile_id=? AND provider=? AND map_id=? AND floor_key=?""",
            (profile_id, scope["source"], scope["map_id"], scope["floor_key"])).fetchone()
        return {"revision": row["revision"], "strokes": json.loads(row["strokes_json"]),
                "legacy_imported": bool(row["legacy_imported"])} if row else {
                    "revision": 0, "strokes": [], "legacy_imported": False}

    @classmethod
    def _result(cls, connection: sqlite3.Connection, profile_id: int, scope: dict[str, str]) -> dict[str, Any]:
        current = cls._row(connection, profile_id, scope)
        legacy = current if not scope["floor_key"] else cls._row(connection, profile_id, {**scope, "floor_key": ""})
        return {"profile_id": profile_id, "scope": scope, "revision": current["revision"],
                "strokes": current["strokes"], "legacy_count": len(legacy["strokes"]),
                "legacy_revision": legacy["revision"]}

    def read(self, profile_id: int, source: str, map_id: str, floor_key: str,
             since: int | None = None, operation_id: str | None = None) -> dict[str, Any]:
        profile_number(profile_id)
        scope = drawing_scope(source, map_id, floor_key)
        if since is not None:
            revision_number(since, "since")
        if operation_id is not None:
            operation_id = operation_uuid(operation_id)
        with self.connect() as connection:
            connection.execute("BEGIN")
            result = self._result(connection, profile_id, scope)
            result["operation_applied"] = operation_id is not None and connection.execute(
                """SELECT 1 FROM map_drawing_operations WHERE profile_id=? AND operation_id=?
                AND provider=? AND map_id=? AND floor_key=?""",
                (profile_id, operation_id, source, map_id, floor_key)).fetchone() is not None
        result["unchanged"] = since is not None and since == result["revision"]
        if result["unchanged"]:
            del result["strokes"]
        return result

    def profile_revision(self, profile_id: int) -> int:
        with self.connect() as connection:
            row = connection.execute("SELECT revision FROM map_drawing_profile_revisions WHERE profile_id=?",
                                     (profile_id,)).fetchone()
        return row[0] if row else 0

    @staticmethod
    def _save(connection: sqlite3.Connection, profile_id: int, scope: dict[str, str],
              strokes: list[dict[str, Any]], revision: int, imported: bool = False) -> None:
        connection.execute("""INSERT INTO map_drawing_scopes
            (profile_id, provider, map_id, floor_key, revision, strokes_json, legacy_imported)
            VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(profile_id, provider, map_id, floor_key)
            DO UPDATE SET revision=excluded.revision, strokes_json=excluded.strokes_json,
            legacy_imported=excluded.legacy_imported""",
            (profile_id, scope["source"], scope["map_id"], scope["floor_key"], revision,
             json.dumps(strokes, separators=(",", ":"), allow_nan=False), int(imported)))

    @staticmethod
    def _check_selection(connection: sqlite3.Connection, profile_id: int, source: str) -> None:
        settings = dict(connection.execute("""SELECT setting_key, setting_value FROM app_settings
            WHERE setting_key IN ('selected_profile_id', ?)""", (f"data_source:{profile_id}",)).fetchall())
        if settings.get("selected_profile_id", str(profile_id)) != str(profile_id):
            raise DrawingError("当前档案已切换，请保留待同步路线。", 409, error_code="profile_changed",
                               profile_id=profile_id)
        selected_source = settings.get(f"data_source:{profile_id}", "tarkov.dev")
        if selected_source != source:
            raise DrawingError("当前来源已切换，请保留待同步路线。", 409, error_code="source_changed",
                               profile_id=profile_id, selected_source=selected_source)

    def apply(self, payload: dict[str, Any]) -> dict[str, Any]:
        command = normalize_operation(payload)
        profile_id = command["profile_id"]
        scope = {key: command[key] for key in ("source", "map_id", "floor_key")}
        fingerprint = hashlib.sha256(json.dumps(
            {key: value for key, value in command.items() if key != "base_revision"},
            sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._check_selection(connection, profile_id, scope["source"])
            if not connection.execute("SELECT 1 FROM profiles WHERE id=?", (profile_id,)).fetchone():
                raise DrawingError("找不到路线档案。", 404)
            previous = connection.execute("""SELECT request_hash FROM map_drawing_operations
                WHERE profile_id=? AND operation_id=?""", (profile_id, command["operation_id"])).fetchone()
            if previous:
                if previous[0] != fingerprint:
                    raise DrawingError("operation_id 已被其他路线操作使用。", 409,
                                       error_code="operation_id_conflict", **self._result(connection, profile_id, scope))
                return {**self._result(connection, profile_id, scope), "replayed": True}
            current = self._row(connection, profile_id, scope)
            if "base_revision" in command and command["base_revision"] != current["revision"]:
                raise DrawingError("路线已更新，请读取最新路线后重试。", 409,
                                   error_code="revision_conflict", **self._result(connection, profile_id, scope))
            operation = command["operation"]
            strokes = current["strokes"]
            imported = current["legacy_imported"]
            changed_legacy = None
            if operation == "append":
                strokes = normalize_strokes([*strokes, command["stroke"]])
            elif operation == "undo":
                strokes = strokes[:-1]
            elif operation == "clear":
                strokes = []
            elif operation == "replace":
                strokes = command["strokes"]
            elif operation == "import_legacy":
                if not imported and not strokes:
                    strokes = command["strokes"]
                imported = True
            elif operation == "assign_legacy":
                legacy_scope = {**scope, "floor_key": ""}
                legacy = self._row(connection, profile_id, legacy_scope)
                if legacy["strokes"]:
                    strokes = normalize_strokes([*strokes, *legacy["strokes"]])
                    changed_legacy = (legacy_scope, legacy)
            changed = strokes != current["strokes"]
            if changed or imported != current["legacy_imported"]:
                self._save(connection, profile_id, scope, strokes, current["revision"] + int(changed), imported)
            if changed_legacy:
                legacy_scope, legacy = changed_legacy
                self._save(connection, profile_id, legacy_scope, [], legacy["revision"] + 1, True)
            if changed or changed_legacy:
                connection.execute("""INSERT INTO map_drawing_profile_revisions (profile_id, revision) VALUES (?, 1)
                    ON CONFLICT(profile_id) DO UPDATE SET revision=revision+1""", (profile_id,))
            connection.execute("""INSERT INTO map_drawing_operations
                (profile_id, operation_id, request_hash, provider, map_id, floor_key) VALUES (?, ?, ?, ?, ?, ?)""",
                (profile_id, command["operation_id"], fingerprint, scope["source"], scope["map_id"], scope["floor_key"]))
            return {**self._result(connection, profile_id, scope), "replayed": False}
