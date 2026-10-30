"""Тесты для менеджера тем (gui/theme_manager.py)."""

import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication

from gui.theme_manager import ThemeManager
from gui.theme import DEFAULT_THEME, THEMES

# ==========================================
# Фикстуры
# ==========================================


@pytest.fixture(autouse=True)
def clean_singleton():
    """Сбрасывает синглтон перед каждым тестом, чтобы тесты не влияли друг на друга."""
    ThemeManager._instance = None
    yield
    ThemeManager._instance = None


@pytest.fixture
def mock_settings(mocker):
    """Мокает QSettings, чтобы не трогать реальные настройки Windows."""
    mock = mocker.patch("gui.theme_manager.QSettings")
    # По умолчанию возвращаем сохраненную тему "dark"
    mock.return_value.value.return_value = "dark"
    return mock


# ==========================================
# 1. Тесты инициализации
# ==========================================


def test_singleton(mock_settings):
    """Проверяет, что возвращается один и тот же экземпляр."""
    tm1 = ThemeManager.instance()
    tm2 = ThemeManager.instance()
    assert tm1 is tm2


def test_init_loads_saved_theme(mock_settings):
    """Проверяет, что при создании загружается тема из QSettings."""
    mock_settings.return_value.value.return_value = "proton"

    tm = ThemeManager.instance()
    assert tm.current == "proton"


def test_init_invalid_theme_fallback(mock_settings):
    """Проверяет, что при неверной теме ставится дефолтная."""
    mock_settings.return_value.value.return_value = "invalid_theme_key"

    tm = ThemeManager.instance()
    assert tm.current == DEFAULT_THEME


# ==========================================
# 2. Тесты применения темы
# ==========================================


def test_available_themes(mock_settings):
    """Проверяет, что возвращается словарь всех тем."""
    tm = ThemeManager.instance()
    available = tm.available()

    assert isinstance(available, dict)
    assert len(available) == len(THEMES)
    assert "dark" in available


def test_apply_theme(mock_settings, mocker):
    """Проверяет, что при применении темы устанавливается стиль и сохраняются настройки."""
    tm = ThemeManager.instance()

    mock_app = mocker.patch.object(QApplication.instance(), "setStyleSheet")
    mock_signal = mocker.patch.object(tm, "theme_changed")

    tm.apply("light_blue")

    assert tm.current == "light_blue"
    assert mock_app.called
    mock_settings.return_value.setValue.assert_called_with(
        "ui/theme", "light_blue"
    )
    assert mock_signal.emit.called


def test_apply_invalid_theme(mock_settings, mocker):
    """Проверяет, что при попытке применить несуществующую тему ничего не ломается."""
    tm = ThemeManager.instance()
    mock_app = mocker.patch.object(QApplication.instance(), "setStyleSheet")
    mock_log = mocker.patch("gui.theme_manager.log.warning")

    tm.apply("ghost_theme")

    assert tm.current != "ghost_theme"
    assert not mock_app.called
    assert mock_log.called


def test_apply_no_qapp(mock_settings, mocker):
    """Покрывает случай, если QApplication еще не создан (ошибка в логе)."""
    mocker.patch("gui.theme_manager.QApplication.instance", return_value=None)
    mock_log = mocker.patch("gui.theme_manager.log.error")

    tm = ThemeManager.instance()
    tm.apply("dark")

    assert mock_log.called


def test_apply_saved(mock_settings, mocker):
    """Проверяет, что apply_saved вызывает apply с текущей темой."""
    tm = ThemeManager.instance()
    mock_apply = mocker.patch.object(tm, "apply")

    tm.apply_saved()
    mock_apply.assert_called_with(tm.current)
