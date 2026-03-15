"""
Tasks API: create, assign, get, submissions, my/tasks, link-repo, submit. Same paths and behavior as original.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.queries import tasks as tq
from app.web.session import require_session


router = APIRouter()


def _api_my_tasks_impl(request: Request):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    student_index = identity.get("student_index")
    if student_index is None:
        return JSONResponse({"error": "Student account required"}, status_code=403)
    out = tq.list_my_assignments(student_index)
    response = JSONResponse({"tasks": out})
    response.headers["Cache-Control"] = "no-store, no-cache"
    return response


@router.post("/tasks")
async def api_create_task(request: Request):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    if (identity.get("role") or "").lower() not in ("professor", "admin"):
        return JSONResponse({"error": "Professor or admin only"}, status_code=403)
    professor_id = identity.get("professor_id")
    if professor_id is None and identity.get("role") != "admin":
        return JSONResponse({"error": "Professor account required"})
    body = await request.json()
    title = body.get("title")
    description = body.get("description")
    subject_id = body.get("subject_id")
    if not title or not description or not subject_id:
        return JSONResponse({"error": "title, description, subject_id required"})
    deadline = body.get("deadline")
    deadline_dt = None
    if deadline:
        try:
            from datetime import datetime, timezone
            if isinstance(deadline, str):
                deadline_dt = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
            else:
                deadline_dt = deadline
        except (ValueError, TypeError):
            pass
    if identity.get("role") == "admin" and professor_id is None:
        professor_id = body.get("created_by_professor_id")
        if not professor_id:
            return JSONResponse({"error": "admin must pass created_by_professor_id"})
    try:
        out = tq.create_task(professor_id, title, description, subject_id, deadline_dt)
        return JSONResponse(out)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/tasks/{task_id:int}/assign-subject-students")
def api_assign_task(task_id: int, request: Request):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    if (identity.get("role") or "").lower() not in ("professor", "admin"):
        return JSONResponse({"error": "Professor or admin only"}, status_code=403)
    professor_id = identity.get("professor_id")
    if professor_id is None and identity.get("role") != "admin":
        return JSONResponse({"error": "Professor account required"})
    try:
        out = tq.assign_task_to_subject_students(task_id, professor_id)
        return JSONResponse(out)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.get("/tasks/{task_id:int}")
def api_get_task(task_id: int, request: Request):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    if (identity.get("role") or "").lower() not in ("professor", "admin"):
        return JSONResponse({"error": "Professor or admin only"}, status_code=403)
    professor_id = identity.get("professor_id")
    if professor_id is None:
        professor_id = 0
    out = tq.get_task_for_professor(task_id, professor_id)
    if not out:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    return JSONResponse(out)


@router.get("/tasks/{task_id:int}/submissions")
def api_task_submissions(task_id: int, request: Request):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    if (identity.get("role") or "").lower() not in ("professor", "admin"):
        return JSONResponse({"error": "Professor or admin only"}, status_code=403)
    professor_id = identity.get("professor_id")
    if professor_id is None:
        professor_id = 0
    out = tq.get_submission_overview_for_professor(task_id, professor_id)
    if not out:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    return JSONResponse(out)


@router.get("/my/tasks")
def api_my_tasks(request: Request):
    return _api_my_tasks_impl(request)


@router.get("/api/my-tasks")
def api_my_tasks_alt(request: Request):
    return _api_my_tasks_impl(request)


@router.get("/api/debug-my-tasks")
def api_debug_my_tasks(request: Request):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated", "student_index": None, "task_count": 0})
    student_index = identity.get("student_index")
    if student_index is None:
        return JSONResponse({"error": "No student_index", "student_index": None, "task_count": 0})
    try:
        tasks = tq.list_my_assignments(student_index)
        return JSONResponse({"student_index": student_index, "task_count": len(tasks or []), "tasks": tasks or []})
    except Exception as e:
        return JSONResponse({"error": str(e), "student_index": student_index, "task_count": 0})


@router.get("/my/tasks/{assignment_id:int}")
def api_my_task_detail(assignment_id: int, request: Request):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    student_index = identity.get("student_index")
    if student_index is None:
        return JSONResponse({"error": "Student account required"}, status_code=403)
    out = tq.get_my_assignment(student_index, assignment_id)
    if not out:
        return JSONResponse({"error": "Assignment not found"}, status_code=404)
    return JSONResponse(out)


@router.post("/my/tasks/{assignment_id:int}/link-repo")
async def api_link_repo(assignment_id: int, request: Request):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    student_index = identity.get("student_index")
    user_id = identity.get("user_id")
    if student_index is None:
        return JSONResponse({"error": "Student account required"}, status_code=403)
    if not user_id:
        return JSONResponse({"error": "User not found"})
    body = await request.json()
    repo_owner = (body.get("repo_owner") or "").strip()
    repo_name = (body.get("repo_name") or "").strip()
    if not repo_owner or not repo_name:
        return JSONResponse({"error": "repo_owner and repo_name required"})
    repo_url = (body.get("repo_url") or "").strip()
    branch = (body.get("branch") or "main").strip()
    try:
        out = tq.link_repo_to_assignment(
            student_index, assignment_id, repo_owner, repo_name, repo_url, branch, user_id
        )
        return JSONResponse(out)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/my/tasks/{assignment_id:int}/submit")
def api_submit_task(assignment_id: int, request: Request):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    student_index = identity.get("student_index")
    user_id = identity.get("user_id")
    if student_index is None:
        return JSONResponse({"error": "Student account required"}, status_code=403)
    if not user_id:
        return JSONResponse({"error": "User not found"})
    try:
        out = tq.submit_assignment(student_index, assignment_id, user_id)
        return JSONResponse(out)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)