"""CLI-режим: поиск дубликатов из командной строки."""

import argparse
import logging
import sys
from pathlib import Path

from core.scanner import scan_directory, normalize_extensions
from core.duplicate_finder import find_duplicates
from core.reports import export_html, export_txt
from core.session import build_session_from_groups
from core.file_ops import apply_action_to_group
from utils.helpers import human_size, parse_size_string

log = logging.getLogger(__name__)


def run(argv):
    parser = argparse.ArgumentParser(
        prog="duplicate-finder --cli",
        description="Поиск дубликатов файлов в командной строке.",
    )
    parser.add_argument("path", help="директория для сканирования")
    parser.add_argument(
        "--no-recursive", action="store_true", help="не заходить в подпапки"
    )
    parser.add_argument(
        "--min-size",
        default="1",
        help="мин. размер, напр. 1MB (по умолчанию 1 байт)",
    )
    parser.add_argument(
        "--max-size", default=None, help="макс. размер, напр. 1GB"
    )
    parser.add_argument(
        "--ext", default="", help="расширения через запятую, напр. .jpg,.png"
    )
    parser.add_argument(
        "--include-empty", action="store_true", help="искать пустые файлы"
    )
    parser.add_argument(
        "--min-savings", default="0", help="порог экономии, напр. 10MB"
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument(
        "--report", default=None, help="путь для отчёта (html или txt)"
    )
    parser.add_argument(
        "--apply",
        choices=["delete", "trash", "symlink", "hardlink"],
        default=None,
        help="применить действие к дубликатам "
        "(первый файл в группе — оригинал)",
    )
    parser.add_argument("--yes", action="store_true", help="без подтверждения")

    args = parser.parse_args(argv)

    root = Path(args.path)
    if not root.is_dir():
        print(f"Ошибка: не директория: {root}", file=sys.stderr)
        return 2

    min_size = parse_size_string(args.min_size)
    max_size = parse_size_string(args.max_size) if args.max_size else None
    extensions = normalize_extensions(args.ext)

    # 1. Сканирование
    print(f"Сканирую {root} …")
    files = list(
        scan_directory(
            root,
            recursive=not args.no_recursive,
            min_size=min_size,
            max_size=max_size,
            extensions=extensions,
        )
    )
    print(f"Найдено {len(files)} файлов. Ищу дубликаты …")

    # 2. Поиск дубликатов
    def cb(stage, done, total):
        if total:
            pct = int(100 * done / total)
            sys.stdout.write(f"\r  {stage}: {pct}%  ")
            sys.stdout.flush()

    result = find_duplicates(
        files,
        progress_cb=cb,
        include_empty=args.include_empty,
        use_cache=not args.no_cache,
        workers=args.workers,
    )
    print()

    # 3. Фильтрация по экономии
    threshold = parse_size_string(args.min_savings)
    shown = {}
    for h, paths in result.items():
        try:
            size = paths[0].stat().st_size
        except OSError:
            size = 0
        if size * (len(paths) - 1) >= threshold:
            shown[h] = paths

    if not shown:
        print("Дубликаты не найдены (или все ниже порога).")
        return 0

    total_wasted = 0
    for h, paths in shown.items():
        try:
            size = paths[0].stat().st_size
        except OSError:
            size = 0
        total_wasted += size * (len(paths) - 1)

    print(
        f"Групп: {len(shown)}. Потенциально освободится: "
        f"{human_size(total_wasted)}\n"
    )

    # 4. Вывод в консоль
    for i, (h, paths) in enumerate(shown.items(), 1):
        try:
            size = paths[0].stat().st_size
        except OSError:
            size = 0
        print(f"Группа #{i} ({len(paths)} файлов, {human_size(size)})")
        for j, p in enumerate(paths):
            mark = "★" if j == 0 else " "
            print(f"  {mark} {p}")
        print()

    # 5. Сохранение отчета
    if args.report:

        session = build_session_from_groups(
            groups=shown,
            root_dir=str(root),
            filters={
                "extensions": sorted(extensions),
                "min_size": min_size,
                "max_size": max_size,
                "include_empty": args.include_empty,
            },
        )
        rp = Path(args.report)
        if rp.suffix.lower() == ".txt":
            export_txt(session, rp)
        else:
            export_html(session, rp)
        print(f"Отчёт сохранён: {rp}")

    # 6. Применение действий (удаление/ссылки)
    if args.apply:
        if not args.yes:
            ans = input("Применить действие? (yes/no): ").strip().lower()
            if ans not in ("yes", "y"):
                print("Отменено.")
                return 0

        ok_sum, err_sum = 0, 0
        for h, paths in shown.items():
            original, targets = paths[0], paths[1:]
            ok, errors = apply_action_to_group(
                original,
                targets,
                args.apply,
            )
            ok_sum += ok
            err_sum += len(errors)

        print(f"Обработано: {ok_sum}, ошибок: {err_sum}")

    return 0
