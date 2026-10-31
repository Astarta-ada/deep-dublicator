"""Диалоговые окна приложения."""

import json
import difflib
import logging
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QWidget,
    QSlider,
    QListWidget,
    QCheckBox,
    QMessageBox,
    QListWidgetItem,
)

from utils.config import APP_NAME, APP_VERSION
from utils.history import get_history
from gui.widgets import human_size
from core.file_ops import undo_action

log = logging.getLogger(__name__)


class DiffDialog(QDialog):
    """==========================================
    Сравнение текстовых файлов
    =========================================="""

    def __init__(self, original: Path, duplicate: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Сравнение: {duplicate.name} ↔ {original.name}")
        self.resize(1100, 700)

        layout = QVBoxLayout(self)

        info = QLabel(
            f"<b>Оригинал:</b> <code>{original}</code><br><b>Дубликат:</b> <code>{duplicate}</code>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        splitter = QSplitter(Qt.Horizontal)
        self._left, self._right = QPlainTextEdit(), QPlainTextEdit()
        for view in (self._left, self._right):
            view.setReadOnly(True)
            view.setLineWrapMode(QPlainTextEdit.NoWrap)
        splitter.addWidget(self._wrap("Оригинал", self._left))
        splitter.addWidget(self._wrap("Дубликат", self._right))
        splitter.setSizes([550, 550])
        layout.addWidget(splitter, 1)

        self._status = QLabel("")
        layout.addWidget(self._status)

        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self._load(original, duplicate)

    def _wrap(self, title, widget):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.addWidget(QLabel(f"<b>{title}</b>"))
        l.addWidget(widget)
        return w

    def _load(self, original, duplicate):
        try:
            with open(original, "r", encoding="utf-8", errors="replace") as f:
                a_lines = f.readlines()[:5000]
            with open(duplicate, "r", encoding="utf-8", errors="replace") as f:
                b_lines = f.readlines()[:5000]
        except OSError as e:
            self._status.setText(f"Ошибка чтения файлов: {e}")
            return
        self._left.setPlainText("".join(a_lines))
        self._right.setPlainText("".join(b_lines))

        if a_lines == b_lines:
            self._status.setText("✅ Файлы идентичны построчно.")
        else:
            diff = list(difflib.unified_diff(a_lines, b_lines))
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


class ImageSlider(QWidget):
    """==========================================
    2. Сравнение изображений (Слайдер)
    =========================================="""

    def __init__(self, pix1, pix2):
        super().__init__()
        self.pix1 = pix1.scaledToWidth(800, Qt.SmoothTransformation)
        self.pix2 = pix2.scaledToWidth(800, Qt.SmoothTransformation)
        self.setFixedSize(self.pix1.size())
        self.pos = 50

    def set_pos(self, val):
        self.pos = val
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        w = self.width()
        split_x = int(w * (self.pos / 100))

        p.drawPixmap(0, 0, self.pix1)
        p.setClipRect(split_x, 0, w - split_x, self.height())
        p.drawPixmap(0, 0, self.pix2)

        # Красная линия-разделитель
        p.setPen(Qt.red)
        p.drawLine(split_x, 0, split_x, self.height())


class SliderDialog(QDialog):
    def __init__(self, img1, img2, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Сравнение фото (Слайдер)")
        layout = QVBoxLayout(self)

        self.slider_widget = ImageSlider(QPixmap(img1), QPixmap(img2))
        layout.addWidget(self.slider_widget)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(50)
        slider.valueChanged.connect(self.slider_widget.set_pos)
        layout.addWidget(slider)


class HistoryDialog(QDialog):
    """==========================================
    3. История операций (Undo-лог)
    =========================================="""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("История операций")
        self.resize(800, 600)

        lay = QVBoxLayout(self)
        self.lst = QListWidget()
        self.lst.currentItemChanged.connect(self._on_select)

        lay.addWidget(self.lst)

        btn_layout = QHBoxLayout()
        self.btn_undo = QPushButton("⏪ Отменить действие")
        self.btn_undo.setEnabled(False)
        self.btn_undo.clicked.connect(self._do_undo)

        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_undo)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        lay.addLayout(btn_layout)

        self._load_history()

    def _load_history(self):
        self.lst.clear()
        # get_history теперь возвращает (id, timestamp, action, path, size, meta, is_undone)
        for row in get_history():
            action_id, t, a, p, s, meta, is_undone = row

            status = " ❌ [ОТМЕНЕНО]" if is_undone else ""
            text = f"[{t[:16]}] {a.upper()}: {p} ({human_size(s)}){status}"

            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, row)
            self.lst.addItem(item)

    def _on_select(self):
        item = self.lst.currentItem()
        if not item:
            self.btn_undo.setEnabled(False)
            return

        data = item.data(Qt.UserRole)
        action = data[2]
        is_undone = data[6]

        # Отменять можно только backup и rename, и если еще не отменено
        can_undo = action in ("backup", "rename") and not is_undone
        self.btn_undo.setEnabled(can_undo)

    def _do_undo(self):
        item = self.lst.currentItem()
        if not item:
            return

        action_id, _, action, path, _, meta, _ = item.data(Qt.UserRole)

        try:
            success = undo_action(action_id, action, path, meta)
            if success:
                QMessageBox.information(
                    self, "Успех", "Действие успешно отменено."
                )
                self._load_history()  # Перезагружаем список
            else:
                QMessageBox.warning(
                    self, "Ошибка", "Это действие нельзя отменить."
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось отменить действие:\n{e}"
            )


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("О программе")
        self.setFixedSize(450, 350)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Заголовок
        title = QLabel(f"<h1>{APP_NAME}</h1>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Версия
        version = QLabel(f"Версия {APP_VERSION}")
        version.setAlignment(Qt.AlignCenter)
        version.setStyleSheet("color: #64748b;")
        layout.addWidget(version)

        # Описание и авторство
        info_html = """
        <p align='center'>Мощный кроссплатформенный инструмент для поиска дубликатов, 
        анализа дискового пространства и очистки мусора.</p>
        
        <p align='center'><b>Автор:</b> Aleksandr Diuzhev</p>
        <p align='center'><b>Лицензия:</b> MIT</p>
        
        <p align='center'><a href='https://github.com/Astarta-ada/deep-dublicator'>
        Перейти в репозиторий на GitHub</a></p>
        """
        desc = QLabel(info_html)
        desc.setWordWrap(True)
        desc.setOpenExternalLinks(True)  # Чтобы ссылка открывалась в браузере
        layout.addWidget(desc)

        layout.addStretch()

        # Кнопка закрытия
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)
