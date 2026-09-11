"""Pallet sessions and target lists backed by completed carton aggregations."""
import csv
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from .box_model import product_key
from .carton_model import CartonRepository
from .revision_model import RevisionRepository


class PalletRepository:
    def __init__(self,store,runtime):
        self.store=store;self.runtime=runtime
        store.db.executescript('''
        CREATE TABLE IF NOT EXISTS pallet_target_lists(id TEXT PRIMARY KEY,name TEXT NOT NULL,product TEXT NOT NULL,batch TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS pallet_targets(list_id TEXT NOT NULL,code TEXT NOT NULL,PRIMARY KEY(list_id,code));
        CREATE TABLE IF NOT EXISTS pallet_sessions(run_id TEXT PRIMARY KEY,list_id TEXT,mfd TEXT NOT NULL,verified INTEGER NOT NULL DEFAULT 0,verified_at TEXT,verified_by TEXT);
        CREATE TABLE IF NOT EXISTS pallet_scan_attempts(id INTEGER PRIMARY KEY,run_id TEXT NOT NULL,ts TEXT NOT NULL,code TEXT NOT NULL,child_level TEXT NOT NULL,status TEXT NOT NULL,note TEXT NOT NULL);
        ''')
        self.revisions=RevisionRepository(store);self.cartons=CartonRepository(store,runtime)

    def product_for(self,doc):
        if doc.get('pallet_product'):return doc['pallet_product']
        if doc.get('child_level')=='CARTON' and doc.get('child_template_id'):
            try:
                child=self.runtime.repo.get(doc['child_template_id'])['document']
                return self.cartons.product_for(child) if child['level']=='CARTON' else None
            except ValueError:return None
        return None

    def templates(self):
        result=[]
        for row in self.runtime.repo.list('PALLET'):
            entry=self.runtime.repo.get(row['id']);doc=entry['document'];product=self.product_for(doc)
            if doc.get('active',True) and product:
                entry['product']=product;result.append(entry)
        return result

    def lists(self,product,batch):
        if not product:return []
        return [dict(r) for r in self.store.db.execute('SELECT l.*,COUNT(t.code) quantity FROM pallet_target_lists l JOIN pallet_targets t ON l.id=t.list_id WHERE product=? AND batch=? GROUP BY l.id ORDER BY created_at DESC',(product_key(product),batch))]

    def candidates(self,product,batch):
        if not product:return []
        # Only finished, printed, unassigned cartons from the selected product/batch.
        rows=self.store.db.execute("""SELECT r.* FROM aggregation_runs r JOIN packages p ON p.stage='CARTON' AND p.code=r.parent_code
          WHERE r.level='CARTON' AND r.state='COMPLETE' AND r.print_state='SENT' AND r.batch=? AND p.active=1 AND COALESCE(p.parent,'')=''
          AND NOT EXISTS(SELECT 1 FROM aggregation_children c WHERE c.child_level='CARTON' AND c.code=r.parent_code)
          ORDER BY r.created_at,r.rowid""",(batch,)).fetchall()
        result=[];nodes=self.revisions.rows()
        for row in rows:
            doc=json.loads(row['document'])
            child_product=self.cartons.product_for(doc)
            if not child_product or product_key(child_product)!=product_key(product):continue
            if any(n['status']!='VALID' for n in self.revisions.family(('CARTON',row['parent_code']),nodes)):continue
            result.append(dict(code=row['parent_code'],batch=row['batch'],quantity=row['quantity'],template_id=row['template_id'],state='SIAP'))
        return result

    def create_targets(self,name,codes,product,batch):
        if not product or not batch.strip():raise ValueError('Pilih produk dan batch terlebih dahulu.')
        if not codes or len(codes)>100000:raise ValueError('Pilih 1 sampai 100.000 carton untuk list target.')
        if len(set(codes))!=len(codes):raise ValueError('List memuat kode carton duplikat.')
        allowed={row['code'] for row in self.candidates(product,batch)}
        unknown=next((c for c in codes if c not in allowed),None)
        if unknown:raise ValueError('Carton belum siap / produk atau batch tidak sesuai: '+unknown)
        identifier=uuid4().hex
        with self.store.db:
            self.store.db.execute('INSERT INTO pallet_target_lists VALUES(?,?,?,?,?)',(identifier,name.strip() or 'PALLET LIST',product_key(product),batch,datetime.now().isoformat(timespec='seconds')))
            self.store.db.executemany('INSERT INTO pallet_targets VALUES(?,?)',[(identifier,c) for c in codes])
            self.store.audit('TARGET PALLET',f'{name}: {len(codes)} carton / {batch}')
        return identifier

    def import_targets(self,path,product,batch):
        if not product or not batch.strip():raise ValueError('Pilih produk dan batch terlebih dahulu.')
        codes=[]
        with open(path,encoding='utf-8-sig',newline='') as handle:
            reader=csv.DictReader(handle)
            if not reader.fieldnames or 'code' not in reader.fieldnames:raise ValueError('CSV wajib memiliki kolom code. Kolom opsional: product, batch.')
            for i,row in enumerate(reader,2):
                code=(row.get('code') or '').strip()
                if not code or len(code)>500:raise ValueError(f'Baris {i}: kode carton kosong / terlalu panjang.')
                if row.get('product') and row['product'].strip()!=product['name']:raise ValueError(f'Baris {i}: produk berbeda.')
                if row.get('batch') and row['batch'].strip()!=batch:raise ValueError(f'Baris {i}: batch berbeda.')
                codes.append(code)
                if len(codes)>100000:raise ValueError('Maksimal 100.000 carton per file.')
        return self.create_targets(Path(path).stem,codes,product,batch)

    def meta(self,identifier):
        row=self.store.db.execute('SELECT * FROM pallet_sessions WHERE run_id=?',(identifier,)).fetchone()
        return dict(row) if row else {}

    def start(self,template_id,batch,mfd,list_id=None):
        batch=batch.strip()
        if not batch:raise ValueError('Batch wajib diisi.')
        datetime.strptime(mfd,'%d/%m/%Y')
        existing=self.store.db.execute("SELECT id FROM aggregation_runs WHERE template_id=? AND batch=? AND (state='OPEN' OR (state='COMPLETE' AND print_state!='SENT')) ORDER BY created_at DESC LIMIT 1",(template_id,batch)).fetchone()
        run=self.runtime.get(existing['id']) if existing else None
        doc=run['document'] if run else self.runtime.repo.get(template_id)['document'];product=self.product_for(doc)
        if doc['level']!='PALLET' or doc['child_level']!='CARTON' or not product:raise ValueError('Lengkapi relasi child CARTON pada template PALLET terlebih dahulu.')
        if list_id:
            target=self.store.db.execute('SELECT * FROM pallet_target_lists WHERE id=?',(list_id,)).fetchone()
            if doc['child_level']!='CARTON' or not target or target['batch']!=batch or target['product']!=product_key(product):raise ValueError('List carton tidak sesuai produk / batch / mode template.')
        if existing:
            meta=self.meta(existing['id'])
            if meta and (meta['list_id']!=list_id or meta['mfd']!=mfd):raise ValueError('Sesi masih terbuka. Gunakan list dan MFD semula sampai sesi selesai.')
        with self.store.db:self.store.put('batch',batch);self.store.put('product',product['name'])
        run=run or self.runtime.start(template_id)
        if not self.meta(run['id']):
            # Retain the original template snapshot when resuming an older session.
            run['document']['pallet_product']=self.product_for(run['document']) or product
            run['document']['data'].update(mfg_date=mfd,product_name=run['document']['pallet_product']['name'])
            with self.store.db:
                self.store.db.execute('INSERT INTO pallet_sessions(run_id,list_id,mfd) VALUES(?,?,?)',(run['id'],list_id,mfd))
                self.store.db.execute('UPDATE aggregation_runs SET document=? WHERE id=?',(json.dumps(run['document']),run['id']))
        run=self.runtime.reserve_code(run['id'])
        with self.store.db:self.store.put('pallet_current_run',run['id'])
        return run

    def scan(self,identifier,code):
        run=self.runtime.get(identifier);doc=run['document'];code=code.strip()
        try:
            if not self.store.get('configuration',{}).get('line_active',True):raise ValueError('Line nonaktif. Aktifkan melalui Pengaturan.')
            if run['state']!='OPEN':raise ValueError('Pallet sudah selesai. Mulai sesi berikutnya.')
            self.validate_contents(run)
            meta=self.meta(identifier)
            if meta.get('list_id') and not self.store.db.execute('SELECT 1 FROM pallet_targets WHERE list_id=? AND code=?',(meta['list_id'],code)).fetchone():raise ValueError('Kode carton tidak terdaftar dalam list target sesi ini.')
            if doc['child_level']=='CARTON':
                if self.store.db.execute("SELECT 1 FROM aggregation_children WHERE child_level='CARTON' AND code=?",(code,)).fetchone():raise ValueError('Carton sudah terikat pada agregasi; duplikat ditolak.')
                child=self.store.db.execute("SELECT r.*,p.active,p.parent FROM aggregation_runs r JOIN packages p ON p.stage='CARTON' AND p.code=r.parent_code WHERE r.level='CARTON' AND r.parent_code=?",(code,)).fetchone()
                if not child or child['state']!='COMPLETE':raise ValueError('Kode bukan hasil Carton yang selesai. Kunci Carton terlebih dahulu.')
                if child['batch']!=run['batch']:raise ValueError('Batch carton berbeda dari pallet.')
                if child['template_id']!=doc.get('child_template_id'):raise ValueError('Template carton berbeda dari template child pallet.')
                child_product=self.cartons.product_for(json.loads(child['document']))
                if not child_product or product_key(child_product)!=product_key(self.product_for(doc)):raise ValueError('Produk carton berbeda dari produk snapshot pallet.')
                if child['parent']:raise ValueError('Carton sudah memiliki parent; duplikat ditolak.')
                if not child['active']:raise ValueError('Carton nonaktif / reject.')
                if child['print_state']!='SENT':raise ValueError('Label carton belum dicetak. Selesaikan cetak di Tahap 2 / Carton.')
            result=self.runtime.scan(identifier,code)
        except ValueError as exc:
            self.record(run,code,'DUPLIKAT' if 'duplikat' in str(exc).lower() else 'REJECT',str(exc));raise
        self.record(run,code,'VALID',doc['child_level']+' diterima pada '+result['parent_code'])
        return result

    def validate_contents(self,run):
        for child in self.store.db.execute('SELECT child_level,code FROM aggregation_children WHERE run_id=?',(run['id'],)):
            family=self.revisions.family((child['child_level'],child['code']))
            if any(n['status']!='VALID' for n in family):raise ValueError('Isi pallet memiliki data belum VALID. Selesaikan revisi dahulu.')
            if child['child_level']=='CARTON':
                p=self.store.db.execute("SELECT active,parent FROM packages WHERE stage='CARTON' AND code=?",(child['code'],)).fetchone()
                if not p or not p['active'] or (p['parent'] and p['parent']!=run['parent_code']):raise ValueError('Status / parent carton berubah. Periksa melalui Revisi.')
                printed=self.store.db.execute("SELECT print_state FROM aggregation_runs WHERE level='CARTON' AND parent_code=?",(child['code'],)).fetchone()
                if not printed or printed['print_state']!='SENT':raise ValueError('Label carton perlu dicetak ulang setelah revisi sebelum pallet dilanjutkan.')

    def validate_print(self,identifier):
        run=self.runtime.get(identifier)
        if run['level']!='PALLET' or run['state']!='COMPLETE':raise ValueError('Kunci pallet sebelum mencetak label.')
        self.validate_contents(run)
        if any(n['status']!='VALID' for n in self.revisions.family(('PALLET',run['parent_code']))):raise ValueError('Pallet atau isinya belum VALID setelah revisi.')
        return run

    def finish(self,identifier):
        run=self.runtime.get(identifier)
        self.validate_contents(run)
        return self.runtime.finish_partial(identifier)

    def record(self,run,code,status,note):
        # Scan attempts do not change the validity of an existing child carton.
        with self.store.db:
            self.store.db.execute('INSERT INTO pallet_scan_attempts(run_id,ts,code,child_level,status,note) VALUES(?,?,?,?,?,?)',(run['id'],datetime.now().isoformat(timespec='seconds'),code,run['document']['child_level'],status,note))

    def verify(self,identifier,code,quantity):
        run=self.runtime.get(identifier)
        if run['state']!='COMPLETE':raise ValueError('Kunci pallet sebelum verifikasi.')
        if run['print_state']!='SENT':raise ValueError('Cetak label pallet sebelum verifikasi.')
        if code.strip()!=run['parent_code']:raise ValueError('Kode hasil scan berbeda dari label pallet yang dipilih.')
        if quantity!=run['quantity']:raise ValueError('Jumlah child yang diperiksa berbeda dari isi pallet.')
        self.validate_contents(run)
        if any(n['status']!='VALID' for n in self.revisions.family(('PALLET',run['parent_code']))):raise ValueError('Pallet atau isinya memiliki status revisi belum VALID.')
        with self.store.db:
            self.store.db.execute('UPDATE pallet_sessions SET verified=1,verified_at=?,verified_by=? WHERE run_id=?',(datetime.now().isoformat(timespec='seconds'),self.store.get('user'),identifier))
            self.store.audit('VERIFIKASI PALLET',json.dumps({'code':code,'quantity':quantity,'child_level':run['document']['child_level'],'method':'operator + scan label'}))

    def recent(self,limit=5):return [dict(r) for r in self.store.db.execute('SELECT * FROM pallet_scan_attempts ORDER BY id DESC LIMIT ?',(limit,))]
    def results(self,limit=5):return [dict(r) for r in self.store.db.execute("SELECT r.*,COALESCE(s.verified,0) verified FROM aggregation_runs r LEFT JOIN pallet_sessions s ON s.run_id=r.id WHERE r.level='PALLET' AND r.state!='CANCELLED' ORDER BY r.created_at DESC,r.rowid DESC LIMIT ?",(limit,))]
    def metrics(self,child_level="CARTON"):
        today=datetime.now().date().isoformat();statuses={r['status']:r['n'] for r in self.store.db.execute('SELECT status,COUNT(*) n FROM pallet_scan_attempts WHERE substr(ts,1,10)=? AND child_level=? GROUP BY status',(today,child_level))}
        total=self.store.db.execute("SELECT COUNT(DISTINCT code) FROM events WHERE stage='PALLET' AND action='Agregasi PALLET' AND source='template' AND substr(ts,1,10)=?",(today,)).fetchone()[0]
        return {'pallets':total,'total':sum(statuses.values()),'valid':statuses.get('VALID',0),'reject':statuses.get('REJECT',0),'duplicate':statuses.get('DUPLIKAT',0)}
