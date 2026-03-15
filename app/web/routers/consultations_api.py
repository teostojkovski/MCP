"""
Consultations API: all /consultations/api/* routes. Same paths and behavior as original.
"""
from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.db import SessionLocal
from app.models import ConsultationAvailability
from app.queries import consultations as cq
from app.web.session import require_session


router = APIRouter()


@router.get("/consultations/api/professors")
def api_professors(request: Request):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    role = (identity.get("role") or "").lower()
    if role not in ("student", "admin"):
        return JSONResponse({"error": "Only students and admins can list professors"})
    professors = cq.list_professors()
    return JSONResponse({"professors": professors})


@router.get("/consultations/api/slots")
def api_slots(request: Request, professor_id: int, date_from: str, date_to: str):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    student_index = identity.get("student_index")
    if student_index is None and identity.get("role") != "admin":
        return JSONResponse({"error": "Student account required"})
    if student_index is None:
        return JSONResponse({"error": "Pass student_index for admin"})
    try:
        df = date.fromisoformat(date_from)
        dt = date.fromisoformat(date_to)
    except ValueError:
        return JSONResponse({"error": "Invalid date format"})
    slots = cq.list_available_slots(professor_id, student_index, df, dt)
    return JSONResponse({"slots": slots})


@router.post("/consultations/api/book")
async def api_book(request: Request):
    from datetime import time
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    body = await request.json()
    student_index = identity.get("student_index")
    if student_index is None and identity.get("role") == "admin":
        student_index = body.get("student_index")
    if student_index is None:
        return JSONResponse({"error": "Student account required"})
    professor_id = body.get("professor_id")
    date_str = body.get("date")
    start_time_str = body.get("start_time")
    duration_minutes = body.get("duration_minutes")
    if not all([professor_id, date_str, start_time_str, duration_minutes]):
        return JSONResponse({"error": "professor_id, date, start_time, duration_minutes required"})
    try:
        booking_date = date.fromisoformat(date_str)
        h, m = map(int, start_time_str.split(":"))
        start_time = time(hour=h, minute=m)
        result = cq.book_slot(student_index, professor_id,
                              booking_date, start_time, int(duration_minutes))
        return JSONResponse({"message": "Booked", "id": result["id"]})
    except ValueError as e:
        return JSONResponse({"error": str(e)})


@router.get("/consultations/api/my-bookings")
def api_my_bookings(request: Request):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    student_index = identity.get("student_index")
    if student_index is None:
        return JSONResponse({"error": "Student account required"})
    bookings = cq.list_my_bookings_student(student_index)

    def dur(b):
        s = b.get("start_time", "0:0").split(":")
        e = b.get("end_time", "0:0").split(":")
        return (int(e[0])*60+int(e[1])) - (int(s[0])*60+int(s[1]))
    for b in bookings:
        b["duration"] = dur(b)
    return JSONResponse({"bookings": bookings})


@router.post("/consultations/api/cancel-booking")
async def api_cancel_booking(request: Request):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    body = await request.json()
    booking_id = body.get("booking_id")
    student_index = identity.get("student_index")
    if student_index is None:
        return JSONResponse({"error": "Student account required"})
    try:
        out = cq.cancel_booking(student_index, booking_id)
        if out:
            return JSONResponse({"message": "Cancelled"})
        return JSONResponse({"error": "Booking not found or not yours"})
    except ValueError as e:
        return JSONResponse({"error": str(e)})


@router.get("/consultations/api/professor-bookings")
def api_professor_bookings(request: Request, professor_id: int):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    role = (identity.get("role") or "").lower()
    if role not in ("professor", "admin"):
        return JSONResponse({"error": "Professor or admin only"})
    if role == "professor" and identity.get("professor_id") != professor_id:
        return JSONResponse({"error": "You can only view your own bookings"})
    bookings = cq.list_bookings_professor(professor_id)
    return JSONResponse({"bookings": bookings})


@router.get("/consultations/api/professor-availabilities")
def api_professor_availabilities(request: Request, professor_id: int):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    if (identity.get("role") or "").lower() == "professor" and identity.get("professor_id") != professor_id:
        return JSONResponse({"error": "You can only view your own availability"})
    db = SessionLocal()
    try:
        rows = db.query(ConsultationAvailability).filter(ConsultationAvailability.professor_id == professor_id).order_by(
            ConsultationAvailability.day_of_week, ConsultationAvailability.start_time).all()
        availabilities = [{"id": a.id, "day_of_week": a.day_of_week, "start_time": a.start_time.strftime(
            "%H:%M"), "end_time": a.end_time.strftime("%H:%M"), "slot_duration": a.slot_duration} for a in rows]
        return JSONResponse({"availabilities": availabilities})
    finally:
        db.close()


@router.post("/consultations/api/availability")
async def api_add_availability(request: Request):
    from datetime import time
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    body = await request.json()
    professor_id = body.get("professor_id")
    if (identity.get("role") or "").lower() == "professor" and identity.get("professor_id") != professor_id:
        return JSONResponse({"error": "You can only add your own availability"})
    try:
        h, m = map(int, body.get("start_time", "0:0").split(":"))
        start_time = time(hour=h, minute=m)
        h, m = map(int, body.get("end_time", "0:0").split(":"))
        end_time = time(hour=h, minute=m)
        out = cq.create_availability(professor_id, int(body.get(
            "day_of_week")), start_time, end_time, int(body.get("slot_duration", 15)))
        return JSONResponse({"message": "Added", "id": out["id"]})
    except ValueError as e:
        return JSONResponse({"error": str(e)})


@router.get("/consultations/api/blocked-dates")
def api_blocked_dates(request: Request, professor_id: int, date_from: str, date_to: str):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    if (identity.get("role") or "").lower() == "professor" and identity.get("professor_id") != professor_id:
        return JSONResponse({"error": "Forbidden"})
    try:
        df = date.fromisoformat(date_from)
        dt = date.fromisoformat(date_to)
    except ValueError:
        return JSONResponse({"error": "Invalid date"})
    dates = cq.list_blocked_dates(professor_id, df, dt)
    return JSONResponse({"dates": dates})


@router.post("/consultations/api/block-date")
async def api_block_date(request: Request):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    body = await request.json()
    professor_id = body.get("professor_id")
    if (identity.get("role") or "").lower() == "professor" and identity.get("professor_id") != professor_id:
        return JSONResponse({"error": "Forbidden"})
    try:
        d = date.fromisoformat(body.get("date", ""))
        cq.block_date(professor_id, d)
        return JSONResponse({"message": "Blocked"})
    except ValueError as e:
        return JSONResponse({"error": str(e)})


@router.post("/consultations/api/unblock-date")
async def api_unblock_date(request: Request):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    body = await request.json()
    professor_id = body.get("professor_id")
    if (identity.get("role") or "").lower() == "professor" and identity.get("professor_id") != professor_id:
        return JSONResponse({"error": "Forbidden"})
    try:
        d = date.fromisoformat(body.get("date", ""))
        ok = cq.unblock_date(professor_id, d)
        return JSONResponse({"message": "Unblocked" if ok else "Not found"})
    except ValueError as e:
        return JSONResponse({"error": str(e)})


@router.put("/consultations/api/availability/{availability_id:int}")
async def api_edit_availability(request: Request, availability_id: int):
    from datetime import time
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    body = await request.json()
    professor_id = body.get("professor_id")
    if (identity.get("role") or "").lower() == "professor" and identity.get("professor_id") != professor_id:
        return JSONResponse({"error": "Forbidden"})
    try:
        h, m = map(int, body.get("start_time", "0:0").split(":"))
        start_time = time(hour=h, minute=m)
        h, m = map(int, body.get("end_time", "0:0").split(":"))
        end_time = time(hour=h, minute=m)
        out = cq.edit_availability(professor_id, availability_id, start_time, end_time, int(
            body.get("slot_duration", 15)))
        if out is None:
            return JSONResponse({"error": "Availability not found"})
        return JSONResponse({"message": "Updated", "id": out["id"]})
    except ValueError as e:
        return JSONResponse({"error": str(e)})


@router.delete("/consultations/api/availability/{availability_id:int}")
def api_delete_availability(request: Request, availability_id: int, professor_id: int):
    _, identity = require_session(request)
    if not identity:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    if (identity.get("role") or "").lower() == "professor" and identity.get("professor_id") != professor_id:
        return JSONResponse({"error": "Forbidden"})
    ok = cq.delete_availability(professor_id, availability_id)
    return JSONResponse({"message": "Deleted"} if ok else {"error": "Not found"})