import os
import shutil
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QLineEdit,
    QFileDialog,
)
from gui.widgets import human_size


class JunkScanner(QThread):
    finished_ok = Signal(list)

    def __init__(self, root):
        super().__init__()
        self.root = root

    def run(self):
        results = []
        # 1. Temp
        temp = os.environ.get("TEMP")
        if temp and os.path.exists(temp):
            size = self._get_size(temp)
            results.append(("Временные файлы Windows (%TEMP%)", temp, size))

        # 2. Сканируем папку на __pycache__, node_modules, Thumbs.db
        cache_size, node_size, thumb_size = 0, 0, 0
        cache_paths, node_paths = [], []

        for dirpath, dirnames, filenames in os.walk(self.root):
            if "__pycache__" in dirnames:
                p = os.path.join(dirpath, "__pycache__")
                cache_size += self._get_size(p)
                cache_paths.append(p)
                dirnames.remove("__pycache__")

            if "node_modules" in dirnames:
                p = os.path.join(dirpath, "node_modules")
                node_size += self._get_size(p)
                node_paths.append(p)
                dirnames.remove("node_modules")

            for f in filenames:
                if f == "Thumbs.db":
                    thumb_size += os.path.getsize(os.path.join(dirpath, f))

        if cache_size > 0:
            results.append(
                (
                    "Кэш Python (__pycache__)",
                    "\n".join(cache_paths),
                    cache_size,
                )
            )
        if node_size > 0:
            results.append(
                (
                    "Зависимости Node.js (node_modules)",
                    "\n".join(node_paths),
                    node_size,
                )
            )
        if thumb_size > 0:
            results.append(
                (
                    "Миниатюры Windows (Thumbs.db)",
                    "Найдены в папке",
                    thumb_size,
                )
            )

        self.finished_ok.emit(results)

    def _get_size(self, path):
        total = 0
        for root, _, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except:
                    pass
        return total


class JunkCleanerTab(QWidget):
    def __init__(self):
        super().__init__()
        self.found_junk = []
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)

        top = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(
            "Папка для поиска мусора (например, C:\\Projects)..."
        )
        top.addWidget(QLabel("Папка:"))
        top.addWidget(self.path_edit, 1)

        btn_browse = QPushButton("Обзор...")
        btn_browse.clicked.connect(self._browse)
        top.addWidget(btn_browse)

        btn_scan = QPushButton("🔍 Анализ мусора")
        btn_scan.setProperty("class", "primary")
        btn_scan.clicked.connect(self._scan)
        top.addWidget(btn_scan)
        lay.addLayout(top)

        self.list_widget = QListWidget()
        lay.addWidget(self.list_widget)

        self.status = QLabel("Готово")
        lay.addWidget(self.status)

        btn_clean = QPushButton("🧹 Очистить выбранное")
        btn_clean.setProperty("class", "danger")
        btn_clean.clicked.connect(self._clean)
        lay.addWidget(btn_clean)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(
            self, "Выберите папку для анализа мусора"
        )
        if d:
            self.path_edit.setText(d)

    def _scan(self):
        p = self.path_edit.text().strip()
        if not os.path.isdir(p):
            return QMessageBox.warning(self, "Ошибка", "Выберите папку")

        self.list_widget.clear()
        self.status.setText("Анализ...")

        self.worker = JunkScanner(p)
        self.worker.finished_ok.connect(self._done)
        self.worker.start()

    def _done(self, res):
        self.status.setText(f"Найдено категорий: {len(res)}")
        self.found_junk = res
        for name, path, size in res:
            item = QListWidgetItem(f"{name} — {human_size(size)}")
            item.setData(Qt.UserRole, (name, path))
            item.setCheckState(Qt.Checked)
            self.list_widget.addItem(item)

    def _clean(self):
        if (
            QMessageBox.question(self, "Очистка", "Удалить выбранный мусор?")
            != QMessageBox.Yes
        ):
            return

        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                name, path = item.data(Qt.UserRole)
                try:
                    if name.startswith("Кэш Python"):
                        for p in path.split("\n"):
                            shutil.rmtree(p, ignore_errors=True)
                    elif name.startswith("Node.js"):
                        for p in path.split("\n"):
                            shutil.rmtree(p, ignore_errors=True)
                    elif name.startswith("Временные"):
                        for f in os.listdir(path):
                            fp = os.path.join(path, f)
                            try:
                                if os.path.isfile(fp):
                                    os.remove(fp)
                                else:
                                    shutil.rmtree(fp)
                            except:
                                pass
                except Exception as e:
                    print(f"Ошибка очистки {name}: {e}")

        QMessageBox.information(self, "Готово", "Выбранный мусор удален.")
        self.list_widget.clear()
