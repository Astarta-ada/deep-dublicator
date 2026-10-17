import logging
import psutil
import shutil
import os
from pathlib import Path
import squarify
from PySide6.QtCore import Qt, QThread, Signal, QDir, QUrl
from PySide6.QtGui import (
    QPainter,
    QColor,
    QFont,
    QDesktopServices,
    QKeySequence,
    QShortcut,
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

log = logging.getLogger(__name__)


class PercentDelegate(QStyledItemDelegate):
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


class FolderScannerWorker(QThread):
    finished_ok = Signal(list)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        results = []
        try:
            with os.scandir(self.path) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            s, c = self._scan(e.path)
                            results.append(
                                {
                                    "name": e.name,
                                    "path": e.path,
                                    "size": s,
                                    "files": c,
                                    "is_dir": True,
                                    "error": None,
                                }
                            )
                        elif e.is_file(follow_symlinks=False):
                            st = e.stat()
                            results.append(
                                {
                                    "name": e.name,
                                    "path": e.path,
                                    "size": st.st_size,
                                    "files": 1,
                                    "is_dir": False,
                                    "error": None,
                                }
                            )
                    except PermissionError:
                        results.append(
                            {
                                "name": e.name,
                                "path": e.path,
                                "size": 0,
                                "files": 0,
                                "is_dir": True,
                                "error": "Доступ закрыт",
                            }
                        )
        except Exception:
            pass
        results.sort(key=lambda x: x["size"], reverse=True)
        self.finished_ok.emit(results)

    def _scan(self, path):
        s, f = 0, 0
        try:
            with os.scandir(path) as it:
                for e in it:
                    try:
                        if e.is_file(follow_symlinks=False):
                            s += e.stat().st_size
                            f += 1
                        elif e.is_dir(follow_symlinks=False):
                            a, b = self._scan(e.path)
                            s += a
                            f += b
                    except:
                        pass
        except:
            pass
        return s, f


class TreemapWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.data = {}

    def set_data(self, d):
        self.data = d
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        if not self.data:
            return
        vals, names = list(self.data.values()), list(self.data.keys())
        rects = squarify.normalize_sizes(vals, self.width(), self.height())
        sq = squarify.squarify(rects, 0, 0, self.width(), self.height())
        for i, r in enumerate(sq):
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


class HeatmapWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(QLabel("<b>Распределение по расширениям:</b>"))

    def update_data(self, data):
        for i in reversed(range(1, self.layout.count())):
            self.layout.itemAt(i).widget().deleteLater()
        exts = {}
        for e in data:
            exts[Path(e["name"]).suffix.lower() or "no_ext"] = (
                exts.get(Path(e["name"]).suffix.lower() or "no_ext", 0)
                + e["size"]
            )
        total = sum(exts.values()) or 1
        for ext, size in sorted(
            exts.items(), key=lambda x: x[1], reverse=True
        )[:10]:
            bar = QProgressBar()
            bar.setValue(int((size / total) * 100))
            bar.setFormat(f"{ext} ({human_size(size)}) - %p%")
            self.layout.addWidget(bar)


class DiskAnalysisTab(QWidget):
    find_duplicates_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.workers = []
        self.history = []
        self.hist_idx = -1
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        # Верх
        top = QHBoxLayout()
        self.btn_back = QPushButton("←")
        self.btn_back.clicked.connect(self._go_back)
        self.btn_fwd = QPushButton("→")
        self.btn_fwd.clicked.connect(self._go_fwd)
        self.lbl_path = QLabel("/")
        self.lbl_path.setStyleSheet("font-weight: bold;")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск...")
        self.search.textChanged.connect(self._filter)

        top.addWidget(QLabel("Диск:"))
        self.combo = QComboBox()
        self.combo.currentIndexChanged.connect(self._on_drive)
        top.addWidget(self.combo)
        top.addWidget(QLabel("Путь:"))
        self.path_edit = QLineEdit()
        top.addWidget(self.path_edit, 1)
        top.addWidget(QPushButton("Обзор", clicked=self._browse))
        top.addWidget(QPushButton("Анализ", clicked=self._start))
        lay.addLayout(top)

        nav = QHBoxLayout()
        nav.addWidget(self.btn_back)
        nav.addWidget(self.btn_fwd)
        nav.addWidget(self.lbl_path, 1)
        nav.addWidget(self.search)
        lay.addLayout(nav)

        # Контент
        self.split = QSplitter()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Имя", "Размер", "Процент", "Файлов"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
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

        self.right_tabs = QTabWidget()
        self.treemap = TreemapWidget()
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
        self.combo.addItem("Выберите...", "")
        for part in psutil.disk_partitions(all=False):
            if not part.mountpoint:
                continue
            try:
                u = psutil.disk_usage(part.mountpoint)
                self.combo.addItem(
                    f"💽 {part.device} ({u.free//(1024**3)}GB free)",
                    part.mountpoint,
                )
            except:
                pass

    def _on_drive(self, i):
        p = self.combo.itemData(i)
        if p:
            self.path_edit.setText(p)
            self._start()

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self)
        if d:
            self.path_edit.setText(d)
            self._start()

    def _start(self):
        p = self.path_edit.text().strip()
        if not os.path.isdir(p):
            return
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
        w.finished.connect(
            lambda: self.workers.remove(w) if w in self.workers else None
        )
        self.workers.append(w)
        w.start()

    def _fill_root(self, p, data):
        self._add_items(self.tree, data, sum(x["size"] for x in data))
        self.treemap.set_data({x["name"]: x["size"] for x in data[:20]})
        self.heatmap.update_data(data)
        self.top_files.clear()
        for x in data:
            if not x["is_dir"]:
                self.top_files.addItem(
                    f"{human_size(x['size'])} — {x['name']}"
                )

    def _expand(self, item):
        if item.childCount() == 1 and item.child(0).text(0) == "...":
            item.takeChildren()
            self._run_worker(item.data(0, Qt.UserRole), self._fill_child, item)

    def _fill_child(self, item, data):
        self._add_items(item, data, item.data(1, Qt.UserRole) or 1)

    def _add_items(self, parent, data, total):
        for e in data:
            it = QTreeWidgetItem(parent)
            it.setText(0, e["name"])
            it.setText(1, human_size(e["size"]))
            it.setText(3, str(e["files"]))
            it.setData(1, Qt.UserRole, e["size"])
            it.setData(0, Qt.UserRole, e["path"])
            it.setData(
                2, Qt.UserRole, (e["size"] / total * 100) if total else 0
            )
            if e["error"]:
                it.setText(2, e["error"])
                it.setForeground(2, QColor("red"))
            elif e["is_dir"]:
                QTreeWidgetItem(it).setText(0, "...")

    def _filter(self, text):
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            it.setHidden(text.lower() not in it.text(0).lower())

    def _menu(self, pos):
        it = self.tree.itemAt(pos)
        if not it:
            return
        p = it.data(0, Qt.UserRole)
        m = QMenu(self)
        m.addAction(
            "Открыть", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(p))
        )
        m.addAction(
            "Искать дубликаты", lambda: self.find_duplicates_requested.emit(p)
        )
        m.addSeparator()
        m.addAction("В корзину", lambda: self._del(it, True))
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
