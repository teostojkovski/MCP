"""
Subject-related query functions.
"""
from typing import Optional, Dict, Any, List
from app.db import SessionLocal
from app.models import Subject, Enrollment, Exam, ExamSession, Student


def get_subject_by_code(code: str) -> Optional[Dict[str, Any]]:
    """
    Get subject by code.

    Args:
        code: Subject code (e.g., "F23L3W004")

    Returns:
        Dictionary with subject data or None if not found
    """
    session = SessionLocal()
    try:
        subject = session.query(Subject).filter(Subject.code == code).first()
        if not subject:
            return None

        return {
            "code": subject.code,
            "name": subject.name,
            "ects": subject.ects,
        }
    finally:
        session.close()


def get_subject_by_name(name: str) -> Optional[Dict[str, Any]]:
    """
    Get subject by name (partial match supported).

    Args:
        name: Subject name or partial name

    Returns:
        Dictionary with subject data or None if not found
    """
    session = SessionLocal()
    try:
        subject = session.query(Subject).filter(
            Subject.name.ilike(f"%{name}%")
        ).first()
        if not subject:
            return None

        return {
            "code": subject.code,
            "name": subject.name,
            "ects": subject.ects,
        }
    finally:
        session.close()


def search_subjects(
    code: Optional[str] = None,
    name: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Search subjects by code or name (partial match).
    Semester/mandatory/elective are per-program (see ProgramSubject).
    """
    session = SessionLocal()
    try:
        query = session.query(Subject)
        if code:
            query = query.filter(Subject.code.ilike(f"%{code}%"))
        if name:
            query = query.filter(Subject.name.ilike(f"%{name}%"))
        subjects = query.limit(limit).all()
        return [{"code": s.code, "name": s.name, "ects": s.ects} for s in subjects]
    finally:
        session.close()


def create_subject(
    code: str,
    name: str,
    ects: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create a new subject (global catalog). Use program_subjects to assign to a program.
    """
    session = SessionLocal()
    try:
        subject = Subject(code=code, name=name, ects=ects)
        session.add(subject)
        session.commit()
        return {"code": subject.code, "name": subject.name, "ects": subject.ects}
    finally:
        session.close()


def get_subject_enrolled_students(
    subject_code: str,
    semester: Optional[int] = None,
    program: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get students enrolled in a subject.

    Args:
        subject_code: Subject code
        semester: Optional semester filter
        program: Optional program filter

    Returns:
        List of student dictionaries
    """
    session = SessionLocal()
    try:
        query = session.query(Student).join(Enrollment).filter(
            Enrollment.subject_code == subject_code
        )

        if semester is not None:
            query = query.filter(Enrollment.semester == semester)
        if program:
            query = query.filter(Student.program == program)

        students = query.distinct().all()

        return [{
            "index": s.index,
            "first_name": s.first_name,
            "last_name": s.last_name,
            "program": s.program,
            "year_of_study": s.year_of_study
        } for s in students]
    finally:
        session.close()


def get_subject_stats(subject_code: str) -> Dict[str, Any]:
    """
    Get statistics for a subject.

    Returns:
        Dictionary with enrollment, exam attempt, pass rate, and average grade stats
    """
    session = SessionLocal()
    try:
        total_enrolled = session.query(Enrollment).filter(
            Enrollment.subject_code == subject_code,
            Enrollment.listened == True
        ).count()

        attempted = session.query(Exam).join(ExamSession).filter(
            ExamSession.subject_code == subject_code
        ).distinct(Exam.student_index).count()

        passed = session.query(Exam).join(ExamSession).filter(
            ExamSession.subject_code == subject_code,
            Exam.passed == True
        ).distinct(Exam.student_index).count()

        exams = session.query(Exam).join(ExamSession).filter(
            ExamSession.subject_code == subject_code
        ).all()

        avg_grade = None
        if exams:
            student_grades = {}
            for exam in exams:
                if exam.student_index not in student_grades or exam.grade > student_grades[exam.student_index]:
                    student_grades[exam.student_index] = exam.grade
            if student_grades:
                avg_grade = round(
                    sum(student_grades.values()) / len(student_grades), 2)

        pass_rate = (passed / attempted * 100) if attempted > 0 else 0

        return {
            "subject_code": subject_code,
            "total_enrolled": total_enrolled,
            "attempted_exam": attempted,
            "passed": passed,
            "failed": attempted - passed,
            "pass_rate": round(pass_rate, 2),
            "average_grade": avg_grade
        }
    finally:
        session.close()
