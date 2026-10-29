"""Журнал операций (история действий) на базе SQLite."""

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

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                path TEXT NOT NULL,
                size INTEGER NOT NULL
            )
        """)
        conn.commit()


def log_action(action: str, path: str, size: int):  # -> None:
    """
    Записывает действие в историю.

    :param action: Тип действия ('delete_hard', 'delete_trash', 'symlink', 'hardlink', 'rename', 'backup').
    :param path: Путь к файлу/папке.
    :param size: Размер файла в байтах (для статистики).
    """

    init_db()

    try:
        # Используем контекстный менеджер (with) — он автоматически делает commit и закрывает соединение
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO actions (timestamp, action, path, size) VALUES (?, ?, ?, ?)",
                (
                    datetime.now().isoformat(timespec="seconds"),
                    action,
                    path,
                    size,
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
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT timestamp, action, path, size "
                "FROM actions ORDER BY id DESC LIMIT 500"
            )
            return cursor.fetchall()
    except sqlite3.Error as e:
        log.error("Не удалось прочитать историю: %s", e)
        return []
