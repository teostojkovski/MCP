from __future__ import annotations

import re
from typing import Optional, List, Tuple

from app.models import Subject, SubjectPrerequisite, SubjectRequirement


def resolve_subject_code(session, code: str) -> Optional[str]:
    s = session.query(Subject).filter(Subject.code == code).first()
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


def add_rule(session, subject_code: str, rule_text: str) -> None:
    if not resolve_subject_code(session, subject_code):
        print(f"⚠️  Skipping (subject not found by code): {subject_code}")
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
    ("F23L2S001", "(F23L2W002)"),
    ("F23L2W001", "(F23L1W020) AND (F23L2W002)"),
    ("F23L3W001", "(F23L2S001)"),
    ("F23L2S002", "(F23L2S015) OR (F23L1S016)"),
    ("F23L2S017", "(F23L1S003)"),
    ("F23L2S030", "(Earned at least 36 ECTS)"),
    ("F23L3S100", "(Earned at least 90 ECTS)"),
    ("F23L3W008", "(F23L3W001)"),
    ("F23L3W009", "(F23L2S015) OR (F23L1S016)"),
    ("F23L3W140", "(F23L1S016)"),
    ("F23L3S012", "(F23L2S002) OR (F23L2S029)"),
    ("F23L3S019", "(F23L3W009)"),
    ("F23L3S138", "(F23L3W004)"),
    ("F23L3W021", "(F23L2S002) AND (F23L3W009)"),
    ("F23L3S022", "(F23L1W005)"),
    ("F23L3S028", "(F23L1W005)"),
    ("F23L3S168", "(Earned at least 180 ECTS)"),
]


def seed_siis_prereqs(session) -> None:
    for subject_code, rule_text in RULES:
        add_rule(session, subject_code, rule_text)
