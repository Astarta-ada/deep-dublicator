"""Тесты для глобальной конфигурации (utils/config.py)."""

import sys
import importlib
import pytest
from pathlib import Path
from unittest.mock import MagicMock

# ==========================================
# 1. Тесты констант (без моков)
# ==========================================


def test_constants_values():
    """Проверяет базовые значения констант."""
    from utils.config import (
        APP_NAME,
        ORG_NAME,
        QUICK_HASH_BYTES,
        CHUNK_SIZE,
        EMPTY_FILE_HASH,
        SESSION_EXT,
        SESSION_VERSION,
    )

    assert APP_NAME == "Duplicate Finder"
    # ИСПРАВЛЕНО: Твое новое значение
    assert ORG_NAME == "Aleksander Diuzhev"
    assert QUICK_HASH_BYTES == 65536
    assert CHUNK_SIZE == 65536
    assert EMPTY_FILE_HASH == "EMPTY"
    assert SESSION_EXT == ".dupsession.json"
    assert SESSION_VERSION == 1


def test_default_exclude_dirs():
    """Проверяет, что в исключениях есть системные папки."""
    from utils.config import DEFAULT_EXCLUDE_DIRS

    assert ".git" in DEFAULT_EXCLUDE_DIRS
    assert "__pycache__" in DEFAULT_EXCLUDE_DIRS
    assert "node_modules" in DEFAULT_EXCLUDE_DIRS
    assert ".venv" in DEFAULT_EXCLUDE_DIRS


# ==========================================
# 2. Тесты путей (с моком QStandardPaths)
# ==========================================


@pytest.fixture
def reload_config(mocker, tmp_path):
    """Перезагружает config с замоканными путями."""
    # ИСПРАВЛЕНО: Мокаем метод writableLocation у реального класса в PySide6,
    # чтобы при перезагрузке модуля мок не затирался
    mocker.patch(
        "PySide6.QtCore.QStandardPaths.writableLocation",
        return_value=str(tmp_path),
    )

    # Перезагружаем модуль, чтобы применились новые пути
    import utils.config

    importlib.reload(utils.config)

    yield utils.config

    # После теста возвращаем всё как было
    mocker.stopall()
    importlib.reload(utils.config)


def test_paths_created(reload_config, tmp_path):
    """Проверяет, что папки для данных и логов создаются."""
    config = reload_config

    # Папка для данных должна существовать
    assert config.APP_DATA_DIR.exists()
    # Папка для логов должна существовать
    assert config.LOG_DIR.exists()

    # Проверяем, что пути указывают во временную папку
    assert str(tmp_path) in str(config.APP_DATA_DIR)
    assert str(tmp_path) in str(config.LOG_DIR)

    # Проверяем пути к файлам
    assert config.HASH_CACHE_DB.name == "hashes.db"
    assert config.AUTOSAVE_FILE.name == "autosave.dupsession.json"
    assert config.LOG_FILE.name == "app.log"


# ==========================================
# 3. Тесты get_resource_path (Обычный режим)
# ==========================================


def test_get_resource_path_normal(reload_config, mocker):
    """Проверяет поиск ресурса в обычном режиме (не EXE)."""
    config = reload_config

    # Имитируем, что мы не в скомпилированном EXE
    mocker.patch.object(sys, "frozen", False, create=True)

    path = config.get_resource_path("assets/icon.png")

    # Путь должен быть относительно PROJECT_ROOT
    assert path == config.PROJECT_ROOT / "assets" / "icon.png"


# ==========================================
# 4. Тесты get_resource_path (Режим EXE)
# ==========================================


def test_get_resource_path_frozen_onedir(reload_config, mocker):
    """Проверяет путь ресурсов в режиме --onedir (sys._MEIPASS отсутствует)."""
    config = reload_config

    # Имитируем EXE без _MEIPASS (режим --onedir)
    mocker.patch.object(sys, "frozen", True, create=True)
    mocker.patch.object(
        sys, "executable", "C:/App/DeepDublicator.exe", create=True
    )
    if hasattr(sys, "_MEIPASS"):
        mocker.patch.object(sys, "_MEIPASS", None, create=True)

    # Перезагружаем модуль, чтобы он пересчитал PROJECT_ROOT
    importlib.reload(config)

    path = config.get_resource_path("assets/icon.png")

    # В режиме onedir ресурсы лежат рядом с EXE
    assert path == Path("C:/App") / "assets" / "icon.png"


def test_get_resource_path_frozen_onefile(reload_config, mocker):
    """Проверяет путь ресурсов в режиме --onefile (sys._MEIPASS есть)."""
    config = reload_config

    # Имитируем EXE с _MEIPASS (режим --onefile)
    mocker.patch.object(sys, "frozen", True, create=True)
    mocker.patch.object(sys, "_MEIPASS", "C:/Temp/_MEI12345", create=True)

    # Перезагружаем модуль
    importlib.reload(config)

    path = config.get_resource_path("assets/icon.png")

    # В режиме onefile ресурсы распакованы во временную папку _MEIPASS
    assert path == Path("C:/Temp/_MEI12345") / "assets" / "icon.png"
