"""Кастомный обработчик логов для вывода в GUI."""

import logging
from PySide6.QtCore import QObject, Signal


class QtLogHandler(QObject, logging.Handler):
    """Перехватывает логи и отправляет их в интерфейс через сигнал."""

    log_signal = Signal(str)

    def __init__(self):
        QObject.__init__(self)
        logging.Handler.__init__(self)

    def emit(self, record):
        # Форматируем сообщение (например, "2023-10-25 12:00:00 | INFO | Модуль | Текст")
        msg = self.format(record)
        # Отправляем сигнал в GUI-поток
        self.log_signal.emit(msg)
