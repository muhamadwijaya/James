"""FRT Cam - entry point."""
import sys

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

import icons
import theme


def app_icon() -> QIcon:
    """Camera on a blue rounded square (same as the sidebar logo)."""
    result = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0, 0, size, size)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor("#4a9bff"))
        g.setColorAt(1, QColor("#1c5ee6"))
        p.setBrush(g)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(r, size * 0.24, size * 0.24)
        inner = int(size * 0.62)
        p.drawPixmap(int((size - inner) / 2), int((size - inner) / 2),
                     icons.pixmap("camera", "#ffffff", inner, 2.0, 1.0))
        p.end()
        result.addPixmap(pm)
    return result


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("FRT Cam")
    app.setStyle("Fusion")
    font = QFont()
    font.setFamilies(theme.FONT_FAMILIES)
    font.setPointSizeF(9)
    app.setFont(font)
    app.setStyleSheet(theme.stylesheet())
    app.setWindowIcon(app_icon())

    from main_window import MainWindow  # after the style is set: widgets read it while building

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
