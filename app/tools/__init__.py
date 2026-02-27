"""
MCP Tools registry.
Combines all tool definitions from domain modules.
Adds session_id to every non-public tool schema so the client (Claude) knows to pass it after login.
"""
from copy import deepcopy

from mcp.types import Tool

from app.tools.registry import ToolDef
from app.tools.students import STUDENT_TOOLS
from app.tools.subjects import SUBJECT_TOOLS
from app.tools.programs import PROGRAM_TOOLS
from app.tools.exams import EXAM_TOOLS
from app.tools.enrollments import ENROLLMENT_TOOLS
from app.tools.auth import AUTH_TOOLS

PUBLIC_TOOL_NAMES = {"auth_start", "auth_status"}

ALL_TOOL_DEFS: list[ToolDef] = (
    AUTH_TOOLS +
    STUDENT_TOOLS +
    SUBJECT_TOOLS +
    PROGRAM_TOOLS +
    EXAM_TOOLS +
    ENROLLMENT_TOOLS
)


def _tool_with_session_id(td: ToolDef) -> ToolDef:
    """Add session_id to inputSchema so the client passes it for authenticated tools."""
    if td.tool.name in PUBLIC_TOOL_NAMES:
        return td
    schema = deepcopy(td.tool.inputSchema)
    props = schema.get("properties") or {}
    props = dict(props)
    props["session_id"] = {
        "type": "string",
        "description": "Session ID from auth_status after device login. Pass this with every authenticated tool call.",
    }
    schema["properties"] = props
    req = list(schema.get("required") or [])
    if "session_id" not in req:
        req.append("session_id")
    schema["required"] = req
    new_tool = Tool(
        name=td.tool.name,
        description=td.tool.description,
        inputSchema=schema,
    )
    return ToolDef(tool=new_tool, handler=td.handler)


_TOOL_DEFS_WITH_SESSION = [_tool_with_session_id(td) for td in ALL_TOOL_DEFS]

TOOLS = [td.tool for td in _TOOL_DEFS_WITH_SESSION]
TOOL_MAP = {td.tool.name: td for td in _TOOL_DEFS_WITH_SESSION}

__all__ = ["TOOLS", "TOOL_MAP", "ALL_TOOL_DEFS"]
