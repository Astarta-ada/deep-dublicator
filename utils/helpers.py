"""Вспомогательные функции общего назначения."""

import os
from datetime import datetime
from pathlib import Path
from typing import Tuple


def human_size(num: int):  # -> str:
    """Преобразует размер в байтах в человекочитаемый формат (KB, MB, GB)."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} PB"


def parse_size_string(s: str):  # -> int:
    """Парсит строку размера ('1.5 GB', '500 MB') в байты."""
    s = s.strip().upper()
    mult = 1
    for suf, m in (
        ("KB", 1024),
        ("MB", 1024**2),
        ("GB", 1024**3),
        ("TB", 1024**4),
    ):
        if s.endswith(suf):
            mult = m
            s = s[: -len(suf)]
            break
    return int(float(s) * mult)


def get_file_creation_time(st):  # -> float:
    """ "
    Кроссплатформенно возвращает время создания файла.
    Использует st_birthtime (если доступно), иначе fallback на st_ctime.
    """
    return getattr(st, "st_birthtime", st.st_ctime)


def format_date(timestamp: float, with_time: bool = False):  # -> str:
    """
    Форматирует timestamp в строку (YYYY-MM-DD или YYYY-MM-DD HH:MM:SS).
    """
    dt = datetime.fromtimestamp(timestamp)
    if with_time:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return dt.strftime("%Y-%m-%d")


def get_dir_stats(path: Path):  # -> Tuple[int, int]:
    """
    Рекурсивно считает размер (в байтах) и количество файлов в папке.
    Возвращает (total_size, total_files).
    Используется в воркерах для анализа диска и очистки мусора.
    """
    total_size = 0
    total_files = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_file(follow_symlinks=False):
                        total_size += entry.stat().st_size
                        total_files += 1
                    elif entry.is_dir(follow_symlinks=False):
                        s, f = get_dir_stats(Path(entry.path))
                        total_size += s
                        total_files += f
                except (PermissionError, OSError):
                    continue
    except (PermissionError, OSError):
        pass
    return total_size, total_files
