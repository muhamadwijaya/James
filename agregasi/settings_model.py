"""Validated configuration, local operator profiles, backups and delivery ledger."""
from copy import deepcopy
from .display_preferences import display_defaults, validate_display
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
import csv
import json
import re
import sqlite3

VERSION = '3.12.0'
LEVELS = ('BOX', 'CARTON', 'PALLET')
ROLES = ('ADMIN', 'OPERATOR', 'QC', 'MAINTENANCE')
SCAN_MODES = ('SCANNER GUN', 'KAMERA IP')


def scanner_camera_url(profile):
    """HTTP snapshot URL of a scanner profile that reads barcodes with a camera."""
    raw = str(profile.get('camera_ip', '')).strip()
    if not raw:
        raise ValueError('Isi alamat IP kamera scanner pada Pengaturan.')
    target = urlparse(raw if '://' in raw else 'http://' + raw)
    if target.scheme not in ('http', 'https') or not target.hostname or target.username or target.password:
        raise ValueError('Alamat kamera scanner: http://IP atau IP saja; port diisi terpisah.')
    port = profile.get('camera_port')
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError('Port kamera scanner harus 1-65535.')
    path = target.path if target.path not in ('', '/') else '/snapshot.jpg'
    return f'{target.scheme}://{target.hostname}:{port}{path}' + (('?' + target.query) if target.query else '')


def defaults():
    return {
        'display': display_defaults(),
        'line': 'AGGREGATION-01', 'shift': 'B', 'mode': 'AGGREGATION',
        'line_active': True, 'start_delay': 2.0, 'stop_delay': 2.0,
        'cache_limit': 1000, 'auto_upload': True, 'upload_timeout': 30,
        'mfd': '2025-05-01', 'language': 'BAHASA INDONESIA', 'theme': 'DARK BLUE',
        'server_host': '192.168.10.15', 'project_url': 'https://api.aggregation.local',
        'api_token': '', 'sync_interval': 60, 'retry_count': 3,
        'printers': {level: {'device': device, 'dpi': dpi, 'darkness': darkness,
                    'speed': speed, 'label': label}
                     for level, device, dpi, darkness, speed, label in [
                         ('BOX', 'ZEBRA ZD421', 203, 15, 5, '60 x 40 mm'),
                         ('CARTON', 'ZEBRA ZT231', 203, 15, 6, '100 x 60 mm'),
                         ('PALLET', 'ZEBRA ZT411', 300, 18, 6, '100 x 150 mm')]},
        'scanners': {level: {'device': 'USB-SCANNER-0'+str(i), 'mode': 'SCANNER GUN',
                     'port': 'COM'+str(i+2), 'baud': 9600,
                     'camera_ip': '192.168.10.3'+str(i), 'camera_port': 8080,
                     'trigger': 'AUTO', 'autofocus': True,
                     'exposure': 120, 'resolution': '1280 x 720'}
                     for i, level in enumerate(LEVELS, 1)},
        'camera': {'device': 'CAM-PTZ-01', 'address': '192.168.10.30',
                   'trigger': 'MANUAL', 'autofocus': True, 'exposure': 150,
                   'resolution': '1920 x 1080'},
        'backup_frequency': 'SETIAP HARI', 'backup_time': '02:00', 'backup_days': 30,
    }


def merge_defaults(raw):
    def merge(base, values):
        for key, value in values.items():
            if key not in base:
                continue
            if isinstance(base[key], dict) and isinstance(value, dict):
                merge(base[key], value)
            else:
                base[key] = deepcopy(value)
        return base
    return merge(defaults(), raw)


def validate(raw):
    if not isinstance(raw, dict):
        raise ValueError('Format konfigurasi harus berupa objek JSON.')
    cfg = merge_defaults(raw)
    cfg['display'] = validate_display(cfg['display'])
    def number(obj, key, minimum, maximum, integer=True):
        value = obj[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f'{key}: nilai harus angka.')
        if not minimum <= value <= maximum or (integer and int(value) != value):
            raise ValueError(f'{key}: isi nilai {minimum}–{maximum}.')
    def choice(obj, key, options):
        if obj[key] not in options:
            raise ValueError(f'{key}: pilihan tidak dikenal.')
    for key in ('line', 'server_host', 'project_url', 'api_token'):
        if not isinstance(cfg[key], str) or len(cfg[key]) > 2048:
            raise ValueError(f'{key}: teks tidak valid.')
        cfg[key] = cfg[key].strip()
    if not cfg['line'] or len(cfg['line']) > 48:
        raise ValueError('Nama line wajib diisi, maksimal 48 karakter.')
    choice(cfg, 'shift', ('A', 'B', 'C'))
    choice(cfg, 'mode', ('AGGREGATION', 'SERIALIZATION'))
    choice(cfg, 'language', ('BAHASA INDONESIA', 'ENGLISH'))
    choice(cfg, 'theme', ('DARK BLUE', 'HIGH CONTRAST'))
    choice(cfg, 'backup_frequency', ('NONAKTIF', 'SETIAP HARI', 'SETIAP MINGGU'))
    for key in ('line_active', 'auto_upload'):
        if not isinstance(cfg[key], bool):
            raise ValueError(f'{key}: nilai harus aktif/nonaktif.')
    for key in ('start_delay', 'stop_delay'):
        number(cfg, key, 0, 600, False)
    for key, low, high in [('cache_limit', 1, 100000), ('upload_timeout', 1, 120),
                           ('sync_interval', 5, 86400), ('retry_count', 0, 10),
                           ('backup_days', 1, 3650)]:
        number(cfg, key, low, high)
    try:
        datetime.strptime(cfg['mfd'], '%Y-%m-%d')
        datetime.strptime(cfg['backup_time'], '%H:%M')
    except (ValueError, TypeError):
        raise ValueError('Tanggal MFD atau jam backup tidak valid.')
    if cfg['project_url']:
        url = urlparse(cfg['project_url'])
        if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError('Project URL harus berupa alamat HTTP/HTTPS tanpa token di URL.')
        if cfg['api_token'] and url.scheme != 'https' and url.hostname not in ('localhost', '127.0.0.1', '::1'):
            raise ValueError('Gunakan HTTPS sebelum menyimpan API token untuk server jaringan.')
    for level in LEVELS:
        obj = cfg['printers'][level]
        if not isinstance(obj, dict) or not isinstance(obj.get('device'), str):
            raise ValueError('Profil printer tidak valid.')
        choice(obj, 'dpi', (203, 300, 600))
        number(obj, 'darkness', 0, 30)
        number(obj, 'speed', 1, 14)
        if not isinstance(obj['label'], str) or not re.fullmatch(r'\d{1,3} x \d{1,3} mm', obj['label']):
            raise ValueError('Ukuran label: contoh 100 x 150 mm.')
        if any(not 10 <= float(v) <= 300 for v in obj['label'].removesuffix(' mm').split(' x ')):
            raise ValueError('Ukuran label harus 10–300 mm.')
        if obj['device'].startswith('tcp://'):
            target = urlparse(obj['device'])
            if not target.hostname or not target.port or target.username or target.password:
                raise ValueError('Printer jaringan: tcp://alamat-ip:9100.')
    for obj in [*cfg['scanners'].values(), cfg['camera']]:
        if not isinstance(obj, dict) or not isinstance(obj.get('device'), str):
            raise ValueError('Profil scanner/kamera tidak valid.')
        choice(obj, 'trigger', ('AUTO', 'MANUAL'))
        number(obj, 'exposure', 1, 10000)
        choice(obj, 'resolution', ('640 x 480', '1280 x 720', '1920 x 1080'))
        if not isinstance(obj['autofocus'], bool):
            raise ValueError('Autofocus harus aktif/nonaktif.')
    if cfg['scanners']['PALLET']['mode'] != 'SCANNER GUN':
        raise ValueError('Scanner PALLET hanya mendukung scanner gun.')
    for obj in cfg['scanners'].values():
        choice(obj, 'baud', (9600, 19200, 38400, 57600, 115200))
        choice(obj, 'mode', SCAN_MODES)
        if not isinstance(obj['port'], str) or not obj['port'].strip():
            raise ValueError('Port scanner wajib diisi.')
        if not isinstance(obj['camera_ip'], str) or len(obj['camera_ip']) > 200:
            raise ValueError('Alamat IP kamera scanner tidak valid.')
        number(obj, 'camera_port', 1, 65535)
        # A camera scanner must be reachable before the line depends on it.
        if obj['mode'] == 'KAMERA IP':
            scanner_camera_url(obj)
    if not isinstance(cfg['camera']['address'], str):
        raise ValueError('Alamat kamera tidak valid.')
    return cfg


class SettingsRepository:
    def __init__(self, store):
        self.store = store
        self.root = store.path.parent
        store.db.executescript('''
            CREATE TABLE IF NOT EXISTS operator_profiles(
              username TEXT PRIMARY KEY COLLATE NOCASE, role TEXT NOT NULL,
              shift TEXT NOT NULL, active INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS delivery_ledger(
              event_id INTEGER PRIMARY KEY REFERENCES events(id), status TEXT NOT NULL,
              attempts INTEGER NOT NULL DEFAULT 0, detail TEXT NOT NULL DEFAULT '',
              updated_at TEXT NOT NULL);
        ''')
        if store.get('operator_profiles_initialized') is not True:
            with store.db:
                store.db.executemany('INSERT OR IGNORE INTO operator_profiles VALUES(?,?,?,?)', [
                    ('admin','ADMIN','ALL',1),('wijaya','OPERATOR','B',1),
                    ('operator1','OPERATOR','A',1),('operator2','OPERATOR','C',0),
                    ('qc1','QC','ALL',1),('qc2','QC','B',1),('maintenance','MAINTENANCE','ALL',1)])
                store.put('operator_profiles_initialized', True)

    def load(self):
        cfg = merge_defaults(self.store.get('configuration', {}))
        for key in ('line', 'shift', 'mode'):
            cfg[key] = self.store.get(key, cfg[key])
        return cfg

    def save(self, raw):
        cfg = validate(raw)
        self.store.configure({'configuration': cfg, 'line': cfg['line'], 'shift': cfg['shift'],
                              'mode': cfg['mode'], 'settings_updated': datetime.now().isoformat(timespec='seconds')})
        try:
            self.store.path.chmod(0o600)
        except OSError:
            pass
        return cfg

    def users(self):
        return [dict(r) for r in self.store.db.execute('SELECT * FROM operator_profiles ORDER BY rowid')]

    def save_user(self, username, role, shift, active, existing=None):
        username = username.strip()
        if not re.fullmatch(r'[A-Za-z0-9_.-]{2,40}', username):
            raise ValueError('Username: 2–40 huruf, angka, titik, garis bawah atau tanda hubung.')
        if role not in ROLES or shift not in ('ALL','A','B','C'):
            raise ValueError('Role atau shift tidak valid.')
        if existing:
            old = self.store.db.execute('SELECT * FROM operator_profiles WHERE username=?', (existing,)).fetchone()
            if not old:
                raise ValueError('Profil tidak ditemukan.')
            if old['role'] == 'ADMIN' and old['active'] and (role != 'ADMIN' or not active):
                n = self.store.db.execute("SELECT COUNT(*) FROM operator_profiles WHERE role='ADMIN' AND active=1").fetchone()[0]
                if n <= 1:
                    raise ValueError('Minimal satu profil ADMIN harus tetap aktif.')
            if existing.casefold() == str(self.store.get('user')).casefold() and not active:
                raise ValueError('Profil sesi yang sedang digunakan tidak dapat dinonaktifkan.')
        with self.store.db:
            try:
                if existing:
                    self.store.db.execute('UPDATE operator_profiles SET username=?,role=?,shift=?,active=? WHERE username=?',
                                          (username, role, shift, int(active), existing))
                else:
                    self.store.db.execute('INSERT INTO operator_profiles VALUES(?,?,?,?)', (username,role,shift,int(active)))
            except sqlite3.IntegrityError:
                raise ValueError('Username sudah digunakan.')
            if existing and existing.casefold() == str(self.store.get('user')).casefold():
                self.store.put('user', username.upper()); self.store.put('role', role)
            self.store.audit('EDIT PROFIL' if existing else 'TAMBAH PROFIL', username)

    def backup(self, now=None):
        now = now or datetime.now()
        folder = self.root / 'backups'; folder.mkdir(exist_ok=True)
        target = folder / ('agregasi-'+now.strftime('%Y%m%d-%H%M%S-%f')+'.sqlite3')
        self.store.db.commit()
        with sqlite3.connect(target) as db:
            self.store.db.backup(db)
        try:
            target.chmod(0o600)
        except OSError:
            pass
        with self.store.db:
            self.store.put('last_backup', now.isoformat())
            self.store.audit('BACKUP', target.name)
        cutoff = now - timedelta(days=self.load()['backup_days'])
        for path in folder.glob('agregasi-*.sqlite3'):
            if path != target and not path.is_symlink() and datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
                path.unlink()
        return target

    def backup_due(self, now=None):
        now = now or datetime.now(); cfg = self.load()
        if cfg['backup_frequency'] == 'NONAKTIF' or now.strftime('%H:%M') < cfg['backup_time']:
            return False
        last = self.store.get('last_backup')
        if last:
            date = datetime.fromisoformat(last).date()
            interval = 7 if cfg['backup_frequency'] == 'SETIAP MINGGU' else 1
            if (now.date()-date).days < interval:
                return False
        return True

    def export_configuration(self, path):
        cfg = self.load(); cfg['api_token'] = ''
        Path(path).write_text(json.dumps({'application':'AGREGASI','version':VERSION,'configuration':cfg},
                                        indent=2, ensure_ascii=False), encoding='utf-8')

    def restore(self, path):
        path = Path(path)
        if path.suffix.lower() in ('.sqlite3','.db'):
            with sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True) as db:
                row = db.execute("SELECT value FROM settings WHERE key='configuration'").fetchone()
                if not row:
                    raise ValueError('Backup ini tidak memuat konfigurasi lengkap.')
                raw = json.loads(row[0])
        else:
            payload = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(payload, dict) or 'configuration' not in payload:
                raise ValueError('Berkas bukan ekspor konfigurasi AGREGASI.')
            raw = payload['configuration']
        cfg = validate(raw)
        # Exported configurations intentionally omit the API token.
        if not cfg['api_token']:
            cfg['api_token'] = self.load()['api_token']
        cfg = validate(cfg)
        self.backup()
        self.save(cfg)
        with self.store.db:
            self.store.audit('RESTORE KONFIGURASI', path.name)
        return cfg

    def clear_temp(self):
        folder = self.root / 'temp'; count = size = 0
        if folder.is_dir() and not folder.is_symlink():
            for path in folder.iterdir():
                if path.is_file() and not path.is_symlink():
                    size += path.stat().st_size; path.unlink(); count += 1
        with self.store.db:
            self.store.audit('BERSIHKAN TEMP', f'{count} berkas, {size} byte; data produksi tidak dihapus')
        return count, size

    def export_log(self, path):
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f); writer.writerow(['WAKTU','AKSI','DETAIL','OPERATOR'])
            for r in self.store.db.execute('SELECT ts,action,detail,operator FROM audit ORDER BY id DESC'):
                writer.writerow([("'"+str(v)) if str(v).startswith(('=','+','-','@')) else v for v in r])

    def delivery_rows(self):
        return [dict(r) for r in self.store.db.execute('''
            SELECT e.*, COALESCE(d.status,'PENDING') delivery_status,
                   COALESCE(d.attempts,0) attempts, COALESCE(d.detail,'') delivery_detail
            FROM events e LEFT JOIN delivery_ledger d ON d.event_id=e.id
            WHERE e.source!='reference' ORDER BY e.id DESC''')]

    def mark_delivery(self, ids, state, detail='', increment=False):
        with self.store.db:
            for identifier in ids:
                self.store.db.execute('''INSERT INTO delivery_ledger VALUES(?,?,?, ?,?)
                    ON CONFLICT(event_id) DO UPDATE SET status=excluded.status,
                    attempts=delivery_ledger.attempts+?,detail=excluded.detail,updated_at=excluded.updated_at''',
                    (identifier,state,int(increment),detail,datetime.now().isoformat(timespec='seconds'),int(increment)))
