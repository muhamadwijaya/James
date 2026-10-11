"""Global Qt stylesheet, generated from the theme palette."""

from __future__ import annotations

from .theme import Color, Font


def build_stylesheet() -> str:
    c = Color
    return f"""
    * {{
        font-family: "{Font.UI}";
        outline: 0;
    }}
    QWidget {{
        color: {c.TEXT_DIM};
        background: transparent;
    }}
    QToolTip {{
        background: {c.CARD};
        color: {c.TEXT};
        border: 1px solid {c.BORDER};
        padding: 5px 8px;
        border-radius: 6px;
    }}

    /* ---- window / surfaces ---- */
    #Root {{ background: {c.WINDOW}; }}
    #Sidebar {{ background: {c.SIDEBAR}; border-right: 1px solid {c.BORDER_SOFT}; }}
    #Header {{ background: {c.HEADER}; border-bottom: 1px solid {c.BORDER_SOFT}; }}
    #Content {{ background: {c.CONTENT}; }}
    #ContentInner {{ background: {c.CONTENT}; }}

    #Card {{
        background: {c.CARD};
        border: 1px solid {c.BORDER};
        border-radius: 14px;
    }}
    #CardGreen {{
        background: {c.CARD};
        border: 1px solid {c.BORDER_GREEN};
        border-radius: 14px;
    }}

    #CardTitle {{ color: {c.TEXT}; background: transparent; }}

    #VSep {{ background: {c.DIVIDER}; border: none; }}
    #HSep {{ background: {c.DIVIDER}; border: none; }}

    /* ---- status pills in header ---- */
    #StatusBox {{
        background: {c.CARD};
        border: 1px solid {c.BORDER};
        border-radius: 12px;
    }}
    #DeviceThumb {{
        background: {c.CARD_ALT};
        border: 1px solid {c.BORDER_GREEN};
        border-radius: 12px;
    }}

    /* ---- scrollbars ---- */
    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{
        background: transparent; width: 10px; margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {c.SCROLL}; border-radius: 5px; min-height: 40px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {c.BORDER_GREEN}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    QScrollBar:horizontal {{
        background: transparent; height: 10px; margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: {c.SCROLL}; border-radius: 5px; min-width: 40px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {c.BORDER_GREEN}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}

    /* ---- combo boxes ---- */
    QComboBox {{
        background: {c.TILE};
        border: 1px solid {c.BORDER};
        border-radius: 8px;
        padding: 6px 10px;
        color: {c.TEXT_DIM};
        min-height: 18px;
    }}
    QComboBox:hover {{ border: 1px solid {c.BORDER_GREEN}; }}
    QComboBox::drop-down {{ border: none; width: 26px; }}
    QComboBox QAbstractItemView {{
        background: {c.CARD};
        border: 1px solid {c.BORDER};
        border-radius: 8px;
        selection-background-color: {c.GREEN_GLOW};
        selection-color: {c.GREEN};
        color: {c.TEXT_DIM};
        padding: 4px;
        outline: 0;
    }}

    /* ---- line edits ---- */
    QLineEdit {{
        background: {c.INPUT};
        border: 1px solid {c.BORDER};
        border-radius: 10px;
        padding: 10px 14px;
        color: {c.TEXT};
        selection-background-color: {c.GREEN_GLOW};
    }}
    QLineEdit:focus {{ border: 1px solid {c.GREEN_DEEP}; }}

    /* ---- generic scroll content ---- */
    QAbstractScrollArea {{ background: transparent; }}
    """
