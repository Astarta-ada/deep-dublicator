"""Сериализация результатов поиска в JSON-сессию.

Сессия — это структурированный снимок результатов сканирования:
группы дубликатов + выбранный оригинал в каждой группе.
Позволяет сохранить результаты и загрузить их позже или на другом ПК.
"""

import getpass
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from utils.config import SESSION_EXT, SESSION_VERSION

log = logging.getLogger(__name__)


@dataclass
class FileEntry:
    """Информация об одном файле в группе."""

    path: str
    size: int
    mtime: float
    is_original: bool = False
    is_empty: bool = False


@dataclass
class DuplicateGroup:
    """Группа одинаковых файлов."""

    hash_key: str
    size: int
    files: list[FileEntry]
    is_empty_group: bool = False


@dataclass
class Session:
    """Полная сессия сканирования."""

    version: int = SESSION_VERSION
    created_at: str = ""
    created_by: str = ""
    root_scan_dir: str = ""
    filters: dict = field(default_factory=dict)
    groups: list[DuplicateGroup] = field(default_factory=list)

    def to_dict(self):  # -> dict:
        """Преобразует сессию в словарь для JSON."""
        return {
            "version": self.version,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "root_scan_dir": self.root_scan_dir,
            "filters": self.filters,
            "groups": [
                {
                    "hash_key": g.hash_key,
                    "size": g.size,
                    "is_empty_group": g.is_empty_group,
                    "files": [asdict(f) for f in g.files],
                }
                for g in self.groups
            ],
        }

    @classmethod
    def from_dict(cls, data: dict):  # -> "Session":
        if data.get("version") != SESSION_VERSION:
            raise ValueError(
                f"Несовместимая версия сессии: {data.get('version')}, "
                f"ожидается {SESSION_VERSION}"
            )
        groups = [
            DuplicateGroup(
                hash_key=g["hash_key"],
                size=g["size"],
                is_empty_group=g.get("is_empty_group", False),
                files=[FileEntry(**f) for f in g["files"]],
            )
            for g in data.get("groups", [])
        ]
        return cls(
            version=data["version"],
            created_at=data.get("created_at", ""),
            created_by=data.get("created_by", ""),
            root_scan_dir=data.get("root_scan_dir", ""),
            filters=data.get("filters", {}),
            groups=groups,
        )


def save_session(session: Session, path: Path):  # -> None:
    """Сохраняет сессию в файл (добавляет .dupsession.json при необходимости)."""
    path = Path(path)
    if not str(path).endswith(SESSION_EXT):
        path = Path(str(path) + SESSION_EXT)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
    log.info("Сессия сохранена: %s (%d групп)", path, len(session.groups))


def load_session(path: Path):  # -> Session:
    """Загружает сессию из файла."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    session = Session.from_dict(data)
    log.info("Сессия загружена: %s (%d групп)", path, len(session.groups))
    return session


def build_session_from_groups(
    groups: dict[str, list[Path]],
    root_dir: str,
    filters: dict,
    empty_hash_keys: Optional[set[str]] = None,
    created_by: str = "",
):  # -> Session:
    """
    Собирает Session из результата find_duplicates() или из виджетов интерфейса.
    Первый путь в каждом списке считается выбранным оригиналом.
    """
    empty_hash_keys = empty_hash_keys or set()

    entries: list[DuplicateGroup] = []

    for h, paths in groups.items():
        files: list[FileEntry] = []
        for i, p in enumerate(paths):
            try:
                st = p.stat()
            except OSError:
                continue
            files.append(
                FileEntry(
                    path=str(p),
                    size=st.st_size,
                    mtime=st.st_mtime,
                    is_original=(i == 0),
                    is_empty=(st.st_size == 0),
                )
            )

        if not files:
            continue

        entries.append(
            DuplicateGroup(
                hash_key=h,
                size=files[0].size,
                files=files,
                is_empty_group=(h in empty_hash_keys),
            )
        )

    return Session(
        version=SESSION_VERSION,
        created_at=datetime.now().isoformat(timespec="seconds"),
        created_by=created_by or getpass.getuser(),
        root_scan_dir=root_dir,
        filters=filters,
        groups=entries,
    )
