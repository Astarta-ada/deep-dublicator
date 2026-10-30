"""Тесты для сериализации сессий (core/session.py)."""

import json
import getpass
from pathlib import Path
import pytest
from unittest.mock import MagicMock

from core.session import (
    FileEntry,
    DuplicateGroup,
    Session,
    save_session,
    load_session,
    build_session_from_groups,
)
from utils.config import SESSION_VERSION, SESSION_EXT

# ==========================================
# Фикстуры
# ==========================================


@pytest.fixture
def sample_session():
    """Создает тестовую сессию."""
    f1 = FileEntry(
        path="C:/file1.txt", size=100, mtime=1600000000.0, is_original=True
    )
    f2 = FileEntry(
        path="C:/file2.txt", size=100, mtime=1600000000.0, is_original=False
    )

    g1 = DuplicateGroup(
        hash_key="hash1", size=100, files=[f1, f2], is_empty_group=False
    )

    return Session(
        version=SESSION_VERSION,
        created_at="2023-01-01T12:00:00",
        created_by="TestUser",
        root_scan_dir="C:/scan",
        filters={"ext": [".txt"]},
        groups=[g1],
    )


# ==========================================
# 1. Тесты для to_dict / from_dict
# ==========================================


def test_session_to_dict(sample_session):
    """Проверяет сериализацию в словарь."""
    data = sample_session.to_dict()

    assert data["version"] == SESSION_VERSION
    assert data["created_by"] == "TestUser"
    assert len(data["groups"]) == 1
    assert data["groups"][0]["hash_key"] == "hash1"
    assert len(data["groups"][0]["files"]) == 2
    assert data["groups"][0]["files"][0]["is_original"] is True


def test_session_from_dict_valid(sample_session):
    """Проверяет десериализацию из словаря."""
    data = sample_session.to_dict()
    restored = Session.from_dict(data)

    assert restored.version == sample_session.version
    assert restored.created_by == sample_session.created_by
    assert len(restored.groups) == 1
    assert restored.groups[0].files[0].path == "C:/file1.txt"


def test_session_from_dict_incompatible_version():
    """Проверяет выброс ошибки при несовпадении версии."""
    data = {"version": 999}  # Заведомо неверная версия

    with pytest.raises(ValueError, match="Несовместимая версия сессии"):
        Session.from_dict(data)


def test_session_from_dict_missing_optional_keys():
    """Проверяет десериализацию, если в JSON пропущены необязательные поля."""
    data = {
        "version": SESSION_VERSION,
        "groups": [
            {
                "hash_key": "h1",
                "size": 10,
                "files": [{"path": "f1.txt", "size": 10, "mtime": 0.0}],
                # is_empty_group пропущен
            }
        ],
        # created_at, created_by, root_scan_dir, filters пропущены
    }

    restored = Session.from_dict(data)
    assert restored.created_at == ""
    assert restored.filters == {}
    assert restored.groups[0].is_empty_group is False


# ==========================================
# 2. Тесты для save_session / load_session
# ==========================================


def test_save_session_with_extension(sample_session, tmp_path):
    """Проверяет сохранение, когда путь уже содержит расширение."""
    file_path = tmp_path / f"session{SESSION_EXT}"
    save_session(sample_session, file_path)

    assert file_path.exists()
    assert file_path.name == f"session{SESSION_EXT}"


def test_save_session_without_extension(sample_session, tmp_path):
    """Проверяет сохранение, когда путь БЕЗ расширения (оно должно добавиться)."""
    file_path = tmp_path / "my_session"
    save_session(sample_session, file_path)

    expected_path = tmp_path / f"my_session{SESSION_EXT}"
    assert expected_path.exists()
    assert not file_path.exists()  # Исходный путь не должен создаться


def test_load_session(sample_session, tmp_path):
    """Проверяет загрузку сессии из файла."""
    file_path = tmp_path / "test.dupsession.json"

    # Сначала сохраняем
    save_session(sample_session, file_path)

    # Потом загружаем
    loaded = load_session(file_path)

    assert loaded.created_by == sample_session.created_by
    assert loaded.groups[0].files[0].is_original is True


# ==========================================
# 3. Тесты для build_session_from_groups
# ==========================================


def test_build_session_success(mocker, tmp_path):
    """Проверяет сборку сессии из готовых групп (счастливый путь)."""
    # Создаем реальные файлы, чтобы stat() работал корректно
    f1 = tmp_path / "file1.txt"
    f2 = tmp_path / "file2.txt"
    e1 = tmp_path / "empty1.txt"
    e2 = tmp_path / "empty2.txt"

    f1.write_text("A" * 100)  # 100 байт
    f2.write_text("A" * 100)  # 100 байт
    e1.touch()  # 0 байт
    e2.touch()  # 0 байт

    mocker.patch("getpass.getuser", return_value="MockUser")

    groups = {"hash1": [f1, f2], "hash_empty": [e1, e2]}

    session = build_session_from_groups(
        groups, root_dir="C:/test", filters={}, empty_hash_keys={"hash_empty"}
    )

    assert session.created_by == "MockUser"
    assert len(session.groups) == 2

    # Проверяем первую группу
    g1 = session.groups[0]
    assert g1.hash_key == "hash1"
    assert g1.files[0].is_original is True
    assert g1.files[1].is_original is False
    assert g1.is_empty_group is False
    assert g1.size == 100

    # Проверяем группу пустых файлов
    g2 = session.groups[1]
    assert g2.is_empty_group is True
    assert g2.files[0].is_empty is True
    assert g2.files[0].size == 0


def test_build_session_custom_created_by(mocker):
    """Проверяет, что явно переданный created_by не перезаписывается."""
    mocker.patch("pathlib.Path.stat")

    session = build_session_from_groups(
        {"h": [Path("f.txt")]},
        root_dir="C:/",
        filters={},
        created_by="CustomUser",
    )
    assert session.created_by == "CustomUser"


def test_build_session_stat_error(mocker):
    """Проверяет пропуск файлов, к которым нет доступа (OSError)."""
    mocker.patch("pathlib.Path.stat", side_effect=OSError("Access denied"))

    groups = {"hash1": [Path("file1.txt"), Path("file2.txt")]}
    session = build_session_from_groups(groups, root_dir="C:/", filters={})

    # Все файлы отвалились на stat, группа не должна создаться
    assert len(session.groups) == 0


def test_build_session_empty_groups():
    """Проверяет сборку на пустом словаре групп."""
    session = build_session_from_groups({}, root_dir="C:/", filters={})
    assert len(session.groups) == 0
