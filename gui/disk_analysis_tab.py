import logging
import psutil
import shutil
import os
import time
from pathlib import Path
import squarify
from PySide6.QtCore import Qt, Signal, QDir, QUrl, QRect
from PySide6.QtGui import (
    QPainter,
    QColor,
    QFont,
    QDesktopServices,
    QKeySequence,
    QShortcut,
    QBrush,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QFileDialog,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QMessageBox,
    QComboBox,
    QStyle,
    QStyledItemDelegate,
    QApplication,
    QHeaderView,
    QStyleOptionProgressBar,
    QMenu,
    QTabWidget,
    QListWidget,
    QProgressBar,
)
from gui.widgets import human_size
from core.file_ops import delete_file
from core.workers import FolderScannerWorker

log = logging.getLogger(__name__)


class TreeItem(QTreeWidgetItem):
    """# ==========================================
    # 1. Кастомный элемент для правильной сортировки
    # =========================================="""

    def __lt__(self, other):
        col = self.treeWidget().sortColumn()
        if col == 1:  # Размер
            return self.data(1, Qt.UserRole) < other.data(1, Qt.UserRole)
        elif col == 2:  # Процент
            return self.data(2, Qt.UserRole) < other.data(2, Qt.UserRole)
        elif col == 3:  # Количество файлов
            return int(self.text(3)) < int(other.text(3))
        # По умолчанию сортируем как текст (Имя)
        return self.text(col) < other.text(col)


class PercentDelegate(QStyledItemDelegate):
    """# ==========================================
    # 2. Делегат для красивой отрисовки процентов
    # =========================================="""

    def paint(self, painter, option, index):
        percent = index.data(Qt.UserRole)
        if percent is None:
            return super().paint(painter, option, index)

        painter.save()

        # Рисуем фон выделения, если строка выбрана
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        # Оставляем отступы, чтобы полоска не прилипала к краям
        rect = option.rect.adjusted(4, 8, -4, -8)

        # 1. Фон прогресс-бара (светло-серый)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#e2e8f0"))
        painter.drawRoundedRect(rect, 3, 3)

        # 2. Заполненная часть (зеленая)
        if percent > 0:
            fill_width = int(rect.width() * (percent / 100.0))
            if fill_width > 0:
                fill_rect = QRect(
                    rect.x(), rect.y(), fill_width, rect.height()
                )
                painter.setBrush(QColor("#10b981"))  # Изумрудно-зеленый
                painter.drawRoundedRect(fill_rect, 3, 3)

        # 3. Текст с процентами поверх полоски
        painter.setPen(
            QColor("#0f172a")
            if not (option.state & QStyle.State_Selected)
            else QColor("#ffffff")
        )
        font = painter.font()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(option.rect, Qt.AlignCenter, f"{percent:.1f}%")

        painter.restore()


class PercentDelegate(QStyledItemDelegate):
    """Делегат для красивой отрисовки процентов (синяя полоска)."""

    def paint(self, painter, option, index):
        percent = index.data(Qt.UserRole)
        if percent is None:
            return super().paint(painter, option, index)
        painter.save()
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        opt = QStyleOptionProgressBar()
        opt.rect = option.rect
        opt.maximum = 100
        opt.progress = int(percent)
        opt.text = f"{percent:.1f}%"
        opt.textVisible = True
        opt.textAlignment = Qt.AlignCenter
        QApplication.style().drawControl(QStyle.CE_ProgressBar, opt, painter)
        painter.restore()


class TreemapWidget(QWidget):
    """Интерактивная карта диска."""

    folder_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = {}
        self.rects = []

    def set_data(self, d):
        self.data = d
        self.update()

    def paintEvent(self, e):
        # Защита от нулевых размеров самого виджета (часто бывает при инициализации)
        if self.width() <= 10 or self.height() <= 10:
            return
        # Отсеиваем файлы с нулевым размером, иначе squarify падает с делением на ноль
        valid_data = {k: v for k, v in self.data.items() if v > 0}

        p = QPainter(self)
        try:

            if not self.data:
                p.drawText(self.rect(), Qt.AlignCenter, "Нет данных для карты")
                return

            vals, names = list(valid_data.values()), list(valid_data.keys())

            # Используем только валидные данные
            rects = squarify.normalize_sizes(vals, self.width(), self.height())
            sq = squarify.squarify(rects, 0, 0, self.width(), self.height())

            self.rects.clear()  # Очищаем старые

            for i, r in enumerate(sq):
                # Сохраняем область квадрата и имя папки для кликов
                self.rects.append(
                    (
                        QRect(
                            int(r["x"]),
                            int(r["y"]),
                            int(r["dx"]),
                            int(r["dy"]),
                        ),
                        names[i],
                    )
                )

                color = QColor.fromHsv(
                    int(360 * (i / max(1, len(names)))), 180, 220
                )
                p.fillRect(
                    int(r["x"]), int(r["y"]), int(r["dx"]), int(r["dy"]), color
                )
                p.setPen(Qt.black)
                if r["dx"] > 60 and r["dy"] > 30:
                    p.setFont(QFont("Arial", 8))
                    p.drawText(
                        int(r["x"]) + 4,
                        int(r["y"]) + 16,
                        f"{names[i]}\n{human_size(vals[i])}",
                    )

        except Exception as err:
            log.error("Ошибка отрисовки Treemap: %s", err)
        finally:
            # Всегда завершаем работу painter, чтобы Qt не ругался
            p.end()

    def mousePressEvent(self, event):
        # Ищем, по какому квадрату кликнули
        if event.button() == Qt.LeftButton:
            for rect, name in self.rects:
                if rect.contains(event.pos()):
                    # Если это папка (добавляем текущий путь), можно эмитить сигнал
                    self.folder_clicked.emit(name)
                    break


class HeatmapWidget(QWidget):
    """Распределение размера диска по расширениям файлов."""

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(QLabel("<b>Распределение по расширениям:</b>"))
        self.layout.addStretch()

    def update_data(self, data):
        # Очищаем старые виджеты (оставляем заголовок и stretch)
        while self.layout.count() > 2:
            item = self.layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        exts = {}

        # for i in reversed(range(1, self.layout.count())):
        #     self.layout.itemAt(i).widget().deleteLater()
        # exts = {}
        # for e in data:
        #     exts[Path(e["name"]).suffix.lower() or "no_ext"] = (
        #         exts.get(Path(e["name"]).suffix.lower() or "no_ext", 0)
        #         + e["size"]
        #     )
        for e in data:
            ext = Path(e["name"]).suffix.lower() or "no_ext"
            exts[ext] = exts.get(ext, 0) + e["size"]

        total = sum(exts.values()) or 1
        for ext, size in sorted(
            exts.items(), key=lambda x: x[1], reverse=True
        )[:10]:
            bar = QProgressBar()
            bar.setValue(int((size / total) * 100))
            bar.setFormat(f"{ext} ({human_size(size)}) - %p%")
            self.layout.addWidget(bar)
            self.layout.insertWidget(self.layout.count() - 1, bar)


class DiskAnalysisTab(QWidget):
    find_duplicates_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.workers = []
        self.history = []
        self.hist_idx = -1
        self.setAcceptDrops(True)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        # --- Верхняя панель (Диски и Путь) ---
        top = QHBoxLayout()

        top.addWidget(QLabel("Диск:"))
        self.combo = QComboBox()
        self.combo.currentIndexChanged.connect(self._on_drive)
        top.addWidget(self.combo)

        top.addWidget(QLabel("Путь:"))
        self.path_edit = QLineEdit()
        self.path_edit.returnPressed.connect(self._start)
        top.addWidget(self.path_edit, 1)

        self.btn_browse = QPushButton("Обзор")
        self.btn_browse.clicked.connect(self._browse)
        top.addWidget(self.btn_browse)

        self.btn_start = QPushButton("Анализировать")
        self.btn_start.setProperty("class", "primary")
        self.btn_start.clicked.connect(self._start)
        top.addWidget(self.btn_start)
        lay.addLayout(top)

        # --- ПРОГРЕСС-БАР (НОВОЕ) ---
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # Режим "бегущей строки" (indeterminate)
        self.progress.setTextVisible(True)
        self.progress.hide()  # Скрыт по умолчанию
        lay.addWidget(self.progress)

        # --- Навигация и Поиск ---
        nav = QHBoxLayout()

        self.btn_back = QPushButton()
        self.btn_back.setIcon(
            QApplication.style().standardIcon(QStyle.SP_ArrowBack)
        )
        self.btn_back.setFixedWidth(30)
        self.btn_back.clicked.connect(self._go_back)

        self.btn_fwd = QPushButton()
        self.btn_fwd.setIcon(
            QApplication.style().standardIcon(QStyle.SP_ArrowForward)
        )
        self.btn_fwd.setFixedWidth(30)
        self.btn_fwd.clicked.connect(self._go_fwd)

        self.lbl_path = QLabel("/")
        self.lbl_path.setStyleSheet("font-weight: bold; color: #2563eb;")

        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "🔍 Поиск по имени файла или папки в дереве..."
        )
        self.search.textChanged.connect(self._filter)

        nav.addWidget(self.btn_back)
        nav.addWidget(self.btn_fwd)
        nav.addWidget(self.lbl_path, 1)
        nav.addWidget(self.search)
        lay.addLayout(nav)

        # --- Основной контент ---
        self.split = QSplitter(Qt.Horizontal)

        # Дерево
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Имя", "Размер", "Процент", "Файлов"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )
        self.tree.header().setSectionResizeMode(
            2, QHeaderView.Fixed
        )  # Фиксируем ширину для полоски
        self.tree.header().setSectionResizeMode(
            3, QHeaderView.ResizeToContents
        )
        self.tree.setColumnWidth(2, 150)  # <--- Ширина колонки "Процент"

        self.tree.setItemDelegateForColumn(2, PercentDelegate(self.tree))
        self.tree.setSortingEnabled(True)
        self.tree.itemExpanded.connect(self._expand)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        self.tree.itemDoubleClicked.connect(
            lambda i, c: QDesktopServices.openUrl(
                QUrl.fromLocalFile(i.data(0, Qt.UserRole))
            )
        )

        # Горячие клавиши
        QShortcut(
            QKeySequence("Delete"),
            self.tree,
            activated=lambda: self._del(self.tree.currentItem(), True),
        )
        QShortcut(
            QKeySequence("Shift+Delete"),
            self.tree,
            activated=lambda: self._del(self.tree.currentItem(), False),
        )
        QShortcut(
            QKeySequence("Ctrl+C"),
            self.tree,
            activated=lambda: QApplication.clipboard().setText(
                self.tree.currentItem().data(0, Qt.UserRole)
            ),
        )

        self.split.addWidget(self.tree)

        # Правая панель с вкладками (Карта, Топ, Типы)
        self.right_tabs = QTabWidget()

        self.treemap = TreemapWidget()
        self.treemap.folder_clicked.connect(self._on_treemap_click)
        self.right_tabs.addTab(self.treemap, "Карта")

        self.top_files = QListWidget()
        self.right_tabs.addTab(self.top_files, "Топ файлов")

        self.heatmap = HeatmapWidget()
        self.right_tabs.addTab(self.heatmap, "Типы")

        self.split.addWidget(self.right_tabs)
        self.split.setSizes([600, 400])
        lay.addWidget(self.split, 1)

        self._populate_drives()

    def _populate_drives(self):
        self.combo.blockSignals(True)
        self.combo.addItem("Выберите диск...", "")
        for part in psutil.disk_partitions(all=False):
            if not part.mountpoint:
                continue
            try:
                u = psutil.disk_usage(part.mountpoint)
                free_gb = u.free / (1024**3)
                self.combo.addItem(
                    f"💽 {part.device} ({free_gb:.1f}GB free)",
                    part.mountpoint,
                )
            except:
                pass

        self.combo.blockSignals(False)

    def _on_drive(self, i):
        p = self.combo.itemData(i)
        if p:
            self.path_edit.setText(p)

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

        # Отключаем кнопку, чтобы избежать двойных кликов
        self.btn_start.setEnabled(False)
        self.btn_start.setText("Анализ...")

        # Показываем прогресс-бар
        self.progress.show()

        self.tree.clear()
        self.treemap.set_data({})
        self.top_files.clear()

        self.lbl_path.setText(p)
        self.history.append(p)
        self.hist_idx = len(self.history) - 1

        self._run_worker(p, self._fill_root, p)

    def _run_worker(self, p, cb, *args):
        w = FolderScannerWorker(p)
        w.finished_ok.connect(lambda d: cb(*args, d) if args else cb(d))

        w.progress.connect(
            self.progress.setFormat
        )  # НОВОЕ: Передаем имя текущей папки в прогресс-бар
        w.finished.connect(
            lambda: self.workers.remove(w) if w in self.workers else None
        )

        self.workers.append(w)
        w.start()

    def _fill_root(self, p, data):
        # Очищаем дерево перед заполнением на случай, если остались старые данные
        self.tree.clear()

        self._add_items(self.tree, data, sum(x["size"] for x in data))
        # Обновляем правую панель
        self.treemap.set_data({x["name"]: x["size"] for x in data[:20]})
        self.heatmap.update_data(data)

        self.top_files.clear()
        for x in data:
            if not x["is_dir"]:
                self.top_files.addItem(
                    f"{human_size(x['size']):>10} — {x['name']}"
                )

        # Включаем кнопку обратно
        self.btn_start.setEnabled(True)
        self.btn_start.setText("Анализировать")
        self.progress.hide()  # Скрываем прогресс-бар

        # Уведомление
        main_win = self.window()
        if hasattr(main_win, "notify"):
            main_win.notify(
                "Анализ диска", f"Анализ '{Path(p).name}' завершен."
            )

    def _expand(self, item):
        """Ленивая загрузка при раскрытии папки."""
        if item.childCount() == 1 and item.child(0).text(0) == "...":
            item.takeChildren()
            self._run_worker(item.data(0, Qt.UserRole), self._fill_child, item)

    def _fill_child(self, item, data):
        self._add_items(item, data, item.data(1, Qt.UserRole) or 1)

    def _add_items(self, parent, data, total):
        now = time.time()
        for e in data:
            # Используем кастомный TreeItem
            it = TreeItem(parent)
            it.setText(0, e["name"])
            it.setText(1, human_size(e["size"]))
            it.setText(3, str(e["files"]))

            it.setData(1, Qt.UserRole, e["size"])
            it.setData(0, Qt.UserRole, e["path"])

            percent = (e["size"] / total * 100) if total else 0
            it.setData(2, Qt.UserRole, percent)
            it.setText(
                2, f"{percent:.1f}%"
            )  # Запасной текст, если делегат отключится

            if e["error"]:
                it.setText(2, e["error"])
                it.setForeground(2, QColor("red"))
            elif e["is_dir"]:
                # Добавляем пустышку для ленивой загрузки
                QTreeWidgetItem(it).setText(0, "...")
            else:
                # Подсветка старых файлов (старше 1 года)
                mtime = e.get("mtime", now)
                if now - mtime > 365 * 24 * 3600:
                    it.setForeground(
                        0, QBrush(QColor("#9ca3af"))
                    )  # Серый текст
                    it.setToolTip(0, "Файл не изменялся более года")

    def _filter(self, text):
        """Поиск по дереву."""
        text = text.lower()

        def check_item(item):
            # Проверяем совпадение в текущем элементе
            match = text in item.text(0).lower()
            child_match = False

            # Рекурсивно проверяем всех детей
            for i in range(item.childCount()):
                if check_item(item.child(i)):
                    child_match = True

            # Показываем элемент, если он сам совпал или совпал кто-то из его детей
            is_visible = match or child_match
            item.setHidden(not is_visible)

            # Автоматически раскрываем папку, если внутри есть совпадения
            if child_match and text:
                item.setExpanded(True)

            return is_visible

        # Запускаем проверку для всех корневых элементов
        for i in range(self.tree.topLevelItemCount()):
            check_item(self.tree.topLevelItem(i))

    def _on_treemap_click(self, folder_name):
        """Открывает папку, по которой кликнули в Treemap."""
        current = Path(self.path_edit.text().strip())
        new_path = current / folder_name.strip("\\")
        if new_path.is_dir():
            self.path_edit.setText(str(new_path))
            self._start()

    def _menu(self, pos):
        it = self.tree.itemAt(pos)
        if not it:
            return
        p = it.data(0, Qt.UserRole)
        m = QMenu(self)
        m.addAction(
            "Открыть", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(p))
        )

        def _trigger_search(target_path):
            tp = Path(target_path)
            if tp.is_file():
                tp = tp.parent
            self.find_duplicates_requested.emit(str(tp))

        m.addAction("Искать дубликаты здесь", lambda: _trigger_search(p))
        m.addSeparator()

        m.addAction("Удалить в корзину", lambda: self._del(it, True))
        m.addAction("Удалить навсегда", lambda: self._del(it, False))
        m.exec(self.tree.viewport().mapToGlobal(pos))

    def _del(self, it, trash):
        if not it:
            return
        p = it.data(0, Qt.UserRole)
        if (
            QMessageBox.question(self, "Удаление", f"Удалить?\n{p}")
            != QMessageBox.Yes
        ):
            return
        try:
            if os.path.isdir(p):
                if trash:
                    from send2trash import send2trash

                    send2trash(p)
                else:
                    shutil.rmtree(p)
            else:
                delete_file(Path(p), trash)
            # Обновляем родителя
            parent = it.parent()
            if parent:
                parent.removeChild(it)
                self._run_worker(
                    parent.data(0, Qt.UserRole), self._refresh, parent
                )
            else:
                self._start()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def _refresh(self, item, data):
        """Обновляет размер папки после удаления файла."""
        item.takeChildren()
        self._add_items(item, data, sum(x["size"] for x in data))

    def _go_back(self):
        if self.hist_idx > 0:
            self.hist_idx -= 1
            self.path_edit.setText(self.history[self.hist_idx])
            self._start()

    def _go_fwd(self):
        if self.hist_idx < len(self.history) - 1:
            self.hist_idx += 1
            self.path_edit.setText(self.history[self.hist_idx])
            self._start()

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
