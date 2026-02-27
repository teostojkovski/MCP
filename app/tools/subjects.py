"""
Subject-related MCP tools.
"""
from mcp.types import Tool, TextContent
from app.tools.registry import ToolDef
import app.queries as queries


async def subject_search_handler(arguments: dict) -> list[TextContent]:
    """Search for subjects by code or name (partial match). Semester/mandatory are per-program."""
    subjects = queries.search_subjects(
        code=arguments.get("code"),
        name=arguments.get("name"),
        limit=arguments.get("limit", 100)
    )

    if not subjects:
        return [TextContent(type="text", text="No subjects found matching the criteria.")]

    result_lines = [f"Found {len(subjects)} subject(s):"]
    for s in subjects:
        ects = s.get("ects") or 6
        result_lines.append(f"  - {s['code']}: {s['name']} ({ects} ECTS)")

    return [TextContent(type="text", text="\n".join(result_lines))]


async def subject_get_handler(arguments: dict) -> list[TextContent]:
    """Get subject by code (global catalog). Semester/mandatory/elective are per-program."""
    subject = queries.get_subject_by_code(arguments["subject_code"])
    if not subject:
        return [TextContent(type="text", text=f"Subject {arguments['subject_code']} not found.")]

    result = f"Subject {subject['code']}:\n"
    result += f"  Name: {subject['name']}\n"
    result += f"  ECTS: {subject.get('ects') or 6}"

    return [TextContent(type="text", text=result)]


async def subject_create_handler(arguments: dict) -> list[TextContent]:
    """Create a new subject (code, name, optional ects). Assign to program via admin."""
    try:
        subject = queries.create_subject(
            code=arguments["code"],
            name=arguments["name"],
            ects=arguments.get("ects"),
        )
        return [TextContent(type="text", text=f"Subject {subject['code']} created successfully.")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error creating subject: {str(e)}")]


async def subject_enrolled_students_handler(arguments: dict) -> list[TextContent]:
    """Get students enrolled in a subject."""
    students = queries.get_subject_enrolled_students(
        subject_code=arguments["subject_code"],
        semester=arguments.get("semester"),
        program=arguments.get("program")
    )

    if not students:
        return [TextContent(type="text", text=f"No students enrolled in subject {arguments['subject_code']}.")]

    result_lines = [f"Found {len(students)} student(s) enrolled in {arguments['subject_code']}:"]
    for s in students:
        result_lines.append(f"  - {s['index']}: {s['first_name']} {s['last_name']} ({s['program']}, Year {s['year_of_study']})")

    return [TextContent(type="text", text="\n".join(result_lines))]


async def subject_stats_handler(arguments: dict) -> list[TextContent]:
    """Get statistics for a subject."""
    stats = queries.get_subject_stats(arguments["subject_code"])

    result = f"Statistics for subject {stats['subject_code']}:\n"
    result += f"  Total Enrolled: {stats['total_enrolled']}\n"
    result += f"  Attempted Exam: {stats['attempted_exam']}\n"
    result += f"  Passed: {stats['passed']}\n"
    result += f"  Failed: {stats['failed']}\n"
    result += f"  Pass Rate: {stats['pass_rate']}%"
    if stats['average_grade']:
        result += f"\n  Average Grade: {stats['average_grade']}"

    return [TextContent(type="text", text=result)]


SUBJECT_TOOLS = [
    ToolDef(
        tool=Tool(
            name="subject_search",
            description="Search subjects by code or name (partial match). There are 3 programs: PIT, SIIS, IMB; semester/mandatory are per-program.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Subject code (partial match)"},
                    "name": {"type": "string", "description": "Subject name (partial match)"},
                    "limit": {"type": "integer", "description": "Maximum number of results", "default": 100}
                }
            }
        ),
        handler=subject_search_handler
    ),
    ToolDef(
        tool=Tool(
            name="subject_get",
            description="Get subject by code.",
            inputSchema={
                "type": "object",
                "properties": {
                    "subject_code": {"type": "string", "description": "Subject code"}
                },
                "required": ["subject_code"]
            }
        ),
        handler=subject_get_handler
    ),
    ToolDef(
        tool=Tool(
            name="subject_create",
            description="Create a new subject (global catalog). Use Programs in admin to assign to a program.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Subject code"},
                    "name": {"type": "string", "description": "Subject name"},
                    "ects": {"type": "integer", "description": "ECTS credits (optional, default 6)"}
                },
                "required": ["code", "name"]
            }
        ),
        handler=subject_create_handler
    ),
    ToolDef(
        tool=Tool(
            name="subject_enrolled_students",
            description="Get students enrolled in a subject (with optional semester/program filters).",
            inputSchema={
                "type": "object",
                "properties": {
                    "subject_code": {"type": "string", "description": "Subject code"},
                    "semester": {"type": "integer", "description": "Semester filter"},
                    "program": {"type": "string", "description": "Program filter"}
                },
                "required": ["subject_code"]
            }
        ),
        handler=subject_enrolled_students_handler
    ),
    ToolDef(
        tool=Tool(
            name="subject_stats",
            description="Get statistics for a subject: enrolled/attempted/passed/pass rate/avg grade.",
            inputSchema={
                "type": "object",
                "properties": {
                    "subject_code": {"type": "string", "description": "Subject code"}
                },
                "required": ["subject_code"]
            }
        ),
        handler=subject_stats_handler
    ),
]

