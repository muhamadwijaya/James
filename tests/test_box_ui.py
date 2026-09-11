import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from agregasi.app import MainWindow
from agregasi.store import Store


class BoxUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.window=MainWindow(self.store);self.page=self.window.pages['box'];self.window.navigate('box')
        cfg=self.window.settings_runtime.repo.load();cfg['scanners']['BOX']['port']='KEYBOARD';self.window.settings_runtime.repo.save(cfg)
    def tearDown(self):self.window.close();self.store.close();self.tmp.cleanup();self.app.processEvents()
    def start(self):self.page.template_selector.setCurrentIndex(1);self.assertIsNotNone(self.page.run)
    def test_empty_screen_pause_reset_and_resume_controls(self):
        p=self.page;self.assertEqual(p.filled,0);self.assertEqual(len(p.cell_buttons),50);self.start()
        p.scan_input.setText('UNIT-1');p.scan();self.assertEqual(p.filled,1)
        p.local_action('stage_start_scan');p.scan_input.setText('UNIT-2');p.scan();self.assertEqual(p.filled,1)
        p.scan_input.clear();p.local_action('stage_start_scan');p.scan_input.setText('UNIT-2');p.scan();self.assertEqual(p.filled,2)
        p.local_action('stage_reset');self.assertEqual(p.filled,2);self.assertIn('berisi child',p.message)
        p.local_action('stage_lock');p.print_callback=lambda *args:True;p.local_action('stage_print_label');p.local_action('stage_reset')
        self.assertIsNone(p.run);self.assertEqual(p.filled,0)
        for control in (p.product,p.batch,p.target_list,p.template_selector,p.mfd):self.assertTrue(control.isEnabled())
    def test_device_scan_upload_conveyor_and_failed_printer(self):
        p=self.page;self.start();self.window.receive_device_scan('BOX','UNIT-DEVICE');self.assertEqual(p.filled,1)
        p.local_action('stage_lock')
        def fail(*args):raise ValueError('Printer unplugged')
        p.print_callback=fail;p.local_action('stage_print_label');self.assertEqual(p.run['print_state'],'ERROR');self.assertIn('Printer unplugged',p.message)
        with patch.object(p.settings_runtime,'upload') as upload,patch.object(p.settings_runtime,'conveyor') as conveyor:
            p.buttons['stage_upload'].click();upload.assert_called_once_with(level='BOX');p.buttons['stage_conveyor'].click();conveyor.assert_called_once()
    def test_navigation_and_reopen_keep_open_session(self):
        p=self.page;self.start();p.scan_input.setText('PERSIST-U1');p.scan();identifier=p.run['id'];self.window.navigate('settings');self.window.navigate('box');self.assertEqual(p.run['id'],identifier);self.assertEqual(p.filled,1)
        self.window.close();self.window=MainWindow(self.store);self.page=self.window.pages['box'];self.assertEqual(self.page.run['id'],identifier);self.assertEqual(self.page.child_codes,['PERSIST-U1'])

if __name__=='__main__':unittest.main()
