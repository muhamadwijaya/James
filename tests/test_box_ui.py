import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from agregasi.app import MainWindow
from agregasi.box_page import GRID
from agregasi.store import Store


class BoxUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.window=MainWindow(self.store);self.page=self.window.pages['box'];self.window.navigate('box')
        cfg=self.window.settings_runtime.repo.load();cfg['scanners']['BOX']['port']='KEYBOARD';self.window.settings_runtime.repo.save(cfg)
    def tearDown(self):self.window.close();self.store.close();self.tmp.cleanup();self.app.processEvents()
    def start(self):
        self.page.template_selector.setCurrentIndex(1);self.assertIsNone(self.page.run)
        self.page.local_action('stage_lock');self.assertIsNotNone(self.page.run)
    def use_camera(self,port=8099):
        p=self.page;p.camera_ip_input.setText('127.0.0.1');p.camera_port_input.setValue(port)
        p.scan_mode_select.setCurrentText('KAMERA IP');p.local_action('stage_camera_apply')
    def test_empty_screen_pause_reset_and_resume_controls(self):
        p=self.page;self.assertEqual(p.filled,0);self.assertEqual(len(p.cell_buttons),25);self.start()
        p.scan_input.setText('UNIT-1');p.scan();self.assertEqual(p.filled,1)
        p.local_action('stage_start_scan');p.scan_input.setText('UNIT-2');p.scan();self.assertEqual(p.filled,1)
        p.scan_input.clear();p.local_action('stage_start_scan');p.scan_input.setText('UNIT-2');p.scan();self.assertEqual(p.filled,2)
        p.local_action('stage_reset');self.assertEqual(p.filled,2);self.assertIn('berisi child',p.message)
        p.local_action('stage_close_box');p.print_callback=lambda *args:True;p.local_action('stage_print_label');p.local_action('stage_reset')
        self.assertIsNone(p.run);self.assertEqual(p.filled,0)
        for control in (p.product,p.batch,p.target_list,p.template_selector,p.mfd):self.assertTrue(control.isEnabled())
    def test_template_is_chosen_first_and_lock_toggles_the_session(self):
        p=self.page
        self.assertEqual(p.template_selector.itemText(0),'Pilih template box…')
        self.assertTrue(p.product.isReadOnly());self.assertEqual(p.buttons['stage_lock'].text(),'KUNCI DATA')
        p.local_action('stage_lock');self.assertIsNone(p.run);self.assertIn('template box aktif',p.message)
        p.template_selector.setCurrentIndex(1)
        # The product is a read-only mirror of the template; it is never picked here.
        self.assertEqual(p.product.text(),p.current_product()['name'])
        p.local_action('stage_lock');self.assertIsNotNone(p.run);self.assertEqual(p.buttons['stage_lock'].text(),'BUKA KUNCI DATA')
        for control in p.inputs:self.assertFalse(control.isEnabled())
        p.local_action('stage_lock');self.assertIsNone(p.run)
        for control in p.inputs:self.assertTrue(control.isEnabled())
        p.template_selector.setCurrentIndex(1);p.local_action('stage_lock');p.scan_input.setText('LOCK-1');p.scan()
        p.local_action('stage_lock');self.assertIsNotNone(p.run);self.assertIn('berisi child',p.message)
    def test_grid_keeps_full_cells_and_scrolls_to_the_template_target(self):
        p=self.page;self.start()
        # Cells keep the reference design size; the target maximum decides how many rows exist.
        self.assertEqual((GRID['w'],GRID['h']),(98,74))
        widths={b.width() for b in p.cell_buttons};heights={b.height() for b in p.cell_buttons}
        self.assertLessEqual(max(widths)-min(widths),2);self.assertLessEqual(max(heights)-min(heights),2)
        self.assertEqual(p.cfg['capacity'],50);self.assertEqual(p.grid_rows(),10)
        self.assertTrue(p.grid_scroll.isVisibleTo(p));self.assertEqual(p.grid_scroll.maximum(),5)
        p.grid_scroll.setValue(5);p.grab()
        self.assertEqual(p.cell_buttons[0].toolTip(),'Unit 26')
        p.local_action('box_cell_0');p.grid_scroll.setValue(0)
        repo=self.window.pages['template'].repo;identifier=repo.list('BOX')[0]['id'];doc=repo.get(identifier)['document']
        p.local_action('stage_lock');doc.update(aggregation_min=1,aggregation_max=12);repo.save(doc,identifier)
        p.refresh();p.template_selector.setCurrentIndex(1);p.local_action('stage_lock')
        self.assertEqual(p.grid_rows(),3);self.assertFalse(p.grid_scroll.isVisibleTo(p));self.assertEqual(p.grid_scroll.maximum(),0)

    def test_locked_template_preview_and_master_box_data(self):
        p=self.page;self.start();p.scan_input.setText('UNIT-1');p.scan()
        image=p.preview_image();self.assertIsNotNone(image);self.assertFalse(image.isNull())
        self.assertIsNone(p.pending_box())
        p.print_callback=lambda *args:True;p.local_action('stage_close_box');p.local_action('stage_print_label')
        pending=p.pending_box();self.assertIsNotNone(pending);rows=dict(p.master_rows(pending))
        self.assertEqual(rows['KODE BOX'],p.run['parent_code']);self.assertTrue(rows['ISI BOX'].startswith('1 / '))
        self.assertIn('MENUNGGU VERIFIKASI',rows['STATUS']);self.assertTrue(p.buttons['stage_verify'].isVisibleTo(p))
        p.grab()
    def test_camera_scanner_mode_shows_the_live_view_instead_of_master_data(self):
        p=self.page;self.start()
        # The stage page itself chooses the scan source and stores it in settings.
        self.assertEqual(p.scan_mode_select.currentText(),'SCANNER GUN')
        self.use_camera()
        profile=self.window.settings_runtime.repo.load()['scanners']['BOX']
        self.assertEqual((profile['mode'],profile['camera_ip'],profile['camera_port']),('KAMERA IP','127.0.0.1',8099))
        self.assertTrue(p.camera_ip_input.isVisibleTo(p));self.assertTrue(p.buttons['stage_camera_apply'].isVisibleTo(p))
        self.assertTrue(p.camera_view.isVisibleTo(p));self.assertFalse(p.buttons['stage_verify'].isVisibleTo(p))
        frame=QImage(80,60,QImage.Format.Format_RGB32);frame.fill(0xFFFFFF)
        p.show_camera_frame('CARTON',frame);self.assertTrue(p.camera_view.pixmap().isNull())
        p.show_camera_frame('BOX',frame);self.assertFalse(p.camera_view.pixmap().isNull())
        p.grab()
        p.scan_mode_select.setCurrentText('SCANNER GUN')
        self.assertEqual(self.window.settings_runtime.repo.load()['scanners']['BOX']['mode'],'SCANNER GUN')
        self.assertFalse(p.camera_view.isVisibleTo(p));self.assertTrue(p.buttons['stage_verify'].isVisibleTo(p))
        self.assertFalse(p.camera_ip_input.isVisibleTo(p))
        # The settings page mirrors the choice made on the stage page.
        self.assertEqual(self.window.pages['settings'].controls['scanners.BOX.mode'].currentText(),'SCANNER GUN')
    def test_maximum_target_prints_the_label_automatically(self):
        repo=self.window.pages['template'].repo;identifier=repo.list('BOX')[0]['id'];doc=repo.get(identifier)['document']
        doc.update(aggregation_min=1,aggregation_max=2,print_mode='MANUAL');repo.save(doc,identifier)
        p=self.page;p.refresh();printed=[]
        p.print_callback=lambda document,template_id,automatic:printed.append(automatic) or True
        self.start();self.assertEqual(p.cfg['capacity'],2)
        for code in ('MAX-1','MAX-2'):p.scan_input.setText(code);p.scan()
        self.assertEqual(printed,[True]);self.assertEqual(p.run['print_state'],'SENT');self.assertIn('otomatis',p.message)
    def test_device_scan_upload_and_failed_printer(self):
        p=self.page;self.start();self.window.receive_device_scan('BOX','UNIT-DEVICE');self.assertEqual(p.filled,1)
        p.local_action('stage_close_box')
        def fail(*args):raise ValueError('Printer unplugged')
        p.print_callback=fail;p.local_action('stage_print_label');self.assertEqual(p.run['print_state'],'ERROR');self.assertIn('Printer unplugged',p.message)
        with patch.object(p.settings_runtime,'upload') as upload:
            p.buttons['stage_upload'].click();upload.assert_called_once_with(level='BOX')
        self.assertNotIn('stage_conveyor',p.buttons)
    def test_navigation_and_reopen_keep_open_session(self):
        p=self.page;self.start();p.scan_input.setText('PERSIST-U1');p.scan();identifier=p.run['id'];self.window.navigate('settings');self.window.navigate('box');self.assertEqual(p.run['id'],identifier);self.assertEqual(p.filled,1)
        self.window.close();self.window=MainWindow(self.store);self.page=self.window.pages['box'];self.assertEqual(self.page.run['id'],identifier);self.assertEqual(self.page.child_codes,['PERSIST-U1'])

if __name__=='__main__':unittest.main()
