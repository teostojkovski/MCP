"""
Consultation MCP tools. Role-based: student, professor, admin.
"""
from datetime import date, time
from mcp.types import Tool, TextContent
from app.tools.registry import ToolDef
from app.queries import consultations as cq


def _identity(arguments: dict):
    sid = (arguments or {}).get("session_id")
    if not sid:
        return None
    return cq.get_user_identity(sid)


def _allow_student(identity: dict) -> bool:
    return identity and identity.get("role") in ("student", "admin")


def _allow_professor(identity: dict, professor_id: int) -> bool:
    if not identity:
        return False
    if identity.get("role") == "admin":
        return True
    if identity.get("role") == "professor":
        return identity.get("professor_id") == professor_id
    return False


def _allow_admin(identity: dict) -> bool:
    return identity and identity.get("role") == "admin"


async def consultation_list_professors_handler(arguments: dict) -> list[TextContent]:
    """List all professors (for choosing who to book with). Requires student or admin login."""
    identity = _identity(arguments)
    if not identity:
        return [TextContent(type="text", text="ERROR: Not authenticated. Log in as a student (or admin) to see professors. Use auth_start then auth_status with your credentials.")]
    role = identity.get("role")
    if role not in ("student", "admin"):
        return [TextContent(type="text", text=f"ERROR: Only students and admins can list professors. You are logged in as {role!r}.")]
    professors = cq.list_professors()
    if not professors:
        return [TextContent(type="text", text="No professors found. An admin may need to run the consultation seed (e.g. py -m app.seed.consultations) to add professors.")]
    lines = ["Professors (you can book consultations with any of these):"]
    for p in professors:
        lines.append(f"  {p['id']}: {p['first_name']} {p['last_name']} ({p['email']})")
    return [TextContent(type="text", text="\n".join(lines))]


async def consultation_list_available_slots_handler(arguments: dict) -> list[TextContent]:
    """List available consultation slots for a professor (student or admin)."""
    identity = _identity(arguments)
    if not identity:
        return [TextContent(type="text", text="ERROR: Not authenticated.")]
    professor_id = arguments.get("professor_id")
    if professor_id is None:
        return [TextContent(type="text", text="ERROR: professor_id is required.")]
    professor_id = int(professor_id)
    student_index = arguments.get("student_index")
    if student_index is not None:
        student_index = int(student_index)
    elif identity.get("role") == "student":
        student_index = identity.get("student_index")
    elif identity.get("role") == "admin":
        return [TextContent(type="text", text="ERROR: As admin, pass student_index to list slots for that student.")]
    else:
        return [TextContent(type="text", text="ERROR: Only students (or admin with student_index) can list available slots.")]
    if student_index is None:
        return [TextContent(type="text", text="ERROR: Your account is not linked to a student. Students must log in with a student account (e.g. student_XXXXX) to see available slots. Admin can pass student_index.")]
    date_from = arguments.get("date_from")
    date_to = arguments.get("date_to")
    if not date_from or not date_to:
        return [TextContent(type="text", text="ERROR: date_from and date_to (YYYY-MM-DD) are required.")]
    try:
        date_from = date.fromisoformat(date_from)
        date_to = date.fromisoformat(date_to)
    except ValueError:
        return [TextContent(type="text", text="ERROR: Invalid date format. Use YYYY-MM-DD.")]
    if not _allow_student(identity) and not _allow_admin(identity):
        return [TextContent(type="text", text="ERROR: Only students or admins can list available slots.")]
    slots = cq.list_available_slots(professor_id, student_index, date_from, date_to)
    if not slots:
        return [TextContent(type="text", text="No available slots in the given range.")]
    lines = [
        f"Free intervals for professor {professor_id} ({date_from} to {date_to}). "
        "You can book 15, 30, or 60 minutes within any interval:"
    ]
    for s in slots[:80]:
        lines.append(f"  {s['date']} {s['start_time']}-{s['end_time']}")
    if len(slots) > 80:
        lines.append(f"  ... and {len(slots) - 80} more.")
    return [TextContent(type="text", text="\n".join(lines))]


async def consultation_book_slot_handler(arguments: dict) -> list[TextContent]:
    """Book a consultation slot (student or admin for a student)."""
    identity = _identity(arguments)
    if not identity:
        return [TextContent(type="text", text="ERROR: Not authenticated.")]
    student_index = arguments.get("student_index")
    if student_index is not None:
        student_index = int(student_index)
    elif identity.get("role") == "student":
        student_index = identity.get("student_index")
    else:
        student_index = None
    if student_index is None and identity.get("role") != "admin":
        return [TextContent(type="text", text="ERROR: student_index required (or login as student).")]
    if identity.get("role") == "admin" and student_index is None:
        return [TextContent(type="text", text="ERROR: As admin, pass student_index to book for that student.")]
    professor_id = arguments.get("professor_id")
    booking_date = arguments.get("date")
    start_time_str = arguments.get("start_time")
    duration_minutes = arguments.get("duration_minutes")
    if professor_id is None or not booking_date or start_time_str is None or duration_minutes is None:
        return [TextContent(type="text", text="ERROR: professor_id, date (YYYY-MM-DD), start_time (HH:MM), duration_minutes (15, 30, or 60) required.")]
    professor_id = int(professor_id)
    duration_minutes = int(duration_minutes)
    if duration_minutes not in (15, 30, 60):
        return [TextContent(type="text", text="ERROR: duration_minutes must be 15, 30, or 60.")]
    try:
        booking_date = date.fromisoformat(booking_date)
        h, m = map(int, start_time_str.strip().split(":"))
        start_time = time(hour=h, minute=m)
    except (ValueError, TypeError):
        return [TextContent(type="text", text="ERROR: Invalid date or start_time. Use YYYY-MM-DD and HH:MM.")]
    if not _allow_student(identity) and not _allow_admin(identity):
        return [TextContent(type="text", text="ERROR: Only students or admins can book slots.")]
    try:
        out = cq.book_slot(student_index, professor_id, booking_date, start_time, duration_minutes)
        return [TextContent(type="text", text=f"Booked: id={out['id']} {out['date']} {out['start_time']}-{out['end_time']}")]
    except ValueError as e:
        return [TextContent(type="text", text=f"ERROR: {e}")]


async def consultation_cancel_booking_handler(arguments: dict) -> list[TextContent]:
    """Cancel a consultation booking (student cancels own; admin can cancel any)."""
    identity = _identity(arguments)
    if not identity:
        return [TextContent(type="text", text="ERROR: Not authenticated.")]
    booking_id = arguments.get("booking_id")
    if booking_id is None:
        return [TextContent(type="text", text="ERROR: booking_id required.")]
    booking_id = int(booking_id)
    student_index = arguments.get("student_index")
    if student_index is not None:
        student_index = int(student_index)
    elif identity.get("role") == "student":
        student_index = identity.get("student_index")
    elif identity.get("role") == "admin":
        return [TextContent(type="text", text="ERROR: As admin, pass student_index to cancel that student's booking.")]
    else:
        student_index = None
    if student_index is None:
        return [TextContent(type="text", text="ERROR: student_index required (or login as student).")]
    try:
        out = cq.cancel_booking(student_index, booking_id)
        if out is None:
            return [TextContent(type="text", text="ERROR: Booking not found or not yours to cancel.")]
        return [TextContent(type="text", text=f"Cancelled: {out['date']} {out['start_time']}-{out['end_time']}")]
    except ValueError as e:
        return [TextContent(type="text", text=f"ERROR: {e}")]


async def consultation_list_my_bookings_handler(arguments: dict) -> list[TextContent]:
    """List my consultation bookings (student sees own; professor sees bookings for them)."""
    identity = _identity(arguments)
    if not identity:
        return [TextContent(type="text", text="ERROR: Not authenticated.")]
    role = identity.get("role")
    if role == "student":
        student_index = identity.get("student_index")
        if student_index is None:
            return [TextContent(type="text", text="ERROR: Your user account is not linked to a student.")]
        bookings = cq.list_my_bookings_student(student_index)
        lines = ["My consultation bookings:"]
        for b in bookings:
            lines.append(f"  id={b['id']} {b['date']} {b['start_time']}-{b['end_time']} with {b['professor_name']}")
    elif role == "professor":
        professor_id = identity.get("professor_id")
        if professor_id is None:
            return [TextContent(type="text", text="ERROR: Your user account is not linked to a professor.")]
        bookings = cq.list_bookings_professor(professor_id)
        lines = ["Bookings for my consultations:"]
        for b in bookings:
            lines.append(f"  id={b['id']} {b['date']} {b['start_time']}-{b['end_time']} student {b['student_name']} ({b['student_index']})")
    elif role == "admin":
        professor_id = arguments.get("professor_id")
        if professor_id is not None:
            professor_id = int(professor_id)
            bookings = cq.list_bookings_professor(professor_id)
            lines = [f"Bookings for professor {professor_id}:"]
            for b in bookings:
                lines.append(f"  id={b['id']} {b['date']} {b['start_time']}-{b['end_time']} student {b['student_name']}")
        else:
            return [TextContent(type="text", text="ERROR: As admin, pass professor_id to list that professor's bookings.")]
    else:
        return [TextContent(type="text", text="ERROR: Unknown role.")]
    if not bookings:
        return [TextContent(type="text", text="No bookings.")]
    return [TextContent(type="text", text="\n".join(lines))]


async def consultation_create_availability_handler(arguments: dict) -> list[TextContent]:
    """Create a consultation availability window (professor or admin)."""
    identity = _identity(arguments)
    if not identity:
        return [TextContent(type="text", text="ERROR: Not authenticated.")]
    professor_id = arguments.get("professor_id")
    if professor_id is not None:
        professor_id = int(professor_id)
    elif identity.get("role") == "professor":
        professor_id = identity.get("professor_id")
    else:
        professor_id = None
    if professor_id is None:
        return [TextContent(type="text", text="ERROR: professor_id required (or login as professor).")]
    if not _allow_professor(identity, professor_id):
        return [TextContent(type="text", text="ERROR: You can only create availability for yourself (or login as admin).")]
    day_of_week = arguments.get("day_of_week")
    start_time_str = arguments.get("start_time")
    end_time_str = arguments.get("end_time")
    slot_duration = arguments.get("slot_duration", 15)
    if day_of_week is None or not start_time_str or not end_time_str:
        return [TextContent(type="text", text="ERROR: day_of_week (0-6), start_time (HH:MM), end_time (HH:MM) required. slot_duration optional (default 15).")]
    day_of_week = int(day_of_week)
    slot_duration = int(slot_duration) if slot_duration is not None else 15
    try:
        h, m = map(int, start_time_str.strip().split(":"))
        start_time = time(hour=h, minute=m)
        h, m = map(int, end_time_str.strip().split(":"))
        end_time = time(hour=h, minute=m)
    except (ValueError, TypeError):
        return [TextContent(type="text", text="ERROR: Invalid start_time or end_time. Use HH:MM.")]
    try:
        out = cq.create_availability(professor_id, day_of_week, start_time, end_time, slot_duration)
        return [TextContent(type="text", text=f"Created availability id={out['id']} day={out['day_of_week']} {out['start_time']}-{out['end_time']} slot={out['slot_duration']}min")]
    except ValueError as e:
        return [TextContent(type="text", text=f"ERROR: {e}")]


async def consultation_edit_availability_handler(arguments: dict) -> list[TextContent]:
    """Edit a consultation availability (professor owns it or admin)."""
    identity = _identity(arguments)
    if not identity:
        return [TextContent(type="text", text="ERROR: Not authenticated.")]
    professor_id = arguments.get("professor_id")
    availability_id = arguments.get("availability_id")
    if professor_id is not None:
        professor_id = int(professor_id)
    elif identity.get("role") == "professor":
        professor_id = identity.get("professor_id")
    else:
        professor_id = None
    if professor_id is None or availability_id is None:
        return [TextContent(type="text", text="ERROR: professor_id and availability_id required.")]
    availability_id = int(availability_id)
    if not _allow_professor(identity, professor_id):
        return [TextContent(type="text", text="ERROR: You can only edit your own availability (or login as admin).")]
    start_time_str = arguments.get("start_time")
    end_time_str = arguments.get("end_time")
    slot_duration = arguments.get("slot_duration", 15)
    if not start_time_str or not end_time_str:
        return [TextContent(type="text", text="ERROR: start_time (HH:MM), end_time (HH:MM) required. slot_duration optional (default 15).")]
    slot_duration = int(slot_duration) if slot_duration is not None else 15
    try:
        h, m = map(int, start_time_str.strip().split(":"))
        start_time = time(hour=h, minute=m)
        h, m = map(int, end_time_str.strip().split(":"))
        end_time = time(hour=h, minute=m)
    except (ValueError, TypeError):
        return [TextContent(type="text", text="ERROR: Invalid start_time or end_time. Use HH:MM.")]
    try:
        out = cq.edit_availability(professor_id, availability_id, start_time, end_time, slot_duration)
        if out is None:
            return [TextContent(type="text", text="ERROR: Availability not found or not yours.")]
        return [TextContent(type="text", text=f"Updated availability id={out['id']} {out['start_time']}-{out['end_time']} slot={out['slot_duration']}min")]
    except ValueError as e:
        return [TextContent(type="text", text=f"ERROR: {e}")]


async def consultation_block_date_handler(arguments: dict) -> list[TextContent]:
    """Block a date so no consultations are offered that day (professor or admin)."""
    identity = _identity(arguments)
    if not identity:
        return [TextContent(type="text", text="ERROR: Not authenticated.")]
    professor_id = arguments.get("professor_id")
    if professor_id is not None:
        professor_id = int(professor_id)
    elif identity.get("role") == "professor":
        professor_id = identity.get("professor_id")
    else:
        professor_id = None
    if professor_id is None:
        return [TextContent(type="text", text="ERROR: professor_id required (or login as professor).")]
    if not _allow_professor(identity, professor_id):
        return [TextContent(type="text", text="ERROR: You can only block dates for yourself (or login as admin).")]
    date_str = arguments.get("date")
    if not date_str:
        return [TextContent(type="text", text="ERROR: date (YYYY-MM-DD) required.")]
    try:
        block_date_val = date.fromisoformat(date_str)
    except ValueError:
        return [TextContent(type="text", text="ERROR: Invalid date. Use YYYY-MM-DD.")]
    try:
        cq.block_date(professor_id, block_date_val)
        return [TextContent(type="text", text=f"Blocked {date_str}: no consultations for professor {professor_id} on that day.")]
    except ValueError as e:
        return [TextContent(type="text", text=f"ERROR: {e}")]


async def consultation_unblock_date_handler(arguments: dict) -> list[TextContent]:
    """Unblock a date so consultations are offered again (professor or admin)."""
    identity = _identity(arguments)
    if not identity:
        return [TextContent(type="text", text="ERROR: Not authenticated.")]
    professor_id = arguments.get("professor_id")
    if professor_id is not None:
        professor_id = int(professor_id)
    elif identity.get("role") == "professor":
        professor_id = identity.get("professor_id")
    else:
        professor_id = None
    if professor_id is None:
        return [TextContent(type="text", text="ERROR: professor_id required (or login as professor).")]
    if not _allow_professor(identity, professor_id):
        return [TextContent(type="text", text="ERROR: You can only unblock dates for yourself (or login as admin).")]
    date_str = arguments.get("date")
    if not date_str:
        return [TextContent(type="text", text="ERROR: date (YYYY-MM-DD) required.")]
    try:
        block_date_val = date.fromisoformat(date_str)
    except ValueError:
        return [TextContent(type="text", text="ERROR: Invalid date. Use YYYY-MM-DD.")]
    ok = cq.unblock_date(professor_id, block_date_val)
    if ok:
        return [TextContent(type="text", text=f"Unblocked {date_str} for professor {professor_id}.")]
    return [TextContent(type="text", text=f"Date {date_str} was not blocked (or already unblocked).")]


async def consultation_list_blocked_dates_handler(arguments: dict) -> list[TextContent]:
    """List dates when a professor has cancelled consultations (blocked)."""
    identity = _identity(arguments)
    if not identity:
        return [TextContent(type="text", text="ERROR: Not authenticated.")]
    professor_id = arguments.get("professor_id")
    if professor_id is None:
        return [TextContent(type="text", text="ERROR: professor_id required.")]
    professor_id = int(professor_id)
    if not _allow_professor(identity, professor_id):
        return [TextContent(type="text", text="ERROR: You can only list your own blocked dates (or login as admin).")]
    date_from = arguments.get("date_from") or ""
    date_to = arguments.get("date_to") or ""
    if not date_from or not date_to:
        return [TextContent(type="text", text="ERROR: date_from and date_to (YYYY-MM-DD) required.")]
    try:
        date_from_val = date.fromisoformat(date_from)
        date_to_val = date.fromisoformat(date_to)
    except ValueError:
        return [TextContent(type="text", text="ERROR: Invalid date format. Use YYYY-MM-DD.")]
    blocked = cq.list_blocked_dates(professor_id, date_from_val, date_to_val)
    if not blocked:
        return [TextContent(type="text", text=f"No blocked dates for professor {professor_id} in range.")]
    return [TextContent(type="text", text=f"Blocked dates for professor {professor_id}: " + ", ".join(blocked))]


async def consultation_draft_consultation_email_handler(arguments: dict) -> list[TextContent]:
    """Draft the consultation email to the professor (student only). Show this to the student for confirmation before sending."""
    identity = _identity(arguments)
    if not identity:
        return [TextContent(type="text", text="ERROR: Not authenticated.")]
    if identity.get("role") != "student":
        return [TextContent(type="text", text="ERROR: Only students can draft consultation emails.")]
    student_index = identity.get("student_index")
    if student_index is None:
        return [TextContent(type="text", text="ERROR: Your account is not linked to a student.")]
    booking_id = arguments.get("booking_id")
    consultation_reason = (arguments.get("consultation_reason") or "").strip()
    if not booking_id:
        return [TextContent(type="text", text="ERROR: booking_id is required.")]
    booking_id = int(booking_id)
    try:
        subject, body = cq.compose_consultation_email(booking_id, student_index, consultation_reason)
        return [
            TextContent(
                type="text",
                text=(
                    "DRAFT – show this to the student and ask for confirmation before calling consultation_send_consultation_email.\n\n"
                    f"Subject: {subject}\n\n"
                    f"Body:\n{body}"
                ),
            )
        ]
    except ValueError as e:
        return [TextContent(type="text", text=f"ERROR: {e}")]


async def consultation_send_consultation_email_handler(arguments: dict) -> list[TextContent]:
    """Send the consultation email to the professor (student only). Call only after the student confirmed the draft. Requires approved_by_user=true."""
    identity = _identity(arguments)
    if not identity:
        return [TextContent(type="text", text="ERROR: Not authenticated.")]
    if identity.get("role") != "student":
        return [TextContent(type="text", text="ERROR: Only students can send consultation emails.")]
    student_index = identity.get("student_index")
    if student_index is None:
        return [TextContent(type="text", text="ERROR: Your account is not linked to a student.")]
    booking_id = arguments.get("booking_id")
    consultation_reason = (arguments.get("consultation_reason") or "").strip()
    approved_by_user = arguments.get("approved_by_user")
    if not booking_id:
        return [TextContent(type="text", text="ERROR: booking_id is required.")]
    if approved_by_user is not True and str(approved_by_user).lower() not in ("true", "1", "yes"):
        return [TextContent(type="text", text="ERROR: You must set approved_by_user to true after the student has confirmed the draft.")]
    booking_id = int(booking_id)
    result = cq.send_consultation_email_for_booking(booking_id, student_index, consultation_reason)
    if result.get("sent"):
        return [TextContent(type="text", text=f"Email sent successfully. Message id: {result.get('message_id', '')}")]
    return [TextContent(type="text", text=f"Failed to send email: {result.get('error', 'Unknown error')}")]


CONSULTATION_TOOLS = [
    ToolDef(
        tool=Tool(
            name="consultation_list_professors",
            description="List all professors (for consultations). Requires student or admin login. Use after auth_status to see professors and then list available slots or book.",
            inputSchema={"type": "object", "properties": {}},
        ),
        handler=consultation_list_professors_handler,
    ),
    ToolDef(
        tool=Tool(
            name="consultation_list_available_slots",
            description="List free consultation intervals for a professor. Students can book 15, 30, or 60 min within any interval. Pass date_from, date_to (YYYY-MM-DD).",
            inputSchema={
                "type": "object",
                "properties": {
                    "professor_id": {"type": "integer"},
                    "student_index": {"type": "integer", "description": "Required if admin; otherwise from session"},
                    "date_from": {"type": "string", "description": "YYYY-MM-DD"},
                    "date_to": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["professor_id", "date_from", "date_to"],
            },
        ),
        handler=consultation_list_available_slots_handler,
    ),
    ToolDef(
        tool=Tool(
            name="consultation_book_slot",
            description="Book a consultation. duration_minutes must be 15, 30, or 60. Start time must be inside a free interval from list_available_slots.",
            inputSchema={
                "type": "object",
                "properties": {
                    "professor_id": {"type": "integer"},
                    "student_index": {"type": "integer", "description": "Required if admin"},
                    "date": {"type": "string"},
                    "start_time": {"type": "string"},
                    "duration_minutes": {"type": "integer"},
                },
                "required": ["professor_id", "date", "start_time", "duration_minutes"],
            },
        ),
        handler=consultation_book_slot_handler,
    ),
    ToolDef(
        tool=Tool(
            name="consultation_cancel_booking",
            description="Cancel a consultation booking. Student cancels own; admin passes student_index and booking_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "booking_id": {"type": "integer"},
                    "student_index": {"type": "integer", "description": "Required if admin"},
                },
                "required": ["booking_id"],
            },
        ),
        handler=consultation_cancel_booking_handler,
    ),
    ToolDef(
        tool=Tool(
            name="consultation_list_my_bookings",
            description="List my consultation bookings (student: own bookings; professor: bookings for me; admin: pass professor_id).",
            inputSchema={
                "type": "object",
                "properties": {"professor_id": {"type": "integer", "description": "For admin: list this professor's bookings"}},
            },
        ),
        handler=consultation_list_my_bookings_handler,
    ),
    ToolDef(
        tool=Tool(
            name="consultation_create_availability",
            description="Create consultation time frame (professor or admin). day_of_week 0=Monday, start_time/end_time HH:MM. Students book 15/30/60 min within. slot_duration optional (default 15).",
            inputSchema={
                "type": "object",
                "properties": {
                    "professor_id": {"type": "integer", "description": "Required if admin"},
                    "day_of_week": {"type": "integer"},
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                    "slot_duration": {"type": "integer", "description": "Optional, default 15"},
                },
                "required": ["day_of_week", "start_time", "end_time"],
            },
        ),
        handler=consultation_create_availability_handler,
    ),
    ToolDef(
        tool=Tool(
            name="consultation_edit_availability",
            description="Edit consultation availability (professor or admin).",
            inputSchema={
                "type": "object",
                "properties": {
                    "professor_id": {"type": "integer"},
                    "availability_id": {"type": "integer"},
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                    "slot_duration": {"type": "integer"},
                },
                "required": ["professor_id", "availability_id", "start_time", "end_time"],
            },
        ),
        handler=consultation_edit_availability_handler,
    ),
    ToolDef(
        tool=Tool(
            name="consultation_block_date",
            description="Block a date so no consultations are offered that day (professor or admin).",
            inputSchema={
                "type": "object",
                "properties": {
                    "professor_id": {"type": "integer", "description": "Required if admin"},
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["date"],
            },
        ),
        handler=consultation_block_date_handler,
    ),
    ToolDef(
        tool=Tool(
            name="consultation_unblock_date",
            description="Unblock a date so consultations are offered again.",
            inputSchema={
                "type": "object",
                "properties": {
                    "professor_id": {"type": "integer"},
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["date"],
            },
        ),
        handler=consultation_unblock_date_handler,
    ),
    ToolDef(
        tool=Tool(
            name="consultation_list_blocked_dates",
            description="List dates when a professor has blocked consultations (no slots that day).",
            inputSchema={
                "type": "object",
                "properties": {
                    "professor_id": {"type": "integer"},
                    "date_from": {"type": "string"},
                    "date_to": {"type": "string"},
                },
                "required": ["professor_id", "date_from", "date_to"],
            },
        ),
        handler=consultation_list_blocked_dates_handler,
    ),
    ToolDef(
        tool=Tool(
            name="consultation_draft_consultation_email",
            description="Draft the email to the professor about a booked consultation (student only). Use after a student books and says they want to email the professor. Ask what the consultation is for (consultation_reason), then call this to get subject and body. Show the draft to the student and only call consultation_send_consultation_email after they confirm.",
            inputSchema={
                "type": "object",
                "properties": {
                    "booking_id": {"type": "integer", "description": "The consultation booking id"},
                    "consultation_reason": {"type": "string", "description": "What the consultation is about (from the student)"},
                },
                "required": ["booking_id", "consultation_reason"],
            },
        ),
        handler=consultation_draft_consultation_email_handler,
    ),
    ToolDef(
        tool=Tool(
            name="consultation_send_consultation_email",
            description="Send the consultation email to the professor via Resend (student only). Call only after showing the draft and getting explicit student confirmation. Must pass approved_by_user=true.",
            inputSchema={
                "type": "object",
                "properties": {
                    "booking_id": {"type": "integer"},
                    "consultation_reason": {"type": "string"},
                    "approved_by_user": {"type": "boolean", "description": "Must be true; set only after student confirmed the draft"},
                },
                "required": ["booking_id", "consultation_reason", "approved_by_user"],
            },
        ),
        handler=consultation_send_consultation_email_handler,
    ),
]
