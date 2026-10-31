"""Журнал операций (история действий) на базе SQLite."""

import contextlib
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from utils.config import APP_DATA_DIR

log = logging.getLogger(__name__)

# Путь к базе данных истории
DB_PATH = APP_DATA_DIR / "history.db"


def init_db():  # -> None:
    """Создает папку и таблицу для истории, если их еще нет."""
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with contextlib.closing(sqlite3.connect(DB_PATH)) as conn:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    path TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    meta TEXT DEFAULT NULL,
                    is_undone INTEGER DEFAULT 0
                )
            """)
            # Миграции для старых баз (если колонок еще нет)
            try:
                conn.execute(
                    "ALTER TABLE actions ADD COLUMN meta TEXT DEFAULT NULL"
                )
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute(
                    "ALTER TABLE actions ADD COLUMN is_undone INTEGER DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass


def log_action(
    action: str, path: str, size: int, meta: str = None
):  # -> None:
    """
    Записывает действие в историю.

    :param action: Тип действия ('delete_hard', 'delete_trash', 'symlink', 'hardlink', 'rename', 'backup').
    :param path: Путь к файлу/папке.
    :param size: Размер файла в байтах (для статистики).
    """

    init_db()

    try:
        # Используем контекстный менеджер (with) — он автоматически делает commit и закрывает соединение
        with contextlib.closing(sqlite3.connect(DB_PATH)) as conn:
            with conn:
                conn.execute(
                    "INSERT INTO actions (timestamp, action, path, size, meta) VALUES (?, ?, ?, ?, ?)",
                    (
                        datetime.now().isoformat(timespec="seconds"),
                        action,
                        path,
                        size,
                        meta,
                    ),
                )
                conn.commit()
    except sqlite3.Error as e:
        # Если база заблокирована или возникла ошибка, мы просто пишем в лог,
        # но НЕ прерываем удаление файла.
        log.error("Не удалось записать действие в историю: %s", e)


def get_history():  # -> list[tuple[str, str, str, int]]:
    """
    Возвращает последние 500 записей из истории.
    Формат: (timestamp, action, path, size).
    """
    init_db()

    try:
        with contextlib.closing(sqlite3.connect(DB_PATH)) as conn:
            cursor = conn.execute(
                "SELECT id, timestamp, action, path, size, meta, is_undone "
                "FROM actions ORDER BY id DESC LIMIT 500"
            )
            return cursor.fetchall()
    except sqlite3.Error as e:
        log.error("Не удалось прочитать историю: %s", e)
        return []


def mark_as_undone(action_id: int):
    """Помечает действие как отмененное."""
    try:
        with contextlib.closing(sqlite3.connect(DB_PATH)) as conn:
            with conn:
                conn.execute(
                    "UPDATE actions SET is_undone = 1 WHERE id = ?",
                    (action_id,),
                )
    except sqlite3.Error as e:
        log.error("Не удалось обновить статус действия: %s", e)
