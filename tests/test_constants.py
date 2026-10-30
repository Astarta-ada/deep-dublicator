"""Тесты для констант и категорий (utils/constants.py)."""

import pytest

from utils.constants import (
    IMAGE_EXTS,
    HEIC_EXTS,
    RAW_EXTS,
    VIDEO_EXTS,
    AUDIO_EXTS,
    TEXT_EXTS,
    DOCUMENT_EXTS,
    ARCHIVE_EXTS,
    CODE_EXTS,
    CATEGORIES,
    get_category,
)

# ==========================================
# 1. Тесты групп расширений
# ==========================================


def test_image_exts():
    assert ".jpg" in IMAGE_EXTS
    assert ".png" in IMAGE_EXTS
    assert ".svg" in IMAGE_EXTS
    assert ".avif" not in IMAGE_EXTS  # Он в HEIC_EXTS


def test_heic_exts():
    assert ".heic" in HEIC_EXTS
    assert ".heif" in HEIC_EXTS
    assert ".avif" in HEIC_EXTS


def test_raw_exts():
    assert ".cr2" in RAW_EXTS
    assert ".nef" in RAW_EXTS
    assert ".dng" in RAW_EXTS


def test_video_exts():
    assert ".mp4" in VIDEO_EXTS
    assert ".mkv" in VIDEO_EXTS
    assert ".webm" in VIDEO_EXTS


def test_audio_exts():
    assert ".mp3" in AUDIO_EXTS
    assert ".flac" in AUDIO_EXTS
    assert ".wav" in AUDIO_EXTS


def test_text_exts():
    assert ".txt" in TEXT_EXTS
    assert ".py" in TEXT_EXTS
    assert ".json" in TEXT_EXTS
    assert ".md" in TEXT_EXTS


def test_document_exts():
    assert ".pdf" in DOCUMENT_EXTS
    assert ".docx" in DOCUMENT_EXTS


def test_archive_exts():
    assert ".zip" in ARCHIVE_EXTS
    assert ".rar" in ARCHIVE_EXTS
    assert ".7z" in ARCHIVE_EXTS


def test_code_exts():
    assert ".py" in CODE_EXTS
    assert ".cpp" in CODE_EXTS
    assert ".go" in CODE_EXTS


# ==========================================
# 2. Тесты словаря CATEGORIES
# ==========================================


def test_categories_keys():
    """Проверяет, что в словаре есть все 6 основных категорий."""
    expected_keys = {
        "🖼 Изображения",
        "🎬 Видео",
        "🎵 Аудио",
        "📄 Документы",
        "🗜 Архивы",
        "💻 Код и скрипты",
    }
    assert set(CATEGORIES.keys()) == expected_keys


def test_categories_combine_exts():
    """Проверяет, что в категорию 'Изображения' попали все три группы."""
    images = CATEGORIES["🖼 Изображения"]
    assert ".jpg" in images  # из IMAGE_EXTS
    assert ".heic" in images  # из HEIC_EXTS
    assert ".cr2" in images  # из RAW_EXTS


# ==========================================
# 3. Тесты функции get_category
# ==========================================


@pytest.mark.parametrize(
    "ext, expected",
    [
        (".jpg", "🖼 Изображения"),
        (".png", "🖼 Изображения"),
        (".heic", "🖼 Изображения"),
        (".cr2", "🖼 Изображения"),
        (".mp4", "🎬 Видео"),
        (".mkv", "🎬 Видео"),
        (".mp3", "🎵 Аудио"),
        (".flac", "🎵 Аудио"),
        (".pdf", "📄 Документы"),
        (".docx", "📄 Документы"),
        (".zip", "🗜 Архивы"),
        (".py", "💻 Код и скрипты"),
        (".html", "💻 Код и скрипты"),
    ],
)
def test_get_category_known(ext, expected):
    """Проверяет, что известные расширения попадают в свои категории."""
    assert get_category(ext) == expected


def test_get_category_unknown():
    """Проверяет fallback для неизвестного расширения."""
    assert get_category(".xyz") == "📦 Другие файлы"
    assert get_category("") == "📦 Другие файлы"
    assert get_category(".unknown_ext") == "📦 Другие файлы"


def test_get_category_case_insensitive():
    """Проверяет, что регистр не влияет на результат."""
    assert get_category(".JPG") == "🖼 Изображения"
    assert get_category(".Png") == "🖼 Изображения"
    assert get_category(".MP4") == "🎬 Видео"
    assert get_category(".Py") == "💻 Код и скрипты"
