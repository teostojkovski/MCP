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
    """Show curriculum for a program: mandatory subjects and elective slots per semester."""
    program_name = arguments.get("program_name")
    if not program_name:
        return [TextContent(type="text", text="Error: program_name is required.")]
    curriculum = queries.get_curriculum_by_program(program_name)
    if not curriculum.get("semesters"):
        return [TextContent(type="text", text=f"No curriculum found for program '{program_name}' or program does not exist.")]
    lines = [f"Curriculum for program '{curriculum['program_name']}':", ""]
    for sem_block in curriculum["semesters"]:
        sem = sem_block["semester"]
        lines.append(f"Semester {sem}")
        lines.append("")
        if sem_block["mandatory"]:
            lines.append("Mandatory:")
            for s in sem_block["mandatory"]:
                lines.append(f"  - {s['code']}: {s['name']} ({s['ects']} ECTS)")
            lines.append("")
        if sem_block["elective_pools"]:
            for pool in sem_block["elective_pools"]:
                lines.append("Elective slots:")
                lines.append(f"Choose {pool['slots']} subject(s)")
                lines.append(f"Pool: {pool['elective_group_code']}")
                lines.append("")
                lines.append("Available subjects:")
                for s in pool["subjects"]:
                    lines.append(f"  - {s['code']}: {s['name']} ({s['ects']} ECTS)")
                lines.append("")
        lines.append("---")
        lines.append("")
    return [TextContent(type="text", text="\n".join(lines).strip())]


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
            description="Show curriculum for a program: per semester, mandatory subjects and elective slots (choose N from pool). Use for 'show curriculum for program X'.",
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
