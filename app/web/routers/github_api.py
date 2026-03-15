"""
GitHub API: /github/link, /github/me, /github/repos. Same paths and behavior as original.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import github_service as gh_service
from app.web.session import get_session, require_session


router = APIRouter()
_log = logging.getLogger("dev_run.github_link")


@router.post("/github/link")
async def api_github_link(request: Request):
    try:
        body = await request.json()
    except Exception as e:
        _log.warning("github/link: invalid body: %s", e)
        return JSONResponse({"error": "Invalid request body (expected JSON): " + str(e)}, status_code=400)
    body = body or {}
    _, identity = require_session(request)
    if not identity:
        _log.warning("github/link: not authenticated")
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    user_id = identity.get("user_id")
    if not user_id:
        _log.warning("github/link: user_id missing for %s", identity.get("username"))
        return JSONResponse({"error": "User not found"}, status_code=400)
    github_username = (body.get("github_username") or "").strip()
    if not github_username:
        return JSONResponse({"error": "github_username required"}, status_code=400)
    _log.info("github/link: user_id=%s username=%s linking gh=%s", user_id, identity.get("username"), github_username)
    try:
        out = gh_service.link_account(
            user_id=user_id,
            github_username=github_username,
            github_user_id=body.get("github_user_id"),
            access_token=body.get("access_token"),
        )
        _log.info("github/link: success for user_id=%s", user_id)
        return JSONResponse(out)
    except ValueError as e:
        _log.warning("github/link: validation failed: %s", e)
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        _log.exception("github/link: unexpected error")
        return JSONResponse({"error": str(e)}, status_code=400)


@router.get("/github/me")
def api_github_me(request: Request):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    username = get_session(request)
    if not username:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    username_str = username.get("user_id") if isinstance(username, dict) else None
    if not username_str:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    out = gh_service.get_linked_account_for_username(username_str)
    if not out:
        return JSONResponse({"linked": False})
    return JSONResponse({"linked": True, "account": out})


@router.get("/github/repos")
def api_github_repos(request: Request):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    if identity.get("student_index") is None:
        return JSONResponse({"error": "Student account required"}, status_code=403)
    user_id = identity.get("user_id")
    if not user_id:
        return JSONResponse({"error": "User not found"}, status_code=400)
    repos, err = gh_service.list_repositories_for_user(user_id)
    if err:
        return JSONResponse({"error": err, "repos": []})
    return JSONResponse({"repos": repos})