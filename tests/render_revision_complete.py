"""Render reference-like revision UI using an isolated production relationship fixture."""
import os,sys,tempfile,json
from pathlib import Path
from datetime import datetime
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter
from PySide6.QtCore import Qt,QPoint
from agregasi.store import Store
from agregasi.app import MainWindow
from agregasi.template_model import default_document
app=QApplication([]);app.setStyle('Fusion');app.setStyleSheet((ROOT/'styles/theme.qss').read_text());out=ROOT/'docs/revisi_lengkap';out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
 s=Store(Path(tmp)/'db');w=MainWindow(s);repo=w.pages['revision'].repo
 def run(level,code,children):
  doc=default_document(level);doc['data']['product_name']='PRODUK UJI';identifier=code
  with s.db:
   s.db.execute('INSERT INTO aggregation_runs(id,template_id,level,batch,document,quantity,state,parent_code,print_state,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(identifier,'fixture-'+level,level,s.get('batch'),json.dumps(doc),len(children),'COMPLETE',code,'SENT',datetime.now().isoformat(timespec='seconds')))
   s.db.execute('INSERT INTO packages(stage,code,batch) VALUES(?,?,?)',(level,code,s.get('batch')))
   for childlevel,child in children:
    s.db.execute('INSERT INTO aggregation_children(run_id,child_level,code,child_template_id,ts) VALUES(?,?,?,?,?)',(identifier,childlevel,child,'fixture-'+childlevel,datetime.now().isoformat(timespec='seconds')))
    if childlevel!='UNIT':s.db.execute('UPDATE packages SET parent=? WHERE stage=? AND code=?',(code,childlevel,child))
   s._event(level,'Agregasi '+level,code,'VALID','Fixture untuk pratinjau',source='template')
 for i in range(1,5):run('BOX',f'BOX-260906-{i:04}',[('UNIT',f'UNIT260906{i:04}{j:02}') for j in range(1,4)])
 run('CARTON','CTN-260906-0001',[('BOX','BOX-260906-0001'),('BOX','BOX-260906-0002')]);run('CARTON','CTN-260906-0002',[('BOX','BOX-260906-0003'),('BOX','BOX-260906-0004')]);run('PALLET','PLT-260906-0001',[('CARTON','CTN-260906-0001'),('CARTON','CTN-260906-0002')])
 for key in [('BOX','BOX-260906-0001'),('CARTON','CTN-260906-0001'),('PALLET','PLT-260906-0001')]:
  repo.unlock(key,'Pemeriksaan data uji');repo.change_status(key,'PENDING','Menunggu verifikasi QC');repo.unlock(key,'Hasil QC diterima');repo.change_status(key,'VALID','Data uji selesai diverifikasi')
 page=w.pages['revision'];page.key=('PALLET','PLT-260906-0001');page.message='PRATINJAU DATA UJI • Semua relasi berasal dari database sementara.';w.navigate('revision');w.resize(1448,1086);w.show();app.processEvents();page.grab().save(str(out/'revisi-lengkap.png'))
 image=QImage(3840,2880,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.transparent);p=QPainter(image);p.scale(3840/1448,2880/1086);page.render(p,QPoint());p.end();image.save(str(out/'revisi-lengkap-4k.png'))
 for width,height in ((1366,768),(1920,1080)):
  w.resize(width,height);app.processEvents();w.grab().save(str(out/f'revisi-{width}x{height}.png'))
 from agregasi.label_render import export_pdf
 export_pdf(repo.label(('BOX','BOX-260906-0001'),w.aggregation_runtime,w.pages['template'].repo),out/'label-reprint-uji.pdf')
 w.close();s.close();app.processEvents()
print('Rendered revision previews and selected-record PDF label.')
