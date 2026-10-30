"""Тесты для обработчика логов GUI (gui/log_handler.py)."""

import logging
import pytest
from gui.log_handler import QtLogHandler

# ==========================================
# 1. Тесты инициализации
# ==========================================


def test_qt_log_handler_init():
    """Проверяет, что обработчик корректно инициализируется."""
    handler = QtLogHandler()

    # Проверяем, что он является наследником logging.Handler
    assert isinstance(handler, logging.Handler)

    # Проверяем, что у него есть сигнал
    assert hasattr(handler, "log_signal")

    # По умолчанию уровень логгера должен быть NOTSET (0)
    assert handler.level == logging.NOTSET


# ==========================================
# 2. Тесты метода emit
# ==========================================


def test_qt_log_handler_emit_direct(mocker):
    """Проверяет прямой вызов emit с кастомным форматтером."""
    handler = QtLogHandler()

    # Подключаем мок к сигналу
    mock_slot = mocker.MagicMock()
    handler.log_signal.connect(mock_slot)

    # Устанавливаем форматтер
    formatter = logging.Formatter("%(levelname)s | %(message)s")
    handler.setFormatter(formatter)

    # Создаем фейковую запись лога
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message",
        args=(),
        exc_info=None,
    )

    # Вызываем emit напрямую
    handler.emit(record)

    # Проверяем, что сигнал получил отформатированную строку
    mock_slot.assert_called_once_with("INFO | Test message")


def test_qt_log_handler_emit_default_format(mocker):
    """Проверяет emit без установленного форматтера (должен вернуть только сообщение)."""
    handler = QtLogHandler()

    mock_slot = mocker.MagicMock()
    handler.log_signal.connect(mock_slot)

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Default message",
        args=(),
        exc_info=None,
    )

    handler.emit(record)

    # По умолчанию logging.Handler форматирует как record.getMessage()
    mock_slot.assert_called_once_with("Default message")


# ==========================================
# 3. Интеграционный тест (с реальным логгером)
# ==========================================


def test_qt_log_handler_integration(mocker):
    """Проверяет, что обработчик перехватывает логи из стандартного логгера."""
    handler = QtLogHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    mock_slot = mocker.MagicMock()
    handler.log_signal.connect(mock_slot)

    # Создаем логгер и добавляем наш обработчик
    logger = logging.getLogger("test_integration_logger")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    try:
        # Отправляем лог
        logger.info("Integration test message")

        # Проверяем, что сигнал сработал
        mock_slot.assert_called_once_with("Integration test message")
    finally:
        # Обязательно удаляем обработчик, чтобы он не мешал другим тестам
        logger.removeHandler(handler)
