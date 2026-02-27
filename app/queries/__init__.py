"""
Query functions package.
Re-exports all query functions for backward compatibility.
"""
from app.queries.students import (
    get_student,
    get_student_by_name,
    search_students,
    create_student,
    update_student,
    get_student_average_grade
)
from app.queries.subjects import (
    get_subject_by_code,
    get_subject_by_name,
    search_subjects,
    create_subject,
    get_subject_enrolled_students,
    get_subject_stats
)
from app.queries.exams import (
    best_exam_result,
    passed_subjects,
    earned_ects,
    list_exams_by_subject_and_date,
    find_or_create_exam_session,
    create_exam_record,
    update_exam_record,
    update_exam_record_by_student_subject
)
from app.queries.enrollments import (
    get_current_enrollments,
    list_enrollments,
    create_enrollment,
    update_enrollment,
    get_students_in_subject_with_status
)
from app.queries.programs import list_programs, get_subjects_by_program

__all__ = [
    "get_student",
    "get_student_by_name",
    "search_students",
    "create_student",
    "update_student",
    "get_student_average_grade",
    "get_subject_by_code",
    "get_subject_by_name",
    "search_subjects",
    "create_subject",
    "get_subject_enrolled_students",
    "get_subject_stats",
    "best_exam_result",
    "passed_subjects",
    "earned_ects",
    "list_exams_by_subject_and_date",
    "find_or_create_exam_session",
    "create_exam_record",
    "update_exam_record",
    "update_exam_record_by_student_subject",
    "get_current_enrollments",
    "list_enrollments",
    "create_enrollment",
    "update_enrollment",
    "get_students_in_subject_with_status",
    "list_programs",
    "get_subjects_by_program",
]
