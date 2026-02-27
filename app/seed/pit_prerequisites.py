from __future__ import annotations

"""
Seed helpers for PIT program prerequisites and requirements.

This module populates:
- subject_prerequisites
- subject_requirements

Examples covered:
- single prerequisite
- OR prerequisite group
- ECTS minimum
- subject with no prerequisites
"""

from app.models import SubjectPrerequisite, SubjectRequirement


def _ensure_prereq(
    session,
    subject_code: str,
    prereq_subject_code: str,
    any_of_group: str | None = None,
    note: str | None = None,
) -> None:
    row = (
        session.query(SubjectPrerequisite)
        .filter(
            SubjectPrerequisite.subject_code == subject_code,
            SubjectPrerequisite.prereq_subject_code == prereq_subject_code,
            SubjectPrerequisite.any_of_group == any_of_group,
        )
        .first()
    )
    if row:
        row.note = note
        return

    session.add(
        SubjectPrerequisite(
            subject_code=subject_code,
            prereq_subject_code=prereq_subject_code,
            any_of_group=any_of_group,
            note=note,
        )
    )


def _ensure_requirement(
    session,
    subject_code: str,
    min_ects: int | None = None,
    min_passed_subjects: int | None = None,
) -> None:
    row = (
        session.query(SubjectRequirement)
        .filter(SubjectRequirement.subject_code == subject_code)
        .first()
    )
    if not row:
        row = SubjectRequirement(subject_code=subject_code)
        session.add(row)

    row.min_ects = min_ects
    row.min_passed_subjects = min_passed_subjects


def seed_pit_prerequisites(session) -> None:
    """
    Seed example PIT prerequisites/requirements.
    """
    # 1) Single prerequisite:
    #    Object-Oriented Programming requires Structural Programming
    _ensure_prereq(
        session,
        subject_code="F23L1S016",  # OOP
        prereq_subject_code="F23L1W020",  # Structural Programming
        note="OOP requires Structural Programming",
    )

    # 2) OR prerequisite group:
    #    Operating Systems requires (Computer Architecture and Organization OR
    #    some alternative architecture course).
    _ensure_prereq(
        session,
        subject_code="F23L2S017",  # Operating Systems
        prereq_subject_code="F23L1S003",  # Архитектура и организација на компјутери
        any_of_group="OS_ARCH_OR",
        note="OS requires at least one architecture course",
    )
    _ensure_prereq(
        session,
        subject_code="F23L2S017",
        prereq_subject_code="F23L1S045",  # Компјутерски архитектури (alternative architecture course)
        any_of_group="OS_ARCH_OR",
        note="OS requires at least one architecture course",
    )

    # 3) ECTS minimum:
    #    Team project requires min 150 ECTS
    _ensure_requirement(
        session,
        subject_code="F23L3W021",  # Тимски проект
        min_ects=150,
    )

    # 4) Subject with no prerequisites:
    #    Web Programming – explicitly has no prereqs / requirements
    _ensure_requirement(
        session,
        subject_code="F23L3W024",  # Веб програмирање
        min_ects=None,
    )

    # 5) Example for testing max 6 enrollments:
    #    No DB rule needed – this is enforced in code by counting
    #    enrollments per (student_index, semester). Create multiple
    #    enrollments for the same student/semester in tests to hit
    #    the “already enrolled in 6 subjects” branch.

