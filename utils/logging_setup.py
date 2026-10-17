"""Настройка логирования: консоль + файл с ротацией."""

import logging
import logging.handlers

from utils.config import LOG_DIR, LOG_FILE


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """
    Инициализирует корневой логгер. Вызывать один раз при старте приложения.
    Пишет DEBUG+ в файл с ротацией и WARNING+ в консоль.
    """
    LOG_DIR.mkdir(exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)-24s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Файл с ротацией (5 бэкапов × 2 МБ)
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    fh.setLevel(level)
    fh.setFormatter(fmt)

    # Консоль — только важное
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)

    root.handlers.clear()
    root.addHandler(fh)
    root.addHandler(ch)

    # Приглушаем шумные библиотеки
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("PySide6").setLevel(logging.WARNING)

    log = logging.getLogger(__name__)
    log.info("Логирование инициализировано, файл: %s", LOG_FILE)
    return root
