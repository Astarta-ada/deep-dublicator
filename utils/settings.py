"""Обёртка над QSettings для пользовательских настроек."""

from PySide6.QtCore import QSettings

_ORG = "DupFinder"
_APP = "Duplicate Finder"


def _settings() -> QSettings:
    return QSettings(_ORG, _APP)


# ---------- последняя папка ----------


def get_last_dir() -> str:
    return _settings().value("scan/last_dir", "", type=str)


def set_last_dir(path: str) -> None:
    _settings().setValue("scan/last_dir", path)


# ---------- недавние сессии ----------


def get_recent_sessions() -> list[str]:
    v = _settings().value("sessions/recent", [])
    if isinstance(v, str):
        v = [v] if v else []
    return [str(x) for x in (v or [])]


def push_recent_session(path: str, max_items: int = 8) -> None:
    lst = get_recent_sessions()
    if path in lst:
        lst.remove(path)
    lst.insert(0, path)
    lst = lst[:max_items]
    _settings().setValue("sessions/recent", lst)


# ---------- порог экономии ----------


def get_min_savings_bytes() -> int:
    try:
        return int(_settings().value("scan/min_savings_bytes", 0))
    except (TypeError, ValueError):
        return 0


def set_min_savings_bytes(v: int) -> None:
    _settings().setValue("scan/min_savings_bytes", int(v))


def get_vt_api_key() -> str:
    return _settings().value("api/virustotal", "", type=str)


def set_vt_api_key(key: str) -> None:
    _settings().setValue("api/virustotal", key)
