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

SIIS_NAME = "Софтверско инженерство и информациски системи"

ELECTIVE_SEMESTER_UNKNOWN = 0


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


def get_or_create_subject(session, code: str, name: Optional[str] = None, semester: Optional[int] = None):
    subj = session.query(Subject).filter(Subject.code == code).first()
    if subj:
        if name:
            _set_if_exists(subj, name=name)
        if semester is not None:
            _set_if_exists(subj, semester=semester)
        return subj

    subj = Subject()
    subj.code = code
    _set_if_exists(subj, name=name or code)
    _set_if_exists(subj, semester=semester)
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


SIIS_MANDATORY: Dict[int, List[Tuple[str, str]]] = {
    1: [
        ("F23L1W004", "Спорт и здравје"),
        ("F23L1W005", "Бизнис и менаџмент"),
        ("F23L1W007", "Вовед во компјутерските науки"),
        ("F23L1W018", "Професионални вештини"),
        ("F23L1W020", "Структурно програмирање"),
        ("F23L2W002", "Математика 1"),
    ],
    2: [
        ("F23L1S003", "Архитектура и организација на компјутери"),
        ("F23L1S016", "Објектно-ориентирано програмирање"),
        ("F23L2S001", "Математика 2"),
        ("F23L2S015", "Објектно ориентирана анализа и дизајн"),
    ],
    3: [
        ("F23L2W001", "Алгоритми и податочни структури"),
        ("F23L2W014", "Компјутерски мрежи и безбедност"),
        ("F23L3W001", "Математика 3"),
    ],
    4: [
        ("F23L2S002", "Анализа на софтверските барања"),
        ("F23L2S017", "Оперативни системи"),
        ("F23L2S030", "Вештачка интелигенција"),
        ("F23L3S100", "Деловна пракса"),
    ],
    5: [
        ("F23L3W004", "Бази на податоци"),
        ("F23L3W008", "Вовед во науката за податоци"),
        ("F23L3W009", "Дизајн и архитектура на софтвер"),
        ("F23L3W140", "Напредно програмирање"),
    ],
    6: [
        ("F23L3S010", "Дизајн на интеракцијата човек-компјутер"),
        ("F23L3S012", "Интегрирани системи"),
        ("F23L3S019", "Софтверски квалитет и тестирање"),
        ("F23L3S138", "Напредни бази на податоци"),
    ],
    7: [
        ("F23L3W021", "Тимски проект"),
    ],
    8: [
        ("F23L3S022", "Управување со ИКТ проекти"),
        ("F23L3S028", "Претприемништво"),
        ("F23L3S168", "Дипломска работа"),
    ],
}

SIIS_ELECTIVE_SLOTS = [
    (2, 1, ["F23L1S"]),
    (3, 2, ["F23L2W"]),
    (3, 3, ["F23L2W"]),
    (4, 4, ["F23L2S"]),
    (5, 5, ["F23L2W", "F23L3W"]),
    (6, 6, ["F23L2S", "F23L3S"]),
    (7, 7, ["F23L3W"]),
    (7, 8, ["F23L3W"]),
    (7, 9, ["F23L3W"]),
    (7, 10, ["F23L3W"]),
    (8, 11, ["F23L2S", "F23L3S"]),
    (8, 12, ["F23L3S"]),
]

POOL_F23L1S: List[Tuple[str, str]] = [
    ("F23L1S052", "Е-учење"),
    ("F23L1S116", "Компјутерски компоненти"),
    ("F23L1S120", "Креативни вештини за решавање проблеми"),
    ("F23L1S146", "Основи на Веб дизајн"),
    ("F23L2S066", "Основи на сајбер безбедноста"),
]

POOL_F23L2S: List[Tuple[str, str]] = [
    ("F23L2S026", "Маркетинг"),
    ("F23L2S042", "Електрични кола"),
    ("F23L2S051", "Информатичко размислување во образованието"),
    ("F23L2S061", "Безжични и мобилни системи"),
    ("F23L2S082", "Визуелно програмирање"),
    ("F23L2S084", "Вовед во екоинформатиката"),
    ("F23L2S090", "Вовед во случајни процеси"),
    ("F23L2S095", "Дигитално процесирање на слика"),
    ("F23L2S097", "Дизајн на алгоритми"),
    ("F23L2S099", "Е-влада"),
    ("F23L2S110", "Интернет технологии"),
    ("F23L2S114", "Компјутерска графика"),
    ("F23L2S119", "Концепти на информатичко општество"),
    ("F23L2S124", "Медиуми и комуникации"),
    ("F23L2S164", "Теорија на информации со дигитални комуникации"),
]

POOL_F23L2W: List[Tuple[str, str]] = [
    ("F23L2W006", "Веројатност и статистика"),
    ("F23L2W055", "Мултимедијални технологии"),
    ("F23L2W067", "Основи на теоријата на информации"),
    ("F23L2W096", "Дигитизација"),
    ("F23L2W100", "Економија за ИКТ инженери"),
    ("F23L2W104", "Инженерска математика"),
    ("F23L2W109", "Интернет програмирање на клиентска страна"),
    ("F23L2W147", "Основи на комуникациски системи"),
    ("F23L2W165", "Управување со техничка поддршка"),
    ("F23L2W167", "Шаблони за дизајн на кориснички интерфејси"),
]

POOL_F23L3S: List[Tuple[str, str]] = [
    ("F23L3S025", "Електронска и мобилна трговија"),
    ("F23L3S036", "Машинско учење"),
    ("F23L3S039", "Основи на теоријата на компјутерските науки"),
    ("F23L3S040", "Вградливи микропроцесорски системи"),
    ("F23L3S047", "Процесирање на сигналите"),
    ("F23L3S057", "Работа со надарени ученици"),
    ("F23L3S059", "Администрација на мрежи"),
    ("F23L3S062", "Виртуелизација"),
    ("F23L3S071", "Психологија на училишна возраст"),
    ("F23L3S073", "Агентно-базирани системи"),
    ("F23L3S087", "Вовед во мрежна наука"),
    ("F23L3S091", "Географски информациски системи"),
    ("F23L3S093", "Дигитална форензика"),
    ("F23L3S094", "Дигитални библиотеки"),
    ("F23L3S113", "Компјутерска анимација"),
    ("F23L3S115", "Компјутерски звук, музика и говор"),
    ("F23L3S118", "Континуирана интеграција и испорака"),
    ("F23L3S122", "Криптографија"),
    ("F23L3S125", "Мерење и анализа на сообраќај"),
    ("F23L3S135", "Мултимедиски системи"),
    ("F23L3S149", "Паралелно програмирање"),
    ("F23L3S150", "Податочно рударење"),
    ("F23L3S153", "Вештачка интелигенција за игри"),
    ("F23L3S155", "Сервисно ориентирани архитектури"),
    ("F23L3S157", "Складови на податоци и аналитичка обработка"),
    ("F23L3S159", "Софтверски дефинирана безбедност"),
    ("F23L3S163", "Автоматизирање на процеси во машинско учење"),
    ("F23L3S166", "Учење на далечина"),
    ("F23L3S054", "Методика на информатиката"),
    ("F23L3S063", "Дизајн на компјутерски мрежи"),
    ("F23L3S069", "Адаптивни и интерактивни веб информациски системи"),
    ("F23L3S070", "Македонски јазик"),
    ("F23L3S078", "Биолошки инспирирано пресметување"),
    ("F23L3S080", "Веб пребарувачки системи"),
    ("F23L3S083", "Виртуелна реалност"),
    ("F23L3S086", "Вовед во когнитивни науки"),
    ("F23L3S101", "Етичко хакирање"),
    ("F23L3S102", "ИКТ за развој"),
    ("F23L3S106", "Откривање знаење со длабоко учење"),
    ("F23L3S107", "Интелигентни системи"),
    ("F23L3S111", "Инфраструктурно програмирање"),
    ("F23L3S112", "Програмски јазици и компајлери"),
    ("F23L3S127", "Мобилни апликации"),
    ("F23L3S130", "Моделирање и менаџирање на бизнис процеси"),
    ("F23L3S131", "Моделирање и симулација"),
    ("F23L3S132", "Модерни трендови во роботика"),
    ("F23L3S139", "Web3 апликации"),
    ("F23L3S141", "Неструктурирани бази на податоци"),
    ("F23L3S144", "Операциони истражувања"),
    ("F23L3S160", "Софтверски дефинирани мрежи"),
    ("F23L3S162", "Споделување и пресметување во толпа"),
]

POOL_F23L3W: List[Tuple[str, str]] = [
    ("F23L3W024", "Веб програмирање"),
    ("F23L3W035", "Линеарна алгебра и примени"),
    ("F23L3W037", "Паралелно и дистрибуирано процесирање"),
    ("F23L3W043", "Информациска безбедност"),
    ("F23L3W044", "Компјутерска електроника"),
    ("F23L3W050", "Дизајн на образовен софтвер"),
    ("F23L3W053", "Компјутерска етика"),
    ("F23L3W056", "Персонализирано учење"),
    ("F23L3W060", "Администрација на системи"),
    ("F23L3W065", "Сајбер безбедност"),
    ("F23L3W081", "Визуелизација"),
    ("F23L3W134", "Мултимедиски мрежи"),
    ("F23L3W136", "Напреден веб дизајн"),
    ("F23L3W142", "Обработка на природните јазици"),
    ("F23L3W148", "Основи на роботиката"),
    ("F23L3W158", "Современи компјутерски архитектури"),
    ("F23L3W161", "Теорија на графови и социјални мрежи"),
    ("F23L3W027", "Менаџмент информациски системи"),
    ("F23L3W038", "Програмски парадигми"),
    ("F23L3W048", "Софтвер за вградливи системи"),
    ("F23L3W064", "Дистрибуирани системи"),
    ("F23L3W068", "Пресметување во облак"),
    ("F23L3W072", "Автономна роботика"),
    ("F23L3W074", "Администрација на бази податоци"),
    ("F23L3W075", "Анализа и дизајн на ИС"),
    ("F23L3W076", "Вовед во анализа на временските серии"),
    ("F23L3W079", "Веб базирани системи"),
    ("F23L3W085", "Вовед во биоинформатиката"),
    ("F23L3W088", "Вовед во паметни градови"),
    ("F23L3W089", "Вовед во препознавање на облици"),
    ("F23L3W092", "Дигитална постпродукција"),
    ("F23L3W098", "Дистрибуирано складирање на податоци"),
    ("F23L3W103", "Имплементација на софтверски системи со слободен и отворен код"),
    ("F23L3W105", "Иновации во ИКТ"),
    ("F23L3W108", "Интернет на нештата"),
    ("F23L3W117", "Компјутерски поддржано производство"),
    ("F23L3W121", "Блоковски вериги и криптовалути"),
    ("F23L3W123", "Машинска визија"),
    ("F23L3W126", "Методологија на истражувањето во ИКТ"),
    ("F23L3W128", "Мобилни информациски системи"),
    ("F23L3W129", "Мобилни платформи и програмирање"),
    ("F23L3W133", "Мрежна и мобилна форензика"),
    ("F23L3W137", "Напредна интеракција човек компјутер"),
    ("F23L3W145", "Оптички мрежи"),
    ("F23L3W152", "Програмирање на видео игри"),
    ("F23L3W154", "Вовед во рударење на масивни податоци"),
    ("F23L3W156", "Системи за поддршка при одлучувањето"),
    ("F23L3W162", "Квантно пресметување"),
    ("F23L3W200", "Сензорски системи"),
]


def seed_siis(session) -> None:
    siis = get_or_create_program(session, SIIS_NAME)
    program_id = getattr(siis, "id")

    for sem, items in SIIS_MANDATORY.items():
        for code, name in items:
            get_or_create_subject(session, code, name=name, semester=sem)
            upsert_program_subject(
                session,
                program_id=program_id,
                subject_code=code,
                semester_number=sem,
                is_mandatory=True,
                elective_group=None,
            )

    for sem, slot_no, groups in SIIS_ELECTIVE_SLOTS:
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
        for code, name in rows:
            get_or_create_subject(session, code, name=name, semester=None)
            upsert_program_subject(
                session,
                program_id=program_id,
                subject_code=code,
                semester_number=ELECTIVE_SEMESTER_UNKNOWN,
                is_mandatory=False,
                elective_group=group_code,
            )


if __name__ == "__main__":
    from app.seed.base import run_seed
    run_seed(seed_siis)
