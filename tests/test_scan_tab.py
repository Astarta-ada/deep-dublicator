"""Тесты для вкладки поиска дубликатов (gui/scan_tab.py)."""

import pytest
import requests
from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtCore import Qt, QPoint, QMimeData, QUrl
from PySide6.QtGui import QDropEvent, QDragEnterEvent
from PySide6.QtWidgets import QMessageBox, QMessageBox, QWidget

from gui.scan_tab import ScanTab
from utils.constants import TEXT_EXTS, IMAGE_EXTS

# ==========================================
# Фикстуры
# ==========================================


@pytest.fixture
def mock_window(mocker):
    """Мокает главное окно (для вызова спиннера и уведомлений)."""
    win = MagicMock()
    win.start_tray_spinner = MagicMock()
    win.stop_tray_spinner = MagicMock()
    win.notify = MagicMock()
    return win


@pytest.fixture
def scan_tab(qtbot, mocker, mock_window):
    """Создает ScanTab с замоканными зависимостями."""
    # Мокаем настройки (чтобы не читать реальные)
    mocker.patch("gui.scan_tab.user_settings._settings")

    # Мокаем окно
    mocker.patch.object(ScanTab, "window", return_value=mock_window)

    tab = ScanTab()
    qtbot.addWidget(tab)

    # Заменяем воркеры на моки, чтобы они не запускались
    tab.worker = MagicMock()
    tab.apply_worker = MagicMock()

    return tab


@pytest.fixture
def mock_group(mocker):
    """Создает мок группы дубликатов."""
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
    """Проверяет переключение режимов (поиск ссылок и pHash)."""
    # Режим "Похожие фото" (индекс 1)
    scan_tab.mode_combo.setCurrentIndex(1)
    scan_tab._mode_changed(1)
    # Используем isHidden вместо isVisible, так как окно не показано на экране
    assert scan_tab.phash_slider.isHidden() is False
    assert scan_tab.target_file_container.isHidden() is True

    # Режим "Ссылки" (индекс 6)
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
# 2. Запуск сканирования и прогресс
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
    # Проверяем, что прогресс-бар не скрыт (isHidden() == False)
    assert scan_tab.progress.isHidden() is False
    assert scan_tab.btn_toggle.isChecked() is False
    assert mock_worker_class.called


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
# 3. Завершение сканирования и заполнение
# ==========================================


def test_done_empty(scan_tab):
    scan_tab._done({})
    assert "не найдены" in scan_tab.status.text()


def test_done_success(scan_tab, mocker):
    mocker.patch("gui.scan_tab.ScanTab._populate")
    mocker.patch("gui.scan_tab.save_session")
    mocker.patch("gui.scan_tab.build_session_from_groups")

    res = {"h1": [Path("f1"), Path("f2")]}
    scan_tab._done(res)

    assert scan_tab.progress.isHidden() is True
    assert scan_tab.scan_btn.isEnabled() is True
    assert "Найдено групп: 1" in scan_tab.status.text()
    assert scan_tab.window().notify.called


def test_populate(scan_tab, mocker):
    # Мокаем методы, чтобы не вызывать реальную отрисовку
    mocker.patch("gui.scan_tab.ScanTab._clear")
    mocker.patch("gui.scan_tab.ScanTab._apply_filter")
    mocker.patch("gui.scan_tab.ScanTab._upd_stat")

    # Мокаем addWidget, чтобы Qt не проверял тип MagicMock
    mocker.patch.object(scan_tab.res_layout, "addWidget")

    mocker.patch("gui.scan_tab.CategoryGroupWidget")
    mock_dup_widget = mocker.patch("gui.scan_tab.DuplicateGroupWidget")

    res = {
        "h1": [Path("img1.jpg"), Path("img2.jpg")],
        "EMPTY": [Path("empty1.txt"), Path("empty2.txt")],
    }

    scan_tab._populate(res)

    # Проверяем, что создались виджеты (2 группы)
    assert mock_dup_widget.call_count == 2
    assert len(scan_tab.groups) == 2


def test_clear(scan_tab, mocker):
    # Создаем реальный QWidget, чтобы addWidget не падал
    mock_widget = QWidget()
    mock_widget.deleteLater = mocker.MagicMock()

    scan_tab.res_layout.addWidget(mock_widget)
    scan_tab.groups = [mock_widget]

    scan_tab._clear()

    assert len(scan_tab.groups) == 0
    assert mock_widget.deleteLater.called


# ==========================================
# 4. Выделение, фильтрация и сортировка
# ==========================================


def test_sel_all(scan_tab, mock_group):
    scan_tab.groups = [mock_group]
    mock_group._checks = [
        MagicMock(isChecked=lambda: True),
        MagicMock(isChecked=lambda: True),
    ]
    mock_group._get_original_index.return_value = 0

    scan_tab._sel_all()
    assert mock_group.set_selected.called


def test_apply_filter(scan_tab, mock_group):
    scan_tab.groups = [mock_group]
    scan_tab.res_filter.matches = MagicMock(return_value=True)

    scan_tab._apply_filter()
    mock_group.setVisible.assert_called_with(True)


def test_sort(scan_tab, mocker):
    scan_tab.last_result = {"h1": [Path("f1"), Path("f2")]}
    mocker.patch("gui.scan_tab.ScanTab._populate")

    # Изначально _sort_descending = True, кнопка показывает "↓"
    # Первый вызов _sort() переключает на False -> стрелка "↑"
    scan_tab._sort()
    assert "↑" in scan_tab.sort_btn.text()

    # Второй вызов _sort() переключает на True -> стрелка "↓"
    scan_tab._sort()
    assert "↓" in scan_tab.sort_btn.text()


# ==========================================
# 5. Сравнение (Diff)
# ==========================================


def test_diff_text(scan_tab, mocker):
    mock_dialog = mocker.patch("gui.scan_tab.DiffDialog")
    scan_tab._diff(Path("file1.txt"), Path("file2.txt"))
    assert mock_dialog.called


def test_diff_image(scan_tab, mocker):
    mock_dialog = mocker.patch("gui.scan_tab.SliderDialog")
    scan_tab._diff(Path("img1.jpg"), Path("img2.jpg"))
    assert mock_dialog.called


# ==========================================
# 6. Применение действий (Удаление и т.д.)
# ==========================================


def test_apply_nothing_selected(scan_tab, mock_group, mocker):
    mock_info = mocker.patch("gui.scan_tab.QMessageBox.information")
    mock_group.selected_count.return_value = 0
    scan_tab.groups = [mock_group]

    scan_tab._apply()
    assert mock_info.called


def test_apply_cancelled(scan_tab, mock_group, mocker):
    mock_group.selected_count.return_value = 1
    scan_tab.groups = [mock_group]
    scan_tab.action_combo.setCurrentIndex(1)  # delete

    mocker.patch(
        "gui.scan_tab.QMessageBox.question", return_value=QMessageBox.No
    )
    mock_worker = mocker.patch("gui.scan_tab.ApplyWorker")

    scan_tab._apply()
    assert not mock_worker.called  # Воркер не должен запуститься


def test_apply_backup_cancelled(scan_tab, mock_group, mocker):
    mock_group.selected_count.return_value = 1
    scan_tab.groups = [mock_group]
    scan_tab.action_combo.setCurrentIndex(4)  # backup

    mocker.patch(
        "gui.scan_tab.QFileDialog.getExistingDirectory", return_value=""
    )
    mock_worker = mocker.patch("gui.scan_tab.ApplyWorker")

    scan_tab._apply()
    assert not mock_worker.called


def test_apply_success(scan_tab, mock_group, mocker):
    mock_group.selected_count.return_value = 1
    scan_tab.groups = [mock_group]
    scan_tab.action_combo.setCurrentIndex(2)  # symlink

    mock_worker = mocker.patch("gui.scan_tab.ApplyWorker")
    scan_tab._apply()

    assert scan_tab.btn_apply.isEnabled() is False
    assert mock_worker.called
    assert mock_worker.return_value.start.called


def test_on_apply_finished(scan_tab, mocker):
    mocker.patch("gui.scan_tab.ScanTab._populate")
    mock_info = mocker.patch("gui.scan_tab.QMessageBox.information")

    scan_tab._on_apply_finished(5, [])

    assert scan_tab.progress.isHidden() is True
    assert scan_tab.btn_apply.isEnabled() is True
    assert "Успешно обработано: 5" in mock_info.call_args[0][2]


# ==========================================
# 7. Сессии и Экспорт
# ==========================================


def test_save_sess(scan_tab, mock_group, mocker):
    scan_tab.groups = [mock_group]
    mocker.patch(
        "gui.scan_tab.QFileDialog.getSaveFileName",
        return_value=("C:\\sess.json", ""),
    )
    mock_save = mocker.patch("gui.scan_tab.save_session")
    mocker.patch("gui.scan_tab.build_session_from_groups")

    scan_tab._save_sess()
    assert mock_save.called


def test_load_sess(scan_tab, mocker, tmp_path):
    # Создаем реальный файл, чтобы Path.exists() вернул True
    real_file = tmp_path / "f.txt"
    real_file.touch()

    mock_session = MagicMock()
    mock_group = MagicMock()
    mock_group.files = [
        MagicMock(path=str(real_file)),
        MagicMock(path=str(real_file)),
    ]
    mock_session.groups = [mock_group]

    mocker.patch("gui.scan_tab.load_session", return_value=mock_session)
    mocker.patch(
        "gui.scan_tab.QFileDialog.getOpenFileName",
        return_value=("C:\\sess.json", ""),
    )
    mock_populate = mocker.patch("gui.scan_tab.ScanTab._populate")

    scan_tab._load_sess()
    assert mock_populate.called


def test_exp_csv(scan_tab, mock_group, mocker, tmp_path):
    scan_tab.groups = [mock_group]
    csv_file = tmp_path / "out.csv"
    mocker.patch(
        "gui.scan_tab.QFileDialog.getSaveFileName",
        return_value=(str(csv_file), ""),
    )

    # Мокаем stat для файлов группы
    mock_stat = MagicMock(st_size=100, st_ctime=1600000000.0)
    mocker.patch("pathlib.Path.stat", return_value=mock_stat)

    scan_tab._exp_csv()
    assert csv_file.exists()
    assert "hash1" in csv_file.read_text(encoding="utf-8")


def test_exp_html(scan_tab, mocker):
    mocker.patch(
        "gui.scan_tab.QFileDialog.getSaveFileName",
        return_value=("C:\\out.html", ""),
    )
    mock_exp = mocker.patch("gui.scan_tab.export_html")
    mocker.patch("gui.scan_tab.ScanTab._get_sess")

    scan_tab._exp_html()
    assert mock_exp.called


def test_exp_script(scan_tab, mock_group, mocker, tmp_path):
    scan_tab.groups = [mock_group]
    bat_file = tmp_path / "out.bat"
    mocker.patch(
        "gui.scan_tab.QFileDialog.getSaveFileName",
        return_value=(str(bat_file), ""),
    )

    scan_tab._exp_script()
    assert bat_file.exists()
    assert "del" in bat_file.read_text(encoding="utf-8")


# ==========================================
# 8. VirusTotal
# ==========================================


def test_check_vt_no_api_key(scan_tab, mock_group, mocker):
    scan_tab.groups = [mock_group]

    # Имитируем, что ключа нет
    mocker.patch("utils.settings.get_vt_api_key", return_value="")
    # Имитируем, что пользователь ввел ключ
    mocker.patch(
        "PySide6.QtWidgets.QInputDialog.getText",
        return_value=("new_key", True),
    )
    mock_set = mocker.patch("utils.settings.set_vt_api_key")

    mocker.patch("core.hasher.hash_file", return_value="hash123")

    # Возвращаем фейковый УСПЕШНЫЙ ответ (200), чтобы не срабатывал блок else
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {
            "attributes": {
                "last_analysis_stats": {
                    "harmless": 1,
                    "malicious": 0,
                    "suspicious": 0,
                }
            }
        }
    }
    mocker.patch("requests.get", return_value=mock_resp)

    #  Мокаем ВСЕ окна сообщений, чтобы они не вылезали на экран
    mocker.patch("gui.scan_tab.QMessageBox.information")
    mocker.patch("gui.scan_tab.QMessageBox.warning")

    scan_tab._check_vt()
    assert mock_set.called


def test_check_vt_success(scan_tab, mock_group, mocker):
    scan_tab.groups = [mock_group]
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


def test_check_vt_404(scan_tab, mock_group, mocker):
    scan_tab.groups = [mock_group]
    mocker.patch("utils.settings.get_vt_api_key", return_value="valid_key")
    mocker.patch("core.hasher.hash_file", return_value="hash123")

    mocker.patch("requests.get", return_value=MagicMock(status_code=404))
    mock_msg = mocker.patch("gui.scan_tab.QMessageBox.information")

    scan_tab._check_vt()
    assert "еще не загружен" in mock_msg.call_args[0][2]


def test_check_vt_error(scan_tab, mock_group, mocker):
    scan_tab.groups = [mock_group]
    mocker.patch("utils.settings.get_vt_api_key", return_value="valid_key")
    mocker.patch("core.hasher.hash_file", return_value="hash123")

    mocker.patch("requests.get", return_value=MagicMock(status_code=500))
    mock_warn = mocker.patch("gui.scan_tab.QMessageBox.warning")

    scan_tab._check_vt()
    assert mock_warn.called


def test_check_vt_exception(scan_tab, mock_group, mocker):
    scan_tab.groups = [mock_group]
    mocker.patch("utils.settings.get_vt_api_key", return_value="valid_key")
    mocker.patch("core.hasher.hash_file", return_value="hash123")

    mocker.patch("requests.get", side_effect=Exception("Network error"))
    mock_crit = mocker.patch("gui.scan_tab.QMessageBox.critical")

    scan_tab._check_vt()
    assert mock_crit.called


# ==========================================
# 9. Drag & Drop
# ==========================================


def test_drag_and_drop(scan_tab, mocker):
    mocker.patch("pathlib.Path.is_dir", return_value=True)

    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile("C:/DropFolder")])

    # ИСПРАВЛЕНО: Используем MagicMock вместо реальных событий
    drag_event = mocker.MagicMock()
    drag_event.mimeData.return_value = mime_data

    scan_tab.dragEnterEvent(drag_event)
    drag_event.acceptProposedAction.assert_called_once()

    drop_event = mocker.MagicMock()
    drop_event.mimeData.return_value = mime_data

    scan_tab.dropEvent(drop_event)
    assert scan_tab.path_edit.text() == "C:\\DropFolder"
    drop_event.acceptProposedAction.assert_called_once()
