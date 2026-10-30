"""Тесты для главного окна (gui/main_window.py)."""

import logging
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtCore import Signal, QObject
from PySide6.QtWidgets import (
    QMessageBox,
    QSystemTrayIcon,
    QListWidget,
    QStackedWidget,
    QWidget,
)
from PySide6.QtGui import QCloseEvent

from gui.main_window import MainWindow
from utils.config import APP_NAME

# ==========================================
# Вспомогательный класс-пустышка
# ==========================================


class DummyTab(QWidget):
    """Реальный QWidget с сигналами и моками для тестов."""

    # Сигнал, который MainWindow пытается подключить
    find_duplicates_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.path_edit = MagicMock()
        self.mode_combo = MagicMock()
        self.table = MagicMock()
        self.table.horizontalHeader.return_value.saveState.return_value = (
            b"state"
        )
        self.restore_autosave = MagicMock()
        self.append_log = MagicMock()

    # Эмуляция метода, если вдруг понадобится
    def setCurrentIndex(self, index):
        pass


# ==========================================
# Фикстуры
# ==========================================


@pytest.fixture
def mock_main_window(mocker):
    """Создает MainWindow со всеми замоканными зависимостями."""
    mocker.patch("gui.main_window.ScanTab", side_effect=DummyTab)
    mocker.patch("gui.main_window.DiskAnalysisTab", side_effect=DummyTab)
    mocker.patch("gui.main_window.SpaceHogsTab", side_effect=DummyTab)
    mocker.patch("gui.main_window.JunkCleanerTab", side_effect=DummyTab)
    mocker.patch("gui.main_window.LogsTab", side_effect=DummyTab)
    mocker.patch("logging.Logger.addHandler")

    mock_settings = mocker.patch("gui.main_window.QSettings")
    mock_settings.return_value.value.return_value = None

    mock_tray = mocker.patch("gui.main_window.QSystemTrayIcon")
    mock_tray.return_value.isSystemTrayAvailable.return_value = True

    mocker.patch("gui.main_window.QtLogHandler")

    mock_tm = mocker.patch("gui.main_window.ThemeManager")
    mock_tm.instance.return_value.available.return_value = {
        "dark": "Тёмная",
        "light": "Светлая",
    }
    mock_tm.instance.return_value.current = "light"

    mocker.patch.object(MainWindow, "_check_autosave")

    window = MainWindow()
    return window


# ==========================================
# 1. Тесты инициализации
# ==========================================


def test_init_and_ui(qtbot, mock_main_window):
    window = mock_main_window
    qtbot.addWidget(window)

    assert APP_NAME in window.windowTitle()

    sidebar = window.findChild(QListWidget)
    assert sidebar is not None
    assert sidebar.count() == 5

    stack = window.findChild(QStackedWidget)
    assert stack is not None
    assert stack.count() == 5

    assert window.qt_log_handler is not None


# ==========================================
# 2. Тесты навигации и связей
# ==========================================


def test_jump_dups(qtbot, mock_main_window):
    window = mock_main_window
    qtbot.addWidget(window)

    window.sidebar.setCurrentRow(3)
    # Передаем путь к папке, чтобы не зависеть от наличия файла на диске
    window._jump_dups("C:/test")

    assert window.sidebar.currentRow() == 0
    window.scan_tab.path_edit.setText.assert_called_with("C:\\test")
    window.scan_tab.mode_combo.setCurrentIndex.assert_called_with(0)


def test_goto_junk_cleaner(qtbot, mock_main_window):
    window = mock_main_window
    qtbot.addWidget(window)

    window._goto_junk_cleaner()
    assert window.sidebar.currentRow() == 3


# ==========================================
# 3. Тесты трея и спиннера
# ==========================================


def test_tray_spinner(qtbot, mock_main_window):
    window = mock_main_window
    qtbot.addWidget(window)

    assert window.tray_spin_state is False

    window._spin_tray()
    assert window.tray_spin_state is True
    assert window.tray.setIcon.called

    window._spin_tray()
    assert window.tray_spin_state is False

    window.start_tray_spinner()
    assert window.tray_timer.isActive() is True

    window.stop_tray_spinner()
    assert window.tray_timer.isActive() is False


def test_notify(qtbot, mock_main_window):
    window = mock_main_window
    qtbot.addWidget(window)

    window.notify("Заголовок", "Сообщение")
    # Проверяем только заголовок и сообщение, не сверяя иконку
    args, kwargs = window.tray.showMessage.call_args
    assert args[0] == "Заголовок"
    assert args[1] == "Сообщение"


# ==========================================
# 4. Тесты автосохранения
# ==========================================


def test_check_autosave_yes(qtbot, mocker):
    """Проверяет восстановление, если пользователь нажал 'Да'."""
    mocker.patch("gui.main_window.ScanTab", side_effect=DummyTab)
    mocker.patch("gui.main_window.DiskAnalysisTab", side_effect=DummyTab)
    mocker.patch("gui.main_window.SpaceHogsTab", side_effect=DummyTab)
    mocker.patch("gui.main_window.JunkCleanerTab", side_effect=DummyTab)
    mocker.patch("gui.main_window.LogsTab", side_effect=DummyTab)

    mock_settings = mocker.patch("gui.main_window.QSettings")
    mock_settings.return_value.value.return_value = None
    mocker.patch("gui.main_window.QSystemTrayIcon")
    mocker.patch("gui.main_window.QtLogHandler")
    mocker.patch("gui.main_window.ThemeManager")

    # ИСПРАВЛЕНО: Подменяем весь объект AUTOSAVE_FILE, а не его атрибут exists
    mock_autosave = MagicMock()
    mock_autosave.exists.return_value = True
    mocker.patch("gui.main_window.AUTOSAVE_FILE", new=mock_autosave)

    mocker.patch(
        "gui.main_window.QMessageBox.question", return_value=QMessageBox.Yes
    )

    window = MainWindow()
    qtbot.addWidget(window)

    assert window.scan_tab.restore_autosave.called


def test_check_autosave_no(qtbot, mocker):
    """Проверяет, что при отказе восстановление не запускается."""
    mocker.patch("gui.main_window.ScanTab", side_effect=DummyTab)
    mocker.patch("gui.main_window.DiskAnalysisTab", side_effect=DummyTab)
    mocker.patch("gui.main_window.SpaceHogsTab", side_effect=DummyTab)
    mocker.patch("gui.main_window.JunkCleanerTab", side_effect=DummyTab)
    mocker.patch("gui.main_window.LogsTab", side_effect=DummyTab)

    mock_settings = mocker.patch("gui.main_window.QSettings")
    mock_settings.return_value.value.return_value = None
    mocker.patch("gui.main_window.QSystemTrayIcon")
    mocker.patch("gui.main_window.QtLogHandler")
    mocker.patch("gui.main_window.ThemeManager")

    mock_autosave = MagicMock()
    mock_autosave.exists.return_value = True
    mocker.patch("gui.main_window.AUTOSAVE_FILE", new=mock_autosave)

    mocker.patch(
        "gui.main_window.QMessageBox.question", return_value=QMessageBox.No
    )

    window = MainWindow()
    qtbot.addWidget(window)

    assert not window.scan_tab.restore_autosave.called


# ==========================================
# 5. Тесты закрытия окна
# ==========================================


def test_close_event(qtbot, mock_main_window):
    window = mock_main_window
    qtbot.addWidget(window)

    event = QCloseEvent()
    window.closeEvent(event)

    window.settings.setValue.assert_any_call(
        "window/geometry", window.saveGeometry()
    )
    assert window.settings.setValue.call_count >= 1
