"""Тесты для диалоговых окон (gui/dialogs.py)."""

import pytest
from pathlib import Path
from PySide6.QtGui import QPixmap, QColor, QPaintEvent
from PySide6.QtCore import QRect

from gui.dialogs import (
    DiffDialog,
    ImageSlider,
    SliderDialog,
    HistoryDialog,
    AboutDialog,
)
from utils.config import APP_NAME

# ==========================================
# 1. Тесты для DiffDialog
# ==========================================


def test_diff_dialog_identical(qtbot, tmp_path):
    """Проверяет, что для одинаковых файлов показывается правильный статус."""
    f1 = tmp_path / "file1.txt"
    f2 = tmp_path / "file2.txt"
    f1.write_text("line1\nline2\n", encoding="utf-8")
    f2.write_text("line1\nline2\n", encoding="utf-8")

    dlg = DiffDialog(f1, f2)
    qtbot.addWidget(dlg)

    assert "идентичны" in dlg._status.text()
    assert dlg._left.toPlainText() == "line1\nline2\n"


def test_diff_dialog_different(qtbot, tmp_path):
    """Проверяет подсчет добавленных и удаленных строк."""
    f1 = tmp_path / "file1.txt"
    f2 = tmp_path / "file2.txt"
    f1.write_text("line1\nline2\n", encoding="utf-8")
    f2.write_text("line1\nline3\nline4\n", encoding="utf-8")

    dlg = DiffDialog(f1, f2)
    qtbot.addWidget(dlg)

    status = dlg._status.text()
    # В f2 добавилась line4 (1 добавление) и line2 заменилась на line3 (1 добавление, 1 удаление)
    # difflib может считать это как -1 / +2
    assert "отличаются" in status
    assert "+" in status
    assert "-" in status


def test_diff_dialog_oserror(qtbot, tmp_path):
    """Покрывает ветку except OSError при чтении файлов."""
    f1 = tmp_path / "ghost1.txt"
    f2 = tmp_path / "ghost2.txt"
    # Файлы не создаем, чтобы вызвать ошибку

    dlg = DiffDialog(f1, f2)
    qtbot.addWidget(dlg)

    assert "Ошибка чтения файлов" in dlg._status.text()


# ==========================================
# 2. Тесты для ImageSlider и SliderDialog
# ==========================================


@pytest.fixture
def dummy_pixmaps():
    """Создает два цветных QPixmap для тестов."""
    pix1 = QPixmap(100, 100)
    pix1.fill(QColor("red"))

    pix2 = QPixmap(100, 100)
    pix2.fill(QColor("blue"))
    return pix1, pix2


def test_image_slider(qtbot, dummy_pixmaps):
    """Проверяет логику виджета слайдера и отрисовку."""
    pix1, pix2 = dummy_pixmaps
    slider = ImageSlider(pix1, pix2)
    qtbot.addWidget(slider)

    # ИСПРАВЛЕНО: виджет масштабируется до 800 пикселей в ширину
    assert slider.pos == 50
    assert slider.width() == 800

    # Меняем позицию
    slider.set_pos(80)
    assert slider.pos == 80

    # Вызываем paintEvent напрямую для покрытия (чтобы не ждать отрисовки окна)
    event = QPaintEvent(QRect(0, 0, 800, 800))
    slider.paintEvent(event)


def test_slider_dialog(qtbot, tmp_path, dummy_pixmaps):
    """Проверяет диалоговое окно со слайдером и покрывает отрисовку."""
    # Сохраняем пиксмапы как файлы, так как SliderDialog принимает пути
    img1 = tmp_path / "img1.png"
    img2 = tmp_path / "img2.png"
    dummy_pixmaps[0].save(str(img1))
    dummy_pixmaps[1].save(str(img2))

    dlg = SliderDialog(str(img1), str(img2))
    qtbot.addWidget(dlg)

    assert dlg.windowTitle() == "Сравнение фото (Слайдер)"
    assert hasattr(dlg, "slider_widget")

    # Явно вызываем paintEvent для покрытия строк отрисовки
    event = QPaintEvent(QRect(0, 0, 800, 800))
    dlg.slider_widget.paintEvent(event)


# ==========================================
# 3. Тесты для HistoryDialog
# ==========================================


def test_history_dialog(qtbot, mocker):
    """Проверяет заполнение списка истории операций."""
    # Мокаем функцию, чтобы не читать реальную БД
    mock_history = [
        (
            1,
            "2023-01-01T12:00:00",
            "backup",
            "C:/file.txt",
            1024,
            '{"backup_path": "C:/bkp"}',
            0,
        ),
        (
            2,
            "2023-01-02T12:00:00",
            "delete_hard",
            "C:/other.txt",
            2048,
            None,
            0,
        ),
    ]
    mocker.patch("gui.dialogs.get_history", return_value=mock_history)

    dlg = HistoryDialog(None)
    qtbot.addWidget(dlg)

    # Находим QListWidget внутри диалога
    list_widget = dlg.findChild(
        type(dlg.children()[1])
    )  # Ищем первый QListWidget
    # Лучше использовать QListWidget напрямую, но мы знаем структуру
    from PySide6.QtWidgets import QListWidget

    list_widget = dlg.findChild(QListWidget)

    assert list_widget.count() == 2

    assert "1.0 KB" in list_widget.item(0).text()
    assert dlg.lst.count() == 2
    assert "BACKUP" in dlg.lst.item(0).text()
    assert "DELETE_HARD" in dlg.lst.item(1).text()

    # При выборе backup кнопка отмены должна быть активна
    dlg.lst.setCurrentRow(0)
    assert dlg.btn_undo.isEnabled() is True

    # При выборе delete_hard кнопка отмены НЕ активна (его нельзя отменить)
    dlg.lst.setCurrentRow(1)
    assert dlg.btn_undo.isEnabled() is False


# ==========================================
# 4. Тесты для AboutDialog
# ==========================================


def test_about_dialog(qtbot):
    """Проверяет окно 'О программе'."""
    dlg = AboutDialog()
    qtbot.addWidget(dlg)

    assert dlg.windowTitle() == "О программе"

    # Проверяем, что на форме есть название приложения и ссылка на GitHub
    from PySide6.QtWidgets import QLabel

    labels = dlg.findChildren(QLabel)

    text_content = "".join([lbl.text() for lbl in labels])
    assert APP_NAME in text_content
    assert "Aleksandr Diuzhev" in text_content
    assert "github.com/Astarta-ada/deep-dublicator" in text_content
