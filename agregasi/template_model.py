"""Persistent templates and portable, versioned label documents (millimetres)."""
import base64
from copy import deepcopy
from datetime import datetime
import json
import math
import re
from uuid import uuid4

LEVELS = ('BOX', 'CARTON', 'PALLET')
PREFIXES = {'BOX': 'BOX', 'CARTON': 'CTN', 'PALLET': 'PLT'}
KINDS = {'text', 'barcode', 'datamatrix', 'qr', 'rectangle', 'line', 'image', 'symbol'}
PRINTER_KINDS = ('LABEL', 'TIJ')
FIELDS = ('serial', 'gtin', 'nie', 'prefix', 'product_name', 'batch', 'mfg_date', 'exp_date',
          'destination', 'ship_to', 'quantity', 'weight', 'template_name')


def new_element(kind, x, y, w, h, **values):
    result = dict(id=uuid4().hex, type=kind, x=x, y=y, w=w, h=h,
                  text='', font=7, bold=False, color='#111820', fill='none',
                  stroke=0.25, align='left', locked=False)
    result.update(values)
    return result


def default_document(level):
    if level not in LEVELS:
        raise ValueError('Level template tidak dikenal.')
    pallet = level == 'PALLET'
    doc = {'schema_version': 1, 'level': level, 'name': f'MASTER {level} SAMPLE',
           'gtin': '18991234567890', 'nie': '', 'prefix': PREFIXES[level], 'serial_type': 'SERIAL',
           'min_digits': 4, 'max_digits': 18, 'child_level': {'BOX':'UNIT','CARTON':'BOX','PALLET':'CARTON'}[level],
           'width_mm': 100, 'height_mm': 150 if pallet else 60, 'dpi': 300,
           'aggregation_min':1,'aggregation_max':{'BOX':50,'CARTON':12,'PALLET':16}[level],'print_mode':'MANUAL',
           'child_product':None,'printer_kind':'LABEL','printer_host':'','printer_port':9100,
           'data': {'serial': '189912345678901234' if pallet else '18991234567890',
                    'gtin': '18991234567890', 'nie': '', 'product_name': 'AGREGASI PRODUCT SAMPLE',
                    'batch': 'BATCH-260501-A', 'mfg_date': '01/05/2025', 'exp_date': '01/05/2026',
                    'destination': 'PT. SAMPLE INDONESIA\nJl. Industri Raya No. 123\nCikarang - Jawa Barat 17530\nIndonesia\nTelp. (021) 1234 5678',
                    'ship_to': 'PT. SAMPLE INDONESIA\nJl. Industri Raya No. 123\nCikarang - Jawa Barat 17530\nIndonesia',
                    'quantity': '16 CARTON' if pallet else ('12 BOX' if level == 'CARTON' else '50 UNIT'),
                    'weight': '128.50 kg' if pallet else '8.00 kg'}, 'elements': []}
    elements = doc['elements']
    def add(kind, x, y, w, h, **values):
        element = new_element(kind, x, y, w, h)
        element.update(values)
        elements.append(element)
    def text(x,y,w,h,value,font=7,bold=False):
        add('text',x,y,w,h,text=value,font=font,bold=bold)
    def line(x,y,w,h=0.2):
        add('line',x,y,w,h,stroke=0.2,dashed=True)
    add('rectangle',3,3,94,140 if pallet else 52,stroke=0.25,dashed=True)
    text(5,5,62,4,'SSCC / PALLET CODE' if pallet else level+' CODE',7,True)
    text(5,11,62,7,'{{serial}}',12 if pallet else 11,True)
    add('barcode',5,21 if pallet else 18,61,22 if pallet else 9,text='{{serial}}',human=True)
    text(70,5,25,4,'2D CODE',7,True)
    add('qr',70,10,24,24 if pallet else 19,text='{{serial}}')
    if pallet:
        line(3,47,94); line(48,47,0.2,71)
        for y,label,value in [(49,'PRODUCT NAME','{{product_name}}'),(64,'BATCH / LOT','{{batch}}')]:
            text(5,y,41,4,label,6.5,True);text(5,y+5,41,7,value,7)
        line(3,62,45);line(3,77,45);line(3,92,45)
        text(5,79,20,4,'MFG DATE',6.5,True);text(27,79,20,4,'EXP DATE',6.5,True)
        text(5,84,20,5,'{{mfg_date}}',6.5);text(27,84,20,5,'{{exp_date}}',6.5)
        text(5,94,40,4,'QTY CARTON',6.5,True)
        add('symbol',5,101,7,8,symbol='package')
        text(14,102,18,7,'{{quantity}}',7,True)
        add('symbol',33,102,4,6,symbol='weight');text(37,102,10,7,'{{weight}}',4.8,True)
        text(50,49,44,4,'DESTINATION',6.5,True);text(50,55,44,24,'{{destination}}',6.5)
        line(48,81,49);text(50,83,44,4,'SHIP TO',6.5,True);text(50,89,44,25,'{{ship_to}}',6.5)
        line(3,118,94)
        for x,icon,label in [(7,'dry','KEEP DRY'),(30,'stack','DO NOT STACK'),(53,'up','THIS SIDE UP'),(76,'care','HANDLE WITH CARE')]:
            add('symbol',x+4,123,12,12,symbol=icon);text(x,137,21,4,label,4.8,True)
        text(4,144,92,3,'{{template_name}}  |  {{width_mm}} x {{height_mm}} mm  |  DPI {{dpi}}',5.2)
    else:
        line(3,30,94);line(52,30,0.2,15)
        text(5,31,46,3,'PRODUCT NAME',5.5,True);text(5,35,46,4,'{{product_name}}',6.5)
        text(54,31,40,3,'BATCH / LOT',5.5,True);text(54,35,40,4,'{{batch}}',6.5)
        text(5,40,46,4,'MFG {{mfg_date}}   EXP {{exp_date}}',5.2)
        text(54,40,40,4,'{{quantity}}   {{weight}}',6,True);line(3,45,94)
        for x,icon,label in [(5,'dry','KEEP DRY'),(29,'stack','DO NOT STACK'),(53,'up','THIS SIDE UP'),(77,'care','HANDLE WITH CARE')]:
            add('symbol',x,47,5,5,symbol=icon);text(x+6,47,16,5,label,4.4,True)
        text(4,56,92,3,'{{template_name}}  |  {{width_mm}} x {{height_mm}} mm  |  DPI {{dpi}}',5.2)
    return doc


def resolve_text(text, document):
    data = dict(document.get('data', {}), gtin=document.get('gtin',''), nie=document.get('nie',document.get('data',{}).get('nie','')), prefix=document.get('prefix',''), template_name=document.get('name',''), width_mm=f"{document.get('width_mm',100):g}", height_mm=f"{document.get('height_mm',60):g}", dpi=str(document.get('dpi',300)))
    return re.sub(r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}', lambda m: str(data.get(m[1], m[0])), str(text))


def validate_document(document):
    if not isinstance(document,dict) or document.get('schema_version') != 1:
        raise ValueError('Format dokumen template tidak didukung (schema_version 1).')
    doc=deepcopy(document)
    if doc.get('level') not in LEVELS: raise ValueError('Level harus BOX, CARTON, atau PALLET.')
    if not isinstance(doc.get('name'),str) or not doc['name'].strip(): raise ValueError('Nama template wajib diisi sebagai teks.')
    if len(str(doc['name']))>120: raise ValueError('Nama template maksimal 120 karakter.')
    if not isinstance(doc.get('nie',''),str) or len(doc.get('nie',''))>80: raise ValueError('NIE maksimal 80 karakter.')
    if not re.fullmatch(r'\d{8}|\d{12,14}',str(doc.get('gtin',''))): raise ValueError('GTIN harus 8, 12, 13, atau 14 digit.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,20}',str(doc.get('prefix',''))): raise ValueError('Prefix hanya huruf, angka, - atau _.')
    if doc.get('serial_type') not in ('SERIAL','UNIX'): raise ValueError('Tipe serial tidak dikenal.')
    if not isinstance(doc.get('active',True),bool):raise ValueError('Status aktif harus true atau false.')
    for key in ('child_template_id','print_template_id'):
        if doc.get(key) is not None and (not isinstance(doc[key],str) or len(doc[key])>128):raise ValueError('Referensi template tidak valid.')
    for key in ('child_template_name','print_template_name'):
        if key in doc and (not isinstance(doc[key],str) or len(doc[key])>160):raise ValueError('Nama referensi template tidak valid.')
    for key,low,high in [('width_mm',20,300),('height_mm',20,300),('dpi',72,600),('min_digits',1,50),('max_digits',1,50)]:
        val=doc.get(key)
        if not isinstance(val,(int,float)) or isinstance(val,bool) or not math.isfinite(val) or not low<=val<=high:
            raise ValueError(f'{key} harus berada pada {low}–{high}.')
        if key in ('dpi','min_digits','max_digits') and (not isinstance(val,int)):
            raise ValueError(f'{key} harus berupa bilangan bulat.')
    if doc['min_digits']>doc['max_digits']: raise ValueError('Min digit tidak boleh melebihi max digit.')
    if doc.get('child_level') not in {'BOX':('UNIT',),'CARTON':('BOX','UNIT'),'PALLET':('CARTON',)}[doc['level']]:
        raise ValueError('Level child tidak sesuai. CARTON dapat memakai BOX atau UNIT langsung.')
    for key,default in [('aggregation_min',1),('aggregation_max',{'BOX':50,'CARTON':12,'PALLET':16}[doc['level']])]:
        doc.setdefault(key,default)
        if not isinstance(doc[key],int) or isinstance(doc[key],bool) or not 1<=doc[key]<=1000000:
            raise ValueError('Target quantity harus bilangan bulat 1–1.000.000.')
    if doc['aggregation_min']>doc['aggregation_max']:raise ValueError('Target minimum tidak boleh melebihi target maksimum.')
    doc.setdefault('print_mode','MANUAL');doc.setdefault('child_product',None)
    if doc['print_mode'] not in ('AUTO','MANUAL'):raise ValueError('Mode cetak harus AUTO atau MANUAL.')
    doc.setdefault('printer_kind','LABEL');doc.setdefault('printer_host','');doc.setdefault('printer_port',9100)
    if doc['printer_kind'] not in PRINTER_KINDS:raise ValueError('Jenis printer harus LABEL atau TIJ.')
    if doc['printer_kind']=='TIJ' and doc['level']!='BOX':raise ValueError('Printer TIJ hanya untuk template agregasi tahap 1 (BOX).')
    if not isinstance(doc['printer_host'],str) or len(doc['printer_host'])>200:raise ValueError('Alamat printer TIJ tidak valid.')
    doc['printer_host']=doc['printer_host'].strip()
    if isinstance(doc['printer_port'],bool) or not isinstance(doc['printer_port'],int) or not 1<=doc['printer_port']<=65535:
        raise ValueError('Port printer TIJ harus 1-65535.')
    if doc['printer_kind']=='TIJ' and not re.fullmatch(r'[A-Za-z0-9_.-]{1,200}',doc['printer_host']):
        raise ValueError('Isi IP atau hostname printer TIJ, contoh 192.168.10.40.')
    product=doc['child_product']
    if product is not None:
        if not isinstance(product,dict) or not isinstance(product.get('id'),(str,int)) or isinstance(product.get('id'),bool) or not isinstance(product.get('name'),str) or not product['name'].strip():raise ValueError('Relasi produk child tidak valid.')
        source=product.get('source')
        if not isinstance(source,dict) or any(not isinstance(source.get(k),str) or not source[k] for k in ('path','table','id_column','name_column')):raise ValueError('Sumber produk child tidak lengkap.')
    if doc['child_level']=='UNIT' and doc.get('child_template_id'):raise ValueError('Pilih salah satu: template BOX atau produk child langsung.')
    if doc['child_level']!='UNIT' and product is not None:raise ValueError('Relasi produk langsung hanya untuk mode UNIT.')
    if not isinstance(doc.get('data'),dict) or any(not isinstance(k,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,49}',k) or not isinstance(v,str) or len(v)>4000 for k,v in doc['data'].items()):
        raise ValueError('Data dinamis tidak valid.')
    if not isinstance(doc.get('elements'),list) or len(doc['elements'])>250: raise ValueError('Maksimal 250 objek per template.')
    identifiers=set()
    for e in doc['elements']:
        if not isinstance(e,dict) or e.get('type') not in KINDS: raise ValueError('Tipe objek tidak didukung.')
        if not isinstance(e.get('id'),str) or not e['id'] or e['id'] in identifiers: raise ValueError('ID objek kosong atau ganda.')
        identifiers.add(e['id'])
        for key in ('x','y','w','h'):
            val=e.get(key)
            if not isinstance(val,(int,float)) or isinstance(val,bool) or not math.isfinite(val):raise ValueError('Koordinat objek tidak valid.')
        if e['w']<=0 or e['h']<=0 or e['x']<0 or e['y']<0 or e['x']+e['w']>doc['width_mm']+0.01 or e['y']+e['h']>doc['height_mm']+0.01:
            raise ValueError('Objek berada di luar ukuran label.')
        if not isinstance(e.get('text',''),str) or len(e.get('text',''))>4000:raise ValueError('Teks objek terlalu panjang.')
        if not isinstance(e.get('font',7),(int,float)) or not 3<=e.get('font',7)<=72:raise ValueError('Font objek harus 3–72 pt.')
        if not isinstance(e.get('stroke',0.25),(int,float)) or not 0.05<=e.get('stroke',0.25)<=5:raise ValueError('Tebal garis tidak valid.')
        if not re.fullmatch(r'#[0-9a-fA-F]{6}',e.get('color','#111820')):raise ValueError('Warna objek tidak valid.')
        if e.get('fill','none')!='none' and not re.fullmatch(r'#[0-9a-fA-F]{6}',e['fill']):raise ValueError('Warna isi tidak valid.')
        if e['type']=='image':
            try:
                raw=base64.b64decode(e.get('image',''),validate=True)
                if not raw or len(raw)>3_000_000:raise ValueError()
            except Exception:raise ValueError('Gambar tertanam tidak valid atau terlalu besar.') from None
    return doc


class TemplateRepository:
    def __init__(self,store):
        self.store=store
        store.db.execute('''CREATE TABLE IF NOT EXISTS label_templates(
            id TEXT PRIMARY KEY, level TEXT NOT NULL, name TEXT NOT NULL,
            document TEXT NOT NULL, published_document TEXT, revision INTEGER NOT NULL DEFAULT 0,
            is_default INTEGER NOT NULL DEFAULT 0, deleted INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL)''')
        store.db.execute('''CREATE TABLE IF NOT EXISTS template_activity(
            id INTEGER PRIMARY KEY, template_id TEXT, level TEXT NOT NULL,
            action TEXT NOT NULL, detail TEXT NOT NULL, ts TEXT NOT NULL, operator TEXT NOT NULL)''')
        store.db.execute('CREATE TABLE IF NOT EXISTS aggregation_products(id TEXT PRIMARY KEY,name TEXT NOT NULL)')
        if not store.get('aggregation_products_initialized',False):
            store.db.execute('INSERT OR IGNORE INTO aggregation_products VALUES(?,?)',('CURRENT-PRODUCT',store.get('product','PRODUK AKTIF')))
            store.put('aggregation_products_initialized',True)
        store.db.execute("""CREATE TABLE IF NOT EXISTS template_agregasi (template_id TEXT PRIMARY KEY, level TEXT NOT NULL, name TEXT NOT NULL, child_level TEXT NOT NULL, child_template_id TEXT, child_product_id TEXT, child_product_name TEXT, child_product_source TEXT, target_min INTEGER NOT NULL CHECK(target_min>=1), target_max INTEGER NOT NULL CHECK(target_max>=target_min), print_mode TEXT NOT NULL CHECK(print_mode IN ('AUTO','MANUAL')), document TEXT NOT NULL, active INTEGER NOT NULL, deleted INTEGER NOT NULL, updated_at TEXT NOT NULL)""")
        if not store.get('template_editor_initialized',False):
            from .template_database import product_choices
            products=product_choices(store)
            with store.db:
                for level in LEVELS:
                    doc=default_document(level)
                    if level=='BOX' and products:doc['child_product']=products[0];doc['child_template_name']=products[0]['name']
                    self._insert(doc,True)
                store.put('template_editor_initialized',True)
        # Backfill settings for existing installations without changing identities or designs.
        for row in store.db.execute('SELECT * FROM label_templates').fetchall():
            doc=validate_document(json.loads(row['document']))
            self._sync_aggregation(row['id'],doc,row['deleted'],row['updated_at'])
        store.db.commit()

    def _sync_aggregation(self,identifier,doc,deleted=0,updated=None):
        product=doc.get('child_product') or {}
        self.store.db.execute("""INSERT INTO template_agregasi VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(template_id) DO UPDATE SET level=excluded.level,name=excluded.name,
            child_level=excluded.child_level,child_template_id=excluded.child_template_id,
            child_product_id=excluded.child_product_id,child_product_name=excluded.child_product_name,
            child_product_source=excluded.child_product_source,target_min=excluded.target_min,
            target_max=excluded.target_max,print_mode=excluded.print_mode,document=excluded.document,
            active=excluded.active,deleted=excluded.deleted,updated_at=excluded.updated_at""",
            (identifier,doc['level'],doc['name'],doc['child_level'],doc.get('child_template_id'),
             str(product['id']) if product else None,product.get('name'),json.dumps(product.get('source')) if product else None,
             doc['aggregation_min'],doc['aggregation_max'],doc['print_mode'],json.dumps(doc,ensure_ascii=False),
             int(doc.get('active',True)),int(deleted),updated or datetime.now().isoformat(timespec='seconds')))

    def _record(self,identifier,level,action,detail):
        self.store.db.execute('INSERT INTO template_activity(template_id,level,action,detail,ts,operator) VALUES(?,?,?,?,?,?)',
                             (identifier,level,action,detail,datetime.now().isoformat(timespec='seconds'),self.store.get('user','OPERATOR')))
    def _insert(self,doc,default=False):
        identifier=uuid4().hex
        self.store.db.execute('INSERT INTO label_templates(id,level,name,document,is_default,updated_at) VALUES(?,?,?,?,?,?)',
                             (identifier,doc['level'],doc['name'],json.dumps(doc,ensure_ascii=False),int(default),datetime.now().isoformat(timespec='seconds')))
        self._sync_aggregation(identifier,validate_document(doc))
        self._record(identifier,doc['level'],'BUAT',doc['name'])
        return identifier
    def list(self,level=None):
        sql='SELECT * FROM label_templates WHERE deleted=0';args=[]
        if level:sql+=' AND level=?';args.append(level)
        return [dict(row) for row in self.store.db.execute(sql+' ORDER BY is_default DESC,updated_at DESC,id',args)]
    def get(self,identifier):
        row=self.store.db.execute('SELECT * FROM label_templates WHERE id=? AND deleted=0',(identifier,)).fetchone()
        if row is None:raise ValueError('Template tidak ditemukan.')
        result=dict(row);result['document']=validate_document(json.loads(result['document']))
        if result['published_document']:result['published_document']=json.loads(result['published_document'])
        return result
    def save(self,document,identifier=None):
        doc=validate_document(document)
        with self.store.db:
            if identifier:
                row=self.get(identifier)
                if row['level']!=doc['level']:raise ValueError('Level template tersimpan tidak boleh diubah.')
                self.store.db.execute('UPDATE label_templates SET name=?,document=?,updated_at=? WHERE id=?',
                                     (doc['name'],json.dumps(doc,ensure_ascii=False),datetime.now().isoformat(timespec='seconds'),identifier))
                self._sync_aggregation(identifier,doc)
                self._record(identifier,doc['level'],'SIMPAN',doc['name'])
            else:identifier=self._insert(doc)
        return identifier
    def duplicate(self,document):
        doc=deepcopy(document);doc['name']+=' - Salinan'
        for e in doc['elements']:e['id']=uuid4().hex
        return self.save(doc)
    def delete(self,identifier):
        row=self.get(identifier)
        with self.store.db:
            self.store.db.execute('UPDATE label_templates SET deleted=1,is_default=0 WHERE id=?',(identifier,))
            self.store.db.execute('UPDATE template_agregasi SET deleted=1 WHERE template_id=?',(identifier,))
            self._record(identifier,row['level'],'HAPUS',row['name'])
    def set_default(self,identifier):
        row=self.get(identifier)
        with self.store.db:
            self.store.db.execute('UPDATE label_templates SET is_default=0 WHERE level=?',(row['level'],))
            self.store.db.execute('UPDATE label_templates SET is_default=1 WHERE id=?',(identifier,))
            self._record(identifier,row['level'],'DEFAULT',row['name'])
    def publish(self,document,identifier=None):
        identifier=self.save(document,identifier)
        with self.store.db:
            self.store.db.execute('UPDATE label_templates SET published_document=document,revision=revision+1 WHERE id=?',(identifier,))
            self._record(identifier,document['level'],'PUBLISH',document['name'])
        return identifier
    def record(self,identifier,level,action,detail):
        with self.store.db:self._record(identifier,level,action,detail)
    def activities(self,limit=8):
        return [dict(r) for r in self.store.db.execute('SELECT * FROM template_activity ORDER BY id DESC LIMIT ?',(limit,))]
