import logging
from pathlib import Path
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QMessageBox,
    QFileDialog,
    QDialog,
    QVBoxLayout,
    QListWidget,
    QCheckBox,
    QPushButton,
    QLabel,
)
from gui.scan_tab import ScanTab
from gui.disk_analysis_tab import DiskAnalysisTab
from gui.theme_manager import ThemeManager
from utils import settings as user_settings
from utils.config import APP_NAME, APP_VERSION
from utils.history import get_history
from core.file_ops import remove_empty_dirs
from gui.widgets import human_size


class HistoryDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("История операций")
        self.resize(800, 600)
        lay = QVBoxLayout(self)
        lst = QListWidget()
        for t, a, p, s in get_history():
            lst.addItem(f"[{t[:16]}] {a.upper()}: {p} ({human_size(s)})")
        lay.addWidget(lst)


class CleanupDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Очистка кэшей")
        self.resize(400, 300)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Выберите папки для очистки:"))
        cbs = []
        for path in ["%TEMP%", "node_modules", "__pycache__"]:
            cb = QCheckBox(path)
            cbs.append(cb)
            lay.addWidget(cb)
        btn = QPushButton("Очистить выбранные")
        btn.clicked.connect(
            lambda: (
                QMessageBox.information(
                    self, "Готово", "Очищено! (Симуляция)"
                ),
                self.accept(),
            )
        )
        lay.addWidget(btn)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1100, 780)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.scan_tab = ScanTab()
        self.tabs.addTab(self.scan_tab, "Поиск дубликатов")

        self.disk_tab = DiskAnalysisTab()
        self.tabs.addTab(self.disk_tab, "Анализ диска")
        self.disk_tab.find_duplicates_requested.connect(self._jump_dups)

        self.setCentralWidget(self.tabs)
        self._build_menu()

    def _build_menu(self):
        mb = self.menuBar()

        # Файл
        fm = mb.addMenu("Файл")
        fm.addAction("Выход", self.close)

        # Инструменты
        tm = mb.addMenu("Инструменты")
        tm.addAction(
            "Очистка кэшей и мусора", lambda: CleanupDialog(self).exec()
        )
        tm.addAction("История операций", lambda: HistoryDialog(self).exec())
        tm.addAction("Удалить пустые папки", self._rm_empty)

        # Вид
        vm = mb.addMenu("Вид")
        self.act_notify = QAction("Уведомлять о завершении", self)
        self.act_notify.setCheckable(True)
        self.act_notify.setChecked(
            user_settings._settings().value("notify", True, bool)
        )
        vm.addAction(self.act_notify)

        self.act_prev = QAction("Превью в группах", self)
        self.act_prev.setCheckable(True)
        self.act_prev.setChecked(
            user_settings._settings().value("group_preview", True, bool)
        )
        vm.addAction(self.act_prev)

        vm.addSeparator()
        tm_menu = vm.addMenu("Тема")
        tmgr = ThemeManager.instance()
        grp = QActionGroup(self)
        for k, n in tmgr.available().items():
            a = QAction(n, self, checkable=True, checked=(k == tmgr.current))
            a.triggered.connect(lambda _, key=k: tmgr.apply(key))
            grp.addAction(a)
            tm_menu.addAction(a)

    def _jump_dups(self, path):
        self.tabs.setCurrentIndex(0)
        self.scan_tab.path_edit.setText(path)
        self.scan_tab.mode_combo.setCurrentIndex(0)

    def _rm_empty(self):
        d = QFileDialog.getExistingDirectory(self, "Удалить пустые папки в…")
        if d:
            remove_empty_dirs(Path(d))
            QMessageBox.information(self, "Готово", "Пустые папки удалены.")
