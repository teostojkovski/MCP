"""
Student-related query functions.
"""
from typing import Optional, Dict, Any, List
from app.db import SessionLocal
from app.models import Student, Exam, ExamSession, Subject, Enrollment


def get_student(index: int) -> Optional[Dict[str, Any]]:
    """
    Get student by index.

    Args:
        index: Student index number

    Returns:
        Dictionary with student data or None if not found
    """
    session = SessionLocal()
    try:
        student = session.query(Student).filter(Student.index == index).first()
        if not student:
            return None

        return {
            "index": student.index,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "program": student.program,
            "start_year": student.start_year,
            "year_of_study": student.year_of_study,
            "status": student.status
        }
    finally:
        session.close()


def get_student_by_name(name: str) -> Optional[Dict[str, Any]]:
    """
    Get student by name (searches first_name and last_name, partial match supported).

    Args:
        name: Student name or partial name (can be first name, last name, or full name)

    Returns:
        Dictionary with student data or None if not found
    """
    session = SessionLocal()
    try:
        name_lower = name.lower().strip()
        students = session.query(Student).filter(
            (Student.first_name.ilike(f"%{name_lower}%")) |
            (Student.last_name.ilike(f"%{name_lower}%")) |
            ((Student.first_name + " " + Student.last_name).ilike(f"%{name_lower}%"))
        ).all()

        if not students:
            return None

        student = students[0]
        return {
            "index": student.index,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "program": student.program,
            "start_year": student.start_year,
            "year_of_study": student.year_of_study,
            "status": student.status
        }
    finally:
        session.close()


def search_students(
    index: Optional[int] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    program: Optional[str] = None,
    start_year: Optional[int] = None,
    year_of_study: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Search students with optional filters.

    Args:
        index: Student index number
        first_name: First name (partial match)
        last_name: Last name (partial match)
        program: Program name
        start_year: Start year
        year_of_study: Year of study (1-4)
        status: Status (active, graduated, inactive)
        limit: Maximum number of results

    Returns:
        List of student dictionaries
    """
    session = SessionLocal()
    try:
        query = session.query(Student)

        if index is not None:
            query = query.filter(Student.index == index)
        if first_name:
            query = query.filter(Student.first_name.ilike(f"%{first_name}%"))
        if last_name:
            query = query.filter(Student.last_name.ilike(f"%{last_name}%"))
        if program:
            query = query.filter(Student.program == program)
        if start_year is not None:
            query = query.filter(Student.start_year == start_year)
        if year_of_study is not None:
            query = query.filter(Student.year_of_study == year_of_study)
        if status:
            query = query.filter(Student.status == status)

        students = query.limit(limit).all()

        return [{
            "index": s.index,
            "first_name": s.first_name,
            "last_name": s.last_name,
            "program": s.program,
            "start_year": s.start_year,
            "year_of_study": s.year_of_study,
            "status": s.status
        } for s in students]
    finally:
        session.close()


def create_student(
    index: int,
    first_name: str,
    last_name: str,
    program: str,
    start_year: int,
    year_of_study: int,
    status: str = "active"
) -> Dict[str, Any]:
    """
    Create a new student.

    Returns:
        Dictionary with created student data
    """
    session = SessionLocal()
    try:
        student = Student(
            index=index,
            first_name=first_name,
            last_name=last_name,
            program=program,
            start_year=start_year,
            year_of_study=year_of_study,
            status=status
        )
        session.add(student)
        session.commit()
        return {
            "index": student.index,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "program": student.program,
            "start_year": student.start_year,
            "year_of_study": student.year_of_study,
            "status": student.status
        }
    finally:
        session.close()


def update_student(
    index: int,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    program: Optional[str] = None,
    year_of_study: Optional[int] = None,
    status: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Update student information.

    Returns:
        Updated student dictionary or None if not found
    """
    session = SessionLocal()
    try:
        student = session.query(Student).filter(Student.index == index).first()
        if not student:
            return None

        if first_name is not None:
            student.first_name = first_name
        if last_name is not None:
            student.last_name = last_name
        if program is not None:
            student.program = program
        if year_of_study is not None:
            student.year_of_study = year_of_study
        if status is not None:
            student.status = status

        session.commit()
        return {
            "index": student.index,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "program": student.program,
            "start_year": student.start_year,
            "year_of_study": student.year_of_study,
            "status": student.status
        }
    finally:
        session.close()


def get_student_average_grade(student_index: int) -> Optional[float]:
    """
    Calculate average grade for a student across all passed exams.

    Returns:
        Average grade or None if no exams
    """
    session = SessionLocal()
    try:
        exams = session.query(Exam).join(ExamSession).filter(
            Exam.student_index == student_index,
            Exam.passed == True
        ).all()

        if not exams:
            return None

        total_grade = sum(exam.grade for exam in exams)
        return round(total_grade / len(exams), 2)
    finally:
        session.close()


