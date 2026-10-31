"""Операции с файлами: удаление, ссылки, перемещение, очистка."""

import ctypes
import logging
import os
import sys
import shutil
import json
from pathlib import Path
from send2trash import send2trash

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from utils.history import log_action, mark_as_undone

log = logging.getLogger(__name__)


def is_file_open(path: Path):  # -> bool:
    """Проверяет, открыт ли файл каким-либо процессом."""

    if not HAS_PSUTIL:
        return False

    try:
        target_path = path.resolve()
    except OSError:
        return False

    for proc in psutil.process_iter(["open_files"]):
        try:
            if proc.info["open_files"]:
                for f in proc.info["open_files"]:
                    if Path(f.path).resolve() == target_path:
                        return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def delete_file(
    path: Path, use_trash: bool = False, dry_run: bool = False
):  # -> None:
    """Удаляет файл. При use_trash=True — в корзину (send2trash)."""
    if dry_run:
        log.info("[DRY-RUN] Удалить: %s", path)
        return

    try:
        size = path.stat().st_size
    except OSError:
        size = 0

    if use_trash:
        send2trash(str(path))
        log.info("В корзину: %s", path)
        log_action("delete_trash", str(path), size)
    else:
        os.remove(path)
        log.info("Удалён: %s", path)
        log_action("delete_hard", str(path), size)


def _check_symlink_rights():
    """Проверяет права на создание симлинков (актуально для Windows)."""
    if sys.platform == "win32":
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            is_admin = False

        if not is_admin:
            raise PermissionError(
                "Для создания симлинков в Windows требуются права администратора "
                "или включенный 'Режим разработчика'."
            )


def _safe_create_link(
    original: Path, duplicate: Path, link_type: str, dry_run: bool
):  # -> None:
    """Вспомогательный метод для безопасного создания ссылок (симлинков или хардлинков)."""
    if dry_run:
        log.info("[DRY-RUN] %s: %s -> %s", link_type, duplicate, original)
        return

    if not original.exists():
        raise FileNotFoundError(f"Оригинал не найден: {original}")

    target = original.resolve()

    # Защита от создания ссылки на самого себя
    if os.path.samefile(duplicate, target):
        raise ValueError(
            "Оригинал и дубликат указывают на один и тот же файл."
        )

    size = duplicate.stat().st_size
    tmp_name = duplicate.with_name(f"{duplicate.name}.tmp_link")

    # Удаляем старый временный файл, если остался от предыдущих сбоев
    if tmp_name.exists() or tmp_name.is_symlink():
        tmp_name.unlink()

    try:
        if link_type == "Symlink":
            _check_symlink_rights()
            os.symlink(target, tmp_name)
        elif link_type == "Hardlink":
            os.link(target, tmp_name)
        else:
            raise ValueError(f"Неизвестный тип ссылки: {link_type}")
    except OSError as e:
        log.error("Не удалось создать %s: %s", link_type, e)
        raise OSError(
            f"Ошибка создания {link_type} (возможно, файлы на разных дисках): {e}"
        )

    # Если ссылка создана успешно, удаляем дубликат и переименовываем временный файл
    try:
        duplicate.unlink()
        tmp_name.rename(duplicate)
        log.info("%s: %s → %s", link_type, duplicate, target)
        log_action(link_type.lower(), str(duplicate), size)
    except Exception as e:
        if tmp_name.exists() or tmp_name.is_symlink():
            tmp_name.unlink()  # Откатываем изменения
        raise OSError(f"Не удалось завершить замену: {e}")


def replace_with_symlink(
    original: Path, duplicate: Path, dry_run: bool = False
):  # -> None:
    """Заменяет duplicate символьной ссылкой на original."""
    _safe_create_link(original, duplicate, "Symlink", dry_run)


def replace_with_hardlink(
    original: Path, duplicate: Path, dry_run: bool = False
):  # -> None:
    """Заменяет duplicate жесткой ссылкой на original."""
    _safe_create_link(original, duplicate, "Hardlink", dry_run)


def move_to_backup(
    backup_dir: Path, duplicate: Path, base_root: Path, dry_run: bool = False
):  # -> None:
    """Перемещает файл в папку бэкапа с сохранением структуры."""
    if dry_run:
        log.info("[DRY-RUN] В бэкап: %s", duplicate)
        return

    try:
        size = duplicate.stat().st_size
    except OSError:
        size = 0

    try:
        rel_path = duplicate.relative_to(base_root)
    except ValueError:
        rel_path = Path(duplicate.name)

    dest = backup_dir / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)

    shutil.move(str(duplicate), str(dest))
    # Сохраняем метаданные (куда переместили)
    meta = json.dumps({"backup_path": str(dest)})

    log.info("Перемещено в бэкап: %s → %s", duplicate, dest)
    log_action("backup", str(duplicate), size)


def rename_duplicates(
    original: Path, duplicates: list[Path], dry_run: bool = False
):  # -> tuple[int, list[tuple[Path, str]]]:
    """Переименовывает дубликаты, добавляя _copy1, _copy2 и т.д."""
    ok = 0
    errors = []

    for i, dup in enumerate(duplicates, 1):
        new_name = dup.with_name(f"{dup.stem}_copy{i}{dup.suffix}")

        if dry_run:
            log.info("[DRY-RUN] Переименовать: %s -> %s", dup, new_name)
            ok += 1
            continue

        try:
            size = dup.stat().st_size
            dup.rename(new_name)
            meta = json.dumps({"new_path": str(new_name)})
            log_action("rename", str(dup), size)
            ok += 1
        except Exception as e:
            log.exception("Ошибка переименования %s", dup)
            errors.append((dup, str(e)))
    return ok, errors


def undo_action(
    action_id: int, action: str, path: str, meta_str: str
):  # -> bool:
    """
    Пытается отменить действие.
    Возвращает True, если успешно, иначе False.
    """
    if not meta_str:
        return False

    try:
        meta = json.loads(meta_str)
    except json.JSONDecodeError:
        return False

    original_path = Path(path)

    try:
        if action == "backup":
            backup_path = Path(meta.get("backup_path", ""))
            if not backup_path.exists():
                raise FileNotFoundError("Файл бэкапа не найден.")
            if original_path.exists():
                raise FileExistsError("По исходному пути уже существует файл.")

            original_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(backup_path), str(original_path))

        elif action == "rename":
            new_path = Path(meta.get("new_path", ""))
            if not new_path.exists():
                raise FileNotFoundError("Переименованный файл не найден.")
            if original_path.exists():
                raise FileExistsError("По исходному пути уже существует файл.")

            new_path.rename(original_path)
        else:
            return False

        mark_as_undone(action_id)
        return True

    except Exception as e:
        log.error("Ошибка отмены действия %s: %s", action, e)
        raise e


def remove_empty_dirs(root: Path):
    """Рекурсивно удаляет пустые директории."""
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        if not dirnames and not filenames:
            try:
                os.rmdir(dirpath)
                log.info("Удалена пустая папка: %s", dirpath)
            except OSError:
                pass


def apply_action_to_group(
    original: Path,
    duplicates: list[Path],
    action: str,
    backup_dir: Path | None = None,
    base_root: Path | None = None,
    dry_run: bool = False,
):  # -> tuple[int, list[tuple[Path, str]]]:
    """
    Применяет действие ко всем дубликатам в группе.
    Возвращает (количество_успешных, список_ошибок).
    """
    ok = 0
    errors: list[tuple[Path, str]] = []

    for dup in duplicates:
        if dup == original:
            continue

        # Проверка, что дубликат не является тем же файлом, что и оригинал (через inode)
        try:
            if os.path.samefile(dup, original):
                continue
        except (OSError, FileNotFoundError):
            pass

        try:
            if action == "delete":
                delete_file(dup, use_trash=False, dry_run=dry_run)
            elif action == "trash":
                delete_file(dup, use_trash=True, dry_run=dry_run)
            elif action == "symlink":
                replace_with_symlink(original, dup, dry_run=dry_run)
            elif action == "hardlink":
                replace_with_hardlink(original, dup, dry_run=dry_run)
            elif action == "backup" and backup_dir and base_root:
                move_to_backup(backup_dir, dup, base_root, dry_run=dry_run)
            else:
                raise ValueError(f"Неизвестное действие: {action}")
            ok += 1
        except Exception as e:
            log.exception("Ошибка при обработке %s", dup)
            errors.append((dup, str(e)))

    return ok, errors
