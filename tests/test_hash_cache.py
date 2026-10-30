"""Тесты для SQLite-кэша хешей (core/hash_cache.py)."""

import contextlib
import sqlite3
import pytest
from pathlib import Path

from core.hash_cache import HashCache, _NoCache

# ==========================================
# 1. Тесты для _NoCache (заглушки)
# ==========================================


def test_no_cache():
    """Проверяет, что заглушка ничего не делает и не падает."""
    cache = _NoCache()
    assert cache.get(Path("test.txt"), 100, 1234.5) is None
    assert cache.put(Path("test.txt"), 100, 1234.5, "hash123") is None
    assert cache.close() is None


# ==========================================
# 2. Тесты для HashCache
# ==========================================


@pytest.fixture
def test_db(tmp_path, mocker):
    """Создает временную БД для тестов, чтобы не трогать реальную."""
    db_file = tmp_path / "test_hashes.db"

    # ИСПРАВЛЕНИЕ: Подменяем саму переменную APP_DATA_DIR на временную папку
    mocker.patch("core.hash_cache.APP_DATA_DIR", new=tmp_path)

    cache = HashCache(db_path=db_file)
    yield cache
    cache.close()


def test_hash_cache_init(test_db, tmp_path):
    """Проверяет, что база данных создается с правильной структурой."""
    db_file = tmp_path / "test_hashes.db"
    assert db_file.exists()

    # ИСПРАВЛЕНИЕ: contextlib.closing гарантирует закрытие соединения
    with contextlib.closing(sqlite3.connect(db_file)) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='hashes'"
        )
        assert cursor.fetchone() is not None


def test_hash_cache_put_and_get(test_db):
    """Проверяет сохранение и чтение хеша."""
    path = Path("C:/test/file.txt")
    test_db.put(path, 1024, 1600000000.0, "abc123hash")

    # Успешное чтение
    assert test_db.get(path, 1024, 1600000000.0) == "abc123hash"


def test_hash_cache_get_miss(test_db):
    """Проверяет, что возвращается None, если файла нет в кэше."""
    path = Path("C:/test/missing.txt")
    assert test_db.get(path, 0, 0.0) is None

    # Проверяем несовпадение по размеру или времени
    test_db.put(path, 1024, 1600000000.0, "hash1")
    assert test_db.get(path, 2048, 1600000000.0) is None
    assert test_db.get(path, 1024, 1600000001.0) is None


def test_hash_cache_put_replace(test_db):
    """Проверяет перезапись (INSERT OR REPLACE) при одинаковых ключах."""
    path = Path("C:/test/file.txt")

    # Сохраняем первый раз
    test_db.put(path, 1024, 1600000000.0, "old_hash")
    assert test_db.get(path, 1024, 1600000000.0) == "old_hash"

    # Перезаписываем с теми же ключами, но другим хешем
    test_db.put(path, 1024, 1600000000.0, "new_hash")
    assert test_db.get(path, 1024, 1600000000.0) == "new_hash"


def test_hash_cache_close_error(mocker):
    """Покрывает ветку except Exception при закрытии базы."""
    # 1. Создаем мок-соединение, которое падает при закрытии
    mock_conn = mocker.MagicMock()
    mock_conn.close.side_effect = Exception("Mock close error")

    # 2. Подменяем sqlite3.connect ДО создания HashCache,
    # чтобы __init__ не создавал реальную БД
    mocker.patch("sqlite3.connect", return_value=mock_conn)

    mock_log_error = mocker.patch("core.hash_cache.log.error")

    # 3. Создаем кэш (он будет использовать мок-соединение)
    cache = HashCache(db_path=Path("dummy.db"))

    # 4. Вызываем close (должен сработать except и вызваться log.error)
    cache.close()

    assert mock_log_error.called
