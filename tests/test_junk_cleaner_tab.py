"""Тесты для вкладки очистки мусора (gui/junk_cleaner_tab.py)."""

import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtCore import Qt, QPoint, QMimeData, QUrl
from PySide6.QtWidgets import QMessageBox, QListWidgetItem
from PySide6.QtGui import QDropEvent, QDragEnterEvent

from gui.junk_cleaner_tab import JunkCleanerTab

# ==========================================
# Фикстуры
# ==========================================


@pytest.fixture
def junk_tab(qtbot):
    """Создает вкладку очистки мусора."""
    tab = JunkCleanerTab()
    qtbot.addWidget(tab)
    return tab


# ==========================================
# 1. Тесты интерфейса и запуска
# ==========================================


def test_initial_state(junk_tab):
    """Проверяет начальное состояние виджетов."""
    assert junk_tab.list_widget.count() == 0
    assert junk_tab.status.text() == "Готово к работе"
    assert junk_tab.btn_scan.isEnabled() is True


def test_browse(junk_tab, mocker):
    """Проверяет выбор папки через диалог."""
    mocker.patch(
        "gui.junk_cleaner_tab.QFileDialog.getExistingDirectory",
        return_value="C:\\SelectedFolder",
    )
    junk_tab._browse()
    assert junk_tab.path_edit.text() == "C:\\SelectedFolder"


def test_scan_invalid_path(junk_tab, mocker):
    """Проверяет предупреждение, если папка не существует."""
    mock_warning = mocker.patch("gui.junk_cleaner_tab.QMessageBox.warning")
    junk_tab.path_edit.setText("C:\\InvalidGhostPath")

    junk_tab._scan()
    assert mock_warning.called


def test_scan_valid_path(junk_tab, mocker):
    """Проверяет запуск фонового воркера и спиннера."""
    mocker.patch("os.path.isdir", return_value=True)

    # Мокаем главное окно, чтобы проверить вызов спиннера
    mock_main_win = MagicMock()
    mock_main_win.start_tray_spinner = MagicMock()
    mocker.patch.object(junk_tab, "window", return_value=mock_main_win)

    # Мокаем воркер
    mock_worker = mocker.patch("gui.junk_cleaner_tab.JunkScanner")

    junk_tab.path_edit.setText("C:\\Valid")
    junk_tab._scan()

    assert junk_tab.btn_scan.isEnabled() is False
    assert junk_tab.status.text() == "Анализ..."
    assert mock_main_win.start_tray_spinner.called
    assert mock_worker.return_value.start.called


def test_done_callback(junk_tab, mocker):
    """Проверяет заполнение списка после завершения сканирования."""
    mock_main_win = MagicMock()
    mock_main_win.stop_tray_spinner = MagicMock()
    mocker.patch.object(junk_tab, "window", return_value=mock_main_win)

    # Имитируем результат от воркера
    res = [("Temp Files", "C:/temp", 1024), ("Python Cache", "C:/py", 2048)]
    junk_tab._done(res)

    assert junk_tab.btn_scan.isEnabled() is True
    assert junk_tab.status.text() == "Найдено категорий мусора: 2"
    assert junk_tab.list_widget.count() == 2
    assert mock_main_win.stop_tray_spinner.called

    # Проверяем первый элемент
    item = junk_tab.list_widget.item(0)
    assert item.text() == "Temp Files — 1.0 KB"
    assert item.checkState() == Qt.Checked


# ==========================================
# 2. Тесты логики очистки (Сложная часть)
# ==========================================


def test_clean_empty_list(junk_tab):
    """Проверяет, что очистка пустого списка ничего не делает."""
    junk_tab._clean()  # Не должно быть ошибок или диалогов


def test_clean_cancelled(junk_tab, mocker):
    """Проверяет, что при отмене удаления ничего не происходит."""
    junk_tab.list_widget.addItem(QListWidgetItem("Test"))
    mocker.patch(
        "gui.junk_cleaner_tab.QMessageBox.question",
        return_value=QMessageBox.No,
    )

    mock_remove = mocker.patch("os.remove")
    junk_tab._clean()

    assert mock_remove.called is False


def test_clean_temp_files(junk_tab, tmp_path, mocker):
    """Проверяет реальное удаление временных файлов."""
    # Создаем реальную структуру для Temp
    temp_dir = tmp_path / "temp_folder"
    temp_dir.mkdir()
    file1 = temp_dir / "file1.tmp"
    file1.write_bytes(b"12345")  # 5 байт

    # Добавляем в список
    item = QListWidgetItem("Temp Files")
    item.setData(Qt.UserRole, ("Temp Files", str(temp_dir)))
    item.setCheckState(Qt.Checked)
    junk_tab.list_widget.addItem(item)

    # Мокаем подтверждение
    mocker.patch(
        "gui.junk_cleaner_tab.QMessageBox.question",
        return_value=QMessageBox.Yes,
    )
    mock_info = mocker.patch("gui.junk_cleaner_tab.QMessageBox.information")

    junk_tab._clean()

    # Файл должен быть удален, папка пуста
    assert not file1.exists()
    assert junk_tab.list_widget.count() == 0
    # Проверяем сообщение (5 байт = 5.0 B)
    assert "Освобождено места: 5.0 B" in mock_info.call_args[0][2]


def test_clean_cache_folder(junk_tab, tmp_path, mocker):
    """Проверяет удаление папок кэша (Chrome Cache)."""
    cache_dir = tmp_path / "chrome_cache"
    cache_dir.mkdir()
    (cache_dir / "cache.dat").write_bytes(b"x" * 100)

    item = QListWidgetItem("Chrome Cache")
    item.setData(Qt.UserRole, ("Chrome Cache", str(cache_dir)))
    item.setCheckState(Qt.Checked)
    junk_tab.list_widget.addItem(item)

    mocker.patch(
        "gui.junk_cleaner_tab.QMessageBox.question",
        return_value=QMessageBox.Yes,
    )
    mocker.patch("gui.junk_cleaner_tab.QMessageBox.information")

    junk_tab._clean()

    # Папка должна быть удалена целиком
    assert not cache_dir.exists()


def test_clean_python_list(junk_tab, tmp_path, mocker):
    """Проверяет удаление списка папок (Python Cache, разделенных \n)."""
    dir1 = tmp_path / "pycache1"
    dir1.mkdir()
    dir2 = tmp_path / "pycache2"
    dir2.mkdir()

    paths_str = f"{dir1}\n{dir2}"

    item = QListWidgetItem("Python Cache")
    item.setData(Qt.UserRole, ("Python Cache", paths_str))
    item.setCheckState(Qt.Checked)
    junk_tab.list_widget.addItem(item)

    mocker.patch(
        "gui.junk_cleaner_tab.QMessageBox.question",
        return_value=QMessageBox.Yes,
    )
    mocker.patch("gui.junk_cleaner_tab.QMessageBox.information")

    junk_tab._clean()

    assert not dir1.exists()
    assert not dir2.exists()


def test_clean_error_handling(junk_tab, mocker):
    """Проверяет обработку ошибок при удалении (вызовет QMessageBox с ошибками)."""
    item = QListWidgetItem("Temp Files")
    item.setData(Qt.UserRole, ("Temp Files", "C:/ghost_path"))
    item.setCheckState(Qt.Checked)
    junk_tab.list_widget.addItem(item)

    mocker.patch(
        "gui.junk_cleaner_tab.QMessageBox.question",
        return_value=QMessageBox.Yes,
    )
    mock_info = mocker.patch("gui.junk_cleaner_tab.QMessageBox.information")

    # Имитируем ошибку при обращении к папке
    mocker.patch("os.path.exists", return_value=False)
    mocker.patch("os.walk", side_effect=Exception("Walk error"))

    junk_tab._clean()

    # Должно появиться сообщение с ошибкой
    assert "Ошибки при удалении некоторых файлов" in mock_info.call_args[0][2]


# ==========================================
# 3. Тесты Drag & Drop
# ==========================================


def test_drag_and_drop(junk_tab, mocker):
    mocker.patch("gui.junk_cleaner_tab.JunkCleanerTab._scan")
    mocker.patch("pathlib.Path.is_dir", return_value=True)

    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile("C:/DropFolder")])

    drag_event = mocker.MagicMock()
    drag_event.mimeData.return_value = mime_data
    junk_tab.dragEnterEvent(drag_event)
    drag_event.acceptProposedAction.assert_called_once()

    drop_event = mocker.MagicMock()
    drop_event.mimeData.return_value = mime_data
    junk_tab.dropEvent(drop_event)
    assert junk_tab.path_edit.text() == "C:\\DropFolder"
    assert junk_tab._scan.called


def test_clean_error(junk_tab, mocker):
    """Покрывает except Exception в _clean (строки 202-213)."""
    item = QListWidgetItem("Temp Files")
    item.setData(Qt.UserRole, ("Temp Files", "C:/ghost"))
    item.setCheckState(Qt.Checked)
    junk_tab.list_widget.addItem(item)

    mocker.patch(
        "gui.junk_cleaner_tab.QMessageBox.question",
        return_value=QMessageBox.Yes,
    )
    mock_info = mocker.patch("gui.junk_cleaner_tab.QMessageBox.information")

    # Имитируем ошибку при вызове os.walk (для подсчета размера)
    mocker.patch("os.walk", side_effect=Exception("Mock error"))

    junk_tab._clean()

    # Должно появиться сообщение с ошибкой
    assert "Ошибки при удалении" in mock_info.call_args[0][2]


def test_clean_size_counting_branches(junk_tab, tmp_path, mocker):
    """Покрывает подсчет размера для Temp/Cache и обработку ошибок внутри цикла."""
    temp_dir = tmp_path / "temp_dir"
    temp_dir.mkdir()
    f1 = temp_dir / "valid.tmp"
    f1.write_bytes(b"12345")  # 5 байт

    item = QListWidgetItem("Temp Files")
    item.setData(Qt.UserRole, ("Temp Files", str(temp_dir)))
    item.setCheckState(Qt.Checked)
    junk_tab.list_widget.addItem(item)

    mocker.patch(
        "gui.junk_cleaner_tab.QMessageBox.question",
        return_value=QMessageBox.Yes,
    )
    mocker.patch("gui.junk_cleaner_tab.QMessageBox.information")

    # Имитируем ошибку при получении размера конкретного файла
    original_getsize = os.path.getsize

    def mock_getsize(path):
        if "valid" in str(path):
            raise OSError("Mock size error")
        return original_getsize(path)

    mocker.patch("os.path.getsize", side_effect=mock_getsize)

    junk_tab._clean()
    # Тест просто должен пройти без падений (ошибка перехвачена)


def test_clean_cache_branch_separately(junk_tab, tmp_path, mocker):
    """Проверяет ветку удаления 'Cache' (не Python, не Temp)."""
    cache_dir = tmp_path / "browser_cache"
    cache_dir.mkdir()
    (cache_dir / "cache_data.bin").write_bytes(b"x" * 50)

    # "Браузерный кэш" содержит "Cache", но не "Temp" и не "Python Cache"
    item = QListWidgetItem("Browser Cache")
    item.setData(Qt.UserRole, ("Browser Cache", str(cache_dir)))
    item.setCheckState(Qt.Checked)
    junk_tab.list_widget.addItem(item)

    mocker.patch(
        "gui.junk_cleaner_tab.QMessageBox.question",
        return_value=QMessageBox.Yes,
    )
    mocker.patch("gui.junk_cleaner_tab.QMessageBox.information")

    junk_tab._clean()

    assert not cache_dir.exists()


def test_clean_nodejs_list(junk_tab, tmp_path, mocker):
    """Проверяет ветку удаления Node.js (разделенных \n)."""
    dir1 = tmp_path / "node_modules"
    dir1.mkdir()

    item = QListWidgetItem("Node.js")
    item.setData(Qt.UserRole, ("Node.js", str(dir1)))
    item.setCheckState(Qt.Checked)
    junk_tab.list_widget.addItem(item)

    mocker.patch(
        "gui.junk_cleaner_tab.QMessageBox.question",
        return_value=QMessageBox.Yes,
    )
    mocker.patch("gui.junk_cleaner_tab.QMessageBox.information")

    junk_tab._clean()
    assert not dir1.exists()
