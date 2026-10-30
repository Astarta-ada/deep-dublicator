"""Настройка тестового окружения (Pytest Fixtures)."""

import os
import sys
import pytest
from pathlib import Path
import logging

# Добавляем корень проекта в sys.path, чтобы импорты работали
sys.path.insert(0, str(Path(__file__).parent.parent))

# from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session", autouse=True)
def init_qapp():
    """Инициализирует QApplication для работы GUI-тестов."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def mock_log_action(mocker):
    """Отключает запись в реальную базу данных SQLite во время тестов."""
    return mocker.patch("core.file_ops.log_action")


@pytest.fixture
def sample_files(tmp_path):
    """
    Создает временную папку со структурой файлов для тестов.
    Возвращает путь к корневой папке.
    """
    # Создаем структуру:
    # tmp_path/
    #   ├── file1.txt (содержимое: "hello")
    #   ├── file2.txt (содержимое: "hello")
    #   ├── subdir/
    #   │   ├── file3.txt (содержимое: "hello")
    #   │   └── file4.txt (содержимое: "world")

    root = tmp_path / "test_root"
    root.mkdir()

    (root / "file1.txt").write_text("hello", encoding="utf-8")
    (root / "file2.txt").write_text("hello", encoding="utf-8")

    subdir = root / "subdir"
    subdir.mkdir()
    (subdir / "file3.txt").write_text("hello", encoding="utf-8")
    (subdir / "file4.txt").write_text("world", encoding="utf-8")

    return root


@pytest.fixture(autouse=True)
def restore_log_handlers():
    """
    Автоматически сохраняет и восстанавливает хендлеры корневого логгера,
    чтобы тесты не влияли на логирование друг друга.
    """
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level

    yield

    # Восстанавливаем состояние
    root.handlers = original_handlers
    root.setLevel(original_level)
