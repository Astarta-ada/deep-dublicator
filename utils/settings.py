"""Обёртка над QSettings для пользовательских настроек."""

from PySide6.QtCore import QSettings
from utils.config import ORG_NAME, APP_NAME


def _settings():  # -> QSettings:
    """Возвращает объект QSettings для текущего приложения."""
    return QSettings(ORG_NAME, APP_NAME)


# ==========================================
# Последняя открытая папка
# ==========================================


def get_last_dir():  # -> str:
    """Возвращает путь к последней просканированной папке."""
    return _settings().value("scan/last_dir", "", type=str)


def set_last_dir(path: str):  # -> None:
    """Сохраняет путь к последней просканированной папке."""
    _settings().setValue("scan/last_dir", path)


# ==========================================
# Список недавних сессий (Recent files)
# ==========================================


def get_recent_sessions():  # -> list[str]:
    """Возвращает список путей к недавно открытым файлам сессий."""
    v = _settings().value("sessions/recent", [])
    if isinstance(v, str):
        v = [v] if v else []
    return [str(x) for x in (v or [])]


def push_recent_session(path: str, max_items: int = 8):  # -> None:
    """Добавляет сессию в начало списка недавних и обрезает его до max_items."""
    lst = get_recent_sessions()
    if path in lst:
        lst.remove(path)
    lst.insert(0, path)
    lst = lst[:max_items]
    _settings().setValue("sessions/recent", lst)


# ==========================================
# Фильтр по минимальной экономии
# ==========================================


def get_min_savings_bytes():  # -> int:
    """Возвращает сохраненный порог экономии в байтах."""
    try:
        return int(_settings().value("scan/min_savings_bytes", 0))
    except (TypeError, ValueError):
        return 0


def set_min_savings_bytes(v: int):  # -> None:
    """Сохраняет порог экономии в байтах."""
    _settings().setValue("scan/min_savings_bytes", int(v))


# ==========================================
# API-ключ VirusTotal
# ==========================================


def get_vt_api_key():  # -> str:
    """Возвращает сохраненный API-ключ для VirusTotal."""
    return _settings().value("api/virustotal", "", type=str)


def set_vt_api_key(key: str):  # -> None:
    """Сохраняет API-ключ для VirusTotal."""
    _settings().setValue("api/virustotal", key)
