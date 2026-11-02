"""SQLite-кэш хешей файлов: (path, size, mtime) → hash."""

import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from utils.config import APP_DATA_DIR, HASH_CACHE_DB

log = logging.getLogger(__name__)


class HashCache:
    """Потокобезопасный кэш хешей на базе SQLite."""

    _DDL = """
    CREATE TABLE IF NOT EXISTS hashes (
        path  TEXT NOT NULL,
        size  INTEGER NOT NULL,
        mtime REAL NOT NULL,
        algorithm TEXT NOT NULL,
        hash  TEXT NOT NULL,
        PRIMARY KEY (path, size, mtime, algorithm)
    );
    CREATE INDEX IF NOT EXISTS idx_hash ON hashes(hash);
    """

    def __init__(self, db_path: Path = HASH_CACHE_DB):
        # Создаем папку для данных (data/), если её нет
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

        self._path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)

        with self._lock:
            # Проверяем структуру существующей таблицы
            try:
                cur = self._conn.execute("PRAGMA table_info(hashes)")
                columns = [row[1] for row in cur.fetchall()]

                # Если таблица существует, но в ней нет колонки 'algorithm' — она устарела
                if columns and "algorithm" not in columns:
                    log.warning(
                        "Обнаружена устаревшая структура кэша. Пересоздаем таблицу..."
                    )
                    self._conn.execute("DROP TABLE hashes")
                    columns = []  # Сбрасываем, чтобы создалась заново

                # Создаем таблицу, если её нет
                if not columns:
                    self._conn.executescript(self._DDL)
                    self._conn.commit()
            except sqlite3.Error as e:
                log.error("Ошибка инициализации кэша: %s", e)

    def get(
        self, path: Path, size: int, mtime: float, algorithm: str
    ):  # -> Optional[str]:
        """
        Возвращает сохраненный хеш, если файл не менялся.
        Если файла нет в кэше или он изменился, возвращает None.
        """
        with self._lock:
            cur = self._conn.execute(
                "SELECT hash FROM hashes WHERE path=? AND size=? AND mtime=? AND algorithm=?",
                (str(path), size, mtime, algorithm),
            )
            row = cur.fetchone()
            return row[0] if row else None

    def put(
        self, path: Path, size: int, mtime: float, algorithm: str, hash_: str
    ):  # -> None:
        """Сохраняет новый хеш в базу (перезаписывает, если такой ключ уже есть)."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO hashes(path, size, mtime, algorithm, hash) "
                "VALUES(?,?,?,?,?)",
                (str(path), size, mtime, algorithm, hash_),
            )
            self._conn.commit()

    def close(self):  # -> None:
        """Безопасно закрывает соединение с базой данных."""
        with self._lock:
            try:
                self._conn.close()
            except Exception as e:
                log.error("Ошибка при закрытии кэша хешей: %s", e)


class _NoCache:
    """Заглушка, когда кэш выключен."""

    def get(self, *a, **kw):
        return None

    def put(self, *a, **kw):
        pass

    def close(self):
        pass
