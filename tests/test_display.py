"""Regression gates for shared sidebar and persisted display settings."""
import os,tempfile,unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QPushButton
from PySide6.QtCore import Qt,QRect
from PySide6.QtTest import QTest
from agregasi.app import MainWindow
from agregasi.store import Store
from agregasi.dashboard import BASE
from agregasi.settings_model import SettingsRepository,defaults,validate
from agregasi.display_preferences import RESOLUTIONS,display_defaults
from agregasi.shared_sidebar import data_for,SECTIONS

class DisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setStyle('Fusion');cls.app.setStyleSheet((BASE/'styles/theme.qss').read_text())
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.window=MainWindow(self.store);self.window.show();self.app.processEvents()
    def tearDown(self):
        self.window.close();self.app.processEvents();self.store.close();self.tmp.cleanup()
    def test_all_reference_resolutions_fit_all_pages(self):
        for resolution in RESOLUTIONS:
            width,height=map(int,resolution.split(' x '));self.window.resize(width,height)
            for key in self.window.PAGES:
                self.window.navigate(key);self.app.processEvents();view=self.window.views[key]
                with self.subTest(resolution=resolution,page=key):
                    self.assertEqual(view.proxy.boundingRect(),view.sceneRect())
                    bounds=view.mapFromScene(view.proxy.sceneBoundingRect()).boundingRect()
                    viewport=view.viewport().rect()
                    for actual,expected in zip((bounds.left(),bounds.top(),bounds.right(),bounds.bottom()),(viewport.left(),viewport.top(),viewport.right(),viewport.bottom())):
                        self.assertLessEqual(abs(actual-expected),1)
                    self.assertAlmostEqual(view.transform().m11(),view.transform().m22(),places=8)
                    self.assertTrue(view.viewport().rect().adjusted(-1,-1,1,1).contains(bounds))
                    self.assertFalse(view.horizontalScrollBar().isVisible());self.assertFalse(view.verticalScrollBar().isVisible())
    def test_appearance_is_internal_and_device_fields_are_hidden(self):
        self.window.navigate('settings');page=self.window.pages['settings'];page.show_display_tab(True);self.app.processEvents()
        self.assertTrue(page.appearance_panel.isVisible());self.assertTrue(page.line_name.isVisibleTo(page)==False)
        page.show_display_tab(False);self.assertTrue(page.line_name.isVisibleTo(page));self.assertFalse(page.appearance_panel.isVisible())
    def test_preferences_persist_without_scaling_drift(self):
        page=self.window.pages['settings'];p=page.appearance_panel
        p.controls['font_scale'].setValue(115);p.controls['icon_scale'].setValue(120);p.controls['density'].setCurrentText('LEGA');p.controls['hover'].setChecked(False);p.save();self.app.processEvents()
        cfg=SettingsRepository(self.store).load()['display'];self.assertEqual(cfg['font_scale'],115);self.assertEqual(cfg['icon_scale'],120);self.assertFalse(cfg['hover'])
        self.assertEqual(self.window.pages['box'].scan_table.verticalHeader().defaultSectionSize(),28)
        p.populate(display_defaults());p.save();p.controls['density'].setCurrentText('LEGA');p.save()
        self.assertEqual(self.window.pages['box'].scan_table.verticalHeader().defaultSectionSize(),28)
        self.assertEqual(self.window.current_page,'dashboard')
    def test_native_size_mode_can_scroll_to_every_element(self):
        cfg=self.window.pages['settings'].repo.load();cfg['display']['fit']='UKURAN ASLI (SCROLL)';self.window.pages['settings'].repo.save(cfg);self.window.apply_display_preferences();self.window.resize(800,600);self.app.processEvents()
        view=self.window.views['dashboard'];self.assertEqual(view.transform().m11(),1)
        self.assertTrue(view.verticalScrollBar().isVisible());self.assertTrue(view.horizontalScrollBar().isVisible())
        view.ensureVisible(QRect(1350,1000,60,60));self.app.processEvents();self.assertGreater(view.verticalScrollBar().value(),0)
    def test_sidebar_layout_and_shortcut_actions_are_shared(self):
        baseline=None
        for key in self.window.PAGES:
            self.window.navigate(key);self.app.processEvents();page=self.window.pages[key];img=page.grab().toImage()
            # Borders have exactly the same coordinates and pixels on all pages.
            sx,sy=page.canvas_factors
            pixels=tuple(img.pixelColor(round(1115*sx),round((y+height//2)*sy)).name() for y,height in SECTIONS)
            if baseline is None:baseline=pixels
            self.assertEqual(pixels,baseline,key)
            b=page.findChild(QPushButton,'shortcut_database')
            expected=self.window.views[key].surface.design_rect(QRect(1118,925,54,51)).toRect()
            self.assertLessEqual(abs(b.geometry().x()-expected.x()),1);self.assertLessEqual(abs(b.geometry().width()-expected.width()),1)
            b.click();self.assertEqual(self.window.current_page,'settings')
        self.window.pages['settings'].show_display_tab(True);self.window.pages['settings'].findChild(QPushButton,'shortcut_printer').click();self.assertFalse(self.window.pages['settings'].appearance_panel.isVisible())
    def test_sidebar_uses_page_specific_live_values(self):
        for key in ('box','carton','pallet'):
            data=data_for(self.window.pages[key]);self.assertEqual(data['total'],0);self.assertEqual(data['rate'],0);self.assertEqual(data['unit'],key)
        self.assertEqual(data_for(self.window.pages['settings'])['detail_title'],'TAMPILAN APLIKASI')
    def test_defaults_migrate_and_invalid_display_is_rejected(self):
        self.assertEqual(validate({'line':'EXISTING'})['display'],display_defaults())
        for key,value in [('resolution','9000 x 5000'),('font_scale',300),('icon_scale',0),('density','invalid'),('hover','yes')]:
            cfg=defaults();cfg['display'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate(cfg)

if __name__=='__main__':unittest.main()
