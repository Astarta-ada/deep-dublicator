"""Тесты для реестра тем и генератора QSS (gui/theme.py)."""

import pytest

from gui.theme import (
    THEMES,
    DEFAULT_THEME,
    build_stylesheet,
    LIGHT_BLUE,
)

# ==========================================
# 1. Валидация данных (Проверка ключей)
# ==========================================


def test_default_theme_is_valid():
    """Проверяет, что тема по умолчанию существует в реестре."""
    assert DEFAULT_THEME in THEMES


def test_all_themes_have_required_keys():
    """
    Проверяет, что каждая тема содержит все ключи,
    которые используются в build_stylesheet.
    """
    # Список всех ключей, которые есть в базовой теме LIGHT_BLUE
    required_keys = set(LIGHT_BLUE.keys())

    for theme_key, theme_data in THEMES.items():
        missing_keys = required_keys - set(theme_data.keys())
        assert (
            not missing_keys
        ), f"В теме '{theme_key}' не хватает ключей: {missing_keys}"


def test_all_themes_have_name():
    """Проверяет, что у каждой темы есть человекочитаемое имя."""
    for theme_key, theme_data in THEMES.items():
        assert "name" in theme_data, f"У темы '{theme_key}' нет ключа 'name'"
        assert isinstance(theme_data["name"], str)
        assert len(theme_data["name"]) > 0


# ==========================================
# 2. Тесты генератора QSS
# ==========================================


def test_build_stylesheet_valid_theme():
    """Проверяет генерацию QSS для существующей темы."""
    qss = build_stylesheet("light_blue")

    # Проверяем, что это строка
    assert isinstance(qss, str)
    assert len(qss) > 1000  # Строка должна быть большой

    # Проверяем, что цвета из темы попали в QSS
    assert LIGHT_BLUE["primary"] in qss
    assert LIGHT_BLUE["bg"] in qss
    assert LIGHT_BLUE["text"] in qss

    # Проверяем наличие базовых селекторов
    assert "QWidget {" in qss
    assert "QPushButton {" in qss
    assert "QMenuBar {" in qss


def test_build_stylesheet_invalid_theme():
    """Проверяет, что при неверном ключе используется тема по умолчанию."""
    qss = build_stylesheet("ghost_theme_does_not_exist")

    # Должна вернуться строка (без исключений)
    assert isinstance(qss, str)

    # В ней должны быть цвета из DEFAULT_THEME (light_blue)
    default_colors = THEMES[DEFAULT_THEME]
    assert default_colors["primary"] in qss
    assert default_colors["bg"] in qss


def test_build_stylesheet_different_themes():
    """Проверяет, что для разных тем генерируются разные стили."""
    qss_light = build_stylesheet("light_blue")
    qss_dark = build_stylesheet("dark")

    # Строки должны различаться
    assert qss_light != qss_dark

    # Проверяем, что в каждой QSS есть характерные цвета для своей темы
    assert THEMES["light_blue"]["primary"] in qss_light
    assert THEMES["dark"]["primary"] in qss_dark

    # Проверяем уникальный цвет фона (bg) для темной темы
    assert THEMES["dark"]["bg"] in qss_dark
    assert THEMES["light_blue"]["bg"] in qss_light
