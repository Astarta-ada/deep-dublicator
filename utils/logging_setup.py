"""Настройка логирования: консоль + файл с ротацией."""

import logging
import logging.handlers

from utils.config import LOG_DIR, LOG_FILE


def setup_logging(level: int = logging.INFO):  # -> logging.Logger:
    """
    Инициализирует корневой логгер.
    Вызывать один раз при старте приложения (в main.py).

    :param level: Минимальный уровень логирования для файла.
    """

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # Пропускаем все уровни в корневой логгер

    # Формат логов: Дата | Уровень | Имя модуля | Сообщение
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)-24s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Файловый хэндлер с ротацией (5 файлов по 2 МБ)
    # Если лог превысит 2 МБ, он переименуется в app.log.1,
    # а старые будут удаляться.

    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    fh.setLevel(level)
    fh.setFormatter(fmt)

    # Консольный хэндлер (выводим только WARNING и выше, чтобы не спамить)
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)

    # Очищаем старые хэндлеры (на случай повторного вызова)
    root.handlers.clear()
    root.addHandler(fh)
    root.addHandler(ch)

    # Приглушаем слишком болтливые сторонние библиотеки
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("PySide6").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    log = logging.getLogger(__name__)
    log.info("Логирование инициализировано, файл: %s", LOG_FILE)
    return root
