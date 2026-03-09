"""
Seed consultation system: professors, users (professor/student/admin), availabilities, example bookings.
Run after DB and students exist. Writes CONSULTATION_CREDENTIALS.md with test credentials.
"""
from __future__ import annotations

from datetime import date, time, timedelta
from pathlib import Path

from app.db import SessionLocal
from app.models import (
    ConsultationAvailability,
    ConsultationBlock,
    ConsultationBooking,
    Professor,
    User,
)
from app.queries.students import search_students
from app.user_auth import hash_password_for_store


def _ensure_user_columns(session) -> None:
    """Add professor_id and student_index to users table if missing."""
    from sqlalchemy import text
    for col in ("professor_id", "student_index"):
        try:
            session.execute(
                text(f"ALTER TABLE users ADD COLUMN {col} INTEGER"))
            session.commit()
        except Exception:
            session.rollback()


SEED_PASSWORD = "test123"

PROFESSORS_DATA = [
    ("Ана", "Јовановска", "ana.jovanovska@finki.ukim.mk"),
    ("Борче", "Ивановски", "borche.ivanovski@finki.ukim.mk"),
    ("Вера", "Стојановска", "vera.stojanovska@finki.ukim.mk"),
]


def seed_consultations(session) -> None:
    from app.models import Base
    from app.db import engine
    Base.metadata.create_all(
        engine,
        tables=[
            Professor.__table__,
            ConsultationAvailability.__table__,
            ConsultationBlock.__table__,
            ConsultationBooking.__table__,
        ],
    )
    _ensure_user_columns(session)
    professors = []
    for first_name, last_name, email in PROFESSORS_DATA:
        p = session.query(Professor).filter(Professor.email == email).first()
        if not p:
            p = Professor(
                first_name=first_name,
                last_name=last_name,
                email=email,
            )
            session.add(p)
            session.flush()
        professors.append(p)

    students = search_students(limit=3)
    if len(students) < 3:
        pass

    for i, p in enumerate(professors):
        username = f"prof_{p.id}"
        u = session.query(User).filter(User.username == username).first()
        if not u:
            u = User(
                username=username,
                password_hash=hash_password_for_store(username, SEED_PASSWORD),
                role="professor",
                professor_id=p.id,
                student_index=None,
            )
            session.add(u)

    for i, s in enumerate(students[:3]):
        username = f"student_{s['index']}"
        u = session.query(User).filter(User.username == username).first()
        if not u:
            u = User(
                username=username,
                password_hash=hash_password_for_store(username, SEED_PASSWORD),
                role="student",
                professor_id=None,
                student_index=s["index"],
            )
            session.add(u)

    admin_username = "admin"
    admin = session.query(User).filter(User.username == admin_username).first()
    if not admin:
        admin = User(
            username=admin_username,
            password_hash=hash_password_for_store(
                admin_username, SEED_PASSWORD),
            role="admin",
            professor_id=None,
            student_index=None,
        )
        session.add(admin)

    session.flush()

    for p in professors:
        session.query(ConsultationAvailability).filter(
            ConsultationAvailability.professor_id == p.id
        ).delete(synchronize_session=False)
    session.flush()
    default_windows = [
        (0, 1, time(10, 0), time(13, 0)),
        (0, 3, time(10, 0), time(13, 0)),
        (1, 0, time(14, 0), time(16, 30)),
        (1, 2, time(14, 0), time(16, 30)),
        (2, 2, time(9, 0), time(11, 30)),
        (2, 4, time(9, 0), time(11, 30)),
    ]
    for prof_idx, day_of_week, start_t, end_t in default_windows:
        if prof_idx >= len(professors):
            continue
        p = professors[prof_idx]
        existing = (
            session.query(ConsultationAvailability)
            .filter(ConsultationAvailability.professor_id == p.id)
            .filter(ConsultationAvailability.day_of_week == day_of_week)
            .filter(ConsultationAvailability.start_time == start_t)
            .first()
        )
        if not existing:
            session.add(
                ConsultationAvailability(
                    professor_id=p.id,
                    day_of_week=day_of_week,
                    start_time=start_t,
                    end_time=end_t,
                    slot_duration=15,
                )
            )
    session.flush()

    today = date.today()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0 and today.weekday() == 0:
        next_monday = today
    else:
        next_monday = today + \
            timedelta(days=days_until_monday if days_until_monday else 7)
    example_specs = [
        (0, 1, time(10, 30), time(11, 0)),
        (1, 0, time(14, 0), time(14, 30)),
        (2, 2, time(9, 15), time(9, 45)),
    ]
    for i, s in enumerate(students[:3]):
        if i >= len(example_specs):
            break
        prof_idx, day_off, start_t, end_t = example_specs[i]
        if prof_idx >= len(professors):
            continue
        prof = professors[prof_idx]
        d = next_monday + timedelta(days=day_off)
        existing_booking = (
            session.query(ConsultationBooking)
            .filter(ConsultationBooking.professor_id == prof.id)
            .filter(ConsultationBooking.date == d)
            .filter(ConsultationBooking.start_time == start_t)
            .first()
        )
        if not existing_booking:
            session.add(
                ConsultationBooking(
                    professor_id=prof.id,
                    student_index=s["index"],
                    date=d,
                    start_time=start_t,
                    end_time=end_t,
                )
            )


def write_credentials(credentials_path: Path) -> None:
    """Append consultation test credentials to a file."""
    lines = [
        "# Consultation system – test credentials",
        "",
        "Use these to log in (device flow) and test consultations.",
        "",
        "## Password (all accounts)",
        f"`{SEED_PASSWORD}`",
        "",
        "## Professors",
    ]
    session = SessionLocal()
    try:
        professors = session.query(Professor).order_by(Professor.id).all()
        for p in professors:
            u = session.query(User).filter(User.professor_id == p.id).first()
            if u:
                lines.append(
                    f"- **{p.first_name} {p.last_name}**: username `{u.username}`")
        lines.append("")
        lines.append("## Students (first 3 from DB)")
        students = search_students(limit=3)
        for s in students:
            u = session.query(User).filter(
                User.student_index == s["index"]).first()
            if u:
                lines.append(
                    f"- **{s['first_name']} {s['last_name']}** (index {s['index']}): username `{u.username}`")
        lines.append("")
        lines.append("## Admin")
        admin = session.query(User).filter(User.role == "admin").first()
        if admin:
            lines.append(f"- username `{admin.username}`")
    finally:
        session.close()

    credentials_path.write_text("\n".join(lines), encoding="utf-8")


def run_seed_consultations() -> None:
    from app.seed.base import run_seed
    run_seed(seed_consultations)
    credentials_path = Path(__file__).resolve(
    ).parent.parent.parent / "CONSULTATION_CREDENTIALS.md"
    write_credentials(credentials_path)
    print(f"Consultation seed done. Credentials written to {credentials_path}")


if __name__ == "__main__":
    run_seed_consultations()
