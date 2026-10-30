"""Тесты для журнала операций (utils/history.py)."""

import sqlite3
import pytest
from pathlib import Path
from datetime import datetime

from utils import history

# ==========================================
# Фикстуры
# ==========================================


@pytest.fixture
def mock_db_path(tmp_path, mocker):
    """Перенаправляет БД истории во временную папку, чтобы не трогать реальные данные."""
    db_file = tmp_path / "test_history.db"
    mocker.patch("utils.history.DB_PATH", db_file)
    mocker.patch("utils.history.APP_DATA_DIR", tmp_path)
    return db_file


# ==========================================
# 1. Тесты init_db
# ==========================================


def test_init_db(mock_db_path):
    """Проверяет, что база данных и таблица создаются."""
    history.init_db()

    assert mock_db_path.exists()

    # ИСПРАВЛЕНО: явно закрываем соединение после проверки
    conn = sqlite3.connect(mock_db_path)
    try:
        cursor = conn.execute("PRAGMA table_info(actions)")
        columns = [row[1] for row in cursor.fetchall()]
    finally:
        conn.close()

    assert "id" in columns
    assert "timestamp" in columns
    assert "action" in columns
    assert "path" in columns
    assert "size" in columns


# ==========================================
# 2. Тесты log_action
# ==========================================


def test_log_action_success(mock_db_path):
    """Проверяет успешную запись действия в историю."""
    history.log_action("delete_hard", "C:/file.txt", 1024)

    # ИСПРАВЛЕНО: явно закрываем соединение после проверки
    conn = sqlite3.connect(mock_db_path)
    try:
        cursor = conn.execute("SELECT action, path, size FROM actions")
        row = cursor.fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] == "delete_hard"
    assert row[1] == "C:/file.txt"
    assert row[2] == 1024


def test_log_action_sqlite_error(mock_db_path, mocker):
    """Проверяет обработку ошибки БД при записи (база заблокирована)."""
    # ИСПРАВЛЕНО: Мокаем init_db, чтобы ошибка возникла именно в блоке try
    mocker.patch("utils.history.init_db")

    # Имитируем ошибку при подключении к БД
    mocker.patch(
        "sqlite3.connect", side_effect=sqlite3.Error("Database is locked")
    )
    mock_log = mocker.patch("utils.history.log.error")

    # Вызов не должен выбросить исключение
    history.log_action("delete_hard", "C:/file.txt", 1024)

    assert mock_log.called
    assert "Database is locked" in str(mock_log.call_args)


# ==========================================
# 3. Тесты get_history
# ==========================================


def test_get_history_success(mock_db_path):
    """Проверяет чтение истории и порядок записей (сначала новые)."""
    # Записываем три действия
    history.log_action("action1", "path1", 10)
    history.log_action("action2", "path2", 20)
    history.log_action("action3", "path3", 30)

    records = history.get_history()

    assert len(records) == 3

    # Проверяем, что последняя запись идет первой (DESC)
    assert records[0][1] == "action3"
    assert records[1][1] == "action2"
    assert records[2][1] == "action1"

    # Проверяем формат (timestamp, action, path, size)
    assert len(records[0]) == 4
    assert isinstance(records[0][0], str)  # timestamp


def test_get_history_sqlite_error(mock_db_path, mocker):
    """Проверяет обработку ошибки БД при чтении."""
    # ИСПРАВЛЕНО: Мокаем init_db
    mocker.patch("utils.history.init_db")

    mocker.patch("sqlite3.connect", side_effect=sqlite3.Error("Read error"))
    mock_log = mocker.patch("utils.history.log.error")

    records = history.get_history()

    # При ошибке должен вернуться пустой список, а не падение
    assert records == []
    assert mock_log.called
    assert "Read error" in str(mock_log.call_args)
