"""
Exam-related MCP tools.
"""
from mcp.types import Tool, TextContent
from app.tools.registry import ToolDef
import app.queries as queries
from app.db import SessionLocal
from app.models import Enrollment, ExamSession, Exam
from datetime import date


async def check_student_passed_subject_handler(arguments: dict) -> list[TextContent]:
    """Check if a student has passed a specific subject."""
    student = None
    if "student_index" in arguments:
        student = queries.get_student(arguments["student_index"])
    elif "student_name" in arguments:
        student = queries.get_student_by_name(arguments["student_name"])

    if not student:
        identifier = arguments.get("student_index") or arguments.get(
            "student_name", "Unknown")
        return [TextContent(type="text", text=f"Student not found: {identifier}")]

    subject = None
    if "subject_code" in arguments:
        subject = queries.get_subject_by_code(arguments["subject_code"])
    elif "subject_name" in arguments:
        subject = queries.get_subject_by_name(arguments["subject_name"])

    if not subject:
        identifier = arguments.get("subject_code") or arguments.get(
            "subject_name", "Unknown")
        return [TextContent(type="text", text=f"Subject not found: {identifier}")]

    session = SessionLocal()
    try:
        enrollment = session.query(Enrollment).filter(
            Enrollment.student_index == student["index"],
            Enrollment.subject_code == subject["code"],
            Enrollment.listened == True
        ).first()
    finally:
        session.close()

    if not enrollment:
        return [TextContent(
            type="text",
            text=f"Student {student['index']} ({student['first_name']} {student['last_name']}) hasn't listened to subject {subject['code']} ({subject['name']})."
        )]

    exam_result = queries.best_exam_result(student["index"], subject["code"])

    if not exam_result:
        return [TextContent(
            type="text",
            text=f"Student {student['index']} ({student['first_name']} {student['last_name']}) has listened to subject {subject['code']} ({subject['name']}) but hasn't taken the exam yet."
        )]

    if exam_result["passed"]:
        return [TextContent(
            type="text",
            text=f"Student {student['index']} ({student['first_name']} {student['last_name']}) has passed subject {subject['code']} ({subject['name']}) with grade {exam_result['grade']}."
        )]
    else:
        return [TextContent(
            type="text",
            text=f"Student {student['index']} ({student['first_name']} {student['last_name']}) has taken the exam for subject {subject['code']} ({subject['name']}) but hasn't passed it (grade: {exam_result['grade']})."
        )]


async def exam_list_by_subject_and_date_handler(arguments: dict) -> list[TextContent]:
    """List exams for a subject filtered by date."""
    subject_code = arguments["subject_code"]
    exam_date = arguments.get("exam_date")
    start_date = arguments.get("start_date")
    end_date = arguments.get("end_date")

    exam_date_obj = None
    start_date_obj = None
    end_date_obj = None

    if exam_date:
        exam_date_obj = date.fromisoformat(exam_date)
    if start_date:
        start_date_obj = date.fromisoformat(start_date)
    if end_date:
        end_date_obj = date.fromisoformat(end_date)

    exams = queries.list_exams_by_subject_and_date(
        subject_code=subject_code,
        exam_date=exam_date_obj,
        start_date=start_date_obj,
        end_date=end_date_obj
    )

    if not exams:
        return [TextContent(type="text", text=f"No exams found for subject {subject_code}.")]

    result_lines = [
        f"Found {len(exams)} exam result(s) for subject {subject_code}:"]
    for exam in exams:
        status = "PASSED" if exam["passed"] else "FAILED"
        result_lines.append(
            f"  - {exam['student_name']} (Index: {exam['student_index']}): "
            f"Grade {exam['grade']} ({status}) - {exam['session_type']} {exam['year']} ({exam['exam_date']})"
        )

    return [TextContent(type="text", text="\n".join(result_lines))]


async def exam_best_result_handler(arguments: dict) -> list[TextContent]:
    """Get best exam result for a student in a subject."""
    result = queries.best_exam_result(
        student_index=arguments["student_index"],
        subject_code=arguments["subject_code"]
    )

    if not result:
        return [TextContent(
            type="text",
            text=f"Student {arguments['student_index']} has not taken exam for subject {arguments['subject_code']}."
        )]

    status = "PASSED" if result["passed"] else "FAILED"
    return [TextContent(
        type="text",
        text=f"Best result: Grade {result['grade']} ({status}) - {result['session_type']} {result['year']} ({result['exam_date']})"
    )]


async def exam_record_create_handler(arguments: dict) -> list[TextContent]:
    """Create an exam record for a student."""
    from datetime import date

    try:
        exam_date = date.fromisoformat(arguments["exam_date"])
        session_type = arguments.get("session_type", "January")

        year = arguments.get("year", exam_date.year)

        exam_session_id = queries.find_or_create_exam_session(
            subject_code=arguments["subject_code"],
            session_type=session_type,
            year=year,
            exam_date=exam_date
        )

        session = SessionLocal()
        try:
            existing = session.query(Exam).filter(
                Exam.exam_session_id == exam_session_id,
                Exam.student_index == arguments["student_index"]
            ).first()
            if existing:
                return [TextContent(
                    type="text",
                    text=f"Student {arguments['student_index']} already has an exam record for this session."
                )]
        finally:
            session.close()

        exam = queries.create_exam_record(
            exam_session_id=exam_session_id,
            student_index=arguments["student_index"],
            grade=arguments["grade"],
            passed=arguments.get("passed")
        )

        return [TextContent(
            type="text",
            text=f"Exam record created successfully (ID: {exam['id']}, Grade: {exam['grade']}, {'PASSED' if exam['passed'] else 'FAILED'})."
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"Error creating exam record: {str(e)}")]


async def exam_record_update_handler(arguments: dict) -> list[TextContent]:
    """Update an exam record."""
    exam_id = arguments.get("exam_id")
    student_index = arguments.get("student_index")
    subject_code = arguments.get("subject_code")

    try:
        if exam_id:
            exam = queries.update_exam_record(
                exam_id=exam_id,
                grade=arguments.get("grade"),
                passed=arguments.get("passed")
            )
        elif student_index and subject_code:
            exam = queries.update_exam_record_by_student_subject(
                student_index=student_index,
                subject_code=subject_code,
                grade=arguments.get("grade"),
                passed=arguments.get("passed")
            )
        else:
            return [TextContent(
                type="text",
                text="Must provide either exam_id or (student_index and subject_code)."
            )]

        if not exam:
            return [TextContent(type="text", text="Exam record not found.")]

        return [TextContent(
            type="text",
            text=f"Exam record {exam['id']} updated successfully (Grade: {exam['grade']}, {'PASSED' if exam['passed'] else 'FAILED'})."
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"Error updating exam record: {str(e)}")]


EXAM_TOOLS = [
    ToolDef(
        tool=Tool(
            name="check_student_passed_subject",
            description="Check if a student has passed a specific subject. Returns whether the student has passed, the grade they received, or indicates if the student hasn't listened to that subject.",
            inputSchema={
                "type": "object",
                "properties": {
                    "student_index": {"type": "integer", "description": "Student index number (e.g., 234800)"},
                    "student_name": {"type": "string", "description": "Student name (first name, last name, or full name). Use this if you don't have the student index."},
                    "subject_code": {"type": "string", "description": "Subject code (e.g., 'F23L1W004')"},
                    "subject_name": {"type": "string", "description": "Subject name or partial name. Use this if you don't have the subject code."}
                },
                "oneOf": [
                    {"required": ["student_index"]},
                    {"required": ["student_name"]}
                ],
                "anyOf": [
                    {"required": ["subject_code"]},
                    {"required": ["subject_name"]}
                ]
            }
        ),
        handler=check_student_passed_subject_handler
    ),
    ToolDef(
        tool=Tool(
            name="exam_list_by_subject_and_date",
            description="List exams for a subject filtered by date (exact date or date range).",
            inputSchema={
                "type": "object",
                "properties": {
                    "subject_code": {"type": "string", "description": "Subject code"},
                    "exam_date": {"type": "string", "description": "Exact exam date (YYYY-MM-DD)"},
                    "start_date": {"type": "string", "description": "Start date for range (YYYY-MM-DD)"},
                    "end_date": {"type": "string", "description": "End date for range (YYYY-MM-DD)"}
                },
                "required": ["subject_code"]
            }
        ),
        handler=exam_list_by_subject_and_date_handler
    ),
    ToolDef(
        tool=Tool(
            name="exam_best_result",
            description="Get best exam result for a student in a subject.",
            inputSchema={
                "type": "object",
                "properties": {
                    "student_index": {"type": "integer", "description": "Student index number"},
                    "subject_code": {"type": "string", "description": "Subject code"}
                },
                "required": ["student_index", "subject_code"]
            }
        ),
        handler=exam_best_result_handler
    ),
    ToolDef(
        tool=Tool(
            name="exam_record_create",
            description="Create an exam record for a student in a subject. Creates exam session if needed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "student_index": {"type": "integer", "description": "Student index number"},
                    "subject_code": {"type": "string", "description": "Subject code"},
                    "grade": {"type": "integer", "description": "Grade (5-10)"},
                    "passed": {"type": "boolean", "description": "Whether passed (auto-calculated if not provided)"},
                    "exam_date": {"type": "string", "description": "Exam date (YYYY-MM-DD)"},
                    "session_type": {"type": "string", "description": "Session type (January, June, August)", "default": "January"},
                    "year": {"type": "integer", "description": "Year (defaults to exam_date year)"}
                },
                "required": ["student_index", "subject_code", "grade", "exam_date"]
            }
        ),
        handler=exam_record_create_handler
    ),
    ToolDef(
        tool=Tool(
            name="exam_record_update",
            description="Update an exam record (identify by exam_id or student_index+subject_code).",
            inputSchema={
                "type": "object",
                "properties": {
                    "exam_id": {"type": "integer", "description": "Exam ID"},
                    "student_index": {"type": "integer", "description": "Student index number"},
                    "subject_code": {"type": "string", "description": "Subject code"},
                    "grade": {"type": "integer", "description": "New grade (5-10)"},
                    "passed": {"type": "boolean", "description": "New passed status"}
                }
            }
        ),
        handler=exam_record_update_handler
    ),
]
