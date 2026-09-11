"""Local demo repository. Device/API adapters can replace this boundary later."""
import csv
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

STAGES = ('BOX', 'CARTON', 'PALLET')
PREFIX = {'BOX': 'BOX', 'CARTON': 'CTN', 'PALLET': 'PLT'}


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY, ts TEXT NOT NULL, stage TEXT NOT NULL,
                action TEXT NOT NULL, code TEXT NOT NULL, status TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '', batch TEXT NOT NULL,
                product TEXT NOT NULL, operator TEXT NOT NULL, source TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS packages(
                stage TEXT NOT NULL, code TEXT NOT NULL, batch TEXT NOT NULL,
                parent TEXT, active INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY(stage, code));
            CREATE TABLE IF NOT EXISTS audit(
                id INTEGER PRIMARY KEY, ts TEXT NOT NULL, action TEXT NOT NULL,
                detail TEXT NOT NULL, operator TEXT NOT NULL);
        ''')
        if self.get('initialized') is None:
            self._seed()

    def get(self, key, default=None):
        row = self.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key, value):
        self.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', (key, json.dumps(value)))

    def configure(self, values):
        with self.db:
            for key, value in values.items():
                self.put(key, value)
            self.audit('PENGATURAN', ', '.join(values))

    def audit(self, action, detail):
        self.db.execute('INSERT INTO audit(ts,action,detail,operator) VALUES(?,?,?,?)',
                        (datetime.now().isoformat(timespec='seconds'), action, detail,
                         self.get('user', 'WIJAYA')))

    def _seed(self):
        with self.db:
            for key, value in {
                'initialized': True, 'product': 'VAKSIMIBIN INHV IB',
                'batch': 'BATCH-250501-A', 'line': 'AGGREGATION-01', 'shift': 'B',
                'user': 'WIJAYA', 'mode': 'AGGREGATION', 'role': 'OPERATOR',
                'login': '01-05-2025 10:00', 'devices': {x: True for x in
                   ['database', 'printer', 'camera', 'scanner', 'conveyor']},
                'current': {'BOX': 'BOX-250501-0007', 'CARTON': 'CTN-250501-0007',
                            'PALLET': 'PLT-250501-0003'},
            }.items():
                self.put(key, value)
            samples = [
                ('10:26:13', 'BOX', 'Scan Box', 'BOX-250501-0006'),
                ('10:26:02', 'BOX', 'Scan Box', 'BOX-250501-0005'),
                ('10:25:49', 'BOX', 'Scan Box', 'BOX-250501-0003'),
                ('10:25:36', 'CARTON', 'Scan Carton', 'CTN-250501-0007'),
                ('10:25:22', 'PALLET', 'Scan Pallet', 'PLT-250501-0003'),
                ('10:25:10', 'CARTON', 'Verifikasi Kamera', 'CTN-250501-0007'),
                ('10:25:01', 'BOX', 'Verifikasi Kamera', 'BOX-250501-0004'),
                ('10:24:48', 'BOX', 'Scan Label', 'BOX-250501-0004')]
            for ts, stage, action, code in reversed(samples):
                self._event(stage, action, code, 'VALID', source='reference', ts='2025-05-01T'+ts)
                self.db.execute('INSERT OR IGNORE INTO packages(stage,code,batch) VALUES(?,?,?)',
                                (stage, code, self.get('batch')))

    def _event(self, stage, action, code, status, note='', source='local', ts=None):
        ts = ts or datetime.now().isoformat(timespec='seconds')
        cur = self.db.execute('''INSERT INTO events
            (ts,stage,action,code,status,note,batch,product,operator,source)
            VALUES(?,?,?,?,?,?,?,?,?,?)''',
            (ts, stage, action, code, status, note, self.get('batch'),
             self.get('product'), self.get('user'), source))
        return cur.lastrowid

    @staticmethod
    def valid_code(stage, code):
        return stage in STAGES and re.fullmatch(PREFIX[stage]+r'-[A-Z0-9]+(?:-[A-Z0-9]+)*', code) is not None

    def next_code(self, stage):
        prefix = PREFIX[stage]+'-'+datetime.now().strftime('%y%m%d')+'-'
        n = 1
        while self.db.execute('SELECT 1 FROM packages WHERE stage=? AND code=?',
                              (stage, prefix+f'{n:04}')).fetchone():
            n += 1
        return prefix+f'{n:04}'

    def scan(self, stage, code, force_reject=False, note='', source='local', commit=True):
        if stage not in STAGES:
            raise ValueError('Tahap tidak dikenal.')
        code = code.strip().upper()
        if not code:
            raise ValueError('Kode harus diisi.')
        if len(code) > 100:
            raise ValueError('Kode maksimal 100 karakter.')
        duplicate = self.db.execute('SELECT 1 FROM packages WHERE stage=? AND code=?',
                                    (stage, code)).fetchone()
        if duplicate:
            status, note = 'DUPLIKAT', note or 'Kode sudah terdaftar.'
        elif force_reject or not self.valid_code(stage, code):
            status = 'REJECT'
            note = note or 'Format kode tidak sesuai tahap.'
        else:
            status = 'VALID'
            self.db.execute('INSERT INTO packages(stage,code,batch) VALUES(?,?,?)',
                            (stage, code, self.get('batch')))
            current = self.get('current')
            current[stage] = code
            self.put('current', current)
        event_id = self._event(stage, 'Scan '+stage.title(), code, status, note, source)
        if commit:
            self.db.commit()
        return event_id, status

    def events(self, stage=None, status=None, limit=1000):
        query, args = 'SELECT * FROM events WHERE 1=1', []
        if stage:
            query += ' AND stage=?'
            args.append(stage)
        if status:
            query += ' AND status=?'
            args.append(status)
        query += ' ORDER BY id DESC LIMIT ?'
        return [dict(row) for row in self.db.execute(query, args+[limit])]

    def summary(self):
        stages = {
            'BOX': {'total': 256, 'valid': 210, 'reject': 18, 'duplicate': 10},
            'CARTON': {'total': 42, 'valid': 30, 'reject': 6, 'duplicate': 6},
            'PALLET': {'total': 15, 'valid': 14, 'reject': 1, 'duplicate': 0},
        }
        for row in self.db.execute("SELECT stage,status,COUNT(*) n FROM events WHERE source!='reference' GROUP BY stage,status"):
            if row['stage'] not in stages or row['status'] not in ('VALID','REJECT','DUPLIKAT'):continue
            target = stages[row['stage']]
            key = {'VALID': 'valid', 'REJECT': 'reject', 'DUPLIKAT': 'duplicate'}[row['status']]
            target[key] += row['n']
            target['total'] += row['n']
        return {'units': 18450, 'valid': 17120, 'reject': 1330, 'duplicate': 650,
                'stages': stages}

    def available(self, stage):
        return [dict(x) for x in self.db.execute(
            'SELECT * FROM packages WHERE stage=? AND active=1 ORDER BY code', (stage,))]

    def link(self, stage, child, parent):
        if stage not in ('BOX', 'CARTON'):
            raise ValueError('Pallet adalah tingkat tertinggi.')
        parent_stage = STAGES[STAGES.index(stage)+1]
        a = self.db.execute('SELECT * FROM packages WHERE stage=? AND code=? AND active=1', (stage, child)).fetchone()
        b = self.db.execute('SELECT * FROM packages WHERE stage=? AND code=? AND active=1', (parent_stage, parent)).fetchone()
        if not a or not b:
            raise ValueError('Kemasan anak dan induk harus berstatus valid.')
        if a['batch'] != b['batch']:
            raise ValueError('Batch kemasan anak dan induk harus sama.')
        if a['parent']:
            raise ValueError('Kemasan anak sudah terhubung ke '+a['parent'])
        with self.db:
            self.db.execute('UPDATE packages SET parent=? WHERE stage=? AND code=?', (parent, stage, child))
            self.audit('HUBUNGKAN', child+' → '+parent)

    def revise(self, event_id, note):
        row = self.db.execute('SELECT * FROM events WHERE id=?', (event_id,)).fetchone()
        if not row or not note.strip():
            raise ValueError('Pilih aktivitas dan tulis alasan revisi.')
        with self.db:
            self.db.execute('UPDATE events SET note=? WHERE id=?', (note.strip(), event_id))
            self.audit('REVISI CATATAN', json.dumps({'event_id': event_id, 'before': row['note'], 'after': note.strip()}))

    def import_rows(self, rows):
        results = []
        with self.db:
            for row in rows:
                results.append(self.scan(row['stage'], row['code'], source='import', commit=False))
            self.audit('IMPORT CSV', str(len(rows))+' baris')
        return results

    @staticmethod
    def read_import(path):
        with open(path, newline='', encoding='utf-8-sig') as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or not {'stage', 'code'}.issubset(reader.fieldnames):
                raise ValueError('CSV wajib memiliki kolom stage,code.')
            rows = []
            for i, row in enumerate(reader, 2):
                stage = (row.get('stage') or '').strip().upper()
                code = (row.get('code') or '').strip().upper()
                if stage not in STAGES or not code or len(code) > 100:
                    raise ValueError(f'Baris {i}: tahap harus BOX/CARTON/PALLET dan kode wajib diisi (maks. 100 karakter).')
                rows.append({'stage': stage, 'code': code})
                if len(rows) > 10000:
                    raise ValueError('Maksimal 10.000 baris per impor.')
        if not rows:
            raise ValueError('CSV tidak berisi data.')
        return rows

    def export_json(self, path):
        payload = {'application': 'AGREGASI UI', 'mode': 'SIMULASI LOKAL',
                   'exported_at': datetime.now().isoformat(),
                   'snapshot_note': 'Angka unit dan grafik awal adalah contoh dari referensi, bukan produksi langsung.',
                   'summary': self.summary(), 'events': self.events(limit=1000000),
                   'packages': [dict(x) for x in self.db.execute('SELECT * FROM packages')],
                   'audit': [dict(x) for x in self.db.execute('SELECT * FROM audit')]}
        Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
        with self.db:
            self.audit('EKSPOR JSON', Path(path).name)

    def close(self):
        self.db.close()
