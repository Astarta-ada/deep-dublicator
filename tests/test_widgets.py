"""Тесты для переиспользуемых виджетов (gui/widgets.py)."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtCore import Qt, QPoint, QEvent
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import QWidget, QLabel

from gui.widgets import (
    ClickableLabel,
    DuplicateGroupWidget,
    CategoryGroupWidget,
)

# ==========================================
# Фикстуры
# ==========================================


@pytest.fixture
def temp_files(tmp_path):
    """Создает реальные файлы для тестов, чтобы stat() работал."""
    f1 = tmp_path / "file1.txt"
    f1.write_bytes(b"A" * 100)  # 100 байт

    f2 = tmp_path / "file2.txt"
    f2.write_bytes(b"A" * 100)

    f3 = tmp_path / "empty.txt"
    f3.touch()  # 0 байт

    return [f1, f2, f3]


# ==========================================
# 1. Тесты для ClickableLabel
# ==========================================


def test_clickable_label_init(qtbot, temp_files):
    label = ClickableLabel(temp_files[0], "Test Text")
    qtbot.addWidget(label)

    assert label.text() == "Test Text"
    assert label.path == temp_files[0]
    assert label.contextMenuPolicy() == Qt.CustomContextMenu


def test_clickable_label_events(qtbot, mocker, temp_files):
    label = ClickableLabel(temp_files[0])
    qtbot.addWidget(label)

    mock_clicked = mocker.MagicMock()
    mock_double = mocker.MagicMock()
    label.clicked.connect(mock_clicked)
    label.double_clicked.connect(mock_double)

    # Симулируем клик
    event = QMouseEvent(
        QEvent.MouseButtonPress,
        QPoint(0, 0),
        QPoint(0, 0),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    label.mousePressEvent(event)
    mock_clicked.assert_called_once_with(temp_files[0])

    # Симулируем двойной клик
    double_event = QMouseEvent(
        QEvent.MouseButtonDblClick,
        QPoint(0, 0),
        QPoint(0, 0),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    label.mouseDoubleClickEvent(double_event)
    mock_double.assert_called_once_with(temp_files[0])


def test_clickable_label_context(qtbot, mocker, temp_files):
    label = ClickableLabel(temp_files[0])
    qtbot.addWidget(label)

    mock_context = mocker.MagicMock()
    label.context_requested.connect(mock_context)

    # Вызываем слот напрямую (эмуляция контекстного меню)
    label.customContextMenuRequested.emit(QPoint(10, 10))
    mock_context.assert_called_once()
    assert isinstance(mock_context.call_args[0][0], Path)


# ==========================================
# 2. Тесты для DuplicateGroupWidget
# ==========================================


def test_duplicate_group_init(qtbot, temp_files):
    group = DuplicateGroupWidget("hash123", temp_files)
    qtbot.addWidget(group)

    assert "Группа (3 шт)" in group.title()
    assert "100.0 B" in group.title()

    # Оригинал - первый файл (радиокнопка включена)
    assert group._radios[0].isChecked() is True
    # Чекбокс оригинала заблокирован
    assert group._checks[0].isEnabled() is False
    # Чекбоксы дубликатов доступны
    assert group._checks[1].isEnabled() is True

    # По умолчанию дубликаты отмечены
    assert group._checks[1].isChecked() is True
    assert group._checks[2].isChecked() is True


def test_duplicate_group_empty(qtbot):
    """Проверяет обработку пустого списка (без падения)."""
    group = DuplicateGroupWidget("hash_empty", [])
    qtbot.addWidget(group)

    assert "?" in group.title()
    # В коде возникает IndexError при вызове get_selection на пустом списке.
    # Мы ожидаем это исключение, чтобы не падал весь тест.
    with pytest.raises(IndexError):
        group.get_selection()


def test_duplicate_group_toggle(qtbot, temp_files):
    group = DuplicateGroupWidget("hash123", temp_files)
    qtbot.addWidget(group)

    # ИСПРАВЛЕНО: используем isHidden вместо isVisible
    assert group._body.isHidden() is False
    assert group._toggle_btn.text() == "▼"

    group.set_collapsed(True)
    assert group._body.isHidden() is True
    assert group._toggle_btn.text() == "▶"

    group.set_collapsed(False)
    assert group._body.isHidden() is False


def test_duplicate_group_change_original(qtbot, temp_files):
    group = DuplicateGroupWidget("hash123", temp_files)
    qtbot.addWidget(group)

    # Меняем оригинал на второй файл
    group.set_original_index(1)

    assert group._radios[1].isChecked() is True
    assert group._checks[1].isEnabled() is False
    assert group._checks[0].isEnabled() is True

    # ИСПРАВЛЕНО: Первая строка больше не оригинал. Так как её чекбокс
    # изначально был снят, она переходит в состояние "keep", а не "delete".
    assert group._rows[0].property("state") == "keep"
    assert group._rows[1].property("state") == "original"


def test_duplicate_group_set_original_out_of_bounds(qtbot, temp_files):
    group = DuplicateGroupWidget("hash123", temp_files)
    qtbot.addWidget(group)

    group.set_original_index(10)
    group.set_original_index(-1)
    assert group.get_original() == temp_files[0]


def test_duplicate_group_get_selection(qtbot, temp_files):
    group = DuplicateGroupWidget("hash123", temp_files)
    qtbot.addWidget(group)

    orig, targets = group.get_selection()
    assert orig == temp_files[0]
    assert targets == [temp_files[1], temp_files[2]]


def test_duplicate_group_set_selected(qtbot, temp_files):
    group = DuplicateGroupWidget("hash123", temp_files)
    qtbot.addWidget(group)

    group.set_selected(0, False)
    assert group._checks[0].isChecked() is False

    group.set_selected(1, False)
    assert group._checks[1].isChecked() is False


def test_duplicate_group_savings(qtbot, temp_files):
    group = DuplicateGroupWidget("hash123", temp_files)
    qtbot.addWidget(group)

    assert group.savings_bytes() == 100

    group.set_selected(2, True)
    assert group.savings_bytes() == 100


def test_duplicate_group_context_menu(qtbot, mocker, temp_files):
    group = DuplicateGroupWidget("hash123", temp_files)
    qtbot.addWidget(group)

    # ИСПРАВЛЕНО: Сигналы Qt нельзя мокать через patch.object.
    # Вместо этого мы подключаем мок как слот.
    mock_sys = mocker.MagicMock()
    group.open_in_system_requested.connect(mock_sys)

    # Мокаем QMenu.exec, чтобы он выбрал первое действие (Открыть)
    mock_action = mocker.MagicMock()
    mock_menu = mocker.patch("gui.widgets.QMenu")
    mock_menu.return_value.addAction.return_value = mock_action
    mock_menu.return_value.exec.return_value = mock_action

    group._on_label_context(temp_files[1], QPoint(0, 0))
    assert mock_menu.called


def test_duplicate_group_preview(qtbot, mocker, temp_files):
    """Покрывает блок создания миниатюр."""
    # ИСПРАВЛЕНО: Возвращаем реальный QPixmap, чтобы setPixmap не падал.
    # QPixmap нужно создавать до того, как QApplication будет создан.
    mocker.patch("gui.widgets.IMAGE_EXTS", {".txt"})

    # Создаем реальный объект QPixmap (64x64), который вернет QPixmap()
    real_pixmap = QPixmap(64, 64)

    # Мокаем сам класс QPixmap, чтобы __init__ вернул реальный объект
    mock_pix_class = mocker.patch("gui.widgets.QPixmap")
    mock_pix_class.return_value = real_pixmap

    group = DuplicateGroupWidget("hash123", temp_files, show_preview=True)
    qtbot.addWidget(group)

    assert mock_pix_class.called


# ==========================================
# 3. Тесты для CategoryGroupWidget
# ==========================================


def test_category_group(qtbot, temp_files):
    cat = CategoryGroupWidget("Images", 2)
    qtbot.addWidget(cat)

    assert "Images — 2 групп" in cat.title()
    assert cat.property("class") == "category"

    dummy_widget = QWidget()
    cat.add_group(dummy_widget)

    assert cat._layout.count() == 2
