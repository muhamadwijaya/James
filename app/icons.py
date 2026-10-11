"""
Vector icon factory.

Icons are defined as small SVG snippets (stroke-based line art, matching the
reference design) and rendered to crisp QIcon / QPixmap at any size and colour.
Using SVG keeps every glyph razor-sharp on HiDPI displays without shipping a
binary icon font.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt, QRectF, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QImage
from PySide6.QtSvg import QSvgRenderer


# Each entry is the *inner* SVG markup drawn on a 24x24 viewbox. "{c}" is
# substituted with the requested stroke colour. Fills use "none" so the line
# weight stays consistent with the mock-up.
_PATHS: dict[str, str] = {
    # --- sidebar navigation ---
    "home": '<path d="M3 11.5 12 4l9 7.5" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
            '<path d="M5.5 10v9.5h13V10" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
            '<path d="M10 20v-5h4v5" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "plug": '<path d="M9 2v5M15 2v5" stroke="{c}" stroke-width="1.8" stroke-linecap="round"/>'
            '<path d="M6.5 7h11v3a5.5 5.5 0 0 1-11 0z" fill="none" stroke="{c}" stroke-width="1.8" stroke-linejoin="round"/>'
            '<path d="M12 15.5V22" stroke="{c}" stroke-width="1.8" stroke-linecap="round"/>',
    "nfc": '<path d="M7 7c3.5-2 6.5-2 10 0 3 1.7 3 7.3 0 9-3.5 2-6.5 2-10 0" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
           '<path d="M8 10.5c2-1 3.8-1 5.8 0 1.7 .9 1.7 3.1 0 4-2 1-3.8 1-5.8 0" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "lf": '<path d="M3 12h2M19 12h2" stroke="{c}" stroke-width="1.8" stroke-linecap="round"/>'
          '<path d="M6.5 8v8M9.5 5.5v13M12 9v6M14.5 5.5v13M17.5 8v8" stroke="{c}" stroke-width="1.8" stroke-linecap="round"/>',
    "hf": '<circle cx="12" cy="12" r="2" fill="{c}"/>'
          '<path d="M8 8a5.5 5.5 0 0 0 0 8M16 8a5.5 5.5 0 0 1 0 8" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round"/>'
          '<path d="M5.5 5.5a9 9 0 0 0 0 13M18.5 5.5a9 9 0 0 1 0 13" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round"/>',
    "card": '<rect x="3" y="5.5" width="18" height="13" rx="2.2" fill="none" stroke="{c}" stroke-width="1.8"/>'
            '<rect x="6" y="9" width="4" height="3" rx="0.6" fill="none" stroke="{c}" stroke-width="1.6"/>'
            '<path d="M6 15h6" stroke="{c}" stroke-width="1.6" stroke-linecap="round"/>',
    "stack": '<path d="M12 3 3 7.5 12 12l9-4.5z" fill="none" stroke="{c}" stroke-width="1.7" stroke-linejoin="round"/>'
             '<path d="M3 12l9 4.5L21 12" fill="none" stroke="{c}" stroke-width="1.7" stroke-linejoin="round"/>'
             '<path d="M3 16.5 12 21l9-4.5" fill="none" stroke="{c}" stroke-width="1.7" stroke-linejoin="round"/>',
    "chip": '<rect x="6" y="6" width="12" height="12" rx="2" fill="none" stroke="{c}" stroke-width="1.8"/>'
            '<rect x="9.5" y="9.5" width="5" height="5" rx="1" fill="none" stroke="{c}" stroke-width="1.6"/>'
            '<path d="M9 3v2.5M15 3v2.5M9 18.5V21M15 18.5V21M3 9h2.5M3 15h2.5M18.5 9H21M18.5 15H21" stroke="{c}" stroke-width="1.6" stroke-linecap="round"/>',
    "terminal": '<rect x="3" y="4.5" width="18" height="15" rx="2.2" fill="none" stroke="{c}" stroke-width="1.8"/>'
                '<path d="M7 9.5l3 2.5-3 2.5" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
                '<path d="M12.5 15h4" stroke="{c}" stroke-width="1.8" stroke-linecap="round"/>',
    "file": '<path d="M6 3h8l4 4v14H6z" fill="none" stroke="{c}" stroke-width="1.8" stroke-linejoin="round"/>'
            '<path d="M14 3v4h4" fill="none" stroke="{c}" stroke-width="1.8" stroke-linejoin="round"/>'
            '<path d="M9 12h6M9 15.5h6" stroke="{c}" stroke-width="1.6" stroke-linecap="round"/>',
    "gear": '<path d="M19.4 13.1a7.5 7.5 0 0 0 0-2.2l2-1.55-2-3.46-2.36 1a7.5 7.5 0 0 0-1.9-1.1L14.8 2.3h-4l-.35 2.5a7.5 7.5 0 0 0-1.9 1.1l-2.36-1-2 3.46 2 1.55a7.5 7.5 0 0 0 0 2.2l-2 1.55 2 3.46 2.36-1a7.5 7.5 0 0 0 1.9 1.1l.35 2.5h4l.35-2.5a7.5 7.5 0 0 0 1.9-1.1l2.36 1 2-3.46z" fill="none" stroke="{c}" stroke-width="1.5" stroke-linejoin="round"/>'
            '<circle cx="12" cy="12" r="3" fill="none" stroke="{c}" stroke-width="1.6"/>',

    # --- card / action icons ---
    "link": '<path d="M9.5 14.5 14.5 9.5" stroke="{c}" stroke-width="1.8" stroke-linecap="round"/>'
            '<path d="M8 12.5 6.5 14a3.2 3.2 0 0 0 4.5 4.5l1.5-1.5" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
            '<path d="M16 11.5 17.5 10a3.2 3.2 0 0 0-4.5-4.5L11.5 7" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "bolt": '<path d="M13 2 4 13h6l-1 9 9-11h-6z" fill="{c}" stroke="{c}" stroke-width="1.2" stroke-linejoin="round"/>',
    "radio": '<circle cx="12" cy="12" r="2" fill="{c}"/>'
             '<path d="M8.5 8.5a5 5 0 0 0 0 7M15.5 8.5a5 5 0 0 1 0 7" fill="none" stroke="{c}" stroke-width="1.7" stroke-linecap="round"/>'
             '<path d="M6 6a9 9 0 0 0 0 12M18 6a9 9 0 0 1 0 12" fill="none" stroke="{c}" stroke-width="1.7" stroke-linecap="round"/>',
    "scan": '<rect x="7" y="7" width="10" height="10" rx="2" fill="none" stroke="{c}" stroke-width="1.7"/>'
            '<rect x="10" y="10" width="4" height="4" rx="1" fill="{c}"/>'
            '<path d="M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8M16 4h2.5A1.5 1.5 0 0 1 20 5.5V8M20 16v2.5a1.5 1.5 0 0 1-1.5 1.5H16M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16" stroke="{c}" stroke-width="1.7" stroke-linecap="round"/>',
    "shield": '<path d="M12 3 5 6v5c0 4.2 2.9 7.6 7 9 4.1-1.4 7-4.8 7-9V6z" fill="none" stroke="{c}" stroke-width="1.7" stroke-linejoin="round"/>'
              '<circle cx="12" cy="11" r="2.4" fill="none" stroke="{c}" stroke-width="1.6"/>',
    "refresh2": '<path d="M20 11a8 8 0 0 0-13.3-4.9L4 8.5" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
                '<path d="M4 13a8 8 0 0 0 13.3 4.9L20 15.5" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
                '<path d="M4 4v4.5h4.5M20 20v-4.5h-4.5" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "sniff": '<path d="M4 9.5h4l7-4.5v14l-7-4.5H4z" fill="none" stroke="{c}" stroke-width="1.7" stroke-linejoin="round"/>'
             '<path d="M18 8.5a5 5 0 0 1 0 7" fill="none" stroke="{c}" stroke-width="1.7" stroke-linecap="round"/>',
    "refresh": '<path d="M20 11a8 8 0 0 0-13.3-4.9L4 8.5" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
               '<path d="M4 13a8 8 0 0 0 13.3 4.9L20 15.5" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
               '<path d="M4 4v4.5h4.5M20 20v-4.5h-4.5" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "play": '<path d="M8 5.5v13l11-6.5z" fill="{c}" stroke="{c}" stroke-width="1.2" stroke-linejoin="round"/>',
    "write": '<path d="M4 20h16" stroke="{c}" stroke-width="1.8" stroke-linecap="round"/>'
             '<path d="M14.5 5.5 18.5 9.5 9 19l-4.5 1 1-4.5z" fill="none" stroke="{c}" stroke-width="1.7" stroke-linejoin="round"/>',
    "dump": '<path d="M12 3v10m0 0 4-4m-4 4-4-4" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
            '<path d="M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "restore": '<path d="M12 21V11m0 0 4 4m-4-4-4 4" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
               '<path d="M4 9V5a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v4" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "format": '<rect x="4" y="4" width="16" height="16" rx="2.4" fill="none" stroke="{c}" stroke-width="1.7"/>'
              '<path d="M8 12l2.5 2.5L16 9" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "keyA": '<circle cx="8.5" cy="14" r="3.5" fill="none" stroke="{c}" stroke-width="1.7"/>'
            '<path d="M11 11.5 19 3.5M16 6.5l2.5 2.5M14 8.5l2 2" stroke="{c}" stroke-width="1.7" stroke-linecap="round"/>',
    "keyB": '<circle cx="8.5" cy="14" r="3.5" fill="none" stroke="{c}" stroke-width="1.7"/>'
            '<path d="M11 11.5 19 3.5M15.5 7l2.5 2.5" stroke="{c}" stroke-width="1.7" stroke-linecap="round"/>',
    "copy": '<rect x="8" y="8" width="11" height="12" rx="2" fill="none" stroke="{c}" stroke-width="1.7"/>'
            '<path d="M5 16V5a1 1 0 0 1 1-1h9" fill="none" stroke="{c}" stroke-width="1.7" stroke-linecap="round"/>',
    "clear": '<path d="M5 7h14" stroke="{c}" stroke-width="1.7" stroke-linecap="round"/>'
             '<path d="M9 7V5h6v2" fill="none" stroke="{c}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>'
             '<path d="M6.5 7l1 12.5a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1l1-12.5" fill="none" stroke="{c}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>',
    "send": '<path d="M4 11.5 20 4l-6 16-3-7z" fill="{c}" stroke="{c}" stroke-width="1.2" stroke-linejoin="round"/>',
    "expand": '<rect x="4" y="4" width="16" height="16" rx="2.4" fill="none" stroke="{c}" stroke-width="1.7"/>'
              '<path d="M9.5 9.5 14.5 14.5M14.5 10v4.5H10" fill="none" stroke="{c}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>',
    "hexview": '<path d="M5 6h3M5 10h3M5 14h3M5 18h3" stroke="{c}" stroke-width="1.8" stroke-linecap="round"/>'
               '<path d="M11 6h8M11 10h8M11 14h8M11 18h5" stroke="{c}" stroke-width="1.8" stroke-linecap="round"/>',
    "chevron": '<path d="M7 10l5 5 5-5" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "min": '<path d="M5 12h14" stroke="{c}" stroke-width="1.6" stroke-linecap="round"/>',
    "max": '<rect x="5" y="5" width="14" height="14" rx="2" fill="none" stroke="{c}" stroke-width="1.6"/>',
    "close": '<path d="M6 6l12 12M18 6 6 18" stroke="{c}" stroke-width="1.6" stroke-linecap="round"/>',
}


def _svg(name: str, color: str) -> str:
    inner = _PATHS[name].format(c=color)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        f"{inner}</svg>"
    )


def pixmap(name: str, size: int, color: str) -> QPixmap:
    """Render an icon to a QPixmap at device pixel ratio for sharpness."""
    renderer = QSvgRenderer(QByteArray(_svg(name, color).encode("utf-8")))
    scale = 3  # super-sample then downscale for clean anti-aliasing
    img = QImage(size * scale, size * scale, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(p, QRectF(0, 0, size * scale, size * scale))
    p.end()
    pm = QPixmap.fromImage(img.scaled(
        size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    pm.setDevicePixelRatio(1)
    return pm


def icon(name: str, size: int, color: str) -> QIcon:
    return QIcon(pixmap(name, size, color))
