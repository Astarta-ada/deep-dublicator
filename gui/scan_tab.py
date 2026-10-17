"""Вкладка поиска дубликатов."""

import csv
import logging
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QCheckBox,
    QFileDialog,
    QScrollArea,
    QComboBox,
    QMessageBox,
    QProgressBar,
    QSplitter,
    QMenu,
    QFrame,
    QToolButton,
    QSlider,
)

from core.scanner import scan_directory
from core.duplicate_finder import (
    find_duplicates,
    find_similar_images,
    find_similar_videos,
    find_audio_duplicates,
    find_zero_fill_files,
    find_by_name,
    find_links_to_file,
)
from core.file_ops import apply_action_to_group, rename_duplicates
from core.session import save_session, load_session, build_session_from_groups
from core.reports import export_txt, export_html, export_deletion_list
from gui.filter_panel import FilterPanel
from gui.preview_panel import PreviewPanel
from gui.result_filter_bar import ResultFilterBar
from gui.widgets import DuplicateGroupWidget, CategoryGroupWidget, human_size
from utils import settings as user_settings
from utils.config import EMPTY_FILE_HASH, DEFAULT_HASH_WORKERS

log = logging.getLogger(__name__)

TEXT_EXTS = {
    ".txt",
    ".py",
    ".js",
    ".ts",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".cs",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".html",
    ".css",
    ".scss",
    ".xml",
    ".json",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".conf",
    ".md",
    ".rst",
    ".log",
    ".csv",
    ".tsv",
    ".sh",
    ".bat",
    ".ps1",
    ".sql",
}

CATEGORIES = {
    "🖼 Изображения": {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".webp",
        ".tiff",
        ".svg",
        ".heic",
    },
    "🎬 Видео": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"},
    "🎵 Аудио": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"},
    "📄 Документы": {
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".txt",
        ".rtf",
        ".odt",
    },
    "🗜 Архивы": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"},
    "💻 Код и скрипты": {
        ".py",
        ".js",
        ".ts",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".cs",
        ".go",
        ".rs",
        ".html",
        ".css",
        ".json",
        ".xml",
    },
}


def get_category(ext: str) -> str:
    ext = ext.lower()
    for cat, exts in CATEGORIES.items():
        if ext in exts:
            return cat
    return "📦 Другие файлы"


class ScanWorker(QThread):
    progress_msg = Signal(str)
    progress_bytes = Signal(str, int, int, float)
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        root,
        recursive,
        min_size,
        max_size,
        extensions,
        include_empty,
        use_cache,
        mode,
        globs,
        phash,
        target_file=None,
    ):
        super().__init__()
        self.root = root
        self.recursive = recursive
        self.min_size = min_size
        self.max_size = max_size
        self.extensions = extensions
        self.include_empty = include_empty
        self.use_cache = use_cache
        self.mode = mode
        self.globs = globs
        self.phash = phash
        self.target_file = Path(target_file) if target_file else None

    def run(self):
        try:
            self.progress_msg.emit("Сканирование директории…")
            is_links = self.mode == "links"
            files = list(
                scan_directory(
                    self.root,
                    self.recursive,
                    self.min_size,
                    self.max_size,
                    self.extensions,
                    exclude_globs=self.globs,
                    include_links=is_links,
                )
            )
            self.progress_msg.emit(f"Найдено {len(files)} файлов. Анализ…")

            start = time.time()

            def cb(stage, done, total):
                el = time.time() - start
                speed = done / el if el > 0 else 0
                eta = (total - done) / speed if speed > 0 else 0
                self.progress_bytes.emit(stage, done, total, eta)

            if self.mode == "strict":
                res = find_duplicates(
                    files,
                    cb,
                    self.include_empty,
                    self.use_cache,
                    DEFAULT_HASH_WORKERS,
                )
            elif self.mode == "similar_img":
                res = find_similar_images(files, self.phash)
            elif self.mode == "similar_vid":
                res = find_similar_videos(files, self.phash)
            elif self.mode == "audio":
                res = find_audio_duplicates(files)
            elif self.mode == "name":
                res = find_by_name(files)
            elif self.mode == "zero":
                res = find_zero_fill_files(files)
            elif self.mode == "links":
                if not self.target_file or not self.target_file.exists():
                    raise ValueError(
                        "Целевой файл не выбран или не существует"
                    )
                self.progress_msg.emit("Поиск ссылок…")
                res = find_links_to_file(self.target_file, files)
            else:
                res = {}

            self.finished_ok.emit(res)
        except Exception as e:
            log.exception("Ошибка сканирования")
            self.failed.emit(str(e))


class ApplyWorker(QThread):
    """Фоновый поток для удаления/замены файлов, чтобы интерфейс не зависал."""

    progress = Signal(int, int)  # обработано, всего
    finished_ok = Signal(int, list)  # успешно, список ошибок

    def __init__(self, groups, action, backup_dir, base_root, dry_run):
        super().__init__()
        self.groups = groups
        self.action = action
        self.backup_dir = backup_dir
        self.base_root = base_root
        self.dry_run = dry_run

    def run(self):
        total_ok = 0
        all_errors = []

        # Считаем общее количество целей
        total_targets = sum(g.selected_count() for g in self.groups)
        processed = 0

        for g in list(self.groups):
            o, targets = g.get_selection()
            if not targets:
                continue

            if self.action == "rename":
                a, b = rename_duplicates(o, targets, self.dry_run)
            else:
                a, b = apply_action_to_group(
                    o,
                    targets,
                    self.action,
                    self.backup_dir,
                    self.base_root,
                    self.dry_run,
                )

            total_ok += a
            all_errors.extend(b)
            processed += len(targets)
            self.progress.emit(processed, total_targets)

        self.finished_ok.emit(total_ok, all_errors)


class ScanTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.apply_worker = None
        self.groups = []
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

        # Контейнер настроек
        self.settings_widget = QWidget()
        settings = QVBoxLayout(self.settings_widget)
        settings.setContentsMargins(0, 0, 0, 0)
        settings.setSpacing(10)

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

        self.glob_edit = QLineEdit()
        self.glob_edit.setPlaceholderText(
            "Исключить по маске (glob): *.tmp, ~$*, desktop.ini"
        )
        settings.addWidget(self.glob_edit)

        # Поле для выбора целевого файла (для режима ссылок)
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

        self.filter_panel = FilterPanel()
        settings.addWidget(self.filter_panel)

        root.addWidget(self.settings_widget)

        # Кнопка поиска (ВНЕ сворачиваемого блока)
        self.scan_btn = QPushButton("🔍  Найти дубликаты")
        self.scan_btn.setProperty("class", "primary")
        self.scan_btn.setMinimumHeight(44)
        self.scan_btn.setCursor(Qt.PointingHandCursor)
        self.scan_btn.clicked.connect(self._start)
        root.addWidget(self.scan_btn)

        self.status = QLabel(self._status)
        self.status.setObjectName("statusLabel")
        root.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.hide()
        root.addWidget(self.progress)

        self.res_filter = ResultFilterBar()
        self.res_filter.filters_changed.connect(self._apply_filter)
        root.addWidget(self.res_filter)

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

        tools.addWidget(self.sort_btn)
        tools.addWidget(self.collapse_btn)
        tools.addWidget(self.dry_run)
        tools.addStretch()
        root.addLayout(tools)

        split = QSplitter(Qt.Horizontal)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.res_container = QWidget()
        self.res_layout = QVBoxLayout(self.res_container)
        self.res_layout.setSpacing(16)
        self.res_layout.addStretch()
        self.scroll.setWidget(self.res_container)
        split.addWidget(self.scroll)

        self.preview = PreviewPanel()
        split.addWidget(self.preview)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)
        split.setSizes([720, 320])
        root.addWidget(split, 1)

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

    def _browse(self):
        d = QFileDialog.getExistingDirectory(
            self, "Выберите директорию", self.path_edit.text() or ""
        )
        if d:
            self.path_edit.setText(d)

    def _start(self):
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
            target_file=target_file,
        )
        self.worker.progress_msg.connect(self.status.setText)
        self.worker.progress_bytes.connect(self._prog_bytes)
        self.worker.finished_ok.connect(self._done)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _prog_bytes(self, stage, done, total, eta):
        if total > 0:
            self.progress.setValue(int(100 * done / total))
            e_str = f"{int(eta//60)}м {int(eta%60)}с" if eta > 0 else "0с"
            stage_ru = {
                "quick_hash": "быстрый хеш",
                "full_hash": "полный хеш",
            }.get(stage, stage)
            self.progress.setFormat(f"{stage_ru} | осталось: {e_str}")

    def _on_failed(self, msg: str):
        self.progress.hide()
        self.scan_btn.setEnabled(True)
        self.btn_toggle.setChecked(True)
        self._toggle_settings(True)
        QMessageBox.critical(self, "Ошибка", msg)

    def _done(self, res):
        self.progress.hide()
        self.scan_btn.setEnabled(True)
        self.last_result = res

        if not res:
            self._status = "Дубликаты не найдены 🎉"
            self.status.setText(self._status)
            return

        self._status = f"Найдено групп: {len(res)}, файлов: {sum(len(v) for v in res.values())}"
        self.status.setText(self._status)
        self._populate(res)

    def _populate(self, res, keep_orig=False):
        origs = (
            {g.hash_key: g.get_original() for g in self.groups}
            if keep_orig
            else {}
        )
        self._clear()
        self.last_result = res

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

        show_prev = user_settings._settings().value(
            "group_preview", True, bool
        )
        sorted_cats = sorted(cats.keys())
        if "📭 Пустые файлы" in sorted_cats:
            sorted_cats.remove("📭 Пустые файлы")
            sorted_cats.insert(0, "📭 Пустые файлы")

        for c_name in sorted_cats:
            cw = CategoryGroupWidget(c_name, len(cats[c_name]))
            for h, paths in cats[c_name]:
                w = DuplicateGroupWidget(h, paths, show_preview=show_prev)
                if keep_orig and h in origs and origs[h] in paths:
                    w.set_original_index(paths.index(origs[h]))

                w.changed.connect(self._upd_stat)
                w.file_clicked.connect(self.preview.show_file)
                w.file_double_clicked.connect(
                    lambda p: QDesktopServices.openUrl(
                        QUrl.fromLocalFile(str(p))
                    )
                )
                w.compare_requested.connect(self._diff)

                self.groups.append(w)
                cw.add_group(w)
            self.res_layout.addWidget(cw)

        self.res_layout.addStretch()
        self._apply_filter()
        self._upd_stat()

    def _clear(self):
        self.groups.clear()
        while self.res_layout.count():
            it = self.res_layout.takeAt(0)
            if it is not None:
                w = it.widget()
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()
        self.preview.clear()
        self.last_result = {}

    def _sel_all(self):
        poss, chk = 0, 0
        for g in self.groups:
            o = g._get_original_index()
            for i, c in enumerate(g._checks):
                if i != o:
                    poss += 1
                    chk += c.isChecked()
        sel = chk < poss
        for g in self.groups:
            o = g._get_original_index()
            for i in range(len(g.paths)):
                if i != o:
                    g.set_selected(i, sel)
        self._upd_stat()

    def _upd_stat(self):
        tot = sum(g.selected_count() for g in self.groups)
        if self.groups:
            self.status.setText(f"{self._status} | отмечено: {tot}")
            self.select_all_btn.setText(
                "☐ Снять все" if tot > 0 else "☑ Отметить все"
            )
        else:
            self.status.setText(self._status)

    def _apply_filter(self):
        for g in self.groups:
            savings = g.savings_bytes()
            g.setVisible(self.res_filter.matches(savings, g.paths))
        self._upd_stat()

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
        for g in self.groups:
            g.set_collapsed(c)

    def _diff(self, o, d):
        if o.suffix.lower() in TEXT_EXTS and d.suffix.lower() in TEXT_EXTS:
            from gui.diff_dialog import DiffDialog

            DiffDialog(o, d, self).exec()
        elif o.suffix.lower() in {".jpg", ".png", ".jpeg", ".webp"}:
            from gui.slider_dialog import SliderDialog

            SliderDialog(str(o), str(d), self).exec()

    def _apply(self):
        act = self.action_combo.currentData()
        dry = self.dry_run.isChecked()

        groups_to_process = [g for g in self.groups if g.selected_count() > 0]
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
                f"Вы уверены, что хотите обработать {sum(g.selected_count() for g in groups_to_process)} файлов?\n"
                f"Действие: {self.action_combo.currentText()}",
            )
            if confirm != QMessageBox.Yes:
                return

        # Запускаем в фоновом потоке, чтобы UI не зависал
        self.btn_apply.setEnabled(False)
        self.scan_btn.setEnabled(False)
        self.progress.show()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("Обработка файлов: %p%")

        self.apply_worker = ApplyWorker(
            groups_to_process, act, bkp, Path(self.path_edit.text()), dry
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

        # Удаляем обработанные группы из интерфейса
        # Собираем хэши групп, где не было ошибок
        # (Для простоты просто перерисовываем список, оставляя только те, где есть ошибки или dry_run)
        if not self.dry_run:
            # Перерисовываем интерфейс на основе оставшихся групп
            # Но проще просто удалить группы, которые полностью обработались
            # В идеале нужно перерисовать по last_result, но мы просто обновим список
            pass

        self._upd_stat()
        msg = f"Успешно обработано: {total_ok}"
        if errors:
            msg += f"\nОшибок: {len(errors)}"
            for p, e in errors[:5]:
                msg += f"\n  {p}: {e}"
        QMessageBox.information(self, "Готово", msg)

    def _save_sess(self):
        if not self.groups:
            return
        p, _ = QFileDialog.getSaveFileName(
            self, "Сессия", "session.dupsession.json", "*.json"
        )
        if p:
            r = {
                w.hash_key: [w.get_original()]
                + [x for x in w.paths if x != w.get_original()]
                for w in self.groups
            }
            save_session(
                build_session_from_groups(
                    r, self.path_edit.text(), self.filter_panel.as_dict()
                ),
                Path(p),
            )

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
                for g in self.groups:
                    for path in g.paths:
                        w.writerow(
                            [
                                g.hash_key[:8],
                                str(path),
                                path.stat().st_size,
                                datetime.fromtimestamp(
                                    path.stat().st_ctime
                                ).strftime("%Y-%m-%d"),
                            ]
                        )

    def _get_sess(self):
        r = {
            w.hash_key: [w.get_original()]
            + [x for x in w.paths if x != w.get_original()]
            for w in self.groups
        }
        return build_session_from_groups(
            r, self.path_edit.text(), self.filter_panel.as_dict()
        )

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
                for g in self.groups:
                    for t in g.get_selection()[1]:
                        f.write(f'del "{t}"\n')
