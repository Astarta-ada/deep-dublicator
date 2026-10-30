"""Тесты для вычисления хешей (core/hasher.py)."""

import hashlib
import pytest
from pathlib import Path

from core.hasher import hash_file

# ==========================================
# Вспомогательные функции
# ==========================================


def get_expected_hash(content: bytes, algo: str = "sha256") -> str:
    """Вычисляет ожидаемый хеш для проверки."""
    h = hashlib.new(algo)
    h.update(content)
    return h.hexdigest()


# ==========================================
# 1. Полный хеш (quick=False)
# ==========================================


def test_hash_file_full(tmp_path):
    """Проверяет вычисление полного хеша с колбэком прогресса."""
    content = b"Hello, World! This is a test file."
    file_path = tmp_path / "test.txt"
    file_path.write_bytes(content)

    expected = get_expected_hash(content)
    progress_calls = []

    # Вызываем полный хеш
    result = hash_file(
        file_path, quick=False, progress_cb=lambda n: progress_calls.append(n)
    )

    assert result == expected
    # Колбэк должен быть вызван хотя бы один раз (файл читается одним чанком)
    assert len(progress_calls) > 0
    assert sum(progress_calls) == len(content)


def test_hash_file_full_no_progress(tmp_path):
    """Проверяет полный хеш без колбэка прогресса."""
    content = b"Data"
    file_path = tmp_path / "test.txt"
    file_path.write_bytes(content)

    result = hash_file(file_path, quick=False, progress_cb=None)
    assert result == get_expected_hash(content)


# ==========================================
# 2. Быстрый хеш (quick=True)
# ==========================================


def test_hash_file_quick(tmp_path):
    """Проверяет вычисление быстрого хеша (только первые N байт)."""
    content = b"First 10 bytes, then some more data that shouldn't be read."
    file_path = tmp_path / "test.txt"
    file_path.write_bytes(content)

    # Читаем только первые 10 байт
    expected = get_expected_hash(content[:10])
    progress_calls = []

    result = hash_file(
        file_path,
        quick=True,
        quick_bytes=10,
        progress_cb=lambda n: progress_calls.append(n),
    )

    assert result == expected
    assert len(progress_calls) == 1
    assert progress_calls[0] == 10


def test_hash_file_quick_empty(tmp_path):
    """Проверяет быстрый хеш для пустого файла (колбэк не должен вызываться)."""
    file_path = tmp_path / "empty.txt"
    file_path.touch()

    progress_calls = []
    result = hash_file(
        file_path,
        quick=True,
        quick_bytes=100,
        progress_cb=lambda n: progress_calls.append(n),
    )

    # Хеш пустой строки
    assert result == get_expected_hash(b"")
    # Колбэк не должен вызываться, так как data пустая
    assert len(progress_calls) == 0


def test_hash_file_quick_no_progress(tmp_path):
    """Проверяет быстрый хеш без колбэка."""
    content = b"Quick test"
    file_path = tmp_path / "test.txt"
    file_path.write_bytes(content)

    result = hash_file(file_path, quick=True, quick_bytes=5, progress_cb=None)
    assert result == get_expected_hash(content[:5])


# ==========================================
# 3. Обработка ошибок
# ==========================================


def test_hash_file_not_found(tmp_path):
    """Проверяет возврат None, если файла нет (OSError)."""
    missing_file = tmp_path / "ghost.txt"
    result = hash_file(missing_file)
    assert result is None


def test_hash_file_permission_error(tmp_path, mocker):
    """Проверяет возврат None при отсутствии прав доступа (PermissionError)."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("data")

    # Имитируем ошибку доступа при открытии файла
    mocker.patch("builtins.open", side_effect=PermissionError("Access denied"))

    result = hash_file(file_path)
    assert result is None


# ==========================================
# 4. Другие алгоритмы
# ==========================================


def test_hash_file_md5(tmp_path):
    """Проверяет работу с другим алгоритмом (MD5)."""
    content = b"MD5 Test"
    file_path = tmp_path / "test.txt"
    file_path.write_bytes(content)

    expected = get_expected_hash(content, algo="md5")
    result = hash_file(file_path, algorithm="md5")

    assert result == expected
