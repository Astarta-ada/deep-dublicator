"""Тесты для вспомогательных функций (utils/helpers.py)."""

import os
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock

from utils.helpers import (
    human_size,
    parse_size_string,
    get_file_creation_time,
    format_date,
    get_dir_stats,
)

# ==========================================
# 1. Тесты human_size
# ==========================================


def test_human_size():
    # Байты
    assert human_size(0) == "0.0 B"
    assert human_size(500) == "500.0 B"
    assert human_size(1023) == "1023.0 B"

    # Килобайты
    assert human_size(1024) == "1.0 KB"
    assert human_size(2048) == "2.0 KB"
    assert human_size(1536) == "1.5 KB"

    # Мегабайты, Гигабайты, Терабайты
    assert human_size(1024**2) == "1.0 MB"
    assert human_size(1024**3) == "1.0 GB"
    assert human_size(1024**4) == "1.0 TB"

    # Петабайты (цикл завершается, срабатывает return в конце)
    assert human_size(1024**5) == "1.0 PB"


# ==========================================
# 2. Тесты parse_size_string
# ==========================================


def test_parse_size_string():
    # Без суффикса (только число)
    assert parse_size_string("100") == 100
    assert parse_size_string(" 100 ") == 100

    # С суффиксами (разный регистр)
    assert parse_size_string("1 KB") == 1024
    assert parse_size_string("1 kb") == 1024
    assert parse_size_string("1.5 MB") == int(1.5 * 1024**2)
    assert parse_size_string("2 GB") == 2 * 1024**3
    assert parse_size_string("0.5 TB") == int(0.5 * 1024**4)


# ==========================================
# 3. Тесты get_file_creation_time
# ==========================================


def test_get_file_creation_time(mocker):
    # Случай 1: st_birthtime существует (Windows, macOS)
    st_with_birth = mocker.MagicMock()
    st_with_birth.st_birthtime = 1600000000.0
    st_with_birth.st_ctime = 1700000000.0

    assert get_file_creation_time(st_with_birth) == 1600000000.0

    # Случай 2: st_birthtime отсутствует (Linux) - должен быть fallback на st_ctime
    st_without_birth = mocker.MagicMock()
    del st_without_birth.st_birthtime
    st_without_birth.st_ctime = 1700000000.0

    assert get_file_creation_time(st_without_birth) == 1700000000.0


# ==========================================
# 4. Тесты format_date
# ==========================================


def test_format_date():
    # Используем фиксированный timestamp (1 января 2023, 12:00:00)
    # Внимание: datetime.fromtimestamp зависит от часового пояса системы.
    # Поэтому мы создаем timestamp из локального времени.
    dt = datetime(2023, 1, 1, 12, 0, 0)
    ts = dt.timestamp()

    # Без времени
    assert format_date(ts) == "2023-01-01"

    # Со временем
    assert format_date(ts, with_time=True) == "2023-01-01 12:00:00"


# ==========================================
# 5. Тесты get_dir_stats
# ==========================================


def test_get_dir_stats_success(tmp_path):
    """Проверяет подсчет размера и количества файлов."""
    # Создаем структуру:
    # tmp_path/
    #   ├── file1.txt (100 байт)
    #   └── subdir/
    #       └── file2.txt (50 байт)

    (tmp_path / "file1.txt").write_bytes(b"A" * 100)

    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "file2.txt").write_bytes(b"B" * 50)

    size, count = get_dir_stats(tmp_path)
    assert size == 150
    assert count == 2


def test_get_dir_stats_empty(tmp_path):
    """Проверяет пустую папку."""
    size, count = get_dir_stats(tmp_path)
    assert size == 0
    assert count == 0


def test_get_dir_stats_outer_exception(mocker, tmp_path):
    """Покрывает внешний except (PermissionError, OSError)."""
    # Имитируем ошибку доступа к самой папке
    mocker.patch("os.scandir", side_effect=PermissionError("Access denied"))

    size, count = get_dir_stats(tmp_path)
    assert size == 0
    assert count == 0


def test_get_dir_stats_inner_exception(mocker, tmp_path):
    """Покрывает внутренний except при обработке конкретного файла."""
    # Создаем реальный файл
    (tmp_path / "valid.txt").write_bytes(b"A" * 10)

    # Создаем "сломанный" entry
    broken_entry = MagicMock()
    broken_entry.is_file.side_effect = OSError("Broken entry")

    # Получаем реальные entry для файла
    with os.scandir(tmp_path) as it:
        real_entries = list(it)

    # Создаем мок контекстного менеджера для os.scandir
    mock_scandir = MagicMock()
    mock_scandir.return_value.__enter__.return_value = real_entries + [
        broken_entry
    ]

    mocker.patch("os.scandir", return_value=mock_scandir.return_value)

    size, count = get_dir_stats(tmp_path)

    # Должен посчитать valid.txt и пропустить broken_entry
    assert size == 10
    assert count == 1
