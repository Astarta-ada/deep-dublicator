"""Панель фильтрации результатов: экономия + поиск по пути."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QPushButton,
)

from utils import settings as user_settings


class ResultFilterBar(QWidget):
    """Фильтрует отображаемые группы по порогу экономии и подстроке пути."""

    filters_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # --- Фильтр по минимальной экономии ---
        layout.addWidget(QLabel("Мин. экономия:"))
        self.min_savings = QSpinBox()
        self.min_savings.setRange(0, 100_000)
        self.min_savings.setSuffix(" МБ")
        self.min_savings.setToolTip(
            "Показывать только те группы, при очистке которых освободится указанное место"
        )

        # Восстанавливаем значение из настроек (переводим байты в МБ)
        self.min_savings.setValue(
            user_settings.get_min_savings_bytes() // (1024 * 1024)
        )
        self.min_savings.valueChanged.connect(self._on_changed)
        layout.addWidget(self.min_savings)

        # --- Поиск по пути --
        layout.addWidget(QLabel("Поиск по пути:"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("подстрока в пути…")
        self.search.textChanged.connect(self._on_changed)
        layout.addWidget(self.search, 1)

        # --- Кнопка сброса ---
        clear_btn = QPushButton("Сбросить")
        clear_btn.clicked.connect(self._on_clear)
        layout.addWidget(clear_btn)

    def _on_clear(self):
        """Сбрасывает все фильтры в значения по умолчанию."""
        self.min_savings.setValue(0)
        self.search.setText("")

    def _on_changed(self):
        """Сохраняет настройки и отправляет сигнал об изменении."""
        user_settings.set_min_savings_bytes(
            self.min_savings.value() * 1024 * 1024
        )
        self.filters_changed.emit()

    # -------- helpers для проверки --------

    def min_savings_bytes(self) -> int:
        return self.min_savings.value() * 1024 * 1024

    def search_text(self) -> str:
        return self.search.text().strip().lower()

    def matches(self, savings_bytes: int, paths) -> bool:
        """
        Проверяет, соответствует ли группа текущим фильтрам.

        :param savings_bytes: сколько байт освободится при удалении дубликатов в группе
        :param paths: список путей файлов в группе (для поиска подстроки)
        """
        # 1. Проверка размера экономии
        if savings_bytes < self.min_savings_bytes():
            return False
        needle = self.search_text()
        # 2. Проверка поисковой строки
        if needle and not any(needle in str(p).lower() for p in paths):
            return False
        return True
