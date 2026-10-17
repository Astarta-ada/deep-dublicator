"""Реестр визуальных тем приложения + генератор QSS."""

# ============================ Палитры ============================

LIGHT_BLUE = {
    "name": "Светлая (синяя)",
    "primary": "#2563eb",
    "primary_hover": "#1d4ed8",
    "primary_press": "#1e40af",
    "success": "#10b981",
    "success_hover": "#059669",
    "success_press": "#047857",
    "danger": "#ef4444",
    "danger_hover": "#dc2626",
    "bg": "#f1f5f9",
    "surface": "#ffffff",
    "surface_alt": "#f8fafc",
    "border": "#e2e8f0",
    "border_strong": "#cbd5e1",
    "text": "#0f172a",
    "text_muted": "#64748b",
    "text_disabled": "#94a3b8",
    "text_on_primary": "#ffffff",
    "legend_bg": "#eff6ff",
    "legend_border": "#bfdbfe",
    "original_bg": "#ecfdf5",
    "original_border": "#a7f3d0",
    "tooltip_bg": "#0f172a",
    "tooltip_text": "#ffffff",
}

LIGHT_EMERALD = {
    **LIGHT_BLUE,
    "name": "Светлая (изумрудная)",
    "primary": "#10b981",
    "primary_hover": "#059669",
    "primary_press": "#047857",
    "danger": "#f43f5e",
    "danger_hover": "#e11d48",
    "legend_bg": "#ecfdf5",
    "legend_border": "#a7f3d0",
    "original_bg": "#eff6ff",
    "original_border": "#bfdbfe",
}

LIGHT_VIOLET = {
    **LIGHT_BLUE,
    "name": "Светлая (фиолетовая)",
    "primary": "#7c3aed",
    "primary_hover": "#6d28d9",
    "primary_press": "#5b21b6",
    "legend_bg": "#f5f3ff",
    "legend_border": "#ddd6fe",
}

DARK = {
    "name": "Тёмная",
    "primary": "#3b82f6",
    "primary_hover": "#60a5fa",
    "primary_press": "#2563eb",
    "success": "#10b981",
    "success_hover": "#34d399",
    "success_press": "#059669",
    "danger": "#ef4444",
    "danger_hover": "#f87171",
    "bg": "#0f172a",  # slate-900
    "surface": "#1e293b",  # slate-800
    "surface_alt": "#334155",  # slate-700
    "border": "#334155",
    "border_strong": "#475569",
    "text": "#f1f5f9",
    "text_muted": "#94a3b8",
    "text_disabled": "#64748b",
    "text_on_primary": "#ffffff",
    "legend_bg": "#1e3a8a",  # blue-900
    "legend_border": "#1e40af",  # blue-800
    "original_bg": "#064e3b",  # emerald-900
    "original_border": "#047857",  # emerald-700
    "tooltip_bg": "#f1f5f9",
    "tooltip_text": "#0f172a",
}

WINDOWS_VISTA = {
    **LIGHT_BLUE,
    "name": "Windows Vista (Aero)",
    "primary": "#3a85ff",
    "primary_hover": "#5599ff",
    "primary_press": "#1a6aff",
    "success": "#43a047",
    "success_hover": "#4caf50",
    "success_press": "#2e7d32",
    "danger": "#d32f2f",
    "danger_hover": "#f44336",
    "bg": "#e9eff5",
    "surface": "#ffffff",
    "surface_alt": "#f4f7fb",
    "border": "#c1d1e6",
    "border_strong": "#a0b5cc",
    "text": "#000000",
    "text_muted": "#5a6b7c",
    "text_disabled": "#a0a0a0",
    "legend_bg": "#e3f2fd",
    "legend_border": "#90caf9",
    "original_bg": "#e8f5e9",
    "original_border": "#a5d6a7",
    "tooltip_bg": "#000000",
    "tooltip_text": "#ffffff",
}

WINDOWS_7 = {
    **LIGHT_BLUE,
    "name": "Windows 7",
    "primary": "#1e6fc2",
    "primary_hover": "#3384d6",
    "primary_press": "#155a9e",
    "success": "#3a9e3a",
    "success_hover": "#4db84d",
    "success_press": "#2b7a2b",
    "danger": "#c42b1c",
    "danger_hover": "#e03d2e",
    "bg": "#f0f0f0",
    "surface": "#ffffff",
    "surface_alt": "#f7f7f7",
    "border": "#a0a0a0",
    "border_strong": "#808080",
    "text": "#000000",
    "text_muted": "#606060",
    "text_disabled": "#b0b0b0",
    "legend_bg": "#e8f1fb",
    "legend_border": "#a3c9f0",
    "original_bg": "#ebf7eb",
    "original_border": "#b5dfb5",
    "tooltip_bg": "#ffffe1",  # Классический желтый тултип Windows
    "tooltip_text": "#000000",
}

WINDOWS_11 = {
    **LIGHT_BLUE,
    "name": "Windows 11",
    "primary": "#0067c0",
    "primary_hover": "#1975c8",
    "primary_press": "#00559e",
    "success": "#0f7b0f",
    "success_hover": "#1a8f1a",
    "success_press": "#0a5c0a",
    "danger": "#c42b1c",
    "danger_hover": "#d13a2b",
    "bg": "#f3f3f3",
    "surface": "#ffffff",
    "surface_alt": "#f9f9f9",
    "border": "#e5e5e5",
    "border_strong": "#cccccc",
    "text": "#1a1a1a",
    "text_muted": "#5e5e5e",
    "text_disabled": "#a0a0a0",
    "legend_bg": "#f0f6fc",
    "legend_border": "#cce0f5",
    "original_bg": "#f1f8f1",
    "original_border": "#cce8cc",
    "tooltip_bg": "#2b2b2b",
    "tooltip_text": "#ffffff",
}

KDE_PLASMA = {
    **LIGHT_BLUE,
    "name": "KDE Plasma (Breeze)",
    "primary": "#3daee9",
    "primary_hover": "#4cb8f0",
    "primary_press": "#2b9bda",
    "success": "#27ae60",
    "success_hover": "#2ecc71",
    "success_press": "#1e8e4e",
    "danger": "#da4453",
    "danger_hover": "#e55765",
    "bg": "#eff0f1",
    "surface": "#ffffff",
    "surface_alt": "#f5f6f7",
    "border": "#bdc3c7",
    "border_strong": "#95a5a6",
    "text": "#232629",
    "text_muted": "#7f8c8d",
    "text_disabled": "#bdc3c7",
    "legend_bg": "#eef7fc",
    "legend_border": "#b8e0f7",
    "original_bg": "#eefaf2",
    "original_border": "#b8e6c8",
    "tooltip_bg": "#31363b",
    "tooltip_text": "#eff0f1",
}

PROTON = {
    **LIGHT_BLUE,
    "name": "Proton",
    "primary": "#6d4aff",
    "primary_hover": "#8569ff",
    "primary_press": "#5533e6",
    "success": "#0c8346",
    "success_hover": "#149e58",
    "success_press": "#086635",
    "danger": "#dc2626",
    "danger_hover": "#ef4444",
    "bg": "#f8f9fa",
    "surface": "#ffffff",
    "surface_alt": "#fcfcfd",
    "border": "#e5e7eb",
    "border_strong": "#d1d5db",
    "text": "#111827",
    "text_muted": "#6b7280",
    "text_disabled": "#9ca3af",
    "legend_bg": "#f4f1ff",
    "legend_border": "#d3c8ff",
    "original_bg": "#f0fdf4",
    "original_border": "#bbf7d0",
    "tooltip_bg": "#1f2937",
    "tooltip_text": "#ffffff",
}

# Реестр: ключ → палитра. Ключ сохраняется в QSettings.
THEMES = {
    "light_blue": LIGHT_BLUE,
    "light_emerald": LIGHT_EMERALD,
    "light_violet": LIGHT_VIOLET,
    "dark": DARK,
    "windows_vista": WINDOWS_VISTA,
    "windows_7": WINDOWS_7,
    "windows_11": WINDOWS_11,
    "kde_plasma": KDE_PLASMA,
    "proton": PROTON,
}

DEFAULT_THEME = "light_blue"


# ============================ Генератор QSS ============================


def build_stylesheet(theme_key: str) -> str:
    """Возвращает QSS-строку для указанной темы."""
    c = THEMES.get(theme_key, THEMES[DEFAULT_THEME])
    return f"""
/* ======================= Базовое ======================= */
QWidget {{
    background: {c['bg']};
    color: {c['text']};
    font-family: "Segoe UI", "SF Pro Text", "Ubuntu", "Roboto", sans-serif;
    font-size: 13px;
}}

QMainWindow, QDialog {{
    background: {c['bg']};
}}

QToolTip {{
    background: {c['tooltip_bg']};
    color: {c['tooltip_text']};
    border: none;
    padding: 4px 8px;
    border-radius: 4px;
}}

QMenuBar {{
    background: {c['surface']};
    color: {c['text']};
    border-bottom: 1px solid {c['border']};
}}
QMenuBar::item {{
    padding: 6px 10px;
    background: transparent;
    border-radius: 6px;
}}
QMenuBar::item:selected {{
    background: {c['surface_alt']};
}}
QMenu {{
    background: {c['surface']};
    color: {c['text']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{
    padding: 6px 20px 6px 24px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {c['primary']};
    color: {c['text_on_primary']};
}}
QMenu::separator {{
    height: 1px;
    background: {c['border']};
    margin: 4px 8px;
}}

/* ======================= Кнопки ======================= */
QPushButton {{
    background: {c['surface']};
    color: {c['text']};
    border: 1px solid {c['border_strong']};
    border-radius: 8px;
    padding: 6px 14px;
    min-height: 22px;
}}
QPushButton:hover {{
    background: {c['surface_alt']};
    border-color: {c['primary']};
    color: {c['primary']};
}}
QPushButton:pressed {{
    background: {c['border']};
}}
QPushButton:disabled {{
    background: {c['surface_alt']};
    color: {c['text_disabled']};
    border-color: {c['border']};
}}

QPushButton[class="primary"] {{
    background: {c['primary']};
    color: {c['text_on_primary']};
    border: none;
    font-weight: 600;
    padding: 10px 18px;
    min-height: 24px;
    border-radius: 10px;
}}
QPushButton[class="primary"]:hover {{
    background: {c['primary_hover']};
    color: {c['text_on_primary']};
}}
QPushButton[class="primary"]:pressed {{
    background: {c['primary_press']};
}}
QPushButton[class="primary"]:disabled {{
    background: {c['border_strong']};
    color: {c['text_disabled']};
}}

QPushButton[class="success"] {{
    background: {c['success']};
    color: {c['text_on_primary']};
    border: none;
    font-weight: 600;
    padding: 8px 16px;
    border-radius: 10px;
}}
QPushButton[class="success"]:hover {{
    background: {c['success_hover']};
    color: {c['text_on_primary']};
}}
QPushButton[class="success"]:pressed {{
    background: {c['success_press']};
}}

QPushButton[class="danger"] {{
    background: {c['danger']};
    color: {c['text_on_primary']};
    border: none;
    font-weight: 600;
    padding: 8px 16px;
    border-radius: 10px;
}}
QPushButton[class="danger"]:hover {{
    background: {c['danger_hover']};
    color: {c['text_on_primary']};
}}

/* ======================= Поля ввода ======================= */
QLineEdit, QSpinBox, QComboBox {{
    background: {c['surface']};
    color: {c['text']};
    border: 1px solid {c['border_strong']};
    border-radius: 8px;
    padding: 5px 10px;
    min-height: 22px;
    selection-background-color: {c['primary']};
    selection-color: {c['text_on_primary']};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 2px solid {c['primary']};
    padding: 4px 9px;
}}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
    background: {c['surface_alt']};
    color: {c['text_disabled']};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {c['text_muted']};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {c['surface']};
    color: {c['text']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {c['primary']};
    selection-color: {c['text_on_primary']};
}}

/* ======================= Группы ======================= */
QGroupBox {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 12px;
    margin-top: 14px;
    padding: 14px 12px 12px 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 2px 8px;
    color: {c['text']};
    background: {c['surface']};
    border-radius: 6px;
}}
QGroupBox QGroupBox {{
    background: {c['surface_alt']};
}}

/* ======================= Вкладки ======================= */
QTabWidget::pane {{
    border: 1px solid {c['border']};
    border-radius: 10px;
    top: -1px;
    background: {c['bg']};
}}
QTabBar::tab {{
    background: transparent;
    color: {c['text_muted']};
    padding: 8px 18px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}}
QTabBar::tab:selected {{
    background: {c['surface']};
    color: {c['primary']};
    font-weight: 600;
    border: 1px solid {c['border']};
    border-bottom: none;
}}
QTabBar::tab:hover:!selected {{
    color: {c['text']};
}}

/* ======================= Чекбоксы / радиокнопки ======================= */
QCheckBox, QRadioButton {{
    spacing: 6px;
    background: transparent;
    color: {c['text']};
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {c['border_strong']};
    border-radius: 4px;
    background: {c['surface']};
}}
QCheckBox::indicator:hover {{
    border-color: {c['primary']};
}}
QCheckBox::indicator:checked {{
    background: {c['primary']};
    border-color: {c['primary']};
    image: none;
}}
QCheckBox::indicator:checked:disabled {{
    background: {c['border_strong']};
    border-color: {c['border_strong']};
}}
QCheckBox::indicator:disabled {{
    background: {c['surface_alt']};
}}

QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {c['border_strong']};
    border-radius: 9px;
    background: {c['surface']};
}}
QRadioButton::indicator:hover {{
    border-color: {c['primary']};
}}
QRadioButton::indicator:checked {{
    background: {c['primary']};
    border: 4px solid {c['primary']};
}}

/* ======================= Прогресс-бар ======================= */
QProgressBar {{
    background: {c['border']};
    border: none;
    border-radius: 6px;
    height: 10px;
    text-align: center;
    color: {c['text']};
}}
QProgressBar::chunk {{
    background: {c['primary']};
    border-radius: 6px;
}}

/* ======================= Скроллбар ======================= */
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 4px 2px 4px 2px;
}}
QScrollBar::handle:vertical {{
    background: {c['border_strong']};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c['text_muted']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px 4px 2px 4px;
}}
QScrollBar::handle:horizontal {{
    background: {c['border_strong']};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {c['text_muted']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ======================= Спец-классы ======================= */
QFrame#legend {{
    background: {c['legend_bg']};
    border: 1px solid {c['legend_border']};
    border-radius: 8px;
}}
QFrame#legend QLabel {{
    background: transparent;
    color: {c['text']};
}}

QLabel#statusLabel {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 6px 10px;
    color: {c['text_muted']};
}}

QWidget#fileRow {{
    border-radius: 6px;
}}
QWidget#fileRow[original="true"] {{
    background: {c['original_bg']};
    border: 1px solid {c['original_border']};
}}
QWidget#fileRow[original="true"] QLabel {{
    background: transparent;
    color: {c['text']};
}}

QLabel#columnHeader {{
    color: {c['text_muted']};
    font-size: 11px;
    font-weight: 600;
    background: transparent;
}}
/* ======================= Глобальная легенда и Категории ======================= */
QFrame#globalLegend {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 8px;
}}
QFrame#globalLegend QLabel {{
    background: transparent;
    color: {c['text']};
}}

/* Контейнер категории (например, "Изображения") */
QGroupBox[class="category"] {{
    background: transparent;
    border: 2px dashed {c['border_strong']};
    border-radius: 12px;
    margin-top: 18px;
    padding-top: 10px;
}}
QGroupBox[class="category"]::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 2px 10px;
    color: {c['primary']};
    background: {c['surface']};
    border: 1px solid {c['primary']};
    border-radius: 8px;
    font-weight: bold;
    font-size: 13px;
}}
/* Вложенные группы внутри категорий оставляем без "двойных" рамок */
QGroupBox[class="category"] QGroupBox {{
    background: {c['surface']};
    border: 1px solid {c['border']};
}}

"""
