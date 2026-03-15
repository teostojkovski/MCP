"""
Reusable auth/identity checks for routes. Return (identity, None) or (None, error_response).
Behavior identical to existing route checks.
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from app.web.session import require_session


def require_authenticated(request: Request) -> tuple[dict | None, JSONResponse | None]:
    """Require logged-in user. Returns (identity, None) or (None, 401 JSONResponse)."""
    _, identity = require_session(request)
    if not identity:
        return None, JSONResponse({"error": "Not authenticated"}, status_code=401)
    return identity, None


def require_student(request: Request) -> tuple[dict | None, JSONResponse | None]:
    """Require student identity. Returns (identity, None) or (None, 401/403 JSONResponse)."""
    identity, err = require_authenticated(request)
    if err:
        return None, err
    if identity.get("student_index") is None:
        return None, JSONResponse({"error": "Student account required"}, status_code=403)
    return identity, None


def require_professor_or_admin(request: Request) -> tuple[dict | None, JSONResponse | None]:
    """Require professor or admin. Returns (identity, None) or (None, 401/403 JSONResponse)."""
    identity, err = require_authenticated(request)
    if err:
        return None, err
    role = (identity.get("role") or "").lower()
    if role not in ("professor", "admin"):
        return None, JSONResponse({"error": "Professor or admin only"}, status_code=403)
    return identity, None


def require_professor_ownership(identity: dict, professor_id: int) -> JSONResponse | None:
    """If current user is professor (not admin), must match professor_id. Returns 403 response or None."""
    role = (identity.get("role") or "").lower()
    if role == "professor" and identity.get("professor_id") != professor_id:
        return JSONResponse({"error": "Forbidden"})
    return None
