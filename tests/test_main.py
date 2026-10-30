"""Тесты для точки входа (main.py)."""

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock

import main
from main import _run_cli, _start_scheduler, main as main_func

# ==========================================
# 1. Тесты _run_cli
# ==========================================


def test_run_cli(mocker):
    """Проверяет передачу аргументов в CLI-режим."""
    # Мокаем саму функцию run из cli.cli
    mock_run = mocker.patch("cli.cli.run", return_value=0)

    # Имитируем аргументы командной строки: main.py --cli C:/test
    mocker.patch.object(sys, "argv", ["main.py", "--cli", "C:/test"])

    result = _run_cli()

    assert result == 0
    # Проверяем, что в run передались только аргументы после --cli
    mock_run.assert_called_once_with(["C:/test"])


# ==========================================
# 2. Тесты _start_scheduler
# ==========================================


def test_start_scheduler(mocker):
    """Проверяет инициализацию фонового планировщика и работу check_schedule."""
    # Мокаем BackgroundScheduler
    mock_scheduler_class = mocker.patch("main.BackgroundScheduler")
    mock_scheduler = mock_scheduler_class.return_value

    # Мокаем настройки
    mock_settings = mocker.patch("main._settings")

    # Запускаем функцию
    scheduler = _start_scheduler()

    assert scheduler is mock_scheduler
    assert mock_scheduler.start.called

    # Извлекаем внутреннюю функцию check_schedule, которую передали в add_job
    check_schedule_func = mock_scheduler.add_job.call_args[0][0]

    # --- Тестируем check_schedule ---
    mock_log = mocker.patch("logging.getLogger")

    # Сценарий 1: Расписание выключено
    mock_settings.return_value.value.return_value = False
    check_schedule_func()
    assert not mock_log.return_value.info.called

    # Сценарий 2: Расписание включено, но путь невалидный
    def mock_value(key, default, type=None):
        if key == "schedule/enabled":
            return True
        if key == "schedule/path":
            return "C:/ghost"
        return default

    mock_settings.return_value.value.side_effect = mock_value
    mocker.patch("pathlib.Path.is_dir", return_value=False)

    check_schedule_func()
    assert not mock_log.return_value.info.called

    # Сценарий 3: Расписание включено, путь валидный
    mocker.patch("pathlib.Path.is_dir", return_value=True)
    check_schedule_func()
    assert mock_log.return_value.info.called


# ==========================================
# 3. Тесты main() — CLI режим
# ==========================================


def test_main_cli_mode(mocker):
    """Проверяет запуск приложения в режиме CLI."""
    # Имитируем аргументы
    mocker.patch.object(sys, "argv", ["main.py", "--cli", "C:/test"])

    # Мокаем зависимости
    mocker.patch("main.setup_logging")
    mock_run_cli = mocker.patch("main._run_cli", return_value=1)

    # QApplication не должен создаваться
    mock_app = mocker.patch("main.QApplication")

    # Перехватываем sys.exit
    with pytest.raises(SystemExit) as excinfo:
        main_func()

    # Проверяем, что sys.exit был вызван с кодом 1 (из _run_cli)
    assert excinfo.value.code == 1
    mock_run_cli.assert_called_once()
    assert not mock_app.called


# ==========================================
# 4. Тесты main() — GUI режим
# ==========================================


def test_main_gui_mode(mocker):
    """Проверяет запуск графического интерфейса."""
    # Имитируем аргументы без --cli
    mocker.patch.object(sys, "argv", ["main.py"])

    # Мокаем всё, что связано с GUI
    mocker.patch("main.setup_logging")

    mock_app = mocker.patch("main.QApplication")
    mock_app.return_value.exec.return_value = (
        0  # Эмулируем успешное закрытие окна
    )

    mock_theme = mocker.patch("main.ThemeManager")
    mock_scheduler = mocker.patch("main._start_scheduler")
    mock_window = mocker.patch("main.MainWindow")

    # Перехватываем sys.exit
    with pytest.raises(SystemExit) as excinfo:
        main_func()

    # Проверяем, что sys.exit был вызван с кодом 0 (из app.exec)
    assert excinfo.value.code == 0

    # Проверяем, что все компоненты были инициализированы
    assert mock_app.called
    mock_theme.instance.return_value.apply_saved.assert_called_once()
    mock_scheduler.assert_called_once()
    mock_window.return_value.show.assert_called_once()
    mock_scheduler.return_value.shutdown.assert_called_once()
