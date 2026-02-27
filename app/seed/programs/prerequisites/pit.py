from __future__ import annotations

import re
from typing import Optional, List, Tuple

from app.models import Subject, SubjectPrerequisite, SubjectRequirement


def resolve_subject_code_by_name(session, subject_name: str) -> Optional[str]:
    s = session.query(Subject).filter(Subject.name == subject_name).first()
    if s:
        return s.code
    s = session.query(Subject).filter(
        Subject.name.ilike(f"%{subject_name}%")).first()
    return s.code if s else None


def _parse_min_ects(rule_text: str) -> Optional[int]:
    m = re.search(r"(?:Earned at least|at least)\s+(\d+)\s*ECTS",
                  rule_text, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*ECTS", rule_text)
    if m:
        return int(m.group(1))
    return None


def add_rule_by_code(session, subject_code: str, rule_text: str) -> None:
    subj = session.query(Subject).filter(Subject.code == subject_code).first()
    if not subj:
        print(f"Warning: Skipping (subject not found): {subject_code!r}")
        return

    session.add(
        SubjectPrerequisite(
            subject_code=subject_code,
            prereq_subject_code=None,
            rule_text=rule_text,
        )
    )

    min_ects = _parse_min_ects(rule_text)
    if min_ects is not None:
        req = session.query(SubjectRequirement).filter(
            SubjectRequirement.subject_code == subject_code
        ).first()
        if not req:
            req = SubjectRequirement(subject_code=subject_code)
            session.add(req)
        req.min_ects = min_ects


RULES: List[Tuple[str, str]] = [
    ("F23L2S017", "(Computer Architectures)"),
    ("F23L2W201", "(Algorithms and data structures)"),
    ("F23L3S168", "(Earned at least 180 ECTS)"),
    ("F23L3W021", "(Earned at least 150 ECTS)"),
]


def seed_pit_prereqs(session) -> None:
    for subject_code, rule_text in RULES:
        add_rule_by_code(session, subject_code, rule_text)
