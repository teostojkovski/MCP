"""
Consultations page: GET /consultations. Same behavior as original.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.session import require_session
from app.web.html.consultations import (
    consultations_student_html,
    consultations_professor_html,
    consultations_admin_html,
)


router = APIRouter()


@router.get("/consultations", response_class=HTMLResponse)
def consultations_page(request: Request):
    session, identity = require_session(request)
    if not session or not identity:
        return RedirectResponse(url="/device", status_code=302)
    role = identity.get("role") or ""
    nav = '<p><a href="/device">Device login</a> | <a href="/consultations">Consultations</a> | <a href="/tasks">Tasks</a> | <a href="/my-tasks">My tasks</a> | <a href="/logout">Logout</a></p>'
    if role == "student":
        return consultations_student_html(nav, identity)
    if role == "professor":
        return consultations_professor_html(nav, identity)
    if role == "admin":
        return consultations_admin_html(nav, identity)
    return HTMLResponse(f"<html><body>{nav}<p>Role {role!r} cannot access consultations.</p></body></html>")