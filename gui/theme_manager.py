"""Управление визуальными темами приложения (применение + сохранение)."""

import logging

from PySide6.QtCore import QSettings, QObject, Signal
from PySide6.QtWidgets import QApplication

from gui.theme import THEMES, DEFAULT_THEME, build_stylesheet
from utils.config import ORG_NAME, APP_NAME, SETTINGS_THEME_KEY

log = logging.getLogger(__name__)


class ThemeManager(QObject):
    """Синглтон-помощник: применяет тему ко всему приложению."""

    theme_changed = Signal(str)  # ключ темы

    _instance: "ThemeManager | None" = None

    @classmethod
    def instance(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance

    def __init__(self):
        super().__init__()
        self._settings = QSettings(ORG_NAME, APP_NAME)
        self._current = self._settings.value(SETTINGS_THEME_KEY, DEFAULT_THEME)
        if self._current not in THEMES:
            self._current = DEFAULT_THEME

    # ---------- публичное API ----------

    @property
    def current(self) -> str:
        """Ключ текущей активной темы."""
        return self._current

    def available(self) -> dict[str, str]:
        """Возвращает словарь {ключ: человекочитаемое имя} для всех доступных тем."""
        return {k: v["name"] for k, v in THEMES.items()}

    def apply(self, theme_key: str) -> None:
        """Применяет тему ко всему приложению и сохраняет выбор."""
        if theme_key not in THEMES:
            log.warning("Неизвестная тема: %s — пропускаю", theme_key)
            return

        app = QApplication.instance()
        if app is None:
            log.error("QApplication не создан — тема не применена")
            return

        # Применяем стили
        app.setStyleSheet(build_stylesheet(theme_key))
        self._current = theme_key

        # Сохраняем в настройки
        self._settings.setValue(SETTINGS_THEME_KEY, theme_key)
        log.info("Тема применена: %s", theme_key)

        # Оповещаем подписчиков (например, если нужно перерисовать кастомные виджеты)
        self.theme_changed.emit(theme_key)

    def apply_saved(self) -> None:
        """Применяет сохранённую тему при старте приложения."""
        self.apply(self._current)
