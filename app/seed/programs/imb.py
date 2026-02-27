from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.db import SessionLocal
from app.models import Subject

try:
    from app.models import Program
except Exception:
    Program = None  # type: ignore

try:
    from app.models import ProgramSubject
except Exception:
    ProgramSubject = None  # type: ignore

IMB_NAME = "Интернет мрежи и безбедност"


def _has_attr(obj: Any, name: str) -> bool:
    return hasattr(obj, name)


def _set_if_exists(obj: Any, **fields: Any) -> None:
    for k, v in fields.items():
        if _has_attr(obj, k) and v is not None:
            setattr(obj, k, v)


def get_or_create_program(session, name: str):
    if Program is None:
        raise RuntimeError(
            "Program model not found. Create Program + ProgramSubject tables first."
        )
    prog = session.query(Program).filter(Program.name == name).first()
    if prog:
        return prog
    prog = Program(name=name)
    session.add(prog)
    session.flush()
    return prog


def get_or_create_subject(
    session,
    code: str,
    name: Optional[str] = None,
    recommended_semester: Optional[int] = None,
):
    subj = session.query(Subject).filter(Subject.code == code).first()
    if subj:
        if name:
            _set_if_exists(subj, name=name)
        if recommended_semester is not None:
            _set_if_exists(subj, semester=recommended_semester)
        return subj

    subj = Subject()
    subj.code = code
    _set_if_exists(subj, name=name or code)
    _set_if_exists(subj, semester=recommended_semester)
    session.add(subj)
    session.flush()
    return subj


def upsert_program_subject(
    session,
    program_id: Any,
    subject_code: str,
    semester_number: int,
    is_mandatory: bool,
    elective_group: Optional[str] = None,
):
    if ProgramSubject is None:
        return

    ps = (
        session.query(ProgramSubject)
        .filter(
            ProgramSubject.program_id == program_id,
            ProgramSubject.subject_code == subject_code,
        )
        .first()
    )

    if not ps:
        ps = ProgramSubject()
        ps.program_id = program_id
        ps.subject_code = subject_code
        session.add(ps)

    ps.semester = semester_number
    ps.is_mandatory = is_mandatory
    ps.elective_group_code = elective_group
    session.flush()


def _upsert_elective_slot_rule(
    session,
    program_id: Any,
    semester_number: int,
    slot_number: int,
    allowed_groups: List[str],
):
    from app.seed.base import ensure_semester_rule_slot
    ensure_semester_rule_slot(
        session, program_id, semester_number, slot_number, allowed_groups
    )


IMB_MANDATORY: Dict[int, List[Tuple[str, str]]] = {
    1: [
        ("F23L1W004", "Спорт и здравје"),
        ("F23L1W005", "Бизнис и менаџмент"),
        ("F23L1W007", "Вовед во компјутерските науки"),
        ("F23L1W018", "Професионални вештини"),
        ("F23L1W020", "Структурно програмирање"),
        ("F23L2W002", "Математика 1"),
    ],
    2: [
        ("F23L1S016", "Објектно-ориентирано програмирање"),
        ("F23L1S045", "Компјутерски архитектури"),
        ("F23L2S001", "Математика 2"),
        ("F23L2S066", "Основи на сајбер безбедноста"),
    ],
    3: [
        ("F23L2W046", "Компјутерски мрежи"),
        ("F23L2W067", "Основи на теоријата на информации"),
        ("F23L2W165", "Управување со техничка поддршка"),
        ("F23L2W201", "Примена на алгоритми и податочни структури"),
    ],
    4: [
        ("F23L2S017", "Оперативни системи"),
        ("F23L2S061", "Безжични и мобилни системи"),
        ("F23L2S110", "Интернет технологии"),
    ],
    5: [
        ("F23L3W004", "Бази на податоци"),
        ("F23L3W060", "Администрација на системи"),
        ("F23L3W065", "Сајбер безбедност"),
    ],
    6: [
        ("F23L3S059", "Администрација на мрежи"),
        ("F23L3S062", "Виртуелизација"),
        ("F23L3S159", "Софтверски дефинирана безбедност"),
    ],
    7: [
        ("F23L3W021", "Тимски проект"),
        ("F23L3W064", "Дистрибуирани системи"),
        ("F23L3W068", "Пресметување во облак"),
    ],
    8: [
        ("F23L3S063", "Дизајн на компјутерски мрежи"),
        ("F23L3S111", "Инфраструктурно програмирање"),
        ("F23L3S168", "Дипломска работа"),
    ],
}

IMB_ELECTIVE_SLOTS = [
    (2, 1, ["F23L1S"]),
    (3, 2, ["F23L2W"]),
    (4, 3, ["F23L2S"]),
    (4, 4, ["F23L2S"]),
    (5, 5, ["F23L2W", "F23L3W"]),
    (5, 6, ["F23L2W", "F23L3W"]),
    (6, 7, ["F23L2S", "F23L3S"]),
    (6, 8, ["F23L3S"]),
    (7, 9, ["F23L3W"]),
    (7, 10, ["F23L3W"]),
    (8, 11, ["F23L3S"]),
    (8, 12, ["F23L3S"]),
]

POOL_F23L1S: List[Tuple[str, str, int]] = [
    ("F23L1S052", "Е-учење", 2),
    ("F23L1S116", "Компјутерски компоненти", 2),
    ("F23L1S120", "Креативни вештини за решавање проблеми", 2),
    ("F23L1S146", "Основи на Веб дизајн", 2),
]

POOL_F23L2S: List[Tuple[str, str, int]] = [
    ("F23L2S015", "Објектно ориентирана анализа и дизајн", 2),
    ("F23L2S026", "Маркетинг", 4),
    ("F23L2S002", "Анализа на софтверските барања", 4),
    ("F23L2S029", "Софтверско инженерство", 4),
    ("F23L2S030", "Вештачка интелигенција", 4),
    ("F23L2S042", "Електрични кола", 4),
    ("F23L2S051", "Информатичко размислување во образованието", 4),
    ("F23L2S082", "Визуелно програмирање", 4),
    ("F23L2S084", "Вовед во екоинформатиката", 4),
    ("F23L2S090", "Вовед во случајни процеси", 4),
    ("F23L2S095", "Дигитално процесирање на слика", 4),
    ("F23L2S097", "Дизајн на алгоритми", 4),
    ("F23L2S099", "Е-влада", 4),
    ("F23L2S114", "Компјутерска графика", 4),
    ("F23L2S119", "Концепти на информатичко општество", 4),
    ("F23L2S124", "Медиуми и комуникации", 4),
    ("F23L2S164", "Теорија на информации со дигитални комуникации", 4),
]

POOL_F23L2W: List[Tuple[str, str, int]] = [
    ("F23L2W006", "Веројатност и статистика", 3),
    ("F23L2W055", "Мултимедијални технологии", 3),
    ("F23L2W096", "Дигитизација", 3),
    ("F23L2W100", "Економија за ИКТ инженери", 3),
    ("F23L2W104", "Инженерска математика", 3),
    ("F23L2W109", "Интернет програмирање на клиентска страна", 3),
    ("F23L2W147", "Основи на комуникациски системи", 3),
    ("F23L2W167", "Шаблони за дизајн на кориснички интерфејси", 3),
]

POOL_F23L3S: List[Tuple[str, str, int]] = [
    ("F23L3S100", "Деловна пракса", 4),
    ("F23L3S010", "Дизајн на интеракцијата човек-компјутер", 6),
    ("F23L3S012", "Интегрирани системи", 6),
    ("F23L3S019", "Софтверски квалитет и тестирање", 6),
    ("F23L3S025", "Електронска и мобилна трговија", 6),
    ("F23L3S036", "Машинско учење", 6),
    ("F23L3S039", "Основи на теоријата на компјутерските науки", 6),
    ("F23L3S040", "Вградливи микропроцесорски системи", 6),
    ("F23L3S047", "Процесирање на сигналите", 6),
    ("F23L3S057", "Работа со надарени ученици", 6),
    ("F23L3S071", "Психологија на училишна возраст", 6),
]

POOL_F23L3W: List[Tuple[str, str, int]] = [
    ("F23L3W001", "Математика 3", 3),
    ("F23L3W008", "Вовед во науката за податоци", 5),
    ("F23L3W009", "Дизајн и архитектура на софтвер", 5),
    ("F23L3W024", "Веб програмирање", 5),
    ("F23L3W035", "Линеарна алгебра и примени", 5),
    ("F23L3W037", "Паралелно и дистрибуирано процесирање", 5),
    ("F23L3W044", "Компјутерска електроника", 5),
    ("F23L3W050", "Дизајн на образовен софтвер", 5),
    ("F23L3W053", "Компјутерска етика", 5),
    ("F23L3W056", "Персонализирано учење", 5),
    ("F23L3W081", "Визуелизација", 5),
    ("F23L3W134", "Мултимедиски мрежи", 5),
    ("F23L3W136", "Напреден веб дизајн", 5),
    ("F23L3W140", "Напредно програмирање", 5),
    ("F23L3W142", "Обработка на природните јазици", 5),
    ("F23L3W148", "Основи на роботиката", 5),
    ("F23L3W158", "Современи компјутерски архитектури", 5),
    ("F23L3W161", "Теорија на графови и социјални мрежи", 5),
    ("F23L3W033", "Тестирање на софтвер", 7),
]


def seed_imb(session) -> None:
    imb = get_or_create_program(session, IMB_NAME)
    program_id = getattr(imb, "id")

    for sem, items in IMB_MANDATORY.items():
        for code, name in items:
            get_or_create_subject(
                session, code, name=name, recommended_semester=sem)
            upsert_program_subject(
                session,
                program_id=program_id,
                subject_code=code,
                semester_number=sem,
                is_mandatory=True,
                elective_group=None,
            )

    for sem, slot_no, groups in IMB_ELECTIVE_SLOTS:
        _upsert_elective_slot_rule(
            session,
            program_id=program_id,
            semester_number=sem,
            slot_number=slot_no,
            allowed_groups=groups,
        )

    pools = [
        ("F23L1S", POOL_F23L1S),
        ("F23L2S", POOL_F23L2S),
        ("F23L2W", POOL_F23L2W),
        ("F23L3S", POOL_F23L3S),
        ("F23L3W", POOL_F23L3W),
    ]

    for group_code, rows in pools:
        for code, name, rec_sem in rows:
            get_or_create_subject(
                session, code, name=name, recommended_semester=rec_sem)
            upsert_program_subject(
                session,
                program_id=program_id,
                subject_code=code,
                semester_number=rec_sem,
                is_mandatory=False,
                elective_group=group_code,
            )


if __name__ == "__main__":
    from app.seed.base import run_seed
    run_seed(seed_imb)
