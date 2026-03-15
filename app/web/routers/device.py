"""
Device login, logout, and device approval. Same paths and behavior as original.
"""
from __future__ import annotations

import secrets
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth_store import approve_user_code
from app.user_auth import authenticate_user
from app.web.session import DEV_SESSIONS, COOKIE_NAME, get_session, safe_next


router = APIRouter()


@router.get("/device", response_class=HTMLResponse)
def device_page(request: Request):
    session = get_session(request)
    next_url = safe_next(request.query_params.get("next"))
    if not session:
        return f"""
        <html>
          <body style="font-family: sans-serif; max-width: 520px; margin: 40px auto;">
            <h2>Device Login (DEV)</h2>
            <p>Sign in to access Consultations, My tasks, and Tasks.</p>
            <form method="post" action="/login" style="display: grid; gap: 12px;">
              <input type="hidden" name="next" value="{next_url}" />
              <label>Username: <input name="username" required style="width: 100%; padding: 8px;" /></label>
              <label>Password: <input name="password" type="password" required style="width: 100%; padding: 8px;" /></label>
              <button type="submit" style="padding: 10px; cursor: pointer;">Login</button>
            </form>
          </body>
        </html>
        """
    return """
    <html>
      <body style="font-family: sans-serif; max-width: 520px; margin: 40px auto;">
        <h2>Device Login (DEV)</h2>
        <p>Paste the <b>user_code</b> from Claude's auth_start.</p>
        <form method="post" action="/device/approve" style="display: grid; gap: 12px;">
          <label>Code (user_code): <input name="user_code" required style="width: 100%; padding: 8px;" placeholder="ABCD-EFGH" /></label>
          <button type="submit" style="padding: 10px; cursor: pointer;">Approve</button>
        </form>
        <p><a href="/consultations">Consultations</a> | <a href="/tasks">Tasks</a> | <a href="/my-tasks">My tasks</a> | <a href="/logout">Logout</a></p>
      </body>
    </html>
    """


@router.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str | None = Form(None),
):
    auth = authenticate_user(username.strip(), password)
    if not auth:
        return """
        <html><body style="font-family: sans-serif; max-width: 520px; margin: 40px auto;">
          <h3>Login failed</h3>
          <p>Invalid username or password.</p>
          <a href="/device">Try again</a>
        </body></html>
        """
    user_id, role = auth
    token = secrets.token_urlsafe(24)
    DEV_SESSIONS[token] = {"user_id": user_id, "role": role}
    redirect_url = safe_next(next) if next else "/consultations"
    r = RedirectResponse(url=redirect_url, status_code=302)
    r.set_cookie(key=COOKIE_NAME, value=token, httponly=True, path="/", samesite="lax")
    return r


@router.get("/logout", response_class=RedirectResponse)
def logout(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        DEV_SESSIONS.pop(token, None)
    r = RedirectResponse(url="/device", status_code=302)
    r.delete_cookie(COOKIE_NAME)
    return r


@router.post("/device/approve", response_class=HTMLResponse)
def device_approve(request: Request, user_code: str = Form(...)):
    session = get_session(request)
    if not session:
        return """
        <html><body style="font-family: sans-serif; max-width: 520px; margin: 40px auto;">
          <h3>Not logged in</h3>
          <a href="/device">Login first</a>
        </body></html>
        """
    user_id = session["user_id"]
    role = (session.get("role") or "").strip().lower()
    code = user_code.strip().upper().replace(" ", "-")
    ok = approve_user_code(user_code=code, user_id=user_id, role=role)
    if ok:
        return """
        <html><body style="font-family: sans-serif; max-width: 520px; margin: 40px auto;">
          <h3>Approved</h3>
          <p>Go back to Claude; auth_status should return session_id.</p>
          <a href="/device">Approve another</a>
        </body></html>
        """
    return """
    <html><body style="font-family: sans-serif; max-width: 520px; margin: 40px auto;">
      <h3>Invalid or expired code</h3>
      <p>In Claude, call <b>auth_start</b> first, then paste the <b>user_code</b> here. If it still fails, the code may have expired (try auth_start again).</p>
      <a href="/device">Try again</a>
    </body></html>
    """
