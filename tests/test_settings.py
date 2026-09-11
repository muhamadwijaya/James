import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QDate, QTime
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from agregasi.store import Store
from agregasi.settings_model import SettingsRepository, defaults, validate
from agregasi.settings_page import SettingsPage
from agregasi.settings_runtime import SettingsRuntime
from agregasi.template_model import default_document, new_element
from agregasi.label_render import export_pdf


class SettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.store=Store(self.root/'data.sqlite3');self.repo=SettingsRepository(self.store)
        self.page=None;self.runtime=None
    def tearDown(self):
        if self.page:self.page.dirty=False;self.page.shutdown();self.page.close();self.page.deleteLater()
        elif self.runtime:self.runtime.shutdown();self.runtime.deleteLater()
        self.app.processEvents();self.store.close();self.tmp.cleanup()

    def test_complete_form_persists_across_restart(self):
        self.page=SettingsPage(self.store);c=self.page.controls
        c['line'].setCurrentText('LINE-TEST');c['shift'].setCurrentIndex(0)
        c['start_delay'].setValue(4.5);c['stop_delay'].setValue(3.2)
        c['cache_limit'].setValue(321);c['auto_upload'].setChecked(False)
        c['upload_timeout'].setValue(7);c['mfd'].setDate(QDate(2026,9,6))
        c['sync_interval'].setValue(15);c['retry_count'].setValue(2)
        c['printers.BOX.device'].setCurrentText('TCP Printer');c['printers.BOX.dpi'].setCurrentText('300')
        c['printers.BOX.darkness'].setValue(22);c['printers.BOX.speed'].setValue(8)
        c['scanners.BOX.trigger'].setCurrentText('MANUAL');c['camera.address'].setText('http://127.0.0.1/snapshot.png')
        c['camera.exposure'].setValue(75);c['backup_time'].setTime(QTime(16,20));c['backup_days'].setValue(60)
        self.assertTrue(self.page.save());snapshot=self.page.collect()
        db=Store(self.store.path)
        try:self.assertEqual(SettingsRepository(db).load(),snapshot)
        finally:db.close()
        c['line'].setCurrentText('UNSAVED');self.page.load();self.assertEqual(c['line'].currentText(),'LINE-TEST')
        self.assertFalse(self.page.dirty)

    def test_invalid_configuration_is_atomic_and_secret_not_logged(self):
        cfg=defaults();cfg['project_url']='https://example.test';cfg['api_token']='test-token-only';self.repo.save(cfg)
        bad=self.repo.load();bad['cache_limit']=0;bad['line']='SHOULD-NOT-SAVE'
        with self.assertRaises(ValueError):self.repo.save(bad)
        self.assertEqual(self.repo.load()['line'],cfg['line'])
        logs=' '.join(r['detail'] for r in self.store.db.execute('SELECT detail FROM audit'))
        self.assertNotIn('test-token-only',logs)
        with self.assertRaises(ValueError):validate(cfg|{'project_url':'http://example.test'})

    def test_configuration_export_restore_and_backup_do_not_erase_production(self):
        cfg=defaults();cfg['line']='RESTORE-LINE';self.repo.save(cfg)
        path=self.root/'settings.json';self.repo.export_configuration(path)
        self.assertEqual(json.loads(path.read_text())['configuration']['api_token'],'')
        self.store.scan('BOX','BOX-ACTUAL-001');count=len(self.store.events())
        changed=self.repo.load();changed['line']='OTHER';self.repo.save(changed)
        self.repo.restore(path)
        self.assertEqual(self.repo.load()['line'],'RESTORE-LINE');self.assertEqual(len(self.store.events()),count)
        backups=list((self.root/'backups').glob('*.sqlite3'));self.assertEqual(len(backups),1)
        with sqlite3.connect(backups[0]) as db:self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        bad=self.root/'bad.json';bad.write_text('{"configuration":{"cache_limit":0}}')
        with self.assertRaises(ValueError):self.repo.restore(bad)
        self.assertEqual(self.repo.load()['line'],'RESTORE-LINE')

    def test_backup_schedule_and_temp_scope(self):
        cfg=defaults();cfg['backup_time']='02:00';self.repo.save(cfg)
        now=datetime(2026,9,6,3,0)
        self.assertTrue(self.repo.backup_due(now));self.repo.backup(now)
        self.assertFalse(self.repo.backup_due(now+timedelta(hours=1)))
        self.assertTrue(self.repo.backup_due(now+timedelta(days=1)))
        tmp=self.root/'temp';tmp.mkdir();(tmp/'cache.dat').write_bytes(b'cache')
        outside=self.root/'must-keep.txt';outside.write_text('keep');(tmp/'linked').symlink_to(outside)
        self.assertEqual(self.repo.clear_temp(),(1,5));self.assertTrue(outside.exists());self.assertTrue(self.store.path.exists())

    def test_user_roles_duplicate_names_and_last_admin(self):
        self.repo.save_user('new.user','QC','A',True)
        self.repo.save_user('new.user','MAINTENANCE','C',False,'new.user')
        row=next(r for r in self.repo.users() if r['username']=='new.user')
        self.assertEqual((row['role'],row['active']),('MAINTENANCE',0))
        with self.assertRaises(ValueError):self.repo.save_user('NEW.USER','QC','B',True)
        with self.assertRaises(ValueError):self.repo.save_user('admin','OPERATOR','ALL',False,'admin')
        with self.assertRaises(ValueError):self.repo.save_user('wijaya','OPERATOR','B',False,'wijaya')

    def test_background_device_refresh_preserves_unsaved_form(self):
        self.page=SettingsPage(self.store)
        self.page.line_name.setText('UNSAVED-LINE')
        self.page.runtime.set_status('api','GAGAL','HTTP 503')
        self.assertEqual(self.page.line_name.text(),'UNSAVED-LINE');self.assertTrue(self.page.dirty)
        self.assertNotEqual(self.repo.load()['line'],'UNSAVED-LINE')

    def test_unknown_printer_and_camera_never_report_online(self):
        with patch('agregasi.settings_runtime.QPrinterInfo.availablePrinters',return_value=[]),patch('agregasi.settings_runtime.QSerialPortInfo.availablePorts',return_value=[]):
            self.runtime=SettingsRuntime(self.store)
            self.assertEqual(self.runtime.status['printer_BOX']['status'],'TIDAK TERDETEKSI')
            self.assertEqual(self.runtime.status['camera']['status'],'BELUM DITES')
            with self.assertRaises(ValueError):self.runtime.configured_printer('BOX')

    def test_test_label_pdf_is_real(self):
        doc=default_document('BOX');doc['width_mm']=60;doc['height_mm']=40;doc['dpi']=203
        doc['elements']=[new_element('text',3,3,54,8,text='TEST PRINTER BOX',font=12)]
        path=self.root/'test.pdf';export_pdf(doc,path)
        self.assertTrue(path.read_bytes().startswith(b'%PDF'));self.assertGreater(path.stat().st_size,1000)

    def test_controls_buttons_and_theme(self):
        self.page=SettingsPage(self.store)
        self.assertEqual(len(self.page.controls),53)
        for name in ('test_connection','test_print_all','calibrate_scanner','calibrate_camera','add_user','edit_user','backup_now','restore_config','export_config','clear_temp','export_log','check_update','save_settings','reload_settings','reset_settings','test_devices','reveal_token'):
            self.assertTrue(self.page.buttons[name].isEnabled(),name)
        self.page.controls['language'].setCurrentText('ENGLISH');self.page.controls['theme'].setCurrentText('HIGH CONTRAST')
        self.assertTrue(self.page.save());self.assertEqual(self.page.buttons['save_settings'].text(),'SAVE SETTINGS')
        self.assertTrue(self.page.high_contrast)

    def test_serial_scanner_waits_for_complete_barcode(self):
        if not hasattr(os,'openpty'):self.skipTest('POSIX pseudo-terminal required')
        master,slave=os.openpty()
        try:
            cfg=defaults();cfg['scanners']['BOX']['port']=os.ttyname(slave);cfg['scanners']['BOX']['trigger']='MANUAL'
            self.repo.save(cfg);self.runtime=SettingsRuntime(self.store);received=[]
            self.runtime.scan_received.connect(lambda level,value:received.append((level,value)))
            self.runtime.listen_scanner('BOX')
            os.write(master,b'BOX-SERIAL-001');QTest.qWait(30);self.assertEqual(received,[])
            os.write(master,b'\r\n');QTest.qWait(40);self.assertEqual(received,[('BOX','BOX-SERIAL-001')])
            os.write(master,b'BOX-SERIAL-002\r');QTest.qWait(30);self.assertEqual(len(received),1)
            self.runtime.listen_scanner('BOX');os.write(master,b'BOX-SERIAL-003\n');QTest.qWait(30)
            self.assertEqual(received[-1],('BOX','BOX-SERIAL-003'))
        finally:
            if self.runtime:self.runtime.shutdown()
            os.close(master);os.close(slave)

    def test_zpl_uses_selected_darkness_speed_and_resolution(self):
        cfg=defaults();cfg['printers']['BOX'].update(device='tcp://127.0.0.1:9100',dpi=203,darkness=20,speed=4)
        self.repo.save(cfg);self.runtime=SettingsRuntime(self.store)
        doc=default_document('BOX');doc['width_mm']=60;doc['height_mm']=40
        doc['elements']=[new_element('text',3,3,54,8,text='TEST',font=12)]
        with patch('agregasi.settings_runtime.socket.create_connection') as connection:
            self.runtime.print_zpl(doc)
            payload=connection.return_value.__enter__.return_value.sendall.call_args.args[0]
        self.assertIn(b'^MD20^PR4',payload);self.assertIn(b'^PW480',payload);self.assertIn(b'^GFA,',payload)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db.sqlite3')
        self.runtime=SettingsRuntime(self.store);self.requests=[];self.response={'success':True};self.code=200
        outer=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                body=json.dumps({'version':'3.6.0'} if self.path=='/version.json' else {'ok':True}).encode()
                self.send_response(200);self.end_headers();self.wfile.write(body)
            def do_POST(self):
                request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                outer.requests.append(request)
                self.send_response(outer.code);self.end_headers()
                self.wfile.write(json.dumps(outer.response).encode())
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        cfg=defaults();cfg['project_url']=f'http://127.0.0.1:{self.server.server_port}';cfg['server_host']='';cfg['retry_count']=0;cfg['auto_upload']=False
        self.runtime.repo.save(cfg)
    def tearDown(self):
        self.runtime.shutdown();self.runtime.deleteLater();self.app.processEvents();self.server.shutdown();self.server.server_close();self.thread.join(timeout=2);self.store.close();self.tmp.cleanup()
    def wait_for(self,predicate):
        for _ in range(250):
            self.app.processEvents()
            if predicate():return
            QTest.qWait(10)
        self.fail('Qt network operation did not finish in time')
    def test_acknowledged_upload_persists_and_is_not_sent_twice(self):
        self.store.scan('BOX','BOX-NETWORK-001');self.runtime.upload();self.wait_for(lambda:not self.runtime.uploading)
        row=self.runtime.repo.delivery_rows()[0];self.assertEqual(row['delivery_status'],'SUCCESS')
        self.assertEqual(row['attempts'],1);self.assertEqual(len(self.requests),1)
        self.runtime.upload();QTest.qWait(50);self.assertEqual(len(self.requests),1)
        self.assertEqual(len(self.requests[0]['events']),1)
        self.assertTrue(self.requests[0]['events'][0]['record_id'])
    def test_http_200_without_ack_does_not_claim_success(self):
        self.response={'message':'received but not accepted'};self.store.scan('BOX','BOX-NOACK-001')
        self.runtime.upload();self.wait_for(lambda:not self.runtime.uploading)
        self.assertEqual(self.runtime.repo.delivery_rows()[0]['delivery_status'],'FAILED')
    def test_partial_ack_and_failed_retry(self):
        a,_=self.store.scan('BOX','BOX-PARTIAL-001');b,_=self.store.scan('BOX','BOX-PARTIAL-002')
        self.response={'accepted_ids':[a]};self.runtime.upload();self.wait_for(lambda:not self.runtime.uploading)
        states={r['id']:r['delivery_status'] for r in self.runtime.repo.delivery_rows()}
        self.assertEqual(states,{a:'SUCCESS',b:'FAILED'})
        self.response={'success':True};self.runtime.upload(retry=True);self.wait_for(lambda:not self.runtime.uploading)
        self.assertEqual(self.requests[-1]['events'][0]['id'],b)
        self.assertTrue(all(r['delivery_status']=='SUCCESS' for r in self.runtime.repo.delivery_rows()))
    def test_health_and_version_use_real_server_responses(self):
        self.runtime.test_connection();self.wait_for(lambda:self.runtime.status['api']['status']=='ONLINE')
        self.runtime.check_update();self.wait_for(lambda:'3.6.0' in self.runtime.last_update)
    def test_shutdown_recovers_unconfirmed_data(self):
        identifier,_=self.store.scan('BOX','BOX-UNCONFIRMED-001')
        self.runtime.repo.mark_delivery([identifier],'SENDING',increment=True);self.runtime.shutdown()
        self.assertEqual(self.runtime.repo.delivery_rows()[0]['delivery_status'],'FAILED')

if __name__=='__main__':unittest.main()
