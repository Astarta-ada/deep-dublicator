"""Тесты для панели фильтров (gui/filter_panel.py)."""

import pytest
from PySide6.QtWidgets import QSpinBox

from gui.filter_panel import FilterPanel
from utils.constants import CATEGORIES

# ==========================================
# Фикстура
# ==========================================


@pytest.fixture
def filter_panel(qtbot):
    panel = FilterPanel()
    qtbot.addWidget(panel)
    return panel


# ==========================================
# 1. Тесты инициализации и пресетов
# ==========================================


def test_initial_state(filter_panel):
    """Проверяет значения по умолчанию."""
    assert filter_panel.preset_combo.currentIndex() == 0
    assert filter_panel.preset_combo.currentText() == "— выбрать пресет —"
    assert filter_panel.ext_edit.text() == ""

    # По умолчанию: мин 1 байт, макс ∞ (0)
    assert filter_panel.min_size_spin.value() == 1
    assert filter_panel.max_size_spin.value() == 0
    assert filter_panel.include_empty_cb.isChecked() is False

    # Проверяем методы-хелперы
    assert filter_panel.get_extensions() == set()
    assert filter_panel.get_min_size() == 1
    assert filter_panel.get_max_size() is None
    assert filter_panel.include_empty() is False


def test_presets_available(filter_panel):
    """Проверяет, что все категории из CATEGORIES попали в выпадающий список."""
    # В списке должно быть "— выбрать пресет —" + количество категорий
    expected_count = 1 + len(CATEGORIES)
    assert filter_panel.preset_combo.count() == expected_count


def test_apply_preset(filter_panel):
    """Проверяет применение пресета (например, 'Изображения')."""
    # Выбираем пресет (индекс 1, так как 0 - это заглушка)
    filter_panel.preset_combo.setCurrentIndex(1)

    # В ext_edit должна появиться строка с расширениями
    ext_text = filter_panel.ext_edit.text()
    assert len(ext_text) > 0

    # Проверяем, что парсинг работает корректно
    exts = filter_panel.get_extensions()
    assert ".jpg" in exts or ".png" in exts  # Зависит от первой категории


def test_apply_empty_preset(filter_panel):
    """Проверяет, что выбор заглушки не меняет поле расширений."""
    filter_panel.ext_edit.setText(".custom")
    filter_panel.preset_combo.setCurrentIndex(0)  # Выбираем заглушку

    assert filter_panel.ext_edit.text() == ".custom"


# ==========================================
# 2. Тесты ручного ввода и размеров
# ==========================================


def test_manual_extensions(filter_panel):
    """Проверяет ручной ввод расширений."""
    filter_panel.ext_edit.setText("jpg, .PNG, txt")
    exts = filter_panel.get_extensions()

    assert exts == {".jpg", ".png", ".txt"}
    assert filter_panel.as_dict()["extensions"] == [".jpg", ".png", ".txt"]


def test_size_filters(filter_panel):
    """Проверяет логику минимального и максимального размера."""
    # Устанавливаем минимальный 100 байт
    filter_panel.min_size_spin.setValue(100)
    assert filter_panel.get_min_size() == 100

    # Устанавливаем максимальный 5000 байт
    filter_panel.max_size_spin.setValue(5000)
    assert filter_panel.get_max_size() == 5000

    # Устанавливаем максимальный 0 (что означает ∞)
    filter_panel.max_size_spin.setValue(0)
    assert filter_panel.get_max_size() is None


# ==========================================
# 3. Тесты логики пустых файлов
# ==========================================


def test_include_empty_logic(filter_panel):
    """Проверяет, что галочка 'Пустые файлы' сбрасывает минимальный размер в 0."""
    # По умолчанию мин. размер 1, галочка не стоит
    filter_panel.min_size_spin.setValue(500)
    assert filter_panel.get_min_size() == 500

    # Ставим галочку
    filter_panel.include_empty_cb.setChecked(True)
    assert filter_panel.include_empty() is True

    # Теперь get_min_size должен вернуть 0, несмотря на то, что в спинбоксе 500
    assert filter_panel.get_min_size() == 0

    # Снимаем галочку
    filter_panel.include_empty_cb.setChecked(False)
    assert (
        filter_panel.get_min_size() == 500
    )  # Возвращается к значению спинбокса


# ==========================================
# 4. Тесты экспорта в словарь (as_dict)
# ==========================================


def test_as_dict(filter_panel):
    """Проверяет сборку всех настроек в словарь."""
    filter_panel.ext_edit.setText(".txt")
    filter_panel.min_size_spin.setValue(10)
    filter_panel.max_size_spin.setValue(100)
    filter_panel.include_empty_cb.setChecked(False)

    result = filter_panel.as_dict()

    assert result == {
        "extensions": [".txt"],
        "min_size": 10,
        "max_size": 100,
        "include_empty": False,
    }
