"""Reproducible UI preview with temporary test data and a loopback HTTP server."""
import json
import os
import sys
import tempfile
import threading
from datetime import datetime,timedelta
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint,Qt
from PySide6.QtGui import QImage,QPainter
from PySide6.QtTest import QTest
from agregasi.app import MainWindow
from agregasi.store import Store

root=Path(__file__).resolve().parents[1];out=root/'docs/upload_previews';out.mkdir(exist_ok=True)
app=QApplication.instance() or QApplication([]);app.setStyle('Fusion');app.setStyleSheet((root/'styles/theme.qss').read_text())
with tempfile.TemporaryDirectory() as tmp:
    store=Store(Path(tmp)/'preview.sqlite3');window=MainWindow(store);runtime=window.settings_runtime
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'accepted_record_ids':[e['record_id'] for i,e in enumerate(data['events']) if i%7!=0]}).encode())
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    cfg=runtime.repo.load();cfg.update(project_url=f'http://127.0.0.1:{server.server_port}',auto_upload=False,retry_count=0,server_host='');runtime.repo.save(cfg)
    identifiers=[]
    for i in range(48):
        stage=('BOX','CARTON','PALLET')[i%3];prefix={'BOX':'BOX','CARTON':'CTN','PALLET':'PLT'}[stage]
        identifier,_=store.scan(stage,f'{prefix}-260906-{i+1:04}');identifiers.append(identifier)
        with store.db:store.db.execute('UPDATE events SET ts=? WHERE id=?',((datetime.now()-timedelta(seconds=(48-i)*45)).isoformat(timespec='seconds'),identifier))
    runtime.upload(event_ids=identifiers[:16])
    for _ in range(500):
        app.processEvents()
        if not runtime.uploading:break
        QTest.qWait(10)
    page=window.pages['send'];page.selected_ids=set(identifiers[-3:]);page.message='PRATINJAU • Data uji sementara. Pengiriman diuji melalui server lokal.'
    window.navigate('send');window.resize(1448,1086);window.show();app.processEvents()
    page.grab().save(str(out/'upload-lengkap.png'))
    image=QImage(3840,2880,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.transparent)
    painter=QPainter(image);painter.setRenderHint(QPainter.RenderHint.Antialiasing);painter.setRenderHint(QPainter.RenderHint.TextAntialiasing);painter.scale(3840/1448,2880/1086);page.render(painter,QPoint(0,0));painter.end();image.save(str(out/'upload-lengkap-4k.png'))
    for width,height in ((1366,768),(1920,1080)):
        window.resize(width,height);app.processEvents();window.grab().save(str(out/f'upload-{width}x{height}.png'))
    pdf=out/'contoh-ekspor-upload.pdf';runtime.delivery.export(pdf,runtime.delivery.rows(),'pdf')
    window.close();app.processEvents();server.shutdown();server.server_close();store.close()
print('Preview, 4K, responsive views and sample PDF rendered.')
