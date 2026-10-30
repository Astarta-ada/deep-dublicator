"""Тесты для фоновых потоков (core/workers.py)."""

import sys
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock

from core.workers import (
    ScanWorker,
    ApplyWorker,
    FolderScannerWorker,
    HogsScanner,
    JunkScanner,
)

# ==========================================
# Фикстуры
# ==========================================


@pytest.fixture
def mock_signals():
    """Создает моки для сигналов QThread."""
    return {
        "progress_msg": MagicMock(),
        "progress_bytes": MagicMock(),
        "finished_ok": MagicMock(),
        "failed": MagicMock(),
        "progress": MagicMock(),
    }


# ==========================================
# 1. ScanWorker
# ==========================================


def test_scan_worker_strict(mocker, mock_signals):
    mocker.patch(
        "core.workers.scan_directory", return_value=[Path("f1"), Path("f2")]
    )
    mock_find = mocker.patch(
        "core.workers.find_duplicates", return_value={"h1": [Path("f1")]}
    )

    worker = ScanWorker(
        root=Path("C:/"),
        recursive=True,
        min_size=1,
        max_size=None,
        extensions=None,
        include_empty=False,
        use_cache=True,
        mode="strict",
        globs=[],
        phash=8,
    )
    # Подменяем сигналы
    worker.progress_msg = mock_signals["progress_msg"]
    worker.progress_bytes = mock_signals["progress_bytes"]
    worker.finished_ok = mock_signals["finished_ok"]

    worker.run()

    assert mock_signals["progress_msg"].emit.call_count == 2
    assert mock_signals["finished_ok"].emit.called
    mock_find.assert_called_once()


def test_scan_worker_modes(mocker):
    """Проверяет вызов правильных функций для каждого режима."""
    mocker.patch("core.workers.scan_directory", return_value=[Path("f1")])

    modes = {
        "similar_img": "find_similar_images",
        "similar_vid": "find_similar_videos",
        "audio": "find_audio_duplicates",
        "name": "find_by_name",
        "zero": "find_zero_fill_files",
    }

    for mode, func_name in modes.items():
        mock_func = mocker.patch(f"core.workers.{func_name}", return_value={})
        worker = ScanWorker(
            Path("C:/"), True, 1, None, None, False, True, mode, [], 8
        )
        worker.finished_ok = MagicMock()
        worker.run()
        mock_func.assert_called_once()


def test_scan_worker_links_valid(mocker):
    mocker.patch("core.workers.scan_directory", return_value=[])
    mocker.patch("pathlib.Path.exists", return_value=True)
    mock_links = mocker.patch(
        "core.workers.find_links_to_file", return_value={"LINKS": []}
    )

    worker = ScanWorker(
        Path("C:/"),
        True,
        1,
        None,
        None,
        False,
        True,
        "links",
        [],
        8,
        target_file="target.txt",
    )
    worker.finished_ok = MagicMock()
    worker.run()
    mock_links.assert_called_once()


def test_scan_worker_links_invalid(mocker):
    mocker.patch("core.workers.scan_directory", return_value=[])
    mocker.patch("pathlib.Path.exists", return_value=False)

    worker = ScanWorker(
        Path("C:/"),
        True,
        1,
        None,
        None,
        False,
        True,
        "links",
        [],
        8,
        target_file="ghost.txt",
    )
    worker.failed = MagicMock()
    worker.run()
    assert worker.failed.emit.called


def test_scan_worker_unknown_mode(mocker):
    mocker.patch("core.workers.scan_directory", return_value=[])
    worker = ScanWorker(
        Path("C:/"), True, 1, None, None, False, True, "unknown", [], 8
    )
    worker.finished_ok = MagicMock()
    worker.run()
    worker.finished_ok.emit.assert_called_once_with({})


def test_scan_worker_exception(mocker):
    mocker.patch(
        "core.workers.scan_directory", side_effect=Exception("Test error")
    )
    worker = ScanWorker(
        Path("C:/"), True, 1, None, None, False, True, "strict", [], 8
    )
    worker.failed = MagicMock()
    worker.run()
    worker.failed.emit.assert_called_once_with("Test error")


# ==========================================
# 2. ApplyWorker
# ==========================================


def test_apply_worker_rename(mocker):
    mock_group = MagicMock()
    mock_group.selected_count.return_value = 1
    mock_group.get_selection.return_value = (Path("orig"), [Path("dup")])

    mock_rename = mocker.patch(
        "core.workers.rename_duplicates", return_value=(1, [])
    )

    worker = ApplyWorker([mock_group], "rename", None, None, False)
    worker.finished_ok = MagicMock()
    worker.progress = MagicMock()
    worker.run()

    mock_rename.assert_called_once()
    worker.finished_ok.emit.assert_called_once_with(1, [])


def test_apply_worker_action(mocker):
    mock_group = MagicMock()
    mock_group.selected_count.return_value = 1
    mock_group.get_selection.return_value = (Path("orig"), [Path("dup")])

    mock_apply = mocker.patch(
        "core.workers.apply_action_to_group", return_value=(1, [])
    )

    worker = ApplyWorker([mock_group], "delete", None, Path("C:/"), False)
    worker.finished_ok = MagicMock()
    worker.progress = MagicMock()
    worker.run()

    mock_apply.assert_called_once()
    worker.finished_ok.emit.assert_called_once()


def test_apply_worker_skip_empty(mocker):
    mock_group = MagicMock()
    mock_group.selected_count.return_value = 0
    mock_group.get_selection.return_value = (Path("orig"), [])

    mock_apply = mocker.patch("core.workers.apply_action_to_group")

    worker = ApplyWorker([mock_group], "delete", None, Path("C:/"), False)
    worker.finished_ok = MagicMock()
    worker.run()

    mock_apply.assert_not_called()
    worker.finished_ok.emit.assert_called_once_with(0, [])


# ==========================================
# 3. FolderScannerWorker
# ==========================================


def test_folder_scanner_worker(mocker):
    # Создаем фейковые entry
    mock_dir = MagicMock()
    mock_dir.name = "folder"
    mock_dir.path = "C:/folder"
    mock_dir.is_dir.return_value = True
    mock_dir.is_file.return_value = False

    mock_file = MagicMock()
    mock_file.name = "file.txt"
    mock_file.path = "C:/file.txt"
    mock_file.is_dir.return_value = False
    mock_file.is_file.return_value = True
    mock_file.stat.return_value = MagicMock(st_size=100, st_mtime=1600000000.0)

    # Мок сканирования папки
    mock_scandir = MagicMock()
    mock_scandir.return_value.__enter__.return_value = [mock_dir, mock_file]
    mocker.patch("os.scandir", mock_scandir)
    mocker.patch("core.workers.get_dir_stats", return_value=(200, 2))

    worker = FolderScannerWorker(Path("C:/"))
    worker.finished_ok = MagicMock()
    worker.progress = MagicMock()
    worker.run()

    assert worker.finished_ok.emit.called
    args = worker.finished_ok.emit.call_args[0][0]
    assert len(args) == 2  # Должны быть папка и файл


def test_folder_scanner_permission_error(mocker):
    mock_dir = MagicMock()
    mock_dir.is_dir.side_effect = PermissionError("Access denied")

    mock_scandir = MagicMock()
    mock_scandir.return_value.__enter__.return_value = [mock_dir]
    mocker.patch("os.scandir", mock_scandir)

    worker = FolderScannerWorker(Path("C:/"))
    worker.finished_ok = MagicMock()
    worker.run()
    assert worker.finished_ok.emit.called


def test_folder_scanner_outer_exception(mocker):
    mocker.patch("os.scandir", side_effect=Exception("Disk error"))
    worker = FolderScannerWorker(Path("C:/"))
    worker.finished_ok = MagicMock()
    worker.run()
    worker.finished_ok.emit.assert_called_once_with([])


# ==========================================
# 4. HogsScanner
# ==========================================


def test_hogs_scanner(tmp_path):
    """Проверяет поиск больших файлов с помощью реальных файлов."""
    # Создаем реальные файлы в tmp_path
    big_file = tmp_path / "big.bin"
    big_file.write_bytes(b"x" * 2000)  # 2000 байт

    small_file = tmp_path / "small.bin"
    small_file.write_bytes(b"x" * 10)  # 10 байт

    worker = HogsScanner(tmp_path, min_size=1000, older_than_days=0)
    worker.finished_ok = MagicMock()
    worker.run()

    # Получаем аргументы, переданные в сигнал
    args = worker.finished_ok.emit.call_args[0][0]

    # Должен быть найден только один файл (big.bin)
    assert len(args) == 1
    assert "big.bin" in args[0][0]


def test_hogs_scanner_age_filter(mocker):
    mocker.patch("os.walk", return_value=[("C:/", [], ["old.bin"])])

    # Файл очень старый (10 лет назад)
    m = MagicMock()
    m.st_size = 2000
    m.st_mtime = 0.0
    mocker.patch("pathlib.Path.stat", return_value=m)

    worker = HogsScanner(Path("C:/"), min_size=1000, older_than_days=365)
    worker.finished_ok = MagicMock()
    worker.run()

    args = worker.finished_ok.emit.call_args[0][0]
    assert len(args) == 1


def test_hogs_scanner_error(mocker, tmp_path):
    """Покрывает ветку except OSError при stat (строка 251)."""
    # Создаем файл, чтобы os.walk его нашел
    f = tmp_path / "err.bin"
    f.write_bytes(b"x" * 100)

    # Имитируем ошибку доступа при вызове stat
    mocker.patch("pathlib.Path.stat", side_effect=OSError("Access denied"))

    worker = HogsScanner(tmp_path, min_size=0, older_than_days=0)
    worker.finished_ok = MagicMock()
    worker.run()

    # Так как stat упал, список результатов должен быть пустым
    args = worker.finished_ok.emit.call_args[0][0]
    assert len(args) == 0


# ==========================================
# 5. JunkScanner (Кроссплатформенность)
# ==========================================


def test_junk_scanner_windows(mocker):
    mocker.patch("sys.platform", "win32")
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("core.workers.get_dir_stats", return_value=(100, 1))
    # Мокаем сканирование __pycache__ и node_modules
    mocker.patch(
        "os.walk", return_value=[("C:/", ["__pycache__", "node_modules"], [])]
    )
    mocker.patch("os.path.isdir", return_value=True)

    worker = JunkScanner(Path("C:/"))
    worker.finished_ok = MagicMock()
    worker.run()

    assert worker.finished_ok.emit.called
    args = worker.finished_ok.emit.call_args[0][0]
    # Temp, Chrome, Edge, Mozilla, Python, Node (6 шт)
    assert len(args) >= 4


def test_junk_scanner_mac(mocker):
    mocker.patch("sys.platform", "darwin")
    mocker.patch("os.path.exists", return_value=False)  # Пропускаем кэши
    mocker.patch("os.path.isdir", return_value=False)

    worker = JunkScanner(Path("C:/"))
    worker.finished_ok = MagicMock()
    worker.run()
    assert worker.finished_ok.emit.called


def test_junk_scanner_linux(mocker):
    mocker.patch("sys.platform", "linux")
    mocker.patch("os.path.exists", return_value=False)
    mocker.patch("os.path.isdir", return_value=False)

    worker = JunkScanner(Path("C:/"))
    worker.finished_ok = MagicMock()
    worker.run()
    assert worker.finished_ok.emit.called


def test_junk_scanner_no_root(mocker):
    mocker.patch("os.path.exists", return_value=False)
    worker = JunkScanner(None)
    worker.finished_ok = MagicMock()
    worker.run()
    worker.finished_ok.emit.assert_called_once_with([])


def test_scan_worker_progress_cb(mocker):
    """Покрывает вызов коллбэка прогресса внутри ScanWorker (строки 84-87)."""
    mocker.patch("core.workers.scan_directory", return_value=[Path("f1")])

    # Имитируем, что find_duplicates вызывает коллбэк, чтобы отработали строки с eta
    def mock_find(files, cb, *args):
        cb("quick_hash", 10, 100)
        return {}

    mocker.patch("core.workers.find_duplicates", side_effect=mock_find)

    worker = ScanWorker(
        Path("C:/"), True, 1, None, None, False, True, "strict", [], 8
    )
    worker.progress_bytes = MagicMock()
    worker.run()

    # Проверяем, что прогресс был отправлен
    assert worker.progress_bytes.emit.called


def test_hogs_scanner_age_filter_skip(mocker, tmp_path):
    """Покрывает ветку continue (пропуск слишком свежего файла)."""
    # Создаем реальный свежий файл
    f = tmp_path / "new.bin"
    f.write_bytes(b"x" * 2000)  # 2000 байт

    # Запрашиваем файлы старше 365 дней. Наш файл создан только что,
    # поэтому он должен быть пропущен (сработает continue).
    worker = HogsScanner(tmp_path, min_size=1000, older_than_days=365)
    worker.finished_ok = MagicMock()
    worker.run()

    # Результат должен быть пустым, так как файл слишком новый
    args = worker.finished_ok.emit.call_args[0][0]
    assert len(args) == 0
