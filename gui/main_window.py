"""Главное окно приложения."""

import logging
from pathlib import Path
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QMessageBox,
    QFileDialog,
    QSystemTrayIcon,
    QMenu,
    QStyle,
)
from PySide6.QtCore import Qt, QSettings, QTimer  # <--- Добавлен QTimer

from gui.scan_tab import ScanTab
from gui.disk_analysis_tab import DiskAnalysisTab
from gui.space_hogs_tab import SpaceHogsTab
from gui.junk_cleaner_tab import JunkCleanerTab
from gui.theme_manager import ThemeManager
from utils import settings as user_settings
from utils.config import APP_NAME, APP_VERSION, AUTOSAVE_FILE

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1100, 780)
        self.setMinimumSize(900, 620)

        # Сохранение геометрии
        self.settings = QSettings("DupFinder", "Duplicate Finder")
        geom = self.settings.value("window/geometry")
        if geom:
            self.restoreGeometry(geom)

        # Переменные для спиннера в трее
        self.tray_timer = QTimer(self)
        self.tray_timer.timeout.connect(self._spin_tray)
        self.tray_spin_state = False

        self._build_ui()
        self._build_tray()
        self._build_menu()

        # Проверка автосохранения
        self._check_autosave()

        log.info("Главное окно создано")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Сайдбар (слева)
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(200)
        self.sidebar.setStyleSheet(
            "QListWidget { background: #1e293b; color: white; border: none; padding-top: 10px; } QListWidget::item { padding: 12px; } QListWidget::item:selected { background: #3b82f6; }"
        )

        # Контент (справа)
        self.stack = QStackedWidget()

        # Добавляем вкладки
        self.pages = [
            ("🔍 Поиск дубликатов", ScanTab()),
            ("📊 Анализ диска", DiskAnalysisTab()),
            ("🐷 Большие файлы", SpaceHogsTab()),
            ("🧹 Очистка мусора", JunkCleanerTab()),
        ]

        for name, widget in self.pages:
            self.sidebar.addItem(QListWidgetItem(name))
            self.stack.addWidget(widget)

        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

        lay.addWidget(self.sidebar)
        lay.addWidget(self.stack, 1)

        # Прокидываем сигнал из анализа диска
        self.disk_tab = self.pages[1][1]
        self.disk_tab.find_duplicates_requested.connect(self._jump_dups)

        # Сохранение ширины колонок (пример для таблицы больших файлов)
        self.hogs_tab = self.pages[2][1]
        hogs_state = self.settings.value("hogs_table/header")
        if hogs_state:
            self.hogs_tab.table.horizontalHeader().restoreState(hogs_state)

    def _build_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self.tray.setToolTip("Deep Dublicator")

        tray_menu = QMenu()
        act_show = QAction("Развернуть", self)
        act_show.triggered.connect(self.showNormal)
        act_quit = QAction("Выход", self)
        act_quit.triggered.connect(self.close)

        tray_menu.addAction(act_show)
        tray_menu.addSeparator()
        tray_menu.addAction(act_quit)
        self.tray.setContextMenu(tray_menu)
        self.tray.show()

    def _build_menu(self):
        mb = self.menuBar()

        # Файл
        fm = mb.addMenu("Файл")
        fm.addAction("Выход", self.close)

        # Вид (Темы)
        vm = mb.addMenu("Вид")
        theme_menu = vm.addMenu("Тема")
        tmgr = ThemeManager.instance()
        grp = QActionGroup(self)
        for k, n in tmgr.available().items():
            a = QAction(n, self, checkable=True, checked=(k == tmgr.current))
            a.triggered.connect(lambda _, key=k: tmgr.apply(key))
            grp.addAction(a)
            theme_menu.addAction(a)

    def _jump_dups(self, path: str):
        self.sidebar.setCurrentRow(0)

        p = Path(path)
        if p.is_file():
            p = p.parent

        self.pages[0][1].path_edit.setText(str(p))
        self.pages[0][1].mode_combo.setCurrentIndex(0)

    def _spin_tray(self):
        self.tray_spin_state = not self.tray_spin_state
        if self.tray_spin_state:
            self.tray.setIcon(
                self.style().standardIcon(QStyle.SP_BrowserReload)
            )
        else:
            self.tray.setIcon(
                self.style().standardIcon(QStyle.SP_ComputerIcon)
            )

    def start_tray_spinner(self):
        self.tray_timer.start(500)

    def stop_tray_spinner(self):
        self.tray_timer.stop()
        self.tray.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))

    def notify(self, title, message):
        """Для вызова из других вкладок."""
        if self.tray.isSystemTrayAvailable():
            self.tray.showMessage(
                title, message, QSystemTrayIcon.Information, 3000
            )

    def _check_autosave(self):
        if AUTOSAVE_FILE.exists():
            res = QMessageBox.question(
                self,
                "Восстановление",
                "Найдены результаты прошлого поиска. Восстановить их?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if res == QMessageBox.Yes:
                self.pages[0][1].restore_autosave()

    def closeEvent(self, event):
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue(
            "hogs_table/header",
            self.hogs_tab.table.horizontalHeader().saveState(),
        )
        super().closeEvent(event)
