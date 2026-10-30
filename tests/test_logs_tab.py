"""Тесты для вкладки с логами (gui/logs_tab.py)."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QPlainTextEdit

from gui.logs_tab import LogsTab

# ==========================================
# Фикстуры
# ==========================================


@pytest.fixture
def logs_tab(qtbot):
    tab = LogsTab()
    qtbot.addWidget(tab)
    return tab


# ==========================================
# 1. Тесты интерфейса
# ==========================================


def test_initial_state(logs_tab):
    """Проверяет начальные настройки текстового поля и наличие элементов."""
    # Поле должно быть только для чтения
    assert logs_tab.text_edit.isReadOnly() is True

    # Перенос строк должен быть отключен (NoWrap) — ИСПРАВЛЕНО ЗДЕСЬ
    assert (
        logs_tab.text_edit.lineWrapMode() == QPlainTextEdit.LineWrapMode.NoWrap
    )

    # Шрифт должен быть Consolas
    assert logs_tab.text_edit.font().family() == "Consolas"
    assert logs_tab.text_edit.font().pointSize() == 10

    # Проверяем, что кнопка очистки существует
    btn = logs_tab.findChild(QPushButton)
    assert btn is not None
    assert btn.text() == "Очистить логи"


# ==========================================
# 2. Тесты добавления логов и автоскролла
# ==========================================


def test_append_log(logs_tab):
    """Проверяет добавление текста."""
    logs_tab.append_log("Тестовое сообщение 1")
    logs_tab.append_log("Тестовое сообщение 2")

    text = logs_tab.text_edit.toPlainText()
    assert "Тестовое сообщение 1" in text
    assert "Тестовое сообщение 2" in text


def test_auto_scroll(logs_tab):
    """Проверяет, что при добавлении большого текста скролл прокручивается вниз."""
    # Искусственно делаем виджет маленьким, чтобы появился скроллбар
    logs_tab.resize(100, 50)

    # Добавляем много строк
    for i in range(100):
        logs_tab.append_log(f"Строка лога номер {i}")

    sb = logs_tab.text_edit.verticalScrollBar()
    # Скроллбар должен быть в самом низу
    assert sb.value() == sb.maximum()
    # Максимум должен быть больше 0 (текст не влез в экран)
    assert sb.maximum() > 0


# ==========================================
# 3. Тесты очистки
# ==========================================


def test_clear_button(qtbot, logs_tab):
    """Проверяет, что кнопка очищает текстовое поле."""
    logs_tab.append_log("Текст, который надо удалить")
    assert logs_tab.text_edit.toPlainText() != ""

    # Находим кнопку и кликаем по ней
    btn = logs_tab.findChild(QPushButton)
    qtbot.mouseClick(btn, Qt.LeftButton)

    assert logs_tab.text_edit.toPlainText() == ""
