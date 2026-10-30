"""Тесты для настройки логирования (utils/logging_setup.py)."""

import logging
import logging.handlers
import pytest
from pathlib import Path

from utils import logging_setup

# ==========================================
# Фикстуры
# ==========================================


@pytest.fixture
def mock_log_paths(mocker, tmp_path):
    """Перенаправляет пути логов во временную папку."""
    log_dir = tmp_path / "logs"
    log_file = log_dir / "app.log"

    # Подменяем константы в модуле логирования
    mocker.patch("utils.logging_setup.LOG_DIR", log_dir)
    mocker.patch("utils.logging_setup.LOG_FILE", log_file)

    return log_dir, log_file


# ==========================================
# 1. Тесты базовой настройки
# ==========================================


def test_setup_logging_creates_dir(mock_log_paths):
    """Проверяет, что папка для логов создается, если её нет."""
    log_dir, log_file = mock_log_paths
    assert not log_dir.exists()

    logging_setup.setup_logging()
    assert log_dir.exists()


def test_setup_logging_returns_root(mock_log_paths):
    """Проверяет, что функция возвращает корневой логгер."""
    root = logging_setup.setup_logging()
    assert root is logging.getLogger()
    assert root.level == logging.DEBUG


# ==========================================
# 2. Тесты обработчиков (Handlers)
# ==========================================


def test_setup_logging_handlers(mock_log_paths):
    """Проверяет, что добавлены правильные обработчики."""
    root = logging_setup.setup_logging()

    # Должно быть ровно 2 обработчика
    assert len(root.handlers) == 2

    # Один из них - RotatingFileHandler
    file_handlers = [
        h
        for h in root.handlers
        if isinstance(h, logging.handlers.RotatingFileHandler)
    ]
    assert len(file_handlers) == 1
    fh = file_handlers[0]
    assert fh.maxBytes == 2_000_000
    assert fh.backupCount == 5
    assert fh.level == logging.INFO  # Уровень по умолчанию
    assert fh.encoding == "utf-8"

    # Другой - StreamHandler
    stream_handlers = [
        h
        for h in root.handlers
        if isinstance(h, logging.StreamHandler)
        and not isinstance(h, logging.FileHandler)
    ]
    assert len(stream_handlers) == 1
    ch = stream_handlers[0]
    assert ch.level == logging.WARNING


def test_setup_logging_clears_old_handlers(mock_log_paths):
    """Проверяет, что при повторном вызове старые обработчики удаляются."""
    # Добавляем фейковый обработчик
    root = logging.getLogger()
    dummy_handler = logging.NullHandler()
    root.addHandler(dummy_handler)
    assert dummy_handler in root.handlers

    # Вызываем настройку
    root = logging_setup.setup_logging()

    # Фейковый обработчик должен быть удален
    assert dummy_handler not in root.handlers
    assert len(root.handlers) == 2


# ==========================================
# 3. Тесты приглушения библиотек
# ==========================================


def test_setup_logging_mutes_libraries(mock_log_paths):
    """Проверяет, что сторонние библиотеки приглушены до WARNING."""
    logging_setup.setup_logging()

    for lib in ("PIL", "PySide6", "urllib3", "apscheduler"):
        assert logging.getLogger(lib).level == logging.WARNING


# ==========================================
# 4. Тесты реальной записи в файл
# ==========================================


def test_setup_logging_writes_to_file(mock_log_paths):
    """Проверяет, что лог действительно записывается в файл."""
    log_dir, log_file = mock_log_paths

    logging_setup.setup_logging()

    # Пишем тестовое сообщение
    log = logging.getLogger("test_logger")
    log.info("Test log message")

    # Обязательно закрываем хэндлеры, чтобы данные сбросились на диск (flush)
    for h in logging.getLogger().handlers:
        h.flush()
        h.close()

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")

    assert "Test log message" in content
    assert "INFO" in content
    assert "test_logger" in content


def test_setup_logging_custom_level(mock_log_paths):
    """Проверяет, что можно передать кастомный уровень для файла."""
    root = logging_setup.setup_logging(level=logging.DEBUG)

    fh = [
        h
        for h in root.handlers
        if isinstance(h, logging.handlers.RotatingFileHandler)
    ][0]
    assert fh.level == logging.DEBUG
