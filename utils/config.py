"""Глобальные константы и пути приложения."""

import sys
from pathlib import Path
from PySide6.QtCore import QStandardPaths, QCoreApplication

# ==========================================
# Метаданные приложения (используется в QSettings и UI)
# ==========================================

APP_NAME = "Duplicate Finder"
APP_VERSION = "0.6.1"
ORG_NAME = "Aleksander Diuzhev"

# инициализируем метаданные до запроса путей QStandardPaths
QCoreApplication.setOrganizationName(ORG_NAME)
QCoreApplication.setApplicationName(APP_NAME)

# ==========================================
# Путь к исходникам / папке с программой
# ==========================================

# Если программа запущена как EXE (PyInstaller), sys.frozen = True
if getattr(sys, "frozen", False):
    # Для режима --onedir путь к EXE находится в sys.executable
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    # Для режима разработки (python main.py)
    PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_resource_path(relative_path: str):  # -> Path:
    """
    Возвращает правильный путь к ресурсу (иконке, переводу)
    и в режиме разработки, и в скомпилированном EXE.
    """
    if getattr(sys, "frozen", False):
        # В PyInstaller --onefile ресурсы распаковываются в sys._MEIPASS
        base_path = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
    else:
        base_path = PROJECT_ROOT
    return base_path / relative_path


# ==========================================
# Системные директории (AppData / .local/share)
# ==========================================

# AppDataLocation: Windows (AppData/Roaming), Linux (~/.local/share), Mac (Application Support)
APP_DATA_DIR = Path(
    QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
)
# AppLocalDataLocation: для логов и кэша (на Windows это папка Local, на Linux/Mac совпадает с AppData)
LOG_DIR = (
    Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))
    / "logs"
)
LOG_FILE = LOG_DIR / "app.log"

# Создаем папки при старте, чтобы SQLite и логгер не падали
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ==========================================
# Файлы данных (в AppData)
# ==========================================
# Файлы данных
HASH_CACHE_DB = APP_DATA_DIR / "hashes.db"
# Автосохранение последней сессии
AUTOSAVE_FILE = APP_DATA_DIR / "autosave.dupsession.json"

# ==========================================
# Параметры приложения
# ==========================================

# Ключ для сохранения выбранной темы в QSettings
SETTINGS_THEME_KEY = "ui/theme"

# ==========================================
# Параметры сканирования и хеширования
# ==========================================

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
    # Добавлены системные папки macOS
    ".DS_Store",
    ".Trashes",
    ".Spotlight-V100",
    ".fseventsd",
}

# ==========================================
# Формат сессий
# ==========================================
SESSION_EXT = ".dupsession.json"
SESSION_VERSION = 1
