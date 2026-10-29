"""Обход директорий с фильтрацией по размерам, расширениям и маскам."""

import fnmatch
import logging
import os
from pathlib import Path
from typing import Iterable, Callable, Optional

from utils.config import DEFAULT_EXCLUDE_DIRS

log = logging.getLogger(__name__)


def normalize_extensions(raw: str):  # -> set[str]:
    """
    Приводит пользовательский ввод к множеству расширений.
    Пример: 'jpg, .PNG' -> {'.jpg', '.png'}
    """
    if not raw or not raw.strip():
        return set()

    parts = raw.replace(";", ",").split(",")
    result: set[str] = set()

    for p in parts:
        p = p.strip().lower()
        if not p:
            continue
        if not p.startswith("."):
            p = "." + p
        result.add(p)

    return result


def scan_directory(
    root: Path,
    recursive: bool = True,
    min_size: int = 1,
    max_size: Optional[int] = None,
    extensions: Optional[set[str]] = None,
    exclude_dirs: Optional[set[str]] = None,
    exclude_globs: Optional[list[str]] = None,
    progress_cb: Optional[Callable[[int], None]] = None,
    include_links: bool = False,
):  # -> Iterable[Path]:
    """
    Возвращает файлы для анализа.

    :param root: Корневая директория.
    :param recursive: Обходить ли поддиректории.
    :param min_size: Минимальный размер файла (0 — включая пустые).
    :param max_size: Максимальный размер (None — без ограничения).
    :param extensions: Множество расширений (None — без фильтра).
    :param exclude_dirs: Имена папок, которые нужно пропускать.
    :param exclude_globs: Маски файлов для пропуска (например, "*.tmp", "~$*").
    :param progress_cb: Колбэк для обновления прогресса (вызывается каждые 500 файлов).
    :param include_links: Если True, сканер будет включать симлинки и хардлинки.
    """

    exclude_dirs = exclude_dirs or DEFAULT_EXCLUDE_DIRS
    exclude_globs = exclude_globs or []
    count = 0

    def _walk(directory: Path):
        nonlocal count
        try:
            # Используем os.scandir для максимальной производительности (кэширует stat)
            with os.scandir(directory) as it:
                for entry in it:
                    try:
                        # 1. Проверка по маскам (glob)
                        if any(
                            fnmatch.fnmatch(entry.name, pat)
                            for pat in exclude_globs
                        ):
                            continue

                        # 2. Обработка символических ссылок
                        if entry.is_symlink():
                            if include_links:
                                yield Path(entry.path)
                            continue

                        # 3. Обработка директорий
                        if entry.is_dir(follow_symlinks=False):
                            if recursive and entry.name not in exclude_dirs:
                                yield from _walk(Path(entry.path))

                        # 4. Обработка файлов
                        elif entry.is_file(follow_symlinks=False):
                            st = entry.stat(follow_symlinks=False)

                            # Пропускаем жесткие ссылки (если не ищем их специально)
                            if st.st_nlink > 1 and not include_links:
                                continue

                            # Фильтр по размеру
                            if st.st_size < min_size:
                                continue
                            if max_size is not None and st.st_size > max_size:
                                continue

                            # Фильтр по расширению
                            ext = os.path.splitext(entry.name)[1].lower()
                            if extensions and ext not in extensions:
                                continue

                            count += 1
                            if progress_cb and count % 500 == 0:
                                progress_cb(count)

                            yield Path(entry.path)

                    except (OSError, PermissionError) as e:
                        log.debug("Пропущен объект %s: %s", entry.name, e)
                        continue

        except (PermissionError, OSError) as e:
            log.warning("Нет доступа к директории %s: %s", directory, e)

    yield from _walk(root)
