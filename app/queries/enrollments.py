"""
Enrollment-related query functions.
"""
from typing import Optional, Dict, Any, List, Set
from app.db import SessionLocal
from app.models import (
    Enrollment,
    Student,
    Subject,
    Exam,
    ExamSession,
    Program,
    ProgramSubject,
    ProgramSemesterRule,
    SubjectPrerequisite,
    SubjectRequirement,
)


def get_current_enrollments(student_index: int) -> List[Dict[str, Any]]:
    """
    Get subjects a student is currently enrolled in (listening but not yet passed).

    Args:
        student_index: Student index number

    Returns:
        List of dictionaries with enrollment and subject information
    """
    session = SessionLocal()
    try:
        enrollments = session.query(Enrollment).filter(
            Enrollment.student_index == student_index,
            Enrollment.listened == True
        ).all()

        passed_codes = set()
        passed_exams = session.query(Exam).join(ExamSession).filter(
            Exam.student_index == student_index,
            Exam.passed == True
        ).all()
        passed_codes = {
            exam.exam_session.subject_code for exam in passed_exams}

        results = []
        for enrollment in enrollments:
            if enrollment.subject_code not in passed_codes:
                subject = session.query(Subject).filter(
                    Subject.code == enrollment.subject_code
                ).first()
                if subject:
                    results.append({
                        "code": subject.code,
                        "name": subject.name,
                        "ects": subject.ects or 6,
                        "semester": enrollment.semester,
                        "enrollment_semester": enrollment.semester
                    })

        results.sort(key=lambda x: x["enrollment_semester"])
        return results
    finally:
        session.close()


def _get_passed_subject_codes(session, student_index: int) -> Set[str]:
    passed_exams = session.query(Exam).join(ExamSession).filter(
        Exam.student_index == student_index,
        Exam.passed == True,
    ).all()
    return {exam.exam_session.subject_code for exam in passed_exams}


def get_passed_subject_codes(student_index: int) -> Set[str]:
    """
    Helper: return set of subject codes the student has passed.
    """
    session = SessionLocal()
    try:
        return _get_passed_subject_codes(session, student_index)
    finally:
        session.close()


def _compute_student_ects(session, student_index: int) -> int:
    passed_codes = _get_passed_subject_codes(session, student_index)
    if not passed_codes:
        return 0

    subjects = (
        session.query(Subject)
        .filter(Subject.code.in_(passed_codes))
        .all()
    )

    total_ects = 0
    for subj in subjects:
        ects = subj.ects if subj.ects is not None else 6
        total_ects += ects
    return total_ects


def compute_student_ects(student_index: int) -> int:
    """
    Helper: compute total ECTS from passed subjects.
    """
    session = SessionLocal()
    try:
        return _compute_student_ects(session, student_index)
    finally:
        session.close()


def _count_student_electives_in_pool(
    session,
    student_index: int,
    semester: int,
    elective_group_code: str,
    program_id: int,
) -> int:
    """
    Count how many electives the student is enrolled in for this semester and pool.
    """
    return (
        session.query(Enrollment)
        .join(
            ProgramSubject,
            (ProgramSubject.subject_code == Enrollment.subject_code)
            & (ProgramSubject.program_id == program_id),
        )
        .filter(
            Enrollment.student_index == student_index,
            Enrollment.semester == semester,
            ProgramSubject.is_mandatory == False,
            ProgramSubject.elective_group_code == elective_group_code,
        )
        .count()
    )


def _check_max_semester_load(session, student_index: int, semester: int) -> None:
    count = (
        session.query(Enrollment)
        .filter(
            Enrollment.student_index == student_index,
            Enrollment.semester == semester,
        )
        .count()
    )
    if count >= 6:
        raise ValueError(
            f"Cannot enroll: already enrolled in 6 subjects in semester {semester}"
        )


def check_max_semester_load(student_index: int, semester: int) -> None:
    """
    Helper: enforce max 6 enrollments per student per semester.
    """
    session = SessionLocal()
    try:
        _check_max_semester_load(session, student_index, semester)
    finally:
        session.close()


def count_student_electives(
    student_index: int,
    semester: int,
    elective_group_code: str,
    program_id: int,
) -> int:
    """
    Count how many electives the student is enrolled in for this semester and pool.
    """
    session = SessionLocal()
    try:
        return _count_student_electives_in_pool(
            session, student_index, semester, elective_group_code, program_id
        )
    finally:
        session.close()


def _check_prerequisites(session, student_index: int, subject_code: str) -> None:
    prereqs = (
        session.query(SubjectPrerequisite)
        .filter(SubjectPrerequisite.subject_code == subject_code)
        .all()
    )
    if not prereqs:
        return

    passed_codes = _get_passed_subject_codes(session, student_index)

    missing_codes: List[str] = []
    grouped: dict[str, List[str]] = {}

    for row in prereqs:
        if row.prereq_subject_code is None:
            continue
        if row.any_of_group:
            grouped.setdefault(row.any_of_group, []).append(
                row.prereq_subject_code
            )
        else:
            if row.prereq_subject_code not in passed_codes:
                missing_codes.append(row.prereq_subject_code)

    missing_msgs: List[str] = []

    if missing_codes:
        subjects = (
            session.query(Subject)
            .filter(Subject.code.in_(missing_codes))
            .all()
        )
        name_map = {s.code: s.name for s in subjects}
        parts = []
        for code in missing_codes:
            name = name_map.get(code)
            if name:
                parts.append(f"{code} ({name})")
            else:
                parts.append(code)
        if len(parts) == 1:
            missing_msgs.append(
                f"missing prerequisite {parts[0]}"
            )
        else:
            missing_msgs.append(
                "missing prerequisites: " + ", ".join(parts)
            )

    for group_key, codes in grouped.items():
        codes = [c for c in codes if c is not None]
        if not codes:
            continue
        if any(code in passed_codes for code in codes):
            continue
        subjects = (
            session.query(Subject)
            .filter(Subject.code.in_(codes))
            .all()
        )
        name_map = {s.code: s.name for s in subjects}
        options = []
        for code in codes:
            name = name_map.get(code)
            if name:
                options.append(f"{code} ({name})")
            else:
                options.append(code)
        missing_msgs.append(
            f"prerequisite group '{group_key}' not satisfied; requires one of: "
            + ", ".join(options)
        )

    if missing_msgs:
        raise ValueError(
            "Cannot enroll: " + "; ".join(missing_msgs)
        )


def check_prerequisites(student_index: int, subject_code: str) -> None:
    """
    Helper: check all subject prerequisites for a student.
    """
    session = SessionLocal()
    try:
        _check_prerequisites(session, student_index, subject_code)
    finally:
        session.close()


def _check_subject_requirements(
    session, student_index: int, subject_code: str
) -> None:
    """Check subject_requirements: min_ects and min_passed_subjects."""
    requirement = (
        session.query(SubjectRequirement)
        .filter(SubjectRequirement.subject_code == subject_code)
        .first()
    )
    if not requirement:
        return

    if requirement.min_ects is not None:
        total_ects = _compute_student_ects(session, student_index)
        if total_ects < requirement.min_ects:
            raise ValueError(
                f"Cannot enroll: requires at least {requirement.min_ects} ECTS, "
                f"student has {total_ects}"
            )

    if requirement.min_passed_subjects is not None:
        passed_codes = _get_passed_subject_codes(session, student_index)
        if len(passed_codes) < requirement.min_passed_subjects:
            raise ValueError(
                f"Cannot enroll: requires at least {requirement.min_passed_subjects} passed subjects, "
                f"student has {len(passed_codes)}"
            )


def list_enrollments(
    student_index: Optional[int] = None,
    subject_code: Optional[str] = None,
    semester: Optional[int] = None,
    listened: Optional[bool] = None,
    limit: int = 200
) -> List[Dict[str, Any]]:
    """
    List enrollments with optional filters.

    Args:
        student_index: Filter by student index
        subject_code: Filter by subject code
        semester: Filter by semester
        listened: Filter by listened status
        limit: Maximum number of results

    Returns:
        List of enrollment dictionaries
    """
    session = SessionLocal()
    try:
        query = session.query(Enrollment)

        if student_index is not None:
            query = query.filter(Enrollment.student_index == student_index)
        if subject_code:
            query = query.filter(Enrollment.subject_code == subject_code)
        if semester is not None:
            query = query.filter(Enrollment.semester == semester)
        if listened is not None:
            query = query.filter(Enrollment.listened == listened)

        enrollments = query.limit(limit).all()

        return [{
            "id": e.id,
            "student_index": e.student_index,
            "student_name": f"{e.student.first_name} {e.student.last_name}",
            "subject_code": e.subject_code,
            "subject_name": e.subject.name,
            "semester": e.semester,
            "listened": e.listened
        } for e in enrollments]
    finally:
        session.close()


def create_enrollment(
    student_index: int,
    subject_code: str,
    semester: int,
    listened: bool = True
) -> Dict[str, Any]:
    """
    Create a new enrollment.

    Returns:
        Dictionary with created enrollment data

    Raises:
        ValueError: If student, subject doesn't exist, or enrollment already exists
    """
    from sqlalchemy.exc import IntegrityError
    session = SessionLocal()
    try:
        student = session.query(Student).filter(
            Student.index == student_index
        ).first()
        if not student:
            raise ValueError(
                f"Student with index {student_index} does not exist"
            )

        subject = session.query(Subject).filter(
            Subject.code == subject_code
        ).first()
        if not subject:
            raise ValueError(
                f"Subject with code {subject_code} does not exist"
            )

        program = session.query(Program).filter(
            Program.name == student.program
        ).first()
        if not program:
            raise ValueError(
                f"Student program '{student.program}' is not configured in programs table"
            )

        mapping = (
            session.query(ProgramSubject)
            .filter(
                ProgramSubject.program_id == program.id,
                ProgramSubject.subject_code == subject_code,
            )
            .first()
        )
        if not mapping:
            raise ValueError("Cannot enroll: subject not in student's program")

        max_semester = student.year_of_study * 2
        if mapping.semester > max_semester:
            raise ValueError(
                f"Cannot enroll: subject is in curriculum semester {mapping.semester}; "
                f"student in year {student.year_of_study} may enroll only in semesters 1–{max_semester}"
            )

        if not mapping.is_mandatory and mapping.elective_group_code:
            rules = (
                session.query(ProgramSemesterRule)
                .filter(
                    ProgramSemesterRule.program_id == program.id,
                    ProgramSemesterRule.semester == semester,
                    ProgramSemesterRule.elective_group_code == mapping.elective_group_code,
                )
                .all()
            )
            total_slots = sum(r.slots for r in rules)
            current_count = _count_student_electives_in_pool(
                session,
                student_index,
                semester,
                mapping.elective_group_code,
                program.id,
            )
            if current_count >= total_slots:
                raise ValueError(
                    f"Cannot enroll: elective pool '{mapping.elective_group_code}' "
                    f"allows at most {total_slots} subject(s) in semester {semester}; "
                    f"already enrolled in {current_count}"
                )

        existing = session.query(Enrollment).filter(
            Enrollment.student_index == student_index,
            Enrollment.subject_code == subject_code,
            Enrollment.semester == semester,
        ).first()
        if existing:
            raise ValueError(
                f"Enrollment already exists: Student {student_index} is already enrolled in "
                f"{subject_code} for semester {semester}"
            )

        _check_max_semester_load(session, student_index, semester)

        _check_prerequisites(session, student_index, subject_code)

        _check_subject_requirements(session, student_index, subject_code)

        enrollment = Enrollment(
            student_index=student_index,
            subject_code=subject_code,
            semester=semester,
            listened=listened,
        )
        session.add(enrollment)
        session.commit()
        session.refresh(enrollment)
        return {
            "id": enrollment.id,
            "student_index": enrollment.student_index,
            "subject_code": enrollment.subject_code,
            "semester": enrollment.semester,
            "listened": enrollment.listened,
        }
    except IntegrityError as e:
        session.rollback()
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        if "uq_enrollment" in error_msg or "unique constraint" in error_msg.lower():
            raise ValueError(
                f"Enrollment already exists: Student {student_index} is already enrolled in "
                f"{subject_code} for semester {semester}"
            )
        raise ValueError(f"Database error: {error_msg}")
    except ValueError:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise ValueError(f"Error creating enrollment: {str(e)}")
    finally:
        session.close()


def update_enrollment(
    enrollment_id: Optional[int] = None,
    student_index: Optional[int] = None,
    subject_code: Optional[str] = None,
    semester: Optional[int] = None,
    listened: Optional[bool] = None
) -> Optional[Dict[str, Any]]:
    """
    Update an enrollment.

    Can identify by enrollment_id or by (student_index, subject_code, semester).

    Returns:
        Updated enrollment dictionary or None if not found
    """
    session = SessionLocal()
    try:
        if enrollment_id:
            enrollment = session.query(Enrollment).filter(
                Enrollment.id == enrollment_id).first()
        elif student_index and subject_code and semester is not None:
            enrollment = session.query(Enrollment).filter(
                Enrollment.student_index == student_index,
                Enrollment.subject_code == subject_code,
                Enrollment.semester == semester
            ).first()
        else:
            return None

        if not enrollment:
            return None

        if listened is not None:
            enrollment.listened = listened

        session.commit()
        return {
            "id": enrollment.id,
            "student_index": enrollment.student_index,
            "subject_code": enrollment.subject_code,
            "semester": enrollment.semester,
            "listened": enrollment.listened
        }
    finally:
        session.close()


def get_students_in_subject_with_status(
    subject_code: str,
    semester: Optional[int] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get students enrolled in a subject, grouped by status (passed/not passed/not attempted).

    Args:
        subject_code: Subject code
        semester: Optional semester filter

    Returns:
        Dictionary with keys: 'passed', 'not_passed', 'not_attempted'
    """
    session = SessionLocal()
    try:
        query = session.query(Enrollment).filter(
            Enrollment.subject_code == subject_code,
            Enrollment.listened == True
        )
        if semester is not None:
            query = query.filter(Enrollment.semester == semester)

        enrollments = query.all()
        enrolled_student_indices = {e.student_index for e in enrollments}

        passed_exams = session.query(Exam).join(ExamSession).filter(
            ExamSession.subject_code == subject_code,
            Exam.passed == True
        ).all()
        passed_student_indices = {exam.student_index for exam in passed_exams}

        failed_exams = session.query(Exam).join(ExamSession).filter(
            ExamSession.subject_code == subject_code,
            Exam.passed == False
        ).all()
        failed_student_indices = {exam.student_index for exam in failed_exams}

        passed = []
        not_passed = []
        not_attempted = []

        for student_index in enrolled_student_indices:
            student = session.query(Student).filter(
                Student.index == student_index).first()
            if not student:
                continue

            student_info = {
                "index": student.index,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "program": student.program
            }

            if student_index in passed_student_indices:
                passed.append(student_info)
            elif student_index in failed_student_indices:
                not_passed.append(student_info)
            else:
                not_attempted.append(student_info)

        return {
            "passed": passed,
            "not_passed": not_passed,
            "not_attempted": not_attempted
        }
    finally:
        session.close()
