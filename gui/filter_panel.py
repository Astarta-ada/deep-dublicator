"""Панель фильтров поиска дубликатов."""

from PySide6.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QCheckBox,
    QSpinBox,
    QComboBox,
)

from core.scanner import normalize_extensions


class FilterPanel(QGroupBox):
    """Панель настроек поиска: пресеты расширений, размеры, пустые файлы."""

    PRESET_GROUPS = {
        "Все файлы": "",
        "Изображения": ".jpg,.jpeg,.png,.gif,.bmp,.webp,.tiff,.heic",
        "Видео": ".mp4,.mkv,.avi,.mov,.wmv,.flv,.webm",
        "Аудио": ".mp3,.wav,.flac,.aac,.ogg,.m4a",
        "Документы": ".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.rtf,.odt",
        "Архивы": ".zip,.rar,.7z,.tar,.gz,.bz2",
        "Код": ".py,.js,.ts,.java,.c,.cpp,.h,.cs,.go,.rs,.rb,.php",
    }

    def __init__(self, parent=None):
        super().__init__("Фильтры", parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)

        # --- Пресеты + расширения
        row1 = QHBoxLayout()
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("— выбрать пресет —")
        for name in self.PRESET_GROUPS:
            self.preset_combo.addItem(name)
        self.preset_combo.currentTextChanged.connect(self._apply_preset)
        row1.addWidget(QLabel("Пресет:"))
        row1.addWidget(self.preset_combo)
        row1.addStretch()
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Расширения:"))
        self.ext_edit = QLineEdit()
        self.ext_edit.setPlaceholderText(".jpg, .png (пусто = все файлы)")
        row2.addWidget(self.ext_edit, 1)
        layout.addLayout(row2)

        # --- Размеры
        row3 = QHBoxLayout()
        self.min_size_spin = QSpinBox()
        self.min_size_spin.setRange(0, 1_000_000_000)
        self.min_size_spin.setValue(1)
        self.min_size_spin.setSuffix(" Б")

        self.max_size_spin = QSpinBox()
        self.max_size_spin.setRange(0, 1_000_000_000)
        self.max_size_spin.setValue(0)
        self.max_size_spin.setSpecialValueText("∞")
        self.max_size_spin.setSuffix(" Б")

        row3.addWidget(QLabel("Мин. размер:"))
        row3.addWidget(self.min_size_spin)
        row3.addWidget(QLabel("Макс. размер:"))
        row3.addWidget(self.max_size_spin)
        row3.addStretch()
        layout.addLayout(row3)

        # --- Особые режимы
        row4 = QHBoxLayout()
        self.include_empty_cb = QCheckBox(
            "Искать пустые файлы отдельной группой"
        )
        self.include_empty_cb.setToolTip(
            "Все пустые файлы будут собраны в одну группу для массовой обработки"
        )
        row4.addWidget(self.include_empty_cb)
        row4.addStretch()
        layout.addLayout(row4)

    def _apply_preset(self, name: str):
        if name in self.PRESET_GROUPS and name != "— выбрать пресет —":
            self.ext_edit.setText(self.PRESET_GROUPS[name])

    # -------- helpers --------

    def get_extensions(self) -> set[str]:
        return normalize_extensions(self.ext_edit.text())

    def get_min_size(self) -> int:
        if self.include_empty_cb.isChecked():
            return 0  # пустые должны попасть в скан
        return max(1, self.min_size_spin.value())

    def get_max_size(self):
        v = self.max_size_spin.value()
        return None if v == 0 else v

    def include_empty(self) -> bool:
        return self.include_empty_cb.isChecked()

    def as_dict(self) -> dict:
        return {
            "extensions": sorted(self.get_extensions()),
            "min_size": self.get_min_size(),
            "max_size": self.get_max_size(),
            "include_empty": self.include_empty(),
        }
