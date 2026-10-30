"""Тесты для обертки над QSettings (utils/settings.py)."""

import pytest
from unittest.mock import MagicMock

from utils import settings

# ==========================================
# Фикстуры
# ==========================================


@pytest.fixture
def mock_settings(mocker):
    """Мокает функцию _settings(), возвращая фейковый QSettings."""
    mock = mocker.patch("utils.settings._settings")
    return mock.return_value


# ==========================================
# 1. Тесты последней папки
# ==========================================


def test_get_last_dir(mock_settings):
    mock_settings.value.return_value = "C:/MyFolder"
    assert settings.get_last_dir() == "C:/MyFolder"


def test_set_last_dir(mock_settings):
    settings.set_last_dir("C:/MyFolder")
    mock_settings.setValue.assert_called_with("scan/last_dir", "C:/MyFolder")


# ==========================================
# 2. Тесты недавних сессий
# ==========================================


def test_get_recent_sessions_list(mock_settings):
    """Проверяет чтение, когда QSettings возвращает список."""
    mock_settings.value.return_value = ["C:/sess1.json", "C:/sess2.json"]
    assert settings.get_recent_sessions() == ["C:/sess1.json", "C:/sess2.json"]


def test_get_recent_sessions_string(mock_settings):
    """Проверяет чтение, когда QSettings возвращает строку (так бывает в реестре Windows)."""
    mock_settings.value.return_value = "C:/sess1.json"
    assert settings.get_recent_sessions() == ["C:/sess1.json"]


def test_get_recent_sessions_empty(mock_settings):
    """Проверяет чтение, когда список пуст или None."""
    mock_settings.value.return_value = []
    assert settings.get_recent_sessions() == []

    mock_settings.value.return_value = None
    assert settings.get_recent_sessions() == []


def test_push_recent_session_new(mock_settings):
    """Проверяет добавление новой сессии."""
    mock_settings.value.return_value = ["C:/old.json"]

    settings.push_recent_session("C:/new.json")
    mock_settings.setValue.assert_called_with(
        "sessions/recent", ["C:/new.json", "C:/old.json"]
    )


def test_push_recent_session_existing(mock_settings):
    """Проверяет, что существующая сессия перемещается в начало (без дубликатов)."""
    mock_settings.value.return_value = ["C:/old1.json", "C:/old2.json"]

    settings.push_recent_session("C:/old2.json")
    mock_settings.setValue.assert_called_with(
        "sessions/recent", ["C:/old2.json", "C:/old1.json"]
    )


def test_push_recent_session_limit(mock_settings):
    """Проверяет, что список обрезается до max_items (8)."""
    # Создаем 8 элементов
    mock_settings.value.return_value = [f"C:/sess{i}.json" for i in range(8)]

    settings.push_recent_session("C:/new.json")

    # Должно остаться 8 элементов, новый в начале, последний отвалился
    called_args = mock_settings.setValue.call_args[0][1]
    assert len(called_args) == 8
    assert called_args[0] == "C:/new.json"
    assert "C:/sess7.json" not in called_args


# ==========================================
# 3. Тесты порога экономии
# ==========================================


def test_get_min_savings_bytes_valid(mock_settings):
    mock_settings.value.return_value = "1024"
    assert settings.get_min_savings_bytes() == 1024


def test_get_min_savings_bytes_invalid(mock_settings):
    """Покрывает except (TypeError, ValueError), если в настройках мусор."""
    mock_settings.value.return_value = "not_a_number"
    assert settings.get_min_savings_bytes() == 0

    mock_settings.value.return_value = None  # int(None) вызовет TypeError
    assert settings.get_min_savings_bytes() == 0


def test_set_min_savings_bytes(mock_settings):
    settings.set_min_savings_bytes(2048)
    mock_settings.setValue.assert_called_with("scan/min_savings_bytes", 2048)


# ==========================================
# 4. Тесты API-ключа VirusTotal
# ==========================================


def test_get_vt_api_key(mock_settings):
    mock_settings.value.return_value = "secret_key_123"
    assert settings.get_vt_api_key() == "secret_key_123"


def test_set_vt_api_key(mock_settings):
    settings.set_vt_api_key("secret_key_123")
    mock_settings.setValue.assert_called_with(
        "api/virustotal", "secret_key_123"
    )
