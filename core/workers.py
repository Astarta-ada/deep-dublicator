"""Фоновые потоки (воркеры) для приложения."""

import os
import time
import logging
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import QThread, Signal, QStandardPaths

from core.scanner import scan_directory
from core.duplicate_finder import (
    find_duplicates,
    find_similar_images,
    find_similar_videos,
    find_audio_duplicates,
    find_zero_fill_files,
    find_by_name,
    find_links_to_file,
)
from core.file_ops import apply_action_to_group, rename_duplicates
from utils.config import DEFAULT_HASH_WORKERS
from utils.helpers import get_dir_stats, format_date

log = logging.getLogger(__name__)


class ScanWorker(QThread):
    """Фоновый поток для поиска дубликатов (с поддержкой ETA)."""

    progress_msg = Signal(str)
    progress_bytes = Signal(str, int, int, float)  # stage, done, total, eta
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        root,
        recursive,
        min_size,
        max_size,
        extensions,
        include_empty,
        use_cache,
        mode,
        globs,
        phash,
        target_file=None,
    ):
        super().__init__()
        self.root = root
        self.recursive = recursive
        self.min_size = min_size
        self.max_size = max_size
        self.extensions = extensions
        self.include_empty = include_empty
        self.use_cache = use_cache
        self.mode = mode
        self.globs = globs
        self.phash = phash
        self.target_file = Path(target_file) if target_file else None

    def run(self):
        try:
            self.progress_msg.emit("Сканирование директории…")
            is_links = self.mode == "links"

            files = list(
                scan_directory(
                    self.root,
                    self.recursive,
                    self.min_size,
                    self.max_size,
                    self.extensions,
                    exclude_globs=self.globs,
                    include_links=is_links,
                )
            )
            self.progress_msg.emit(f"Найдено {len(files)} файлов. Анализ…")

            start = time.time()

            def cb(stage, done, total):
                el = time.time() - start
                speed = done / el if el > 0 else 0
                eta = (total - done) / speed if speed > 0 else 0
                self.progress_bytes.emit(stage, done, total, eta)

            if self.mode == "strict":
                res = find_duplicates(
                    files,
                    cb,
                    self.include_empty,
                    self.use_cache,
                    DEFAULT_HASH_WORKERS,
                )
            elif self.mode == "similar_img":
                res = find_similar_images(files, self.phash)
            elif self.mode == "similar_vid":
                res = find_similar_videos(files, self.phash)
            elif self.mode == "audio":
                res = find_audio_duplicates(files)
            elif self.mode == "name":
                res = find_by_name(files)
            elif self.mode == "zero":
                res = find_zero_fill_files(files)
            elif self.mode == "links":
                if not self.target_file or not self.target_file.exists():
                    raise ValueError(
                        "Целевой файл не выбран или не существует"
                    )
                self.progress_msg.emit("Поиск ссылок…")
                res = find_links_to_file(self.target_file, files)
            else:
                res = {}

            self.finished_ok.emit(res)
        except Exception as e:
            log.exception("Ошибка сканирования")
            self.failed.emit(str(e))


class ApplyWorker(QThread):
    """Фоновый поток для удаления/замены файлов, чтобы интерфейс не зависал."""

    progress = Signal(int, int)
    finished_ok = Signal(int, list)

    def __init__(self, groups, action, backup_dir, base_root, dry_run):
        super().__init__()
        self.groups = groups
        self.action = action
        self.backup_dir = backup_dir
        self.base_root = base_root
        self.dry_run = dry_run

    def run(self):
        total_ok = 0
        all_errors = []
        total_targets = sum(g.selected_count() for g in self.groups)
        processed = 0

        for g in list(self.groups):
            o, targets = g.get_selection()
            if not targets:
                continue

            if self.action == "rename":
                a, b = rename_duplicates(o, targets, self.dry_run)
            else:
                a, b = apply_action_to_group(
                    o,
                    targets,
                    self.action,
                    self.backup_dir,
                    self.base_root,
                    self.dry_run,
                )

            total_ok += a
            all_errors.extend(b)
            processed += len(targets)
            self.progress.emit(processed, total_targets)

        self.finished_ok.emit(total_ok, all_errors)


class FolderScannerWorker(QThread):
    """Воркер для анализа диска (ленивая загрузка веток дерева)."""

    finished_ok = Signal(list)
    progress = Signal(str)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        results = []
        try:
            with os.scandir(self.path) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            self.progress.emit(f"Сканирование: {e.name}...")

                            s, c = get_dir_stats(e.path)
                            results.append(
                                {
                                    "name": e.name,
                                    "path": e.path,
                                    "size": s,
                                    "files": c,
                                    "is_dir": True,
                                    "error": None,
                                }
                            )
                        elif e.is_file(follow_symlinks=False):
                            st = e.stat()
                            results.append(
                                {
                                    "name": e.name,
                                    "path": e.path,
                                    "size": st.st_size,
                                    "files": 1,
                                    "is_dir": False,
                                    "error": None,
                                    "mtime": st.st_mtime,
                                }
                            )
                    except PermissionError:
                        results.append(
                            {
                                "name": e.name,
                                "path": e.path,
                                "size": 0,
                                "files": 0,
                                "is_dir": True,
                                "error": "Доступ закрыт",
                            }
                        )
        except Exception:
            pass
        results.sort(key=lambda x: x["size"], reverse=True)
        self.finished_ok.emit(results)


class HogsScanner(QThread):
    """Воркер для поиска больших файлов."""

    finished_ok = Signal(list)

    def __init__(self, root, min_size, older_than_days):
        super().__init__()
        self.root = root
        self.min_size = min_size
        self.older_than_days = older_than_days

    def run(self):
        results = []
        now = datetime.now().timestamp()
        for dirpath, _, filenames in os.walk(self.root):
            for f in filenames:
                try:
                    p = Path(dirpath) / f
                    st = p.stat()
                    if st.st_size >= self.min_size:
                        if self.older_than_days > 0:
                            days_old = (now - st.st_mtime) / (24 * 3600)
                            if days_old < self.older_than_days:
                                continue
                        results.append(
                            (
                                str(p),
                                st.st_size,
                                format_date(st.st_mtime),
                            )
                        )
                except OSError:
                    pass
        results.sort(key=lambda x: x[1], reverse=True)
        self.finished_ok.emit(results)


class JunkScanner(QThread):
    """Воркер для поиска системного мусора и кэшей (кроссплатформенный)."""

    finished_ok = Signal(list)

    def __init__(self, root):
        super().__init__()
        self.root = root

    def run(self):
        results = []

        # Получаем системные пути кэшей (работает на Windows, Linux, Mac)
        local = QStandardPaths.writableLocation(
            QStandardPaths.GenericCacheLocation
        )
        temp = QStandardPaths.writableLocation(QStandardPaths.TempLocation)

        caches = {
            "Temp Files": temp,
            "Chrome Cache": os.path.join(local, "Google", "Chrome"),
            "Edge Cache": os.path.join(local, "Microsoft", "Edge"),
            "Mozilla Cache": os.path.join(local, "Mozilla", "Firefox"),
        }

        for name, path in caches.items():
            if path and os.path.exists(path):
                size, _ = get_dir_stats(Path(path))
                if size > 0:
                    results.append((name, path, size))

        # Мусор в выбранной папке
        cache_size, node_size = 0, 0
        cache_paths, node_paths = [], []

        if self.root and os.path.isdir(self.root):
            for dirpath, dirnames, filenames in os.walk(self.root):
                if "__pycache__" in dirnames:
                    p = os.path.join(dirpath, "__pycache__")
                    s, _ = get_dir_stats(Path(p))
                    cache_size += s
                    cache_paths.append(p)
                    dirnames.remove("__pycache__")

                if "node_modules" in dirnames:
                    p = os.path.join(dirpath, "node_modules")
                    s, _ = get_dir_stats(Path(p))
                    node_size += s
                    node_paths.append(p)
                    dirnames.remove("node_modules")

        if cache_size > 0:
            results.append(
                ("Python Cache", "\n".join(cache_paths), cache_size)
            )
        if node_size > 0:
            results.append(("Node.js", "\n".join(node_paths), node_size))

        self.finished_ok.emit(results)
