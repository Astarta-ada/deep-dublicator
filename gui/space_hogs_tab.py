import os
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import Qt, QThread, Signal, QUrl
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


class HogsScanner(QThread):
    finished_ok = Signal(list)

    def __init__(self, root, min_size, older_than_days):
        super().__init__()
        self.root = root
        self.min_size = min_size
        self.older_than_days = older_than_days

    def run(self):
        results = []
        now = datetime.now().timestamp()
        for dirpath, _, filenames in os.walk(self.root):
            for f in filenames:
                try:
                    p = Path(dirpath) / f
                    st = p.stat()
                    if st.st_size >= self.min_size:
                        if self.older_than_days > 0:
                            days_old = (now - st.st_mtime) / (24 * 3600)
                            if days_old < self.older_than_days:
                                continue
                        results.append(
                            (
                                str(p),
                                st.st_size,
                                datetime.fromtimestamp(st.st_mtime).strftime(
                                    "%Y-%m-%d"
                                ),
                            )
                        )
                except OSError:
                    pass
        results.sort(key=lambda x: x[1], reverse=True)
        self.finished_ok.emit(results)


# Кастомный элемент таблицы для правильной сортировки размеров
class SizeItem(QTableWidgetItem):
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

        top = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Папка для поиска...")
        top.addWidget(QLabel("Папка:"))
        top.addWidget(self.path_edit, 1)
        top.addWidget(QPushButton("Обзор", clicked=self._browse))

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

        self.status = QLabel("Готово")
        self.status.setObjectName("statusLabel")
        lay.addWidget(self.status)

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
        d = QFileDialog.getExistingDirectory(self)
        if d:
            self.path_edit.setText(d)

    def _start(self):
        p = self.path_edit.text().strip()
        if not os.path.isdir(p):
            return QMessageBox.warning(self, "Ошибка", "Укажите папку")
        self.btn_start.setEnabled(False)
        self.table.setRowCount(0)
        self.status.setText("Сканирование...")

        self.worker = HogsScanner(
            p, self.size_combo.currentData(), self.old_combo.currentData()
        )
        self.worker.finished_ok.connect(self._done)
        self.worker.start()

    def _done(self, res):
        self.btn_start.setEnabled(True)
        self.status.setText(f"Найдено файлов: {len(res)}")

        # 1. Отключаем сортировку ПЕРЕД заполнением (КРИТИЧНО!)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(res))

        for i, (path, size, date) in enumerate(res):
            item_path = QTableWidgetItem(path)
            item_size = SizeItem(size)  # Используем наш кастомный класс
            item_date = QTableWidgetItem(date)

            self.table.setItem(i, 0, item_path)
            self.table.setItem(i, 1, item_size)
            self.table.setItem(i, 2, item_date)

        # 2. Включаем сортировку обратно, когда всё загружено
        self.table.setSortingEnabled(True)

        main_win = self.window()
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
