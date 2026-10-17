import sqlite3
from datetime import datetime
from pathlib import Path
from utils.config import APP_DATA_DIR

DB_PATH = APP_DATA_DIR / "history.db"


def init_db():
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT, action TEXT, path TEXT, size INTEGER
            )
        """)


def log_action(action: str, path: str, size: int):
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO actions (timestamp, action, path, size) VALUES (?, ?, ?, ?)",
            (datetime.now().isoformat(), action, path, size),
        )


def get_history():
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(
            "SELECT timestamp, action, path, size FROM actions ORDER BY id DESC LIMIT 500"
        ).fetchall()
