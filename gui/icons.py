"""Line icons (24x24 SVG, stroke = currentColor) rendered to QPixmap/QIcon in any color."""
from __future__ import annotations

import tempfile
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_PATHS: dict[str, str] = {
    "home": '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h5v-6h4v6h5V10"/>',
    "list": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.5h.01"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.2a2.6 2.6 0 1 1 3.6 2.4c-.7.3-1.1.9-1.1 1.6v.6M12 16.8h.01"/>',
    "wifi": '<path d="M2.5 9a14 14 0 0 1 19 0"/><path d="M5.5 12.5a9.5 9.5 0 0 1 13 0"/>'
            '<path d="M8.7 15.9a5 5 0 0 1 6.6 0"/><path d="M12 19.3h.01"/>',
    "gear": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1'
            'a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3'
            'l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1'
            'a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9'
            'a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8'
            'l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    "play": '<path d="M7 4.5l12 7.5-12 7.5z" fill="currentColor"/>',
    "stop": '<rect x="5.5" y="5.5" width="13" height="13" rx="2" fill="currentColor"/>',
    "download": '<path d="M12 3v12M7 10l5 5 5-5"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
    "file_check": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>'
                  '<path d="M9 14.5l2 2 4-4"/>',
    "copy": '<rect x="8" y="8" width="12" height="12" rx="2"/>'
            '<path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
    "file_x": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>'
              '<path d="M10 12.5l4 4M14 12.5l-4 4"/>',
    "file_text": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>'
                 '<path d="M9 13h6M9 17h6"/>',
    "alert": '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5M12 16.5h.01"/>',
    "link": '<path d="M10 14a5 5 0 0 0 7.1 0l3-3a5 5 0 0 0-7.1-7.1l-1.2 1.2"/>'
            '<path d="M14 10a5 5 0 0 0-7.1 0l-3 3a5 5 0 0 0 7.1 7.1l1.2-1.2"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M20.5 20.5l-4.5-4.5"/>',
    "eye": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "eye_off": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'
               '<path d="M3 3l18 18"/>',
    "zoom_in": '<circle cx="11" cy="11" r="7"/><path d="M20.5 20.5l-4.5-4.5M11 8v6M8 11h6"/>',
    "zoom_out": '<circle cx="11" cy="11" r="7"/><path d="M20.5 20.5l-4.5-4.5M8 11h6"/>',
    "fullscreen": '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
    "chevron_left": '<path d="M15 18l-6-6 6-6"/>',
    "chevron_right": '<path d="M9 18l6-6-6-6"/>',
    "chevron_down": '<path d="M6 9l6 6 6-6"/>',
    "chevron_up": '<path d="M6 15l6-6 6 6"/>',
    "tag": '<path d="M3 12.5V4a1 1 0 0 1 1-1h8.5l8.5 8.5-9.5 9.5z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "pin": '<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    "gauge": '<path d="M4 18a8 8 0 1 1 16 0"/><path d="M12 14l3.5-4"/>',
    "grid": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 12h18M12 3v18"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-9 9"/>',
    "activity": '<path d="M2 12h4l2.5-6 4.5 12 2.5-6H22"/>',
    "sparkle": '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8"/>',
    "camera": '<path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/>'
              '<circle cx="12" cy="13.5" r="3.5"/>',
    "rename": '<path d="M4 6h16M4 12h11M4 18h7"/><path d="M17 15l3 3-3 3"/>',
    "minimize": '<path d="M5 12h14"/>',
    "maximize": '<rect x="5" y="5" width="14" height="14" rx="1.5"/>',
    "restore": '<rect x="5" y="8" width="11" height="11" rx="1.5"/><path d="M8 8V6a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-2"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "trash": '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
    "open": '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    "server": '<rect x="3" y="4" width="18" height="7" rx="1.5"/><rect x="3" y="13" width="18" height="7" rx="1.5"/>'
              '<path d="M7 7.5h.01M7 16.5h.01"/>',
}


def _svg(name: str, color: str, stroke: float) -> bytes:
    body = _PATHS[name].replace("currentColor", color)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>').encode()


@lru_cache(maxsize=512)
def pixmap(name: str, color: str = "#e8eef8", size: int = 18, stroke: float = 2.0, dpr: float = 2.0) -> QPixmap:
    px = int(round(size * dpr))
    image = QImage(px, px, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(QByteArray(_svg(name, color, stroke)))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, px, px))
    painter.end()
    result = QPixmap.fromImage(image)
    result.setDevicePixelRatio(dpr)
    return result


def icon(name: str, color: str = "#e8eef8", size: int = 18, stroke: float = 2.0) -> QIcon:
    return QIcon(pixmap(name, color, size, stroke))


_EXPORT_DIR = Path(tempfile.gettempdir()) / "frtcam_icons_v1"


def file_url(name: str, color: str, size: int = 14, stroke: float = 2.4) -> str:
    """PNG on disk for Qt style sheets (url(...)); a @2x variant is written for HiDPI screens."""
    stem = f"{name}_{color.lstrip('#')}_{size}_{stroke}"
    target = _EXPORT_DIR / f"{stem}.png"
    try:
        _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            pixmap(name, color, size, stroke, 1.0).save(str(target), "PNG")
        hi = _EXPORT_DIR / f"{stem}@2x.png"
        if not hi.exists():
            image = pixmap(name, color, size, stroke, 2.0).toImage()
            image.setDevicePixelRatio(1.0)
            image.save(str(hi), "PNG")
    except OSError:
        return ""
    return target.as_posix()
