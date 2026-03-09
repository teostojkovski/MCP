from __future__ import annotations

import sqlite3
import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).resolve().parent.parent / "auth_store.db"


def _conn():
    c = sqlite3.connect(_DB_PATH, timeout=10.0)
    c.row_factory = sqlite3.Row
    return c


def _init_db():
    global _init_db_executed
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS pending_logins (
                device_code TEXT PRIMARY KEY,
                user_code TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                approved INTEGER NOT NULL DEFAULT 0,
                user_id TEXT,
                role TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
        """)
    _init_db_executed = True


_init_db_executed = False


def _ensure_db():
    global _init_db_executed
    if not _init_db_executed:
        _init_db()
        _init_db_executed = True


@dataclass
class PendingLogin:
    device_code: str
    user_code: str
    created_at: datetime
    expires_at: datetime
    approved: bool = False
    user_id: Optional[str] = None
    role: Optional[str] = None


@dataclass
class Session:
    session_id: str
    user_id: str
    role: str
    created_at: datetime
    expires_at: datetime


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _gen_token(num_bytes: int = 24) -> str:
    return secrets.token_urlsafe(num_bytes)


def _gen_user_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    part1 = "".join(secrets.choice(alphabet) for _ in range(4))
    part2 = "".join(secrets.choice(alphabet) for _ in range(4))
    return f"{part1}-{part2}"


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def create_pending_login(ttl_minutes: int = 10) -> PendingLogin:
    if ttl_minutes <= 0:
        raise ValueError("ttl_minutes must be > 0")
    _ensure_db()

    now = _now()
    expires = now + timedelta(minutes=ttl_minutes)
    device_code = _gen_token(24)
    user_code = _gen_user_code()

    with _conn() as c:
        _cleanup_expired_conn(c)
        while True:
            cur = c.execute(
                "SELECT 1 FROM pending_logins WHERE device_code = ?", (
                    device_code,)
            )
            if cur.fetchone() is None:
                break
            device_code = _gen_token(24)
        c.execute(
            """INSERT INTO pending_logins (device_code, user_code, created_at, expires_at, approved)
               VALUES (?, ?, ?, ?, 0)""",
            (device_code, user_code, _iso(now), _iso(expires)),
        )

    return PendingLogin(
        device_code=device_code,
        user_code=user_code,
        created_at=now,
        expires_at=expires,
    )


def _cleanup_expired_conn(c: sqlite3.Connection) -> None:
    now = _iso(_now())
    c.execute("DELETE FROM pending_logins WHERE expires_at <= ?", (now,))
    c.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))


def approve_user_code(user_code: str, user_id: str, role: str) -> bool:
    if not user_code or not user_id or not role:
        return False
    role = (str(role) or "").strip().lower()
    if not role:
        return False
    _ensure_db()
    now = _iso(_now())

    with _conn() as c:
        _cleanup_expired_conn(c)
        cur = c.execute(
            """UPDATE pending_logins SET approved = 1, user_id = ?, role = ?
               WHERE user_code = ? AND expires_at > ?""",
            (str(user_id), role, user_code, now),
        )
        if cur.rowcount == 0:
            return False
    return True


def exchange_device_code_for_session(device_code: str, ttl_hours: int = 8) -> Optional[Session]:
    if not device_code:
        return None
    if ttl_hours <= 0:
        raise ValueError("ttl_hours must be > 0")
    _ensure_db()
    now = _now()
    now_iso = _iso(now)
    expires_at = now + timedelta(hours=ttl_hours)

    with _conn() as c:
        _cleanup_expired_conn(c)
        row = c.execute(
            """SELECT device_code, user_code, created_at, expires_at, approved, user_id, role
               FROM pending_logins WHERE device_code = ?""",
            (device_code,),
        ).fetchone()
        if not row:
            return None
        if row["expires_at"] <= now_iso:
            c.execute(
                "DELETE FROM pending_logins WHERE device_code = ?", (device_code,))
            return None
        if not row["approved"] or not row["user_id"] or not row["role"]:
            return None

        session_id = _gen_token(24)
        while True:
            exists = c.execute(
                "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            if not exists:
                break
            session_id = _gen_token(24)

        c.execute(
            """INSERT INTO sessions (session_id, user_id, role, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, row["user_id"], row["role"],
             _iso(now), _iso(expires_at)),
        )
        c.execute("DELETE FROM pending_logins WHERE device_code = ?",
                  (device_code,))

    role = (row["role"] or "").strip().lower()
    return Session(
        session_id=session_id,
        user_id=row["user_id"],
        role=role,
        created_at=now,
        expires_at=expires_at,
    )


def get_session(session_id: str) -> Optional[Session]:
    if not session_id:
        return None
    _ensure_db()
    now_iso = _iso(_now())

    with _conn() as c:
        _cleanup_expired_conn(c)
        row = c.execute(
            """SELECT session_id, user_id, role, created_at, expires_at
               FROM sessions WHERE session_id = ? AND expires_at > ?""",
            (session_id, now_iso),
        ).fetchone()
    if not row:
        return None
    role = (row["role"] or "").strip().lower()
    return Session(
        session_id=row["session_id"],
        user_id=row["user_id"],
        role=role,
        created_at=_parse_dt(row["created_at"]),
        expires_at=_parse_dt(row["expires_at"]),
    )
