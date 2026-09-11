import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QPushButton

from agregasi.app import MainWindow
from agregasi.dashboard import BASE
from agregasi.pages import OperationPage
from agregasi.store import Store
from agregasi.navigation import FOOTER, ITEMS, button_rect


class UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')
        cls.app.setStyleSheet((BASE / 'styles/theme.qss').read_text(encoding='utf-8'))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'db.sqlite3')
        self.window = MainWindow(self.store)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.store.close()
        self.tmp.cleanup()
        self.app.processEvents()

    def test_sidebar_frame_stays_fixed_across_navigation(self):
        from agregasi.sidebar_layout import SIDEBAR
        from PySide6.QtCore import QRect
        bounds = QRect(*SIDEBAR)
        for key, page in self.window.pages.items():
            with self.subTest(page=key):
                calls = []
                original = page.panel
                def record(*args, **kwargs):
                    calls.append(tuple(args[:4]))
                    return original(*args, **kwargs)
                page.panel = record
                try:
                    self.window.navigate(key)
                    self.app.processEvents()
                    page.grab()
                finally:
                    page.panel = original
                self.assertIn(SIDEBAR, calls)
                for button in page.findChildren(QPushButton):
                    if button.isVisible() and (button.objectName().startswith('shortcut_') or button.objectName().startswith('template_connection_')):
                        self.assertTrue(bounds.contains(button.geometry()), (key, button.objectName()))

    def test_all_navigation_is_internal_pages(self):
        expected = ('dashboard', 'box', 'carton', 'pallet', 'revision', 'send', 'settings', 'template')
        dash_buttons = self.window.pages['dashboard'].controls.findChildren(QPushButton)
        self.assertEqual(len(dash_buttons), 46)
        for key in expected:
            button = self.window.pages['dashboard'].controls.findChild(QPushButton, 'nav_' + key)
            self.assertIsNotNone(button, key)
            button.click()
            self.app.processEvents()
            self.assertEqual(self.window.current_page, key)
            self.assertIs(self.window.host.currentWidget(), self.window.views[key])
            self.assertEqual(self.window.findChildren(QDialog), [])

    def test_stage_scan_enter_records_once_and_duplicate(self):
        page = self.window.pages['box']
        self.assertIsInstance(page, OperationPage)
        page.template_selector.setCurrentIndex(1)
        page.local_action('stage_lock')
        before = len(self.store.events())
        page.scan_input.setText('UNIT-UI-001')
        QTest.keyClick(page.scan_input, Qt.Key.Key_Return)
        self.app.processEvents()
        self.assertEqual(len(self.store.events()), before + 1)
        self.assertEqual(self.store.events()[0]['status'], 'VALID')
        page.scan_input.setText('UNIT-UI-001')
        page.findChild(QPushButton, 'stage_start_scan').click()
        self.assertEqual(self.store.events()[0]['status'], 'DUPLIKAT')

    def test_responsive_canvas_fills_viewport_without_scrollbars(self):
        for width, height in ((1448, 1086), (1366, 768), (1920, 1080), (820, 600)):
            self.window.resize(width, height)
            self.app.processEvents()
            view = self.window.views['dashboard']
            self.assertAlmostEqual(view.transform().m11(), view.transform().m22(), places=8)
            scene_rect = view.mapFromScene(view.sceneRect()).boundingRect()
            self.assertLessEqual(scene_rect.width(), view.viewport().width() + 1)
            self.assertLessEqual(scene_rect.height(), view.viewport().height() + 1)
            self.assertFalse(view.horizontalScrollBar().isVisible())
            self.assertFalse(view.verticalScrollBar().isVisible())
        self.assertFalse(self.window.pages['dashboard'].grab().isNull())

    def test_settings_page_updates_local_configuration(self):
        page = self.window.pages['settings']
        page.line_name.setText('AGGREGATION-02')
        page.shift.setCurrentText('A (06:00 - 14:00)')
        page.findChild(QPushButton, 'save_settings').click()
        self.assertEqual(self.store.get('line'), 'AGGREGATION-02')
        self.assertEqual(self.store.get('shift'), 'A')

    def test_navigation_click_targets_and_colours_match_across_pages(self):
        self.window.resize(1366, 768)
        self.app.processEvents()
        active_colours = None
        inactive_colours = None
        for index in list(range(len(ITEMS))) + [0, 7, 1]:
            key = ITEMS[index][0]
            view = self.window.views[self.window.current_page]
            QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                             pos=view.mapFromScene(button_rect(index).center()))
            self.app.processEvents()
            self.assertEqual(self.window.current_page, key)
            page = self.window.pages[key]
            page.navigation.hovered = None
            page.navigation.keyboard_focus = None
            image = page.grab().toImage()
            for j, (name, _, _) in enumerate(ITEMS):
                rect = button_rect(j)
                self.assertTrue(FOOTER.contains(rect))
                button = page.findChild(QPushButton, 'nav_' + name)
                self.assertEqual(button.geometry(), rect)
                self.assertEqual(button.isChecked(), name == key, f'{key}: {name}')
                # Clear space, away from icon/text and the rounded border.
                colours = tuple(image.pixelColor(rect.x()+8, rect.y()+offset).name()
                                for offset in (9, 55))
                if name == key:
                    if active_colours is None:
                        active_colours = colours
                    self.assertEqual(colours, active_colours)
                else:
                    if inactive_colours is None:
                        inactive_colours = colours
                    self.assertEqual(colours, inactive_colours)
        self.assertNotEqual(active_colours, inactive_colours)

    def test_entire_footer_has_identical_rendering_on_every_page(self):
        reference = None
        for key, page in self.window.pages.items():
            self.window.navigate(key)
            self.app.processEvents()
            page.navigation.hovered = page.navigation.keyboard_focus = None
            original = page.active
            try:
                # Same selection isolates visual drift between page classes.
                page.active = 'template'
                footer = page.grab(FOOTER).toImage()
                if reference is None:
                    reference = footer
                self.assertEqual(footer, reference, key)
            finally:
                page.active = original

    def test_revision_search_and_filter_use_real_controls(self):
        page = self.window.pages['revision']
        # Revision search now uses its actual level-specific field.
        page.box.setText('BOX-250501-0006')
        page.search_button.click()
        self.app.processEvents()
        self.assertGreaterEqual(page.grid.rowCount(), 1)
        page.status_filter.setCurrentText('REJECT')
        self.app.processEvents()
        self.assertEqual(page.grid.rowCount(), 0)


if __name__ == '__main__':
    unittest.main()
