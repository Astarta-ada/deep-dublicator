"""SQLite-кэш хешей файлов: (path, size, mtime) → hash."""

import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from utils.config import APP_DATA_DIR, HASH_CACHE_DB

log = logging.getLogger(__name__)


class HashCache:
    """Потокобезопасный кэш хешей."""

    _DDL = """
    CREATE TABLE IF NOT EXISTS hashes (
        path  TEXT NOT NULL,
        size  INTEGER NOT NULL,
        mtime REAL NOT NULL,
        hash  TEXT NOT NULL,
        PRIMARY KEY (path, size, mtime)
    );
    CREATE INDEX IF NOT EXISTS idx_hash ON hashes(hash);
    """

    def __init__(self, db_path: Path = HASH_CACHE_DB):
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.executescript(self._DDL)
        self._conn.commit()

    def get(self, path: Path, size: int, mtime: float) -> Optional[str]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT hash FROM hashes WHERE path=? AND size=? AND mtime=?",
                (str(path), size, mtime),
            )
            row = cur.fetchone()
            return row[0] if row else None

    def put(self, path: Path, size: int, mtime: float, hash_: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO hashes(path, size, mtime, hash) "
                "VALUES(?,?,?,?)",
                (str(path), size, mtime, hash_),
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass


class _NoCache:
    """Заглушка, когда кэш выключен."""

    def get(self, *a, **kw):
        return None

    def put(self, *a, **kw):
        pass

    def close(self):
        pass
