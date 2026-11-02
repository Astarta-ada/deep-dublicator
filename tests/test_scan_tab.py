"""Тесты для вкладки поиска дубликатов (gui/scan_tab.py)."""

import pytest
import requests
from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtCore import Qt, QPoint, QMimeData, QUrl
from PySide6.QtGui import QDropEvent, QDragEnterEvent, QStandardItemModel
from PySide6.QtWidgets import QMessageBox, QFileDialog, QWidget, QTreeView

from gui.scan_tab import ScanTab
from gui.models import DuplicateItem
from utils.constants import (
    TEXT_EXTS,
    IMAGE_EXTS,
    ROLE_IS_ORIGINAL,
    ROLE_IS_CHECKED,
)

# ==========================================
# Фикстуры
# ==========================================


@pytest.fixture
def mock_window(mocker):
    win = MagicMock()
    win.start_tray_spinner = MagicMock()
    win.stop_tray_spinner = MagicMock()
    win.notify = MagicMock()
    return win


@pytest.fixture
def scan_tab(qtbot, mocker, mock_window):
    mocker.patch("gui.scan_tab.user_settings._settings")
    mocker.patch.object(ScanTab, "window", return_value=mock_window)

    tab = ScanTab()
    qtbot.addWidget(tab)

    tab.worker = MagicMock()
    tab.apply_worker = MagicMock()
    return tab


@pytest.fixture
def mock_group(mocker):
    g = MagicMock()
    g.hash_key = "hash1"
    g.paths = [Path("C:/file1.txt"), Path("C:/file2.txt")]
    g.get_original.return_value = g.paths[0]
    g.selected_count.return_value = 1
    g.savings_bytes.return_value = 1024
    g.get_selection.return_value = (g.paths[0], [g.paths[1]])
    return g


# ==========================================
# 1. Тесты интерфейса и настроек
# ==========================================


def test_initial_state(scan_tab):
    assert scan_tab.status.text() == "Готово"
    assert scan_tab.progress.isHidden() is True
    assert scan_tab.btn_toggle.isChecked() is True


def test_toggle_settings(scan_tab):
    scan_tab.btn_toggle.setChecked(False)
    scan_tab._toggle_settings(False)
    assert scan_tab.settings_widget.isVisible() is False
    assert "Развернуть" in scan_tab.btn_toggle.text()


def test_mode_changed(scan_tab):
    scan_tab.mode_combo.setCurrentIndex(1)
    scan_tab._mode_changed(1)
    assert scan_tab.phash_slider.isHidden() is False
    assert scan_tab.target_file_container.isHidden() is True

    scan_tab.mode_combo.setCurrentIndex(6)
    scan_tab._mode_changed(6)
    assert scan_tab.target_file_container.isHidden() is False


def test_browse(scan_tab, mocker):
    mocker.patch(
        "gui.scan_tab.QFileDialog.getExistingDirectory",
        return_value="C:\\TestDir",
    )
    scan_tab._browse()
    assert scan_tab.path_edit.text() == "C:\\TestDir"


def test_browse_target(scan_tab, mocker):
    mocker.patch(
        "gui.scan_tab.QFileDialog.getOpenFileName",
        return_value=("C:\\test.txt", ""),
    )
    scan_tab._browse_target_file()
    assert scan_tab.target_file_edit.text() == "C:\\test.txt"


# ==========================================
# 2. Запуск сканирования
# ==========================================


def test_start_invalid_path(scan_tab, mocker):
    mock_warn = mocker.patch("gui.scan_tab.QMessageBox.warning")
    scan_tab.path_edit.setText("C:/GhostPath")
    scan_tab._start()
    assert mock_warn.called


def test_start_valid_path(scan_tab, mocker):
    mocker.patch("pathlib.Path.is_dir", return_value=True)
    mock_worker_class = mocker.patch("gui.scan_tab.ScanWorker")

    scan_tab.path_edit.setText("C:/Valid")
    scan_tab._start()

    assert scan_tab.scan_btn.isEnabled() is False
    assert scan_tab.progress.isHidden() is False
    assert scan_tab.btn_toggle.isChecked() is False
    assert mock_worker_class.called
    assert scan_tab.window().start_tray_spinner.called


def test_prog_bytes(scan_tab):
    scan_tab._prog_bytes("quick_hash", 50, 100, 60)
    assert scan_tab.progress.value() == 50
    assert "быстрый хеш" in scan_tab.progress.format()
    assert "1м 0с" in scan_tab.progress.format()


def test_on_failed(scan_tab, mocker):
    mock_crit = mocker.patch("gui.scan_tab.QMessageBox.critical")
    scan_tab._on_failed("Test error")

    assert scan_tab.progress.isHidden() is True
    assert scan_tab.scan_btn.isEnabled() is True
    assert mock_crit.called
    scan_tab.window().stop_tray_spinner.assert_called_once()


# ==========================================
# 3. Завершение сканирования и заполнение модели
# ==========================================


def test_done_empty(scan_tab):
    scan_tab._done({})
    assert "не найдены" in scan_tab.status.text()


def test_done_success(scan_tab, mocker):
    mocker.patch("gui.scan_tab.ScanTab._populate")
    mocker.patch("PySide6.QtCore.QTimer.singleShot")

    res = {"h1": [Path("f1"), Path("f2")]}
    scan_tab._done(res)

    assert scan_tab.progress.isHidden() is True
    assert scan_tab.scan_btn.isEnabled() is True
    assert "Найдено групп: 1" in scan_tab.status.text()
    assert scan_tab.window().notify.called


def test_populate_model(scan_tab, mocker):
    """Проверяет заполнение модели и вкладок."""
    res = {
        "h1": [Path("f1.txt"), Path("f2.txt")],
        "EMPTY": [Path("e1.txt"), Path("e2.txt")],
    }

    scan_tab._populate(res)

    assert scan_tab.model.rowCount() == 2
    assert scan_tab.category_tabs.count() == 3  # Все + Пустые + Документы

    # Находим категорию по имени, так как они отсортированы по алфавиту
    names = [
        scan_tab.model.item(i, 0).text()
        for i in range(scan_tab.model.rowCount())
    ]
    assert any("Пустые файлы" in n for n in names)
    assert any("Документы" in n for n in names)

    # Проверяем, что у категорий есть пустышка "Загрузка..."
    for i in range(scan_tab.model.rowCount()):
        assert scan_tab.model.item(i, 0).child(0).text() == "Загрузка..."


def test_on_category_expanded(scan_tab, mocker):
    """Проверяет ленивую загрузку групп."""
    mocker.patch("pathlib.Path.stat", return_value=MagicMock(st_size=100))

    res = {"h1": [Path("f1.txt"), Path("f2.txt")]}
    scan_tab._populate(res)

    cat_item = scan_tab.model.item(0, 0)
    mocker.patch("PySide6.QtCore.QTimer.singleShot")

    scan_tab._on_category_expanded(cat_item.index())

    assert cat_item.rowCount() == 1  # Загрузилась одна группа
    assert cat_item.child(0).text() != "Загрузка..."
    assert cat_item.child(0).rowCount() == 2


def test_clear(scan_tab):
    scan_tab._clear()
    assert scan_tab.model.rowCount() == 0
    assert scan_tab.last_result == {}


# ==========================================
# 4. Выделение и фильтрация
# ==========================================


def test_sel_all(scan_tab, mocker):
    mocker.patch("pathlib.Path.stat", return_value=MagicMock(st_size=100))

    res = {"h1": [Path("f1.txt"), Path("f2.txt")]}
    scan_tab._populate(res)
    scan_tab._on_category_expanded(scan_tab.model.item(0, 0).index())

    group_item = scan_tab.model.item(0, 0).child(0)

    # Изначально второй файл отмечен, первый (оригинал) - нет
    assert group_item.child(0).data(ROLE_IS_CHECKED) is False
    assert group_item.child(1).data(ROLE_IS_CHECKED) is True

    # Вызываем "Снять все" (так как один уже отмечен, но не все)
    scan_tab._sel_all()

    # Теперь должны быть отмечены все не-оригиналы
    assert group_item.child(0).data(ROLE_IS_CHECKED) is False
    assert group_item.child(1).data(ROLE_IS_CHECKED) is False


def test_apply_filter(scan_tab, mocker):
    mocker.patch("pathlib.Path.stat", return_value=MagicMock(st_size=100))

    res = {"h1": [Path("f1.txt"), Path("f2.txt")]}
    scan_tab._populate(res)
    scan_tab._on_category_expanded(scan_tab.model.item(0, 0).index())

    mock_hide = mocker.patch.object(scan_tab.tree, "setRowHidden")
    scan_tab.res_filter.matches = MagicMock(return_value=False)

    scan_tab._apply_filter()
    assert mock_hide.called


# ==========================================
# 5. Применение действий
# ==========================================


def test_apply_success(scan_tab, mocker):
    mocker.patch("pathlib.Path.stat", return_value=MagicMock(st_size=100))

    res = {"h1": [Path("f1.txt"), Path("f2.txt")]}
    scan_tab._populate(res)
    scan_tab._on_category_expanded(scan_tab.model.item(0, 0).index())

    mock_worker = mocker.patch("gui.scan_tab.ApplyWorker")
    mocker.patch(
        "gui.scan_tab.QMessageBox.question", return_value=QMessageBox.Yes
    )

    scan_tab.action_combo.setCurrentIndex(1)  # delete
    scan_tab._apply()

    assert scan_tab.btn_apply.isEnabled() is False
    assert mock_worker.called


def test_on_apply_finished(scan_tab, mocker):
    mocker.patch("gui.scan_tab.ScanTab._populate")
    mock_info = mocker.patch("gui.scan_tab.QMessageBox.information")

    scan_tab._on_apply_finished(5, [])

    assert scan_tab.progress.isHidden() is True
    assert scan_tab.btn_apply.isEnabled() is True
    assert "Успешно обработано: 5" in mock_info.call_args[0][2]


# ==========================================
# 6. Экспорт
# ==========================================


def test_save_sess(scan_tab, mocker, tmp_path):
    mocker.patch("pathlib.Path.stat", return_value=MagicMock(st_size=100))
    res = {"h1": [Path("f1.txt"), Path("f2.txt")]}
    scan_tab._populate(res)
    scan_tab._on_category_expanded(scan_tab.model.item(0, 0).index())

    sess_file = tmp_path / "sess.json"
    mocker.patch(
        "gui.scan_tab.QFileDialog.getSaveFileName",
        return_value=(str(sess_file), ""),
    )
    mock_save = mocker.patch("gui.scan_tab.save_session")

    scan_tab._save_sess()
    assert mock_save.called


def test_exp_csv(scan_tab, mocker, tmp_path):
    mocker.patch(
        "pathlib.Path.stat",
        return_value=MagicMock(st_size=100, st_ctime=1600000000.0),
    )
    res = {"h1": [Path("f1.txt"), Path("f2.txt")]}
    scan_tab._populate(res)
    scan_tab._on_category_expanded(scan_tab.model.item(0, 0).index())

    csv_file = tmp_path / "out.csv"
    mocker.patch(
        "gui.scan_tab.QFileDialog.getSaveFileName",
        return_value=(str(csv_file), ""),
    )

    scan_tab._exp_csv()
    assert csv_file.exists()
    content = csv_file.read_text(encoding="utf-8")
    assert "f1.txt" in content
    assert "f2.txt" in content


def test_exp_script(scan_tab, mocker, tmp_path):
    mocker.patch("pathlib.Path.stat", return_value=MagicMock(st_size=100))
    res = {"h1": [Path("f1.txt"), Path("f2.txt")]}
    scan_tab._populate(res)
    scan_tab._on_category_expanded(scan_tab.model.item(0, 0).index())

    bat_file = tmp_path / "out.bat"
    mocker.patch(
        "gui.scan_tab.QFileDialog.getSaveFileName",
        return_value=(str(bat_file), ""),
    )

    scan_tab._exp_script()
    assert bat_file.exists()
    assert "del" in bat_file.read_text(encoding="utf-8")


def test_do_autosave(scan_tab, mocker):
    mocker.patch("pathlib.Path.stat", return_value=MagicMock(st_size=100))
    res = {"h1": [Path("f1.txt"), Path("f2.txt")]}
    scan_tab._populate(res)

    mocker.patch("gui.scan_tab.save_session")
    scan_tab._do_autosave()
    # Просто проверяем, что не упало


# ==========================================
# 7. VirusTotal
# ==========================================


def test_check_vt_success(scan_tab, mocker):
    mocker.patch("pathlib.Path.stat", return_value=MagicMock(st_size=100))
    res = {"h1": [Path("f1.txt"), Path("f2.txt")]}
    scan_tab._populate(res)
    scan_tab._on_category_expanded(scan_tab.model.item(0, 0).index())

    mocker.patch("utils.settings.get_vt_api_key", return_value="valid_key")
    mocker.patch("core.hasher.hash_file", return_value="hash123")

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "data": {
            "attributes": {
                "last_analysis_stats": {
                    "harmless": 70,
                    "malicious": 0,
                    "suspicious": 0,
                }
            }
        }
    }
    mocker.patch("requests.get", return_value=mock_resp)
    mock_msg = mocker.patch("gui.scan_tab.QMessageBox.information")

    scan_tab._check_vt()
    assert mock_msg.called


def test_check_vt_404(scan_tab, mocker):
    mocker.patch("pathlib.Path.stat", return_value=MagicMock(st_size=100))
    res = {"h1": [Path("f1.txt"), Path("f2.txt")]}
    scan_tab._populate(res)
    scan_tab._on_category_expanded(scan_tab.model.item(0, 0).index())

    mocker.patch("utils.settings.get_vt_api_key", return_value="valid_key")
    mocker.patch("core.hasher.hash_file", return_value="hash123")
    mocker.patch("requests.get", return_value=MagicMock(status_code=404))
    mock_msg = mocker.patch("gui.scan_tab.QMessageBox.information")

    scan_tab._check_vt()
    assert "еще не загружен" in mock_msg.call_args[0][2]


# ==========================================
# 8. Drag & Drop
# ==========================================


def test_drag_and_drop(scan_tab, mocker):
    mocker.patch("pathlib.Path.is_dir", return_value=True)
    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile("C:/DropFolder")])

    drag_event = mocker.MagicMock()
    drag_event.mimeData.return_value = mime_data
    scan_tab.dragEnterEvent(drag_event)
    drag_event.acceptProposedAction.assert_called_once()

    drop_event = mocker.MagicMock()
    drop_event.mimeData.return_value = mime_data
    scan_tab.dropEvent(drop_event)
    assert scan_tab.path_edit.text() == "C:\\DropFolder"
