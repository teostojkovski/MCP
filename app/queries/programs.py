"""
Program-related query functions.
Programs: PIT, SIIS, IMB (by name in DB).
"""
from typing import List, Dict, Any, Optional
from app.db import SessionLocal
from app.models import Program, ProgramSubject, Subject


def list_programs() -> List[Dict[str, Any]]:
    """List all programs (id, name). Students have program = Program.name."""
    session = SessionLocal()
    try:
        programs = session.query(Program).order_by(Program.name).all()
        return [{"id": p.id, "name": p.name} for p in programs]
    finally:
        session.close()


def get_subjects_by_program(program_name: str) -> List[Dict[str, Any]]:
    """
    List subjects in a program with semester and mandatory/elective.
    program_name must match Student.program and Program.name.
    """
    session = SessionLocal()
    try:
        program = session.query(Program).filter(Program.name == program_name).first()
        if not program:
            return []
        q = (
            session.query(ProgramSubject, Subject)
            .join(Subject, Subject.code == ProgramSubject.subject_code)
            .filter(ProgramSubject.program_id == program.id)
            .order_by(ProgramSubject.semester, ProgramSubject.subject_code)
        )
        result = []
        for ps, subj in q:
            result.append({
                "code": subj.code,
                "name": subj.name,
                "ects": subj.ects or 6,
                "semester": ps.semester,
                "is_mandatory": ps.is_mandatory,
                "elective_group_code": ps.elective_group_code,
            })
        return result
    finally:
        session.close()
