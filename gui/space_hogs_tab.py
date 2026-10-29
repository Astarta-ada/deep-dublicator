"""Вкладка поиска больших файлов (Space Hogs)."""

import os
import logging
from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QComboBox,
    QMessageBox,
    QMenu,
)
from gui.widgets import human_size
from core.file_ops import delete_file
from core.workers import HogsScanner

log = logging.getLogger(__name__)


class SizeItem(QTableWidgetItem):
    """Кастомный элемент таблицы для правильной числовой сортировки размеров."""

    def __init__(self, size_bytes):
        super().__init__(human_size(size_bytes))
        self.size_bytes = size_bytes

    def __lt__(self, other):
        # Сортируем по реальному размеру в байтах, а не по строке
        return self.size_bytes < other.size_bytes


class SpaceHogsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.setAcceptDrops(True)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        # --- Верхняя панель фильтров ---
        top = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Папка для поиска...")
        top.addWidget(QLabel("Папка:"))
        top.addWidget(self.path_edit, 1)

        btn_browse = QPushButton("Обзор...")
        btn_browse.clicked.connect(self._browse)
        top.addWidget(btn_browse)

        self.size_combo = QComboBox()
        self.size_combo.addItem("> 100 МБ", 100 * 1024 * 1024)
        self.size_combo.addItem("> 500 МБ", 500 * 1024 * 1024)
        self.size_combo.addItem("> 1 ГБ", 1024 * 1024 * 1024)
        top.addWidget(QLabel("Размер:"))
        top.addWidget(self.size_combo)

        self.old_combo = QComboBox()
        self.old_combo.addItem("Любой возраст", 0)
        self.old_combo.addItem("Старше 1 года", 365)
        self.old_combo.addItem("Старше 2 лет", 730)
        top.addWidget(QLabel("Возраст:"))
        top.addWidget(self.old_combo)

        self.btn_start = QPushButton("🔍 Сканировать")
        self.btn_start.setProperty("class", "primary")
        self.btn_start.clicked.connect(self._start)
        top.addWidget(self.btn_start)
        lay.addLayout(top)

        # --- Статус ---
        self.status = QLabel("Готово к работе")
        self.status.setObjectName("statusLabel")
        lay.addWidget(self.status)

        # --- Таблица результатов ---
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Файл", "Размер", "Изменён"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeToContents
        )

        # Сортировка включена, но мы будем отключать её при заполнении
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._menu)
        lay.addWidget(self.table)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Выберите папку")
        if d:
            self.path_edit.setText(d)

    def _start(self):
        p = self.path_edit.text().strip()
        if not os.path.isdir(p):
            return QMessageBox.warning(
                self, "Ошибка", "Укажите существующую папку"
            )
        self.btn_start.setEnabled(False)
        self.table.setRowCount(0)
        self.status.setText("Сканирование...")

        # Запускаем спиннер в трее
        main_win = self.window()
        if hasattr(main_win, "start_tray_spinner"):
            main_win.start_tray_spinner()

        self.worker = HogsScanner(
            p, self.size_combo.currentData(), self.old_combo.currentData()
        )
        self.worker.finished_ok.connect(self._done)
        self.worker.start()

    def _done(self, res):
        self.btn_start.setEnabled(True)
        self.status.setText(f"Найдено файлов: {len(res)}")

        # 1. Получаем ссылку на главное окно один раз
        main_win = self.window()

        # 2. Останавливаем спиннер
        if hasattr(main_win, "stop_tray_spinner"):
            main_win.stop_tray_spinner()

        # 3. Отключаем сортировку ПЕРЕД заполнением (КРИТИЧНО для правильного отображения!)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(res))

        for i, (path, size, date) in enumerate(res):
            item_path = QTableWidgetItem(path)
            item_size = SizeItem(
                size
            )  # Кастомный класс для правильной сортировки размеров
            item_date = QTableWidgetItem(date)

            self.table.setItem(i, 0, item_path)
            self.table.setItem(i, 1, item_size)
            self.table.setItem(i, 2, item_date)

        # 4. Включаем сортировку обратно
        self.table.setSortingEnabled(True)

        # 5. Отправляем уведомление (используем ту же переменную main_win)
        if hasattr(main_win, "notify"):
            main_win.notify(
                "Большие файлы", f"Поиск завершен. Найдено: {len(res)}"
            )

    def _menu(self, pos):
        it = self.table.itemAt(pos)
        if not it:
            return
        row = it.row()
        path = self.table.item(row, 0).text()

        m = QMenu(self)
        m.addAction(
            "Открыть",
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(path)),
        )
        m.addAction("Удалить в корзину", lambda: self._del(path, row))
        m.exec(self.table.viewport().mapToGlobal(pos))

    def _del(self, path, row):
        if (
            QMessageBox.question(
                self, "Удаление", f"Удалить в корзину?\n{path}"
            )
            == QMessageBox.Yes
        ):
            try:
                delete_file(Path(path), use_trash=True)
                self.table.removeRow(row)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", str(e))

    # --- Drag & Drop ---
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            for url in e.mimeData().urls():
                if url.isLocalFile() and Path(url.toLocalFile()).is_dir():
                    e.acceptProposedAction()
                    return
        e.ignore()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            if url.isLocalFile():
                p = Path(url.toLocalFile())
                if p.is_dir():
                    self.path_edit.setText(str(p))
                    self._start()
                    e.acceptProposedAction()
                    return
        e.ignore()
