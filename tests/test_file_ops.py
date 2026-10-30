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


def test_check_symlink_rights_windows_admin(mocker):
    """Покрывает успешную проверку прав на Windows."""
    mocker.patch("sys.platform", "win32")
    mocker.patch("ctypes.windll.shell32.IsUserAnAdmin", return_value=1)
    _check_symlink_rights()  # Не должно быть исключений


def test_check_symlink_rights_windows_not_admin(mocker):
    """Покрывает выброс PermissionError."""
    mocker.patch("sys.platform", "win32")
    mocker.patch("ctypes.windll.shell32.IsUserAnAdmin", return_value=0)

    with pytest.raises(PermissionError):
        _check_symlink_rights()


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
    """Покрывает откат изменений при ошибке переименования."""
    mocker.patch("os.path.samefile", return_value=False)
    mocker.patch("os.link")
    mocker.patch("pathlib.Path.rename", side_effect=Exception("Rename failed"))

    # Имитируем, что временный файл существует, чтобы сработала строка отката (unlink)
    mocker.patch("pathlib.Path.exists", return_value=True)
    mock_unlink = mocker.patch("pathlib.Path.unlink")

    with pytest.raises(OSError, match="Не удалось завершить замену"):
        _safe_create_link(files[0], files[1], "Hardlink", dry_run=False)

    # Проверяем, что откат (удаление) действительно был вызван
    assert mock_unlink.called


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
    mocker.patch("pathlib.Path.stat", side_effect=OSError)
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
