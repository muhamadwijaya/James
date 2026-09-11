import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json,tempfile,threading,time,unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
from PySide6.QtCore import Qt,QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QPushButton,QTableWidget,QSpinBox
from agregasi.app import MainWindow
from agregasi.store import Store
from agregasi.template_model import default_document,new_element
from agregasi.template_database import product_choices
from agregasi.label_render import render_image
from agregasi.pallet_camera import PalletCamera,decode_frame
from agregasi.ui_dialogs import AppDialog


class PalletUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.window=MainWindow(self.store);self.page=self.window.pages['pallet'];self.window.navigate('pallet');self.window.show();self.app.processEvents()
        self.runtime=self.window.aggregation_runtime;self.templates=self.runtime.repo
        doc=default_document('CARTON');doc.update(child_level='UNIT',child_product=product_choices(self.store)[0],aggregation_max=1);self.carton_id=self.templates.save(doc)
        doc=default_document('PALLET');doc.update(child_template_id=self.carton_id,aggregation_min=1,aggregation_max=2);self.pallet_id=self.templates.save(doc)
        self.carton_codes=[]
        for i in range(3):
            r=self.window.pages['carton'].repo.start(self.carton_id,self.store.get('batch'),'10/09/2026');r=self.window.pages['carton'].repo.scan(r['id'],f'PALLET-UI-UNIT-{i}');self.runtime.print_result(r['id']);self.carton_codes.append(r['parent_code'])
        cfg=self.window.settings_runtime.repo.load();cfg.update(auto_upload=False,retry_count=0);self.window.settings_runtime.repo.save(cfg);self.page.refresh()
    def tearDown(self):self.window.close();self.store.close();self.tmp.cleanup();self.app.processEvents()
    def start(self):self.page.template_selector.setCurrentIndex(self.page.template_selector.findData(self.pallet_id));self.assertIsNotNone(self.page.run)
    def fill(self):
        self.start()
        for code in self.carton_codes[:2]:self.page.scan_input.setText(code);self.page.scan()
    def test_device_scan_duplicate_print_retry_and_navigation(self):
        p=self.page;self.start();self.window.receive_device_scan('PALLET',self.carton_codes[0]);self.assertEqual(p.filled,1)
        self.window.receive_device_scan('PALLET',self.carton_codes[0]);self.assertEqual(p.filled,1);self.assertIn('duplikat',p.message)
        self.window.navigate('carton');self.window.receive_device_scan('PALLET',self.carton_codes[1]);self.assertEqual(p.filled,1);self.window.navigate('pallet')
        self.window.receive_device_scan('PALLET',self.carton_codes[1]);self.assertEqual(p.run['state'],'COMPLETE')
        p.print_callback=lambda *args:False;p.buttons['stage_print_label'].click();self.assertEqual(p.run['print_state'],'ERROR')
        printed=[];p.print_callback=lambda doc,*args:printed.append(doc) or True;p.buttons['stage_print_label'].click();self.assertEqual(p.run['print_state'],'SENT');self.assertEqual(printed[0]['data']['quantity'],'2 CARTON')
        self.assertEqual(p.repo.revisions.get(('PALLET',p.run['parent_code']))['print_state'],'TERKIRIM KE PRINTER')
        with patch.object(p.settings_runtime,'conveyor') as conveyor:p.buttons['stage_conveyor'].click();conveyor.assert_called_once()
    def test_target_dialog_and_verified_label_use_saved_data(self):
        p=self.page
        def targets():
            d=next(d for d in self.window.findChildren(AppDialog) if d.isVisible());grid=d.findChild(QTableWidget);grid.item(0,0).setCheckState(Qt.CheckState.Checked)
            next(b for b in d.findChildren(QPushButton) if b.text()=='Simpan list').click();d.accept()
        QTimer.singleShot(50,targets);p.show_targets();self.assertIsNotNone(p.target_list.currentData());self.start()
        p.scan_input.setText(self.carton_codes[0]);p.scan();p.buttons['stage_lock'].click();p.print_callback=lambda *args:True;p.buttons['stage_print_label'].click()
        def verify():
            d=p.verification_dialog;self.window.receive_device_scan('PALLET',p.run['parent_code']);d.findChild(QSpinBox).setValue(1)
            next(b for b in d.findChildren(QPushButton) if b.text()=='Simpan verifikasi').click()
        QTimer.singleShot(50,verify);p.verify_dialog(p.run);self.assertEqual(p.repo.meta(p.run['id'])['verified'],1)
    def test_pause_reset_and_restart_preserve_partial_pallet(self):
        p=self.page;self.start();p.scan_input.setText(self.carton_codes[0]);p.scan();p.buttons['stage_start_scan'].click();p.scan_input.setText(self.carton_codes[1]);p.scan();self.assertEqual(p.filled,1)
        p.buttons['stage_reset'].click();self.assertEqual(p.filled,1);identifier=p.run['id']
        self.window.close();self.window=MainWindow(self.store);self.page=self.window.pages['pallet'];self.assertEqual(self.page.run['id'],identifier);self.assertEqual(self.page.child_codes,[self.carton_codes[0]])
    def test_grid_has_24_equal_cells_and_pages_without_changing_sidebar(self):
        p=self.page;doc=self.templates.get(self.pallet_id)['document'];doc['aggregation_max']=48;self.templates.save(doc,self.pallet_id);p.refresh();self.start()
        self.assertEqual(len(p.cell_buttons),24);self.assertFalse(p.buttons['grid_prev'].isEnabled());p.buttons['grid_next'].click();self.assertEqual(p.grid_page,1);self.assertFalse(p.buttons['grid_next'].isEnabled());p.buttons['grid_prev'].click();self.assertEqual(p.grid_page,0)
        from agregasi.sidebar_layout import SIDEBAR
        calls=[];original=p.panel
        def record(*args,**kwargs):calls.append(args[:4]);return original(*args,**kwargs)
        p.panel=record;p.grab();p.panel=original;self.assertIn(SIDEBAR,calls)
        rects=[b.geometry() for b in p.cell_buttons];self.assertEqual(len({(r.width(),r.height()) for r in rects}),1)
        for i,r in enumerate(rects):
            self.assertGreaterEqual(r.top(),234);self.assertLess(r.bottom(),648)
            self.assertTrue(all(not r.intersects(other) for other in rects[i+1:]))
    def test_camera_decoder_reads_real_codes_and_latches_repeated_frame(self):
        code=self.carton_codes[0];doc=default_document('BOX');doc['elements']=[new_element('barcode',4,4,90,35,text=code)];frame=render_image(doc)
        self.assertEqual(decode_frame(frame),[code]);cam=PalletCamera(self.window.settings_runtime,self.page);received=[];cam.decoded.connect(received.append);cam.last_image=frame
        cam.read_barcode();cam.read_barcode();self.assertEqual(received,[code]);cam.read_barcode(force=True);self.assertEqual(received,[code,code]);cam.close();cam.deleteLater()
    def test_pallet_upload_requires_actual_ack_and_only_sends_pallet(self):
        self.fill();requests=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                data=json.loads(self.rfile.read(int(self.headers['Content-Length'])));requests.append(data)
                body=json.dumps({'accepted_record_ids':[r['record_id'] for r in data['events']]}).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            cfg=self.window.settings_runtime.repo.load();cfg['project_url']=f'http://127.0.0.1:{server.server_port}/upload';self.window.settings_runtime.repo.save(cfg)
            self.page.buttons['stage_upload'].click();deadline=time.monotonic()+5
            while self.window.settings_runtime.uploading and time.monotonic()<deadline:QTest.qWait(20)
            self.assertTrue(requests);self.assertTrue(all(row['stage']=='PALLET' for data in requests for row in data['events']))
            rows=[r for r in self.window.settings_runtime.delivery.rows() if r['stage']=='PALLET'];self.assertTrue(rows);self.assertTrue(all(r['delivery_status']=='SUCCESS' for r in rows))
        finally:server.shutdown();server.server_close()

if __name__=='__main__':unittest.main()
