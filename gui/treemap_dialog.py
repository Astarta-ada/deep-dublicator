from PySide6.QtGui import QPainter, QColor, QFont, Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget, QLabel
import squarify
import os
from pathlib import Path


class TreemapWidget(QWidget):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.data = []
        # Собираем топ-20 самых больших папок/файлов
        items = []
        try:
            for entry in os.scandir(path):
                size = (
                    entry.stat().st_size
                    if entry.is_file()
                    else self._get_dir_size(entry.path)
                )
                items.append((entry.name, size))
        except Exception:
            pass

        items.sort(key=lambda x: x[1], reverse=True)
        items = items[:20]
        self.total = sum(x[1] for x in items) or 1
        self.data = items

    def _get_dir_size(self, p):
        total = 0
        for root, _, files in os.walk(p):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except:
                    pass
        return total

    def paintEvent(self, event):
        p = QPainter(self)
        if not self.data:
            return

        # Используем squarify для расчета прямоугольников
        values = [x[1] for x in self.data]
        rects = squarify.normalize_sizes(values, self.width(), self.height())
        squarified = squarify.squarify(
            rects, 0, 0, self.width(), self.height()
        )

        for i, r in enumerate(squarified):
            name, size = self.data[i]
            color = QColor.fromHsv(int(360 * (i / len(self.data))), 200, 220)
            p.fillRect(
                int(r["x"]), int(r["y"]), int(r["dx"]), int(r["dy"]), color
            )

            if r["dx"] > 50 and r["dy"] > 20:
                p.setPen(Qt.black)
                p.setFont(QFont("Arial", 8))
                mb = size / (1024 * 1024)
                text = f"{name}\n{mb:.1f} MB"
                p.drawText(int(r["x"]) + 4, int(r["y"]) + 15, text)


class TreemapDialog(QDialog):
    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Карта диска: {path}")
        self.resize(1000, 700)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(f"Нажмите для обновления (топ-20 объектов)\n{path}")
        )
        layout.addWidget(TreemapWidget(path))
