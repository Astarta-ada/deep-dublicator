"""Тесты для моделей данных и делегатов (gui/models.py)."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from PySide6.QtCore import Qt, QPoint, QModelIndex, QRect
from PySide6.QtGui import QStandardItemModel, QMouseEvent
from PySide6.QtWidgets import QStyleOptionViewItem

from gui.models import DuplicateItem, DuplicateDelegate
from utils.constants import ROLE_IS_ORIGINAL, ROLE_IS_CHECKED


def test_duplicate_item():
    item = DuplicateItem("Test", path=Path("C:/file.txt"))
    assert item.text() == "Test"
    assert item.path == Path("C:/file.txt")
    assert item.is_group is False
    assert item.is_category is False
    # Проверяем, что флаг интерактивности установлен
    assert item.flags() & Qt.ItemIsUserCheckable


def test_duplicate_delegate_editor_event_radio(qtbot, mocker):
    delegate = DuplicateDelegate()
    model = QStandardItemModel()

    # Создаем группу (родителя)
    parent = DuplicateItem("Group", is_group=True)
    model.appendRow(parent)

    # Создаем два файла внутри
    item1 = DuplicateItem("File1", path=Path("f1"))
    item1.setData(True, ROLE_IS_ORIGINAL)
    parent.appendRow(item1)

    item2 = DuplicateItem("File2", path=Path("f2"))
    item2.setData(False, ROLE_IS_ORIGINAL)
    parent.appendRow(item2)

    index2 = item2.index()
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 100, 20)

    event = mocker.MagicMock()
    event.type.return_value = QMouseEvent.MouseButtonRelease
    event.position.return_value.toPoint.return_value.x.return_value = 10

    result = delegate.editorEvent(event, model, option, index2)

    assert result is True
    # Оригинал переключился на второй файл
    assert item1.data(ROLE_IS_ORIGINAL) is False
    assert item2.data(ROLE_IS_ORIGINAL) is True
    assert item2.data(ROLE_IS_CHECKED) is False


def test_duplicate_delegate_editor_event_checkbox(qtbot, mocker):
    delegate = DuplicateDelegate()
    model = QStandardItemModel()

    item = DuplicateItem("File", path=Path("f1"))
    item.setData(False, ROLE_IS_ORIGINAL)
    item.setData(False, ROLE_IS_CHECKED)
    model.appendRow(item)

    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 100, 20)

    event = mocker.MagicMock()
    event.type.return_value = QMouseEvent.MouseButtonRelease
    event.position.return_value.toPoint.return_value.x.return_value = 40

    result = delegate.editorEvent(event, model, option, item.index())

    assert result is True
    assert item.data(ROLE_IS_CHECKED) is True


def test_duplicate_delegate_editor_event_original_checkbox(qtbot, mocker):
    """Проверяет, что чекбокс оригинала нельзя нажать."""
    delegate = DuplicateDelegate()
    model = QStandardItemModel()

    item = DuplicateItem("File", path=Path("f1"))
    item.setData(True, ROLE_IS_ORIGINAL)  # Это оригинал
    model.appendRow(item)

    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 100, 20)

    event = mocker.MagicMock()
    event.type.return_value = QMouseEvent.MouseButtonRelease
    event.position.return_value.toPoint.return_value.x.return_value = (
        40  # Клик по чекбоксу
    )

    result = delegate.editorEvent(event, model, option, item.index())
    assert result is False  # Клик проигнорирован
    assert item.data(ROLE_IS_CHECKED) is None
