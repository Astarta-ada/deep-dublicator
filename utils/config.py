from pathlib import Path

APP_NAME = "Duplicate Finder"
APP_VERSION = "0.5.0"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "app.log"
APP_DATA_DIR = PROJECT_ROOT / "data"
HASH_CACHE_DB = APP_DATA_DIR / "hashes.db"

# Автосохранение последней сессии
AUTOSAVE_FILE = APP_DATA_DIR / "autosave.dupsession.json"

QUICK_HASH_BYTES = 65536
CHUNK_SIZE = 65536
EMPTY_FILE_HASH = "EMPTY"
SESSION_EXT = ".dupsession.json"
SESSION_VERSION = 1
DEFAULT_EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    ".idea",
    ".vscode",
}
DEFAULT_HASH_WORKERS = 4
