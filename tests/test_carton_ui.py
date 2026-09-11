import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QApplication,QPushButton,QTableWidget,QLineEdit,QSpinBox
from agregasi.app import MainWindow
from agregasi.store import Store
from agregasi.template_model import default_document
from agregasi.template_database import product_choices
from agregasi.ui_dialogs import AppDialog


class CartonUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.window=MainWindow(self.store);self.page=self.window.pages['carton'];self.window.navigate('carton');self.window.show();self.app.processEvents()
        self.runtime=self.window.aggregation_runtime;self.templates=self.runtime.repo;doc=default_document('BOX');doc.update(child_product=product_choices(self.store)[0],aggregation_max=1);self.box_id=self.templates.save(doc)
        doc=default_document('CARTON');doc.update(child_template_id=self.box_id,aggregation_min=1,aggregation_max=2);self.carton_id=self.templates.save(doc)
        self.box_codes=[]
        for i in range(3):
            r=self.window.pages['box'].repo.start(self.box_id,self.store.get('batch'),'10/09/2026');r=self.window.pages['box'].repo.scan(r['id'],f'UI-UNIT-{i}');self.runtime.print_result(r['id']);self.box_codes.append(r['parent_code'])
        cfg=self.window.settings_runtime.repo.load();cfg['scanners']['CARTON']['port']='KEYBOARD';self.window.settings_runtime.repo.save(cfg);self.page.refresh()
    def tearDown(self):self.window.close();self.store.close();self.tmp.cleanup();self.app.processEvents()
    def start(self):self.page.template_selector.setCurrentIndex(self.page.template_selector.findData(self.carton_id));self.assertIsNotNone(self.page.run)
    def test_scan_device_duplicate_print_retry_and_navigation_resume(self):
        p=self.page;self.start();self.window.receive_device_scan('CARTON',self.box_codes[0]);self.assertEqual(p.filled,1)
        self.window.receive_device_scan('CARTON',self.box_codes[0]);self.assertEqual(p.filled,1);self.assertIn('duplikat',p.message)
        p.scan_input.setText(self.box_codes[1]);p.scan();self.assertEqual(p.run['state'],'COMPLETE')
        p.print_callback=lambda *args:False;p.buttons['stage_print_label'].click();self.assertEqual(p.run['print_state'],'ERROR')
        printed=[];p.print_callback=lambda doc,*args:printed.append(doc) or True;p.buttons['stage_print_label'].click();self.assertEqual(p.run['print_state'],'SENT');self.assertEqual(printed[0]['data']['quantity'],'2 BOX')
        self.window.navigate('box');self.window.navigate('carton');self.assertEqual(p.filled,2)
        with patch.object(p.settings_runtime,'upload') as upload:
            p.buttons['stage_upload'].click();upload.assert_called_once_with(level='CARTON')
        self.assertNotIn('stage_conveyor',p.buttons)
    def test_target_dialog_creates_list_and_verification_dialog_saves(self):
        p=self.page
        def choose_targets():
            d=next(d for d in self.window.findChildren(AppDialog) if d.isVisible());grid=d.findChild(QTableWidget);grid.item(0,0).setCheckState(Qt.CheckState.Checked)
            next(b for b in d.findChildren(QPushButton) if b.text()=='Simpan list').click();d.accept()
        QTimer.singleShot(100,choose_targets);p.show_targets();self.assertIsNotNone(p.target_list.currentData());self.start()
        p.scan_input.setText(self.box_codes[0]);p.scan();p.buttons['stage_lock'].click();p.print_callback=lambda *args:True;p.buttons['stage_print_label'].click()
        def verify():
            d=p.verification_dialog;d.code.setText(p.run['parent_code']);d.findChild(QSpinBox).setValue(1)
            next(b for b in d.findChildren(QPushButton) if b.text()=='Simpan verifikasi').click()
        QTimer.singleShot(100,verify);p.verify_dialog(p.run);self.assertEqual(p.repo.meta(p.run['id'])['verified'],1)
    def test_pause_reset_and_reopen_keep_saved_children(self):
        p=self.page;self.start();p.scan_input.setText(self.box_codes[0]);p.scan();p.buttons['stage_start_scan'].click();p.scan_input.setText(self.box_codes[1]);p.scan();self.assertEqual(p.filled,1)
        p.buttons['stage_reset'].click();self.assertEqual(p.filled,1);identifier=p.run['id']
        self.window.close();self.window=MainWindow(self.store);self.page=self.window.pages['carton'];self.assertEqual(self.page.run['id'],identifier);self.assertEqual(self.page.child_codes,[self.box_codes[0]])
    def test_grid_can_show_later_groups_without_changing_frame(self):
        p=self.page;doc=self.templates.get(self.carton_id)['document'];doc['aggregation_max']=24;self.templates.save(doc,self.carton_id);p.refresh();self.start();self.assertEqual(len(p.cell_buttons),12);p.buttons['grid_next'].click();self.assertEqual(p.grid_page,1);p.buttons['grid_prev'].click();self.assertEqual(p.grid_page,0)
        from agregasi.sidebar_layout import SIDEBAR
        frames=[];original=p.panel
        def record(*args,**kwargs):frames.append(args[:4]);return original(*args,**kwargs)
        p.panel=record;p.grab();p.panel=original;self.assertIn(SIDEBAR,frames)

if __name__=='__main__':unittest.main()
