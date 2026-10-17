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

        layout.addWidget(QLabel("Мин. экономия:"))
        self.min_savings = QSpinBox()
        self.min_savings.setRange(0, 100_000)
        self.min_savings.setSuffix(" МБ")
        self.min_savings.setValue(
            user_settings.get_min_savings_bytes() // (1024 * 1024)
        )
        self.min_savings.valueChanged.connect(self._on_changed)
        layout.addWidget(self.min_savings)

        layout.addWidget(QLabel("Поиск по пути:"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("подстрока в пути…")
        self.search.textChanged.connect(self._on_changed)
        layout.addWidget(self.search, 1)

        clear_btn = QPushButton("Сбросить")
        clear_btn.clicked.connect(self._on_clear)
        layout.addWidget(clear_btn)

    def _on_clear(self):
        self.min_savings.setValue(0)
        self.search.setText("")

    def _on_changed(self):
        user_settings.set_min_savings_bytes(
            self.min_savings.value() * 1024 * 1024
        )
        self.filters_changed.emit()

    # helpers

    def min_savings_bytes(self) -> int:
        return self.min_savings.value() * 1024 * 1024

    def search_text(self) -> str:
        return self.search.text().strip().lower()

    def matches(self, savings_bytes: int, paths) -> bool:
        if savings_bytes < self.min_savings_bytes():
            return False
        needle = self.search_text()
        if needle and not any(needle in str(p).lower() for p in paths):
            return False
        return True
