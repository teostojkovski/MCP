"""
Program-related MCP tools.
There are 3 programs: PIT, SIIS, IMB. Students enroll only in subjects of their program.
"""
from mcp.types import Tool, TextContent
from app.tools.registry import ToolDef
import app.queries as queries


async def program_list_handler(arguments: dict) -> list[TextContent]:
    """List all programs (id, name). Use program name when creating students or checking curriculum."""
    programs = queries.list_programs()
    if not programs:
        return [TextContent(type="text", text="No programs found. Seed the database.")]
    lines = ["Programs (use name for student.program and for program_subjects):"]
    for p in programs:
        lines.append(f"  - {p['id']}: {p['name']}")
    return [TextContent(type="text", text="\n".join(lines))]


async def program_subjects_handler(arguments: dict) -> list[TextContent]:
    """List subjects in a program by program name (semester, mandatory/elective)."""
    program_name = arguments.get("program_name")
    if not program_name:
        return [TextContent(type="text", text="Error: program_name is required.")]
    subjects = queries.get_subjects_by_program(program_name)
    if not subjects:
        return [TextContent(type="text", text=f"No subjects found for program '{program_name}' or program does not exist.")]
    lines = [f"Subjects in program '{program_name}':"]
    for s in subjects:
        kind = "mandatory" if s["is_mandatory"] else f"elective ({s['elective_group_code'] or '—'})"
        lines.append(f"  - {s['code']}: {s['name']} (Sem {s['semester']}, {s['ects']} ECTS, {kind})")
    return [TextContent(type="text", text="\n".join(lines))]


PROGRAM_TOOLS = [
    ToolDef(
        tool=Tool(
            name="program_list",
            description="List all programs (PIT, SIIS, IMB). Students have program = program name.",
            inputSchema={"type": "object", "properties": {}}
        ),
        handler=program_list_handler
    ),
    ToolDef(
        tool=Tool(
            name="program_subjects",
            description="List subjects in a program by program name (semester, mandatory/elective).",
            inputSchema={
                "type": "object",
                "properties": {
                    "program_name": {"type": "string", "description": "Program name (e.g. Примена на информациски технологии)"}
                },
                "required": ["program_name"]
            }
        ),
        handler=program_subjects_handler
    ),
]
