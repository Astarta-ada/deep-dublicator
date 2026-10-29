"""Глобальные константы и пути приложения."""

from pathlib import Path

# ==========================================
# Метаданные приложения (используется в QSettings и UI)
# ==========================================

APP_NAME = "Duplicate Finder"
APP_VERSION = "0.6.0"
ORG_NAME = "Aleksander Diuzhev"

# Ключи для QSettings
SETTINGS_THEME_KEY = "ui/theme"

# ==========================================
# Пути проекта и системные директории
# ==========================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "app.log"
APP_DATA_DIR = PROJECT_ROOT / "data"
HASH_CACHE_DB = APP_DATA_DIR / "hashes.db"

# Автосохранение последней сессии
AUTOSAVE_FILE = APP_DATA_DIR / "autosave.dupsession.json"

# Размер быстрого хеша (читаем первые 64 КБ)
QUICK_HASH_BYTES = 65536

# Размер чанка при полном чтении файла
CHUNK_SIZE = 65536

# Количество потоков для параллельного хеширования
DEFAULT_HASH_WORKERS = 4

# Специальный синтетический ключ для группы пустых файлов
EMPTY_FILE_HASH = "EMPTY"

# Папки, которые по умолчанию игнорируются при рекурсивном сканировании
DEFAULT_EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    ".idea",
    ".vscode",
}

# ==========================================
# Формат сессий
# ==========================================
SESSION_EXT = ".dupsession.json"
SESSION_VERSION = 1
