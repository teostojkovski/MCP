"""
Subjects API: GET /tasks/api/subjects. Same path and behavior as original.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.queries.subjects import search_subjects
from app.web.session import require_session


router = APIRouter()


@router.get("/tasks/api/subjects")
def api_list_subjects(request: Request):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    subjects = search_subjects(limit=500)
    return JSONResponse({"subjects": subjects})