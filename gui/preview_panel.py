"""Панель предпросмотра выбранного файла.

Поддерживает:
- стандартные изображения (через Qt / Pillow);
- HEIC/HEIF/AVIF (pillow-heif);
- PDF (pypdfium2) — рендер первой страницы;
- RAW (rawpy) — опционально;
- видео (opencv) — первый кадр;
- аудио (mutagen) — метаданные;
- текст — первые 200 строк.
"""

import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap, QImage
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QFrame,
)

from gui.widgets import human_size

log = logging.getLogger(__name__)

# ---------- опциональные зависимости ----------

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    Image = None
    HAS_PIL = False

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
    HAS_HEIF = True
except ImportError:
    HAS_HEIF = False

try:
    import pypdfium2 as pdfium

    HAS_PDF = True
except ImportError:
    HAS_PDF = False

try:
    import rawpy

    HAS_RAWPY = True
except ImportError:
    HAS_RAWPY = False

try:
    import cv2

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import mutagen

    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

# ---------- расширения ----------

BASE_IMAGE_EXTS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".webp",
    ".tiff",
    ".tif",
    ".ico",
    ".svg",
}
HEIC_EXTS = {".heic", ".heif", ".avif"}
RAW_EXTS = {
    ".cr2",
    ".cr3",
    ".nef",
    ".arw",
    ".dng",
    ".raf",
    ".orf",
    ".rw2",
    ".pef",
    ".srw",
}
VIDEO_EXTS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
    ".m4v",
    ".mpg",
    ".mpeg",
}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".opus"}
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

TEXT_PREVIEW_LIMIT = 200
IMAGE_MAX_H = 600


def pil_to_pixmap(img) -> QPixmap:
    """PIL.Image → QPixmap."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    data = img.tobytes("raw", "RGBA")
    qim = QImage(data, img.width, img.height, QImage.Format_RGBA8888).copy()
    return QPixmap.fromImage(qim)


class PreviewPanel(QWidget):
    """Справа от списка групп: показывает содержимое выбранного файла."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(260)
        self._current_path: Path | None = None
        self._current_pixmap: QPixmap | None = None  # для масштабирования
        self._current_pil = None
        self._build_ui()
        self.clear()

    # ---------- UI ----------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        title = QLabel("Предпросмотр")
        title.setStyleSheet("font-weight: 600; font-size: 14px;")
        root.addWidget(title)

        self.name_label = QLabel("Файл не выбран")
        self.name_label.setWordWrap(True)
        self.name_label.setStyleSheet("font-weight: 600;")
        root.addWidget(self.name_label)

        self.meta_label = QLabel("")
        self.meta_label.setWordWrap(True)
        self.meta_label.setObjectName("statusLabel")
        self.meta_label.setTextFormat(Qt.RichText)
        root.addWidget(self.meta_label)

        self.open_btn = QPushButton("Открыть в системе")
        self.open_btn.setEnabled(False)
        self.open_btn.setCursor(Qt.PointingHandCursor)
        self.open_btn.clicked.connect(self._open_in_system)
        root.addWidget(self.open_btn)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        root.addWidget(line)

        self._content = QWidget()
        cl = QVBoxLayout(self._content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(4)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self._image_label.setMinimumHeight(200)
        self._image_label.hide()

        self._text_view = QPlainTextEdit()
        self._text_view.setReadOnly(True)
        self._text_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._text_view.hide()

        self._hint_label = QLabel()
        self._hint_label.setWordWrap(True)
        self._hint_label.setAlignment(Qt.AlignCenter)
        self._hint_label.setStyleSheet("color: #64748b;")

        cl.addWidget(self._image_label, 1)
        cl.addWidget(self._text_view, 1)
        cl.addWidget(self._hint_label, 1)
        root.addWidget(self._content, 1)

    # ---------- публичное API ----------

    def clear(self):
        self._current_path = None
        self._current_pixmap = None
        self._current_pil = None
        self.name_label.setText("Файл не выбран")
        self.meta_label.setText("")
        self.open_btn.setEnabled(False)
        self._image_label.clear()
        self._image_label.hide()
        self._text_view.clear()
        self._text_view.hide()
        self._hint_label.setText(
            "Кликните по пути файла слева, чтобы увидеть предпросмотр.\n"
            "Двойной клик — открыть в системном приложении."
        )
        self._hint_label.show()

    def show_file(self, path: Path):
        self._current_path = path
        self._current_pixmap = None
        self._current_pil = None
        self._image_label.clear()
        self._image_label.hide()
        self._text_view.clear()
        self._text_view.hide()
        self._hint_label.hide()

        try:
            st = path.stat()
        except OSError as e:
            log.warning("Не могу прочитать %s: %s", path, e)
            self.name_label.setText(path.name)
            self.meta_label.setText(
                f"<span style='color:#ef4444;'>Файл недоступен: {e}</span>"
            )
            self.open_btn.setEnabled(False)
            return

        self.name_label.setText(path.name)
        mtime = datetime.fromtimestamp(st.st_mtime).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        self.meta_label.setText(
            f"<b>Размер:</b> {human_size(st.st_size)}<br>"
            f"<b>Изменён:</b> {mtime}<br>"
            f"<b>Путь:</b><br><span style='color:#64748b;'>{path}</span>"
        )
        self.open_btn.setEnabled(True)

        ext = path.suffix.lower()

        if ext in HEIC_EXTS:
            self._show_image(path, kind="heic")
        elif ext in RAW_EXTS:
            self._show_raw(path)
        elif ext in BASE_IMAGE_EXTS:
            self._show_image(path, kind="base")
        elif ext == ".pdf":
            self._show_pdf(path)
        elif ext in VIDEO_EXTS:
            self._show_video(path)
        elif ext in AUDIO_EXTS:
            self._show_audio(path)
        elif ext in TEXT_EXTS:
            self._show_text(path)
        else:
            self._hint_label.setText(
                f"Предпросмотр для расширения "
                f"'{ext or 'без расширения'}' недоступен.\n"
                "Двойной клик — открыть в системе."
            )
            self._hint_label.show()

    # ---------- изображения ----------

    def _show_image(self, path: Path, kind: str = "base"):
        if kind == "heic" and not HAS_HEIF:
            self._hint_label.setText(
                "Для предпросмотра HEIC/AVIF установите:\n"
                "pip install pillow-heif"
            )
            self._hint_label.show()
            return

        # SVG и ICO лучше отдать Qt (он умеет рендерить вектор)
        if path.suffix.lower() in {".svg", ".ico"}:
            pix = QPixmap(str(path))
            if not pix.isNull():
                self._set_pixmap(pix)
                return

        # Всё остальное — через Pillow (универсально, HEIC-совместимо)
        if HAS_PIL:
            try:
                img = Image.open(path)
                img.load()
                self._set_pil(img)
                return
            except Exception as e:
                log.warning("PIL не смог открыть %s: %s", path, e)

        # Fallback — родной QPixmap
        pix = QPixmap(str(path))
        if pix.isNull():
            self._hint_label.setText("Не удалось загрузить изображение.")
            self._hint_label.show()
            return
        self._set_pixmap(pix)

    def _show_raw(self, path: Path):
        if not HAS_RAWPY:
            self._hint_label.setText(
                "Для предпросмотра RAW-файлов установите:\n"
                "pip install rawpy"
            )
            self._hint_label.show()
            return
        try:
            with rawpy.imread(str(path)) as raw:
                rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=True)
            img = Image.fromarray(rgb)
            self._set_pil(img)
        except Exception as e:
            log.warning("RAW не открыт %s: %s", path, e)
            self._hint_label.setText(f"Не удалось декодировать RAW: {e}")
            self._hint_label.show()

    # ---------- PDF ----------

    def _show_pdf(self, path: Path):
        if not HAS_PDF:
            self._hint_label.setText(
                "Для предпросмотра PDF установите:\n" "pip install pypdfium2"
            )
            self._hint_label.show()
            return
        try:
            pdf = pdfium.PdfDocument(str(path))
            if len(pdf) == 0:
                raise ValueError("документ пуст")
            page = pdf[0]
            # scale=1.0 — рендерим в натуральном размере, потом масштабируем
            pil_image = page.render(scale=1.5).to_pil()
            pdf.close()
            self._set_pil(pil_image)
        except Exception as e:
            log.exception("PDF не открыт %s", path)
            self._hint_label.setText(f"Не удалось открыть PDF: {e}")
            self._hint_label.show()

    # ---------- видео ----------

    def _show_video(self, path: Path):
        if not HAS_CV2:
            self._hint_label.setText(
                "Для предпросмотра видео установите:\n"
                "pip install opencv-python-headless"
            )
            self._hint_label.show()
            return
        try:
            cap = cv2.VideoCapture(str(path))
            ret, frame = cap.read()
            fps = cap.get(cv2.CAP_PROP_FPS)
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.release()
            if not ret:
                raise ValueError("не удалось прочитать первый кадр")

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            qim = QImage(
                frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888
            ).copy()
            pix = QPixmap.fromImage(qim)
            self._set_pixmap(pix)

            info = []
            if fps > 0 and frames > 0:
                dur = frames / fps
                info.append(f"{int(dur // 60)}:{int(dur % 60):02d}")
            if w and h:
                info.append(f"{w}×{h}")
            if info:
                self.meta_label.setText(
                    self.meta_label.text()
                    + f"<br><b>Видео:</b> "
                    + ", ".join(info)
                )
        except Exception as e:
            log.exception("Видео не открыто %s", path)
            self._hint_label.setText(f"Не удалось открыть видео: {e}")
            self._hint_label.show()

    # ---------- аудио ----------

    def _show_audio(self, path: Path):
        info_html = ""
        if HAS_MUTAGEN:
            try:
                mf = mutagen.File(str(path), easy=True)
                if mf is not None:
                    tags = []
                    for key in ("title", "artist", "album", "date"):
                        if key in mf and mf[key]:
                            tags.append(
                                f"<b>{key.capitalize()}:</b> "
                                f"{', '.join(str(x) for x in mf[key])}"
                            )
                    if mf.info and getattr(mf.info, "length", None):
                        sec = mf.info.length
                        tags.append(
                            f"<b>Длительность:</b> "
                            f"{int(sec // 60)}:{int(sec % 60):02d}"
                        )
                    if tags:
                        info_html = "<br>".join(tags)
            except Exception as e:
                log.debug("mutagen не прочитал %s: %s", path, e)

        self._hint_label.setText(
            "🎵 Аудиофайл"
            + (f"<br><br>{info_html}" if info_html else "")
            + "<br><br>Двойной клик — открыть в плеере."
        )
        self._hint_label.setTextFormat(Qt.RichText)
        self._hint_label.show()

    # ---------- текст ----------

    def _show_text(self, path: Path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= TEXT_PREVIEW_LIMIT:
                        lines.append(
                            f"\n… показаны первые {TEXT_PREVIEW_LIMIT} строк"
                        )
                        break
                    lines.append(line.rstrip("\n"))
            self._text_view.setPlainText("\n".join(lines))
            self._text_view.show()
        except OSError as e:
            log.warning("Не могу прочитать %s: %s", path, e)
            self._hint_label.setText(f"Ошибка чтения: {e}")
            self._hint_label.show()

    # ---------- отображение / масштабирование ----------

    def _set_pixmap(self, pix: QPixmap):
        self._current_pixmap = pix
        self._current_pil = None
        self._update_image_display()

    def _set_pil(self, img):
        self._current_pil = img
        self._current_pixmap = None
        self._update_image_display()

    def _update_image_display(self):
        max_w = max(200, self._content.width() - 8)

        if self._current_pil is not None:
            img = self._current_pil.copy()
            img.thumbnail((max_w, IMAGE_MAX_H), Image.Resampling.LANCZOS)
            pix = pil_to_pixmap(img)
        elif self._current_pixmap is not None:
            pix = self._current_pixmap.scaled(
                max_w,
                IMAGE_MAX_H,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        else:
            return

        self._image_label.setPixmap(pix)
        self._image_label.show()
        self._text_view.hide()
        self._hint_label.hide()

    def _open_in_system(self):
        if self._current_path is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._current_path)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Перемасштабируем уже загруженное изображение без повторного чтения
        if self._current_pil is not None or self._current_pixmap is not None:
            self._update_image_display()
