"""Тесты для операций с файлами (core/file_ops.py)."""

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from core.file_ops import (
    is_file_open,
    delete_file,
    _check_symlink_rights,
    _safe_create_link,
    replace_with_symlink,
    replace_with_hardlink,
    move_to_backup,
    rename_duplicates,
    remove_empty_dirs,
    apply_action_to_group,
    undo_action,
)

# ==========================================
# Фикстуры
# ==========================================


@pytest.fixture
def mock_log_action(mocker):
    """Отключает запись в базу данных истории."""
    return mocker.patch("core.file_ops.log_action")


@pytest.fixture
def files(tmp_path):
    """Создает два реальных файла для тестов."""
    f1 = tmp_path / "original.txt"
    f2 = tmp_path / "duplicate.txt"
    f1.write_text("hello world")
    f2.write_text("hello world")
    return f1, f2


# ==========================================
# 1. is_file_open
# ==========================================


def test_is_file_open_no_psutil(mocker, files):
    """Покрывает if not HAS_PSUTIL."""
    mocker.patch("core.file_ops.HAS_PSUTIL", False)
    assert is_file_open(files[0]) is False


def test_is_file_open_resolve_error(mocker, files):
    """Покрывает except OSError при resolve."""
    mocker.patch("pathlib.Path.resolve", side_effect=OSError("Resolve error"))
    assert is_file_open(files[0]) is False


def test_is_file_open_found(mocker, files):
    """Покрывает успешный поиск открытого файла."""
    mock_proc = MagicMock()
    mock_file = MagicMock()
    mock_file.path = str(files[0])
    mock_proc.info = {"open_files": [mock_file]}

    mocker.patch("psutil.process_iter", return_value=[mock_proc])
    assert is_file_open(files[0]) is True


def test_is_file_open_not_found(mocker, files):
    """Покрывает сценарий, когда файл не открыт ни одним процессом."""
    mock_proc = MagicMock()
    mock_proc.info = {"open_files": []}

    mocker.patch("psutil.process_iter", return_value=[mock_proc])
    assert is_file_open(files[0]) is False


def test_is_file_open_psutil_errors(mocker, files):
    """Покрывает except (NoSuchProcess, AccessDenied)."""
    import psutil

    mock_proc = MagicMock()
    # Имитируем ошибку доступа к процессу
    type(mock_proc).info = mocker.PropertyMock(side_effect=psutil.AccessDenied)

    mocker.patch("psutil.process_iter", return_value=[mock_proc])
    assert is_file_open(files[0]) is False


# ==========================================
# 2. delete_file
# ==========================================


def test_delete_file_dry_run(mock_log_action, mocker, files):
    mock_remove = mocker.patch("os.remove")
    delete_file(files[0], dry_run=True)
    mock_remove.assert_not_called()


def test_delete_file_stat_error(mock_log_action, mocker, files):
    """Покрывает except OSError при stat (size = 0)."""
    mocker.patch("pathlib.Path.stat", side_effect=OSError)
    mock_remove = mocker.patch("os.remove")

    delete_file(files[0], use_trash=False)
    mock_remove.assert_called_once()


def test_delete_file_to_trash(mock_log_action, mocker, files):
    mock_trash = mocker.patch("core.file_ops.send2trash")
    delete_file(files[0], use_trash=True)
    mock_trash.assert_called_once()


def test_delete_file_hard(mock_log_action, mocker, files):
    mock_remove = mocker.patch("os.remove")
    delete_file(files[0], use_trash=False)
    mock_remove.assert_called_once()


# ==========================================
# 3. _check_symlink_rights
# ==========================================


def test_check_symlink_rights_not_windows(mocker):
    """Покрывает if sys.platform != 'win32' (ничего не делает)."""
    mocker.patch("sys.platform", "linux")
    _check_symlink_rights()  # Не должно быть исключений


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows-only (ctypes.windll)"
)
def test_check_symlink_rights_windows_admin(mocker):
    """Покрывает успешную проверку прав на Windows."""
    mocker.patch("sys.platform", "win32")
    mocker.patch("ctypes.windll.shell32.IsUserAnAdmin", return_value=1)
    _check_symlink_rights()  # Не должно быть исключений


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows-only (ctypes.windll)"
)
def test_check_symlink_rights_windows_not_admin(mocker):
    """Покрывает выброс PermissionError."""
    mocker.patch("sys.platform", "win32")
    mocker.patch("ctypes.windll.shell32.IsUserAnAdmin", return_value=0)

    with pytest.raises(PermissionError):
        _check_symlink_rights()


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows-only (ctypes.windll)"
)
def test_check_symlink_rights_ctypes_error(mocker):
    """Покрывает except Exception при вызове ctypes (is_admin = False)."""
    mocker.patch("sys.platform", "win32")
    mocker.patch("ctypes.windll.shell32.IsUserAnAdmin", side_effect=Exception)

    with pytest.raises(PermissionError):
        _check_symlink_rights()


# ==========================================
# 4. _safe_create_link
# ==========================================


def test_safe_create_link_dry_run(mocker, files):
    mock_symlink = mocker.patch("os.symlink")
    _safe_create_link(files[0], files[1], "Symlink", dry_run=True)
    mock_symlink.assert_not_called()


def test_safe_create_link_missing_original(files, tmp_path):
    ghost = tmp_path / "ghost.txt"
    with pytest.raises(FileNotFoundError):
        _safe_create_link(ghost, files[1], "Symlink", dry_run=False)


def test_safe_create_link_same_file(mocker, files):
    mocker.patch("os.path.samefile", return_value=True)
    with pytest.raises(ValueError, match="указывают на один и тот же файл"):
        _safe_create_link(files[0], files[1], "Symlink", dry_run=False)


def test_safe_create_link_tmp_exists(mocker, mock_log_action, files):
    """Покрывает удаление старого временного файла и успешное создание."""
    tmp_link = files[1].with_name(f"{files[1].name}.tmp_link")
    tmp_link.touch()  # Создаем фейковый временный файл

    mocker.patch("os.path.samefile", return_value=False)
    mocker.patch("core.file_ops._check_symlink_rights")
    mocker.patch("os.symlink")
    mocker.patch("pathlib.Path.rename")

    _safe_create_link(files[0], files[1], "Symlink", dry_run=False)
    assert not tmp_link.exists()  # Должен быть удален


def test_safe_create_link_unknown_type(mocker, files):
    mocker.patch("os.path.samefile", return_value=False)
    with pytest.raises(ValueError, match="Неизвестный тип ссылки"):
        _safe_create_link(files[0], files[1], "Unknown", dry_run=False)


def test_safe_create_link_oserror(mocker, files):
    """Покрывает except OSError при создании ссылки."""
    mocker.patch("os.path.samefile", return_value=False)
    mocker.patch("os.link", side_effect=OSError("Cross-device link"))

    with pytest.raises(OSError, match="Ошибка создания Hardlink"):
        _safe_create_link(files[0], files[1], "Hardlink", dry_run=False)


def test_safe_create_link_rollback(mocker, files):
    """Покрывает откат: первый rename (dup→bak) ок, второй (tmp→dup) падает."""
    mocker.patch("os.path.samefile", return_value=False)

    # os.link создаёт реальный tmp-файл, чтобы откат имел что убирать
    def fake_link(src, dst):
        Path(dst).touch()

    mocker.patch("os.link", side_effect=fake_link)

    # Первый rename (duplicate → bak) — реальный, второй (tmp → duplicate) — падает.
    orig_rename = Path.rename
    calls = {"n": 0}

    def mock_rename(self, target):
        calls["n"] += 1
        if calls["n"] == 2:
            raise Exception("Rename failed")
        return orig_rename(self, target)

    mocker.patch.object(Path, "rename", mock_rename)

    with pytest.raises(OSError, match="Не удалось завершить замену"):
        _safe_create_link(files[0], files[1], "Hardlink", dry_run=False)

    # Дубликат восстановлен на месте после отката
    assert files[1].exists()
    # tmp_link убран
    tmp_name = files[1].with_name(f"{files[1].name}.tmp_link")
    assert not tmp_name.exists()
    # bak_link тоже не остался висеть
    bak_name = files[1].with_name(f"{files[1].name}.bak_link")
    assert not bak_name.exists()


def test_replace_wrappers(mocker, files):
    """Покрывает вызовы replace_with_symlink и replace_with_hardlink."""
    mock_safe = mocker.patch("core.file_ops._safe_create_link")

    replace_with_symlink(files[0], files[1])
    mock_safe.assert_called_with(files[0], files[1], "Symlink", False)

    replace_with_hardlink(files[0], files[1])
    mock_safe.assert_called_with(files[0], files[1], "Hardlink", False)


# ==========================================
# 5. move_to_backup
# ==========================================


def test_move_to_backup_dry_run(mocker, files, tmp_path):
    mock_move = mocker.patch("shutil.move")
    move_to_backup(tmp_path, files[1], tmp_path, dry_run=True)
    mock_move.assert_not_called()


def test_move_to_backup_stat_error(mock_log_action, mocker, files, tmp_path):
    real_stat = Path.stat

    def fake_stat(self):
        if self == files[1]:
            raise OSError
        return real_stat(self)

    mocker.patch("pathlib.Path.stat", fake_stat)
    mocker.patch("shutil.move")
    move_to_backup(tmp_path, files[1], tmp_path, dry_run=False)


def test_move_to_backup_relative_error(
    mock_log_action, mocker, files, tmp_path
):
    """Покрывает except ValueError при relative_to (файл вне base_root)."""
    mocker.patch("pathlib.Path.relative_to", side_effect=ValueError)
    mock_move = mocker.patch("shutil.move")

    move_to_backup(tmp_path, files[1], tmp_path, dry_run=False)
    assert mock_move.called


def test_move_to_backup_success(mock_log_action, mocker, files, tmp_path):
    backup_dir = tmp_path / "backup"
    mocker.patch("shutil.move")
    move_to_backup(backup_dir, files[1], tmp_path, dry_run=False)


# ==========================================
# 6. rename_duplicates
# ==========================================


def test_rename_duplicates_dry_run(mocker, files):
    mock_rename = mocker.patch("pathlib.Path.rename")
    ok, errs = rename_duplicates(files[0], [files[1]], dry_run=True)
    assert ok == 1
    mock_rename.assert_not_called()


def test_rename_duplicates_success(mock_log_action, mocker, files):
    mock_rename = mocker.patch("pathlib.Path.rename")
    ok, errs = rename_duplicates(files[0], [files[1]], dry_run=False)
    assert ok == 1
    mock_rename.assert_called_once()


def test_rename_duplicates_error(mocker, files):
    mocker.patch("pathlib.Path.stat", side_effect=Exception("Stat failed"))
    ok, errs = rename_duplicates(files[0], [files[1]], dry_run=False)
    assert ok == 0
    assert len(errs) == 1


# ==========================================
# 7. remove_empty_dirs
# ==========================================


def test_remove_empty_dirs(mocker, tmp_path, caplog):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    mock_rmdir = mocker.patch("os.rmdir")
    remove_empty_dirs(tmp_path)
    mock_rmdir.assert_called()


def test_remove_empty_dirs_error(mocker, tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    mocker.patch("os.rmdir", side_effect=OSError("Access denied"))
    remove_empty_dirs(tmp_path)  # Не должно падать


# ==========================================
# 8. apply_action_to_group
# ==========================================


def test_apply_action_skip_original_and_samefile(mocker, files):
    """Покрывает пропуск, если dup == original и если samefile == True."""
    mocker.patch("os.path.samefile", return_value=True)
    mock_delete = mocker.patch("core.file_ops.delete_file")

    ok, errs = apply_action_to_group(files[0], [files[0], files[1]], "delete")
    assert ok == 0
    mock_delete.assert_not_called()


def test_apply_action_samefile_error(mocker, files):
    """Покрывает pass при ошибке samefile."""
    mocker.patch("os.path.samefile", side_effect=OSError)
    mocker.patch("core.file_ops.delete_file")

    apply_action_to_group(files[0], [files[1]], "delete")


def test_apply_action_delete(mocker, files):
    mock_delete = mocker.patch("core.file_ops.delete_file")
    ok, errs = apply_action_to_group(files[0], [files[1]], "delete")
    assert ok == 1
    mock_delete.assert_called_with(files[1], use_trash=False, dry_run=False)


def test_apply_action_trash(mocker, files):
    mock_delete = mocker.patch("core.file_ops.delete_file")
    ok, errs = apply_action_to_group(files[0], [files[1]], "trash")
    assert ok == 1
    mock_delete.assert_called_with(files[1], use_trash=True, dry_run=False)


def test_apply_action_symlink(mocker, files):
    mock_symlink = mocker.patch("core.file_ops.replace_with_symlink")
    ok, errs = apply_action_to_group(files[0], [files[1]], "symlink")
    assert ok == 1
    mock_symlink.assert_called_once()


def test_apply_action_hardlink(mocker, files):
    mock_hardlink = mocker.patch("core.file_ops.replace_with_hardlink")
    ok, errs = apply_action_to_group(files[0], [files[1]], "hardlink")
    assert ok == 1
    mock_hardlink.assert_called_once()


def test_apply_action_backup(mocker, files, tmp_path):
    mock_backup = mocker.patch("core.file_ops.move_to_backup")
    ok, errs = apply_action_to_group(
        files[0], [files[1]], "backup", backup_dir=tmp_path, base_root=tmp_path
    )
    assert ok == 1
    mock_backup.assert_called_once()


def test_apply_action_unknown(mocker, files):
    """Покрывает raise ValueError внутри try и его перехват."""
    ok, errs = apply_action_to_group(files[0], [files[1]], "unknown_action")
    assert ok == 0
    assert len(errs) == 1
    assert "Неизвестное действие" in errs[0][1]


def test_import_psutil_fail(mocker):
    """Покрывает строки 15-16: except ImportError при отсутствии psutil."""
    import sys
    import importlib
    import core.file_ops

    # Имитируем, что psutil не установлен
    mocker.patch.dict(sys.modules, {"psutil": None})
    importlib.reload(core.file_ops)
    assert core.file_ops.HAS_PSUTIL is False

    # Возвращаем все как было для других тестов
    mocker.stopall()
    importlib.reload(core.file_ops)


def test_undo_action_backup(tmp_path, mocker):
    orig = tmp_path / "file.txt"
    backup = tmp_path / "backup" / "file.txt"
    backup.parent.mkdir()
    backup.write_text("data")

    meta = '{"backup_path": "' + str(backup).replace("\\", "\\\\") + '"}'

    # Мокаем mark_as_undone
    mock_mark = mocker.patch("core.file_ops.mark_as_undone")

    success = undo_action(1, "backup", str(orig), meta)

    assert success is True
    assert orig.exists()
    assert not backup.exists()
    assert mock_mark.called


# ==========================================
# 9. Тесты для undo_action (Новое)
# ==========================================


def test_undo_action_backup_success(tmp_path, mocker):
    """Проверяет восстановление файла из бэкапа."""
    orig = tmp_path / "file.txt"
    backup = tmp_path / "backup" / "file.txt"
    backup.parent.mkdir()
    backup.write_text("data")

    meta = f'{{"backup_path": "{str(backup).replace(chr(92), chr(92)*2)}"}}'
    mock_mark = mocker.patch("core.file_ops.mark_as_undone")

    success = undo_action(1, "backup", str(orig), meta)

    assert success is True
    assert orig.exists()
    assert not backup.exists()
    assert mock_mark.called


def test_undo_action_rename_success(tmp_path, mocker):
    """Проверяет отмену переименования."""
    orig = tmp_path / "file.txt"
    new_path = tmp_path / "file_copy1.txt"
    new_path.write_text("data")

    meta = f'{{"new_path": "{str(new_path).replace(chr(92), chr(92)*2)}"}}'
    mock_mark = mocker.patch("core.file_ops.mark_as_undone")

    success = undo_action(1, "rename", str(orig), meta)

    assert success is True
    assert orig.exists()
    assert not new_path.exists()
    assert mock_mark.called


def test_undo_action_invalid_meta(tmp_path):
    """Проверяет некорректный JSON в метаданных."""
    success = undo_action(1, "backup", "C:/file.txt", "not_a_json")
    assert success is False


def test_undo_action_missing_meta():
    """Проверяет отсутствие метаданных (None)."""
    success = undo_action(1, "backup", "C:/file.txt", None)
    assert success is False


def test_undo_action_unsupported_action():
    """Проверяет неподдерживаемое действие (например, delete)."""
    success = undo_action(1, "delete_hard", "C:/file.txt", "{}")
    assert success is False


def test_undo_action_file_missing(tmp_path):
    """Проверяет ошибку, если файл бэкапа не найден."""
    orig = tmp_path / "file.txt"
    meta = '{"backup_path": "C:/ghost_backup.txt"}'

    with pytest.raises(FileNotFoundError):
        undo_action(1, "backup", str(orig), meta)


def test_undo_action_dest_exists(tmp_path):
    """Проверяет ошибку, если исходный файл уже существует."""
    orig = tmp_path / "file.txt"
    orig.write_text("existing")
    backup = tmp_path / "backup.txt"
    backup.write_text("data")

    meta = f'{{"backup_path": "{str(backup).replace(chr(92), chr(92)*2)}"}}'

    with pytest.raises(FileExistsError):
        undo_action(1, "backup", str(orig), meta)


def test_move_to_backup_passes_meta_to_log_action(tmp_path, mocker):
    """Регресс: meta должна реально попасть в log_action (для Undo)."""
    mock_log = mocker.patch("core.file_ops.log_action")
    orig = tmp_path / "dup.txt"
    orig.write_text("data")
    backup_dir = tmp_path / "backup"
    move_to_backup(backup_dir, orig, tmp_path, dry_run=False)

    # Последний аргумент (meta) должен быть JSON с backup_path
    args, kwargs = mock_log.call_args
    meta = kwargs.get("meta") or (args[3] if len(args) > 3 else None)
    assert meta is not None
    assert "backup_path" in meta


def test_rename_duplicates_passes_meta_to_log_action(tmp_path, mocker):
    """Регресс: meta для rename должна попасть в log_action."""
    mock_log = mocker.patch("core.file_ops.log_action")
    orig = tmp_path / "a.txt"
    dup = tmp_path / "b.txt"
    orig.write_text("x")
    dup.write_text("x")
    rename_duplicates(orig, [dup], dry_run=False)

    args, kwargs = mock_log.call_args
    meta = kwargs.get("meta") or (args[3] if len(args) > 3 else None)
    assert meta is not None
    assert "new_path" in meta


def test_undo_through_real_db(tmp_path, mocker):
    """Интеграционный: move_to_backup → запись в БД → undo_action."""
    mocker.patch("utils.history.APP_DATA_DIR", tmp_path)
    mocker.patch("utils.history.DB_PATH", tmp_path / "history.db")
    # log_action не мокаем — пусть пишет в реальную (временную) БД
    from utils import history
    from core.file_ops import move_to_backup, undo_action
    import sqlite3

    orig = tmp_path / "dup.txt"
    orig.write_text("data")
    backup = tmp_path / "backup"
    move_to_backup(backup, orig, tmp_path, dry_run=False)
    assert not orig.exists()

    conn = sqlite3.connect(tmp_path / "history.db")
    row = conn.execute(
        "SELECT id, action, path, meta FROM actions ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()

    action_id, action, path, meta = row
    assert action == "backup"
    assert meta is not None
    assert undo_action(action_id, action, path, meta) is True
    assert orig.exists()
