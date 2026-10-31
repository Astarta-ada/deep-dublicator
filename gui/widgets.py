"""Переиспользуемые виджеты (группы дубликатов, категории, метки)."""

from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QHBoxLayout,
    QRadioButton,
    QLabel,
    QCheckBox,
    QWidget,
    QSizePolicy,
    QButtonGroup,
    QToolButton,
    QMenu,
)

from utils.config import EMPTY_FILE_HASH
from utils.constants import IMAGE_EXTS
from utils.helpers import human_size, format_date, get_file_creation_time


class ClickableLabel(QLabel):
    """Метка с сигналами клика, двойного клика и контекстного меню."""

    clicked = Signal(Path)
    double_clicked = Signal(Path)
    context_requested = Signal(Path, QPoint)

    def __init__(self, path: Path, text: str = "", parent=None):
        super().__init__(text or str(path), parent)
        self.path = path
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda p: self.context_requested.emit(
                self.path, self.mapToGlobal(p)
            )
        )

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.path)
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.double_clicked.emit(self.path)
        super().mouseDoubleClickEvent(e)


class DuplicateGroupWidget(QGroupBox):
    """
    Одна группа дубликатов (сворачиваемая, с превью и контекстным меню).
    """

    changed = Signal()
    file_clicked = Signal(Path)
    file_double_clicked = Signal(Path)
    compare_requested = Signal(Path, Path)
    open_in_system_requested = Signal(Path)

    def __init__(
        self, hash_key: str, paths: list[Path], show_preview=False, parent=None
    ):
        super().__init__(parent)
        self.hash_key, self.paths = hash_key, paths

        tag = " [ПУСТЫЕ]" if hash_key == EMPTY_FILE_HASH else ""
        size_str = human_size(paths[0].stat().st_size) if paths else "?"
        self.setTitle(f"Группа ({len(paths)} шт){tag} — {size_str}")

        outer = QVBoxLayout(self)
        outer.setSpacing(6)
        outer.setContentsMargins(14, 18, 14, 14)

        # --- Верхняя строка (кнопка сворачивания и превью) ---
        top_row = QHBoxLayout()
        self._toggle_btn = QToolButton()
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setChecked(True)
        self._toggle_btn.setText("▼")
        self._toggle_btn.setFixedSize(22, 22)
        self._toggle_btn.clicked.connect(self._on_toggle)
        top_row.addWidget(self._toggle_btn, 0, Qt.AlignTop)

        # Блок миниатюр (если включено в настройках и это картинки)
        if show_preview and paths:
            preview_layout = QHBoxLayout()
            for p in paths[:4]:
                if p.suffix.lower() in IMAGE_EXTS:
                    pix = QPixmap(str(p))
                    if not pix.isNull():
                        lbl = QLabel()
                        lbl.setPixmap(
                            pix.scaled(
                                64,
                                64,
                                Qt.KeepAspectRatio,
                                Qt.SmoothTransformation,
                            )
                        )
                        preview_layout.addWidget(lbl)
            preview_layout.addStretch()
            top_row.addLayout(preview_layout, 1)
        else:
            top_row.addStretch()
        outer.addLayout(top_row)

        # --- Сворачиваемое тело группы ---
        self._body = QWidget()
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(0, 6, 0, 0)
        body_layout.setSpacing(4)

        # Группа для радиокнопок (гарантирует ровно 1 оригинал)
        self._radio_group = QButtonGroup(self)
        self._radio_group.setExclusive(True)
        self._radios, self._checks, self._rows = [], [], []

        for i, path in enumerate(paths):
            row = QWidget()
            row.setObjectName("fileRow")
            h = QHBoxLayout(row)
            h.setContentsMargins(8, 6, 8, 6)
            h.setSpacing(10)

            radio = QRadioButton()
            radio.setFixedWidth(20)
            self._radio_group.addButton(radio, i)
            if i == 0:
                radio.setChecked(True)

            check = QCheckBox()
            check.setFixedWidth(20)
            check.setChecked(i != 0)

            # Инфо о дате создания/изменения
            try:
                st = path.stat()
                c_time = format_date(get_file_creation_time(st))
                m_time = format_date(st.st_mtime)
                info = f"{path}\nСоздан: {c_time} | Изменён: {m_time}"
            except Exception:
                info = str(path)

            label = ClickableLabel(path, info)
            label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            label.clicked.connect(self.file_clicked.emit)
            label.double_clicked.connect(self.file_double_clicked.emit)
            label.context_requested.connect(self._on_label_context)

            h.addWidget(radio)
            h.addWidget(check)
            h.addWidget(label, 1)

            radio.toggled.connect(self._on_radio_toggled)
            # Оборачиваем в лямбду, так как check.toggled передает bool
            check.toggled.connect(lambda _: self.changed.emit())

            self._radios.append(radio)
            self._checks.append(check)
            self._rows.append(row)
            body_layout.addWidget(row)

        outer.addWidget(self._body)
        self._refresh_row_states()

    # ---------- Слоты ----------
    def _on_toggle(self, c):
        self._body.setVisible(c)
        self._toggle_btn.setText("▼" if c else "▶")

    def _on_label_context(self, path: Path, pos):
        menu = QMenu(self)
        menu.addAction(
            "Открыть", lambda: self.open_in_system_requested.emit(path)
        )
        menu.addAction(
            "Сравнить",
            lambda: self.compare_requested.emit(self.get_original(), path),
        )
        menu.exec(pos)

    def _on_radio_toggled(self, c):
        if c:
            self._refresh_row_states()
            self.changed.emit()

    def _refresh_row_states(self):
        """Обновляет блокировку чекбоксов и цвета строк (QSS)."""
        orig = self._get_original_index()
        for i, (r, c, row) in enumerate(
            zip(self._radios, self._checks, self._rows)
        ):
            is_o = i == orig

            # Блокируем/разблокируем чекбокс
            c.blockSignals(True)
            c.setChecked(not is_o and c.isChecked())
            c.setEnabled(not is_o)
            c.blockSignals(False)

            # Жирный шрифт для оригинала
            f = r.font()
            f.setBold(is_o)
            r.setFont(f)

            # Устанавливаем состояние для QSS (цвета)
            if is_o:
                row.setProperty("state", "original")
            elif c.isChecked():
                row.setProperty("state", "delete")
            else:
                row.setProperty("state", "keep")

            # Принудительно обновляем стиль
            row.style().unpolish(row)
            row.style().polish(row)

    def _get_original_index(self) -> int:
        for i, r in enumerate(self._radios):
            if r.isChecked():
                return i
        if self._radios:
            self._radios[0].setChecked(True)
        return 0

    # ---------- Публичное API ----------
    def get_selection(self):
        return (
            self.paths[self._get_original_index()],
            [
                self.paths[i]
                for i, c in enumerate(self._checks)
                if c.isChecked()
            ],
        )

    def get_original(self):
        return self.paths[self._get_original_index()]

    def set_original_index(self, idx):
        """Безопасно устанавливает оригинал по индексу."""
        if not (0 <= idx < len(self._radios)):
            return  # Защита от IndexError
        self._radios[idx].setChecked(True)
        self._refresh_row_states()

    def set_selected(self, idx: int, checked: bool):
        """Безопасно отмечает/снимает чекбокс (с защитой оригинала)."""
        if not (0 <= idx < len(self._checks)):
            return  # Защита от IndexError
        if idx == self._get_original_index():
            return  # Оригинал нельзя отметить для удаления
        self._checks[idx].setChecked(checked)

    def selected_count(self):
        return sum(1 for c in self._checks if c.isChecked())

    def set_collapsed(self, c):
        self._toggle_btn.setChecked(not c)
        self._on_toggle(not c)

    def savings_bytes(self):
        o = self._get_original_index()
        return sum(
            self.paths[i].stat().st_size
            for i, c in enumerate(self._checks)
            if c.isChecked() and i != o
        )


class CategoryGroupWidget(QGroupBox):
    """Контейнер для групп дубликатов одного типа (Изображения, Видео и т.д.)."""

    def __init__(self, title: str, count: int, parent=None):
        super().__init__(parent)
        self.category_name = title
        self.setTitle(f"{title} — {count} групп")
        self.setProperty("class", "category")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 16, 8, 8)
        self._layout.setSpacing(8)
        # Пружина, прижимающая группы к верху
        self._layout.addStretch()

    def add_group(self, w):
        self._layout.insertWidget(self._layout.count() - 1, w)
