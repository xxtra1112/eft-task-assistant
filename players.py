from __future__ import annotations

import hashlib
import secrets
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from storage import default_database_path


SESSION_LIFETIME_SECONDS = 30 * 24 * 60 * 60
MOBILE_PAIRING_LIFETIME_SECONDS = 120


@dataclass(frozen=True)
class Player:
    id: str
    username: str
    is_admin: bool

    def public_data(self) -> dict[str, str | bool]:
        return {"id": self.id, "username": self.username, "is_admin": self.is_admin}


class PlayerAuthStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or default_database_path().parent
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "players.sqlite3"
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
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

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS players (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    username_key TEXT NOT NULL UNIQUE,
                    salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    is_admin INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    player_id TEXT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                    expires_at INTEGER NOT NULL,
                    scope TEXT NOT NULL DEFAULT 'full'
                )
                """
            )
            session_columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(sessions)").fetchall()
            }
            if "scope" not in session_columns:
                connection.execute(
                    "ALTER TABLE sessions ADD COLUMN scope TEXT NOT NULL DEFAULT 'full'"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS sessions_expiry_idx ON sessions(expires_at)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mobile_pairing_tokens (
                    token_hash TEXT PRIMARY KEY,
                    player_id TEXT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                    expires_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS mobile_pairing_expiry_idx ON mobile_pairing_tokens(expires_at)"
            )

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("ascii")).hexdigest()

    def local_player(self) -> Player:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT id FROM players WHERE is_admin = 1 ORDER BY created_at, id LIMIT 1"
            ).fetchone()
            if row is None:
                player_id = secrets.token_hex(16)
                username = "本地档案"
                salt = secrets.token_bytes(16)
                password_hash = secrets.token_bytes(32)
                connection.execute(
                    """
                    INSERT INTO players (id, username, username_key, salt, password_hash, is_admin, created_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                    """,
                    (
                        player_id,
                        username,
                        f"__local_installation_{player_id}",
                        salt,
                        password_hash,
                        int(time.time()),
                    ),
                )
                return Player(player_id, username, True)
        return Player(str(row["id"]), "本地档案", True)

    @staticmethod
    def _save_session(
        connection: sqlite3.Connection,
        player_id: str,
        token: str,
        now: int,
        scope: str = "full",
    ) -> None:
        connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        connection.execute(
            "INSERT INTO sessions (token_hash, player_id, expires_at, scope) VALUES (?, ?, ?, ?)",
            (
                PlayerAuthStore._token_hash(token),
                player_id,
                now + SESSION_LIFETIME_SECONDS,
                scope,
            ),
        )

    def authenticate(self, token: str | None) -> Player | None:
        if not token or len(token) > 256:
            return None
        try:
            token_hash = self._token_hash(token)
        except UnicodeEncodeError:
            return None
        now = int(time.time())
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT players.id, players.username, players.is_admin, sessions.expires_at
                FROM sessions JOIN players ON players.id = sessions.player_id
                WHERE sessions.token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            if row is None:
                return None
            if int(row["expires_at"]) <= now:
                connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
                return None
        return Player(str(row["id"]), str(row["username"]), bool(row["is_admin"]))

    def session_scope(self, token: str | None) -> str | None:
        if not token or len(token) > 256:
            return None
        try:
            token_hash = self._token_hash(token)
        except UnicodeEncodeError:
            return None
        now = int(time.time())
        with self._connect() as connection:
            row = connection.execute(
                "SELECT scope, expires_at FROM sessions WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()
            if row is None:
                return None
            if int(row["expires_at"]) <= now:
                connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
                return None
        return str(row["scope"])

    def logout(self, token: str | None) -> None:
        if not token or len(token) > 256:
            return
        try:
            token_hash = self._token_hash(token)
        except UnicodeEncodeError:
            return
        with self._connect() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))

    def has_live_session(self, player_id: str) -> bool:
        with self._connect() as connection:
            return connection.execute(
                "SELECT 1 FROM sessions WHERE player_id = ? AND expires_at > ? LIMIT 1",
                (player_id, int(time.time())),
            ).fetchone() is not None

    def create_mobile_pairing_token(self, player_id: str) -> tuple[str, int]:
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        expires_at = now + MOBILE_PAIRING_LIFETIME_SECONDS
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            player_exists = connection.execute(
                "SELECT 1 FROM players WHERE id = ?", (player_id,)
            ).fetchone()
            if player_exists is None:
                raise ValueError("找不到本机档案身份。")
            connection.execute(
                "DELETE FROM mobile_pairing_tokens WHERE player_id = ? OR expires_at <= ?",
                (player_id, now),
            )
            connection.execute(
                "INSERT INTO mobile_pairing_tokens (token_hash, player_id, expires_at) VALUES (?, ?, ?)",
                (self._token_hash(token), player_id, expires_at),
            )
        return token, expires_at

    def consume_mobile_pairing_token(self, token: str | None) -> tuple[Player, str] | None:
        if not token or len(token) > 128:
            return None
        try:
            token_hash = self._token_hash(token)
        except UnicodeEncodeError:
            return None
        now = int(time.time())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT players.id, players.username, players.is_admin, mobile_pairing_tokens.expires_at
                FROM mobile_pairing_tokens
                JOIN players ON players.id = mobile_pairing_tokens.player_id
                WHERE mobile_pairing_tokens.token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "DELETE FROM mobile_pairing_tokens WHERE token_hash = ?", (token_hash,)
            )
            if int(row["expires_at"]) <= now:
                return None
            session_token = secrets.token_urlsafe(32)
            self._save_session(connection, str(row["id"]), session_token, now, "mobile")
            player = Player(str(row["id"]), str(row["username"]), bool(row["is_admin"]))
        return player, session_token

    def cancel_mobile_pairing_tokens(self, player_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM mobile_pairing_tokens WHERE player_id = ?", (player_id,)
            )

    def database_path(self, player: Player) -> Path:
        if player.is_admin:
            return self.root / default_database_path().name
        player_directory = self.root / "players"
        player_directory.mkdir(parents=True, exist_ok=True)
        return player_directory / f"{player.id}.sqlite3"
