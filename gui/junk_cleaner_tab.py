import os
import shutil
import logging
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QLineEdit,
    QFileDialog,
)
from gui.widgets import human_size
from core.workers import JunkScanner

log = logging.getLogger(__name__)


class JunkCleanerTab(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.found_junk = []
        self.setAcceptDrops(True)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        # --- Верхняя панель ---
        top = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(
            "Папка для поиска мусора (например, C:\\Projects)..."
        )
        top.addWidget(QLabel("Папка:"))
        top.addWidget(self.path_edit, 1)

        self.btn_browse = QPushButton("Обзор...")
        self.btn_browse.clicked.connect(self._browse)
        top.addWidget(self.btn_browse)

        self.btn_scan = QPushButton("🔍 Анализ мусора")
        self.btn_scan.setProperty("class", "primary")
        self.btn_scan.clicked.connect(self._scan)
        top.addWidget(self.btn_scan)
        lay.addLayout(top)

        # --- Список найденного мусора ---
        self.list_widget = QListWidget()
        lay.addWidget(self.list_widget)

        self.status = QLabel("Готово к работе")
        self.status.setObjectName("statusLabel")
        lay.addWidget(self.status)

        # --- Кнопка очистки ---
        self.btn_clean = QPushButton("🧹 Очистить выбранное")
        self.btn_clean.setProperty("class", "danger")
        self.btn_clean.setMinimumHeight(36)
        self.btn_clean.clicked.connect(self._clean)
        lay.addWidget(self.btn_clean)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(
            self, "Выберите папку для анализа мусора"
        )
        if d:
            self.path_edit.setText(d)

    def _scan(self):
        p = self.path_edit.text().strip()
        if not os.path.isdir(p):
            return QMessageBox.warning(
                self, "Ошибка", "Укажите существующую папку"
            )

        self.list_widget.clear()
        self.status.setText("Анализ...")
        self.btn_scan.setEnabled(False)

        # Запускаем спиннер в трее
        main_win = self.window()
        if hasattr(main_win, "start_tray_spinner"):
            main_win.start_tray_spinner()

        self.worker = JunkScanner(p)
        self.worker.finished_ok.connect(self._done)
        self.worker.start()

    def _done(self, res):
        self.btn_scan.setEnabled(True)

        # Останавливаем спиннер
        main_win = self.window()
        if hasattr(main_win, "stop_tray_spinner"):
            main_win.stop_tray_spinner()

        self.status.setText(f"Найдено категорий мусора: {len(res)}")
        self.found_junk = res
        for name, path, size in res:
            item = QListWidgetItem(f"{name} — {human_size(size)}")
            item.setData(Qt.UserRole, (name, path))
            item.setCheckState(Qt.Checked)  # По умолчанию всё отмечено
            self.list_widget.addItem(item)

    def _clean(self):
        if self.list_widget.count() == 0:
            return

        if (
            QMessageBox.question(
                self,
                "Очистка",
                "Удалить выбранный мусор? Это действие необратимо.",
            )
            != QMessageBox.Yes
        ):
            return

        cleaned_size = 0
        errors = []

        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                name, path = item.data(Qt.UserRole)
                try:
                    # Считаем размер перед удалением
                    if name.startswith("Кэш Python") or name.startswith(
                        "Node.js"
                    ):
                        for p in path.split("\n"):
                            for root, _, files in os.walk(p):
                                for f in files:
                                    try:
                                        cleaned_size += os.path.getsize(
                                            os.path.join(root, f)
                                        )
                                    except:
                                        pass
                    elif "Temp" in name or "Cache" in name:
                        for root, _, files in os.walk(path):
                            for f in files:
                                try:
                                    cleaned_size += os.path.getsize(
                                        os.path.join(root, f)
                                    )
                                except:
                                    pass

                    # Удаление
                    if "Temp" in name:
                        for f in os.listdir(path):
                            fp = os.path.join(path, f)
                            try:
                                if os.path.isfile(fp):
                                    os.remove(fp)
                                else:
                                    shutil.rmtree(fp)
                            except:
                                pass

                    elif "Cache" in name:
                        if os.path.exists(path):
                            shutil.rmtree(path, ignore_errors=True)

                    else:
                        for p in path.split("\n"):
                            shutil.rmtree(p, ignore_errors=True)

                except Exception as e:
                    log.error(f"Ошибка очистки {name}: {e}")
                    errors.append(str(e))

        self.list_widget.clear()

        msg = f"Выбранный мусор успешно удален.\nОсвобождено места: {human_size(cleaned_size)}"
        if errors:
            msg += f"\n\nОшибки при удалении некоторых файлов:\n" + "\n".join(
                errors[:5]
            )

        QMessageBox.information(self, "Готово", msg)
        self.status.setText("Готово к работе")

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
                    self._scan()  # Автоматически запускаем анализ
                    e.acceptProposedAction()
                    return
        e.ignore()
