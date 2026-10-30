"""Тесты для панели фильтрации результатов (gui/result_filter_bar.py)."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from PySide6.QtCore import Qt

from gui.result_filter_bar import ResultFilterBar

# ==========================================
# Фикстуры
# ==========================================


@pytest.fixture
def mock_settings(mocker):
    """Мокает модуль user_settings, чтобы не трогать реальный реестр."""
    mock = mocker.patch("gui.result_filter_bar.user_settings")
    mock.get_min_savings_bytes.return_value = (
        5 * 1024 * 1024
    )  # По умолчанию 5 МБ
    return mock


@pytest.fixture
def filter_bar(qtbot, mock_settings):
    """Создает виджет с замоканными настройками."""
    bar = ResultFilterBar()
    qtbot.addWidget(bar)
    return bar


# ==========================================
# 1. Тесты инициализации
# ==========================================


def test_initial_state(filter_bar, mock_settings):
    """Проверяет, что значение подгружается из настроек."""
    # В настройках 5 МБ, значит спинбокс должен показывать 5
    assert filter_bar.min_savings.value() == 5
    assert filter_bar.search.text() == ""

    # Проверяем хелперы
    assert filter_bar.min_savings_bytes() == 5 * 1024 * 1024
    assert filter_bar.search_text() == ""


# ==========================================
# 2. Тесты изменения значений (Сохранение и Сигналы)
# ==========================================


def test_on_changed_saves_settings(filter_bar, mock_settings, qtbot):
    """Проверяет, что при изменении спинбокса настройки сохраняются."""
    # Меняем значение на 10 МБ
    filter_bar.min_savings.setValue(10)

    # Проверяем, что вызвался метод сохранения (10 МБ в байтах)
    mock_settings.set_min_savings_bytes.assert_called_with(10 * 1024 * 1024)


def test_on_changed_emits_signal(filter_bar, qtbot):
    """Проверяет, что изменения отправляют сигнал."""
    with qtbot.waitSignal(filter_bar.filters_changed, timeout=100):
        filter_bar.search.setText("test")


# ==========================================
# 3. Тесты сброса (Кнопка)
# ==========================================


def test_clear_button(filter_bar, mock_settings, qtbot):
    """Проверяет, что кнопка сбрасывает фильтры."""
    # Устанавливаем какие-то значения
    filter_bar.min_savings.setValue(100)
    filter_bar.search.setText("hello")

    # Находим кнопку и кликаем
    from PySide6.QtWidgets import QPushButton

    btn = filter_bar.findChild(QPushButton)
    (
        qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
        if hasattr(Qt, "MouseButton")
        else btn.click()
    )

    # Проверяем, что всё сбросилось
    assert filter_bar.min_savings.value() == 0
    assert filter_bar.search.text() == ""

    # И настройки сохранились как 0
    mock_settings.set_min_savings_bytes.assert_called_with(0)


# ==========================================
# 4. Тесты логики фильтрации (matches)
# ==========================================


def test_matches_size_threshold(filter_bar):
    """Проверяет фильтрацию по размеру экономии."""
    filter_bar.min_savings.setValue(10)  # 10 МБ

    # 5 МБ (меньше порога) - должно быть False
    assert filter_bar.matches(5 * 1024 * 1024, []) is False

    # 15 МБ (больше порога) - должно быть True
    assert filter_bar.matches(15 * 1024 * 1024, []) is True

    # Ровно 10 МБ - должно быть True (>=)
    assert filter_bar.matches(10 * 1024 * 1024, []) is True


def test_matches_search_text(filter_bar):
    """Проверяет фильтрацию по подстроке в пути."""
    filter_bar.min_savings.setValue(0)  # Сбрасываем размер
    filter_bar.search.setText("documents")

    paths1 = [Path("C:/Users/user/Documents/file.txt")]
    paths2 = [Path("C:/Windows/system32.dll")]

    # Совпадение есть
    assert filter_bar.matches(0, paths1) is True

    # Совпадения нет
    assert filter_bar.matches(0, paths2) is False

    # Регистронезависимость (вводим "DOCUMENTS", а в пути "documents")
    filter_bar.search.setText("DOCUMENTS")
    assert filter_bar.matches(0, paths1) is True


def test_matches_combined(filter_bar):
    """Проверяет совместную работу размера и поиска."""
    filter_bar.min_savings.setValue(10)
    filter_bar.search.setText("photo")

    # 15 МБ и путь содержит "photo" -> True
    assert (
        filter_bar.matches(15 * 1024 * 1024, [Path("/photos/img.jpg")]) is True
    )

    # 5 МБ и путь содержит "photo" -> False (не прошел по размеру)
    assert (
        filter_bar.matches(5 * 1024 * 1024, [Path("/photos/img.jpg")]) is False
    )

    # 15 МБ, но путь НЕ содержит "photo" -> False
    assert (
        filter_bar.matches(15 * 1024 * 1024, [Path("/docs/img.jpg")]) is False
    )
