"""
Exam-related query functions.
"""
from typing import Optional, Dict, Any, List
from datetime import date
from app.db import SessionLocal
from app.models import Exam, ExamSession, Student, Subject


def best_exam_result(student_index: int, subject_code: str) -> Optional[Dict[str, Any]]:
    """
    Get the best exam result for a student in a subject.

    Args:
        student_index: Student index number
        subject_code: Subject code

    Returns:
        Dictionary with exam data (grade, passed, exam_date, session_type, year) or None
    """
    session = SessionLocal()
    try:
        exams = session.query(Exam).join(ExamSession).filter(
            Exam.student_index == student_index,
            ExamSession.subject_code == subject_code
        ).order_by(Exam.grade.desc(), ExamSession.year.desc(), ExamSession.exam_date.desc()).all()

        if not exams:
            return None

        best = exams[0]

        return {
            "student_index": best.student_index,
            "subject_code": best.exam_session.subject_code,
            "grade": best.grade,
            "passed": best.passed,
            "exam_date": best.exam_session.exam_date.isoformat() if best.exam_session.exam_date else None,
            "session_type": best.exam_session.session_type,
            "year": best.exam_session.year
        }
    finally:
        session.close()


def passed_subjects(student_index: int) -> List[Dict[str, Any]]:
    """
    Get all subjects that a student has passed.

    Args:
        student_index: Student index number

    Returns:
        List of dictionaries with subject and exam information
    """
    from app.queries.subjects import get_subject_by_code
    session = SessionLocal()
    try:
        passed_exams = session.query(Exam).join(ExamSession).filter(
            Exam.student_index == student_index,
            Exam.passed == True
        ).all()

        passed_subject_codes = list(
            set(exam.exam_session.subject_code for exam in passed_exams))

        results = []
        for code in passed_subject_codes:
            subject = session.query(Subject).filter(
                Subject.code == code).first()
            if subject:
                best_result = best_exam_result(student_index, code)
                results.append({
                    "code": subject.code,
                    "name": subject.name,
                    "ects": subject.ects,
                    "semester": subject.semester,
                    "grade": best_result["grade"] if best_result else None,
                    "exam_date": best_result["exam_date"] if best_result else None,
                    "session_type": best_result.get("session_type") if best_result else None,
                    "year": best_result.get("year") if best_result else None
                })

        results.sort(key=lambda x: x["semester"])
        return results
    finally:
        session.close()


def earned_ects(student_index: int) -> int:
    """
    Calculate total ECTS credits earned by a student.
    ECTS = number of passed subjects × 6 (since all subjects are 6 ECTS).

    Args:
        student_index: Student index number

    Returns:
        Total ECTS credits earned
    """
    passed = passed_subjects(student_index)
    return len(passed) * 6


def list_exams_by_subject_and_date(
    subject_code: str,
    exam_date: Optional[date] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> List[Dict[str, Any]]:
    """
    List exams for a subject filtered by date.

    Args:
        subject_code: Subject code
        exam_date: Exact exam date
        start_date: Start of date range
        end_date: End of date range

    Returns:
        List of exam dictionaries with student and session info
    """
    session = SessionLocal()
    try:
        query = session.query(Exam).join(ExamSession).filter(
            ExamSession.subject_code == subject_code
        )

        if exam_date:
            query = query.filter(ExamSession.exam_date == exam_date)
        elif start_date or end_date:
            if start_date:
                query = query.filter(ExamSession.exam_date >= start_date)
            if end_date:
                query = query.filter(ExamSession.exam_date <= end_date)

        exams = query.order_by(
            ExamSession.exam_date.desc(), Exam.grade.desc()).all()

        return [{
            "id": exam.id,
            "student_index": exam.student.index,
            "student_name": f"{exam.student.first_name} {exam.student.last_name}",
            "grade": exam.grade,
            "passed": exam.passed,
            "exam_date": exam.exam_session.exam_date.isoformat(),
            "session_type": exam.exam_session.session_type,
            "year": exam.exam_session.year
        } for exam in exams]
    finally:
        session.close()


def find_or_create_exam_session(
    subject_code: str,
    session_type: str,
    year: int,
    exam_date: date
) -> int:
    """
    Find or create an exam session.

    Returns:
        Exam session ID
    """
    session = SessionLocal()
    try:
        exam_session = session.query(ExamSession).filter(
            ExamSession.subject_code == subject_code,
            ExamSession.session_type == session_type,
            ExamSession.year == year
        ).first()

        if not exam_session:
            exam_session = ExamSession(
                subject_code=subject_code,
                session_type=session_type,
                year=year,
                exam_date=exam_date
            )
            session.add(exam_session)
            session.commit()
            session.refresh(exam_session)

        return exam_session.id
    finally:
        session.close()


def create_exam_record(
    exam_session_id: int,
    student_index: int,
    grade: int,
    passed: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Create an exam record for a student in an exam session.

    Args:
        exam_session_id: Exam session ID
        student_index: Student index
        grade: Grade (5-10)
        passed: Whether passed (auto-calculated if None, grade >= 6)

    Returns:
        Dictionary with created exam data
    """
    session = SessionLocal()
    try:
        if passed is None:
            passed = grade >= 6

        exam = Exam(
            exam_session_id=exam_session_id,
            student_index=student_index,
            grade=grade,
            passed=passed
        )
        session.add(exam)
        session.commit()
        return {
            "id": exam.id,
            "exam_session_id": exam.exam_session_id,
            "student_index": exam.student_index,
            "grade": exam.grade,
            "passed": exam.passed
        }
    finally:
        session.close()


def update_exam_record_by_student_subject(
    student_index: int,
    subject_code: str,
    grade: Optional[int] = None,
    passed: Optional[bool] = None
) -> Optional[Dict[str, Any]]:
    """
    Update exam record by student and subject (updates best result).

    Args:
        student_index: Student index
        subject_code: Subject code
        grade: New grade
        passed: New passed status

    Returns:
        Updated exam dictionary or None if not found
    """
    session = SessionLocal()
    try:
        exam = session.query(Exam).join(ExamSession).filter(
            Exam.student_index == student_index,
            ExamSession.subject_code == subject_code
        ).order_by(Exam.grade.desc()).first()

        if not exam:
            return None

        if grade is not None:
            exam.grade = grade
            if passed is None:
                exam.passed = grade >= 6
        if passed is not None:
            exam.passed = passed

        session.commit()
        return {
            "id": exam.id,
            "exam_session_id": exam.exam_session_id,
            "student_index": exam.student_index,
            "grade": exam.grade,
            "passed": exam.passed
        }
    finally:
        session.close()


def update_exam_record(
    exam_id: int,
    grade: Optional[int] = None,
    passed: Optional[bool] = None
) -> Optional[Dict[str, Any]]:
    """
    Update an exam record.

    Args:
        exam_id: Exam ID
        grade: New grade
        passed: New passed status (auto-calculated if grade provided and passed is None)

    Returns:
        Updated exam dictionary or None if not found
    """
    session = SessionLocal()
    try:
        exam = session.query(Exam).filter(Exam.id == exam_id).first()
        if not exam:
            return None

        if grade is not None:
            exam.grade = grade
            if passed is None:
                exam.passed = grade >= 6
        if passed is not None:
            exam.passed = passed

        session.commit()
        return {
            "id": exam.id,
            "exam_session_id": exam.exam_session_id,
            "student_index": exam.student_index,
            "grade": exam.grade,
            "passed": exam.passed
        }
    finally:
        session.close()
