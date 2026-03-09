"""
Program-related query functions.
Programs: PIT, SIIS, IMB (by name in DB).
Curriculum: mandatory subjects and elective slots per semester.
"""
from typing import List, Dict, Any, Optional
from app.db import SessionLocal
from app.models import Program, ProgramSubject, ProgramSemesterRule, Subject


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
        program = session.query(Program).filter(
            Program.name == program_name).first()
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


def get_semester_mandatory_subjects(
    program_id: int, semester: int
) -> List[Dict[str, Any]]:
    """
    Return list of mandatory subjects for a program in a given semester.
    Each item: {code, name, ects, semester}.
    """
    session = SessionLocal()
    try:
        rows = (
            session.query(ProgramSubject, Subject)
            .join(Subject, Subject.code == ProgramSubject.subject_code)
            .filter(
                ProgramSubject.program_id == program_id,
                ProgramSubject.semester == semester,
                ProgramSubject.is_mandatory == True,
            )
            .order_by(ProgramSubject.subject_code)
        )
        return [
            {
                "code": subj.code,
                "name": subj.name,
                "ects": subj.ects or 6,
                "semester": ps.semester,
            }
            for ps, subj in rows
        ]
    finally:
        session.close()


def get_semester_elective_pools(
    program_id: int, semester: int
) -> List[Dict[str, Any]]:
    """
    Return elective pools for a program in a given semester.
    Each pool: {elective_group_code, slots, subjects: [{code, name, ects}, ...]}.
    slots = sum of rule.slots for that pool (handles choice_key OR-rules).
    """
    session = SessionLocal()
    try:
        rules = (
            session.query(ProgramSemesterRule)
            .filter(
                ProgramSemesterRule.program_id == program_id,
                ProgramSemesterRule.semester == semester,
            )
            .all()
        )
        if not rules:
            return []

        pool_slots: Dict[str, int] = {}
        for r in rules:
            pool_slots[r.elective_group_code] = (
                pool_slots.get(r.elective_group_code, 0) + r.slots
            )

        result = []
        for group_code, slots in sorted(pool_slots.items()):
            subjects_in_pool = (
                session.query(ProgramSubject, Subject)
                .join(Subject, Subject.code == ProgramSubject.subject_code)
                .filter(
                    ProgramSubject.program_id == program_id,
                    ProgramSubject.is_mandatory == False,
                    ProgramSubject.elective_group_code == group_code,
                )
                .order_by(ProgramSubject.subject_code)
            )
            result.append({
                "elective_group_code": group_code,
                "slots": slots,
                "subjects": [
                    {
                        "code": subj.code,
                        "name": subj.name,
                        "ects": subj.ects or 6,
                    }
                    for ps, subj in subjects_in_pool
                ],
            })
        return result
    finally:
        session.close()


def get_subject_pool(
    program_id: int, subject_code: str
) -> Optional[str]:
    """
    Return elective_group_code if subject is elective in this program, else None (mandatory).
    Returns None if subject is not in program.
    """
    session = SessionLocal()
    try:
        row = (
            session.query(ProgramSubject)
            .filter(
                ProgramSubject.program_id == program_id,
                ProgramSubject.subject_code == subject_code,
            )
            .first()
        )
        if not row:
            return None
        return row.elective_group_code
    finally:
        session.close()


def get_curriculum_by_program(program_name: str) -> Dict[str, Any]:
    """
    Curriculum structured by semester: mandatory subjects and elective slots per semester.
    Returns: {program_name, semesters: [{semester, mandatory: [...], elective_pools: [...]}]}.
    """
    session = SessionLocal()
    try:
        program = session.query(Program).filter(
            Program.name == program_name).first()
        if not program:
            return {"program_name": program_name, "semesters": []}

        semesters_out = []
        for sem in range(1, 9):
            mandatory = get_semester_mandatory_subjects(program.id, sem)
            elective_pools = get_semester_elective_pools(program.id, sem)
            if mandatory or elective_pools:
                semesters_out.append({
                    "semester": sem,
                    "mandatory": mandatory,
                    "elective_pools": elective_pools,
                })
        return {
            "program_name": program_name,
            "semesters": semesters_out,
        }
    finally:
        session.close()
