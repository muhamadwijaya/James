"""Dark navy theme of FRT Cam: colors and the application style sheet."""
from __future__ import annotations

import icons

FONT_FAMILIES = ["Segoe UI", "Inter", "Noto Sans", "DejaVu Sans"]
MONO_FAMILIES = ["Cascadia Mono", "Consolas", "DejaVu Sans Mono", "monospace"]

BG = "#081325"
SIDEBAR = "#07101f"
CARD = "#0c1a30"
CARD_2 = "#0e1f39"
BORDER = "#1a2d4d"
INPUT = "#0a172d"
INPUT_BORDER = "#22385e"
TEXT = "#e8eef8"
MUTED = "#93a6c4"
DIM = "#5d7296"

BLUE = "#2f80ff"
BLUE_DARK = "#1c63e8"
GREEN = "#22c55e"
RED = "#ef4444"
ORANGE = "#f59e0b"
PURPLE = "#8b5cf6"
CYAN = "#38bdf8"

STATUS_COLORS = {"saved": GREEN, "duplicate": ORANGE, "unmatched": PURPLE, "error": RED}
STATUS_TEXT = {
    "saved": "Disimpan",
    "duplicate": "Duplikat (dibuang)",
    "duplicate_kept": "Duplikat (_duplikat)",
    "unmatched": "Tidak sesuai",
    "error": "Gagal",
}


def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {int(alpha * 255)})"


def stylesheet() -> str:
    families = ", ".join(f'"{f}"' for f in FONT_FAMILIES)
    mono = ", ".join(f'"{f}"' for f in MONO_FAMILIES)
    chevron_down = icons.file_url("chevron_down", MUTED, 14)
    chevron_up_small = icons.file_url("chevron_up", MUTED, 10, 2.6)
    chevron_down_small = icons.file_url("chevron_down", MUTED, 10, 2.6)
    check = icons.file_url("check", "#ffffff", 12, 3.2)
    return f"""
* {{ font-family: {families}; color: {TEXT}; }}
QWidget {{ font-size: 9pt; }}
QMainWindow, #root {{ background: {BG}; }}
#rootFrame {{ background: {BG}; border: 1px solid {BORDER}; }}
QLabel {{ background: transparent; }}
QToolTip {{ background: {CARD}; color: {TEXT}; border: 1px solid {BORDER}; padding: 5px 7px; }}

#sidebar {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0a1730, stop:0.6 #08122a, stop:1 #071a3a);
            border-right: 1px solid {BORDER}; }}
#brandTitle {{ font-size: 14pt; font-weight: 700; }}
QPushButton#navButton {{ text-align: left; padding: 11px 16px; border: none; border-radius: 9px;
                         background: transparent; color: #c9d5e8; font-size: 10pt; }}
QPushButton#navButton:hover {{ background: {rgba(BLUE, 0.10)}; }}
QPushButton#navButton:checked {{ color: #ffffff; font-weight: 600;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e66f5, stop:1 #2f86ff);
    border: 1px solid #4b95ff; }}
#versionCard {{ background: {rgba(BLUE, 0.07)}; border: 1px solid {BORDER}; border-radius: 10px; }}

#header {{ background: transparent; }}
#headerTitle {{ font-size: 14pt; font-weight: 700; }}
#headerSubtitle {{ color: {MUTED}; font-size: 9pt; }}
QPushButton#windowButton {{ background: transparent; border: none; border-radius: 6px; padding: 6px; }}
QPushButton#windowButton:hover {{ background: {rgba('#ffffff', 0.08)}; }}
QPushButton#closeButton {{ background: transparent; border: none; border-radius: 6px; padding: 6px; }}
QPushButton#closeButton:hover {{ background: {RED}; }}

#card {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {CARD_2}, stop:1 {CARD});
         border: 1px solid {BORDER}; border-radius: 12px; }}
#cardTitle {{ font-size: 11pt; font-weight: 700; }}
#cardSubtitle {{ color: {MUTED}; font-size: 8.5pt; }}
#formLabel {{ color: #c3cfe2; }}
#muted {{ color: {MUTED}; }}
#hint {{ color: {MUTED}; font-size: 8pt; }}
#mono {{ font-family: {mono}; }}
#renameResult {{ font-family: {mono}; color: {GREEN}; font-weight: 600; font-size: 9.5pt; }}
#renameBad {{ color: {RED}; }}

QLineEdit, QComboBox, QSpinBox {{
    background: {INPUT}; border: 1px solid {INPUT_BORDER}; border-radius: 7px;
    padding: 4px 10px; min-height: 18px; selection-background-color: {BLUE}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1px solid {BLUE}; }}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{ color: #b9c6db; background: {INPUT}; border-color: #1d3152; }}
QComboBox {{ padding-right: 28px; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{ image: url({chevron_down}); width: 14px; height: 14px; }}
QComboBox QAbstractItemView {{ background: {CARD}; border: 1px solid {BORDER}; outline: none;
                               selection-background-color: {BLUE}; padding: 4px; }}
QSpinBox {{ padding-right: 24px; }}
QSpinBox::up-button, QSpinBox::down-button {{ subcontrol-origin: border; width: 22px; border: none;
                                               border-left: 1px solid {INPUT_BORDER}; background: transparent; }}
QSpinBox::up-button {{ subcontrol-position: top right; border-top-right-radius: 7px; }}
QSpinBox::down-button {{ subcontrol-position: bottom right; border-bottom-right-radius: 7px; }}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: {rgba(BLUE, 0.15)}; }}
QSpinBox::up-arrow {{ image: url({chevron_up_small}); width: 10px; height: 10px; }}
QSpinBox::down-arrow {{ image: url({chevron_down_small}); width: 10px; height: 10px; }}

QCheckBox, QRadioButton {{ spacing: 9px; background: transparent; }}
QCheckBox:disabled, QRadioButton:disabled {{ color: #c3cfe2; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid #3a5079; background: {INPUT}; }}
QCheckBox::indicator:checked {{ background: {BLUE}; border: 1px solid {BLUE}; image: url({check}); }}
QCheckBox::indicator:disabled {{ border-color: #2f456b; }}
QCheckBox::indicator:checked:disabled {{ background: #2b6be0; border-color: #2b6be0; }}
QRadioButton::indicator:disabled {{ border-color: #2f456b; }}
QRadioButton::indicator {{ width: 16px; height: 16px; border-radius: 9px; border: 1px solid #3a5079; background: {INPUT}; }}
QRadioButton::indicator:checked {{ border: 2px solid {BLUE};
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                                stop:0 {BLUE}, stop:0.5 {BLUE}, stop:0.6 {INPUT}, stop:1 {INPUT}); }}

QPushButton {{ background: #11223f; border: 1px solid {INPUT_BORDER}; border-radius: 7px; padding: 5px 12px; }}
QPushButton:hover {{ background: #16294b; border-color: #2d4a78; }}
QPushButton:pressed {{ background: #0e1d36; }}
QPushButton:disabled {{ color: #a9b8ce; border-color: #1d3152; }}
QPushButton#iconButton {{ padding: 6px; min-width: 22px; }}
QPushButton#primaryButton {{ border: 1px solid #4a90ff; border-radius: 9px; font-size: 11pt; font-weight: 600;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1b5ff0, stop:1 #3a8cff); }}
QPushButton#primaryButton:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2a6cf7, stop:1 #4a97ff); }}
QPushButton#primaryButton:disabled {{ color: #dbe7ff; border-color: #2f6fd8;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a4fb8, stop:1 #2d6fd0); }}
QPushButton#dangerButton {{ border: 1px solid #ff6b6b; border-radius: 9px; font-size: 11pt; font-weight: 600;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #d92d3a, stop:1 #f04848); }}
QPushButton#dangerButton:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #e43a47, stop:1 #f55a5a); }}
QPushButton#dangerButton:disabled {{ color: #f3d6d9; border-color: #a83a44;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #8f2430, stop:1 #a8343e); }}

#statusBox {{ border-radius: 9px; }}
#stateButton {{ border-radius: 9px; font-size: 11.5pt; font-weight: 600; }}

QTableView {{ background: transparent; border: none; gridline-color: transparent; outline: none;
              selection-background-color: {rgba(BLUE, 0.16)}; selection-color: {TEXT}; }}
QTableView::item {{ border-bottom: 1px solid #13233f; padding-left: 4px; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{ background: transparent; color: #c3cfe2; border: none; border-bottom: 1px solid {BORDER};
                        padding: 8px 6px; font-weight: 600; }}
QTableCornerButton::section {{ background: transparent; border: none; }}

QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #243a60; border-radius: 4px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #243a60; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QProgressBar {{ background: #18294a; border: none; border-radius: 4px; max-height: 8px; min-height: 8px; }}
QProgressBar::chunk {{ border-radius: 4px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e66f5, stop:1 #3d95ff); }}

QPlainTextEdit {{ background: {INPUT}; border: 1px solid {BORDER}; border-radius: 9px; padding: 6px;
                  font-family: {mono}; font-size: 9pt; }}
QMenu {{ background: {CARD}; border: 1px solid {BORDER}; padding: 4px; }}
QMenu::item {{ padding: 6px 22px 6px 10px; border-radius: 5px; }}
QMenu::item:selected {{ background: {rgba(BLUE, 0.35)}; }}
QMenu::indicator {{ width: 14px; height: 14px; }}
QMessageBox, QDialog {{ background: {BG}; }}
"""
