"""
In-memory DEV session storage and identity resolution.
Preserves exact behavior: cookie name, session dict shape, identity from User table.
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import Request
from app.db import SessionLocal
from app.models import User, Professor

DEV_SESSIONS: dict[str, dict] = {}
COOKIE_NAME = "dev_session"


def get_session(request: Request) -> dict | None:
    token = request.cookies.get(COOKIE_NAME)
    return DEV_SESSIONS.get(token) if token else None


def get_user_identity_from_session(session: dict) -> dict | None:
    """Resolve session (user_id, role) to professor_id / student_index / user_id (internal) from User table."""
    if not session:
        return None
    username = session.get("user_id")
    role = (session.get("role") or "").strip().lower()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return {"role": role, "professor_id": None, "student_index": None, "user_id": None, "username": username}
        professor_id = getattr(user, "professor_id", None)
        if professor_id is None and role == "professor" and username:
            m = re.match(r"^prof_(\d+)$", (username or "").strip(), re.IGNORECASE)
            if m:
                try:
                    pid = int(m.group(1))
                    if db.query(Professor).filter(Professor.id == pid).first():
                        user.professor_id = pid
                        try:
                            db.commit()
                        except Exception:
                            db.rollback()
                        professor_id = pid
                except (ValueError, IndexError):
                    pass
        return {
            "role": role,
            "professor_id": professor_id,
            "student_index": getattr(user, "student_index", None),
            "user_id": user.id,
            "username": username,
        }
    finally:
        db.close()


def safe_next(next_val: str | None) -> str:
    """Allow only relative paths (no open redirect)."""
    if not next_val or not next_val.strip().startswith("/") or "//" in next_val.strip():
        return "/consultations"
    return next_val.strip().split("?")[0] or "/consultations"


def require_session(request: Request) -> tuple[dict | None, dict | None]:
    """Return (session, identity) or (None, None) if not logged in."""
    session = get_session(request)
    if not session:
        return None, None
    identity = get_user_identity_from_session(session)
    return session, identity
