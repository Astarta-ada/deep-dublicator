"""Тесты для вкладки анализа диска (gui/disk_analysis_tab.py)."""

import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtCore import Qt, QPoint, QMimeData, QUrl, QRect
from PySide6.QtGui import (
    QPaintEvent,
    QDropEvent,
    QDragEnterEvent,
    QPixmap,
    QColor,
    QBrush,
    QPainter,
)
from PySide6.QtWidgets import (
    QTreeWidget,
    QMessageBox,
    QTreeWidgetItem,
    QStyleOptionViewItem,
    QStyle,
    QFileDialog,
)

from gui.disk_analysis_tab import (
    TreeItem,
    PercentDelegate,
    TreemapWidget,
    HeatmapWidget,
    DiskAnalysisTab,
)

# ==========================================
# 1. Тесты для вспомогательных классов
# ==========================================


def test_tree_item_sorting(qtbot, mocker):
    """Проверяет кастомную сортировку TreeItem."""
    tree = QTreeWidget()
    qtbot.addWidget(tree)

    item1 = TreeItem(tree)
    item1.setText(0, "B")
    item1.setData(1, Qt.UserRole, 200)
    item1.setData(2, Qt.UserRole, 20.0)
    item1.setText(3, "2")

    item2 = TreeItem(tree)
    item2.setText(0, "A")
    item2.setData(1, Qt.UserRole, 100)
    item2.setData(2, Qt.UserRole, 10.0)
    item2.setText(3, "1")

    # Мокаем sortColumn, так как напрямую установить его в тесте нельзя
    mocker.patch.object(tree, "sortColumn", return_value=0)
    assert item2.__lt__(item1) is True  # "A" < "B"

    mocker.patch.object(tree, "sortColumn", return_value=1)
    assert item2.__lt__(item1) is True  # 100 < 200

    mocker.patch.object(tree, "sortColumn", return_value=2)
    assert item2.__lt__(item1) is True  # 10.0 < 20.0

    mocker.patch.object(tree, "sortColumn", return_value=3)
    assert item2.__lt__(item1) is True  # 1 < 2


def test_percent_delegate(qtbot, mocker):
    """Покрывает отрисовку делегата (PercentDelegate)."""
    delegate = PercentDelegate()

    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 100, 20)
    option.state = QStyle.State_None

    mock_index = mocker.MagicMock()
    mock_index.data.return_value = 50.0

    # Создаем реальный QPainter, чтобы drawControl не падал
    pixmap = QPixmap(200, 50)
    painter = QPainter(pixmap)

    # Вызываем отрисовку
    delegate.paint(painter, option, mock_index)
    painter.end()


def test_treemap_widget(qtbot, mocker):
    """Покрывает отрисовку Treemap через render()."""
    widget = TreemapWidget()
    widget.resize(800, 600)
    qtbot.addWidget(widget)

    # Рендерим пустой виджет (вызывает paintEvent)
    pixmap = QPixmap(800, 600)
    widget.render(pixmap)

    # Данные с нулевым размером
    widget.set_data({"file1": 0, "file2": 100})
    widget.render(pixmap)

    # Валидные данные
    widget.set_data({"folder1": 500, "folder2": 300})
    widget.render(pixmap)

    # Проверяем клик по карте (подключаем реальный мок вместо патча emit)
    mock_slot = mocker.MagicMock()
    widget.folder_clicked.connect(mock_slot)

    if widget.rects:
        rect, name = widget.rects[0]
        click_event = mocker.MagicMock()
        click_event.button.return_value = Qt.LeftButton
        click_event.pos.return_value = rect.center()

        widget.mousePressEvent(click_event)
        mock_slot.assert_called_once_with(name)


def test_heatmap_widget(qtbot):
    """Покрывает обновление Heatmap."""
    widget = HeatmapWidget()
    qtbot.addWidget(widget)

    data = [
        {"name": "file1.txt", "size": 100},
        {"name": "file2.txt", "size": 200},
        {"name": "movie.mp4", "size": 800},
    ]
    widget.update_data(data)
    assert widget.layout.count() > 2


# ==========================================
# 2. Тесты для DiskAnalysisTab
# ==========================================


@pytest.fixture
def disk_tab(qtbot, mocker):
    """Создает вкладку анализа диска с замоканными дисками."""
    mock_part = mocker.MagicMock()
    mock_part.mountpoint = "C:\\"
    mock_part.device = "C:"
    mocker.patch("psutil.disk_partitions", return_value=[mock_part])

    mock_usage = mocker.MagicMock()
    mock_usage.free = 100 * 1024**3
    mocker.patch("psutil.disk_usage", return_value=mock_usage)

    tab = DiskAnalysisTab()
    qtbot.addWidget(tab)
    return tab


def test_init_and_drives(disk_tab):
    assert disk_tab.combo.count() == 2
    assert "C:" in disk_tab.combo.itemText(1)


def test_on_drive_and_browse(disk_tab, mocker):
    disk_tab.combo.setCurrentIndex(1)
    assert disk_tab.path_edit.text() == "C:\\"

    # ИСПРАВЛЕНО: правильный путь для мока
    mocker.patch(
        "gui.disk_analysis_tab.QFileDialog.getExistingDirectory",
        return_value="D:\\NewPath",
    )
    disk_tab._browse()
    assert disk_tab.path_edit.text() == "D:\\NewPath"


def test_start_invalid_path(disk_tab, mocker):
    mock_warning = mocker.patch("gui.disk_analysis_tab.QMessageBox.warning")
    disk_tab.path_edit.setText("C:\\Invalid_Ghost_Path_999")
    disk_tab._start()
    assert mock_warning.called


def test_start_valid_path(disk_tab, mocker):
    mocker.patch("os.path.isdir", return_value=True)
    mock_worker = mocker.patch(
        "gui.disk_analysis_tab.DiskAnalysisTab._run_worker"
    )

    disk_tab.path_edit.setText("C:\\Valid")
    disk_tab._start()

    assert disk_tab.btn_start.isEnabled() is False
    # ИСПРАВЛЕНО: isVisible() == False, так как виджет не показан на экране.
    # Проверяем, что он не скрыт (isHidden == False)
    assert disk_tab.progress.isHidden() is False
    assert mock_worker.called


def test_fill_root(disk_tab, mocker):
    mock_notify = mocker.patch.object(disk_tab.window(), "notify", create=True)
    data = [
        {
            "name": "folder1",
            "size": 500,
            "files": 5,
            "is_dir": True,
            "error": None,
            "path": "C:/folder1",
        },
        {
            "name": "file1.txt",
            "size": 100,
            "files": 1,
            "is_dir": False,
            "error": None,
            "path": "C:/file1.txt",
        },
    ]

    disk_tab._fill_root("C:\\", data)

    assert disk_tab.tree.topLevelItemCount() == 2
    assert disk_tab.btn_start.isEnabled() is True
    assert disk_tab.top_files.count() == 1
    assert mock_notify.called


def test_expand_and_fill_child(disk_tab, mocker):
    item = TreeItem(disk_tab.tree)
    item.setText(0, "folder1")
    item.setData(0, Qt.UserRole, "C:/folder1")
    # ИСПРАВЛЕНО: добавлен импорт QTreeWidgetItem
    QTreeWidgetItem(item).setText(0, "...")

    mock_run_worker = mocker.patch(
        "gui.disk_analysis_tab.DiskAnalysisTab._run_worker"
    )
    disk_tab._expand(item)

    assert item.childCount() == 0
    assert mock_run_worker.called


def test_add_items_all_states(disk_tab):
    """Проверяет добавление элементов с разными состояниями (ошибка, старая папка, файл)."""
    import time

    old_mtime = time.time() - (400 * 24 * 3600)

    data = [
        {
            "name": "err_folder",
            "size": 0,
            "files": 0,
            "is_dir": True,
            "error": "Access denied",
            "path": "C:/err",
        },
        {
            "name": "empty_folder",
            "size": 0,
            "files": 0,
            "is_dir": True,
            "error": None,
            "path": "C:/empty",
        },
        {
            "name": "old_file.txt",
            "size": 10,
            "files": 1,
            "is_dir": False,
            "error": None,
            "path": "C:/old.txt",
            "mtime": old_mtime,
        },
    ]

    disk_tab._add_items(disk_tab.tree, data, 10)
    assert disk_tab.tree.topLevelItemCount() == 3

    # ИСПРАВЛЕНО: Ищем элементы по имени, так как сортировка в дереве перемешала их порядок
    def get_item(name):
        for i in range(disk_tab.tree.topLevelItemCount()):
            it = disk_tab.tree.topLevelItem(i)
            if it.text(0) == name:
                return it
        return None

    err_item = get_item("err_folder")
    assert err_item.foreground(2).color().name() == "#ff0000"

    empty_item = get_item("empty_folder")
    assert empty_item.child(0).text(0) == "..."

    old_item = get_item("old_file.txt")
    assert old_item.foreground(0).color().name() == "#9ca3af"


def test_filter(disk_tab):
    parent = TreeItem(disk_tab.tree)
    parent.setText(0, "Documents")
    child = TreeItem(parent)
    child.setText(0, "report.pdf")
    disk_tab.tree.addTopLevelItem(parent)

    disk_tab._filter("report")
    assert parent.isHidden() is False
    assert child.isHidden() is False
    assert parent.isExpanded() is True

    disk_tab._filter("nothing")
    assert parent.isHidden() is True


def test_on_treemap_click(disk_tab, mocker):
    disk_tab.path_edit.setText("C:/")
    mocker.patch("pathlib.Path.is_dir", return_value=True)
    mock_start = mocker.patch("gui.disk_analysis_tab.DiskAnalysisTab._start")

    disk_tab._on_treemap_click("Windows")
    assert disk_tab.path_edit.text() == "C:\\Windows"
    assert mock_start.called


def test_menu_and_del(disk_tab, mocker):
    # ИСПРАВЛЕНО: делаем элемент дочерним, чтобы он удалялся из дерева,
    # а не вызывал self._start() (как происходит с корневыми элементами)
    parent = TreeItem(disk_tab.tree)
    parent.setText(0, "parent")
    item = TreeItem(parent)
    item.setText(0, "test.txt")
    item.setData(0, Qt.UserRole, "C:/test.txt")
    disk_tab.tree.addTopLevelItem(parent)

    mocker.patch(
        "gui.disk_analysis_tab.QMessageBox.question",
        return_value=QMessageBox.Yes,
    )
    mocker.patch("os.path.isdir", return_value=False)
    mocker.patch("gui.disk_analysis_tab.delete_file")
    mocker.patch(
        "gui.disk_analysis_tab.DiskAnalysisTab._run_worker"
    )  # Чтобы не запускался реальный воркер

    disk_tab._del(item, trash=True)
    assert parent.childCount() == 0  # Элемент удален из родителя


def test_navigation(disk_tab, mocker):
    mocker.patch("gui.disk_analysis_tab.DiskAnalysisTab._start")
    disk_tab.history = ["C:/", "C:/Windows"]
    disk_tab.hist_idx = 1

    disk_tab._go_back()
    assert disk_tab.hist_idx == 0
    assert disk_tab.path_edit.text() == "C:/"

    disk_tab._go_fwd()
    assert disk_tab.hist_idx == 1
    assert disk_tab.path_edit.text() == "C:/Windows"


def test_drag_and_drop(disk_tab, mocker):
    mocker.patch("gui.disk_analysis_tab.DiskAnalysisTab._start")
    mocker.patch("pathlib.Path.is_dir", return_value=True)
    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile("C:/NewDrop")])

    drag_event = mocker.MagicMock()
    drag_event.mimeData.return_value = mime_data
    disk_tab.dragEnterEvent(drag_event)
    drag_event.acceptProposedAction.assert_called_once()

    drop_event = mocker.MagicMock()
    drop_event.mimeData.return_value = mime_data
    disk_tab.dropEvent(drop_event)
    assert disk_tab.path_edit.text() == "C:\\NewDrop"


# ==========================================
# 3. Тесты для повышения покрытия (Отрисовка и ошибки)
# ==========================================


def test_treemap_paint_events(qtbot):
    """Принудительно вызывает отрисовку Treemap для покрытия строк 71-111."""
    widget = TreemapWidget()
    widget.resize(800, 600)
    qtbot.addWidget(widget)

    # 1. Отрисовка с валидными данными
    widget.set_data({"folder1": 500, "folder2": 300})
    pixmap = QPixmap(800, 600)
    widget.render(pixmap)

    # 2. Отрисовка с нулевыми данными
    widget.set_data({"empty": 0})
    widget.render(pixmap)

    # 3. Отрисовка с отрицательными данными (вызовет исключение внутри squarify, но оно поймается)
    widget.set_data({"negative": -100})
    widget.render(pixmap)


def test_heatmap_paint_events(qtbot):
    """Покрывает update_data в HeatmapWidget."""
    widget = HeatmapWidget()
    qtbot.addWidget(widget)

    # Вызываем с данными, чтобы отработал цикл создания QProgressBar
    data = [{"name": "file.txt", "size": 100}, {"name": "no_ext", "size": 50}]
    widget.update_data(data)

    # Вызываем повторно, чтобы сработала очистка старых виджетов
    widget.update_data(data)


def test_del_exception(disk_tab, mocker):
    """Покрывает ветку except в _del (строка 505)."""
    item = TreeItem(disk_tab.tree)
    item.setText(0, "test.txt")
    item.setData(0, Qt.UserRole, "C:/test.txt")
    disk_tab.tree.addTopLevelItem(item)

    mocker.patch(
        "gui.disk_analysis_tab.QMessageBox.question",
        return_value=QMessageBox.Yes,
    )
    mocker.patch(
        "gui.disk_analysis_tab.QMessageBox.critical"
    )  # Мокаем вывод ошибки

    # Имитируем ошибку при удалении
    mocker.patch("os.path.isdir", return_value=False)
    mocker.patch(
        "gui.disk_analysis_tab.delete_file",
        side_effect=Exception("Delete error"),
    )

    disk_tab._del(item, trash=True)
    # Если ошибка поймана, тест не упадет


def test_refresh(disk_tab, mocker):
    """Покрывает метод _refresh (строки 577-597)."""
    item = TreeItem(disk_tab.tree)
    item.setData(1, Qt.UserRole, 100)

    # Создаем пустышку
    QTreeWidgetItem(item).setText(0, "...")

    # Данные для обновления
    data = [
        {
            "name": "new_file.txt",
            "size": 50,
            "files": 1,
            "is_dir": False,
            "error": None,
            "path": "C:/new.txt",
        }
    ]

    disk_tab._refresh(item, data)
    assert item.childCount() == 1
    assert item.child(0).text(0) == "new_file.txt"


def test_drag_enter_invalid(disk_tab, mocker):
    mocker.patch("pathlib.Path.is_dir", return_value=False)
    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile("C:/file.txt")])

    drag_event = mocker.MagicMock()
    drag_event.mimeData.return_value = mime_data
    disk_tab.dragEnterEvent(drag_event)

    # Проверяем, что был вызван ignore(), а не acceptProposedAction()
    drag_event.ignore.assert_called_once()


def test_drop_invalid(disk_tab, mocker):
    """Покрывает ветку e.ignore() в dropEvent (строка 665)."""
    mocker.patch("pathlib.Path.is_dir", return_value=False)  # Не папка
    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile("C:/file.txt")])

    drop_event = QDropEvent(
        QPoint(0, 0), Qt.CopyAction, mime_data, Qt.LeftButton, Qt.NoModifier
    )
    disk_tab.dropEvent(drop_event)
    assert not drop_event.isAccepted()
