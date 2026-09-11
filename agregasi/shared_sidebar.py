"""One sidebar composition on every page; only the data model changes."""
from datetime import datetime
import json
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QPushButton
from .sidebar_layout import SIDEBAR
from .settings_model import VERSION
from .typography import draw_text

WHITE, MUTED, GREEN, RED, YELLOW, BLUE = '#f0f5ff','#c4d3e5','#73e342','#ff403e','#ffc621','#12afff'
# These bounds deliberately match the BOX reference. No page-specific transforms.
SECTIONS = ((211,146),(365,118),(491,157),(656,117),(781,104),(893,86))
SHORTCUTS = ('database','printer','camera','scanner','logout')

def data_for(page):
    key=getattr(page,'sidebar_key',page.active); store=page.store; today=datetime.now().date().isoformat()
    runtime=getattr(page,'settings_runtime',None)
    from .settings_model import merge_defaults
    cfg=merge_defaults(store.get('configuration',{}))
    result=dict(title='TOTAL AGREGASI HARI INI',total=0,unit='unit',rate=0,rate_label='VALID',
                summary_title='RINGKASAN UMUM',summary=[],detail_title='PRODUK AKTIF',detail=[],activity=[])
    def row(label,value,color=WHITE,icon=None):return (label,str(value),color,icon)
    if key in ('box','carton','pallet') and getattr(page,'repo',None):
        level=key.upper();child=page.cfg['child'];m=page.repo.metrics() if key=='box' else page.repo.metrics(child)
        total=m['total'];count=m[{'box':'boxes','carton':'cartons','pallet':'pallets'}[key]];unit=child.lower()
        result.update(title='TOTAL '+level+' HARI INI',total=count,unit=key,rate=m['valid']/total*100 if total else 0,
                      rate_label='UNIT VALID' if key=='box' else 'SCAN VALID',summary_title='RINGKASAN TAHAP '+str(('box','carton','pallet').index(key)+1),detail_title=level+' TERSIAPKAN')
        result['summary']=[row('TOTAL '+child+' TERPROSES',f'{total} {unit}',WHITE,'barcode'),
            row('VALID',f"{m['valid']} {unit}",GREEN,'check_circle'),row('REJECT',f"{m['reject']} {unit}",RED,'reject'),
            row('DUPLIKAT',f"{m['duplicate']} {unit}",YELLOW,'reject'),row(level+' TERBENTUK',f'{count} {key}',BLUE,key)]
        capacity=max(1,page.cfg['capacity'])
        result['detail']=[row('KODE '+level+' SAAT INI',page.run['parent_code'] if page.run else '—',GREEN),
            row('BATCH',page.run['batch'] if page.run else page.batch.currentText()),row('KAPASITAS '+level,f'{capacity} {unit}'),
            row('ISI SAAT INI',f'{page.filled} {unit} ({page.filled/capacity*100:.1f}%)')]
        result['activity']=[(r['ts'][11:19],'SCAN',r['code'],r['status']) for r in page.repo.recent()[:5]]
    elif key=='template' and hasattr(page,'repo'):
        m=page.sidebar_metrics();result.update(title='TOTAL TEMPLATE AKTIF',total=m['active'],unit='template',rate=100*m['active']/max(1,m['total']),rate_label='AKTIF',summary_title='RINGKASAN TEMPLATE',detail_title='PENGGUNAAN TEMPLATE')
        result['summary']=[row(level+' TEMPLATE',f"{m['counts'][level]} template",WHITE,level.lower()) for level in ('BOX','CARTON','PALLET')]+[row('NONAKTIF',m['total']-m['active'],YELLOW),row('TEMPLATE DEFAULT',m['defaults'],GREEN)]
        result['detail']=[row(level,f"{m['usage'][level]} kali") for level in ('BOX','CARTON','PALLET')]+[row('TERAKHIR DIUBAH',m['edited'].replace('T',' ')[:16] or '—')]
        result['activity']=[(r['ts'][11:19],r['action'],r['detail'] or r['level'],r['operator']) for r in page.repo.activities(5)]
    elif key=='revision':
        logs=getattr(page,'log_rows',[]);recent=[r for r in logs if r['ts'][:10]==today];states=[json.loads(r['after_json'])['status'] for r in recent];valid=states.count('VALID')
        result.update(title='TOTAL REVISION HARI INI',total=len(recent),unit='aksi',rate=100*valid/max(1,len(recent)),summary_title='RINGKASAN REVISION',detail_title='DATA TERPILIH')
        result['summary']=[row('TOTAL REVISION',len(recent)),row('VALID',valid,GREEN),row('REJECT',states.count('REJECT'),RED),row('DUPLIKAT',states.count('DUPLIKAT'),YELLOW),row('DIPULIHKAN',sum(r['action']=='PULIHKAN VALID' for r in recent),BLUE)]
        item=getattr(page,'item',None)
        result['detail']=[row(label,item[field] or '—') for label,field in [('TIPE','level'),('KODE','code'),('BATCH','batch'),('STATUS','status')]] if item else [row('PILIH DATA','Belum dipilih')]
        result['activity']=[(r['ts'][11:19],r['action'],r['code'],json.loads(r['after_json'])['status']) for r in logs[:5]]
    elif key=='send':
        c=getattr(page,'counts',{});history=getattr(page,'all_history',[]);recent=[r for r in history if r['sent_at'][:10]==today];total=len({r['id'] for r in recent});sent=len({r['id'] for r in recent if r['delivery_status']=='SUCCESS'})
        result.update(title='TOTAL DATA KIRIM HARI INI',total=sent,unit='data',rate=100*sent/max(1,total),rate_label='TERKIRIM',summary_title='RINGKASAN KIRIM DATA',detail_title='SERVER / DATABASE')
        result['summary']=[row('TOTAL QUEUE',sum(c.get(k,0) for k in ('PENDING','SENDING','FAILED'))),row('PENDING',c.get('PENDING',0),YELLOW),row('SEDANG DIKIRIM',c.get('SENDING',0),BLUE),row('BERHASIL',c.get('SUCCESS',0),GREEN),row('GAGAL',c.get('FAILED',0),RED)]
        status=runtime.status if runtime else {};metrics=runtime.upload_metrics if runtime else {}
        result['detail']=[row('DATABASE',status.get('database',{}).get('status','BELUM DITES')),row('API SERVER',status.get('api',{}).get('status','BELUM DITES')),row('RESPONSE TIME',str(metrics.get('duration_ms','—'))+' ms'),row('AUTO UPLOAD','AKTIF' if cfg.get('auto_upload') else 'NONAKTIF')]
        result['activity']=[(r['sent_at'][11:19],'UPLOAD',r['code'],r['delivery_status']) for r in history[:5]]
    elif key=='settings':
        states=runtime.status if runtime else {};online=sum(v.get('status') in ('ONLINE','DRIVER SIAP','TERDETEKSI') for v in states.values())
        result.update(title='PERANGKAT SIAP',total=online,unit='device',rate=100*online/max(1,len(states)),rate_label='SIAP',summary_title='RINGKASAN PENGATURAN',detail_title='TAMPILAN APLIKASI')
        result['summary']=[row('LINE PRODUKSI',store.get('line')),row('MODE',store.get('mode')),row('SHIFT',store.get('shift')),row('AUTO UPLOAD','AKTIF' if cfg.get('auto_upload') else 'NONAKTIF',GREEN),row('CACHE LIMIT',cfg.get('cache_limit',1000))]
        d=cfg.get('display',{});result['detail']=[row('RESOLUSI',d.get('resolution','OTOMATIS')),row('MODE',d.get('window_mode','MAKSIMAL')),row('FONT',d.get('font_family','OTOMATIS')),row('SKALA FONT / IKON',f"{d.get('font_scale',100)}% / {d.get('icon_scale',100)}%")]
        result['activity']=[(r['ts'][11:19],r['action'],r['detail'],r['operator']) for r in store.db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 5")]
    else:
        m=store.summary();result.update(total=m['units'],rate=100*m['valid']/max(1,m['units']))
        result['summary']=[row('TOTAL UNIT TERPROSES',f"{m['units']:,} unit".replace(',','.'),WHITE,'barcode'),row('VALID',f"{m['valid']:,} unit".replace(',','.'),GREEN,'check_circle'),row('REJECT',f"{m['reject']:,} unit".replace(',','.'),RED,'reject'),row('DUPLIKAT',f"{m['duplicate']:,} unit".replace(',','.'),YELLOW,'reject'),row('MODE',store.get('mode'),BLUE)]
        result['detail']=[row('PRODUK',store.get('product')),row('BATCH',store.get('batch')),row('LINE',store.get('line')),row('SHIFT',store.get('shift'))]
        result['activity']=[(r['ts'][11:19],'SCAN '+r['stage'],r['code'],r['status']) for r in store.events(limit=5)]
    states=runtime.status if runtime else {};level=key.upper() if key in ('box','carton','pallet') else 'BOX'
    result['system']=[row('DATABASE',states.get('database',{}).get('status','BELUM DITES')),
        row('PRINTER LABEL '+level,states.get('printer_'+level,{}).get('status','BELUM DITES')),
        row('KAMERA VERIFIKASI',states.get('camera',{}).get('status','BELUM DITES')),
        row('SCANNER',states.get('scanner_'+level,{}).get('status','BELUM DITES')),row('VERSI SISTEM','v'+VERSION)]
    return result

def paint_sidebar(page):
    page.panel(*SIDEBAR);d=data_for(page);p=page.p
    # Bypass page-local translation overrides so geometry and text treatment are identical.
    def text(x,y,w,h,value,size=10,color=WHITE,bold=False,align=Qt.AlignmentFlag.AlignLeft):
        return draw_text(p,x,y,w,h,value,size,color,bold,align)
    text(1118,81,249,25,'DASHBOARD AGREGASI',14,bold=True)
    text(1372,84,50,21,'SIM' if page.active=='dashboard' else 'LIVE',9,BLUE,align=Qt.AlignmentFlag.AlignRight)
    page.rect(1115,112,190,89);text(1126,119,171,21,d['title'],10,MUTED)
    text(1126,148,119,40,f"{d['total']:,}".replace(',','.'),28,bold=True)
    text(1248,160,48,23,d['unit'],10,align=Qt.AlignmentFlag.AlignRight)
    page.rect(1313,112,111,89);circle=QRectF(1333,124,68,68)
    p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(QColor('#206680'),8));p.drawEllipse(circle)
    p.setPen(QPen(QColor(GREEN),8));p.drawArc(circle,90*16,-round(max(0,min(100,d['rate']))*3.6*16))
    text(1331,140,73,20,f"{d['rate']:.1f}%",13,bold=True,align=Qt.AlignmentFlag.AlignCenter)
    text(1331,160,73,17,d['rate_label'],8,MUTED,align=Qt.AlignmentFlag.AlignCenter)
    titles=(d['summary_title'],d['detail_title'],'AKTIVITAS TERKINI','INFORMASI SISTEM','AKUN LOGIN','SHORTCUT KONEKSI')
    for (y,h),title in zip(SECTIONS,titles):
        page.rect(1115,y,309,h,stroke='#2a627f',radius=4);text(1127,y+4,283,25,title,13,bold=True);page.line(1127,y+31,283)
    def paint_row(y,row,h=20):
        label,value,color,ico=row
        if ico:page.icon(ico,1127,y+3,13)
        start=1147 if ico else 1127
        # Separate label/value cells. Long values elide inside their own cell.
        text(start,y,1286-start,h,label,9,MUTED)
        text(1291,y,122,h,value,10,color,align=Qt.AlignmentFlag.AlignRight)
    for i,row in enumerate(d['summary'][:5]):paint_row(246+i*21,row)
    for i,row in enumerate(d['detail'][:4]):paint_row(399+i*20,row,19)
    for x,w,label in [(1127,54,'WAKTU'),(1184,48,'JENIS'),(1237,109,'KETERANGAN'),(1350,63,'OLEH' if getattr(page,'sidebar_key',page.active) in ('template','settings') else 'STATUS')]:text(x,524,w,18,label,8,MUTED)
    for i,row in enumerate(d['activity'][:5]):
        for x,w,val in zip((1127,1184,1237,1350),(54,48,109,63),row):
            text(x,545+i*19,w,18,val,9,{'VALID':GREEN,'SUCCESS':GREEN,'REJECT':RED,'FAILED':RED,'DUPLIKAT':YELLOW}.get(val,WHITE))
    for i,row in enumerate(d['system']):
        label,value,_,ico=row;paint_row(689+i*16,(label,value,GREEN if value in ('ONLINE','DRIVER SIAP','TERDETEKSI') else MUTED,ico),16)
    page.icon('user',1129,820,45)
    for i,(label,value) in enumerate([('USERNAME',page.store.get('user')),('ROLE',page.store.get('role')),('SHIFT',page.store.get('shift')),('LOGIN',page.store.get('login'))]):
        text(1186,815+i*16,66,17,label,8,MUTED);text(1255,815+i*16,158,17,value,9,GREEN if i==0 else WHITE)
    for i,(ico,label,c1,c2) in enumerate([('database','DATABASE','#288d49','#06492e'),('printer','PRINTER','#1576b7','#063963'),('camera','KAMERA','#00a0b1','#00565d'),('barcode','SCANNER','#7453ae','#402264'),('power','LOGOUT','#ce3836','#841f26')]):
        x=1118+i*62;page.rect(x,925,54,51,c1,c2,c1,4);page.icon(ico,x+15,931,25);text(x,957,54,17,label,8,align=Qt.AlignmentFlag.AlignCenter)

def install_sidebar_controls(page):
    page.sidebar_key=page.active
    for i,key in enumerate(SHORTCUTS):
        b=page.findChild(QPushButton,'shortcut_'+key)
        if b:
            b.setGeometry(1118+i*62,925,54,51);b.setAccessibleName('Keluar' if key=='logout' else 'Pengaturan '+key);b.show();b.raise_()
    # Remove legacy frame-level targets and page-specific shortcut overlays.
    for b in page.findChildren(QPushButton):
        if b.objectName() in ('sidebar_stats','sidebar_summary','sidebar_product','sidebar_activity','sidebar_system','account') or b.objectName().startswith('template_connection_'):b.hide()
    if page.active=='template':
        page.history_button.hide()
        for i,b in enumerate(page.summary_buttons.values()):b.setGeometry(1127,246+i*21,286,20);b.setToolTip('')
