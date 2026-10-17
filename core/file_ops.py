"""Операции с файлами: удаление, ссылки, перемещение, очистка."""

import logging
import os
import shutil
import psutil
from pathlib import Path

from utils.history import log_action

log = logging.getLogger(__name__)


def remove_empty_dirs(root: Path):
    """Рекурсивно удаляет пустые директории."""
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        if not dirnames and not filenames:
            try:
                os.rmdir(dirpath)
                log.info("Удалена пустая папка: %s", dirpath)
            except OSError:
                pass


def is_file_open(path: Path) -> bool:
    """Проверяет, открыт ли файл каким-либо процессом."""
    for proc in psutil.process_iter(["open_files"]):
        try:
            if proc.info["open_files"]:
                for f in proc.info["open_files"]:
                    if Path(f.path).resolve() == path.resolve():
                        return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def delete_file(
    path: Path, use_trash: bool = False, dry_run: bool = False
) -> None:
    """Удаляет файл. При use_trash=True — в корзину (send2trash)."""
    if dry_run:
        log.info("[DRY-RUN] Удалить: %s", path)
        return

    size = path.stat().st_size
    if use_trash:
        from send2trash import send2trash

        send2trash(str(path))
        log.info("В корзину: %s", path)
        log_action("delete_trash", str(path), size)
    else:
        os.remove(path)
        log.info("Удалён: %s", path)
        log_action("delete_hard", str(path), size)


def replace_with_symlink(
    original: Path, duplicate: Path, dry_run: bool = False
) -> None:
    """Безопасно заменяет duplicate символьной ссылкой на original."""
    if dry_run:
        log.info("[DRY-RUN] Симлинк: %s -> %s", duplicate, original)
        return

    if not original.exists():
        raise FileNotFoundError(f"Оригинал не найден: {original}")

    size = duplicate.stat().st_size

    try:
        target = original.resolve()
        # Проверка, чтобы не создать ссылку на самого себя
        if duplicate.resolve() == target:
            raise ValueError(
                "Дубликат и оригинал указывают на один и тот же файл"
            )
    except Exception as e:
        log.error("Ошибка разрешения путей: %s", e)
        raise

    # 1. Создаем временный симлинк, чтобы не потерять файл при ошибке
    tmp_name = duplicate.with_name(duplicate.name + ".tmp_symlink")
    if tmp_name.exists() or tmp_name.is_symlink():
        tmp_name.unlink()

    try:
        # В Windows для симлинков нужны права администратора или режим разработчика
        os.symlink(target, tmp_name)
    except OSError as e:
        log.error("Не удалось создать симлинк: %s", e)
        raise OSError(
            f"Ошибка симлинка (возможно, нет прав администратора): {e}"
        )

    # 2. Если симлинк создан успешно, удаляем старый файл и переименовываем временный
    try:
        duplicate.unlink()
        tmp_name.rename(duplicate)
        log.info("Симлинк: %s → %s", duplicate, target)
        log_action("symlink", str(duplicate), size)
    except Exception as e:
        if tmp_name.exists() or tmp_name.is_symlink():
            tmp_name.unlink()  # Откатываем временный файл
        raise OSError(f"Не удалось завершить замену: {e}")


def replace_with_hardlink(
    original: Path, duplicate: Path, dry_run: bool = False
) -> None:
    """Заменяет duplicate жесткой ссылкой на original (безопасно)."""
    if dry_run:
        log.info("[DRY-RUN] Хардлинк: %s -> %s", duplicate, original)
        return

    if not original.exists():
        raise FileNotFoundError(f"Оригинал не найден: {original}")

    size = duplicate.stat().st_size
    target = original.resolve()

    # Создаем временный хардлинк рядом с дубликатом
    tmp_name = duplicate.with_name(duplicate.name + ".tmp_hardlink")
    if tmp_name.exists():
        tmp_name.unlink()

    try:
        os.link(target, tmp_name)
    except OSError as e:
        log.error("Не удалось создать хардлинк: %s", e)
        raise OSError(
            f"Ошибка хардлинка (возможно, файлы на разных дисках или нет прав): {e}"
        )

    # Если хардлинк создан, удаляем старый дубликат и переименовываем временный
    try:
        duplicate.unlink()
        tmp_name.rename(duplicate)
        log.info("Хардлинк: %s → %s", duplicate, target)
        log_action("hardlink", str(duplicate), size)
    except Exception as e:
        if tmp_name.exists():
            tmp_name.unlink()  # Откатываем временный файл
        raise OSError(f"Не удалось завершить замену: {e}")


def move_to_backup(
    backup_dir: Path, duplicate: Path, base_root: Path, dry_run: bool = False
) -> None:
    """Перемещает файл в папку бэкапа с сохранением структуры."""
    if dry_run:
        log.info("[DRY-RUN] В бэкап: %s", duplicate)
        return

    size = duplicate.stat().st_size
    try:
        rel_path = duplicate.relative_to(base_root)
    except ValueError:
        rel_path = Path(duplicate.name)

    dest = backup_dir / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(duplicate), str(dest))
    log.info("Перемещено в бэкап: %s → %s", duplicate, dest)
    log_action("backup", str(duplicate), size)


def rename_duplicates(
    original: Path, duplicates: list[Path], dry_run: bool = False
) -> tuple[int, list[tuple[Path, str]]]:
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
            log_action("rename", str(dup), size)
            ok += 1
        except Exception as e:
            log.exception("Ошибка переименования %s", dup)
            errors.append((dup, str(e)))
    return ok, errors


def apply_action_to_group(
    original: Path,
    duplicates: list[Path],
    action: str,
    backup_dir: Path | None = None,
    base_root: Path | None = None,
    dry_run: bool = False,
) -> tuple[int, list[tuple[Path, str]]]:
    """Применяет действие ко всем дубликатам в группе."""
    ok = 0
    errors: list[tuple[Path, str]] = []

    # Получаем абсолютные пути для проверки совпадений
    try:
        orig_resolved = original.resolve()
    except Exception:
        orig_resolved = original

    for dup in duplicates:
        try:
            dup_resolved = dup.resolve()
        except Exception:
            dup_resolved = dup

        # ИСПРАВЛЕНИЕ: Если пути ведут к одному и тому же файлу, пропускаем
        if dup == original or dup_resolved == orig_resolved:
            continue

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
