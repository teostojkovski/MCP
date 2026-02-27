"""
Enrollment-related MCP tools.
"""
from mcp.types import Tool, TextContent
from app.tools.registry import ToolDef
import app.queries as queries


async def enrollment_list_handler(arguments: dict) -> list[TextContent]:
    """List enrollments with optional filters."""
    enrollments = queries.list_enrollments(
        student_index=arguments.get("student_index"),
        subject_code=arguments.get("subject_code"),
        semester=arguments.get("semester"),
        listened=arguments.get("listened"),
        limit=arguments.get("limit", 200)
    )

    if not enrollments:
        return [TextContent(type="text", text="No enrollments found matching the criteria.")]

    result_lines = [f"Found {len(enrollments)} enrollment(s):"]
    for e in enrollments:
        listened_str = "listening" if e["listened"] else "not listening"
        result_lines.append(
            f"  - {e['student_name']} (Index: {e['student_index']}) enrolled in "
            f"{e['subject_code']} ({e['subject_name']}) - Semester {e['semester']} ({listened_str})"
        )

    return [TextContent(type="text", text="\n".join(result_lines))]


async def enrollment_create_handler(arguments: dict) -> list[TextContent]:
    """Create a new enrollment."""
    try:
        student_index = arguments.get("student_index")
        subject_code = arguments.get("subject_code")
        semester = arguments.get("semester")

        if not student_index:
            return [TextContent(type="text", text="Error: student_index is required.")]
        if not subject_code:
            return [TextContent(type="text", text="Error: subject_code is required.")]
        if semester is None:
            return [TextContent(type="text", text="Error: semester is required.")]

        enrollment = queries.create_enrollment(
            student_index=student_index,
            subject_code=subject_code,
            semester=semester,
            listened=arguments.get("listened", True)
        )

        student = queries.get_student(student_index)
        subject = queries.get_subject_by_code(subject_code)

        student_name = f"{student['first_name']} {student['last_name']}" if student else f"Index {student_index}"
        subject_name = subject['name'] if subject else subject_code

        return [TextContent(
            type="text",
            text=f"Enrollment created successfully: {student_name} (Index: {student_index}) enrolled in "
                 f"{subject_name} ({subject_code}) for semester {semester} (ID: {enrollment['id']})."
        )]
    except ValueError as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error creating enrollment: {str(e)}")]


async def enrollment_update_handler(arguments: dict) -> list[TextContent]:
    """Update an enrollment."""
    enrollment = queries.update_enrollment(
        enrollment_id=arguments.get("enrollment_id"),
        student_index=arguments.get("student_index"),
        subject_code=arguments.get("subject_code"),
        semester=arguments.get("semester"),
        listened=arguments.get("listened")
    )

    if not enrollment:
        return [TextContent(type="text", text="Enrollment not found.")]

    return [TextContent(type="text", text=f"Enrollment {enrollment['id']} updated successfully.")]


async def enrollment_students_in_subject_with_status_handler(arguments: dict) -> list[TextContent]:
    """Get students in a subject grouped by status (passed/not passed/not attempted)."""
    status = queries.get_students_in_subject_with_status(
        subject_code=arguments["subject_code"],
        semester=arguments.get("semester")
    )

    result_lines = [f"Students in subject {arguments['subject_code']}:"]

    if status["passed"]:
        result_lines.append(f"\nPassed ({len(status['passed'])}):")
        for s in status["passed"]:
            result_lines.append(
                f"  - {s['index']}: {s['first_name']} {s['last_name']} ({s['program']})")

    if status["not_passed"]:
        result_lines.append(f"\nNot Passed ({len(status['not_passed'])}):")
        for s in status["not_passed"]:
            result_lines.append(
                f"  - {s['index']}: {s['first_name']} {s['last_name']} ({s['program']})")

    if status["not_attempted"]:
        result_lines.append(
            f"\nNot Attempted ({len(status['not_attempted'])}):")
        for s in status["not_attempted"]:
            result_lines.append(
                f"  - {s['index']}: {s['first_name']} {s['last_name']} ({s['program']})")

    return [TextContent(type="text", text="\n".join(result_lines))]


ENROLLMENT_TOOLS = [
    ToolDef(
        tool=Tool(
            name="enrollment_list",
            description="List enrollments with optional filters (student_index, subject_code, semester, listened).",
            inputSchema={
                "type": "object",
                "properties": {
                    "student_index": {"type": "integer", "description": "Student index number"},
                    "subject_code": {"type": "string", "description": "Subject code"},
                    "semester": {"type": "integer", "description": "Semester number"},
                    "listened": {"type": "boolean", "description": "Whether student is listening"},
                    "limit": {"type": "integer", "description": "Maximum number of results", "default": 200}
                }
            }
        ),
        handler=enrollment_list_handler
    ),
    ToolDef(
        tool=Tool(
            name="enrollment_create",
            description="Create enrollment. Enforces: subject must be in student's program; max 6 subjects per semester; prerequisites and min ECTS must be satisfied. Use program_list and program_subjects to see curricula.",
            inputSchema={
                "type": "object",
                "properties": {
                    "student_index": {"type": "integer", "description": "Student index number"},
                    "subject_code": {"type": "string", "description": "Subject code"},
                    "semester": {"type": "integer", "description": "Semester number"},
                    "listened": {"type": "boolean", "description": "Whether student is listening", "default": True}
                },
                "required": ["student_index", "subject_code", "semester"]
            }
        ),
        handler=enrollment_create_handler
    ),
    ToolDef(
        tool=Tool(
            name="enrollment_update",
            description="Update an enrollment (identify by enrollment_id or student_index+subject_code+semester).",
            inputSchema={
                "type": "object",
                "properties": {
                    "enrollment_id": {"type": "integer", "description": "Enrollment ID"},
                    "student_index": {"type": "integer", "description": "Student index number"},
                    "subject_code": {"type": "string", "description": "Subject code"},
                    "semester": {"type": "integer", "description": "Semester number"},
                    "listened": {"type": "boolean", "description": "Whether student is listening"}
                }
            }
        ),
        handler=enrollment_update_handler
    ),
    ToolDef(
        tool=Tool(
            name="enrollment_students_in_subject_with_status",
            description="Get students in a subject grouped by status (passed/not passed/not attempted).",
            inputSchema={
                "type": "object",
                "properties": {
                    "subject_code": {"type": "string", "description": "Subject code"},
                    "semester": {"type": "integer", "description": "Optional semester filter"}
                },
                "required": ["subject_code"]
            }
        ),
        handler=enrollment_students_in_subject_with_status_handler
    ),
]
