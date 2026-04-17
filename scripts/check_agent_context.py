#!/usr/bin/env python3
"""
Проверка контекста агента: ключевые файлы репозитория и давность последней даты в HANDOFF.md.
Запуск из корня репозитория: python scripts/check_agent_context.py
"""
import argparse
import re
import sys
from datetime import date
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_REQUIRED = [
    "HANDOFF.md",
    "TASKS.md",
    "AGENT_WORKFLOW.md",
    "CONTINUE_PROMPT.md",
    "START_CHECKLIST.md",
    "docs/handoff-conventions.md",
    "docs/examples-orchestration.md",
    "ProjectTP/subagent-orchestration-policy.md",
]


def find_last_step_dates(handoff_text: str) -> List[date]:
    dates: List[date] = []
    for m in re.finditer(r"\*\*Время:\*\*\s*(\d{4})-(\d{2})-(\d{2})", handoff_text):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            dates.append(date(y, mo, d))
        except ValueError:
            continue
    return dates


def has_active_anchor(text: str) -> bool:
    return "## Якорь ACTIVE" in text or "**ACTIVE:**" in text


def main() -> int:
    p = argparse.ArgumentParser(description="Проверка файлов и свежести HANDOFF.md")
    p.add_argument(
        "--max-days",
        type=int,
        default=21,
        metavar="N",
        help="Предупреждение, если последняя дата в логе старше N дней (0 = не проверять)",
    )
    p.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Корень репозитория",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Код выхода 1 при любых предупреждениях (для CI)",
    )
    args = p.parse_args()
    root: Path = args.root.resolve()
    errors = 0
    warnings = 0

    for rel in DEFAULT_REQUIRED:
        path = root / rel
        if not path.is_file():
            print(f"ERROR: нет файла: {rel}")
            errors += 1
        else:
            print(f"OK: {rel}")

    handoff_path = root / "HANDOFF.md"
    if handoff_path.is_file():
        text = handoff_path.read_text(encoding="utf-8")
        if not has_active_anchor(text):
            print("WARN: в HANDOFF.md не найден якорь ACTIVE (см. START_CHECKLIST.md / handoff-conventions.md)")
            warnings += 1
        dates = find_last_step_dates(text)
        if not dates:
            print("WARN: в HANDOFF.md не найдено полей **Время:** с датой YYYY-MM-DD")
            warnings += 1
        elif args.max_days > 0:
            last = dates[-1]
            age = (date.today() - last).days
            if age > args.max_days:
                print(
                    f"WARN: последняя дата в логе {last} ({age} дн. назад); проверь актуальность контекста"
                )
                warnings += 1
            else:
                print(f"OK: последняя дата в логе {last} (в пределах {args.max_days} дн.)")

    if errors:
        print(f"\nИтого: {errors} ошибок, {warnings} предупреждений", file=sys.stderr)
        return 1
    print(f"\nИтого: 0 ошибок, {warnings} предупреждений")
    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
