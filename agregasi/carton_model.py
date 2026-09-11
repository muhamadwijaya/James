"""Carton sessions and target lists backed by completed box aggregations."""
import csv
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from .box_model import product_key
from .revision_model import RevisionRepository


class CartonRepository:
    def __init__(self,store,runtime):
        self.store=store;self.runtime=runtime
        store.db.executescript('''
        CREATE TABLE IF NOT EXISTS carton_target_lists(id TEXT PRIMARY KEY,name TEXT NOT NULL,product TEXT NOT NULL,batch TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS carton_targets(list_id TEXT NOT NULL,code TEXT NOT NULL,PRIMARY KEY(list_id,code));
        CREATE TABLE IF NOT EXISTS carton_sessions(run_id TEXT PRIMARY KEY,list_id TEXT,mfd TEXT NOT NULL,verified INTEGER NOT NULL DEFAULT 0,verified_at TEXT,verified_by TEXT);
        CREATE TABLE IF NOT EXISTS carton_scan_attempts(id INTEGER PRIMARY KEY,run_id TEXT NOT NULL,ts TEXT NOT NULL,code TEXT NOT NULL,child_level TEXT NOT NULL,status TEXT NOT NULL,note TEXT NOT NULL);
        ''')
        self.revisions=RevisionRepository(store)

    def product_for(self,doc):
        if doc.get('carton_product'):return doc['carton_product']
        if doc['child_level']=='UNIT':return doc.get('child_product')
        if doc.get('child_template_id'):
            try:return self.runtime.repo.get(doc['child_template_id'])['document'].get('child_product')
            except ValueError:return None
        return None

    def templates(self):
        result=[]
        for row in self.runtime.repo.list('CARTON'):
            entry=self.runtime.repo.get(row['id']);doc=entry['document'];product=self.product_for(doc)
            if doc.get('active',True) and product:
                entry['product']=product;result.append(entry)
        return result

    def lists(self,product,batch):
        if not product:return []
        return [dict(r) for r in self.store.db.execute('SELECT l.*,COUNT(t.code) quantity FROM carton_target_lists l JOIN carton_targets t ON l.id=t.list_id WHERE product=? AND batch=? GROUP BY l.id ORDER BY created_at DESC',(product_key(product),batch))]

    def candidates(self,product,batch):
        if not product:return []
        # Find only finished, printed, unassigned boxes from the chosen product/batch.
        rows=self.store.db.execute("""SELECT r.* FROM aggregation_runs r JOIN packages p ON p.stage='BOX' AND p.code=r.parent_code
          WHERE r.level='BOX' AND r.state='COMPLETE' AND r.print_state='SENT' AND r.batch=? AND p.active=1 AND COALESCE(p.parent,'')=''
          AND NOT EXISTS(SELECT 1 FROM aggregation_children c WHERE c.child_level='BOX' AND c.code=r.parent_code)
          ORDER BY r.created_at,r.rowid""",(batch,)).fetchall()
        result=[];nodes=self.revisions.rows()
        for row in rows:
            doc=json.loads(row['document'])
            if not doc.get('child_product') or product_key(doc['child_product'])!=product_key(product):continue
            if any(n['status']!='VALID' for n in self.revisions.family(('BOX',row['parent_code']),nodes)):continue
            result.append(dict(code=row['parent_code'],batch=row['batch'],quantity=row['quantity'],template_id=row['template_id'],state='SIAP'))
        return result

    def create_targets(self,name,codes,product,batch):
        if not product or not batch.strip():raise ValueError('Pilih produk dan batch terlebih dahulu.')
        if not codes or len(codes)>100000:raise ValueError('Pilih 1 sampai 100.000 box untuk list target.')
        if len(set(codes))!=len(codes):raise ValueError('List memuat kode box duplikat.')
        allowed={row['code'] for row in self.candidates(product,batch)}
        unknown=next((c for c in codes if c not in allowed),None)
        if unknown:raise ValueError('Box belum siap / produk atau batch tidak sesuai: '+unknown)
        identifier=uuid4().hex
        with self.store.db:
            self.store.db.execute('INSERT INTO carton_target_lists VALUES(?,?,?,?,?)',(identifier,name.strip() or 'CARTON LIST',product_key(product),batch,datetime.now().isoformat(timespec='seconds')))
            self.store.db.executemany('INSERT INTO carton_targets VALUES(?,?)',[(identifier,c) for c in codes])
            self.store.audit('TARGET CARTON',f'{name}: {len(codes)} box / {batch}')
        return identifier

    def import_targets(self,path,product,batch):
        if not product or not batch.strip():raise ValueError('Pilih produk dan batch terlebih dahulu.')
        codes=[]
        with open(path,encoding='utf-8-sig',newline='') as handle:
            reader=csv.DictReader(handle)
            if not reader.fieldnames or 'code' not in reader.fieldnames:raise ValueError('CSV wajib memiliki kolom code. Kolom opsional: product, batch.')
            for i,row in enumerate(reader,2):
                code=(row.get('code') or '').strip()
                if not code or len(code)>500:raise ValueError(f'Baris {i}: kode box kosong / terlalu panjang.')
                if row.get('product') and row['product'].strip()!=product['name']:raise ValueError(f'Baris {i}: produk berbeda.')
                if row.get('batch') and row['batch'].strip()!=batch:raise ValueError(f'Baris {i}: batch berbeda.')
                codes.append(code)
                if len(codes)>100000:raise ValueError('Maksimal 100.000 box per file.')
        return self.create_targets(Path(path).stem,codes,product,batch)

    def meta(self,identifier):
        row=self.store.db.execute('SELECT * FROM carton_sessions WHERE run_id=?',(identifier,)).fetchone()
        return dict(row) if row else {}

    def start(self,template_id,batch,mfd,list_id=None):
        batch=batch.strip()
        if not batch:raise ValueError('Batch wajib diisi.')
        datetime.strptime(mfd,'%d/%m/%Y');doc=self.runtime.repo.get(template_id)['document'];product=self.product_for(doc)
        if doc['level']!='CARTON' or doc['child_level'] not in ('BOX','UNIT') or not product:raise ValueError('Lengkapi relasi child pada template CARTON terlebih dahulu.')
        if list_id:
            target=self.store.db.execute('SELECT * FROM carton_target_lists WHERE id=?',(list_id,)).fetchone()
            if doc['child_level']!='BOX' or not target or target['batch']!=batch or target['product']!=product_key(product):raise ValueError('List box tidak sesuai produk / batch / mode template.')
        existing=self.store.db.execute("SELECT id FROM aggregation_runs WHERE template_id=? AND batch=? AND (state='OPEN' OR (state='COMPLETE' AND print_state!='SENT')) ORDER BY created_at DESC LIMIT 1",(template_id,batch)).fetchone()
        if existing:
            meta=self.meta(existing['id'])
            if meta and (meta['list_id']!=list_id or meta['mfd']!=mfd):raise ValueError('Sesi masih terbuka. Gunakan list dan MFD semula sampai sesi selesai.')
        with self.store.db:self.store.put('batch',batch);self.store.put('product',product['name'])
        run=self.runtime.start(template_id)
        if not self.meta(run['id']):
            # Retain the original template snapshot when resuming an older session.
            run['document']['carton_product']=self.product_for(run['document']) or product
            run['document']['data'].update(mfg_date=mfd,product_name=run['document']['carton_product']['name'])
            with self.store.db:
                self.store.db.execute('INSERT INTO carton_sessions(run_id,list_id,mfd) VALUES(?,?,?)',(run['id'],list_id,mfd))
                self.store.db.execute('UPDATE aggregation_runs SET document=? WHERE id=?',(json.dumps(run['document']),run['id']))
        run=self.runtime.reserve_code(run['id'])
        with self.store.db:self.store.put('carton_current_run',run['id'])
        return run

    def scan(self,identifier,code):
        run=self.runtime.get(identifier);doc=run['document'];code=code.strip()
        try:
            if not self.store.get('configuration',{}).get('line_active',True):raise ValueError('Line nonaktif. Aktifkan melalui Pengaturan.')
            if run['state']!='OPEN':raise ValueError('Carton sudah selesai. Mulai sesi berikutnya.')
            self.validate_contents(run)
            meta=self.meta(identifier)
            if meta.get('list_id') and not self.store.db.execute('SELECT 1 FROM carton_targets WHERE list_id=? AND code=?',(meta['list_id'],code)).fetchone():raise ValueError('Kode box tidak terdaftar dalam list target sesi ini.')
            if doc['child_level']=='BOX':
                if self.store.db.execute("SELECT 1 FROM aggregation_children WHERE child_level='BOX' AND code=?",(code,)).fetchone():raise ValueError('Box sudah terikat pada agregasi; duplikat ditolak.')
                child=self.store.db.execute("SELECT r.*,p.active,p.parent FROM aggregation_runs r JOIN packages p ON p.stage='BOX' AND p.code=r.parent_code WHERE r.level='BOX' AND r.parent_code=?",(code,)).fetchone()
                if not child or child['state']!='COMPLETE':raise ValueError('Kode bukan hasil Box yang selesai. Kunci Box terlebih dahulu.')
                if child['batch']!=run['batch']:raise ValueError('Batch box berbeda dari carton.')
                if child['template_id']!=doc.get('child_template_id'):raise ValueError('Template box berbeda dari template child carton.')
                if child['parent']:raise ValueError('Box sudah memiliki parent; duplikat ditolak.')
                if not child['active']:raise ValueError('Box nonaktif / reject.')
                if child['print_state']!='SENT':raise ValueError('Label box belum dicetak. Selesaikan cetak di Tahap 1 / Box.')
            result=self.runtime.scan(identifier,code)
        except ValueError as exc:
            self.record(run,code,'DUPLIKAT' if 'duplikat' in str(exc).lower() else 'REJECT',str(exc));raise
        self.record(run,code,'VALID',doc['child_level']+' diterima pada '+result['parent_code'])
        return result

    def validate_contents(self,run):
        for child in self.store.db.execute('SELECT child_level,code FROM aggregation_children WHERE run_id=?',(run['id'],)):
            family=self.revisions.family((child['child_level'],child['code']))
            if any(n['status']!='VALID' for n in family):raise ValueError('Isi carton memiliki data belum VALID. Selesaikan revisi dahulu.')
            if child['child_level']=='BOX':
                p=self.store.db.execute("SELECT active,parent FROM packages WHERE stage='BOX' AND code=?",(child['code'],)).fetchone()
                if not p or not p['active'] or (p['parent'] and p['parent']!=run['parent_code']):raise ValueError('Status / parent box berubah. Periksa melalui Revisi.')

    def finish(self,identifier):
        run=self.runtime.get(identifier)
        self.validate_contents(run)
        return self.runtime.finish_partial(identifier)

    def record(self,run,code,status,note):
        # Scan attempts do not change the validity of an existing child box.
        with self.store.db:
            self.store.db.execute('INSERT INTO carton_scan_attempts(run_id,ts,code,child_level,status,note) VALUES(?,?,?,?,?,?)',(run['id'],datetime.now().isoformat(timespec='seconds'),code,run['document']['child_level'],status,note))

    def verify(self,identifier,code,quantity):
        run=self.runtime.get(identifier)
        if run['state']!='COMPLETE':raise ValueError('Kunci carton sebelum verifikasi.')
        if run['print_state']!='SENT':raise ValueError('Cetak label carton sebelum verifikasi.')
        if code.strip()!=run['parent_code']:raise ValueError('Kode hasil scan berbeda dari label carton yang dipilih.')
        if quantity!=run['quantity']:raise ValueError('Jumlah child yang diperiksa berbeda dari isi carton.')
        if any(n['status']!='VALID' for n in self.revisions.family(('CARTON',run['parent_code']))):raise ValueError('Carton atau isinya memiliki status revisi belum VALID.')
        with self.store.db:
            self.store.db.execute('UPDATE carton_sessions SET verified=1,verified_at=?,verified_by=? WHERE run_id=?',(datetime.now().isoformat(timespec='seconds'),self.store.get('user'),identifier))
            self.store.audit('VERIFIKASI CARTON',json.dumps({'code':code,'quantity':quantity,'child_level':run['document']['child_level'],'method':'operator + scan label'}))

    def recent(self,limit=5):return [dict(r) for r in self.store.db.execute('SELECT * FROM carton_scan_attempts ORDER BY id DESC LIMIT ?',(limit,))]
    def results(self,limit=5):return [dict(r) for r in self.store.db.execute("SELECT r.*,COALESCE(s.verified,0) verified FROM aggregation_runs r LEFT JOIN carton_sessions s ON s.run_id=r.id WHERE r.level='CARTON' AND r.state!='CANCELLED' ORDER BY r.created_at DESC,r.rowid DESC LIMIT ?",(limit,))]
    def metrics(self,child_level="BOX"):
        today=datetime.now().date().isoformat();statuses={r['status']:r['n'] for r in self.store.db.execute('SELECT status,COUNT(*) n FROM carton_scan_attempts WHERE substr(ts,1,10)=? AND child_level=? GROUP BY status',(today,child_level))}
        total=self.store.db.execute("SELECT COUNT(DISTINCT code) FROM events WHERE stage='CARTON' AND action='Agregasi CARTON' AND source='template' AND substr(ts,1,10)=?",(today,)).fetchone()[0]
        return {'cartons':total,'total':sum(statuses.values()),'valid':statuses.get('VALID',0),'reject':statuses.get('REJECT',0),'duplicate':statuses.get('DUPLIKAT',0)}
