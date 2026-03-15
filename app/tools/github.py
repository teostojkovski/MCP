"""
MCP tool: list the current user's linked GitHub repos (student: send repos to Claude).
"""
from mcp.types import Tool, TextContent
from app.tools.registry import ToolDef
from app.github_service import get_linked_account_for_username, list_repositories_for_user
from app.db import SessionLocal
from app.models import User


async def github_list_my_repos_handler(arguments: dict) -> list[TextContent]:
    """List GitHub repos for the current user. Student only. Link GitHub in the browser (username + token) first."""
    user = (arguments or {}).get("_user")
    if not user:
        return [TextContent(type="text", text="NOT_AUTHENTICATED")]
    role = (user.get("role") or "").strip().lower()
    if role != "student":
        return [TextContent(type="text", text="FORBIDDEN: student only")]
    username = user.get("user_id")
    if not username:
        return [TextContent(type="text", text="NOT_AUTHENTICATED")]
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == username).first()
        if not u:
            return [TextContent(type="text", text="User not found")]
        linked = get_linked_account_for_username(username)
        if not linked:
            return [TextContent(type="text", text="GitHub not linked. Log in to the web app and link your GitHub (username + token) first.")]
        repos, err = list_repositories_for_user(u.id)
    finally:
        db.close()
    if err:
        return [TextContent(type="text", text=err)]
    if not repos:
        return [TextContent(type="text", text="No repos found for your linked GitHub account (public repos are listed; add a token to include private repos).")]
    lines = [f"Linked as {linked.get('github_username', '?')}. Repos ({len(repos)}):"]
    for r in repos:
        url = r.get("html_url") or f"https://github.com/{r.get('owner', '')}/{r.get('name', '')}"
        lines.append(f"  - {r.get('full_name', '')}  {url}")
    return [TextContent(type="text", text="\n".join(lines))]


GITHUB_TOOLS = [
    ToolDef(
        tool=Tool(
            name="github_list_my_repos",
            description="List the current student's GitHub repos. Use after the student has linked GitHub in the browser (username + token). So the student can say 'list my repos' and then e.g. 'submit assignment 1 with repo https://github.com/me/myproject'.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        handler=github_list_my_repos_handler,
    ),
]
