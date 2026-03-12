"""
Consultation availability and booking queries.
Professors set time frames (e.g. Monday 10:00-14:00). Students book 15, 30, or 60 min
anywhere inside; the system checks the interval fits in a free part of the frame.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.db import SessionLocal
from app.models import (
    ConsultationAvailability,
    ConsultationBlock,
    ConsultationBooking,
    ConsultationEmailLog,
    Professor,
    Student,
)


def _time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _minutes_to_time(m: int) -> time:
    h, mn = divmod(m, 60)
    return time(hour=h, minute=mn)


def _merge_intervals(intervals: List[tuple[int, int]]) -> List[tuple[int, int]]:
    """Merge overlapping intervals. Input sorted by start."""
    if not intervals:
        return []
    out = [list(intervals[0])]
    for a, b in intervals[1:]:
        if a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def _subtract_busy_from_intervals(
    free: List[tuple[int, int]], busy: List[tuple[int, int]]
) -> List[tuple[int, int]]:
    """Subtract busy intervals from free; return new free list."""
    for (bs, be) in busy:
        new_free = []
        for (fs, fe) in free:
            if fe <= bs or fs >= be:
                new_free.append((fs, fe))
            else:
                if fs < bs:
                    new_free.append((fs, min(fe, bs)))
                if be < fe:
                    new_free.append((max(fs, be), fe))
        free = new_free
    return sorted(free)


def _booking_overlaps_interval(
    booking_start_min: int, booking_end_min: int,
    interval_start: int, interval_end: int
) -> bool:
    return not (interval_end <= booking_start_min or booking_end_min <= interval_start)


def list_available_slots(
    professor_id: int,
    student_index: int,
    date_from: date,
    date_to: date,
) -> List[Dict[str, Any]]:
    """
    List professor's free intervals in [date_from, date_to].
    Students can book 15, 30, or 60 minutes within any shown interval.
    Excludes blocked dates; excludes time already booked; excludes intervals
    that would overlap this student's other bookings.
    """
    session = SessionLocal()
    try:
        professor = session.query(Professor).filter(
            Professor.id == professor_id).first()
        if not professor:
            return []

        student = session.query(Student).filter(
            Student.index == student_index).first()
        if not student:
            return []

        blocked_dates = set(
            row.date for row in
            session.query(ConsultationBlock.date)
            .filter(ConsultationBlock.professor_id == professor_id)
            .filter(ConsultationBlock.date >= date_from)
            .filter(ConsultationBlock.date <= date_to)
            .all()
        )

        student_bookings = (
            session.query(ConsultationBooking)
            .filter(ConsultationBooking.student_index == student_index)
            .filter(ConsultationBooking.date >= date_from)
            .filter(ConsultationBooking.date <= date_to)
            .all()
        )
        student_busy: Dict[date, List[tuple[int, int]]] = {}
        for b in student_bookings:
            student_busy.setdefault(b.date, []).append(
                (_time_to_minutes(b.start_time), _time_to_minutes(b.end_time))
            )

        prof_bookings = (
            session.query(ConsultationBooking)
            .filter(ConsultationBooking.professor_id == professor_id)
            .filter(ConsultationBooking.date >= date_from)
            .filter(ConsultationBooking.date <= date_to)
            .all()
        )
        prof_busy: Dict[date, List[tuple[int, int]]] = {}
        for b in prof_bookings:
            prof_busy.setdefault(b.date, []).append(
                (_time_to_minutes(b.start_time), _time_to_minutes(b.end_time))
            )

        result = []
        d = date_from
        while d <= date_to:
            if d in blocked_dates:
                d += timedelta(days=1)
                continue
            weekday = d.weekday()
            availabilities = (
                session.query(ConsultationAvailability)
                .filter(ConsultationAvailability.professor_id == professor_id)
                .filter(ConsultationAvailability.day_of_week == weekday)
                .all()
            )

            raw = [
                (_time_to_minutes(av.start_time), _time_to_minutes(av.end_time))
                for av in availabilities
            ]
            raw.sort(key=lambda x: x[0])
            free = _merge_intervals(raw)
            free = _subtract_busy_from_intervals(free, prof_busy.get(d, []))
            free = _subtract_busy_from_intervals(free, student_busy.get(d, []))
            for (i_start, i_end) in free:
                if i_end > i_start:
                    result.append({
                        "date": d.isoformat(),
                        "start_time": _minutes_to_time(i_start).strftime("%H:%M"),
                        "end_time": _minutes_to_time(i_end).strftime("%H:%M"),
                    })
            d += timedelta(days=1)

        return result
    finally:
        session.close()


ALLOWED_BOOKING_DURATIONS = (15, 30, 60)


def book_slot(
    student_index: int,
    professor_id: int,
    booking_date: date,
    start_time: time,
    duration_minutes: int,
) -> Dict[str, Any]:
    """
    Book a consultation. Duration must be 15, 30, or 60 minutes.
    The requested interval must lie entirely within a free slot (availability minus existing bookings).
    """
    session = SessionLocal()
    try:
        if duration_minutes not in ALLOWED_BOOKING_DURATIONS:
            raise ValueError(
                f"Duration must be 15, 30, or 60 minutes (got {duration_minutes})"
            )

        professor = session.query(Professor).filter(
            Professor.id == professor_id).first()
        if not professor:
            raise ValueError(f"Professor {professor_id} not found")

        student = session.query(Student).filter(
            Student.index == student_index).first()
        if not student:
            raise ValueError(f"Student {student_index} not found")

        start_min = _time_to_minutes(start_time)
        end_min = start_min + duration_minutes
        if end_min > 24 * 60:
            raise ValueError("Booking end time exceeds midnight")

        if session.query(ConsultationBlock).filter(
            ConsultationBlock.professor_id == professor_id,
            ConsultationBlock.date == booking_date,
        ).first():
            raise ValueError(
                f"Professor has cancelled consultations on {booking_date}")

        weekday = booking_date.weekday()
        availabilities = (
            session.query(ConsultationAvailability)
            .filter(ConsultationAvailability.professor_id == professor_id)
            .filter(ConsultationAvailability.day_of_week == weekday)
            .all()
        )
        raw = [
            (_time_to_minutes(av.start_time), _time_to_minutes(av.end_time))
            for av in availabilities
        ]
        raw.sort(key=lambda x: x[0])
        free = _merge_intervals(raw)

        prof_bookings = (
            session.query(ConsultationBooking)
            .filter(ConsultationBooking.professor_id == professor_id)
            .filter(ConsultationBooking.date == booking_date)
            .all()
        )
        prof_busy = [(_time_to_minutes(b.start_time),
                      _time_to_minutes(b.end_time)) for b in prof_bookings]
        free = _subtract_busy_from_intervals(free, prof_busy)

        found = False
        for (fs, fe) in free:
            if fs <= start_min and end_min <= fe:
                found = True
                break
        if not found:
            raise ValueError(
                f"The time {start_time} for {duration_minutes} min on {booking_date} is not available. "
                "Book only within the free intervals shown by list_available_slots."
            )

        student_bookings = (
            session.query(ConsultationBooking)
            .filter(ConsultationBooking.student_index == student_index)
            .filter(ConsultationBooking.date == booking_date)
            .all()
        )
        for b in student_bookings:
            bs = _time_to_minutes(b.start_time)
            be = _time_to_minutes(b.end_time)
            if _booking_overlaps_interval(bs, be, start_min, end_min):
                raise ValueError(
                    f"You already have a booking at this time: {b.start_time}-{b.end_time}"
                )

        end_time_obj = _minutes_to_time(end_min)
        booking = ConsultationBooking(
            professor_id=professor_id,
            student_index=student_index,
            date=booking_date,
            start_time=start_time,
            end_time=end_time_obj,
        )
        session.add(booking)
        session.commit()
        session.refresh(booking)
        return {
            "id": booking.id,
            "professor_id": booking.professor_id,
            "student_index": booking.student_index,
            "date": booking.date.isoformat(),
            "start_time": booking.start_time.strftime("%H:%M"),
            "end_time": booking.end_time.strftime("%H:%M"),
        }
    except ValueError:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise ValueError(str(e))
    finally:
        session.close()


def cancel_booking(student_index: int, booking_id: int) -> Optional[Dict[str, Any]]:
    """Cancel a booking. Only the student who owns it can cancel. Returns cancelled booking info."""
    session = SessionLocal()
    try:
        booking = (
            session.query(ConsultationBooking)
            .filter(ConsultationBooking.id == booking_id)
            .first()
        )
        if not booking:
            return None
        if booking.student_index != student_index:
            raise ValueError("You can only cancel your own booking")
        out = {
            "id": booking.id,
            "professor_id": booking.professor_id,
            "student_index": booking.student_index,
            "date": booking.date.isoformat(),
            "start_time": booking.start_time.strftime("%H:%M"),
            "end_time": booking.end_time.strftime("%H:%M"),
        }
        session.delete(booking)
        session.commit()
        return out
    except ValueError:
        session.rollback()
        raise
    finally:
        session.close()


def create_availability(
    professor_id: int,
    day_of_week: int,
    start_time: time,
    end_time: time,
    slot_duration: int = 15,
) -> Dict[str, Any]:
    """Create a consultation time frame (one window per day). Students book 15/30/60 min within it.
    0 <= day_of_week <= 6 (Monday=0). slot_duration is minimum bookable (default 15)."""
    session = SessionLocal()
    try:
        if not (0 <= day_of_week <= 6):
            raise ValueError("day_of_week must be 0-6 (Monday=0)")
        if slot_duration <= 0:
            raise ValueError("slot_duration must be positive")
        if _time_to_minutes(start_time) >= _time_to_minutes(end_time):
            raise ValueError("start_time must be before end_time")

        professor = session.query(Professor).filter(
            Professor.id == professor_id).first()
        if not professor:
            raise ValueError(f"Professor {professor_id} not found")

        av = ConsultationAvailability(
            professor_id=professor_id,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            slot_duration=slot_duration,
        )
        session.add(av)
        session.commit()
        session.refresh(av)
        return {
            "id": av.id,
            "professor_id": av.professor_id,
            "day_of_week": av.day_of_week,
            "start_time": av.start_time.strftime("%H:%M"),
            "end_time": av.end_time.strftime("%H:%M"),
            "slot_duration": av.slot_duration,
        }
    except ValueError:
        session.rollback()
        raise
    finally:
        session.close()


def edit_availability(
    professor_id: int,
    availability_id: int,
    start_time: time,
    end_time: time,
    slot_duration: int,
) -> Optional[Dict[str, Any]]:
    """Edit an availability. Only the owning professor (or admin) may edit."""
    session = SessionLocal()
    try:
        av = (
            session.query(ConsultationAvailability)
            .filter(ConsultationAvailability.id == availability_id)
            .first()
        )
        if not av or av.professor_id != professor_id:
            return None
        if slot_duration <= 0:
            raise ValueError("slot_duration must be positive")
        if _time_to_minutes(start_time) >= _time_to_minutes(end_time):
            raise ValueError("start_time must be before end_time")

        av.start_time = start_time
        av.end_time = end_time
        av.slot_duration = slot_duration
        session.commit()
        session.refresh(av)
        return {
            "id": av.id,
            "professor_id": av.professor_id,
            "day_of_week": av.day_of_week,
            "start_time": av.start_time.strftime("%H:%M"),
            "end_time": av.end_time.strftime("%H:%M"),
            "slot_duration": av.slot_duration,
        }
    except ValueError:
        session.rollback()
        raise
    finally:
        session.close()


def delete_availability(professor_id: int, availability_id: int) -> bool:
    """Delete an availability slot. Only the owning professor (or admin) may delete."""
    session = SessionLocal()
    try:
        av = (
            session.query(ConsultationAvailability)
            .filter(ConsultationAvailability.id == availability_id)
            .first()
        )
        if not av or av.professor_id != professor_id:
            return False
        session.delete(av)
        session.commit()
        return True
    finally:
        session.close()


def list_bookings_professor(professor_id: int) -> List[Dict[str, Any]]:
    """List all bookings for a professor."""
    session = SessionLocal()
    try:
        bookings = (
            session.query(ConsultationBooking)
            .filter(ConsultationBooking.professor_id == professor_id)
            .order_by(ConsultationBooking.date, ConsultationBooking.start_time)
            .all()
        )
        out = []
        for b in bookings:
            student = session.query(Student).filter(
                Student.index == b.student_index).first()
            name = f"{student.first_name} {student.last_name}" if student else str(
                b.student_index)
            out.append({
                "id": b.id,
                "student_index": b.student_index,
                "student_name": name,
                "date": b.date.isoformat(),
                "start_time": b.start_time.strftime("%H:%M"),
                "end_time": b.end_time.strftime("%H:%M"),
            })
        return out
    finally:
        session.close()


def list_my_bookings_student(student_index: int) -> List[Dict[str, Any]]:
    """List all bookings for a student."""
    session = SessionLocal()
    try:
        bookings = (
            session.query(ConsultationBooking)
            .filter(ConsultationBooking.student_index == student_index)
            .order_by(ConsultationBooking.date, ConsultationBooking.start_time)
            .all()
        )
        out = []
        for b in bookings:
            prof = session.query(Professor).filter(
                Professor.id == b.professor_id).first()
            name = f"{prof.first_name} {prof.last_name}" if prof else str(
                b.professor_id)
            out.append({
                "id": b.id,
                "professor_id": b.professor_id,
                "professor_name": name,
                "date": b.date.isoformat(),
                "start_time": b.start_time.strftime("%H:%M"),
                "end_time": b.end_time.strftime("%H:%M"),
            })
        return out
    finally:
        session.close()


def block_date(professor_id: int, block_date_val: date) -> Dict[str, Any]:
    """Block a date for consultations (no slots offered that day)."""
    session = SessionLocal()
    try:
        professor = session.query(Professor).filter(
            Professor.id == professor_id).first()
        if not professor:
            raise ValueError(f"Professor {professor_id} not found")
        existing = (
            session.query(ConsultationBlock)
            .filter(ConsultationBlock.professor_id == professor_id)
            .filter(ConsultationBlock.date == block_date_val)
            .first()
        )
        if existing:
            return {"professor_id": professor_id, "date": block_date_val.isoformat(), "blocked": True}
        session.add(ConsultationBlock(
            professor_id=professor_id, date=block_date_val))
        session.commit()
        return {"professor_id": professor_id, "date": block_date_val.isoformat(), "blocked": True}
    except ValueError:
        session.rollback()
        raise
    finally:
        session.close()


def unblock_date(professor_id: int, block_date_val: date) -> bool:
    """Remove a date block so consultations are offered again."""
    session = SessionLocal()
    try:
        deleted = (
            session.query(ConsultationBlock)
            .filter(ConsultationBlock.professor_id == professor_id)
            .filter(ConsultationBlock.date == block_date_val)
            .delete()
        )
        session.commit()
        return deleted > 0
    finally:
        session.close()


def list_blocked_dates(professor_id: int, date_from: date, date_to: date) -> List[str]:
    """List blocked dates for a professor in range."""
    session = SessionLocal()
    try:
        rows = (
            session.query(ConsultationBlock)
            .filter(ConsultationBlock.professor_id == professor_id)
            .filter(ConsultationBlock.date >= date_from)
            .filter(ConsultationBlock.date <= date_to)
            .all()
        )
        return [r.date.isoformat() for r in rows]
    finally:
        session.close()


def list_professors() -> List[Dict[str, Any]]:
    """List all professors (id, name, email)."""
    session = SessionLocal()
    try:
        rows = session.query(Professor).order_by(Professor.id).all()
        return [
            {"id": p.id, "first_name": p.first_name,
                "last_name": p.last_name, "email": p.email}
            for p in rows
        ]
    finally:
        session.close()


def get_user_identity(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Resolve session_id to role and optional professor_id / student_index.
    Returns {"role": "admin"|"professor"|"student", "professor_id": int|None, "student_index": int|None}
    or None if session invalid.
    """
    from app.auth_store import get_session
    from app.models import User

    sess = get_session(session_id)
    if not sess:
        return None
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == sess.user_id).first()
        role = (sess.role or "").strip().lower() if not user else (
            user.role or "").strip().lower()
        if not user:
            return {"role": role, "professor_id": None, "student_index": None}
        return {
            "role": role,
            "professor_id": getattr(user, "professor_id", None),
            "student_index": getattr(user, "student_index", None),
        }
    finally:
        db.close()


def _normalize_email(value: Any) -> Optional[str]:
    """Return a non-empty trimmed string or None. Used for student/professor email."""
    if value is None:
        return None
    s = (value or "").strip()
    return s if s and "@" in s else None


def get_booking_for_email(booking_id: int, student_index: int) -> Optional[Dict[str, Any]]:
    """
    Get booking with professor and student details for email. Returns None if booking
    not found or does not belong to this student. Student email: primary from
    students.email, fallback student{index}@gmail.com only when primary is missing.
    """
    session = SessionLocal()
    try:
        booking = (
            session.query(ConsultationBooking)
            .filter(ConsultationBooking.id == booking_id)
            .filter(ConsultationBooking.student_index == student_index)
            .first()
        )
        if not booking:
            return None
        prof = session.query(Professor).filter(
            Professor.id == booking.professor_id).first()
        student = session.query(Student).filter(
            Student.index == booking.student_index).first()
        if not prof or not student:
            return None
        student_email_raw = getattr(student, "email", None)
        student_email_valid = _normalize_email(student_email_raw)
        student_email = student_email_valid if student_email_valid else f"student{student.index}@gmail.com"
        prof_email = _normalize_email(prof.email)
        if not prof_email:
            return None
        return {
            "booking_id": booking.id,
            "date": booking.date.isoformat(),
            "start_time": booking.start_time.strftime("%H:%M"),
            "end_time": booking.end_time.strftime("%H:%M"),
            "professor_name": f"{prof.first_name} {prof.last_name}",
            "professor_email": prof_email,
            "student_name": f"{student.first_name} {student.last_name}",
            "student_email": student_email,
            "_student_email_from_db": student_email_valid is not None,
        }
    finally:
        session.close()


def consultation_email_already_sent(booking_id: int) -> bool:
    """True if we already logged a successful send for this booking."""
    session = SessionLocal()
    try:
        return (
            session.query(ConsultationEmailLog)
            .filter(ConsultationEmailLog.booking_id == booking_id)
            .filter(ConsultationEmailLog.status == "sent")
            .first()
            is not None
        )
    finally:
        session.close()


def compose_consultation_email(
    booking_id: int,
    student_index: int,
    consultation_reason: str,
) -> tuple[str, str]:
    """
    Compose subject and body for the professor consultation email. Raises ValueError
    if booking not found or not owned by student.
    """
    data = get_booking_for_email(booking_id, student_index)
    if not data:
        raise ValueError("Booking not found or does not belong to you.")
    reason = (consultation_reason or "").strip() or "General consultation"
    subject = f"Consultation request – {data['date']} {data['start_time']} – {data['student_name']}"
    body = (
        f"Dear {data['professor_name']},\n\n"
        f"I have booked a consultation with you on {data['date']} at {data['start_time']}–{data['end_time']}.\n\n"
        f"Reason for the consultation:\n{reason}\n\n"
        f"Best regards,\n{data['student_name']}\n{data['student_email']}"
    )
    return subject, body


def log_consultation_email(
    booking_id: int,
    student_index: int,
    professor_id: int,
    provider: str,
    provider_message_id: Optional[str],
    subject: str,
    body: str,
    status: str,
    sent_at: Optional[datetime] = None,
    error_message: Optional[str] = None,
) -> None:
    session = SessionLocal()
    try:
        log = ConsultationEmailLog(
            booking_id=booking_id,
            student_index=student_index,
            professor_id=professor_id,
            provider=provider,
            provider_message_id=provider_message_id,
            subject=subject,
            body=body,
            status=status,
            sent_at=sent_at or datetime.now(timezone.utc),
            error_message=error_message,
        )
        session.add(log)
        session.commit()
    finally:
        session.close()


def send_consultation_email_for_booking(
    booking_id: int,
    student_index: int,
    consultation_reason: str,
) -> Dict[str, Any]:
    """
    Compose, send via Resend, and log. Returns {"sent": True, "message_id": "..."} or
    {"sent": False, "error": "..."}. Prevents duplicate sends for same booking.
    """
    if consultation_email_already_sent(booking_id):
        return {"sent": False, "error": "An email for this booking was already sent."}
    data = get_booking_for_email(booking_id, student_index)
    if not data:
        return {"sent": False, "error": "Booking not found or does not belong to you."}
    if not data.get("_student_email_from_db"):
        return {
            "sent": False,
            "error": (
                f"Student (table students, column email) is missing for the student linked to this booking "
                f"(students.index={student_index}). Re-run the consultation seed to backfill placeholder emails: "
                "py -m app.seed.consultations"
            ),
        }
    if not data.get("professor_email"):
        return {
            "sent": False,
            "error": (
                f"Professor (table professors, column email) is missing for professor_id linked to this booking. "
                "Re-run the consultation seed."
            ),
        }
    subject, body = compose_consultation_email(
        booking_id, student_index, consultation_reason)
    professor_id = None
    session = SessionLocal()
    try:
        b = session.query(ConsultationBooking).filter(
            ConsultationBooking.id == booking_id).first()
        professor_id = b.professor_id if b else None
    finally:
        session.close()
    if not professor_id:
        return {"sent": False, "error": "Booking not found."}
    try:
        from app.mail import send_consultation_email as mail_send
        result = mail_send(
            to_email=data["professor_email"],
            subject=subject,
            body_plain=body,
            reply_to=data["student_email"],
        )
        msg_id = result.get("id")
        log_consultation_email(
            booking_id=booking_id,
            student_index=student_index,
            professor_id=professor_id,
            provider="resend",
            provider_message_id=msg_id,
            subject=subject,
            body=body,
            status="sent",
            sent_at=None,
            error_message=None,
        )
        return {"sent": True, "message_id": msg_id}
    except Exception as e:
        log_consultation_email(
            booking_id=booking_id,
            student_index=student_index,
            professor_id=professor_id,
            provider="resend",
            provider_message_id=None,
            subject=subject,
            body=body,
            status="failed",
            sent_at=None,
            error_message=str(e)[:1000],
        )
        return {"sent": False, "error": str(e)}
