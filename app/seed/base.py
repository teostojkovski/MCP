from __future__ import annotations

from typing import Optional, Callable

from app.db import SessionLocal
from app.models import Program, Subject, ProgramSubject, ProgramSemesterRule


def upsert_program(session, name: str) -> Program:
    program = session.query(Program).filter(Program.name == name).first()
    if program:
        return program

    program = Program(name=name)
    session.add(program)
    session.flush()
    return program


def upsert_subject(session, code: str, name: str, ects: Optional[int] = None) -> Subject:
    subj = session.query(Subject).filter(Subject.code == code).first()
    if subj:
        if name and subj.name != name:
            subj.name = name
        if ects is not None:
            subj.ects = ects
        return subj

    subj = Subject(code=code, name=name, ects=ects)
    session.add(subj)
    session.flush()
    return subj


def ensure_program_subject(
    session,
    program_id: int,
    subject_code: str,
    semester: int,
    is_mandatory: bool,
    elective_group_code: Optional[str] = None,
) -> None:
    if is_mandatory and elective_group_code is not None:
        raise ValueError("Mandatory subject cannot have elective_group_code")
    if (not is_mandatory) and not elective_group_code:
        raise ValueError("Elective subject must have elective_group_code")

    row = (
        session.query(ProgramSubject)
        .filter(
            ProgramSubject.program_id == program_id,
            ProgramSubject.subject_code == subject_code,
        )
        .first()
    )

    if row:
        row.semester = semester
        row.is_mandatory = is_mandatory
        row.elective_group_code = elective_group_code
        return

    session.add(
        ProgramSubject(
            program_id=program_id,
            subject_code=subject_code,
            semester=semester,
            is_mandatory=is_mandatory,
            elective_group_code=elective_group_code,
        )
    )


def ensure_semester_rule(
    session,
    program_id: int,
    semester: int,
    elective_group_code: str,
    slots: int,
    choice_key: Optional[str] = None,
    note: Optional[str] = None,
) -> None:
    if slots <= 0:
        raise ValueError("slots must be > 0")

    has_choice_key = hasattr(ProgramSemesterRule, "choice_key")
    has_note = hasattr(ProgramSemesterRule, "note")

    q = session.query(ProgramSemesterRule).filter(
        ProgramSemesterRule.program_id == program_id,
        ProgramSemesterRule.semester == semester,
        ProgramSemesterRule.elective_group_code == elective_group_code,
    )
    if has_choice_key:
        q = q.filter(ProgramSemesterRule.choice_key == choice_key)

    existing = q.first()

    if existing:
        existing.slots = slots
        if has_choice_key:
            existing.choice_key = choice_key
        if has_note:
            existing.note = note
        return

    kwargs = dict(
        program_id=program_id,
        semester=semester,
        elective_group_code=elective_group_code,
        slots=slots,
    )
    if has_choice_key:
        kwargs["choice_key"] = choice_key
    if has_note:
        kwargs["note"] = note

    session.add(ProgramSemesterRule(**kwargs))


def ensure_semester_rule_slot(
    session,
    program_id: int,
    semester: int,
    slot_number: int,
    group_codes: list,
) -> None:
    """Add one ProgramSemesterRule per group with same choice_key (OR slot)."""
    choice_key = f"S{semester}C{slot_number}"
    for g in group_codes:
        ensure_semester_rule(
            session,
            program_id=program_id,
            semester=semester,
            elective_group_code=g,
            slots=1,
            choice_key=choice_key,
        )


def run_seed(seed_fn: Callable) -> None:
    """Run a seed function in a managed session with commit/rollback."""
    session = SessionLocal()
    try:
        seed_fn(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
