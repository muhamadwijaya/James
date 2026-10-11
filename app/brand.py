"""
Brand mark renderer.

The reference uses an angular, geometric animal-head emblem drawn in a green
gradient. We reproduce it with inline SVG so it scales cleanly and can be tinted
or sized for both the header wordmark and the sidebar footer card.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt, QRectF
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


_LOGO_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#5bf0a8"/>
      <stop offset="0.55" stop-color="#28c97e"/>
      <stop offset="1" stop-color="#0c6f45"/>
    </linearGradient>
    <linearGradient id="g2" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#7cf7bd"/>
      <stop offset="1" stop-color="#1f9e63"/>
    </linearGradient>
  </defs>
  <!-- left horn -->
  <path d="M60 30 L20 14 L30 40 L46 44 L60 54 Z" fill="url(#g2)"/>
  <!-- right horn -->
  <path d="M60 30 L100 14 L90 40 L74 44 L60 54 Z" fill="url(#g2)"/>
  <!-- left face plane -->
  <path d="M60 36 L42 46 L40 72 L60 108 Z" fill="url(#g)"/>
  <!-- right face plane (slightly darker to add facet depth) -->
  <path d="M60 36 L78 46 L80 72 L60 108 Z" fill="url(#g)" opacity="0.88"/>
  <!-- centre ridge highlight -->
  <path d="M60 40 L54 66 L60 96 L66 66 Z" fill="#8ffbce" opacity="0.55"/>
  <!-- eye cutouts (window colour) -->
  <path d="M49 52 L57 56 L55 64 L48 61 Z" fill="#02110b"/>
  <path d="M71 52 L63 56 L65 64 L72 61 Z" fill="#02110b"/>
  <!-- snout notch -->
  <path d="M60 74 L55 84 L60 98 L65 84 Z" fill="#03140d"/>
</svg>
"""


def logo_pixmap(size: int) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(_LOGO_SVG.encode("utf-8")))
    scale = 3
    img = QImage(size * scale, size * scale, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(p, QRectF(0, 0, size * scale, size * scale))
    p.end()
    return QPixmap.fromImage(
        img.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))


_DEVICE_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 150">
  <defs>
    <linearGradient id="body" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#424b55"/>
      <stop offset="1" stop-color="#20272e"/>
    </linearGradient>
  </defs>
  <!-- board body, slight isometric -->
  <path d="M35 60 L120 40 L180 72 L95 96 Z" fill="url(#body)" stroke="#59646f" stroke-width="1.6"/>
  <path d="M35 60 L35 78 L95 114 L95 96 Z" fill="#171d23" stroke="#59646f" stroke-width="1.3"/>
  <path d="M180 72 L180 90 L95 114 L95 96 Z" fill="#232b32" stroke="#59646f" stroke-width="1.3"/>
  <!-- usb connector -->
  <path d="M110 34 L130 30 L138 36 L118 40 Z" fill="#30373e" stroke="#59646f" stroke-width="1"/>
  <!-- antenna ports -->
  <circle cx="60" cy="68" r="6" fill="#12161b" stroke="#6b7680" stroke-width="1.5"/>
  <circle cx="150" cy="74" r="5" fill="#12161b" stroke="#6b7680" stroke-width="1.5"/>
  <!-- bull emblem hint on board -->
  <path d="M108 65 L99 61 L103 70 L108 73 L113 70 L117 61 Z" fill="#2ee89c"/>
</svg>
"""


def device_pixmap(w: int, h: int) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(_DEVICE_SVG.encode("utf-8")))
    scale = 3
    img = QImage(w * scale, h * scale, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(p, QRectF(0, 0, w * scale, h * scale))
    p.end()
    return QPixmap.fromImage(
        img.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
