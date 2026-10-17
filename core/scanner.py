import fnmatch
import logging
from pathlib import Path
from typing import Iterable, Callable, Optional
from utils.config import DEFAULT_EXCLUDE_DIRS

log = logging.getLogger(__name__)


def normalize_extensions(raw: str) -> set[str]:
    if not raw or not raw.strip():
        return set()
    return {
        f".{p.strip().lstrip('.').lower()}"
        for p in raw.replace(";", ",").split(",")
        if p.strip()
    }


def scan_directory(
    root: Path,
    recursive=True,
    min_size=1,
    max_size=None,
    extensions=None,
    exclude_dirs=None,
    exclude_globs=None,
    progress_cb=None,
    include_links=False,
):
    exclude_dirs = exclude_dirs or DEFAULT_EXCLUDE_DIRS
    exclude_globs = exclude_globs or []
    count = 0

    def _walk(directory: Path):
        nonlocal count
        try:
            entries = list(directory.iterdir())
        except (PermissionError, OSError):
            return

        for entry in entries:
            try:
                if any(
                    fnmatch.fnmatch(entry.name, pat) for pat in exclude_globs
                ):
                    continue
                if entry.is_symlink():
                    # Если ищем ссылки, симлинки тоже нужно собирать
                    if include_links:
                        yield entry
                    continue
                if entry.is_dir():
                    if recursive and entry.name not in exclude_dirs:
                        yield from _walk(entry)
                elif entry.is_file():
                    try:
                        st = entry.stat()
                    except OSError:
                        continue

                    # Пропускаем хардлинки, ТОЛЬКО если мы не ищем ссылки
                    if st.st_nlink > 1 and not include_links:
                        continue

                    size = entry.stat().st_size
                    if size < min_size:
                        continue
                    if max_size is not None and size > max_size:
                        continue
                    if extensions and entry.suffix.lower() not in extensions:
                        continue
                    count += 1
                    if progress_cb and count % 500 == 0:
                        progress_cb(count)
                    yield entry
            except (OSError, PermissionError):
                continue

    yield from _walk(root)
