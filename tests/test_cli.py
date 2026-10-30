"""Тесты для CLI-режима (cli/cli.py)."""

import sys
from pathlib import Path
import pytest

from cli.cli import run

# ==========================================
# Фикстуры
# ==========================================


@pytest.fixture
def mock_cli_env(mocker, tmp_path):
    """Базовая настройка моков для CLI."""
    # Создаем фейковую директорию
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()

    # Мокаем сканер, чтобы он не ходил по реальному диску
    mocker.patch(
        "cli.cli.scan_directory", return_value=[Path("a.txt"), Path("b.txt")]
    )

    # Мокаем парсинг размеров для предсказуемости
    mocker.patch(
        "cli.cli.parse_size_string",
        side_effect=lambda x: int(x) if str(x).isdigit() else 1024,
    )

    return test_dir


# ==========================================
# 1. Базовые проверки аргументов
# ==========================================


def test_cli_invalid_directory(capsys):
    """Проверяет ветку, когда передана несуществующая папка."""
    res = run(["C:/invalid_path_999"])
    assert res == 2

    captured = capsys.readouterr()
    assert "Ошибка: не директория" in captured.err


def test_cli_no_duplicates(mock_cli_env, mocker, capsys):
    """Проверяет ветку, когда дубликаты не найдены."""
    mocker.patch("cli.cli.find_duplicates", return_value={})

    res = run([str(mock_cli_env)])
    assert res == 0
    captured = capsys.readouterr()
    assert "Дубликаты не найдены" in captured.out


def test_cli_no_duplicates_above_threshold(mock_cli_env, mocker, capsys):
    """Проверяет ветку фильтрации по экономии (файлы найдены, но они мелкие)."""
    mocker.patch(
        "cli.cli.find_duplicates",
        return_value={"hash": [Path("a.txt"), Path("b.txt")]},
    )
    # Устанавливаем огромный порог экономии
    res = run([str(mock_cli_env), "--min-savings", "999999999"])

    assert res == 0
    captured = capsys.readouterr()
    assert "Дубликаты не найдены (или все ниже порога)" in captured.out


# ==========================================
# 2. Вывод результатов и прогресс
# ==========================================


def test_cli_finds_duplicates_and_prints(
    mock_cli_env, mocker, capsys, tmp_path
):
    """Проверяет основной сценарий вывода найденных дубликатов."""
    # Создаем реальные файлы, чтобы stat() работал
    f1 = tmp_path / "file1.txt"
    f2 = tmp_path / "file2.txt"
    f1.write_text("hello")
    f2.write_text("hello")

    # Мокаем find_duplicates, чтобы он вызвал коллбэк и вернул наши файлы
    def mock_find(files, progress_cb, **kwargs):
        if progress_cb:
            progress_cb("quick_hash", 10, 10)  # Покрываем коллбэк вывода
        return {"hash123": [f1, f2]}

    mocker.patch("cli.cli.find_duplicates", side_effect=mock_find)

    res = run([str(mock_cli_env)])
    assert res == 0

    captured = capsys.readouterr()
    assert "quick_hash: 100%" in captured.out
    assert "Группа #1 (2 файлов" in captured.out
    assert "★" in captured.out


# ==========================================
# 3. Обработка ошибок доступа (OSError)
# ==========================================


def test_cli_oserror_on_stat(mock_cli_env, mocker):
    """Проверяет обработку ошибки, если файл нельзя прочитать (stat падает)."""
    mocker.patch(
        "cli.cli.find_duplicates",
        return_value={"hash": [Path("ghost.txt"), Path("ghost2.txt")]},
    )
    mocker.patch("pathlib.Path.stat", side_effect=OSError("Access denied"))

    res = run([str(mock_cli_env)])
    assert res == 0


# ==========================================
# 4. Сохранение отчетов
# ==========================================


def test_cli_export_txt(mock_cli_env, mocker, tmp_path):
    """Проверяет сохранение отчета в TXT."""
    f1, f2 = tmp_path / "f1.txt", tmp_path / "f2.txt"
    f1.write_text("data")
    f2.write_text("data")

    mocker.patch("cli.cli.find_duplicates", return_value={"hash": [f1, f2]})

    report_file = tmp_path / "report.txt"
    mock_export = mocker.patch("cli.cli.export_txt")
    mock_build_session = mocker.patch("cli.cli.build_session_from_groups")

    res = run([str(mock_cli_env), "--report", str(report_file)])

    assert res == 0
    assert mock_build_session.called
    assert mock_export.called


def test_cli_export_html(mock_cli_env, mocker, tmp_path):
    """Проверяет сохранение отчета в HTML."""
    f1, f2 = tmp_path / "f1.txt", tmp_path / "f2.txt"
    f1.write_text("data")
    f2.write_text("data")

    mocker.patch("cli.cli.find_duplicates", return_value={"hash": [f1, f2]})

    report_file = tmp_path / "report.html"
    mock_export = mocker.patch("cli.cli.export_html")

    res = run([str(mock_cli_env), "--report", str(report_file)])

    assert res == 0
    assert mock_export.called


# ==========================================
# 5. Применение действий (Удаление)
# ==========================================


def test_cli_apply_action_with_yes_flag(
    mock_cli_env, mocker, tmp_path, capsys
):
    """Проверяет удаление с флагом --yes (без запроса ввода)."""
    f1, f2 = tmp_path / "f1.txt", tmp_path / "f2.txt"
    f1.write_text("data")
    f2.write_text("data")

    mocker.patch("cli.cli.find_duplicates", return_value={"hash": [f1, f2]})

    # Мокаем функцию применения действия
    mock_apply = mocker.patch(
        "cli.cli.apply_action_to_group", return_value=(1, [])
    )

    res = run([str(mock_cli_env), "--apply", "delete", "--yes"])

    assert res == 0
    assert mock_apply.called

    captured = capsys.readouterr()
    assert "Обработано: 1, ошибок: 0" in captured.out


def test_cli_apply_action_cancel(
    mock_cli_env, mocker, tmp_path, monkeypatch, capsys
):
    """Проверяет отмену удаления пользователем (ввод 'no')."""
    f1, f2 = tmp_path / "f1.txt", tmp_path / "f2.txt"
    f1.write_text("data")
    f2.write_text("data")

    mocker.patch("cli.cli.find_duplicates", return_value={"hash": [f1, f2]})

    # Имитируем ввод пользователя "no"
    monkeypatch.setattr("builtins.input", lambda _: "no")

    res = run([str(mock_cli_env), "--apply", "delete"])
    assert res == 0

    captured = capsys.readouterr()
    assert "Отменено." in captured.out


def test_cli_apply_action_confirm_yes(
    mock_cli_env, mocker, tmp_path, monkeypatch
):
    """Проверяет удаление с подтверждением ввода 'yes'."""
    f1, f2 = tmp_path / "f1.txt", tmp_path / "f2.txt"
    f1.write_text("data")
    f2.write_text("data")

    mocker.patch("cli.cli.find_duplicates", return_value={"hash": [f1, f2]})

    # Имитируем ввод пользователя "yes"
    monkeypatch.setattr("builtins.input", lambda _: "yes")
    mock_apply = mocker.patch(
        "cli.cli.apply_action_to_group", return_value=(1, ["err"])
    )

    res = run([str(mock_cli_env), "--apply", "delete"])
    assert res == 0
    assert mock_apply.called
