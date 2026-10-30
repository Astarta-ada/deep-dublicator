"""Тесты для панели предпросмотра (gui/preview_panel.py)."""

import sys
import importlib
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image
from PySide6.QtCore import QSize
from PySide6.QtGui import QPixmap, QImage, QDesktopServices, QResizeEvent
from PySide6.QtWidgets import QLabel

from gui.preview_panel import (
    PreviewPanel,
    pil_to_pixmap,
    HAS_PIL,
    HAS_HEIF,
    HAS_PDF,
    HAS_RAWPY,
    HAS_CV2,
    HAS_MUTAGEN,
)

# ==========================================
# 1. Тесты утилиты pil_to_pixmap
# ==========================================


def test_pil_to_pixmap():
    """Проверяет конвертацию PIL.Image в QPixmap."""
    img = Image.new("RGB", (10, 10), color="black")
    pix = pil_to_pixmap(img)

    assert isinstance(pix, QPixmap)
    assert not pix.isNull()
    assert pix.width() == 10
    assert pix.height() == 10


# ==========================================
# 2. Тесты интерфейса и базовые
# ==========================================


@pytest.fixture
def preview_panel(qtbot):
    panel = PreviewPanel()
    qtbot.addWidget(panel)
    return panel


def test_initial_state(preview_panel):
    assert preview_panel._current_path is None
    assert preview_panel._current_pixmap is None
    assert preview_panel._current_pil is None

    assert preview_panel.name_label.text() == "Файл не выбран"
    assert preview_panel.meta_label.text() == ""
    assert preview_panel.open_btn.isEnabled() is False
    assert preview_panel._image_label.isHidden() is True
    assert preview_panel._text_view.isHidden() is True
    assert preview_panel._hint_label.isHidden() is False


def test_clear(preview_panel):
    preview_panel.name_label.setText("Test")
    preview_panel._current_path = Path("test.txt")
    preview_panel.open_btn.setEnabled(True)

    preview_panel.clear()

    assert preview_panel.name_label.text() == "Файл не выбран"
    assert preview_panel._current_path is None
    assert preview_panel.open_btn.isEnabled() is False


def test_show_file_missing(preview_panel):
    preview_panel.show_file(Path("C:/ghost_file.txt"))

    assert "Файл недоступен" in preview_panel.meta_label.text()
    assert preview_panel.open_btn.isEnabled() is False


# ==========================================
# 3. Тесты отображения разных типов
# ==========================================


def test_show_file_text(preview_panel, tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("Line 1\nLine 2\n", encoding="utf-8")

    preview_panel.show_file(f)

    assert preview_panel.name_label.text() == "test.txt"
    assert preview_panel.open_btn.isEnabled() is True
    assert preview_panel._text_view.isHidden() is False
    assert preview_panel._text_view.toPlainText() == "Line 1\nLine 2"


def test_show_text_truncated(preview_panel, tmp_path):
    f = tmp_path / "long.txt"
    f.write_text("Line\n" * 300, encoding="utf-8")

    preview_panel.show_file(f)
    assert (
        "… показаны первые 200 строк" in preview_panel._text_view.toPlainText()
    )


def test_show_text_error(preview_panel, mocker):
    f = Path("ghost.txt")
    mocker.patch(
        "pathlib.Path.stat", return_value=MagicMock(st_size=10, st_mtime=0)
    )
    mocker.patch("builtins.open", side_effect=OSError("Read error"))

    preview_panel.show_file(f)
    assert "Ошибка чтения: Read error" in preview_panel._hint_label.text()


def test_show_file_unsupported(preview_panel, tmp_path):
    f = tmp_path / "test.xyz"
    f.write_text("data")

    preview_panel.show_file(f)
    assert (
        "Предпросмотр для расширения '.xyz' недоступен"
        in preview_panel._hint_label.text()
    )


# ==========================================
# 4. Тесты изображений (ИСПРАВЛЕНО)
# ==========================================


def test_show_image_success(preview_panel, tmp_path):
    f = tmp_path / "test.png"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(f)

    preview_panel.show_file(f)
    assert preview_panel._image_label.isHidden() is False
    assert preview_panel._current_pil is not None


def test_show_image_no_pil(preview_panel, mocker, tmp_path):
    """Покрывает fallback на QPixmap, если PIL недоступен."""
    mocker.patch("gui.preview_panel.HAS_PIL", False)

    # Создаем реальный файл, чтобы QPixmap мог его прочитать
    f = tmp_path / "test.png"
    img = Image.new("RGB", (10, 10), color="white")
    img.save(f)

    preview_panel._show_image(f, kind="base")
    assert preview_panel._current_pixmap is not None


def test_show_image_heic_no_lib(preview_panel, mocker):
    mocker.patch("gui.preview_panel.HAS_HEIF", False)
    preview_panel._show_image(Path("test.heic"), kind="heic")
    assert "Для предпросмотра HEIC" in preview_panel._hint_label.text()


def test_show_image_error(preview_panel, mocker):
    mocker.patch("gui.preview_panel.HAS_PIL", True)
    mocker.patch("PIL.Image.open", side_effect=Exception("PIL Error"))

    # Патчим QPixmap в модуле, чтобы isNull() вернул True
    mocker.patch("gui.preview_panel.QPixmap.isNull", return_value=True)

    preview_panel._show_image(Path("test.png"))
    assert (
        "Не удалось загрузить изображение" in preview_panel._hint_label.text()
    )


# ==========================================
# 5. Тесты RAW, PDF, Видео
# ==========================================


def test_show_raw_no_lib(preview_panel, mocker):
    mocker.patch("gui.preview_panel.HAS_RAWPY", False)
    preview_panel._show_raw(Path("test.cr2"))
    assert "Для предпросмотра RAW" in preview_panel._hint_label.text()


def test_show_raw_error(preview_panel, mocker):
    mocker.patch("gui.preview_panel.HAS_RAWPY", True)
    mocker.patch("rawpy.imread", side_effect=Exception("RAW Error"))
    preview_panel._show_raw(Path("test.cr2"))
    assert "Не удалось декодировать RAW" in preview_panel._hint_label.text()


def test_show_pdf_no_lib(preview_panel, mocker):
    mocker.patch("gui.preview_panel.HAS_PDF", False)
    preview_panel._show_pdf(Path("test.pdf"))
    assert "Для предпросмотра PDF" in preview_panel._hint_label.text()


def test_show_pdf_empty(preview_panel, mocker):
    mocker.patch("gui.preview_panel.HAS_PDF", True)
    mock_pdf = mocker.patch("pypdfium2.PdfDocument")
    mock_pdf.return_value.__len__.return_value = 0

    preview_panel._show_pdf(Path("test.pdf"))
    assert "документ пуст" in preview_panel._hint_label.text()


def test_show_video_no_lib(preview_panel, mocker):
    mocker.patch("gui.preview_panel.HAS_CV2", False)
    preview_panel._show_video(Path("test.mp4"))
    assert "Для предпросмотра видео" in preview_panel._hint_label.text()


def test_show_video_error(preview_panel, mocker):
    mocker.patch("gui.preview_panel.HAS_CV2", True)
    mocker.patch("cv2.VideoCapture").return_value.read.return_value = (
        False,
        None,
    )

    preview_panel._show_video(Path("test.mp4"))
    assert "Не удалось открыть видео" in preview_panel._hint_label.text()


def test_show_video_success(preview_panel, mocker):
    """ИСПРАВЛЕНО: Используем реальный QPixmap вместо MagicMock."""
    mocker.patch("gui.preview_panel.HAS_CV2", True)
    mock_cap = mocker.patch("cv2.VideoCapture").return_value
    mock_cap.read.return_value = (True, "frame")
    mock_cap.get.side_effect = [30.0, 90.0]  # fps, frames

    mocker.patch(
        "cv2.cvtColor",
        return_value=MagicMock(shape=(100, 200, 3), data=b"data"),
    )
    mocker.patch("PySide6.QtGui.QImage")
    # Возвращаем реальный QPixmap, чтобы setPixmap не упал
    mocker.patch(
        "PySide6.QtGui.QPixmap.fromImage", return_value=QPixmap(100, 200)
    )

    preview_panel._show_video(Path("test.mp4"))
    assert "<b>Видео:</b> 0:03, 200×100" in preview_panel.meta_label.text()


# ==========================================
# 6. Тесты аудио
# ==========================================


def test_show_audio_no_lib(preview_panel, mocker):
    mocker.patch("gui.preview_panel.HAS_MUTAGEN", False)
    preview_panel._show_audio(Path("test.mp3"))
    assert "🎵 Аудиофайл" in preview_panel._hint_label.text()
    assert "Двойной клик" in preview_panel._hint_label.text()


def test_show_audio_success(preview_panel, mocker):
    mocker.patch("gui.preview_panel.HAS_MUTAGEN", True)

    mock_mf = MagicMock()
    mock_mf.__contains__.side_effect = lambda k: k in ("title", "artist")
    mock_mf.__getitem__.side_effect = lambda k: (
        ["Test Title"] if k == "title" else ["Test Artist"]
    )
    mock_mf.info.length = 125  # 2:05

    mocker.patch("mutagen.File", return_value=mock_mf)

    preview_panel._show_audio(Path("test.mp3"))
    text = preview_panel._hint_label.text()
    assert "<b>Title:</b> Test Title" in text
    assert "<b>Artist:</b> Test Artist" in text
    assert "<b>Длительность:</b> 2:05" in text


# ==========================================
# 7. Тесты масштабирования и открытия (ИСПРАВЛЕНО)
# ==========================================


def test_open_in_system(preview_panel, mocker):
    mock_open = mocker.patch("gui.preview_panel.QDesktopServices.openUrl")

    preview_panel._open_in_system()
    mock_open.assert_not_called()

    preview_panel._current_path = Path("test.txt")
    preview_panel._open_in_system()
    mock_open.assert_called_once()


def test_resize_event(preview_panel, mocker):
    """ИСПРАВЛЕНО: Используем реальный QResizeEvent вместо MagicMock."""
    preview_panel._current_pixmap = QPixmap(10, 10)
    mock_update = mocker.patch(
        "gui.preview_panel.PreviewPanel._update_image_display"
    )

    # Создаем валидное событие изменения размера
    event = QResizeEvent(QSize(800, 600), QSize(400, 300))
    preview_panel.resizeEvent(event)

    assert mock_update.called


# ==========================================
# 8. Тесты покрытия импортов (ветки try/except)
# ==========================================


def test_missing_dependencies(mocker):
    """Покрывает ветки except ImportError при отсутствии библиотек."""
    # Имитируем, что библиотек нет
    mock_modules = {
        "PIL": None,
        "pillow_heif": None,
        "pypdfium2": None,
        "rawpy": None,
        "cv2": None,
        "mutagen": None,
    }
    mocker.patch.dict(sys.modules, mock_modules)

    import gui.preview_panel

    importlib.reload(gui.preview_panel)

    assert gui.preview_panel.HAS_PIL is False
    assert gui.preview_panel.HAS_HEIF is False
    assert gui.preview_panel.HAS_PDF is False
    assert gui.preview_panel.HAS_RAWPY is False
    assert gui.preview_panel.HAS_CV2 is False
    assert gui.preview_panel.HAS_MUTAGEN is False

    # Возвращаем все обратно для других тестов
    mocker.stopall()
    importlib.reload(gui.preview_panel)
