"""
GitHub integration: link account, list repos, validate repo, get latest commit SHA.
Uses httpx if available; otherwise requests. Token stored per-user in GitHubAccount.
Supports public repos without token; token optional for listing/validating private repos.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from app.db import SessionLocal
from app.models import GitHubAccount, User

logger = logging.getLogger(__name__)

# Optional: use env for default token when not per-user (e.g. server-side app)
GITHUB_API_BASE = os.getenv("GITHUB_API_BASE", "https://api.github.com")


def _get_http_client():
    try:
        import httpx
        return httpx
    except ImportError:
        try:
            import requests
            return requests
        except ImportError:
            return None


def _github_request(
    method: str,
    path: str,
    token: Optional[str] = None,
    timeout: float = 15.0,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], int]:
    """
    Call GitHub API. path is relative to GITHUB_API_BASE (e.g. /users/foo).
    Returns (response_json, error_message, status_code). If success, error_message is None.
    """
    client = _get_http_client()
    if not client:
        return None, "HTTP client not available (install httpx or requests)", 0
    url = f"{GITHUB_API_BASE}{path}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    try:
        if method.upper() != "GET":
            return None, "Only GET supported", 0
        r = client.get(url, headers=headers, timeout=timeout)
        if r.status_code != 200:
            msg = getattr(r, "text", None) or str(r)
            try:
                data = r.json() if hasattr(r, "json") else {}
                msg = data.get("message", msg)
            except Exception:
                pass
            return None, msg or f"HTTP {r.status_code}", r.status_code
        data = r.json()
        return data, None, r.status_code
    except Exception as e:
        logger.exception("GitHub API request failed: %s %s", path, e)
        return None, str(e), 0


def get_linked_account_for_user(user_id: int) -> Optional[GitHubAccount]:
    """Get GitHubAccount for user_id (User.id). One per user."""
    session = SessionLocal()
    try:
        return (
            session.query(GitHubAccount)
            .filter(GitHubAccount.user_id == user_id)
            .first()
        )
    finally:
        session.close()


def get_linked_account_for_username(username: str) -> Optional[Dict[str, Any]]:
    """Resolve username to User.id then return linked GitHub account as dict (no token)."""
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.username == username).first()
        if not user:
            return None
        gh = (
            session.query(GitHubAccount)
            .filter(GitHubAccount.user_id == user.id)
            .first()
        )
        if not gh:
            return None
        return {
            "id": gh.id,
            "user_id": gh.user_id,
            "github_username": gh.github_username,
            "github_user_id": gh.github_user_id,
            "connected_at": gh.connected_at.isoformat() if gh.connected_at else None,
        }
    finally:
        session.close()


def _github_get_user(github_username: str, token: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Verify GitHub user exists. Returns (user_data, error_message).
    Works without token for public profiles (rate limit lower).
    """
    path = f"/users/{github_username}"
    data, err, status = _github_request("GET", path, token=token, timeout=10.0)
    if err:
        if status == 404:
            return None, "GitHub username not found"
        return None, err or "GitHub user lookup failed"
    if not data or not data.get("login"):
        return None, "GitHub username not found"
    logger.debug("GitHub user found: %s id=%s", data.get("login"), data.get("id"))
    return data, None


def link_account(
    user_id: int,
    github_username: str,
    github_user_id: Optional[str] = None,
    access_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Link GitHub account to user. Validates that the GitHub user exists via API, then saves.
    One account per user; upserts. Store token as-is (TODO: encrypt if required by security policy).
    """
    github_username = (github_username or "").strip()
    if not github_username:
        raise ValueError("github_username is required")

    # Validate GitHub user exists and get github_user_id
    user_data, err = _github_get_user(github_username, access_token)
    if err:
        logger.warning("GitHub link failed for user_id=%s username=%s: %s", user_id, github_username, err)
        raise ValueError(err)
    resolved_user_id = str(user_data.get("id", "")) if user_data else (github_user_id or "")

    session = SessionLocal()
    try:
        existing = (
            session.query(GitHubAccount)
            .filter(GitHubAccount.user_id == user_id)
            .first()
        )
        token_to_store = access_token  # TODO: encrypt for production
        if existing:
            existing.github_username = github_username
            existing.github_user_id = resolved_user_id
            if access_token is not None:
                existing.access_token_encrypted = token_to_store
            session.commit()
            session.refresh(existing)
            logger.info("GitHub account updated for user_id=%s: %s", user_id, github_username)
            return {
                "id": existing.id,
                "user_id": existing.user_id,
                "github_username": existing.github_username,
                "connected_at": existing.connected_at.isoformat() if existing.connected_at else None,
            }
        gh = GitHubAccount(
            user_id=user_id,
            github_username=github_username,
            github_user_id=resolved_user_id,
            access_token_encrypted=token_to_store,
        )
        session.add(gh)
        session.commit()
        session.refresh(gh)
        logger.info("GitHub account linked for user_id=%s: %s", user_id, github_username)
        return {
            "id": gh.id,
            "user_id": gh.user_id,
            "github_username": gh.github_username,
            "connected_at": gh.connected_at.isoformat() if gh.connected_at else None,
        }
    finally:
        session.close()


def _token_for_account(account: GitHubAccount) -> Optional[str]:
    return getattr(account, "access_token_encrypted", None) or None


def list_repositories_for_user(user_id: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    List repos for the linked GitHub account. With token: list repos the user can see.
    Without token: list public repos for the linked username only.
    Returns (repos_list, error_message). If error_message is set, repos_list may be empty.
    """
    session = SessionLocal()
    try:
        account = (
            session.query(GitHubAccount)
            .filter(GitHubAccount.user_id == user_id)
            .first()
        )
        if not account:
            return [], "No linked GitHub account for this user"
        token = _token_for_account(account)
        username = (account.github_username or "").strip()
        if not username:
            return [], "Linked GitHub account has no username"
        if token:
            repos = _github_list_repos_authenticated(token)
        else:
            repos = _github_list_repos_public(username)
        return repos, None
    finally:
        session.close()


def _github_list_repos_public(username: str) -> List[Dict[str, Any]]:
    """List public repos for a user (no auth). GET /users/:username/repos."""
    path = f"/users/{username}/repos?per_page=100&sort=updated&type=owner"
    data, err, _ = _github_request("GET", path, token=None, timeout=15.0)
    if err or not data:
        if err:
            logger.debug("List public repos for %s failed: %s", username, err)
        return []
    out = []
    for repo in data if isinstance(data, list) else []:
        full_name = repo.get("full_name") or ""
        owner_obj = repo.get("owner", {}) or {}
        owner_login = owner_obj.get("login", "") if isinstance(owner_obj, dict) else ""
        if "/" in full_name:
            owner_str, name = full_name.split("/", 1)
        else:
            owner_str = owner_login
            name = repo.get("name", "")
        out.append({
            "full_name": full_name,
            "owner": owner_login or (full_name.split("/", 1)[0] if "/" in full_name else owner_str),
            "name": name or repo.get("name", ""),
            "clone_url": repo.get("clone_url"),
            "html_url": repo.get("html_url"),
            "default_branch": repo.get("default_branch", "main"),
        })
    return out


def _github_list_repos_authenticated(token: str) -> List[Dict[str, Any]]:
    """List repos for the authenticated user. GET /user/repos."""
    path = "/user/repos?per_page=100&sort=updated"
    data, err, _ = _github_request("GET", path, token=token, timeout=15.0)
    if err or not data:
        return []
    out = []
    for repo in data if isinstance(data, list) else []:
        full_name = repo.get("full_name") or ""
        owner = repo.get("owner", {}) or {}
        owner_login = owner.get("login", "") if isinstance(owner, dict) else ""
        if "/" in full_name:
            parts = full_name.split("/", 1)
            owner_str, name = parts[0], parts[1]
        else:
            owner_str = owner_login
            name = repo.get("name", "")
        out.append({
            "full_name": full_name,
            "owner": owner_str or owner_login,
            "name": name or repo.get("name", ""),
            "clone_url": repo.get("clone_url"),
            "html_url": repo.get("html_url"),
            "default_branch": repo.get("default_branch", "main"),
        })
    return out


def validate_repository(
    owner: str, repo: str, user_id: int
) -> Tuple[bool, Optional[str]]:
    """
    Check that the repo exists and belongs to the user's linked GitHub account.
    Enforces: repo owner must equal linked github_username (student can only link their own repos).
    Works with or without token (public repos can be validated unauthenticated).
    Returns (True, default_branch) or (False, error_message).
    """
    session = SessionLocal()
    try:
        account = (
            session.query(GitHubAccount)
            .filter(GitHubAccount.user_id == user_id)
            .first()
        )
        if not account:
            return False, "No linked GitHub account for this user"
        linked_username = (account.github_username or "").strip().lower()
        owner_normalized = (owner or "").strip().lower()
        if linked_username != owner_normalized:
            logger.warning("Repo owner %r does not match linked GitHub account %r", owner, account.github_username)
            return False, "Repository does not belong to your linked GitHub account"
        token = _token_for_account(account)
        return _github_repo_info(owner, repo, token)
    finally:
        session.close()


def _github_repo_info(
    owner: str, repo: str, token: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """Check repo exists on GitHub; return (True, default_branch) or (False, error). Works without token for public repos."""
    path = f"/repos/{owner}/{repo}"
    data, err, status = _github_request("GET", path, token=token, timeout=10.0)
    if err:
        if status == 404:
            return False, "Repository not found"
        return False, err or f"Repository not found or no access (HTTP {status})"
    if not data:
        return False, "Repository not found"
    default_branch = data.get("default_branch") or "main"
    return True, default_branch


def get_latest_commit_sha(
    owner: str, repo: str, branch: str, user_id: int
) -> Tuple[Optional[str], Optional[str]]:
    """
    Get latest commit SHA for branch. Uses token if available; for public repos works without token.
    Returns (sha, error_message).
    """
    session = SessionLocal()
    try:
        account = (
            session.query(GitHubAccount)
            .filter(GitHubAccount.user_id == user_id)
            .first()
        )
        if not account:
            return None, "No linked GitHub account for this user"
        # Enforce repo belongs to linked account
        linked_username = (account.github_username or "").strip().lower()
        if (owner or "").strip().lower() != linked_username:
            return None, "Repository does not belong to your linked GitHub account"
        token = _token_for_account(account)
        return _github_branch_sha(owner, repo, branch, token)
    finally:
        session.close()


def _github_branch_sha(
    owner: str, repo: str, branch: str, token: Optional[str] = None
) -> Tuple[Optional[str], Optional[str]]:
    """Get latest commit SHA for branch. Works without token for public repos."""
    path = f"/repos/{owner}/{repo}/commits/{branch}"
    data, err, status = _github_request("GET", path, token=token, timeout=10.0)
    if err:
        if status == 404:
            return None, "Could not fetch latest commit SHA (branch or repo not found)"
        return None, err or "Could not fetch latest commit SHA"
    if not data:
        return None, "Could not fetch latest commit SHA"
    sha = data.get("sha")
    return (sha, None) if sha else (None, "No SHA in response")


# ---------- Repo contents (for professor to analyze submissions) ----------
# Uses public GitHub API; no token required for public repos.

def fetch_repo_contents(
    owner: str,
    repo: str,
    ref: str,
    path: str = "",
    token: Optional[str] = None,
    max_file_size: int = 100_000,
    max_total_chars: int = 200_000,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetch file or directory contents from a GitHub repo at a given ref (commit SHA or branch).
    Returns (contents_text, error_message). contents_text is formatted for LLM consumption.
    For directory: lists names and types; fetches README.md if present.
    For file: returns decoded content (text). Respects max_file_size and max_total_chars.
    Works without token for public repos.
    """
    import base64
    path_clean = (path or "").strip().strip("/")
    query = f"?ref={ref}" if ref else ""
    if path_clean:
        api_path = f"/repos/{owner}/{repo}/contents/{path_clean}{query}"
    else:
        api_path = f"/repos/{owner}/{repo}/contents{query}"
    data, err, status = _github_request("GET", api_path, token=token, timeout=15.0)
    if err:
        if status == 404:
            return None, "Repository path not found (wrong ref or path)."
        return None, err or "Failed to fetch repository contents."
    if not data:
        return None, "No content returned."

    # Single file
    if isinstance(data, dict):
        if data.get("type") != "file":
            return None, "Path is not a file."
        enc = data.get("encoding")
        content_b64 = data.get("content")
        if enc != "base64" or not content_b64:
            return None, "File content not available (binary or empty)."
        try:
            raw = base64.b64decode(content_b64).decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning("Decode repo file failed: %s", e)
            return None, "Could not decode file content."
        if len(raw) > max_file_size:
            raw = raw[:max_file_size] + "\n\n... (truncated)"
        return raw, None

    # Directory listing
    if not isinstance(data, list):
        return None, "Unexpected API response."
    lines = [f"Contents of /{path_clean or '.'} at ref {ref[:7] if ref else 'HEAD'}:", ""]
    readme_content = None
    for item in data if isinstance(data, list) else []:
        name = item.get("name", "")
        typ = item.get("type", "file")
        size = item.get("size", 0) or 0
        lines.append(f"  [{typ}] {name}" + (f" ({size} bytes)" if typ == "file" else "/"))
        if typ == "file" and name.upper() == "README.MD" and readme_content is None:
            readme_path = f"{path_clean}/{name}".strip("/")
            readme_data, _ = fetch_repo_contents(
                owner, repo, ref, readme_path, token, max_file_size, max_total_chars - 5000
            )
            if readme_data:
                readme_content = readme_data
    result = "\n".join(lines)
    if readme_content:
        result += "\n\n--- README.md ---\n\n" + readme_content
    if len(result) > max_total_chars:
        result = result[:max_total_chars] + "\n\n... (output truncated)"
    return result, None
