"""
Student-related MCP tools.
"""
from mcp.types import Tool, TextContent
from app.tools.registry import ToolDef
import app.queries as queries


async def get_student_subjects_handler(arguments: dict) -> list[TextContent]:
    """Get all subjects that a student is currently listening to."""
    student = None
    if "student_index" in arguments:
        student = queries.get_student(arguments["student_index"])
    elif "student_name" in arguments:
        student = queries.get_student_by_name(arguments["student_name"])

    if not student:
        identifier = arguments.get("student_index") or arguments.get(
            "student_name", "Unknown")
        return [TextContent(
            type="text",
            text=f"Student not found: {identifier}"
        )]

    enrollments = queries.get_current_enrollments(student["index"])

    if not enrollments:
        return [TextContent(
            type="text",
            text=f"Student {student['index']} ({student['first_name']} {student['last_name']}) is not currently listening to any subjects."
        )]

    subject_list = []
    for subj in enrollments:
        subject_list.append(
            f"- {subj['code']}: {subj['name']} (Semester {subj['semester']}, {subj['ects']} ECTS)")

    result = f"Student {student['index']} ({student['first_name']} {student['last_name']}) is listening to {len(enrollments)} subject(s):\n" + \
        "\n".join(subject_list)

    return [TextContent(type="text", text=result)]


async def student_search_handler(arguments: dict) -> list[TextContent]:
    """Search for students with optional filters."""
    students = queries.search_students(
        index=arguments.get("index"),
        first_name=arguments.get("first_name"),
        last_name=arguments.get("last_name"),
        program=arguments.get("program"),
        start_year=arguments.get("start_year"),
        year_of_study=arguments.get("year_of_study"),
        status=arguments.get("status"),
        limit=arguments.get("limit", 100)
    )

    if not students:
        return [TextContent(type="text", text="No students found matching the criteria.")]

    result_lines = [f"Found {len(students)} student(s):"]
    for s in students:
        result_lines.append(
            f"  - {s['index']}: {s['first_name']} {s['last_name']} ({s['program']}, Year {s['year_of_study']}, {s['status']})")

    return [TextContent(type="text", text="\n".join(result_lines))]


async def student_get_handler(arguments: dict) -> list[TextContent]:
    """Get student by index."""
    student = queries.get_student(arguments["student_index"])
    if not student:
        return [TextContent(type="text", text=f"Student {arguments['student_index']} not found.")]

    result = f"Student {student['index']}:\n"
    result += f"  Name: {student['first_name']} {student['last_name']}\n"
    result += f"  Program: {student['program']}\n"
    result += f"  Start Year: {student['start_year']}\n"
    result += f"  Year of Study: {student['year_of_study']}\n"
    result += f"  Status: {student['status']}"

    return [TextContent(type="text", text=result)]


async def student_create_handler(arguments: dict) -> list[TextContent]:
    """Create a new student."""
    try:
        student = queries.create_student(
            index=arguments["index"],
            first_name=arguments["first_name"],
            last_name=arguments["last_name"],
            program=arguments["program"],
            start_year=arguments["start_year"],
            year_of_study=arguments["year_of_study"],
            status=arguments.get("status", "active")
        )
        return [TextContent(type="text", text=f"Student {student['index']} created successfully.")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error creating student: {str(e)}")]


async def student_update_handler(arguments: dict) -> list[TextContent]:
    """Update student information."""
    student = queries.update_student(
        index=arguments["student_index"],
        first_name=arguments.get("first_name"),
        last_name=arguments.get("last_name"),
        program=arguments.get("program"),
        year_of_study=arguments.get("year_of_study"),
        status=arguments.get("status")
    )
    if not student:
        return [TextContent(type="text", text=f"Student {arguments['student_index']} not found.")]

    return [TextContent(type="text", text=f"Student {student['index']} updated successfully.")]


async def student_academic_summary_handler(arguments: dict) -> list[TextContent]:
    """Get academic summary for a student."""
    student_index = arguments.get("student_index")
    if not student_index:
        student = queries.get_student_by_name(
            arguments.get("student_name", ""))
        if not student:
            return [TextContent(type="text", text="Student not found.")]
        student_index = student["index"]
    else:
        student = queries.get_student(student_index)
        if not student:
            return [TextContent(type="text", text=f"Student {student_index} not found.")]

    ects = queries.earned_ects(student_index)
    passed = queries.passed_subjects(student_index)
    enrollments = queries.get_current_enrollments(student_index)
    avg_grade = queries.get_student_average_grade(student_index)

    result = f"Academic Summary for {student['first_name']} {student['last_name']} (Index: {student_index}):\n"
    result += f"  Program: {student['program']}\n"
    result += f"  Year of Study: {student['year_of_study']}\n"
    result += f"  ECTS Earned: {ects}\n"
    result += f"  Passed Subjects: {len(passed)}\n"
    result += f"  Current Enrollments: {len(enrollments)}\n"
    if avg_grade:
        result += f"  Average Grade: {avg_grade}"

    return [TextContent(type="text", text=result)]


async def student_passed_subjects_handler(arguments: dict) -> list[TextContent]:
    """Get list of subjects a student has passed."""
    student_index = arguments.get("student_index")
    if not student_index:
        student = queries.get_student_by_name(
            arguments.get("student_name", ""))
        if not student:
            return [TextContent(type="text", text="Student not found.")]
        student_index = student["index"]
    else:
        student = queries.get_student(student_index)
        if not student:
            return [TextContent(type="text", text=f"Student {student_index} not found.")]

    passed = queries.passed_subjects(student_index)

    if not passed:
        return [TextContent(type="text", text=f"Student {student_index} has not passed any subjects yet.")]

    result_lines = [
        f"Student {student_index} has passed {len(passed)} subject(s):"]
    for subj in passed:
        result_lines.append(
            f"  - {subj['code']}: {subj['name']} (Grade: {subj['grade']}, Semester: {subj['semester']})")

    return [TextContent(type="text", text="\n".join(result_lines))]


STUDENT_TOOLS = [
    ToolDef(
        tool=Tool(
            name="get_student_subjects",
            description="Get all subjects that a student is currently listening to (enrolled but not yet passed). Returns a list of subjects with their codes, names, semesters, and ECTS credits.",
            inputSchema={
                "type": "object",
                "properties": {
                    "student_index": {"type": "integer", "description": "Student index number (e.g., 234800)"},
                    "student_name": {"type": "string", "description": "Student name (first name, last name, or full name). Use this if you don't have the student index."}
                },
                "oneOf": [
                    {"required": ["student_index"]},
                    {"required": ["student_name"]}
                ]
            }
        ),
        handler=get_student_subjects_handler
    ),
    ToolDef(
        tool=Tool(
            name="student_search",
            description="Search for students with optional filters (index, name, program, year, status).",
            inputSchema={
                "type": "object",
                "properties": {
                    "index": {"type": "integer", "description": "Student index number"},
                    "first_name": {"type": "string", "description": "First name (partial match)"},
                    "last_name": {"type": "string", "description": "Last name (partial match)"},
                    "program": {"type": "string", "description": "Program name"},
                    "start_year": {"type": "integer", "description": "Start year"},
                    "year_of_study": {"type": "integer", "description": "Year of study (1-4)"},
                    "status": {"type": "string", "description": "Status (active, graduated, inactive)"},
                    "limit": {"type": "integer", "description": "Maximum number of results", "default": 100}
                }
            }
        ),
        handler=student_search_handler
    ),
    ToolDef(
        tool=Tool(
            name="student_get",
            description="Get student by index.",
            inputSchema={
                "type": "object",
                "properties": {
                    "student_index": {"type": "integer", "description": "Student index number"}
                },
                "required": ["student_index"]
            }
        ),
        handler=student_get_handler
    ),
    ToolDef(
        tool=Tool(
            name="student_create",
            description="Create a new student.",
            inputSchema={
                "type": "object",
                "properties": {
                    "index": {"type": "integer", "description": "Student index number"},
                    "first_name": {"type": "string", "description": "First name"},
                    "last_name": {"type": "string", "description": "Last name"},
                    "program": {"type": "string", "description": "Program name"},
                    "start_year": {"type": "integer", "description": "Start year"},
                    "year_of_study": {"type": "integer", "description": "Year of study (1-4)"},
                    "status": {"type": "string", "description": "Status (active, graduated, inactive)", "default": "active"}
                },
                "required": ["index", "first_name", "last_name", "program", "start_year", "year_of_study"]
            }
        ),
        handler=student_create_handler
    ),
    ToolDef(
        tool=Tool(
            name="student_update",
            description="Update student information (program, year_of_study, status, name).",
            inputSchema={
                "type": "object",
                "properties": {
                    "student_index": {"type": "integer", "description": "Student index number"},
                    "first_name": {"type": "string", "description": "First name"},
                    "last_name": {"type": "string", "description": "Last name"},
                    "program": {"type": "string", "description": "Program name"},
                    "year_of_study": {"type": "integer", "description": "Year of study (1-4)"},
                    "status": {"type": "string", "description": "Status (active, graduated, inactive)"}
                },
                "required": ["student_index"]
            }
        ),
        handler=student_update_handler
    ),
    ToolDef(
        tool=Tool(
            name="student_academic_summary",
            description="Get academic summary for a student: earned ECTS, passed subjects, current enrollments, average grade.",
            inputSchema={
                "type": "object",
                "properties": {
                    "student_index": {"type": "integer", "description": "Student index number"},
                    "student_name": {"type": "string", "description": "Student name"}
                },
                "oneOf": [
                    {"required": ["student_index"]},
                    {"required": ["student_name"]}
                ]
            }
        ),
        handler=student_academic_summary_handler
    ),
    ToolDef(
        tool=Tool(
            name="student_passed_subjects",
            description="Get list of subjects a student has passed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "student_index": {"type": "integer", "description": "Student index number"},
                    "student_name": {"type": "string", "description": "Student name"}
                },
                "oneOf": [
                    {"required": ["student_index"]},
                    {"required": ["student_name"]}
                ]
            }
        ),
        handler=student_passed_subjects_handler
    ),
]
