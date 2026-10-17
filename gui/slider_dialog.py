from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtWidgets import QDialog, QVBoxLayout, QSlider, QWidget


class ImageSlider(QWidget):
    def __init__(self, pix1, pix2):
        super().__init__()
        self.pix1 = pix1.scaledToWidth(800, Qt.SmoothTransformation)
        self.pix2 = pix2.scaledToWidth(800, Qt.SmoothTransformation)
        self.setFixedSize(self.pix1.size())
        self.pos = 50  # Процент

    def set_pos(self, val):
        self.pos = val
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        w = self.width()
        split_x = int(w * (self.pos / 100))

        # Рисуем первую картинку целиком
        p.drawPixmap(0, 0, self.pix1)
        # Рисуем вторую поверх, обрезая по ползунку
        p.setClipRect(split_x, 0, w - split_x, self.height())
        p.drawPixmap(0, 0, self.pix2)
        # Линия
        p.setPen(Qt.red)
        p.drawLine(split_x, 0, split_x, self.height())


class SliderDialog(QDialog):
    def __init__(self, img1, img2, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Сравнение фото (Слайдер)")
        layout = QVBoxLayout(self)

        pix1 = QPixmap(img1)
        pix2 = QPixmap(img2)

        self.slider_widget = ImageSlider(pix1, pix2)
        layout.addWidget(self.slider_widget)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(50)
        slider.valueChanged.connect(self.slider_widget.set_pos)
        layout.addWidget(slider)
