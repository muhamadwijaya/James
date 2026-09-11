"""Local aggregation sessions using a snapshot of the saved template settings."""
from copy import deepcopy
from datetime import datetime
import json
from uuid import uuid4
from .template_database import product_choices
from .label_render import check_renderable


class AggregationRuntime:
    def __init__(self,store,repo):
        self.store=store;self.repo=repo
        store.db.executescript('''
        CREATE TABLE IF NOT EXISTS aggregation_runs(
            id TEXT PRIMARY KEY,template_id TEXT NOT NULL,level TEXT NOT NULL,
            batch TEXT NOT NULL,document TEXT NOT NULL,quantity INTEGER NOT NULL DEFAULT 0,
            state TEXT NOT NULL DEFAULT 'OPEN',parent_code TEXT UNIQUE,
            print_state TEXT NOT NULL DEFAULT 'WAITING',print_error TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS aggregation_children(
            run_id TEXT NOT NULL,child_level TEXT NOT NULL,code TEXT NOT NULL,
            product_id TEXT,child_template_id TEXT,ts TEXT NOT NULL DEFAULT '',UNIQUE(child_level,code));
        CREATE TABLE IF NOT EXISTS aggregation_counters(prefix TEXT PRIMARY KEY,value INTEGER NOT NULL);
        ''')
        if 'ts' not in [r[1] for r in store.db.execute('PRAGMA table_info(aggregation_children)')]:
            store.db.execute("ALTER TABLE aggregation_children ADD COLUMN ts TEXT NOT NULL DEFAULT ''");store.db.commit()

    def get(self,identifier):
        row=self.store.db.execute('SELECT * FROM aggregation_runs WHERE id=?',(identifier,)).fetchone()
        if not row:raise ValueError('Sesi agregasi tidak ditemukan.')
        result=dict(row);result['document']=json.loads(result['document']);return result

    def start(self,template_id):
        doc=self.repo.get(template_id)['document']
        if not doc.get('active',True):raise ValueError('Template nonaktif tidak dapat digunakan.')
        if doc['child_level']=='UNIT':
            product=doc.get('child_product')
            if not product:raise ValueError('Pilih produk child dan simpan template terlebih dahulu.')
            if not any(p['id']==product['id'] for p in product_choices(self.store,product['source'])):raise ValueError('Produk child tidak tersedia.')
        else:
            child_id=doc.get('child_template_id')
            if not child_id:raise ValueError('Pilih template child dan simpan terlebih dahulu.')
            child=self.repo.get(child_id)['document']
            if child['level']!=doc['child_level'] or not child.get('active',True):raise ValueError('Template child tidak sesuai atau nonaktif.')
        check_renderable(doc)
        # Resume an unfinished session; later template edits cannot alter its targets.
        row=self.store.db.execute("SELECT id FROM aggregation_runs WHERE template_id=? AND batch=? AND (state='OPEN' OR (state='COMPLETE' AND print_state!='SENT')) ORDER BY created_at DESC LIMIT 1",(template_id,self.store.get('batch'))).fetchone()
        if row:return self.get(row['id'])
        identifier=uuid4().hex
        with self.store.db:
            self.store.db.execute('INSERT INTO aggregation_runs(id,template_id,level,batch,document,created_at) VALUES(?,?,?,?,?,?)',
                (identifier,template_id,doc['level'],self.store.get('batch'),json.dumps(doc),datetime.now().isoformat(timespec='seconds')))
        return self.get(identifier)

    def _next_code(self,doc):
        prefix=doc['prefix']
        counter=self.store.db.execute('SELECT value FROM aggregation_counters WHERE prefix=?',(prefix,)).fetchone()
        serial=(counter[0] if counter else 0)+1
        if doc['serial_type']=='UNIX':serial=max(serial,int(datetime.now().timestamp()))
        if len(str(serial))>doc['max_digits']:raise ValueError('Nomor serial melebihi max digit template. Perbarui template sebelum sesi baru.')
        self.store.db.execute('INSERT INTO aggregation_counters VALUES(?,?) ON CONFLICT(prefix) DO UPDATE SET value=excluded.value',(prefix,serial))
        code=prefix+'-'+str(serial).zfill(doc['min_digits'])
        return code

    def reserve_code(self,identifier):
        run=self.get(identifier)
        if not run['parent_code'] and run['state']=='OPEN':
            with self.store.db:
                code=self._next_code(run['document'])
                self.store.db.execute('UPDATE aggregation_runs SET parent_code=? WHERE id=?',(code,identifier))
        return self.get(identifier)

    def _finish(self,run,quantity):
        doc=run['document']
        code=run['parent_code'] or self._next_code(doc)
        # Reaching the template maximum always queues the label automatically;
        # print_mode only decides an early lock below the maximum.
        state='PENDING' if quantity==doc['aggregation_max'] else 'WAITING'
        self.store.db.execute('INSERT INTO packages(stage,code,batch) VALUES(?,?,?)',(run['level'],code,run['batch']))
        self.store.db.execute('INSERT INTO events(ts,stage,action,code,status,note,batch,product,operator,source) VALUES(?,?,?,?,?,?,?,?,?,?)',(datetime.now().isoformat(timespec='seconds'),run['level'],'Agregasi '+run['level'],code,'VALID',doc['name'],run['batch'],doc['data'].get('product_name',''),self.store.get('user'),'template'))
        current=self.store.get('current');current[run['level']]=code;self.store.put('current',current)
        if doc['child_level']!='UNIT':
            self.store.db.execute('UPDATE packages SET parent=? WHERE stage=? AND code IN (SELECT code FROM aggregation_children WHERE run_id=?)',(code,doc['child_level'],run['id']))
        self.store.db.execute("UPDATE aggregation_runs SET state='COMPLETE',parent_code=?,print_state=? WHERE id=?",(code,state,run['id']))

    def scan(self,identifier,code):
        run=self.get(identifier);doc=run['document'];code=code.strip()
        if not code or len(code)>500:raise ValueError('Masukkan kode child (maksimal 500 karakter).')
        if run['state']!='OPEN':raise ValueError('Target/sesi selesai. Mulai sesi berikutnya.')
        if self.store.db.execute("SELECT 1 FROM sqlite_master WHERE name='revision_state'").fetchone():
            revision=self.store.db.execute('SELECT status FROM revision_state WHERE level=? AND code=?',(doc['child_level'],code)).fetchone()
            if revision and revision['status']!='VALID':raise ValueError('Child belum VALID setelah revisi.')
            if doc['child_level']!='UNIT':
                from .revision_model import RevisionRepository
                family=RevisionRepository(self.store).family((doc['child_level'],code))
                if any(r['status']!='VALID' for r in family):raise ValueError('Relasi child memuat data belum VALID. Selesaikan revisi sebelum agregasi.')
        if doc['child_level']!='UNIT':
            package=self.store.db.execute('SELECT active FROM packages WHERE stage=? AND code=?',(doc['child_level'],code)).fetchone()
            if package and not package['active']:raise ValueError('Kemasan child nonaktif/reject.')
        if self.store.db.execute('SELECT 1 FROM aggregation_children WHERE child_level=? AND code=?',(doc['child_level'],code)).fetchone():raise ValueError('Kode child sudah terikat pada agregasi; duplikat ditolak.')
        if doc['child_level']!='UNIT':
            child=self.store.db.execute("SELECT * FROM aggregation_runs WHERE parent_code=? AND state='COMPLETE'",(code,)).fetchone()
            if not child or child['template_id']!=doc.get('child_template_id') or child['level']!=doc['child_level']:
                raise ValueError('Kode bukan hasil agregasi dari template child yang dipilih.')
            if child['batch']!=run['batch']:raise ValueError('Batch child berbeda dari sesi ini.')
        if doc['child_level']=='UNIT' and self.store.db.execute('SELECT 1 FROM aggregation_runs WHERE parent_code=?',(code,)).fetchone():raise ValueError('Mode produk langsung memerlukan kode UNIT, bukan kode kemasan agregasi.')
        quantity=run['quantity']+1
        if quantity>doc['aggregation_max']:raise ValueError('Target maksimum sudah tercapai.')
        with self.store.db:
            self.store.db.execute('INSERT INTO aggregation_children(run_id,child_level,code,product_id,child_template_id,ts) VALUES(?,?,?,?,?,?)',(identifier,doc['child_level'],code,
                json.dumps(doc['child_product']['id']) if doc.get('child_product') else None,doc.get('child_template_id'),datetime.now().isoformat(timespec='seconds')))
            self.store.db.execute('UPDATE aggregation_runs SET quantity=? WHERE id=?',(quantity,identifier))
            if quantity==doc['aggregation_max']:self._finish(run,quantity)
        return self.get(identifier)

    def finish_partial(self,identifier):
        run=self.get(identifier)
        if run['state']!='OPEN':return run
        if run['quantity']<run['document']['aggregation_min']:raise ValueError('Quantity belum mencapai target minimum.')
        with self.store.db:self._finish(run,run['quantity'])
        return self.get(identifier)

    def print_document(self,identifier):
        run=self.get(identifier)
        if run['state']!='COMPLETE':raise ValueError('Selesaikan agregasi sebelum mencetak label.')
        doc=deepcopy(run['document']);doc['data'].update(serial=run['parent_code'],quantity=f"{run['quantity']} {doc['child_level']}",batch=run['batch'])
        return check_renderable(doc)

    def claim_print(self,identifier,automatic=False):
        self.print_document(identifier)
        states=('PENDING',) if automatic else ('PENDING','WAITING','ERROR')
        with self.store.db:
            result=self.store.db.execute("UPDATE aggregation_runs SET print_state='SENDING',print_error='' WHERE id=? AND print_state IN ("+','.join('?' for _ in states)+')',(identifier,*states))
        return result.rowcount==1

    def print_result(self,identifier,error=None):
        with self.store.db:self.store.db.execute('UPDATE aggregation_runs SET print_state=?,print_error=? WHERE id=?',('ERROR' if error else 'SENT',str(error or ''),identifier))

    def reset_empty(self,identifier):
        run=self.get(identifier)
        if run['state']=='OPEN' and run['quantity']:raise ValueError('Sesi berisi child. Selesaikan dengan Kunci; data tidak dihapus oleh Reset.')
        if run['state']=='OPEN':
            with self.store.db:self.store.db.execute("UPDATE aggregation_runs SET state='CANCELLED' WHERE id=?",(identifier,))
