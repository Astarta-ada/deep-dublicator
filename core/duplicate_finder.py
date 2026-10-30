"""Алгоритмы поиска дубликатов, похожих файлов и ссылок."""

import os
import logging
import threading
import imagehash
import mutagen

try:
    import cv2

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

from PIL import Image

from collections import defaultdict

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, Callable, Optional

from core.hasher import hash_file
from core.hash_cache import HashCache, _NoCache
from utils.config import EMPTY_FILE_HASH, DEFAULT_HASH_WORKERS
from utils.constants import (
    IMAGE_EXTS,
    HEIC_EXTS,
    RAW_EXTS,
    VIDEO_EXTS,
    AUDIO_EXTS,
)

log = logging.getLogger(__name__)

ProgressCb = Callable[[str, int, int], None]


# ==========================================
# Ядро: Поиск точных дубликатов по хешу
# =========================================


def _hash_stage(
    files: list[Path],
    cache,
    quick: bool,
    workers: int,
    done_ref: list[int],
    total_ref: list[int],
    lock: threading.Lock,
    progress_cb: Optional[ProgressCb],
    stage_name: str,
):
    by_hash: dict[str, list[Path]] = defaultdict(list)

    def worker(path: Path):
        try:
            st = path.stat()
        except OSError:  # pragma: no cover
            return path, None  # pragma: no cover

        # Проверка кэша (только для полного хеша)
        if not quick:
            cached = cache.get(path, st.st_size, st.st_mtime)
            if cached:
                with lock:
                    done_ref[0] += st.st_size
                    if progress_cb:
                        progress_cb(stage_name, done_ref[0], total_ref[0])
                return path, cached

        def on_chunk(n: int):
            with lock:
                done_ref[0] += n
                if progress_cb and done_ref[0] % (1 << 20) < n:
                    progress_cb(stage_name, done_ref[0], total_ref[0])

        h = hash_file(path, quick=quick, progress_cb=on_chunk)
        if h and not quick:
            cache.put(path, st.st_size, st.st_mtime, h)
        return path, h

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for fut in as_completed([pool.submit(worker, f) for f in files]):
            path, h = fut.result()
            if h:
                by_hash[h].append(path)
    return by_hash


def find_duplicates(
    files: Iterable[Path],
    progress_cb: Optional[ProgressCb] = None,
    include_empty: bool = False,
    use_cache: bool = True,
    workers: int = DEFAULT_HASH_WORKERS,
):  # -> dict[str, list[Path]]:
    """Трехступенчатый поиск точных дубликатов: размер → быстрый хеш → полный хеш."""
    by_size: dict[int, list[Path]] = defaultdict(list)
    for f in files:
        try:
            by_size[f.stat().st_size].append(f)
        except OSError:
            continue
    result: dict[str, list[Path]] = {}

    # Отдельная группа для пустых файлов
    if include_empty and 0 in by_size and len(by_size[0]) > 1:
        result[EMPTY_FILE_HASH] = list(by_size[0])
    by_size.pop(0, None)

    candidates = [f for g in by_size.values() if len(g) > 1 for f in g]
    if not candidates:
        return result

    cache = HashCache() if use_cache else _NoCache()
    lock = threading.Lock()
    done = [0]
    try:
        # Этап 1: Быстрый хеш
        total_q = sum(f.stat().st_size for f in candidates if f.exists())
        total_ref = [total_q]
        if progress_cb:
            progress_cb("quick_hash", 0, total_q)
        by_quick = _hash_stage(
            candidates,
            cache,
            True,
            workers,
            done,
            total_ref,
            lock,
            progress_cb,
            "quick_hash",
        )
        candidates = [f for g in by_quick.values() if len(g) > 1 for f in g]
        if not candidates:
            return result

        # Этап 2: Полный хеш
        done[0] = 0
        total_f = sum(f.stat().st_size for f in candidates if f.exists())
        total_ref[0] = total_f
        if progress_cb:
            progress_cb("full_hash", 0, total_f)
        by_full = _hash_stage(
            candidates,
            cache,
            False,
            workers,
            done,
            total_ref,
            lock,
            progress_cb,
            "full_hash",
        )
        for h, paths in by_full.items():
            if len(paths) > 1:
                result[h] = paths
    finally:
        cache.close()
    return result


# ==========================================
# Специализированные поиски (Фото, Видео, Аудио, Имена)
# ==========================================


def find_by_name(files: list[Path]):  # -> dict[str, list[Path]]:
    """Группирует файлы с одинаковыми именами."""
    groups = defaultdict(list)
    for f in files:
        groups[f.name.lower()].append(f)
    return {k: v for k, v in groups.items() if len(v) > 1}


def find_similar_images(
    files: list[Path], threshold: int = 8
):  # -> dict[str, list[Path]]:
    """Поиск визуально похожих изображений через Perceptual Hash."""
    valid_exts = IMAGE_EXTS | HEIC_EXTS | RAW_EXTS
    hashes = {}
    for f in files:
        if f.suffix.lower() not in valid_exts:
            continue  # pragma: no cover
        try:
            with Image.open(f) as img:
                hashes[f] = imagehash.phash(img)
        except Exception:
            continue
    groups, processed = {}, set()
    for p1, h1 in hashes.items():
        if p1 in processed:
            continue
        group = [p1]
        processed.add(p1)
        for p2, h2 in hashes.items():
            if p2 in processed:
                continue
            if h1 - h2 <= threshold:  # Расстояние Хэмминга
                group.append(p2)
                processed.add(p2)
        if len(group) > 1:
            groups[str(h1)] = group
    return groups


def find_similar_videos(
    files: list[Path], threshold: int = 8
):  # -> dict[str, list[Path]]:
    """Поиск похожих видео по первому кадру (требует OpenCV)."""

    if not HAS_CV2:
        log.warning("OpenCV не установлен, поиск видео невозможен")
        return {}

    hashes = {}
    for f in files:
        if f.suffix.lower() not in VIDEO_EXTS:
            continue  # pragma: no cover
        try:
            cap = cv2.VideoCapture(str(f))
            ret, frame = cap.read()
            cap.release()
            if ret:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                hashes[f] = imagehash.phash(Image.fromarray(rgb))
        except Exception:
            continue
    groups, processed = {}, set()
    for p1, h1 in hashes.items():
        if p1 in processed:
            continue
        group = [p1]
        processed.add(p1)
        for p2, h2 in hashes.items():
            if p2 in processed:
                continue
            if h1 - h2 <= threshold:
                group.append(p2)
                processed.add(p2)
        if len(group) > 1:
            groups[str(h1)] = group
    return groups


def find_audio_duplicates(files: list[Path]):  # -> dict[str, list[Path]]:
    """Поиск аудио с одинаковыми ID3-тегами (Исполнитель - Название)."""

    groups = {}
    for f in files:
        if f.suffix.lower() not in AUDIO_EXTS:
            continue
        try:
            audio = mutagen.File(str(f), easy=True)
            if audio and "artist" in audio and "title" in audio:
                key = f"{audio['artist'][0]} - {audio['title'][0]}".lower()
                groups.setdefault(key, []).append(f)
        except Exception:
            continue
    return {k: v for k, v in groups.items() if len(v) > 1}


def find_zero_fill_files(files: list[Path]):  # -> dict[str, list[Path]]:
    """Поиск мусорных файлов, забитых нулями (от 1 МБ)."""
    zero_files = []
    for f in files:
        try:
            if f.stat().st_size < 1024 * 1024:
                continue  # pragma: no cover
            with open(f, "rb") as fh:
                if all(b == 0 for b in fh.read(8192)):
                    zero_files.append(f)
        except OSError:
            continue
    return {"ZERO_FILL": zero_files} if len(zero_files) > 1 else {}


# ==========================================
# Поиск ссылок (Симлинки и Хардлинки)
# ==========================================


def find_links_to_file(
    target_file: Path, files: list[Path]
):  # -> dict[str, list[Path]]:
    """
    Ищет все символьные и жесткие ссылки, указывающие на target_file.
    Использует кроссплатформенный os.path.samefile.
    """
    if not target_file.exists():
        return {}

    found_links = []

    for f in files:
        if f == target_file:
            continue  # pragma: no cover

        try:
            if os.path.samefile(f, target_file):
                found_links.append(f)
        except (OSError, FileNotFoundError):
            continue

    # Если нашли хотя бы одну ссылку, группируем их с оригиналом
    if found_links:
        return {"LINKS": [target_file] + found_links}

    return {}
