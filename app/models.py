from __future__ import annotations

from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Student(Base):
    __tablename__ = "students"

    index: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(60), nullable=False)
    last_name: Mapped[str] = mapped_column(String(60), nullable=False)

    program: Mapped[str] = mapped_column(String(120), nullable=False)

    start_year: Mapped[int] = mapped_column(Integer, nullable=False)
    year_of_study: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="active")

    enrollments = relationship(
        "Enrollment", back_populates="student", cascade="all, delete-orphan"
    )
    exams = relationship("Exam", back_populates="student",
                         cascade="all, delete-orphan")
    disciplinary_actions = relationship(
        "DisciplinaryAction", back_populates="student", cascade="all, delete-orphan"
    )


class Subject(Base):
    """
    Global subject catalog.
    A subject exists once (code is PK) and can appear in many programs with different roles.
    """
    __tablename__ = "subjects"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    ects: Mapped[int | None] = mapped_column(Integer, nullable=True)

    enrollments = relationship(
        "Enrollment", back_populates="subject", cascade="all, delete-orphan"
    )
    exam_sessions = relationship(
        "ExamSession", back_populates="subject", cascade="all, delete-orphan"
    )

    program_mappings = relationship(
        "ProgramSubject", back_populates="subject", cascade="all, delete-orphan"
    )

    prerequisites = relationship(
        "SubjectPrerequisite",
        foreign_keys="SubjectPrerequisite.subject_code",
        back_populates="subject",
        cascade="all, delete-orphan",
    )
    as_prerequisite_for = relationship(
        "SubjectPrerequisite",
        foreign_keys="SubjectPrerequisite.prereq_subject_code",
        back_populates="prereq_subject",
        cascade="all, delete-orphan",
    )
    requirement = relationship(
        "SubjectRequirement",
        back_populates="subject",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)

    curriculum = relationship(
        "ProgramSubject", back_populates="program", cascade="all, delete-orphan"
    )
    semester_rules = relationship(
        "ProgramSemesterRule", back_populates="program", cascade="all, delete-orphan"
    )


class ProgramSubject(Base):
    """
    Curriculum mapping:
    - Same Subject can be mandatory in one program and elective in another.
    """
    __tablename__ = "program_subjects"
    __table_args__ = (
        UniqueConstraint("program_id", "subject_code",
                         name="uq_program_subject"),
        CheckConstraint("semester >= 0 AND semester <= 8",
                        name="ck_program_subject_semester"),
        CheckConstraint(
            "(is_mandatory = TRUE AND elective_group_code IS NULL) OR "
            "(is_mandatory = FALSE AND elective_group_code IS NOT NULL)",
            name="ck_program_subject_mandatory_group",
        ),
        Index("ix_program_subject_program_semester", "program_id", "semester"),
        Index("ix_program_subject_subject_code", "subject_code"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)

    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id"), nullable=False)
    subject_code: Mapped[str] = mapped_column(
        ForeignKey("subjects.code"), nullable=False)

    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False)
    elective_group_code: Mapped[str | None] = mapped_column(
        String(20), nullable=True)

    program = relationship("Program", back_populates="curriculum")
    subject = relationship("Subject", back_populates="program_mappings")


class ProgramSemesterRule(Base):
    """
    Elective slots per semester per program.

    Use choice_key to represent OR rules.
    Example:
      Semester 5: choose 1 from (F23L2W OR F23L3W)
      -> rows:
         (sem=5, group=F23L2W, slots=1, choice_key="S5C1")
         (sem=5, group=F23L3W, slots=1, choice_key="S5C1")
    """
    __tablename__ = "program_semester_rules"
    __table_args__ = (
        UniqueConstraint(
            "program_id",
            "semester",
            "elective_group_code",
            "choice_key",
            name="uq_program_semester_rule",
        ),
        CheckConstraint("semester >= 1 AND semester <= 8",
                        name="ck_program_semester_rule_semester"),
        CheckConstraint("slots > 0", name="ck_program_semester_rule_slots"),
        Index("ix_program_semester_rule_program_semester",
              "program_id", "semester"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id"), nullable=False)

    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    elective_group_code: Mapped[str] = mapped_column(
        String(20), nullable=False)
    slots: Mapped[int] = mapped_column(Integer, nullable=False)

    choice_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    program = relationship("Program", back_populates="semester_rules")


class SubjectPrerequisite(Base):
    """
    Per-subject prerequisite rules.

    - subject_code: subject the student wants to enroll INTO
    - prereq_subject_code: subject that must be PASSED first
    - any_of_group: string key to represent OR prerequisites
      Example: “A or B” -> two rows with same any_of_group
    """

    __tablename__ = "subject_prerequisites"
    __table_args__ = (
        Index("ix_subject_prereq_subject", "subject_code"),
        Index("ix_subject_prereq_prereq_subject", "prereq_subject_code"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    subject_code: Mapped[str] = mapped_column(
        ForeignKey("subjects.code"), nullable=False
    )
    prereq_subject_code: Mapped[str] = mapped_column(
        ForeignKey("subjects.code"), nullable=True
    )
    any_of_group: Mapped[str | None] = mapped_column(String(50), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rule_text: Mapped[str | None] = mapped_column(String(500), nullable=True)

    subject = relationship(
        "Subject",
        foreign_keys=[subject_code],
        back_populates="prerequisites",
    )
    prereq_subject = relationship(
        "Subject",
        foreign_keys=[prereq_subject_code],
        back_populates="as_prerequisite_for",
    )


class SubjectRequirement(Base):
    """
    Per-subject high-level requirements such as minimum ECTS or
    minimum number of passed subjects.
    """

    __tablename__ = "subject_requirements"

    subject_code: Mapped[str] = mapped_column(
        ForeignKey("subjects.code"), primary_key=True
    )
    min_ects: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_passed_subjects: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    subject = relationship("Subject", back_populates="requirement")


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("student_index", "subject_code",
                         "semester", name="uq_enrollment"),
        CheckConstraint("semester >= 1 AND semester <= 8",
                        name="ck_enrollment_semester"),
        Index("ix_enrollment_student_semester", "student_index", "semester"),
        Index("ix_enrollment_subject_code", "subject_code"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    student_index: Mapped[int] = mapped_column(
        ForeignKey("students.index"), nullable=False)
    subject_code: Mapped[str] = mapped_column(
        ForeignKey("subjects.code"), nullable=False)
    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    listened: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True)

    student = relationship("Student", back_populates="enrollments")
    subject = relationship("Subject", back_populates="enrollments")


class ExamSession(Base):
    __tablename__ = "exam_sessions"
    __table_args__ = (
        UniqueConstraint("subject_code", "session_type",
                         "year", name="uq_exam_session"),
        Index("ix_exam_session_subject_year", "subject_code", "year"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    subject_code: Mapped[str] = mapped_column(
        ForeignKey("subjects.code"), nullable=False)
    session_type: Mapped[str] = mapped_column(String(20), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    exam_date: Mapped[date] = mapped_column(Date, nullable=False)

    subject = relationship("Subject", back_populates="exam_sessions")
    exams = relationship("Exam", back_populates="exam_session",
                         cascade="all, delete-orphan")


class Exam(Base):
    __tablename__ = "exams"
    __table_args__ = (
        UniqueConstraint("exam_session_id", "student_index",
                         name="uq_exam_student_session"),
        Index("ix_exam_student", "student_index"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    exam_session_id: Mapped[int] = mapped_column(
        ForeignKey("exam_sessions.id"), nullable=False)
    student_index: Mapped[int] = mapped_column(
        ForeignKey("students.index"), nullable=False)
    grade: Mapped[int] = mapped_column(Integer, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)

    student = relationship("Student", back_populates="exams")
    exam_session = relationship("ExamSession", back_populates="exams")


class DisciplinaryAction(Base):
    __tablename__ = "disciplinary_actions"
    __table_args__ = (Index("ix_disciplinary_student", "student_index"),)

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    student_index: Mapped[int] = mapped_column(
        ForeignKey("students.index"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(60), nullable=False)
    note: Mapped[str] = mapped_column(String(255), nullable=False)
    action_date: Mapped[date] = mapped_column(Date, nullable=False)

    student = relationship("Student", back_populates="disciplinary_actions")


class User(Base):
    """Device-login users: username + password, role from DB (no user input)."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(60), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)

    role: Mapped[str] = mapped_column(String(20), nullable=False)
