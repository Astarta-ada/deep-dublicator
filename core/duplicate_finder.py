import logging
import threading
import cv2
import imagehash
import mutagen
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, Callable, Optional
from PIL import Image
from core.hasher import hash_file
from core.hash_cache import HashCache, _NoCache
from utils.config import EMPTY_FILE_HASH, DEFAULT_HASH_WORKERS

log = logging.getLogger(__name__)
ProgressCb = Callable[[str, int, int], None]


def _hash_stage(
    files,
    cache,
    quick,
    workers,
    done_ref,
    total_ref,
    lock,
    progress_cb,
    stage_name,
):
    by_hash = defaultdict(list)

    def worker(path: Path):
        try:
            st = path.stat()
        except OSError:
            return path, None
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
    progress_cb=None,
    include_empty=False,
    use_cache=True,
    workers=4,
):
    by_size = defaultdict(list)
    for f in files:
        try:
            by_size[f.stat().st_size].append(f)
        except OSError:
            pass
    result = {}
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


def find_by_name(files: list[Path]) -> dict[str, list[Path]]:
    groups = defaultdict(list)
    for f in files:
        groups[f.name.lower()].append(f)
    return {k: v for k, v in groups.items() if len(v) > 1}


def find_similar_images(
    files: list[Path], threshold=8
) -> dict[str, list[Path]]:
    hashes = {}
    for f in files:
        if f.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
            continue
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
            if h1 - h2 <= threshold:
                group.append(p2)
                processed.add(p2)
        if len(group) > 1:
            groups[str(h1)] = group
    return groups


def find_similar_videos(
    files: list[Path], threshold=8
) -> dict[str, list[Path]]:
    hashes = {}
    for f in files:
        if f.suffix.lower() not in {".mp4", ".mkv", ".avi", ".mov"}:
            continue
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


def find_audio_duplicates(files: list[Path]) -> dict[str, list[Path]]:
    groups = {}
    for f in files:
        if f.suffix.lower() not in {".mp3", ".flac", ".m4a", ".ogg", ".wav"}:
            continue
        try:
            audio = mutagen.File(str(f), easy=True)
            if audio and "artist" in audio and "title" in audio:
                key = f"{audio['artist'][0]} - {audio['title'][0]}".lower()
                groups.setdefault(key, []).append(f)
        except Exception:
            continue
    return {k: v for k, v in groups.items() if len(v) > 1}


def find_zero_fill_files(files: list[Path]) -> dict[str, list[Path]]:
    zero_files = []
    for f in files:
        try:
            if f.stat().st_size < 1024 * 1024:
                continue
            with open(f, "rb") as fh:
                if all(b == 0 for b in fh.read(8192)):
                    zero_files.append(f)
        except OSError:
            continue
    return {"ZERO_FILL": zero_files} if len(zero_files) > 1 else {}


def find_links_to_file(
    target_file: Path, files: list[Path]
) -> dict[str, list[Path]]:
    """Ищет все символьные и жесткие ссылки, указывающие на target_file."""
    if not target_file.exists():
        return {}

    target_file = target_file.resolve()
    try:
        target_stat = target_file.stat()
        target_ino = target_stat.st_ino
        target_dev = target_stat.st_dev
    except OSError:
        return {}

    found_links = []

    for f in files:
        if f == target_file:
            continue

        try:
            # 1. Проверка на символьную ссылку
            if f.is_symlink():
                if f.resolve() == target_file:
                    found_links.append(f)
                continue

            # 2. Проверка на жесткую ссылку
            st = f.stat()
            if st.st_ino == target_ino and st.st_dev == target_dev:
                found_links.append(f)

        except OSError:
            continue

    # Если нашли хотя бы одну ссылку, группируем их с оригиналом
    if found_links:
        return {"LINKS": [target_file] + found_links}

    return {}
