"""Точка входа в приложение Deep Dublicator."""

import sys
import logging
from pathlib import Path
import datetime

from PySide6.QtWidgets import QApplication
from apscheduler.schedulers.background import BackgroundScheduler

from utils.logging_setup import setup_logging
from utils.settings import _settings
from gui.main_window import MainWindow
from gui.theme_manager import ThemeManager
from utils.config import APP_NAME, ORG_NAME


def _run_cli():
    """Запуск в режиме командной строки (без GUI)."""
    from cli.cli import run

    return run(sys.argv[2:])


def _start_scheduler():
    """
    Инициализация фонового планировщика.
    В будущем здесь можно реализовать запуск сканирования по расписанию.
    """

    scheduler = BackgroundScheduler()

    def check_schedule():
        """Проверяет настройки и запускает фоновое сканирование."""
        enabled = _settings().value("schedule/enabled", False, type=bool)
        if enabled:
            path = _settings().value("schedule/path", "", type=str)
            if path and Path(path).is_dir():
                log = logging.getLogger("scheduler")
                log.info(
                    "[%s] Запущено фоновое сканирование папки: %s",
                    datetime.datetime.now().strftime("%H:%M"),
                    path,
                )
                # Реализовать вызов логики сканирования без GUI

    # Проверяем расписание каждый час
    scheduler.add_job(check_schedule, "interval", hours=24)
    scheduler.start()
    return scheduler


def main():
    """Главная функция запуска."""

    # Инициализация логирования
    setup_logging()
    log = logging.getLogger(__name__)

    # Проверка аргументов командной строки
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        log.info("=== Запуск в режиме CLI ===")
        sys.exit(_run_cli())

    # Запуск графического интерфейса
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)

    # Применяем сохраненную тему оформления
    ThemeManager.instance().apply_saved()

    # Запускаем фоновый планировщик
    scheduler = _start_scheduler()

    # Создаем и показываем главное окно
    window = MainWindow()
    window.show()

    # Запускаем цикл обработки событий Qt
    exit_code = app.exec()

    # Корректное завершение
    log.info("=== Завершение работы приложения (код %d) ===", exit_code)
    scheduler.shutdown()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
