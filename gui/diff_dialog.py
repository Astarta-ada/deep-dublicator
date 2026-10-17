"""Диалог сравнения двух текстовых файлов."""

import difflib
import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QWidget,
    QVBoxLayout as VBox,
)

log = logging.getLogger(__name__)

MAX_LINES = 5000


class DiffDialog(QDialog):
    def __init__(self, original: Path, duplicate: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Сравнение: {duplicate.name} ↔ {original.name}")
        self.resize(1100, 700)

        layout = QVBoxLayout(self)

        info = QLabel(
            f"<b>Оригинал:</b> <code>{original}</code><br>"
            f"<b>Дубликат:</b> <code>{duplicate}</code>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        splitter = QSplitter(Qt.Horizontal)
        self._left = QPlainTextEdit()
        self._right = QPlainTextEdit()
        for view in (self._left, self._right):
            view.setReadOnly(True)
            view.setLineWrapMode(QPlainTextEdit.NoWrap)

        splitter.addWidget(self._wrap("Оригинал", self._left))
        splitter.addWidget(self._wrap("Дубликат", self._right))
        splitter.setSizes([550, 550])
        layout.addWidget(splitter, 1)

        bottom = QHBoxLayout()
        self._status = QLabel("")
        bottom.addWidget(self._status, 1)
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

        self._load(original, duplicate)

    @staticmethod
    def _wrap(title: str, widget):
        w = QWidget()
        l = VBox(w)
        l.setContentsMargins(0, 0, 0, 0)
        lab = QLabel(title)
        lab.setStyleSheet("font-weight: 600; padding: 4px;")
        l.addWidget(lab)
        l.addWidget(widget, 1)
        return w

    def _load(self, original: Path, duplicate: Path):
        try:
            with open(original, "r", encoding="utf-8", errors="replace") as f:
                a_lines = f.readlines()[:MAX_LINES]
            with open(duplicate, "r", encoding="utf-8", errors="replace") as f:
                b_lines = f.readlines()[:MAX_LINES]
        except OSError as e:
            log.exception("Ошибка чтения файлов для diff")
            self._status.setText(f"Ошибка: {e}")
            return

        self._left.setPlainText("".join(a_lines))
        self._right.setPlainText("".join(b_lines))

        if a_lines == b_lines:
            self._status.setText("✅ Файлы идентичны построчно.")
        else:
            diff = list(
                difflib.unified_diff(
                    a_lines,
                    b_lines,
                    fromfile="оригинал",
                    tofile="дубликат",
                    n=2,
                )
            )
            added = sum(
                1
                for l in diff
                if l.startswith("+") and not l.startswith("+++")
            )
            removed = sum(
                1
                for l in diff
                if l.startswith("-") and not l.startswith("---")
            )
            self._status.setText(
                f"⚠️ Файлы отличаются: +{added} / -{removed} строк."
            )
