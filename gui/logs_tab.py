"""Вкладка для отображения логов в реальном времени."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QLabel,
)
from PySide6.QtGui import QFont


class LogsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        layout.addWidget(QLabel("<b>Журнал событий (логи):</b>"))

        # Текстовое поле с моноширинным шрифтом
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(
            QFont("Consolas", 10)
        )  # Удобный шрифт для логов
        self.text_edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        layout.addWidget(self.text_edit)

        # Кнопка очистки
        btn_layout = QHBoxLayout()
        btn_clear = QPushButton("Очистить логи")
        btn_clear.clicked.connect(self.text_edit.clear)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_clear)
        layout.addLayout(btn_layout)

    def append_log(self, text: str):
        """Добавляет строку в лог и прокручивает вниз."""
        self.text_edit.appendPlainText(text)
        # Автоскролл в самый низ
        sb = self.text_edit.verticalScrollBar()
        sb.setValue(sb.maximum())
