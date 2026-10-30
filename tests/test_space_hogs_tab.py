"""Тесты для вкладки поиска больших файлов (gui/space_hogs_tab.py)."""

import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtCore import Qt, QPoint, QMimeData, QUrl
from PySide6.QtGui import QDropEvent, QDragEnterEvent
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem, QTableWidget

from gui.space_hogs_tab import SpaceHogsTab, SizeItem

# ==========================================
# Фикстуры
# ==========================================


@pytest.fixture
def mock_window(mocker):
    """Мокает главное окно (для спиннера и уведомлений)."""
    win = MagicMock()
    win.start_tray_spinner = MagicMock()
    win.stop_tray_spinner = MagicMock()
    win.notify = MagicMock()
    return win


@pytest.fixture
def hogs_tab(qtbot, mocker, mock_window):
    """Создает вкладку с замоканными зависимостями."""
    mocker.patch.object(SpaceHogsTab, "window", return_value=mock_window)
    tab = SpaceHogsTab()
    qtbot.addWidget(tab)
    return tab


# ==========================================
# 1. Тесты для SizeItem (Кастомная сортировка)
# ==========================================


def test_size_item_sorting():
    """Проверяет, что SizeItem сравнивает реальные байты, а не строки."""
    item1 = SizeItem(100)  # 100.0 B
    item2 = SizeItem(2048)  # 2.0 KB

    # При сравнении 100 Байт должно быть меньше, чем 2 КБ
    assert item1.__lt__(item2) is True
    assert item2.__lt__(item1) is False

    # Проверка строкового отображения
    assert item1.text() == "100.0 B"
    assert item2.text() == "2.0 KB"


# ==========================================
# 2. Тесты интерфейса
# ==========================================


def test_initial_state(hogs_tab):
    assert hogs_tab.table.rowCount() == 0
    assert hogs_tab.status.text() == "Готово к работе"
    assert hogs_tab.btn_start.isEnabled() is True


def test_browse(hogs_tab, mocker):
    mocker.patch(
        "gui.space_hogs_tab.QFileDialog.getExistingDirectory",
        return_value="C:\\Selected",
    )
    hogs_tab._browse()
    assert hogs_tab.path_edit.text() == "C:\\Selected"


# ==========================================
# 3. Тесты сканирования
# ==========================================


def test_start_invalid_path(hogs_tab, mocker):
    mock_warning = mocker.patch("gui.space_hogs_tab.QMessageBox.warning")
    hogs_tab.path_edit.setText("C:\\Ghost")
    hogs_tab._start()
    assert mock_warning.called


def test_start_valid_path(hogs_tab, mocker):
    mocker.patch("os.path.isdir", return_value=True)
    mock_worker = mocker.patch("gui.space_hogs_tab.HogsScanner")

    hogs_tab.path_edit.setText("C:\\Valid")
    hogs_tab._start()

    assert hogs_tab.btn_start.isEnabled() is False
    assert hogs_tab.status.text() == "Сканирование..."
    assert hogs_tab.window().start_tray_spinner.called
    assert mock_worker.return_value.start.called


def test_done_fills_table(hogs_tab, mocker):
    mock_win = hogs_tab.window()

    # Имитируем результат от воркера
    res = [
        ("C:/file1.bin", 1000, "2023-01-01"),
        ("C:/file2.bin", 500, "2023-01-02"),
    ]

    hogs_tab._done(res)

    assert hogs_tab.btn_start.isEnabled() is True
    assert hogs_tab.status.text() == "Найдено файлов: 2"
    assert hogs_tab.table.rowCount() == 2

    # ИСПРАВЛЕНО: Собираем данные из таблицы независимо от порядка строк
    paths = []
    sizes = []
    for i in range(2):
        paths.append(hogs_tab.table.item(i, 0).text())
        sizes.append(hogs_tab.table.item(i, 1).text())

    assert "C:/file1.bin" in paths
    assert "C:/file2.bin" in paths
    assert "1000.0 B" in sizes
    assert "500.0 B" in sizes

    # Проверяем спиннер и уведомление
    mock_win.stop_tray_spinner.assert_called_once()
    mock_win.notify.assert_called_once()


# ==========================================
# 4. Тесты меню и удаления
# ==========================================


def test_menu(hogs_tab, mocker):
    """Покрывает вызов контекстного меню."""
    hogs_tab.table.setRowCount(1)
    hogs_tab.table.setItem(0, 0, QTableWidgetItem("test.txt"))

    # Мокаем QMenu, чтобы он не открывался реально
    mock_menu = mocker.patch("gui.space_hogs_tab.QMenu")
    hogs_tab._menu(QPoint(10, 10))

    assert mock_menu.called


def test_del_success(hogs_tab, tmp_path, mocker):
    """Проверяет удаление файла из таблицы."""
    # Создаем реальный файл
    file_path = tmp_path / "test.bin"
    file_path.write_bytes(b"x" * 100)

    hogs_tab.table.setRowCount(1)
    hogs_tab.table.setItem(0, 0, QTableWidgetItem(str(file_path)))

    mocker.patch(
        "gui.space_hogs_tab.QMessageBox.question", return_value=QMessageBox.Yes
    )
    mock_delete = mocker.patch("gui.space_hogs_tab.delete_file")

    hogs_tab._del(str(file_path), 0)

    assert mock_delete.called
    assert hogs_tab.table.rowCount() == 0


def test_del_error(hogs_tab, mocker):
    """Покрывает ошибку при удалении."""
    hogs_tab.table.setRowCount(1)
    hogs_tab.table.setItem(0, 0, QTableWidgetItem("test.txt"))

    mocker.patch(
        "gui.space_hogs_tab.QMessageBox.question", return_value=QMessageBox.Yes
    )
    mocker.patch(
        "gui.space_hogs_tab.delete_file", side_effect=Exception("Delete error")
    )
    mock_crit = mocker.patch("gui.space_hogs_tab.QMessageBox.critical")

    hogs_tab._del("test.txt", 0)

    assert mock_crit.called
    assert hogs_tab.table.rowCount() == 1  # Строка не удалилась


# ==========================================
# 5. Drag & Drop
# ==========================================


def test_drag_and_drop(hogs_tab, mocker):
    mocker.patch("pathlib.Path.is_dir", return_value=True)
    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile("C:/DropFolder")])

    drag_event = mocker.MagicMock()
    drag_event.mimeData.return_value = mime_data
    hogs_tab.dragEnterEvent(drag_event)
    drag_event.acceptProposedAction.assert_called_once()

    drop_event = mocker.MagicMock()
    drop_event.mimeData.return_value = mime_data
    mocker.patch("gui.space_hogs_tab.SpaceHogsTab._start")
    hogs_tab.dropEvent(drop_event)
    assert hogs_tab.path_edit.text() == "C:\\DropFolder"


def test_drag_enter_invalid(hogs_tab, mocker):
    mocker.patch("pathlib.Path.is_dir", return_value=False)
    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile("C:/file.txt")])

    drag_event = mocker.MagicMock()
    drag_event.mimeData.return_value = mime_data
    hogs_tab.dragEnterEvent(drag_event)
    drag_event.ignore.assert_called_once()


def test_drop_invalid(hogs_tab, mocker):
    mocker.patch("pathlib.Path.is_dir", return_value=False)
    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile("C:/file.txt")])

    drop_event = mocker.MagicMock()
    drop_event.mimeData.return_value = mime_data
    hogs_tab.dropEvent(drop_event)
    drop_event.ignore.assert_called_once()
