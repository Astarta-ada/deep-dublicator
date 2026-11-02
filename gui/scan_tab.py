"""Вкладка поиска дубликатов."""

import csv
import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QTimer, QModelIndex
from PySide6.QtGui import (
    QDesktopServices,
    QKeySequence,
    QShortcut,
    QStandardItemModel,
    QColor,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QCheckBox,
    QFileDialog,
    QComboBox,
    QMessageBox,
    QProgressBar,
    QSplitter,
    QMenu,
    QFrame,
    QToolButton,
    QSlider,
    QAbstractItemView,
    QTabBar,
    QTreeView,
    QHeaderView,
)


from core.session import save_session, load_session, build_session_from_groups
from core.reports import export_txt, export_html, export_deletion_list
from core.workers import ScanWorker, ApplyWorker
from gui.filter_panel import FilterPanel
from gui.preview_panel import PreviewPanel
from gui.result_filter_bar import ResultFilterBar
from utils.helpers import human_size
from gui.models import DuplicateDelegate, DuplicateItem
from gui.dialogs import DiffDialog, SliderDialog
from utils import settings as user_settings
from utils.config import EMPTY_FILE_HASH, DEFAULT_HASH_WORKERS, AUTOSAVE_FILE
from utils.constants import (
    TEXT_EXTS,
    IMAGE_EXTS,
    get_category,
    ROLE_PATH,
    ROLE_IS_ORIGINAL,
    ROLE_IS_CHECKED,
    ROLE_IS_GROUP,
    ROLE_IS_CATEGORY,
)

log = logging.getLogger(__name__)


class ScanTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.apply_worker = None
        # self.groups = []
        self.last_result = {}
        self._status = "Готово"
        self._sort_descending = True
        self._build_ui()
        self._setup_hotkeys()
        self.setAcceptDrops(True)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # --- Кнопка сворачивания настроек ---
        self.btn_toggle = QToolButton()
        self.btn_toggle.setText("⚙️ Настройки (Свернуть)")
        self.btn_toggle.setCheckable(True)
        self.btn_toggle.setChecked(True)
        self.btn_toggle.setStyleSheet(
            "QToolButton { border: none; font-weight: bold; color: #2563eb; }"
        )
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.clicked.connect(self._toggle_settings)
        root.addWidget(self.btn_toggle)

        # --- Контейнер настроек ---
        self.settings_widget = QWidget()
        settings = QVBoxLayout(self.settings_widget)
        settings.setContentsMargins(0, 0, 0, 0)
        settings.setSpacing(10)

        # Путь
        top = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(
            "Директория для поиска или перетащите папку сюда…"
        )
        top.addWidget(QLabel("Папка:"))
        top.addWidget(self.path_edit, 1)
        browse_btn = QPushButton("Обзор…")
        browse_btn.clicked.connect(self._browse)
        top.addWidget(browse_btn)
        settings.addLayout(top)

        # Режим и чекбоксы
        mode_row = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Точные дубликаты (Хеш)", "strict")
        self.mode_combo.addItem("Похожие фото (pHash)", "similar_img")
        self.mode_combo.addItem("Похожие видео", "similar_vid")
        self.mode_combo.addItem("Аудио по тегам", "audio")
        self.mode_combo.addItem("По имени файла", "name")
        self.mode_combo.addItem("Мусорные файлы (Нули)", "zero")
        self.mode_combo.addItem("🔗 Поиск ссылок (Links)", "links")
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)

        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItem("xxHash (Самый быстрый)", "xxhash")
        self.algorithm_combo.addItem("MD5 (Стандартный)", "md5")
        self.algorithm_combo.addItem("SHA-256 (Надёжный)", "sha256")

        mode_row.addWidget(QLabel("Алгоритм:"))
        mode_row.addWidget(self.algorithm_combo)
        mode_row.addSpacing(16)

        self.phash_lbl = QLabel("Порог:")
        self.phash_lbl.hide()
        self.phash_slider = QSlider(Qt.Horizontal)
        self.phash_slider.setRange(0, 20)
        self.phash_slider.setValue(8)
        self.phash_slider.setFixedWidth(100)
        self.phash_slider.hide()

        mode_row.addWidget(QLabel("Режим:"))
        mode_row.addWidget(self.mode_combo)
        mode_row.addWidget(self.phash_lbl)
        mode_row.addWidget(self.phash_slider)
        mode_row.addSpacing(16)

        self.rec_cb = QCheckBox("Рекурсивно")
        self.rec_cb.setChecked(True)
        self.cache_cb = QCheckBox("Кэш")
        self.cache_cb.setChecked(True)
        mode_row.addWidget(self.rec_cb)
        mode_row.addWidget(self.cache_cb)
        mode_row.addStretch()
        settings.addLayout(mode_row)

        # Глобы
        self.glob_edit = QLineEdit()
        self.glob_edit.setPlaceholderText(
            "Исключить по маске (glob): *.tmp, ~$*, desktop.ini"
        )
        settings.addWidget(self.glob_edit)

        # Целевой файл (для ссылок)
        self.target_file_layout = QHBoxLayout()
        self.target_file_edit = QLineEdit()
        self.target_file_edit.setPlaceholderText(
            "Выберите файл, ссылки на который нужно найти..."
        )
        btn_browse_target = QPushButton("Выбрать файл…")
        btn_browse_target.clicked.connect(self._browse_target_file)
        self.target_file_layout.addWidget(QLabel("Целевой файл:"))
        self.target_file_layout.addWidget(self.target_file_edit, 1)
        self.target_file_layout.addWidget(btn_browse_target)

        self.target_file_container = QWidget()
        self.target_file_container.setLayout(self.target_file_layout)
        self.target_file_container.hide()
        settings.addWidget(self.target_file_container)

        # Фильтры
        self.filter_panel = FilterPanel()
        settings.addWidget(self.filter_panel)
        root.addWidget(self.settings_widget)

        # --- Кнопка поиска (всегда на виду) ---
        self.scan_btn = QPushButton("🔍  Найти дубликаты")
        self.scan_btn.setProperty("class", "primary")
        self.scan_btn.setMinimumHeight(44)
        self.scan_btn.setCursor(Qt.PointingHandCursor)
        self.scan_btn.clicked.connect(self._start)
        root.addWidget(self.scan_btn)

        # Статус и прогресс
        self.status = QLabel(self._status)
        self.status.setObjectName("statusLabel")
        root.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.hide()
        root.addWidget(self.progress)

        # Фильтр результатов
        self.res_filter = ResultFilterBar()
        self.res_filter.filters_changed.connect(self._apply_filter)
        root.addWidget(self.res_filter)

        # Инструменты
        tools = QHBoxLayout()
        self.sort_btn = QPushButton("↕ Сортировать (↓)")
        self.sort_btn.clicked.connect(self._sort)

        self.collapse_btn = QPushButton("⯅ Свернуть все")
        self.collapse_btn.setCheckable(True)
        self.collapse_btn.toggled.connect(self._collapse)

        self.dry_run = QCheckBox("Симуляция (Dry-run)")
        self.dry_run.setChecked(False)
        self.dry_run.setToolTip(
            "Показать, что будет сделано, но не удалять файлы"
        )

        self.vt_btn = QPushButton("🛡 VirusTotal")
        self.vt_btn.setToolTip("Проверить хеш первого файла в базе VirusTotal")
        self.vt_btn.clicked.connect(self._check_vt)

        tools.addWidget(self.sort_btn)
        tools.addWidget(self.collapse_btn)
        tools.addWidget(self.dry_run)
        tools.addWidget(self.vt_btn)
        tools.addStretch()
        root.addLayout(tools)

        # --- Вкладки категорий ---
        self.category_tabs = QTabBar()
        self.category_tabs.setExpanding(False)
        self.category_tabs.setDrawBase(False)
        self.category_tabs.setStyleSheet(
            "QTabBar::tab { padding: 6px 12px; margin-right: 4px; }"
        )
        self.category_tabs.currentChanged.connect(self._apply_category_filter)
        root.addWidget(self.category_tabs)

        # Сплиттер (Список + Превью)
        split = QSplitter(Qt.Horizontal)

        self.tree = QTreeView()
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree.clicked.connect(self._on_tree_click)
        self.tree.setItemDelegateForColumn(0, DuplicateDelegate(self.tree))
        self.tree.expanded.connect(self._on_category_expanded)

        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Файл / Группа"])
        self.tree.setModel(self.model)
        self.tree.header().setSectionResizeMode(QHeaderView.Stretch)

        split.addWidget(self.tree)

        # Добавляем превью в сплиттер
        self.preview = PreviewPanel()
        split.addWidget(self.preview)

        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)
        split.setSizes([720, 320])
        root.addWidget(split, 1)

        # Панель действий
        actions = QHBoxLayout()
        actions.setSpacing(8)

        self.action_combo = QComboBox()
        self.action_combo.addItem("Удалить в корзину", "trash")
        self.action_combo.addItem("Удалить навсегда", "delete")
        self.action_combo.addItem("Заменить симлинком", "symlink")
        self.action_combo.addItem("Заменить хардлинком", "hardlink")
        self.action_combo.addItem("Переместить в бэкап…", "backup")
        self.action_combo.addItem("Переименовать копии", "rename")

        actions.addWidget(QLabel("Действие:"))
        actions.addWidget(self.action_combo)

        self.select_all_btn = QPushButton("☑ Отметить все")
        self.select_all_btn.clicked.connect(self._sel_all)
        actions.addStretch()
        actions.addWidget(self.select_all_btn)

        self.btn_apply = QPushButton("Применить к отмеченным")
        self.btn_apply.setProperty("class", "danger")
        self.btn_apply.setCursor(Qt.PointingHandCursor)
        self.btn_apply.clicked.connect(self._apply)
        actions.addWidget(self.btn_apply)

        exp_btn = QPushButton("Экспорт ▾")
        em = QMenu(exp_btn)
        em.addAction("💾 Сохранить сессию", self._save_sess)
        em.addAction("📂 Загрузить сессию", self._load_sess)
        em.addSeparator()
        em.addAction("📊 CSV-отчёт", self._exp_csv)
        em.addAction("📄 HTML-отчёт", self._exp_html)
        em.addAction("📋 Список на удаление (.txt)", self._exp_txt)
        em.addAction("💻 Скрипт для удаления (.bat)", self._exp_script)
        exp_btn.setMenu(em)
        actions.addWidget(exp_btn)

        root.addLayout(actions)

    def _setup_hotkeys(self):
        QShortcut(QKeySequence("F5"), self, activated=self._start)
        QShortcut(
            QKeySequence("Ctrl+F"),
            self,
            activated=lambda: self.res_filter.search.setFocus(),
        )
        QShortcut(QKeySequence("Delete"), self, activated=self._apply)

    def _toggle_settings(self, checked: bool):
        self.settings_widget.setVisible(checked)
        self.btn_toggle.setText(
            "⚙️ Настройки (Свернуть)"
            if checked
            else "⚙️ Настройки (Развернуть)"
        )

    def _mode_changed(self, idx):
        mode = self.mode_combo.currentData()
        show_phash = mode in ("similar_img", "similar_vid")
        self.phash_lbl.setVisible(show_phash)
        self.phash_slider.setVisible(show_phash)
        self.target_file_container.setVisible(mode == "links")

    def _browse_target_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите файл")
        if path:
            self.target_file_edit.setText(path)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(
            self, "Выберите директорию", self.path_edit.text() or ""
        )
        if d:
            self.path_edit.setText(d)

    def _start(self):

        # Если предыдущий поток еще работает - останавливаем его
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()

        p = Path(self.path_edit.text().strip())
        if not p.is_dir():
            QMessageBox.warning(
                self, "Ошибка", "Укажите существующую директорию"
            )
            return

        self._clear()
        self.scan_btn.setEnabled(False)
        self.progress.show()
        self.progress.setValue(0)

        self.btn_toggle.setChecked(False)
        self._toggle_settings(False)

        globs = [
            g.strip() for g in self.glob_edit.text().split(",") if g.strip()
        ]
        target_file = (
            self.target_file_edit.text().strip()
            if self.mode_combo.currentData() == "links"
            else None
        )

        # Спиннер в трее
        main_win = self.window()
        if hasattr(main_win, "start_tray_spinner"):
            main_win.start_tray_spinner()

        self.worker = ScanWorker(
            p,
            self.rec_cb.isChecked(),
            self.filter_panel.get_min_size(),
            self.filter_panel.get_max_size(),
            self.filter_panel.get_extensions(),
            self.filter_panel.include_empty(),
            self.cache_cb.isChecked(),
            self.mode_combo.currentData(),
            globs,
            self.phash_slider.value(),
            algorithm=self.algorithm_combo.currentData(),
            target_file=target_file,
        )
        self.worker.progress_msg.connect(self.status.setText)
        self.worker.progress_bytes.connect(self._prog_bytes)
        self.worker.finished_ok.connect(self._done)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _prog_bytes(self, stage, done, total, eta, current_file=""):
        try:
            if total > 0:
                pct = max(0, min(100, int(100 * done / total)))
                self.progress.setValue(pct)

                # Безопасное форматирование ETA
                e_str = (
                    f"{int(eta//60)}м {int(eta%60)}с"
                    if eta > 0 and eta != float("inf")
                    else "0с"
                )

                stage_ru = {
                    "quick_hash": "быстрый хеш",
                    "full_hash": "полный хеш",
                }.get(stage, stage)
                file_part = ""
                if current_file:
                    name = current_file
                    if len(name) > 35:
                        name = name[:32] + "…"
                    file_part = f" | {name}"

                self.progress.setFormat(
                    f"{stage_ru}{file_part}  | осталось: {e_str}"
                )
        except (OverflowError, ValueError, ZeroDivisionError):
            pass

    def _on_failed(self, msg: str):
        self.progress.hide()
        self.scan_btn.setEnabled(True)
        self.btn_toggle.setChecked(True)
        self._toggle_settings(True)

        main_win = self.window()
        if hasattr(main_win, "stop_tray_spinner"):
            main_win.stop_tray_spinner()

        QMessageBox.critical(self, "Ошибка", msg)

    def _done(self, res):
        self.progress.hide()
        self.scan_btn.setEnabled(True)
        self.last_result = res

        main_win = self.window()
        if hasattr(main_win, "stop_tray_spinner"):
            main_win.stop_tray_spinner()

        if not res:
            self._status = "Дубликаты не найдены 🎉"
            self.status.setText(self._status)
            return

        self._status = f"Найдено групп: {len(res)}, файлов: {sum(len(v) for v in res.values())}"
        self.status.setText(self._status)
        self._populate(res)

        # --- АВТОСОХРАНЕНИЕ ---
        QTimer.singleShot(1000, self._do_autosave)

        # Уведомление в трей
        if hasattr(main_win, "notify"):
            main_win.notify("Поиск завершен", f"Найдено групп: {len(res)}")

    def restore_autosave(self):
        """Загружает сессию из автосохранения."""
        if not AUTOSAVE_FILE.exists():
            return
        try:
            s = load_session(AUTOSAVE_FILE)
            res = {
                g.hash_key: [
                    Path(f.path) for f in g.files if Path(f.path).exists()
                ]
                for g in s.groups
            }
            res = {k: v for k, v in res.items() if len(v) > 1}

            if res:
                self._status = f"Восстановлено из кэша: {len(res)} групп"
                self.status.setText(self._status)
                self._populate(res, keep_orig=True)
        except Exception as e:
            log.error("Не удалось восстановить сессию: %s", e)

    def _populate(self, res, keep_orig=False):
        self.model.clear()
        self.model.setHorizontalHeaderLabels(["Файл / Группа"])
        self.last_result = res
        self._raw_cats = {}

        cats = {}
        for h, paths in res.items():
            if not paths:
                continue
            if h == EMPTY_FILE_HASH:
                c = "📭 Пустые файлы"
            elif h == "ZERO_FILL":
                c = "🗑 Мусорные файлы"
            elif h == "LINKS":
                c = "🔗 Ссылки на файл"
            else:
                c = get_category(paths[0].suffix)
            cats.setdefault(c, []).append((h, paths))

        self.category_tabs.blockSignals(True)
        while self.category_tabs.count() > 0:
            self.category_tabs.removeTab(0)
        self.category_tabs.addTab("Все")
        for c_name in sorted(cats.keys()):
            self.category_tabs.addTab(c_name)
        self.category_tabs.setCurrentIndex(0)
        self.category_tabs.blockSignals(False)

        root = self.model.invisibleRootItem()
        for c_name in sorted(cats.keys()):
            cat_item = DuplicateItem(
                f"{c_name} ({len(cats[c_name])} групп)", is_category=True
            )
            cat_item.setBackground(QColor("#e2e8f0"))
            # Пасхалка для пагинации: сохраняем данные в категорию
            self._raw_cats[c_name] = cats[c_name]
            # Добавляем пустышку, чтобы появилась стрелочка раскрытия
            cat_item.appendRow(DuplicateItem("Загрузка...", is_group=True))
            root.appendRow(cat_item)

    def _on_category_expanded(self, index):
        """Ленивая загрузка групп при раскрытии категории."""
        cat_item = self.model.itemFromIndex(index)
        if not cat_item or not cat_item.is_category:
            return

        if cat_item.rowCount() > 1 or (
            cat_item.rowCount() == 1
            and cat_item.child(0).text() != "Загрузка..."
        ):
            return

        cat_item.removeRow(0)

        c_name = cat_item.text().split(" (")[0]
        groups_data = self._raw_cats.get(c_name, [])

        # Чанкинг - добавляем группы порциями, чтобы не вешать UI
        def add_chunk(start_idx):
            for i in range(start_idx, min(start_idx + 50, len(groups_data))):
                h, paths = groups_data[i]
                size_str = (
                    human_size(paths[0].stat().st_size) if paths else "?"
                )
                group_item = DuplicateItem(
                    f"Группа ({len(paths)} шт) — {size_str}", is_group=True
                )
                for j, p in enumerate(paths):
                    file_item = DuplicateItem(str(p), path=p)
                    file_item.setData(j == 0, ROLE_IS_ORIGINAL)
                    file_item.setData(j != 0, ROLE_IS_CHECKED)
                    group_item.appendRow(file_item)
                cat_item.appendRow(group_item)

            if start_idx + 50 < len(groups_data):
                QTimer.singleShot(10, lambda: add_chunk(start_idx + 50))

        add_chunk(0)
        self.tree.expand(index)
        self._update_selection_status()

    def _clear(self):
        self.model.clear()
        self.model.setHorizontalHeaderLabels(["Файл / Группа"])
        self.preview.clear()
        self.last_result = {}

    def _sel_all(self):
        root = self.model.invisibleRootItem()
        all_checked = True
        for i in range(root.rowCount()):
            cat = root.child(i)
            for j in range(cat.rowCount()):
                grp = cat.child(j)
                for k in range(grp.rowCount()):
                    f = grp.child(k)
                    if not f.data(ROLE_IS_ORIGINAL) and not f.data(
                        ROLE_IS_CHECKED
                    ):
                        all_checked = False
                        break

        select = not all_checked

        for i in range(root.rowCount()):
            cat = root.child(i)
            for j in range(cat.rowCount()):
                grp = cat.child(j)
                for k in range(grp.rowCount()):
                    f = grp.child(k)
                    if not f.data(ROLE_IS_ORIGINAL):
                        f.setData(select, ROLE_IS_CHECKED)

        self._update_selection_status()

    def _update_selection_status(self):
        total_checked = 0
        total_possible = 0
        root = self.model.invisibleRootItem()

        for i in range(root.rowCount()):
            cat_item = root.child(i)
            for j in range(cat_item.rowCount()):
                group_item = cat_item.child(j)
                for k in range(group_item.rowCount()):
                    file_item = group_item.child(k)
                    total_possible += 1
                    if file_item.data(ROLE_IS_CHECKED):
                        total_checked += 1

        # Вычитаем количество оригиналов из общего числа возможных
        total_possible -= self._count_groups()

        if total_checked > 0:
            self.select_all_btn.setText("☐ Снять все")
        else:
            self.select_all_btn.setText("☑ Отметить все")

        self.status.setText(f"{self._status} | отмечено: {total_checked}")

    def _count_groups(self):
        count = 0
        root = self.model.invisibleRootItem()
        for i in range(root.rowCount()):
            count += root.child(i).rowCount()
        return count

    def _apply_category_filter(self, index):
        """Скрывает/показывает группы в зависимости от выбранной вкладки."""
        if index < 0:
            return

        selected_cat = self.category_tabs.tabText(index)
        root = self.model.invisibleRootItem()

        for i in range(root.rowCount()):
            cat_item = root.child(i)
            is_match = selected_cat == "Все" or cat_item.text().startswith(
                selected_cat
            )
            self.tree.setRowHidden(i, QModelIndex(), not is_match)

    def _apply_filter(self):
        root = self.model.invisibleRootItem()
        for i in range(root.rowCount()):
            cat_item = root.child(i)
            for j in range(cat_item.rowCount()):
                grp_item = cat_item.child(j)

                orig = None
                paths = []
                savings = 0
                for k in range(grp_item.rowCount()):
                    f = grp_item.child(k)
                    paths.append(f.path)
                    if f.data(ROLE_IS_ORIGINAL):
                        orig = f.path
                    elif f.data(ROLE_IS_CHECKED):
                        try:
                            savings += f.path.stat().st_size
                        except:
                            pass

                matches = self.res_filter.matches(savings, paths)
                self.tree.setRowHidden(j, cat_item.index(), not matches)

    def _sort(self):
        self._sort_descending = not self._sort_descending
        arrow = "↓" if self._sort_descending else "↑"
        self.sort_btn.setText(f"↕ Сортировать ({arrow})")

        def get_savings(item):
            h, paths = item
            if not paths or h in (EMPTY_FILE_HASH, "ZERO_FILL"):
                return 0
            try:
                return paths[0].stat().st_size * (len(paths) - 1)
            except OSError:
                return 0

        sorted_res = dict(
            sorted(
                self.last_result.items(),
                key=get_savings,
                reverse=self._sort_descending,
            )
        )
        self._populate(sorted_res, keep_orig=True)

    def _collapse(self, c):
        if c:
            self.tree.collapseAll()
        else:
            self.tree.expandAll()

    def _diff(self, o, d):
        if o.suffix.lower() in TEXT_EXTS and d.suffix.lower() in TEXT_EXTS:
            DiffDialog(o, d, self).exec()
        elif o.suffix.lower() in IMAGE_EXTS:
            SliderDialog(str(o), str(d), self).exec()

    def _on_tree_click(self, index):
        item = self.model.itemFromIndex(index)
        if item and item.path:
            self.preview.show_file(item.path)

    def _apply(self):
        act = self.action_combo.currentData()
        dry = self.dry_run.isChecked()

        groups_to_process = []
        root = self.model.invisibleRootItem()

        for i in range(root.rowCount()):
            cat = root.child(i)
            for j in range(cat.rowCount()):
                grp = cat.child(j)
                orig = None
                targets = []
                for k in range(grp.rowCount()):
                    f = grp.child(k)
                    if f.data(ROLE_IS_ORIGINAL):
                        orig = f.path
                    elif f.data(ROLE_IS_CHECKED):
                        targets.append(f.path)
                if orig and targets:
                    groups_to_process.append((orig, targets))

        if not groups_to_process:
            QMessageBox.information(
                self, "Ничего не выбрано", "Отметьте файлы для обработки."
            )
            return

        bkp = None
        if act == "backup":
            d = QFileDialog.getExistingDirectory(
                self, "Выберите папку для бэкапа"
            )
            if not d:
                return
            bkp = Path(d)

        if not dry and act in ("delete", "trash"):
            confirm = QMessageBox.question(
                self,
                "Подтверждение",
                f"Вы уверены, что хотите обработать {sum(len(t) for _, t in groups_to_process)} файлов?\n"
                f"Действие: {self.action_combo.currentText()}",
            )
            if confirm != QMessageBox.Yes:
                return

        self.btn_apply.setEnabled(False)
        self.scan_btn.setEnabled(False)
        self.progress.show()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("Обработка файлов: %p%")

        main_win = self.window()
        if hasattr(main_win, "start_tray_spinner"):
            main_win.start_tray_spinner()

        # Адаптер для ApplyWorker
        class DummyGroup:
            def __init__(self, orig, targets):
                self._orig = orig
                self._targets = targets

            def selected_count(self):
                return len(self._targets)

            def get_selection(self):
                return self._orig, self._targets

        adapted_groups = [DummyGroup(o, t) for o, t in groups_to_process]

        self.apply_worker = ApplyWorker(
            adapted_groups, act, bkp, Path(self.path_edit.text()), dry
        )
        self.apply_worker.progress.connect(
            lambda cur, tot: self.progress.setValue(int(100 * cur / tot))
        )
        self.apply_worker.finished_ok.connect(self._on_apply_finished)
        self.apply_worker.start()

    def _on_apply_finished(self, total_ok, errors):
        self.progress.hide()
        self.btn_apply.setEnabled(True)
        self.scan_btn.setEnabled(True)

        main_win = self.window()
        if hasattr(main_win, "stop_tray_spinner"):
            main_win.stop_tray_spinner()

        if not self.dry_run:
            self._populate(self.last_result, keep_orig=True)

        self._update_selection_status()
        msg = f"Успешно обработано: {total_ok}"
        if errors:
            msg += f"\nОшибок: {len(errors)}"
            for p, e in errors[:5]:
                msg += f"\n  {p}: {e}"
        QMessageBox.information(self, "Готово", msg)

    def _get_sess(self):
        result = {}
        root = self.model.invisibleRootItem()
        for i in range(root.rowCount()):
            cat = root.child(i)
            for j in range(cat.rowCount()):
                grp = cat.child(j)
                orig = None
                paths = []
                for k in range(grp.rowCount()):
                    f = grp.child(k)
                    paths.append(f.path)
                    if f.data(ROLE_IS_ORIGINAL):
                        orig = f.path
                if orig and len(paths) > 1:
                    result[str(orig)] = [orig] + [
                        p for p in paths if p != orig
                    ]
        return build_session_from_groups(
            result, self.path_edit.text(), self.filter_panel.as_dict()
        )

    def _save_sess(self):
        if not self.model.rowCount():
            return
        p, _ = QFileDialog.getSaveFileName(
            self, "Сессия", "session.dupsession.json", "*.json"
        )
        if p:
            save_session(self._get_sess(), Path(p))

    def _load_sess(self):
        p, _ = QFileDialog.getOpenFileName(self, "Сессия", "", "*.json")
        if p:
            s = load_session(Path(p))
            res = {}
            for g in s.groups:
                ex = [Path(f.path) for f in g.files if Path(f.path).exists()]
                if len(ex) > 1:
                    res[g.hash_key] = ex
            self._populate(res, True)

    def _exp_csv(self):
        p, _ = QFileDialog.getSaveFileName(self, "CSV", "dups.csv", "*.csv")
        if p:
            with open(p, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["Группа", "Файл", "Размер", "Дата"])
                root = self.model.invisibleRootItem()
                for i in range(root.rowCount()):
                    cat = root.child(i)
                    for j in range(cat.rowCount()):
                        grp = cat.child(j)
                        for k in range(grp.rowCount()):
                            path = grp.child(k).path
                            try:
                                st = path.stat()
                                w.writerow(
                                    [
                                        j,
                                        str(path),
                                        st.st_size,
                                        datetime.fromtimestamp(
                                            st.st_ctime
                                        ).strftime("%Y-%m-%d"),
                                    ]
                                )
                            except:
                                pass

    def _exp_html(self):
        p, _ = QFileDialog.getSaveFileName(
            self, "HTML", "report.html", "*.html"
        )
        if p:
            export_html(self._get_sess(), Path(p))

    def _exp_txt(self):
        p, _ = QFileDialog.getSaveFileName(
            self, "Список", "delete.txt", "*.txt"
        )
        if p:
            export_deletion_list(self._get_sess(), Path(p))

    def _exp_script(self):
        p, _ = QFileDialog.getSaveFileName(
            self, "Скрипт", "delete.bat", "*.bat"
        )
        if p:
            with open(p, "w", encoding="utf-8") as f:
                f.write("@echo off\n")
                root = self.model.invisibleRootItem()
                for i in range(root.rowCount()):
                    cat = root.child(i)
                    for j in range(cat.rowCount()):
                        grp = cat.child(j)
                        for k in range(grp.rowCount()):
                            f_item = grp.child(k)
                            if f_item.data(ROLE_IS_CHECKED):
                                f.write(f'del "{f_item.path}"\n')

    def _check_vt(self):
        import requests
        from utils.settings import get_vt_api_key, set_vt_api_key
        from core.hasher import hash_file

        api_key = get_vt_api_key()
        if not api_key:
            from PySide6.QtWidgets import QInputDialog

            key, ok = QInputDialog.getText(
                self, "VirusTotal API", "Введите API-ключ VirusTotal:"
            )
            if ok and key:
                set_vt_api_key(key)
                api_key = key
            else:
                return

        if self.model.rowCount() == 0:
            return
        first_file = self.model.item(0, 0).child(0).child(0).path

        h = hash_file(first_file)
        if not h:
            return

        self.status.setText("Запрос к VirusTotal...")
        try:
            r = requests.get(
                f"https://www.virustotal.com/api/v3/files/{h}",
                headers={"x-apikey": api_key},
            )
            if r.status_code == 200:
                stats = r.json()["data"]["attributes"]["last_analysis_stats"]
                msg = f"Файл: {first_file.name}\nБезопасно: {stats['harmless']}\nВредоносно: {stats['malicious']}\nПодозрительно: {stats['suspicious']}"
                QMessageBox.information(self, "VirusTotal", msg)
            elif r.status_code == 404:
                QMessageBox.information(
                    self,
                    "VirusTotal",
                    "Файл еще не загружен в базу VirusTotal.",
                )
            else:
                QMessageBox.warning(
                    self, "Ошибка", f"Ошибка API: {r.status_code}"
                )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
        self.status.setText(self._status)

    def _do_autosave(self):
        """Фоновое (отложенное) сохранение сессии."""
        if self.model.rowCount() == 0:
            return
        try:
            save_session(self._get_sess(), AUTOSAVE_FILE)
            log.info("Автосохранение завершено.")
        except Exception as e:
            log.error("Не удалось автосохранить сессию: %s", e)

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
                    e.acceptProposedAction()
                    return
        e.ignore()
