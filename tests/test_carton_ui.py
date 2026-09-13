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
from agregasi.ui_dialogs import AppDialog,MessageBox


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
    def start(self,identifier=None):
        p=self.page;p.template_selector.setCurrentIndex(p.template_selector.findData(identifier or self.carton_id))
        self.assertIsNone(p.run);p.local_action('stage_lock');self.assertIsNotNone(p.run)
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
    def test_box_child_template_follows_stage_one_batch_and_list(self):
        p=self.page;product=product_choices(self.store)[0]
        self.assertEqual([r['batch'] for r in p.repo.pending_batches(product,self.box_id)],[self.store.get('batch')])
        self.start()
        # Product, batch and target list are taken from the stage-1 aggregation.
        self.assertTrue(p.auto_child);self.assertEqual(p.product.text(),product['name'])
        self.assertEqual(p.batch.currentText(),self.store.get('batch'));self.assertFalse(p.batch.isEditable())
        self.assertFalse(p.batch.isEnabled());self.assertFalse(p.target_list.isEnabled())
        self.assertIn('OTOMATIS',p.target_list.currentText());self.assertIn('3 box',p.target_list.currentText())
        self.assertIsNone(p.target_list.currentData());self.assertIsNone(p.repo.meta(p.run['id'])['list_id'])
        p.scan_input.setText(self.box_codes[0]);p.scan();self.assertEqual(p.filled,1)
        # An aggregated box leaves the pending list of stage 1.
        self.assertEqual(p.repo.pending_batches(product,self.box_id)[0]['quantity'],2)
        codes={row['code'] for row in p.repo.candidates(product,self.store.get('batch'),self.box_id)}
        self.assertEqual(codes,set(self.box_codes[1:]))
        QTimer.singleShot(100,lambda:next(d for d in self.window.findChildren(AppDialog) if d.isVisible()).accept())
        p.show_targets()

    def test_direct_child_template_lets_batch_and_unit_list_be_chosen(self):
        p=self.page;product=product_choices(self.store)[0]
        doc=default_document('CARTON');doc.update(child_level='UNIT',child_product=product,aggregation_min=1,aggregation_max=2)
        direct=self.templates.save(doc)
        path=Path(self.tmp.name)/'unit-list.csv';path.write_text('serial\nDU-1\nDU-2\n')
        list_id=self.window.pages['box'].repo.import_targets(path,product,self.store.get('batch'));p.refresh()
        p.template_selector.setCurrentIndex(p.template_selector.findData(direct))
        # Choosing a template no longer opens the session, so batch and list stay editable.
        self.assertIsNone(p.run);self.assertEqual(p.buttons['stage_lock'].text(),'KUNCI DATA')
        self.assertFalse(p.auto_child);self.assertTrue(p.batch.isEditable())
        self.assertTrue(p.batch.isEnabled());self.assertTrue(p.target_list.isEnabled())
        self.assertEqual(p.target_list.itemText(1),'unit-list | 2 unit')
        p.target_list.setCurrentIndex(p.target_list.findData(list_id));p.local_action('stage_lock')
        self.assertIsNotNone(p.run);self.assertEqual(p.repo.meta(p.run['id'])['list_id'],list_id)
        p.scan_input.setText('OUTSIDE');p.scan();self.assertIn('tidak terdaftar',p.message)
        p.scan_input.setText('DU-1');p.scan();self.assertEqual(p.filled,1)

    def test_verification_dialog_saves(self):
        p=self.page;self.start()
        p.scan_input.setText(self.box_codes[0]);p.scan();p.print_callback=lambda *args:True
        # Below the maximum the PRINT LABEL button closes the carton after a confirmation.
        with patch('agregasi.carton_page.MessageBox.question',return_value=MessageBox.StandardButton.Yes):
            p.buttons['stage_print_label'].click()
        self.assertEqual(p.run['state'],'COMPLETE');self.assertEqual(p.run['print_state'],'SENT')
        def verify():
            d=p.verification_dialog;d.code.setText(p.run['parent_code']);d.findChild(QSpinBox).setValue(1)
            next(b for b in d.findChildren(QPushButton) if b.text()=='Simpan verifikasi').click()
        QTimer.singleShot(100,verify);p.verify_dialog(p.run);self.assertEqual(p.repo.meta(p.run['id'])['verified'],1)
    def test_pause_reset_and_reopen_keep_saved_children(self):
        p=self.page;self.start();p.scan_input.setText(self.box_codes[0]);p.scan();p.buttons['stage_start_scan'].click();p.scan_input.setText(self.box_codes[1]);p.scan();self.assertEqual(p.filled,1)
        p.buttons['stage_lock'].click();self.assertIn('berisi child',p.message);self.assertIsNotNone(p.run)
        p.buttons['stage_reset'].click();self.assertEqual(p.filled,1);identifier=p.run['id']
        self.window.close();self.window=MainWindow(self.store);self.page=self.window.pages['carton'];self.assertEqual(self.page.run['id'],identifier);self.assertEqual(self.page.child_codes,[self.box_codes[0]])
    def test_grid_can_show_later_groups_without_changing_frame(self):
        p=self.page;doc=self.templates.get(self.carton_id)['document'];doc['aggregation_max']=24;self.templates.save(doc,self.carton_id);p.refresh();self.start();self.assertEqual(len(p.cell_buttons),12);p.buttons['grid_next'].click();self.assertEqual(p.grid_page,1);p.buttons['grid_prev'].click();self.assertEqual(p.grid_page,0)
        from agregasi.sidebar_layout import SIDEBAR
        frames=[];original=p.panel
        def record(*args,**kwargs):frames.append(args[:4]);return original(*args,**kwargs)
        p.panel=record;p.grab();p.panel=original;self.assertIn(SIDEBAR,frames)

if __name__=='__main__':unittest.main()
