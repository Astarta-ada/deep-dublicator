"""Вычисление хешей файлов с поддержкой прогресса."""

import hashlib
import logging
from pathlib import Path
from typing import Callable, Optional

from utils.config import CHUNK_SIZE, QUICK_HASH_BYTES

log = logging.getLogger(__name__)


def hash_file(
    path: Path,
    algorithm: str = "sha256",
    quick: bool = False,
    quick_bytes: int = QUICK_HASH_BYTES,
    progress_cb: Optional[Callable[[int], None]] = None,
):  # -> Optional[str]:
    """
    Вычисляет хеш файла.

    :param path: Путь к файлу.
    :param algorithm: Алгоритм хеширования (по умолчанию "sha256").
    :param quick: Если True — читает только первые quick_bytes байт (для быстрой проверки).
    :param quick_bytes: Количество байт для быстрого чтения.
    :param progress_cb: Функция обратного вызова, принимает количество прочитанных байт.
    :return: Hex-строка хеша или None в случае ошибки чтения.
    """
    h = hashlib.new(algorithm)
    try:
        with open(path, "rb") as f:
            if quick:
                data = f.read(quick_bytes)
                h.update(data)
                if progress_cb and data:
                    progress_cb(len(data))
            else:
                while chunk := f.read(CHUNK_SIZE):
                    h.update(chunk)
                    if progress_cb:
                        progress_cb(len(chunk))
    except (OSError, PermissionError) as e:
        log.debug("Не удалось прочитать %s: %s", path, e)
        return None
    return h.hexdigest()
