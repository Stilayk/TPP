from __future__ import annotations

from app.employee_exit_blocks import ALL_EMPLOYEE_EXIT_BLOCK_IDS, compose_employee_exit_instruction
from app.services import build_employee_exit_instruction, normalize_employee_exit_instruction_text


def test_full_instruction_contains_bitrix_and_support() -> None:
    t = compose_employee_exit_instruction("Иван И.", "user1", "Pass1", "rz", blocks=None)
    assert "Битрикс" in t
    assert "8 800 1000 750" in t


def test_subset_excludes_unchecked_blocks() -> None:
    t = compose_employee_exit_instruction("Иван И.", "u", "p", "rz", blocks=["company", "bitlocker"])
    assert "Sokolov" in t or "оборудование" in t
    assert "bitlocker" in t.lower()
    assert "Битрикс" not in t
    assert "8 800" not in t


def test_unknown_block_ids_fallen_back_to_all() -> None:
    t = compose_employee_exit_instruction("Иван И.", "u", "p", "rz", blocks=["nope", "invalid"])
    assert len(t) > 200
    assert len(ALL_EMPLOYEE_EXIT_BLOCK_IDS) >= 8


def test_normalize_instruction_strips_extra_blank_lines_and_spaces() -> None:
    assert normalize_employee_exit_instruction_text("Строка 1\n\n\nСтрока 2") == "Строка 1\n\nСтрока 2"
    assert normalize_employee_exit_instruction_text("Два  пробела  здесь") == "Два пробела здесь"


def test_build_instruction_uses_normalization_for_portal_block() -> None:
    t = build_employee_exit_instruction("Иван", "u", "p", "rz", blocks=["portal_intro"])
    assert "\n\n\n" not in t
    assert "учётной записи" in t
