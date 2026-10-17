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


def _run_cli():
    from cli.cli import run

    return run(sys.argv[2:])


def _start_scheduler():
    scheduler = BackgroundScheduler()

    def check_schedule():
        enabled = _settings().value("schedule/enabled", False, type=bool)
        if enabled:
            path = _settings().value("schedule/path", "", type=str)
            if path and Path(path).is_dir():
                logging.getLogger("scheduler").info(
                    "Фоновое сканирование: %s", path
                )

    scheduler.add_job(check_schedule, "interval", hours=24)
    scheduler.start()
    return scheduler


def main():
    setup_logging()
    log = logging.getLogger(__name__)

    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        sys.exit(_run_cli())

    app = QApplication(sys.argv)
    app.setApplicationName("Duplicate Finder")
    app.setOrganizationName("DupFinder")

    ThemeManager.instance().apply_saved()
    scheduler = _start_scheduler()

    window = MainWindow()
    window.show()

    exit_code = app.exec()
    scheduler.shutdown()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
