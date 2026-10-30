"""Тесты для сканера директорий (core/scanner.py)."""

import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from core.scanner import normalize_extensions, scan_directory

# ==========================================
# 1. Тесты для normalize_extensions
# ==========================================


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("", set()),
        (None, set()),
        ("   ", set()),
        ("jpg", {".jpg"}),
        ("jpg, png", {".jpg", ".png"}),
        (".PNG;.JPG", {".png", ".jpg"}),
        ("  jpg  ,  .PNG  ,  ,  txt  ", {".jpg", ".png", ".txt"}),
    ],
)
def test_normalize_extensions(raw, expected):
    """Проверяет парсинг расширений из пользовательского ввода."""
    assert normalize_extensions(raw) == expected


# ==========================================
# Фикстуры для scan_directory
# ==========================================


@pytest.fixture
def test_tree(tmp_path):
    """
    Создает структуру:
    root/
      ├── file1.txt (10 байт)
      ├── file2.jpg (20 байт)
      ├── empty.txt (0 байт)
      ├── ignored.tmp
      ├── subdir/
      │   ├── nested.txt (10 байт)
      │   └── ignored.tmp
      └── __pycache__/
          └── cache.pyc
    """
    root = tmp_path / "root"
    root.mkdir()

    (root / "file1.txt").write_bytes(b"A" * 10)
    (root / "file2.jpg").write_bytes(b"B" * 20)
    (root / "empty.txt").write_bytes(b"")
    (root / "ignored.tmp").write_bytes(b"C" * 10)

    sub = root / "subdir"
    sub.mkdir()
    (sub / "nested.txt").write_bytes(b"D" * 10)
    (sub / "ignored.tmp").write_bytes(b"E" * 10)

    cache = root / "__pycache__"
    cache.mkdir()
    (cache / "cache.pyc").write_bytes(b"F" * 10)

    return root


# ==========================================
# 2. Тесты для scan_directory (Базовые)
# ==========================================


def test_scan_recursive(test_tree):
    """Проверяет рекурсивный обход (по умолчанию)."""
    results = list(scan_directory(test_tree, min_size=0))
    names = {p.name for p in results}

    # Должны найтись файлы из подпапок, но не из __pycache__
    assert "file1.txt" in names
    assert "nested.txt" in names
    assert "cache.pyc" not in names  # исключен DEFAULT_EXCLUDE_DIRS
    assert "ignored.tmp" in names  # globs не заданы


def test_scan_non_recursive(test_tree):
    """Проверяет обход без входа в подпапки."""
    results = list(scan_directory(test_tree, recursive=False, min_size=0))
    names = {p.name for p in results}

    assert "file1.txt" in names
    assert "nested.txt" not in names  # подпапка не пройдена


def test_scan_exclude_globs(test_tree):
    """Проверяет исключение по маскам (*.tmp)."""
    results = list(
        scan_directory(test_tree, min_size=0, exclude_globs=["*.tmp"])
    )
    names = {p.name for p in results}

    assert "ignored.tmp" not in names
    assert "file1.txt" in names


# ==========================================
# 3. Тесты фильтрации по размерам и расширениям
# ==========================================


def test_scan_min_max_size(test_tree):
    """Проверяет фильтрацию по минимальному и максимальному размеру."""
    # Ищем только файлы от 5 до 15 байт
    results = list(scan_directory(test_tree, min_size=5, max_size=15))
    names = {p.name for p in results}

    assert "file1.txt" in names  # 10 байт
    assert "nested.txt" in names  # 10 байт
    assert "file2.jpg" not in names  # 20 байт (больше max)
    assert "empty.txt" not in names  # 0 байт (меньше min)


def test_scan_extensions(test_tree):
    """Проверяет фильтр по расширениям."""
    results = list(scan_directory(test_tree, min_size=0, extensions={".jpg"}))
    names = {p.name for p in results}

    assert names == {"file2.jpg"}


# ==========================================
# 4. Тесты ссылок (Symlink / Hardlink)
# ==========================================


def test_scan_symlinks_ignored(test_tree, tmp_path):
    """Проверяет, что симлинки пропускаются по умолчанию."""
    link = test_tree / "symlink.txt"
    try:
        os.symlink(test_tree / "file1.txt", link)
    except OSError:
        pytest.skip("Нет прав на создание симлинка")

    results = list(scan_directory(test_tree, min_size=0))
    names = {p.name for p in results}
    assert "symlink.txt" not in names


def test_scan_symlinks_included(test_tree):
    """Проверяет, что симлинки включаются при include_links=True."""
    link = test_tree / "symlink.txt"
    try:
        os.symlink(test_tree / "file1.txt", link)
    except OSError:
        pytest.skip("Нет прав на создание симлинка")

    results = list(scan_directory(test_tree, min_size=0, include_links=True))
    names = {p.name for p in results}
    assert "symlink.txt" in names


def test_scan_hardlinks_ignored(test_tree, mocker):
    """Проверяет, что хардлинки (nlink > 1) пропускаются по умолчанию."""
    mock_entry = mocker.MagicMock()
    mock_entry.name = "hardlink.txt"
    mock_entry.path = str(test_tree / "hardlink.txt")
    mock_entry.is_symlink.return_value = False
    mock_entry.is_dir.return_value = False
    mock_entry.is_file.return_value = True

    # Имитируем stat с nlink = 2 (хардлинк)
    mock_stat = mocker.MagicMock()
    mock_stat.st_nlink = 2
    mock_stat.st_size = 10
    mock_entry.stat.return_value = mock_stat

    # Возвращаем контекстный менеджер, как это делает os.scandir
    mock_scandir = mocker.MagicMock()
    mock_scandir.return_value.__enter__.return_value = [mock_entry]
    mocker.patch("os.scandir", mock_scandir)

    results = list(scan_directory(test_tree, min_size=0))
    assert len(results) == 0


def test_scan_hardlinks_included(test_tree, mocker):
    """Проверяет, что хардлинки включаются при include_links=True."""
    mock_entry = mocker.MagicMock()
    mock_entry.name = "hardlink.txt"
    mock_entry.path = str(test_tree / "hardlink.txt")
    mock_entry.is_symlink.return_value = False
    mock_entry.is_dir.return_value = False
    mock_entry.is_file.return_value = True

    mock_stat = mocker.MagicMock()
    mock_stat.st_nlink = 2
    mock_stat.st_size = 10
    mock_entry.stat.return_value = mock_stat

    mock_scandir = mocker.MagicMock()
    mock_scandir.return_value.__enter__.return_value = [mock_entry]
    mocker.patch("os.scandir", mock_scandir)

    results = list(scan_directory(test_tree, min_size=0, include_links=True))
    assert len(results) == 1
    assert results[0].name == "hardlink.txt"


# ==========================================
# 5. Тесты прогресс-бара
# ==========================================


def test_scan_progress_callback(tmp_path, mocker):
    """Проверяет, что progress_cb вызывается каждые 500 файлов."""
    root = tmp_path / "many_files"
    root.mkdir()
    for i in range(500):
        (root / f"file{i}.txt").write_text("x")

    mock_cb = MagicMock()
    list(scan_directory(root, min_size=0, progress_cb=mock_cb))

    # Колбэк должен быть вызван ровно 1 раз (на 500-м файле)
    assert mock_cb.call_count == 1
    assert mock_cb.call_args[0][0] == 500


# ==========================================
# 6. Тесты обработки ошибок доступа
# ==========================================


def test_scan_scandir_permission_error(tmp_path, mocker):
    """Покрывает внешний except (PermissionError, OSError) на уровне директории."""
    mocker.patch("os.scandir", side_effect=PermissionError("Access denied"))

    results = list(scan_directory(tmp_path, min_size=0))
    assert results == []  # Ничего не найдено, не упало


def test_scan_entry_error(test_tree, mocker):
    """Покрывает внутренний except при чтении entry."""
    mock_entry = mocker.MagicMock()
    mock_entry.name = "broken.txt"
    mock_entry.path = str(test_tree / "broken.txt")
    # При проверке на симлинк выбрасываем ошибку
    mock_entry.is_symlink.side_effect = OSError("Broken symlink check")

    # Правильный мок контекстного менеджера
    mock_scandir = mocker.MagicMock()
    mock_scandir.return_value.__enter__.return_value = [mock_entry]
    mocker.patch("os.scandir", mock_scandir)

    results = list(scan_directory(test_tree, min_size=0))
    assert results == []  # Ошибка поймана, программа не упала
