"""
Device-login user auth: password hashing and DB lookup. No new dependencies (hashlib only).
"""
import hashlib
from typing import Optional, Tuple

from app.db import SessionLocal
from app.models import User

SALT = "student-grade-mcp-dev"


def _hash_password(username: str, password: str) -> str:
    return hashlib.sha256((SALT + username + password).encode()).hexdigest()


def authenticate_user(username: str, password: str) -> Optional[Tuple[str, str]]:
    """
    Verify username/password against users table. Returns (user_id, role) or None.
    user_id is the username (used as session identity).
    """
    if not username or not password:
        return None
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.username == username.strip()).first()
        if not user:
            return None
        want = _hash_password(user.username, password)
        if want != user.password_hash:
            return None
        return (user.username, user.role)
    finally:
        session.close()


def hash_password_for_store(username: str, password: str) -> str:
    """For seeding: compute hash to store in User.password_hash."""
    return _hash_password(username, password)
