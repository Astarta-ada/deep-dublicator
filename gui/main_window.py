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
    QSystemTrayIcon,
    QMenu,
    QStyle,
)
from PySide6.QtCore import QSettings, QTimer

# Импорты вкладок
from gui.scan_tab import ScanTab
from gui.disk_analysis_tab import DiskAnalysisTab
from gui.space_hogs_tab import SpaceHogsTab
from gui.junk_cleaner_tab import JunkCleanerTab
from gui.logs_tab import LogsTab

# Импорты менеджеров и диалогов
from gui.theme_manager import ThemeManager
from gui.dialogs import HistoryDialog, AboutDialog
from gui.log_handler import QtLogHandler


from utils import settings as user_settings
from utils.config import APP_NAME, APP_VERSION, AUTOSAVE_FILE, ORG_NAME

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1100, 780)
        self.setMinimumSize(900, 620)

        # --- НАСТРОЙКА ЛОГГЕРА ДЛЯ GUI ---
        self.qt_log_handler = QtLogHandler()
        # Формат для интерфейса (без имени модуля, чтобы не занимать много места)
        self.qt_log_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(message)s", "%H:%M:%S"
            )
        )
        logging.getLogger().addHandler(self.qt_log_handler)

        # Сохранение геометрии
        self.settings = QSettings(ORG_NAME, APP_NAME)
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
            "QListWidget { background: #1e293b; color: white; border: none; padding-top: 10px; }"
            "QListWidget::item { padding: 12px; }"
            "QListWidget::item:selected { background: #3b82f6; }"
        )

        # Контент (справа)
        self.stack = QStackedWidget()

        # Создаем вкладки и сохраняем ссылки на них для прямого доступа
        self.scan_tab = ScanTab()
        self.disk_tab = DiskAnalysisTab()
        self.hogs_tab = SpaceHogsTab()
        self.junk_tab = JunkCleanerTab()
        self.logs_tab = LogsTab()

        self.pages = [
            ("🔍 Поиск дубликатов", self.scan_tab),
            ("📊 Анализ диска", self.disk_tab),
            ("🐷 Большие файлы", self.hogs_tab),
            ("🧹 Очистка мусора", self.junk_tab),
            ("📝 Логи", self.logs_tab),
        ]

        for name, widget in self.pages:
            self.sidebar.addItem(QListWidgetItem(name))
            self.stack.addWidget(widget)

        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

        lay.addWidget(self.sidebar)
        lay.addWidget(self.stack, 1)

        # Подключаем сигнал логгера к текстовому полю вкладки "Логи"
        self.qt_log_handler.log_signal.connect(self.logs_tab.append_log)

        # Прокидываем сигнал из анализа диска
        self.disk_tab.find_duplicates_requested.connect(self._jump_dups)

        # Сохранение ширины колонок (пример для таблицы больших файлов)
        hogs_state = self.settings.value("hogs_table/header")
        if hogs_state:
            self.hogs_tab.table.horizontalHeader().restoreState(hogs_state)

    def _build_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self.tray.setToolTip(APP_NAME)

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

        # Инструменты
        tm = mb.addMenu("Инструменты")
        tm.addAction("Очистка кэшей и мусора", self._goto_junk_cleaner)
        tm.addAction("История операций", lambda: HistoryDialog(self).exec())

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

        # --- Справка ---
        help_menu = mb.addMenu("Справка")
        help_menu.addAction("О программе", lambda: AboutDialog(self).exec())

    def _jump_dups(self, path: str):
        """Переход с вкладки анализа диска на поиск дубликатов по пути."""
        self.sidebar.setCurrentRow(0)

        p = Path(path)
        if p.is_file():
            p = p.parent

        self.scan_tab.path_edit.setText(str(p))
        self.scan_tab.mode_combo.setCurrentIndex(0)

    def _goto_junk_cleaner(self):
        """Переключает на вкладку очистки мусора и разворачивает окно."""
        self.sidebar.setCurrentRow(3)  # Индекс вкладки "Очистка мусора"
        self.showNormal()
        self.activateWindow()

    def _spin_tray(self):
        """Управление спиннером в трее"""
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
        """Уведомление в системном трее."""
        if self.tray.isSystemTrayAvailable():
            self.tray.showMessage(
                title, message, QSystemTrayIcon.Information, 3000
            )

    def _check_autosave(self):
        """Проверяет наличие файла автосохранения при запуске."""
        if AUTOSAVE_FILE.exists():
            res = QMessageBox.question(
                self,
                "Восстановление",
                "Найдены результаты прошлого поиска. Восстановить их?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if res == QMessageBox.Yes:
                self.scan_tab.restore_autosave()

    def closeEvent(self, event):
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue(
            "hogs_table/header",
            self.hogs_tab.table.horizontalHeader().saveState(),
        )
        super().closeEvent(event)
