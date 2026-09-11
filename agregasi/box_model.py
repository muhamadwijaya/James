"""Persistent BOX target lists, scan attempts and operator verification."""
import csv
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4


def product_key(product):
    return json.dumps({'id':product['id'],'source':product['source']},sort_keys=True)


class BoxRepository:
    def __init__(self,store,runtime):
        self.store=store;self.runtime=runtime
        store.db.executescript('''
        CREATE TABLE IF NOT EXISTS box_target_lists(id TEXT PRIMARY KEY,name TEXT NOT NULL,product TEXT NOT NULL,batch TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS box_targets(list_id TEXT NOT NULL,serial TEXT NOT NULL,PRIMARY KEY(list_id,serial));
        CREATE TABLE IF NOT EXISTS box_sessions(run_id TEXT PRIMARY KEY,list_id TEXT,mfd TEXT NOT NULL,verified INTEGER NOT NULL DEFAULT 0,verified_at TEXT,verified_by TEXT);
        CREATE TABLE IF NOT EXISTS box_scan_attempts(id INTEGER PRIMARY KEY,run_id TEXT NOT NULL,ts TEXT NOT NULL,code TEXT NOT NULL,status TEXT NOT NULL,note TEXT NOT NULL);
        ''')

    def lists(self,product,batch):
        if not product:return []
        return [dict(r) for r in self.store.db.execute('SELECT l.*,COUNT(t.serial) quantity FROM box_target_lists l JOIN box_targets t ON l.id=t.list_id WHERE product=? AND batch=? GROUP BY l.id ORDER BY created_at DESC',(product_key(product),batch))]

    def import_targets(self,path,product,batch):
        if not product or not batch.strip():raise ValueError('Pilih produk dan isi batch terlebih dahulu.')
        with open(path,encoding='utf-8-sig',newline='') as handle:
            reader=csv.DictReader(handle)
            if not reader.fieldnames or 'serial' not in reader.fieldnames:raise ValueError('CSV wajib memiliki kolom serial. Kolom opsional: product, batch.')
            codes=[];seen=set()
            for i,row in enumerate(reader,2):
                code=(row.get('serial') or '').strip()
                if not code or len(code)>500:raise ValueError(f'Baris {i}: serial wajib diisi (maksimal 500 karakter).')
                if code in seen:raise ValueError(f'Baris {i}: serial duplikat dalam file.')
                if row.get('product') and row['product'].strip()!=product['name']:raise ValueError(f'Baris {i}: produk berbeda dari pilihan.')
                if row.get('batch') and row['batch'].strip()!=batch.strip():raise ValueError(f'Baris {i}: batch berbeda dari pilihan.')
                codes.append(code);seen.add(code)
                if len(codes)>100000:raise ValueError('Maksimal 100.000 serial per file.')
        if not codes:raise ValueError('CSV tidak berisi serial.')
        identifier=uuid4().hex
        with self.store.db:
            self.store.db.execute('INSERT INTO box_target_lists VALUES(?,?,?,?,?)',(identifier,Path(path).stem,product_key(product),batch.strip(),datetime.now().isoformat(timespec='seconds')))
            self.store.db.executemany('INSERT INTO box_targets VALUES(?,?)',[(identifier,c) for c in codes])
            self.store.audit('IMPORT TARGET BOX',f'{Path(path).name}: {len(codes)} unit / {batch}')
        return identifier

    def start(self,template_id,batch,mfd,list_id=None):
        if not batch.strip():raise ValueError('Batch wajib diisi.')
        datetime.strptime(mfd,'%d/%m/%Y')
        doc=self.runtime.repo.get(template_id)['document']
        if doc['level']!='BOX' or doc['child_level']!='UNIT':raise ValueError('Pilih template BOX dengan child UNIT.')
        if list_id:
            row=self.store.db.execute('SELECT * FROM box_target_lists WHERE id=?',(list_id,)).fetchone()
            if not row or row['batch']!=batch.strip() or row['product']!=product_key(doc['child_product']):raise ValueError('List data tidak sesuai produk / batch template.')
        with self.store.db:
            self.store.put('batch',batch.strip());self.store.put('product',doc['child_product']['name'])
        run=self.runtime.start(template_id)
        meta=self.store.db.execute('SELECT * FROM box_sessions WHERE run_id=?',(run['id'],)).fetchone()
        if meta and (meta['list_id']!=list_id or meta['mfd']!=mfd):raise ValueError('Sesi template ini masih terbuka. Gunakan list dan MFD semula, lalu selesaikan sesi.')
        if not meta:
            run['document']['data']['mfg_date']=mfd
            run['document']['data']['product_name']=doc['child_product']['name']
            with self.store.db:
                self.store.db.execute('INSERT INTO box_sessions(run_id,list_id,mfd) VALUES(?,?,?)',(run['id'],list_id,mfd))
                self.store.db.execute('UPDATE aggregation_runs SET document=? WHERE id=?',(json.dumps(run['document']),run['id']))
        self.runtime.reserve_code(run['id'])
        with self.store.db:self.store.put('box_current_run',run['id'])
        return self.runtime.get(run['id'])

    def scan(self,identifier,code):
        code=code.strip();run=self.runtime.get(identifier)
        try:
            if not self.store.get('configuration',{}).get('line_active',True):raise ValueError('Line nonaktif. Aktifkan melalui Pengaturan.')
            meta=self.meta(identifier)
            if meta.get('list_id') and not self.store.db.execute('SELECT 1 FROM box_targets WHERE list_id=? AND serial=?',(meta['list_id'],code)).fetchone():raise ValueError('Serial tidak terdaftar pada list data sesi ini.')
            result=self.runtime.scan(identifier,code)
        except ValueError as exc:
            status='DUPLIKAT' if 'duplikat' in str(exc).lower() else 'REJECT'
            self.record(identifier,code,status,str(exc));raise
        self.record(identifier,code,'VALID','Unit diterima pada '+(result['parent_code'] or identifier))
        return result

    def record(self,identifier,code,status,note):
        run=self.runtime.get(identifier);ts=datetime.now().isoformat(timespec='seconds')
        with self.store.db:
            self.store.db.execute('INSERT INTO box_scan_attempts(run_id,ts,code,status,note) VALUES(?,?,?,?,?)',(identifier,ts,code,status,note))
            self.store.db.execute('INSERT INTO events(ts,stage,action,code,status,note,batch,product,operator,source) VALUES(?,?,?,?,?,?,?,?,?,?)',(ts,'UNIT','Scan Unit',code,status,note,run['batch'],run['document']['child_product']['name'],self.store.get('user'),'box'))

    def meta(self,identifier):
        row=self.store.db.execute('SELECT * FROM box_sessions WHERE run_id=?',(identifier,)).fetchone()
        return dict(row) if row else {}

    def verify(self,identifier,code,quantity):
        run=self.runtime.get(identifier)
        if run['state']!='COMPLETE':raise ValueError('Kunci box sebelum verifikasi.')
        if run['print_state']!='SENT':raise ValueError('Cetak label box sebelum verifikasi.')
        if code.strip()!=run['parent_code']:raise ValueError('Kode hasil scan tidak sama dengan label box yang dipilih.')
        if quantity!=run['quantity']:raise ValueError('Jumlah unit yang diperiksa berbeda dari isi box.')
        if self.store.db.execute("SELECT 1 FROM sqlite_master WHERE name='revision_state'").fetchone():
            invalid=self.store.db.execute("SELECT 1 FROM revision_state WHERE status!='VALID' AND ((level='BOX' AND code=?) OR (level='UNIT' AND code IN (SELECT code FROM aggregation_children WHERE run_id=?)))",(run['parent_code'],identifier)).fetchone()
            if invalid:raise ValueError('Box atau unit memiliki status revisi belum VALID.')
        with self.store.db:
            self.store.db.execute('UPDATE box_sessions SET verified=1,verified_at=?,verified_by=? WHERE run_id=?',(datetime.now().isoformat(timespec='seconds'),self.store.get('user'),identifier))
            self.store.audit('VERIFIKASI BOX',json.dumps({'code':code,'quantity':quantity,'method':'operator + scan label'}))

    def recent(self,limit=5):
        return [dict(r) for r in self.store.db.execute('SELECT * FROM box_scan_attempts ORDER BY id DESC LIMIT ?',(limit,))]

    def results(self,limit=5):
        return [dict(r) for r in self.store.db.execute("SELECT r.*,COALESCE(s.verified,0) verified FROM aggregation_runs r LEFT JOIN box_sessions s ON s.run_id=r.id WHERE r.level='BOX' AND r.state!='CANCELLED' ORDER BY r.created_at DESC,r.rowid DESC LIMIT ?",(limit,))]

    def metrics(self):
        today=datetime.now().date().isoformat()
        statuses={r['status']:r['n'] for r in self.store.db.execute('SELECT status,COUNT(*) n FROM box_scan_attempts WHERE substr(ts,1,10)=? GROUP BY status',(today,))}
        total=self.store.db.execute("SELECT COUNT(DISTINCT code) FROM events WHERE stage='BOX' AND action='Agregasi BOX' AND source='template' AND substr(ts,1,10)=?",(today,)).fetchone()[0]
        return {'boxes':total,'total':sum(statuses.values()),'valid':statuses.get('VALID',0),'reject':statuses.get('REJECT',0),'duplicate':statuses.get('DUPLIKAT',0)}
