"""Фрагменты инструкции «выход сотрудника» (см. задачу №58). Порядок — в EMPLOYEE_EXIT_BLOCK_ORDER."""

from __future__ import annotations

from typing import Callable

BlockFn = Callable[[str, str, str, str], str]


def _company(fio: str, _login: str, _password: str, _domain: str) -> str:
    return (
        f"Добрый день, {fio}, я системный администратор в компании Sokolov, вам выдано оборудование."
    )


def _bitlocker(_fio: str, _login: str, _password: str, _domain: str) -> str:
    return "При включении ноутбука открывается bitlocker - стандартный пароль от него Sokolov2026"


def _credentials(_fio: str, login: str, password: str, _domain: str) -> str:
    return (
        f"Ваш логин - {login}, ваш пароль, при первом входе попросит сменить - {password}"
    )


def _domain(_fio: str, login: str, _password: str, domain: str) -> str:
    domain_login_example = f"{domain}\\{login}"
    return (
        f"Ваш домен — {domain}.\n"
        f"Пример учётной записи в формате домена: {domain_login_example}"
    )


def _portal_intro(_fio: str, _login: str, _password: str, _domain: str) -> str:
    return (
        "Вход в сервисы осуществляется по доменной учётной записи.\n\n"
        "После входа в учетную запись вы можете войти в информационные ресурсы компании, почту, битрикс24."
    )


def _bitrix(_fio: str, _login: str, _password: str, _domain: str) -> str:
    return (
        "При входе в Битрикс у вас запросит адрес сайта - 'portal.hpdd.ru', логин и пароль от вашей доменной учётной записи."
    )


def _outlook(_fio: str, _login: str, _password: str, _domain: str) -> str:
    return "Для входа в Outlook также используется доменная учётная запись."


def _zoom(_fio: str, login: str, _password: str, domain: str) -> str:
    domain_login_example = f"{domain}\\{login}"
    return (
        f"При входе в ZOOM нужно выбрать вход через Active Directory и ввести учётную запись в формате {domain_login_example} и пароль."
    )


def _notes(_fio: str, _login: str, _password: str, _domain: str) -> str:
    return (
        "Важно:\n"
        "• Папка 'Загрузки' автоматически очищается при перезагрузке.\n"
        "• Папка 'Документы' синхронизируется с сервером, для удобства при смене оборудования - данные будут синхронизированы."
    )


def _support(_fio: str, _login: str, _password: str, _domain: str) -> str:
    return (
        "По всем вопросам вы можете набрать по номеру 8 800 1000 750 (добавочный уточняйте у руководителя или в службе поддержки)."
    )


EMPLOYEE_EXIT_BLOCK_ORDER: tuple[tuple[str, BlockFn], ...] = (
    ("company", _company),
    ("bitlocker", _bitlocker),
    ("credentials", _credentials),
    ("domain", _domain),
    ("portal_intro", _portal_intro),
    ("bitrix", _bitrix),
    ("outlook", _outlook),
    ("zoom", _zoom),
    ("notes", _notes),
    ("support", _support),
)

ALL_EMPLOYEE_EXIT_BLOCK_IDS: tuple[str, ...] = tuple(bid for bid, _ in EMPLOYEE_EXIT_BLOCK_ORDER)


def normalize_employee_exit_blocks(blocks: list[str] | None) -> list[str]:
    """Пустой список или None — полный набор; неизвестные id отбрасываются."""
    known_order = [bid for bid, _ in EMPLOYEE_EXIT_BLOCK_ORDER]
    known_set = set(known_order)
    if not blocks:
        return list(known_order)
    chosen = [bid for bid in known_order if bid in set(blocks) & known_set]
    return chosen if chosen else list(known_order)


def compose_employee_exit_instruction(
    fio: str, login: str, password: str, domain: str, blocks: list[str] | None = None
) -> str:
    fio = (fio or "").strip()
    login = (login or "").strip()
    password = (password or "").strip()
    domain = (domain or "").strip()
    by_id = {bid: fn for bid, fn in EMPLOYEE_EXIT_BLOCK_ORDER}
    parts: list[str] = []
    for bid in normalize_employee_exit_blocks(blocks):
        parts.append(by_id[bid](fio, login, password, domain))
    return "\n\n".join(parts)
