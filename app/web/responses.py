"""
Shared response helpers. Behavior identical to existing.
"""
from __future__ import annotations

from urllib.parse import quote
from fastapi.responses import RedirectResponse


def redirect_to_login(next_path: str) -> RedirectResponse:
    return RedirectResponse(url=f"/device?next={quote(next_path)}", status_code=302)
