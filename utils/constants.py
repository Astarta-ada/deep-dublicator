"""Глобальные константы приложения."""

# ==========================================
# Группы расширений файлов
# ==========================================

IMAGE_EXTS = {
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

DOCUMENT_EXTS = {
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
}
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"}
CODE_EXTS = {
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
}

# ==========================================
# Категории для группировки в интерфейсе
# ==========================================

CATEGORIES = {
    "🖼 Изображения": IMAGE_EXTS | HEIC_EXTS | RAW_EXTS,
    "🎬 Видео": VIDEO_EXTS,
    "🎵 Аудио": AUDIO_EXTS,
    "📄 Документы": DOCUMENT_EXTS,
    "🗜 Архивы": ARCHIVE_EXTS,
    "💻 Код и скрипты": CODE_EXTS,
}


def get_category(ext: str) -> str:
    """Возвращает категорию файла по его расширению."""
    ext = ext.lower()
    for cat, exts in CATEGORIES.items():
        if ext in exts:
            return cat
    return "📦 Другие файлы"
