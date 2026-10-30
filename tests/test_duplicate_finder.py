"""Тесты для алгоритмов поиска дубликатов (core/duplicate_finder.py)."""

import os
import sys
import importlib
import pytest
from pathlib import Path
from PIL import Image, ImageDraw

from core.duplicate_finder import (
    find_duplicates,
    find_by_name,
    find_similar_images,
    find_similar_videos,
    find_audio_duplicates,
    find_zero_fill_files,
    find_links_to_file,
)

# ==========================================
# 1. Поиск точных дубликатов (Хеш)
# ==========================================


def test_find_duplicates_basic(tmp_path):
    f1, f2, f3 = tmp_path / "a.txt", tmp_path / "b.txt", tmp_path / "c.txt"
    f1.write_text("hello")
    f2.write_text("hello")
    f3.write_text("hello")
    res = find_duplicates([f1, f2, f3], use_cache=False)
    assert len(res) == 1
    assert len(list(res.values())[0]) == 3


def test_find_duplicates_include_empty(tmp_path):
    e1, e2 = tmp_path / "e1.txt", tmp_path / "e2.txt"
    e1.touch()
    e2.touch()
    res = find_duplicates([e1, e2], include_empty=True, use_cache=False)
    assert "EMPTY" in res


def test_find_duplicates_stat_error(tmp_path, mocker):
    """Покрывает строку 105-106 (except OSError при stat)."""
    f1 = tmp_path / "a.txt"
    f1.write_text("data")
    mocker.patch("pathlib.Path.stat", side_effect=OSError("Access denied"))
    res = find_duplicates([f1], use_cache=False)
    assert res == {}


def test_find_duplicates_full_hash_cache_hit(tmp_path, mocker):
    """Покрывает строки 61-62 (кэш срабатывает на этапе ПОЛНОГО хеша)."""
    f1, f2 = tmp_path / "a.txt", tmp_path / "b.txt"
    f1.write_text("12345")
    f2.write_text("abcde")  # Одинаковый размер

    mock_cache = mocker.MagicMock()
    mock_cache.get.return_value = "cached_hash"
    mocker.patch("core.duplicate_finder.HashCache", return_value=mock_cache)

    calls = []

    def cb(stage, done, total):
        calls.append(stage)

    # Быстрый хеш должен вернуть одинаковые хеши, чтобы файлы прошли дальше
    mocker.patch("core.duplicate_finder.hash_file", return_value="quick_hash")

    res = find_duplicates([f1, f2], use_cache=True, progress_cb=cb)
    assert "cached_hash" in res
    assert "full_hash" in calls


def test_find_duplicates_cache_put_full_hash(tmp_path, mocker):
    """Покрывает строку 78 (cache.put на этапе полного хеша)."""
    f1, f2 = tmp_path / "a.txt", tmp_path / "b.txt"
    f1.write_text("12345")
    f2.write_text("abcde")

    mock_cache = mocker.MagicMock()
    mock_cache.get.return_value = None  # Кэш пуст
    mocker.patch("core.duplicate_finder.HashCache", return_value=mock_cache)

    mocker.patch("core.duplicate_finder.hash_file", return_value="new_hash")

    find_duplicates([f1, f2], use_cache=True)
    assert mock_cache.put.called


def test_find_duplicates_no_candidates_after_quick(tmp_path, mocker):
    """Покрывает строку 188 (return после быстрого хеша, если нет совпадений)."""
    f1, f2 = tmp_path / "a.txt", tmp_path / "b.txt"
    f1.write_text("12345")
    f2.write_text("abcde")  # Одинаковый размер

    def mock_hash(path, **kwargs):
        if "a.txt" in str(path):
            return "hash_a"
        return "hash_b"

    mocker.patch("core.duplicate_finder.hash_file", side_effect=mock_hash)
    res = find_duplicates([f1, f2], use_cache=False)
    assert res == {}


# ==========================================
# 2. Поиск по имени
# ==========================================


def test_find_by_name(tmp_path):
    f1 = tmp_path / "dir1"
    f2 = tmp_path / "dir2"
    f1.mkdir()
    f2.mkdir()
    p1 = f1 / "same_name.txt"
    p2 = f2 / "same_name.txt"
    p1.write_text("1")
    p2.write_text("2")
    res = find_by_name([p1, p2])
    assert "same_name.txt" in res


def test_find_by_name_empty():
    assert find_by_name([]) == {}


# ==========================================
# 3. Поиск нулевых файлов (Мусор)
# ==========================================


def test_find_zero_fill_files(tmp_path):
    zero1 = tmp_path / "z1.bin"
    zero2 = tmp_path / "z2.bin"
    for f in [zero1, zero2]:
        with open(f, "wb") as fh:
            fh.write(b"\0" * (1024 * 1024 + 1))

    res = find_zero_fill_files([zero1, zero2])
    assert "ZERO_FILL" in res


def test_find_zero_fill_files_stat_error(tmp_path, mocker):
    """Покрывает строку 295 (except OSError)."""
    f1 = tmp_path / "a.bin"
    f1.write_text("data")
    mocker.patch.object(Path, "stat", side_effect=OSError("Disk error"))
    res = find_zero_fill_files([f1])
    assert res == {}


# ==========================================
# 4. Поиск ссылок (Симлинки и Хардлинки)
# ==========================================


def test_find_links_to_file(tmp_path, mocker):
    target = tmp_path / "target.txt"
    target.write_text("data")
    other = tmp_path / "other.txt"
    other.write_text("data")

    def mock_samefile(p1, p2):
        return str(p1).endswith("target.txt") or str(p2).endswith("target.txt")

    mocker.patch("os.path.samefile", side_effect=mock_samefile)
    res = find_links_to_file(target, [other])
    assert "LINKS" in res


def test_find_links_to_file_error(tmp_path, mocker):
    """Покрывает строку 301 (except OSError / FileNotFoundError)."""
    target = tmp_path / "target.txt"
    target.write_text("data")
    other = tmp_path / "other.txt"
    other.write_text("data")

    mocker.patch("os.path.samefile", side_effect=OSError("Link error"))
    res = find_links_to_file(target, [other])
    assert res == {}


# ==========================================
# 5. Поиск похожих фото (pHash)
# ==========================================


def test_find_similar_images(tmp_path):
    img1 = Image.new("RGB", (100, 100), color="white")
    ImageDraw.Draw(img1).line((0, 0, 100, 100), fill="black", width=5)
    img1.save(tmp_path / "img1.png")

    img2 = Image.new("RGB", (100, 100), color="white")
    ImageDraw.Draw(img2).line((0, 0, 100, 100), fill="black", width=6)
    img2.save(tmp_path / "img2.png")

    img3 = Image.new("RGB", (100, 100), color="white")
    ImageDraw.Draw(img3).ellipse((20, 20, 80, 80), fill="black")
    img3.save(tmp_path / "img3.png")

    files = [
        tmp_path / "img1.png",
        tmp_path / "img2.png",
        tmp_path / "img3.png",
    ]
    res = find_similar_images(files, threshold=8)
    assert len(res) == 1
    assert len(list(res.values())[0]) == 2


def test_find_similar_images_error_open(tmp_path, mocker):
    """Покрывает строку 223 (except Exception при Image.open)."""
    bad_file = tmp_path / "bad.png"
    bad_file.touch()
    # Явно патчим Image.open именно в модуле
    mocker.patch(
        "core.duplicate_finder.Image.open", side_effect=Exception("PIL error")
    )
    res = find_similar_images([bad_file])
    assert res == {}


def test_find_similar_images_processed_continue(tmp_path):
    """Покрывает строки 231-232 (if p2 in processed: continue)."""
    img = Image.new("RGB", (100, 100), color="white")
    ImageDraw.Draw(img).line((0, 0, 100, 100), fill="black", width=5)

    f1, f2, f3 = (
        tmp_path / "img1.png",
        tmp_path / "img2.png",
        tmp_path / "img3.png",
    )
    for f in [f1, f2, f3]:
        img.save(f)

    res = find_similar_images([f1, f2, f3], threshold=8)
    assert len(list(res.values())[0]) == 3


# ==========================================
# 6. Поиск похожих видео (Первый кадр)
# ==========================================


def test_find_similar_videos_no_cv2(mocker):
    mocker.patch("core.duplicate_finder.HAS_CV2", False)
    assert find_similar_videos([Path("dummy.mp4")]) == {}


def test_find_similar_videos_with_cv2(mocker):
    mocker.patch("core.duplicate_finder.HAS_CV2", True)
    mock_cap = mocker.MagicMock()
    mock_cap.read.return_value = (True, "fake_frame")
    mocker.patch("cv2.VideoCapture", return_value=mock_cap)
    mocker.patch("cv2.cvtColor", return_value="rgb_frame")
    mocker.patch("PIL.Image.fromarray")

    mock_phash = mocker.patch("core.duplicate_finder.imagehash.phash")
    mock_phash.return_value = 100

    res = find_similar_videos([Path("vid1.mp4"), Path("vid2.mp4")])
    assert len(res) == 1


def test_find_similar_videos_error(mocker):
    """Покрывает строку 256 (except Exception при VideoCapture)."""
    mocker.patch("core.duplicate_finder.HAS_CV2", True)
    mocker.patch("cv2.VideoCapture", side_effect=Exception("Video error"))
    res = find_similar_videos([Path("vid.mp4")])
    assert res == {}


def test_import_cv2_fail(mocker):
    """Покрывает except ImportError при импорте cv2."""
    mocker.patch.dict(sys.modules, {"cv2": None})
    import core.duplicate_finder

    importlib.reload(core.duplicate_finder)
    assert core.duplicate_finder.HAS_CV2 is False
    mocker.stopall()
    importlib.reload(core.duplicate_finder)


# ==========================================
# 7. Поиск аудио по тегам
# ==========================================


def test_find_audio_duplicates(tmp_path, mocker):
    f1 = tmp_path / "song1.mp3"
    f2 = tmp_path / "song2.mp3"
    f1.touch()
    f2.touch()

    def mock_mutagen_file(path, easy=True):
        return {"artist": ["Linkin Park"], "title": ["Numb"]}

    mocker.patch(
        "core.duplicate_finder.mutagen.File", side_effect=mock_mutagen_file
    )
    res = find_audio_duplicates([f1, f2])
    assert "linkin park - numb" in res


def test_find_audio_duplicates_wrong_ext(tmp_path):
    """Покрывает строку 273 (если расширение не аудио)."""
    bad_file = tmp_path / "file.txt"
    bad_file.touch()
    res = find_audio_duplicates([bad_file])
    assert res == {}


def test_find_audio_duplicates_error(mocker):
    """Покрывает строки 277-278 (except Exception при чтении тегов)."""
    mocker.patch(
        "core.duplicate_finder.mutagen.File",
        side_effect=Exception("Read error"),
    )
    res = find_audio_duplicates([Path("bad.mp3")])
    assert len(res) == 0


def test_on_chunk_progress_callback_trigger(tmp_path, mocker):
    """
    Покрывает строку 78: progress_cb внутри on_chunk.
    Мы вручную вызываем коллбэк с большим значением,
    чтобы сработало условие `done_ref[0] % (1 << 20) < n`.
    """
    f1, f2 = tmp_path / "a.txt", tmp_path / "b.txt"
    f1.write_text("12345")
    f2.write_text("12345")

    # Мокаем hash_file, чтобы он вызывал переданный ему progress_cb (on_chunk)
    def mock_hash_file(path, quick, progress_cb):
        if progress_cb:
            progress_cb(2 * 1024 * 1024)  # Вызываем с 2 МБ
        return "hash123"

    mocker.patch("core.duplicate_finder.hash_file", side_effect=mock_hash_file)

    calls = []

    def cb(stage, done, total):
        calls.append(stage)

    find_duplicates([f1, f2], use_cache=False, progress_cb=cb)
    assert "quick_hash" in calls


def test_find_links_to_missing_file(tmp_path):
    """
    Покрывает строку 295:
    Сценарий, когда целевой файл не существует, функция сразу возвращает пустой словарь.
    """
    ghost_file = tmp_path / "ghost.txt"
    # Мы специально НЕ создаем файл
    res = find_links_to_file(ghost_file, [])
    assert res == {}
