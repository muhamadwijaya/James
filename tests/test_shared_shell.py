"""Render and interaction regressions for page-to-page layout consistency."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QRectF, QPoint, Qt
from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtTest import QTest
from agregasi.app import MainWindow
from agregasi.store import Store
from agregasi.dashboard import BASE
from agregasi.display_preferences import configure_display, display_defaults
from agregasi.typography import draw_text


class SharedShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')
        cls.app.setStyleSheet((BASE / 'styles/theme.qss').read_text())

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'db')
        self.window = MainWindow(self.store)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        configure_display(display_defaults())
        self.window.close()
        self.app.processEvents()
        self.store.close()
        self.tmp.cleanup()

    def test_rendered_header_fonts_and_positions_stay_identical(self):
        for scale in (100, 115):
            configure_display(dict(display_defaults(), font_scale=scale))
            for size in ((1920, 1280), (1920, 1080), (1366, 768), (800, 600)):
                self.window.resize(*size)
                baseline = None
                for key in self.window.PAGES:
                    self.window.navigate(key)
                    self.app.processEvents()
                    page = self.window.pages[key]
                    rendered = []
                    def capture(*args, **kwargs):
                        result = draw_text(*args, **kwargs)
                        rendered.append(result)
                        return result
                    with patch('agregasi.typography.draw_text', side_effect=capture):
                        image = page.grab().toImage()
                    # paint_header calls the same renderer three times first.
                    signature = [(r[0].toString(), r[2].getRect()) for r in rendered[:3]]
                    logo = image.copy(0, 0, round(600 * page.canvas_factors[0]), 42)
                    if baseline is None:
                        baseline = signature, logo
                    self.assertEqual(signature, baseline[0], (scale, size, key))
                    self.assertEqual(logo, baseline[1], (scale, size, key))

    def test_painted_body_edges_and_all_eight_navigation_targets(self):
        for size in ((1920, 1280), (1920, 1080), (1366, 768), (800, 600)):
            self.window.resize(*size)
            for index, key in enumerate(self.window.PAGES):
                self.window.navigate(key)
                self.app.processEvents()
                QTest.qWait(20)
                page = self.window.pages[key]
                view = self.window.views[key]
                panel_rects = []
                method = 'reference_panel' if key == 'template' else 'panel'
                original = getattr(page, method)
                def capture(x, y, w, h, *args, **kwargs):
                    if x < 1106:
                        panel_rects.append(page.p.worldTransform().mapRect(QRectF(x, y, w, h)))
                    return original(x, y, w, h, *args, **kwargs)
                with patch.object(page, method, side_effect=capture):
                    page.grab()
                envelope = QRectF()
                for rect in panel_rects:
                    envelope = envelope.united(rect)
                sx, sy = page.canvas_factors
                self.assertAlmostEqual(envelope.left() / sx, 15, places=5, msg=key)
                self.assertAlmostEqual(envelope.top() / sy, 83, places=5, msg=key)
                self.assertAlmostEqual(envelope.right() / sx, 1095, places=5, msg=key)
                if key != 'settings':
                    self.assertAlmostEqual(envelope.bottom() / sy, 985, places=5, msg=key)
                buttons = list(page.navigation.buttons.values())
                widths = [b.width() for b in buttons]
                self.assertLessEqual(max(widths) - min(widths), 1)
                self.assertEqual(len({b.height() for b in buttons}), 1)
                self.assertEqual(len({b.y() for b in buttons}), 1)
                self.assertGreater(buttons[0].x(), 0)
                self.assertLess(buttons[-1].geometry().right(), page.width())
                # Use actual viewport mouse input, including the last menu.
                target_key = self.window.PAGES[(index + 1) % 8]
                button = page.navigation.buttons[target_key]
                point = button.mapTo(page, button.rect().center())
                QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                                 pos=view.mapFromScene(point))
                self.app.processEvents()
                self.assertEqual(self.window.current_page, target_key)

    def test_appearance_and_template_controls_follow_their_panels_without_drift(self):
        for size in ((1920, 1280), (800, 600), (1920, 1280)):
            self.window.resize(*size)
            self.window.navigate('settings')
            settings = self.window.pages['settings']
            settings.show_display_tab(True)
            self.app.processEvents()
            sx, sy = settings.canvas_factors
            rect = settings.appearance_panel.geometry()
            for actual, expected in zip((rect.x(), rect.y(), rect.width(), rect.height()),
                                        (15 * sx, 83 * sy, 1080 * sx, 902 * sy)):
                self.assertLessEqual(abs(actual - expected), 1)
            settings.show_display_tab(False)
            self.assertTrue(settings.line_name.isVisibleTo(settings))
            self.window.navigate('template')
            self.app.processEvents()
            page = self.window.pages['template']
            view = self.window.views['template']
            for level in ('BOX', 'CARTON', 'PALLET'):
                button = page.selectors[level]
                point = button.mapTo(page, button.rect().center())
                QTest.qWait(20)
                QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                                 pos=view.mapFromScene(point))
                self.assertEqual(page.template_kind, level)
                editor = page.active_editor
                for child in (editor.canvas, editor.tabs, editor.list_table):
                    top_left = child.mapTo(page, QPoint(0, 0))
                    self.assertTrue(page.stack.geometry().contains(top_left), child.objectName())
                    self.assertTrue(page.stack.geometry().contains(top_left + QPoint(child.width()-1, child.height()-1)))


if __name__ == '__main__':
    unittest.main()
