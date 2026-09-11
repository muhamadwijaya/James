"""Traceable corrections; original scans and acknowledged payloads stay immutable."""
import csv,json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
LEVELS=('UNIT','BOX','CARTON','PALLET')
STATES=('VALID','REJECT','DUPLIKAT','PENDING')

class RevisionRepository:
    def __init__(self,store):
        self.store=store
        store.db.executescript('''
        CREATE TABLE IF NOT EXISTS revision_state(level TEXT,code TEXT,status TEXT NOT NULL,locked INTEGER NOT NULL DEFAULT 1,note TEXT NOT NULL DEFAULT '',print_state TEXT NOT NULL DEFAULT '',PRIMARY KEY(level,code));
        CREATE TABLE IF NOT EXISTS revision_log(id INTEGER PRIMARY KEY,ts TEXT NOT NULL,action TEXT NOT NULL,level TEXT NOT NULL,code TEXT NOT NULL,batch TEXT NOT NULL,before_json TEXT NOT NULL,after_json TEXT NOT NULL,operator TEXT NOT NULL,note TEXT NOT NULL);
        ''')
    def has(self,table):return bool(self.store.db.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone())
    def rows(self):
        nodes={}
        for e in self.store.db.execute('SELECT * FROM events ORDER BY id'):
            if e['stage'] not in LEVELS:continue
            # Failed rescan attempts cannot invalidate a child already accepted into a box.
            prior=nodes.get((e['stage'],e['code']))
            if e['source']=='box' and e['status']!='VALID' and prior and prior['status']=='VALID':continue
            r=dict(e);r.update(level=r['stage'],parent='',parent_level='',locked=True,print_state='BELUM DICETAK',quantity=1,run_id=None)
            nodes[(r['level'],r['code'])]=r
        for p in self.store.db.execute('SELECT * FROM packages'):
            key=(p['stage'],p['code'])
            if key not in nodes:nodes[key]=dict(id=None,ts='',level=p['stage'],stage=p['stage'],code=p['code'],batch=p['batch'],product='',operator='',note='',status='VALID' if p['active'] else 'REJECT',parent='',parent_level='',locked=True,print_state='BELUM DICETAK',quantity=1,source='local',run_id=None)
            r=nodes[key];r['parent']=p['parent'] or '';r['parent_level']=LEVELS[LEVELS.index(p['stage'])+1] if p['parent'] and p['stage']!='PALLET' else ''
            if not p['active']:r['status']='REJECT'
        if self.has('aggregation_runs'):
            runs={r['id']:dict(r) for r in self.store.db.execute('SELECT * FROM aggregation_runs')}
            for run in runs.values():
                key=(run['level'],run['parent_code']);doc=json.loads(run['document'])
                if key in nodes:nodes[key].update(run_id=run['id'],quantity=run['quantity'],print_state=run['print_state'],product=doc['data'].get('product_name',''))
            for child in self.store.db.execute('SELECT * FROM aggregation_children'):
                run=runs.get(child['run_id'])
                if not run:continue
                key=(child['child_level'],child['code']);doc=json.loads(run['document'])
                if key not in nodes:
                    nodes[key]=dict(id=None,ts=child['ts'],stage=key[0],level=key[0],code=key[1],batch=run['batch'],product=(doc.get('child_product') or {}).get('name',doc['data'].get('product_name','')),operator='',note='',status='VALID',parent='',parent_level='',locked=True,print_state='BELUM DICETAK',quantity=1,source='template',run_id=None)
                nodes[key]['parent']=run['parent_code'] or '';nodes[key]['parent_level']=run['level'] if run['parent_code'] else '';nodes[key]['owner_run']=run['id']
        for state in self.store.db.execute('SELECT * FROM revision_state'):
            key=(state['level'],state['code'])
            if key in nodes:
                nodes[key].update(status=state['status'],locked=bool(state['locked']),note=state['note'])
                if state['print_state']:nodes[key]['print_state']=state['print_state']
        return list(nodes.values())
    def get(self,key):
        r=next((r for r in self.rows() if (r['level'],r['code'])==tuple(key)),None)
        if not r:raise ValueError('Data sudah tidak tersedia. Muat ulang pencarian.')
        return r
    def family(self,key,rows=None):
        nodes={(r['level'],r['code']):r for r in (rows if rows is not None else self.rows())}
        if tuple(key) not in nodes:return []
        # Walk ancestors first, then enumerate every descendant of the top parent.
        current=tuple(key);seen=set()
        while current in nodes and current not in seen:
            seen.add(current);r=nodes[current];parent=(r['parent_level'],r['parent'])
            if not r['parent'] or parent not in nodes:break
            current=parent
        children={}
        for k,r in nodes.items():children.setdefault((r['parent_level'],r['parent']),[]).append(k)
        found={current};todo=[current]
        while todo:
            parent=todo.pop()
            for k in children.get(parent,[]):
                if k not in found:found.add(k);todo.append(k)
        return [nodes[k] for k in found if k in nodes]
    def search(self,queries=None,batch='',start='',end='',status=''):
        if start and end and start>end:raise ValueError('Tanggal awal harus sebelum atau sama dengan tanggal akhir.')
        rows=self.rows();result=[];queries={k:v.strip().casefold() for k,v in (queries or {}).items() if v.strip()}
        allowed=None
        if queries:
            nodes={(r['level'],r['code']):r for r in rows};children={}
            for key,r in nodes.items():children.setdefault((r['parent_level'],r['parent']),[]).append(key)
            anchor=min(queries,key=LEVELS.index);allowed=set()
            for key,r in nodes.items():
                if r['level']!=anchor or queries[anchor] not in r['code'].casefold():continue
                chain={};node=key
                while node in nodes and node not in chain:
                    chain[node]=nodes[node];node=(nodes[node]['parent_level'],nodes[node]['parent'])
                if not all(any(x['level']==level and value in x['code'].casefold() for x in chain.values()) for level,value in queries.items()):continue
                allowed.update(chain);todo=[key];seen=set()
                while todo:
                    current=todo.pop()
                    if current in seen:continue
                    seen.add(current);allowed.add(current);todo.extend(children.get(current,[]))
        for r in rows:
            if allowed is not None and (r['level'],r['code']) not in allowed:continue
            if batch and r['batch']!=batch or status and r['status']!=status:continue
            if start and r['ts'][:10]<start or end and r['ts'][:10]>end:continue
            result.append(r)
        return result
    def logs(self):return [dict(r) for r in self.store.db.execute('SELECT * FROM revision_log ORDER BY id DESC')]
    @staticmethod
    def reason(note):
        if not isinstance(note,str) or len(note.strip())<3:raise ValueError('Tulis alasan revisi minimal 3 karakter.')
        if len(note)>1000:raise ValueError('Alasan maksimal 1.000 karakter.')
        return note.strip()
    def _record(self,action,before,after,note,event=True):
        ts=datetime.now().isoformat(timespec='seconds');operator=self.store.get('user')
        self.store.db.execute('INSERT INTO revision_log(ts,action,level,code,batch,before_json,after_json,operator,note) VALUES(?,?,?,?,?,?,?,?,?)',(ts,action,before['level'],before['code'],before['batch'],json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),operator,note))
        self.store.audit(action,before['code']+': '+note)
        if event:
            detail=json.dumps({'reason':note,'before':{k:before.get(k) for k in ('status','parent','parent_level')},'after':{k:after.get(k) for k in ('status','parent','parent_level')}},ensure_ascii=False)
            self.store.db.execute('INSERT INTO events(ts,stage,action,code,status,note,batch,product,operator,source) VALUES(?,?,?,?,?,?,?,?,?,?)',(ts,before['level'],action,before['code'],after['status'],detail,before['batch'],before['product'],operator,'revision'))
    def _state(self,r,**changes):
        v=dict(level=r['level'],code=r['code'],status=r['status'],locked=int(r['locked']),note=r['note'],print_state=r.get('print_state',''));v.update(changes)
        self.store.db.execute('INSERT INTO revision_state VALUES(:level,:code,:status,:locked,:note,:print_state) ON CONFLICT(level,code) DO UPDATE SET status=excluded.status,locked=excluded.locked,note=excluded.note,print_state=excluded.print_state',v)
    def unlock(self,key,note):
        note=self.reason(note);r=self.get(key)
        if not r['locked']:raise ValueError('Data sudah terbuka untuk revisi.')
        with self.store.db:self._state(r,locked=0);self._record('UNLOCK DATA',r,r|{'locked':False},note,False)
    def require_unlocked(self,r):
        if r['locked']:raise ValueError('Klik UNLOCK DATA terlebih dahulu dan tulis alasan.')
        if self.has('delivery_ledger') and self.store.db.execute("SELECT 1 FROM delivery_ledger d JOIN events e ON e.id=d.event_id WHERE e.stage=? AND e.code=? AND d.status='SENDING'",(r['level'],r['code'])).fetchone():raise ValueError('Data sedang dikirim. Tunggu respons server sebelum revisi.')
    def change_status(self,key,status,note):
        note=self.reason(note);r=self.get(key);self.require_unlocked(r)
        if status not in STATES:raise ValueError('Status tidak valid.')
        if status=='VALID' and r['level']!='UNIT':
            package=self.store.db.execute('SELECT 1 FROM packages WHERE stage=? AND code=?',key).fetchone()
            if not package and not self.store.valid_code(r['level'],r['code']):raise ValueError('Format kode tidak valid; kode tidak dapat dipulihkan menjadi kemasan valid.')
        action='PULIHKAN VALID' if status=='VALID' and r['status']!='VALID' else 'TANDAI REJECT' if status=='REJECT' else 'UPDATE STATUS'
        after=r|dict(status=status,note=note,locked=True)
        with self.store.db:
            if r['level']!='UNIT':
                self.store.db.execute('UPDATE packages SET active=? WHERE stage=? AND code=?',(int(status=='VALID'),*key))
                if status=='VALID':self.store.db.execute('INSERT OR IGNORE INTO packages(stage,code,batch,active) VALUES(?,?,?,1)',(*key,r['batch']))
            self._state(after);self._record(action,r,after,note)
            if self.has('pallet_sessions'):
                ancestor=after
                while ancestor:
                    if ancestor['level']=='PALLET' and ancestor.get('run_id'):
                        self.store.db.execute('UPDATE pallet_sessions SET verified=0,verified_at=NULL,verified_by=NULL WHERE run_id=?',(ancestor['run_id'],))
                    ancestor=self.get((ancestor['parent_level'],ancestor['parent'])) if ancestor['parent'] else None
        return self.get(key)
    def candidates(self,key):
        r=self.get(key);allowed={'UNIT':('BOX','CARTON'),'BOX':('CARTON',),'CARTON':('PALLET',),'PALLET':()}[r['level']]
        return [x for x in self.rows() if x['level'] in allowed and x['batch']==r['batch'] and x['status']=='VALID' and x['code']!=r['parent']]
    def move(self,key,target_key,note):
        note=self.reason(note);r=self.get(key);self.require_unlocked(r);target=self.get(target_key)
        if r['status']!='VALID':raise ValueError('Data anak harus VALID sebelum dipindahkan.')
        if not any((x['level'],x['code'])==tuple(target_key) for x in self.candidates(key)):raise ValueError('Parent harus sesuai level, VALID, berbeda dari parent lama, dan berada pada batch yang sama.')
        source=self.get((r['parent_level'],r['parent'])) if r['parent'] else None
        affected={}
        for parent in (source,target):
            while parent and (parent['level'],parent['code']) not in affected:
                affected[(parent['level'],parent['code'])]=parent
                parent=self.get((parent['parent_level'],parent['parent'])) if parent['parent'] else None
        source_run=self.store.db.execute('SELECT * FROM aggregation_runs WHERE id=?',(r.get('owner_run'),)).fetchone() if r.get('owner_run') else None
        target_run=self.store.db.execute('SELECT * FROM aggregation_runs WHERE id=?',(target['run_id'],)).fetchone() if target['run_id'] else None
        if bool(source_run)!=bool(target_run):raise ValueError('Pemindahan harus antar sesi agregasi bertemplate, atau antar kemasan manual.')
        if target_run:
            doc=json.loads(target_run['document']);src=json.loads(source_run['document'])
            if doc['child_level']!=r['level'] or source_run['state']!='COMPLETE' or target_run['state']!='COMPLETE':raise ValueError('Sesi asal/tujuan harus selesai dan jenis child harus sesuai.')
            if source_run['quantity']-1<src['aggregation_min']:raise ValueError('Pemindahan membuat jumlah asal di bawah minimum.')
            if target_run['quantity']+1>doc['aggregation_max']:raise ValueError('Kapasitas parent tujuan sudah penuh.')
            if r['level']=='UNIT' and doc.get('child_product')!=src.get('child_product'):raise ValueError('Produk unit asal dan tujuan berbeda.')
            if r['level']!='UNIT':
                own=self.store.db.execute('SELECT template_id FROM aggregation_runs WHERE id=?',(r['run_id'],)).fetchone() if r['run_id'] else None
                if not own or own['template_id']!=doc.get('child_template_id'):raise ValueError('Template child tidak sesuai parent tujuan.')
        elif r['level']=='UNIT':raise ValueError('Unit harus dipindahkan antar sesi agregasi yang tercatat.')
        after=r|dict(parent=target['code'],parent_level=target['level'],locked=True,note=note)
        with self.store.db:
            if target_run:
                self.store.db.execute('UPDATE aggregation_children SET run_id=? WHERE run_id=? AND child_level=? AND code=?',(target_run['id'],source_run['id'],*key))
                for run,delta in ((source_run,-1),(target_run,1)):
                    self.store.db.execute("UPDATE aggregation_runs SET quantity=quantity+?,print_state='WAITING',print_error='' WHERE id=?",(delta,run['id']))
            if r['level']!='UNIT':self.store.db.execute('UPDATE packages SET parent=? WHERE stage=? AND code=?',(target['code'],*key))
            self._state(after);self._record('PINDAH PARENT',r,after,note)
            for parent in affected.values():
                if parent:
                    self._state(parent,print_state='CETAK ULANG');self._record('ISI PARENT BERUBAH',parent,self.get((parent['level'],parent['code'])),note)
                    if parent['level']=='PALLET' and parent.get('run_id') and self.has('pallet_sessions'):
                        self.store.db.execute('UPDATE pallet_sessions SET verified=0,verified_at=NULL,verified_by=NULL WHERE run_id=?',(parent['run_id'],))
                        self.store.db.execute("UPDATE aggregation_runs SET print_state='WAITING',print_error='' WHERE id=?",(parent['run_id'],))
        return self.get(key)
    def record_print(self,key,note,state):
        note=self.reason(note);r=self.get(key)
        with self.store.db:
            if r['run_id'] and state=='TERKIRIM KE PRINTER':self.store.db.execute("UPDATE aggregation_runs SET print_state='SENT',print_error='' WHERE id=?",(r['run_id'],))
            self._state(r,print_state=state);self._record('REPRINT LABEL',r,r|{'print_state':state},note,False)
    def label(self,key,aggregation,templates):
        r=self.get(key)
        if r['run_id']:return aggregation.print_document(r['run_id'])
        # A trace label for records with no saved production label snapshot.
        from .template_model import default_document,new_element
        doc=default_document(r['level'] if r['level']!='UNIT' else 'BOX');doc.update(width_mm=60,height_mm=40)
        doc['data'].update(serial=r['code'],product_name=r['product'],batch=r['batch'],quantity=str(r['quantity']))
        doc['elements']=[new_element('text',3,2,54,6,text='LABEL TRACEABILITY',font=10),new_element('text',3,9,54,5,text=r['product'],font=8),new_element('barcode',3,15,54,13,text=r['code']),new_element('text',3,30,54,5,text=r['code'],font=8),new_element('text',3,35,54,4,text=r['batch'],font=7)]
        return doc
    def export(self,path,rows,logs=False):
        from .upload_model import safe_cell
        with open(path,'w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f)
            if logs:
                w.writerow(['WAKTU','AKTIVITAS','LEVEL','KODE','BATCH','DARI STATUS','KE STATUS','PARENT LAMA','PARENT BARU','USER','CATATAN'])
                for r in rows:
                    a=json.loads(r['before_json']);b=json.loads(r['after_json']);w.writerow([safe_cell(v) for v in (r['ts'],r['action'],r['level'],r['code'],r['batch'],a['status'],b['status'],a['parent'],b['parent'],r['operator'],r['note'])])
            else:
                w.writerow(['WAKTU','LEVEL','KODE','BATCH','PARENT','STATUS','USER','CATATAN'])
                for r in rows:w.writerow([safe_cell(r[k]) for k in ('ts','level','code','batch','parent','status','operator','note')])
