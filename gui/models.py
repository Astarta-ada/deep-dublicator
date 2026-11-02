"""Модели данных и делегаты для QTreeView."""

import logging
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QStandardItem, QColor, QFont, QMouseEvent
from PySide6.QtWidgets import (
    QStyledItemDelegate,
    QStyle,
    QStyleOptionButton,
    QApplication,
)

from utils.constants import (
    ROLE_PATH,
    ROLE_IS_ORIGINAL,
    ROLE_IS_CHECKED,
    ROLE_IS_GROUP,
    ROLE_IS_CATEGORY,
)

log = logging.getLogger(__name__)


class DuplicateItem(QStandardItem):
    """Элемент дерева (категория, группа или файл)."""

    def __init__(self, text="", path=None, is_group=False, is_category=False):
        super().__init__(text)
        self.path = path
        self.is_group = is_group
        self.is_category = is_category
        self.setEditable(False)

        # ИСПРАВЛЕНИЕ: Добавляем флаги, чтобы QTreeView передавал события в editorEvent
        if not is_group and not is_category:
            self.setFlags(
                Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable
            )


class DuplicateDelegate(QStyledItemDelegate):
    """Рисует радиокнопку и чекбокс для строк с файлами."""

    def paint(self, painter, option, index):
        item = index.model().itemFromIndex(index)
        if not item or item.is_group or item.is_category:
            super().paint(painter, option, index)
            return

        painter.save()

        is_orig = item.data(ROLE_IS_ORIGINAL)
        is_checked = item.data(ROLE_IS_CHECKED)

        # Цвета состояний
        if is_orig:
            painter.fillRect(option.rect, QColor("#ecfdf5"))
        elif is_checked:
            painter.fillRect(option.rect, QColor("#fef2f2"))
        elif option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        # Радиокнопка (Оригинал)
        radio_opt = QStyleOptionButton()
        radio_opt.rect = option.rect.adjusted(
            4, 0, -option.rect.width() + 30, 0
        )
        radio_opt.state = QStyle.State_Enabled | (
            QStyle.State_On if is_orig else QStyle.State_Off
        )
        QApplication.style().drawControl(
            QStyle.CE_RadioButton, radio_opt, painter
        )

        # Чекбокс (Дубликат)
        check_opt = QStyleOptionButton()
        check_opt.rect = option.rect.adjusted(
            34, 0, -option.rect.width() + 60, 0
        )
        check_opt.state = QStyle.State_Enabled | (
            QStyle.State_On if is_checked else QStyle.State_Off
        )
        if is_orig:
            check_opt.state |= QStyle.State_ReadOnly
        QApplication.style().drawControl(
            QStyle.CE_CheckBox, check_opt, painter
        )

        # Текст
        text_rect = option.rect.adjusted(64, 0, 0, 0)
        painter.setPen(QColor("#0f172a"))
        painter.drawText(
            text_rect, Qt.AlignVCenter | Qt.AlignLeft, item.text()
        )

        painter.restore()

    def editorEvent(self, event, model, option, index):
        """Обрабатываем клики по радио и чекбоксам."""
        item = model.itemFromIndex(index)
        if not item or item.is_group or item.is_category:
            return super().editorEvent(event, model, option, index)

        if event.type() == QMouseEvent.MouseButtonRelease:
            # Вычисляем позицию клика относительно ЛЕВОГО КРАЯ ЯЧЕЙКИ
            x_pos = event.position().toPoint().x() - option.rect.x()

            # Клик по радиокнопке (Оригинал)
            if 4 <= x_pos <= 30:
                parent = item.parent()
                if parent and parent.rowCount() > 0:
                    # Снимаем галочки и оригинал со всех файлов в группе
                    for row in range(parent.rowCount()):
                        sib = parent.child(row)
                        sib.setData(False, ROLE_IS_ORIGINAL)
                        sib.setData(False, ROLE_IS_CHECKED)

                    # Ставим оригинал на текущий
                    item.setData(True, ROLE_IS_ORIGINAL)

                    # ИСПРАВЛЕНИЕ: Передаем диапазон от ПЕРВОГО до ПОСЛЕДНЕГО ФАЙЛА в группе
                    model.dataChanged.emit(
                        parent.child(0).index(),
                        parent.child(parent.rowCount() - 1).index(),
                    )
                return True

            # Клик по чекбоксу (Дубликат)
            elif 34 <= x_pos <= 60:
                if not item.data(ROLE_IS_ORIGINAL):
                    item.setData(
                        not item.data(ROLE_IS_CHECKED), ROLE_IS_CHECKED
                    )
                    model.dataChanged.emit(index, index)
                    return True
        return False
