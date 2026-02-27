"""
MCP Server for Student Grade Management System.
Minimal registry-based implementation.
"""
from app.tools import TOOLS, TOOL_MAP
from app.auth_store import get_session

from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server
from mcp.server import Server
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


app = Server("student-grade-mcp")

PUBLIC_TOOLS = {"auth_start", "auth_status"}

READ_TOOLS = {
    "get_student_subjects",
    "student_search",
    "student_get",
    "student_academic_summary",
    "student_passed_subjects",
    "subject_search",
    "subject_get",
    "subject_enrolled_students",
    "subject_stats",
    "check_student_passed_subject",
    "exam_list_by_subject_and_date",
    "exam_best_result",
    "enrollment_list",
    "enrollment_students_in_subject_with_status",
    "program_list",
    "program_subjects",
}

PROFESSOR_WRITE_TOOLS = {"exam_record_create", "exam_record_update"}

ADMIN_WRITE_TOOLS = {
    "student_create",
    "student_update",
    "enrollment_create",
    "enrollment_update",
    "subject_create",
}


def is_allowed(tool_name: str, role: str) -> bool:
    """
    - student: read tools only (handlers should restrict to own data).
    - professor: read tools + exam_record_create, exam_record_update.
    - admin: everything.
    """
    if not role:
        return False

    if tool_name in READ_TOOLS:
        return role in {"student", "professor", "admin"}

    if tool_name in PROFESSOR_WRITE_TOOLS:
        return role in {"professor", "admin"}

    if tool_name in ADMIN_WRITE_TOOLS:
        return role == "admin"

    return False


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    if name not in TOOL_MAP:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    if name not in PUBLIC_TOOLS:
        arguments = arguments or {}
        session_id = arguments.get("session_id")

        if not session_id:
            return [TextContent(type="text", text="NOT_AUTHENTICATED: call auth_start first")]

        session = get_session(session_id)
        if not session:
            return [TextContent(type="text", text="NOT_AUTHENTICATED: session expired, call auth_start")]

        if not is_allowed(name, session.role):
            return [TextContent(type="text", text="FORBIDDEN")]

        arguments["_user"] = {"user_id": session.user_id, "role": session.role}

    tool_def = TOOL_MAP[name]
    return await tool_def.handler(arguments)


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
