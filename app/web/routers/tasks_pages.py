"""
Tasks pages: GET /tasks (professor), GET /my-tasks (student). Same behavior as original.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.session import require_session
from app.web.responses import redirect_to_login
from app.web.html.tasks import tasks_professor_html, my_tasks_student_html


router = APIRouter()


@router.get("/tasks", response_class=HTMLResponse)
def tasks_page(request: Request):
    session, identity = require_session(request)
    if not session or not identity:
        return redirect_to_login("/tasks")
    role = (identity.get("role") or "").lower()
    if role not in ("professor", "admin"):
        return RedirectResponse(url="/my-tasks", status_code=302)
    return tasks_professor_html(identity)


@router.get("/my-tasks", response_class=HTMLResponse)
def my_tasks_page(request: Request):
    session, identity = require_session(request)
    if not session or not identity:
        return redirect_to_login("/my-tasks")
    role = (identity.get("role") or "").lower()
    if role != "student":
        return RedirectResponse(url="/tasks", status_code=302)
    resp = my_tasks_student_html(identity)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp