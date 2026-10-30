"""Тесты для генерации отчетов (core/reports.py)."""

import datetime
from pathlib import Path
import pytest

from core.session import Session, DuplicateGroup, FileEntry
from core.reports import export_txt, export_html, export_deletion_list

# ==========================================
# Фикстуры
# ==========================================


@pytest.fixture
def sample_session():
    """Создает тестовую сессию с двумя группами файлов."""
    # Время для тестов (1 января 2023, 12:00)
    mtime = datetime.datetime(2023, 1, 1, 12, 0).timestamp()

    g1 = DuplicateGroup(
        hash_key="hash1",
        size=1024,
        is_empty_group=False,
        files=[
            FileEntry(
                path="C:/test/file1.txt",
                size=1024,
                mtime=mtime,
                is_original=True,
            ),
            FileEntry(
                path="C:/test/file2.txt",
                size=1024,
                mtime=mtime,
                is_original=False,
            ),
        ],
    )

    g2 = DuplicateGroup(
        hash_key="hash2",
        size=0,
        is_empty_group=True,
        files=[
            FileEntry(
                path="C:/test/<script>empty1.txt",
                size=0,
                mtime=mtime,
                is_original=True,
            ),
            FileEntry(
                path="C:/test/empty2.txt",
                size=0,
                mtime=mtime,
                is_original=False,
            ),
        ],
    )

    return Session(
        version=1,
        created_at="2023-01-01T12:00:00",
        created_by="TestUser",
        root_scan_dir="C:/test",
        filters={"ext": [".txt"]},
        groups=[g1, g2],
    )


# ==========================================
# 1. Тесты для export_txt
# ==========================================


def test_export_txt(sample_session, tmp_path):
    """Проверяет экспорт в текстовый формат."""
    report_path = tmp_path / "report.txt"
    export_txt(sample_session, report_path)

    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")

    # Проверяем заголовки
    assert "Отчёт о дубликатах файлов" in content
    assert "Автор: TestUser" in content
    assert "Директория: C:/test" in content

    # Проверяем группы и пометки
    assert "Группа #1 — 2 файлов, 1.0 KB каждый" in content
    assert "Группа #2 [ПУСТЫЕ] — 2 файлов, 0.0 B каждый" in content

    # Проверяем звездочки оригиналов (★)
    assert "  ★ C:/test/file1.txt" in content
    assert "    C:/test/file2.txt" in content
    assert (
        "  ★ C:/test/<script>empty1.txt" in content
    )  # В txt экранирование не нужно


# ==========================================
# 2. Тесты для export_html
# ==========================================


def test_export_html(sample_session, tmp_path):
    """Проверяет экспорт в HTML и экранирование спецсимволов."""
    report_path = tmp_path / "report.html"
    export_html(sample_session, report_path)

    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")

    # Проверяем базовую структуру
    assert "<!DOCTYPE html>" in content
    assert "<title>Отчёт о дубликатах</title>" in content

    # Проверяем заголовки
    assert "Дата:</b> 2023-01-01T12:00:00" in content
    assert "Автор:</b> TestUser" in content

    # Проверяем группы
    assert "Группа #1 <small>" in content
    assert "Группа #2 🗂️ ПУСТЫЕ <small>" in content

    # Проверяем звездочки (★)
    assert "<td align='center'>★</td>" in content

    # Проверяем ДАТУ ИЗМЕНЕНИЯ (должна быть отформатирована как YYYY-MM-DD HH:MM)
    assert "<td>2023-01-01 12:00</td>" in content

    # Проверяем ЭКРАНИРОВАНИЕ (<script> должен стать &lt;script&gt;)
    assert "C:/test/&lt;script&gt;empty1.txt" in content
    assert (
        "C:/test/<script>empty1.txt" not in content
    )  # В чистом виде быть не должно


# ==========================================
# 3. Тесты для export_deletion_list
# ==========================================


def test_export_deletion_list(sample_session, tmp_path):
    """Проверяет создание списка только для удаления (без оригиналов)."""
    report_path = tmp_path / "delete.txt"
    export_deletion_list(sample_session, report_path)

    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    lines = content.strip().split("\n")

    # В списке должно быть ровно 2 файла (не-оригиналы)
    assert len(lines) == 2

    # Проверяем, что оригиналов там нет
    assert "C:/test/file2.txt" in lines
    assert "C:/test/empty2.txt" in lines

    assert "C:/test/file1.txt" not in lines
    assert "C:/test/<script>empty1.txt" not in lines


# ==========================================
# 4. Тесты на пустую сессию (граничные случаи)
# ==========================================


def test_export_empty_session(tmp_path):
    """Проверяет работу функций на пустой сессии (без групп)."""
    empty_session = Session(groups=[])

    # TXT
    txt_path = tmp_path / "empty.txt"
    export_txt(empty_session, txt_path)
    assert "Групп: 0" in txt_path.read_text(encoding="utf-8")

    # HTML
    html_path = tmp_path / "empty.html"
    export_html(empty_session, html_path)
    assert "<b>Групп:</b> 0" in html_path.read_text(encoding="utf-8")

    # Deletion List
    del_path = tmp_path / "empty_del.txt"
    export_deletion_list(empty_session, del_path)
    assert del_path.read_text(encoding="utf-8") == ""
