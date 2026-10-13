from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import time
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from storage import default_database_path


PASSWORD_ITERATIONS = 310_000
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
    def _normalize_username(username: str) -> tuple[str, str]:
        normalized = unicodedata.normalize("NFKC", username).strip()
        if not normalized or len(normalized) > 32:
            raise ValueError("玩家名称需为 1–32 个字符。")
        if any(character.isspace() or ord(character) < 32 for character in normalized):
            raise ValueError("玩家名称不能包含空白或控制字符。")
        return normalized, normalized.casefold()

    @staticmethod
    def _validate_password(password: str) -> None:
        if len(password) < 8:
            raise ValueError("密码至少需要 8 个字符。")
        if len(password) > 256:
            raise ValueError("密码不能超过 256 个字符。")

    @staticmethod
    def _password_hash(password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
        )

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("ascii")).hexdigest()

    def has_players(self) -> bool:
        with self._connect() as connection:
            return connection.execute("SELECT 1 FROM players LIMIT 1").fetchone() is not None

    def register(self, username: str, password: str) -> tuple[Player, str]:
        normalized, username_key = self._normalize_username(username)
        self._validate_password(password)
        player_id = secrets.token_hex(16)
        token = secrets.token_urlsafe(32)
        salt = secrets.token_bytes(16)
        password_hash = self._password_hash(password, salt)
        now = int(time.time())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            is_admin = connection.execute("SELECT 1 FROM players LIMIT 1").fetchone() is None
            try:
                connection.execute(
                    """
                    INSERT INTO players (id, username, username_key, salt, password_hash, is_admin, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (player_id, normalized, username_key, salt, password_hash, int(is_admin), now),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("这个玩家名称已经被使用。") from error
            self._save_session(connection, player_id, token, now)
        return Player(player_id, normalized, is_admin), token

    def login(self, username: str, password: str) -> tuple[Player, str] | None:
        normalized, username_key = self._normalize_username(username)
        if len(password) > 256:
            return None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM players WHERE username_key = ?", (username_key,)
            ).fetchone()
        if row is None:
            self._password_hash(password, b"\x00" * 16)
            return None
        actual_hash = self._password_hash(password, bytes(row["salt"]))
        if not hmac.compare_digest(actual_hash, bytes(row["password_hash"])):
            return None
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        with self._connect() as connection:
            self._save_session(connection, str(row["id"]), token, now)
        player = Player(str(row["id"]), str(row["username"]), bool(row["is_admin"]))
        return player, token

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
                raise ValueError("找不到玩家账号。")
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
