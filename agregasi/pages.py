"""Full-screen internal pages for the AGREGASI desktop application.

The reference screens use a shared 1448x1086 canvas.  Each page is still a
normal QWidget: the host scales that canvas to the available viewport and the
controls remain real Qt widgets.  No page is opened as a modal dialog.
"""
from .sidebar_layout import fixed_sidebar, SIDEBAR
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QLinearGradient, QPolygonF
from .responsive_surface import SurfaceSvgRenderer as QSvgRenderer, SurfacePainter
from PySide6.QtWidgets import (
    QWidget, QPushButton, QLineEdit, QComboBox, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QLabel, QPlainTextEdit
)

from .ui_controls import ThemedComboBox as QComboBox
from .dashboard import BASE, WHITE, MUTED, GREEN, RED, YELLOW, BLUE, num
from .typography import draw_text, ui_font
from .display_preferences import CURRENT, icon_rect
from .navigation import Navigation, ITEMS, button_rect, CANVAS_TOP, CANVAS_BOTTOM, PANEL_BORDER, PANEL_SHADOW_ALPHA

from .store import STAGES, PREFIX
from .shell_layout import BODY, content_transform, paint_header


class PageBase(QWidget):
    """A responsive design canvas with the common header/sidebar/navigation."""

    action = Signal(str)
    changed = Signal()
    W, H = 1448, 1086

    def __init__(self, store, active, title, subtitle, kind='generic'):
        super().__init__()
        self.store = store
        self.setFont(ui_font())
        self.active = active
        self.title = title
        self.subtitle = subtitle
        self.kind = kind
        self.setFixedSize(self.W, self.H)
        self.icons = {p.stem: QSvgRenderer(str(p)) for p in (BASE / 'assets/svg').glob('*.svg')}
        self.widgets = []
        self._make_common_hotspots()
        self.navigation = Navigation(self, self)

    def hotspot(self, name, x, y, w, h, tip=''):
        button = QPushButton(self)
        button.setObjectName(name)
        button.setGeometry(x, y, w, h)
        # Tooltips from transparent overlays render as a black native bubble;
        # use a soft local hover state so each function feels part of the page.
        button.setToolTip('')
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet('QPushButton { background: transparent; border: 0; border-radius: 6px; } QPushButton:hover { background: rgba(80,176,255,18); border: 0; } QPushButton:focus { background: rgba(80,176,255,28); border: 1px solid rgba(168,229,255,130); } QPushButton:pressed { background: rgba(80,176,255,48); }')
        button.clicked.connect(lambda checked=False, n=name: self.action.emit(n))
        self.widgets.append(button)
        return button

    def field(self, x, y, w, h, value='', placeholder=''):
        edit = QLineEdit(self)
        edit.setGeometry(x, y, w, h)
        edit.setText(str(value) if value is not None else '')
        edit.setCursorPosition(0)
        edit.setToolTip(edit.text())
        edit.textChanged.connect(edit.setToolTip)
        edit.setPlaceholderText(placeholder)
        edit.setMaxLength(120)
        edit.setStyleSheet('QLineEdit { color:#e9f5ff; background:#04283f; border:1px solid #3f6780; border-radius:4px; padding:2px 8px; font-size:12px; } QLineEdit:focus { border:1px solid #65caff; }')
        self.widgets.append(edit)
        return edit

    def combo(self, x, y, w, h, values, current=None):
        box = QComboBox(self)
        box.setGeometry(x, y, w, h)
        box.addItems([str(v) for v in values])
        if current is not None:
            box.setCurrentText(str(current))
        box.setStyleSheet('QComboBox { color:#e9f5ff; background:#04283f; border:1px solid #3f6780; border-radius:4px; padding:2px 8px; font-size:12px; } QComboBox:focus { border:1px solid #65caff; } QComboBox QAbstractItemView { color:#e9f5ff; background:#062d46; selection-background-color:#0a6eaa; }')
        box.setToolTip(box.currentText())
        box.currentTextChanged.connect(box.setToolTip)
        self.widgets.append(box)
        return box

    def checkbox(self, x, y, w, h, text):
        box = QCheckBox(text, self)
        box.setGeometry(x, y, w, h)
        box.setStyleSheet('QCheckBox { color:#e9f5ff; font-size:12px; } QCheckBox::indicator { width:17px; height:17px; } QCheckBox::indicator:checked { background:#3eaf51; border:1px solid #7bef66; border-radius:8px; }')
        self.widgets.append(box)
        return box

    def table(self, x, y, w, h, headers, widths=None):
        grid = QTableWidget(self)
        grid.setGeometry(x, y, w, h)
        grid.setColumnCount(len(headers)); grid.setHorizontalHeaderLabels(headers)
        grid.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        grid.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        grid.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        grid.verticalHeader().setVisible(False)
        grid.setAlternatingRowColors(True)
        grid.setWordWrap(False)
        grid.setTextElideMode(Qt.TextElideMode.ElideRight)
        grid.verticalHeader().setDefaultSectionSize(32)
        grid.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        grid.setStyleSheet('QTableWidget { background:#03243a; alternate-background-color:#07334d; color:#e4f3ff; gridline-color:#285169; border:1px solid #355e76; font-size:11px; } QHeaderView::section { background:#0a3c58; color:#e7f5ff; border:0; border-bottom:1px solid #4a7891; padding:7px 4px; font-size:10px; } QTableWidget::item { padding:4px; } QTableWidget::item:selected { background:#0a6390; }')
        if widths:
            for i, width in enumerate(widths): grid.setColumnWidth(i, round(width * (w - 18) / sum(widths)))
            grid.horizontalHeader().setStretchLastSection(True)
        else: grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.widgets.append(grid)
        return grid

    def text(self, x, y, w, h, value, size=13, color=WHITE, bold=False,
             align=Qt.AlignmentFlag.AlignLeft, wrap=False):
        return draw_text(self.p, x, y, w, h, value, size, color, bold, align, wrap)

    def line(self, x, y, w, color='#29485f'):
        self.p.setPen(QPen(QColor(color), 1)); self.p.drawLine(QPointF(x, y), QPointF(x + w, y))

    def rect(self, x, y, w, h, c1='#062c4a', c2='#001b30', stroke='#385e78', radius=6, shadow=False):
        radius = radius * CURRENT['radius'] / 5 if radius else 0
        if self.store.get('configuration',{}).get('theme')=='HIGH CONTRAST' and c1=='#062c4a':
            c1=c2='#000814';stroke='#91b5cd'
        if shadow:
            self.p.setPen(Qt.PenStyle.NoPen); self.p.setBrush(QColor(20, 40, 60, PANEL_SHADOW_ALPHA)); self.p.drawRoundedRect(QRectF(x, y + 3, w, h), radius, radius)
        grad = QLinearGradient(x, y, x + w * .65, y + h); grad.setColorAt(0, QColor(c1)); grad.setColorAt(1, QColor(c2))
        self.p.setBrush(grad); self.p.setPen(QPen(QColor(stroke), 1)); self.p.drawRoundedRect(QRectF(x, y, w, h), radius, radius)

    def panel(self, x, y, w, h, title=None):
        self.rect(x, y, w, h, stroke=PANEL_BORDER, shadow=True)
        self.p.setBrush(Qt.BrushStyle.NoBrush); self.p.setPen(QPen(QColor('#476981'), .7)); self.p.drawRoundedRect(QRectF(x + 2, y + 2, w - 4, h - 4), 5, 5)
        if title:
            self.text(x + 12, y + 6, w - 24, 25, title, 14, bold=True); self.line(x + 10, y + 34, w - 20)

    def icon(self, name, x, y, size=34):
        if name in self.icons: self.icons[name].render(self.p, icon_rect(x,y,size))

    def dot(self, x, y, color=GREEN, kind='check', size=14):
        self.p.setPen(Qt.PenStyle.NoPen); self.p.setBrush(QColor(color))
        if kind == 'warning': self.p.drawPolygon(QPolygonF([QPointF(x + size / 2, y), QPointF(x + size, y + size), QPointF(x, y + size)]))
        else: self.p.drawEllipse(QRectF(x,y,size,size))
        self.text(x, y - 1, size, size + 1, '!' if kind == 'warning' else ('×' if kind == 'cross' else '✓'), size - 2, '#003347', True, Qt.AlignmentFlag.AlignCenter)

    def header(self):
        paint_header(self, self.subtitle)

    def _make_common_hotspots(self):
        for index, (name, _, label) in enumerate(ITEMS):
            r = button_rect(index)
            self.hotspot('nav_' + name, r.x(), r.y(), r.width(), r.height(), label)
        for name, x in [('database', 1118), ('printer', 1180), ('camera', 1242), ('scanner', 1304), ('logout', 1366)]:
            self.hotspot('shortcut_' + name, x, 925, 54, 51, 'Koneksi ' + name)

    def nav(self):
        self.navigation.paint(self.p)

    def sidebar(self):
        from .shared_sidebar import paint_sidebar
        paint_sidebar(self)

    def paintEvent(self, event):
        self.p = SurfacePainter(self)
        self.p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.header()
        self.p.save()
        self.p.setClipRect(BODY.adjusted(-1, -1, 1, 4))
        self.p.setWorldTransform(content_transform(self.active), True)
        self.paint_content()
        self.p.restore()
        self.sidebar(); self.nav(); self.p.end()

    def paint_content(self):
        pass


class OperationPage(PageBase):
    CONFIG = {
        'BOX': dict(sub='PEMINDAHAN & VERIFIKASI UNIT PRODUK', child='UNIT', capacity=50, code='BOX-250501-0001', cols=10, rows=5, filled=3, action='START SCAN'),
        'CARTON': dict(sub='PENYUSUNAN BOX KE CARTON', child='BOX', capacity=12, code='CTN-250501-0007', cols=4, rows=3, filled=5, action='START SCAN BOX'),
        'PALLET': dict(sub='PENYUSUNAN CARTON KE PALLET', child='CARTON', capacity=24, code='PLT-250501-0003', cols=6, rows=4, filled=8, action='START SCAN CARTON'),
    }
    def __init__(self, store, stage):
        cfg = dict(self.CONFIG[stage]); super().__init__(store, stage.lower(), f'Tahap / {stage}', cfg['sub'], stage); self.stage=stage; self.cfg=cfg; self.filled=cfg['filled']; self.message='Siap menerima scan.'
        self.scan_input=self.field(142,946,205,34,'', 'kode '+cfg['child'].lower()+' / enter')
        self.hotspot('stage_start_scan',140,894,145,44,'Mulai scan '+cfg['child'].lower())
        self.hotspot('stage_print_label',297,894,153,44,'Cetak label')
        self.hotspot('stage_reset',461,894,153,44,'Reset '+stage.lower())
        self.hotspot('stage_conveyor',623,894,155,44,'Jalankan conveyor simulasi')
        self.hotspot('stage_upload',915,894,165,48,'Upload instan')
        self.scan_input.returnPressed.connect(self.scan)
        self.action.connect(self.local_action)

    def configure_templates(self,runtime,print_callback):
        self.runtime=runtime;self.run=None;self.print_callback=print_callback
        self.template_selector=self.combo(101,795,229,27,['Pilih template agregasi…'])
        self.template_selector.currentIndexChanged.connect(self.start_template);self.template_selector.show()
        self.hotspot('stage_lock',29,824,301,31,'Selesaikan sesi jika target minimum tercapai').show()
        self.refresh()

    def refresh(self):
        if not hasattr(self,'runtime'):return
        selected=self.template_selector.currentData();self.template_selector.blockSignals(True)
        self.template_selector.clear();self.template_selector.addItem('Pilih template agregasi…',None)
        for row in self.runtime.repo.list(self.stage):
            self.template_selector.addItem(row['name'],row['id'])
        self.template_selector.setCurrentIndex(max(0,self.template_selector.findData(selected)));self.template_selector.blockSignals(False)
        if self.run:self.update_run(self.runtime.get(self.run['id']))

    def start_template(self):
        identifier=self.template_selector.currentData()
        if identifier is None:
            self.run=None;self.cfg=dict(self.CONFIG[self.stage]);self.subtitle=self.cfg['sub'];self.filled=self.cfg['filled'];self.message='Mode tampilan contoh. Pilih template untuk agregasi tersimpan.';self.update();return
        try:
            self.update_run(self.runtime.start(identifier));self.message='Sesi memakai template tersimpan. Scan kode child sesuai produk yang dipilih.'
        except Exception as exc:
            self.run=None;self.message=str(exc)
        self.update()

    def update_run(self,run):
        self.run=run;doc=run['document'];self.filled=run['quantity']
        self.child_codes=[row[0] for row in self.store.db.execute('SELECT code FROM aggregation_children WHERE run_id=? ORDER BY rowid LIMIT 60',(run['id'],))]
        self.subtitle='AGREGASI '+doc['child_level']+' KE '+self.stage
        self.recent_children=[dict(ts=row['ts'] or '—',code=row['code'],status='VALID') for row in self.store.db.execute('SELECT code,ts FROM aggregation_children WHERE run_id=? ORDER BY rowid DESC LIMIT 5',(run['id'],))]
        capacity=doc['aggregation_max'];visible=min(60,capacity)
        columns=min(10,max(1,int(visible**.5)+1));rows=(visible+columns-1)//columns
        self.cfg.update(child=doc['child_level'],capacity=capacity,cols=columns,rows=rows,code=run['parent_code'] or 'BELUM SELESAI',action='SCAN '+doc['child_level'])
        self.scan_input.setPlaceholderText('kode '+doc['child_level'].lower()+' / Enter')
        self.update()

    def print_run(self,automatic=False):
        if not self.run:return
        try:
            if not self.runtime.claim_print(self.run['id'],automatic):
                self.message='Label sudah dikirim atau tugas cetak sedang diproses.';return
            document=self.runtime.print_document(self.run['id'])
            sent=self.print_callback(document,self.run['template_id'],automatic)
            if not sent:
                self.runtime.print_result(self.run['id'],'Cetak dibatalkan.');self.message='Cetak dibatalkan; gunakan Print Label untuk mencoba lagi.'
            else:
                self.runtime.print_result(self.run['id']);self.message='Label agregasi berhasil diproses.'
        except Exception as exc:
            if self.run and self.runtime.get(self.run['id'])['print_state']=='SENDING':self.runtime.print_result(self.run['id'],str(exc))
            self.message=str(exc)
        finally:self.update_run(self.runtime.get(self.run['id']));self.update()

    def local_action(self, name):
        if name == 'stage_start_scan':
            if not self.scan_input.text().strip() and hasattr(self,'settings_runtime'):
                try:self.message=self.settings_runtime.listen_scanner(self.stage);self.scan_input.setFocus()
                except ValueError as exc:self.message=str(exc)
                self.update()
            else:self.scan()
        elif name=='stage_lock' and getattr(self,'run',None):
            try:self.update_run(self.runtime.finish_partial(self.run['id']));self.message='Sesi dikunci. Tekan Print Label untuk mencetak.'
            except Exception as exc:self.message=str(exc)
            self.update()
        elif name=='stage_print_label' and getattr(self,'run',None):self.print_run()
        elif name=='stage_reset' and getattr(self,'run',None):
            try:self.runtime.reset_empty(self.run['id']);self.update_run(self.runtime.start(self.run['template_id']));self.message='Sesi agregasi berikutnya siap.'
            except Exception as exc:self.message=str(exc)
            self.update()
        elif name == 'stage_print_label': self.message='Label '+self.stage.lower()+' dikirim ke printer simulasi.'; self.update()
        elif name == 'stage_reset': self.filled=0; self.message='Tahap di-reset pada tampilan sesi ini; riwayat tidak dihapus.'; self.update()
        elif name == 'stage_conveyor':
            if hasattr(self,'settings_runtime'):self.settings_runtime.conveyor();self.message='Lihat hasil perintah controller pada Pengaturan.'
            else:self.message='Controller conveyor belum dikonfigurasi.'
            self.update()
        elif name == 'stage_upload':
            if hasattr(self,'settings_runtime'):self.settings_runtime.upload(level=self.stage);self.message='Pengiriman diproses melalui koneksi di Pengaturan.'
            else:self.message='Koneksi API belum dikonfigurasi.'
            self.update()

    def scan(self):
        if not self.scan_input.text().strip():
            self.message='Pindai barcode atau masukkan kode terlebih dahulu.';self.update();return
        if not self.store.get('configuration',{}).get('line_active',True):
            self.message='Line nonaktif. Aktifkan melalui Pengaturan untuk menerima scan.';self.update();return
        if hasattr(self,'runtime') and self.template_selector.currentData():
            if not self.run:self.message='Template belum siap. Periksa relasi child dan pilih kembali template.';self.update();return
            try:
                self.update_run(self.runtime.scan(self.run['id'],self.scan_input.text()))
                self.scan_input.clear();self.message=f"VALID • {self.run['quantity']} / {self.run['document']['aggregation_max']}"
                if self.run['state']=='COMPLETE':
                    if self.run['print_state']=='PENDING':self.print_run(automatic=True)
                    else:self.message='Target maksimum tercapai. Tekan Print Label (manual).';self.update()
                self.changed.emit()
            except Exception as exc:self.message=str(exc);self.update()
            return
        code=self.scan_input.text().strip().upper() or self.store.next_code(self.stage)
        try:
            _, status=self.store.scan(self.stage, code)
            if status == 'VALID': self.filled=min(self.cfg['capacity'], self.filled+1)
            self.message=f'{status} • {code}'; self.scan_input.clear(); self.changed.emit(); self.update()
        except Exception as exc: self.message=str(exc); self.update()

    def paint_content(self):
        steps = [('DATA TARGET', 'Memuat data '+self.cfg['child'].lower()+' target untuk satu '+self.stage.lower()+'.', 'revision'),
                 ('SCAN '+self.cfg['child'], 'Memindai kode yang akan masuk ke '+self.stage.lower()+'.', 'barcode'),
                 ('PRINTER LABEL '+self.stage, 'Mencetak label '+self.stage.lower()+' / kode agregasi.', 'printer'),
                 ('VERIFIKASI KAMERA', 'Verifikasi susunan '+self.cfg['child'].lower()+' dan label '+self.stage.lower()+'.', 'camera')]
        for i, (label, desc, ico) in enumerate(steps):
            x = 15 + i * 274
            self.rect(x, 84, 258, 97, stroke='#2b5c79', shadow=True)
            self.rect(x+12, 96, 24, 24, '#eff7ff', '#eff7ff', '#eff7ff', 3)
            self.text(x+12, 95, 24, 26, str(i+1), 14, '#0b3454', True, Qt.AlignmentFlag.AlignCenter)
            self.text(x+45, 96, 203, 24, label, 12, bold=True)
            self.text(x+12, 125, 198, 46, desc, 11, MUTED, wrap=True)
            self.icon(ico, x+217, 134, 28)
            if i < 3:
                self.text(x+260, 114, 14, 30, '›', 22, '#083b60', align=Qt.AlignmentFlag.AlignCenter)
        self.panel(15,193,1080,483)
        self.text(27,199,405,28,'AGREGASI '+self.cfg['child']+' KE '+self.stage,14,bold=True)
        self.text(440,199,470,28,'KODE '+self.stage+' SAAT INI: '+self.cfg['code'],11,MUTED)
        self.text(926,199,155,28,'KAPASITAS: '+str(self.cfg['capacity'])+' '+self.cfg['child'],10,MUTED,align=Qt.AlignmentFlag.AlignRight)
        self.line(25,227,1060)
        inner_x, inner_y, gap = 32, 233, 7; cell_w=(1040-(self.cfg['cols']-1)*gap)/self.cfg['cols']; cell_h=(405-(self.cfg['rows']-1)*gap)/self.cfg['rows']
        for n in range(min(60,self.cfg['capacity'])):
            r,c=divmod(n,self.cfg['cols']); x=inner_x+c*(cell_w+gap); y=inner_y+r*(cell_h+gap); filled=n<self.filled; scanning=(n==self.filled and self.filled<self.cfg['capacity'])
            self.rect(x,y,cell_w,cell_h,'#087640' if filled else '#0d3049','#06442e' if filled else '#29435b','#43cd55' if filled else '#6b86a0',4)
            self.text(x+10,y+7,40,22,f'{n+1:02}',13,'#f1f7ff',True)
            if filled:
                self.icon('barcode',x+cell_w/2-20,y+cell_h/2-18,40); self.dot(x+cell_w-26,y+8,GREEN,size=18); self.text(x+3,y+cell_h-27,cell_w-6,20,(self.child_codes[n] if getattr(self,'run',None) and n<len(self.child_codes) else self.cfg['child']+'250501'+f'{n+1:04}'),8,align=Qt.AlignmentFlag.AlignCenter)
            elif scanning:
                self.rect(x+2,y+2,cell_w-4,cell_h-4,'#054e87','#022d52','#20a4ed',4); self.text(x,y+cell_h/2-13,cell_w,24,'SCANNING...',12,bold=True,align=Qt.AlignmentFlag.AlignCenter)
            else:self.text(x,y+cell_h/2-13,cell_w,24,'—',17,MUTED,align=Qt.AlignmentFlag.AlignCenter)
        self.text(27,651,112,20,'PROGRES AGREGASI',10,MUTED); self.rect(154,653,608,12,'#0e304a','#0a253b','#2b5873',6); self.rect(157,655,604*min(1,self.filled/self.cfg['capacity']),8,BLUE,'#0574bd',BLUE,4); self.text(777,648,198,23,f'{self.filled} / {self.cfg["capacity"]} {self.cfg["child"]} ({self.filled/self.cfg["capacity"]*100:.1f}%)'.replace('.',','),10); self.text(985,648,95,23,'CACHE: '+str(self.filled),10,align=Qt.AlignmentFlag.AlignRight)
        self.panel(15,687,336,195,'PILIH PRODUK / BATCH / LIST DATA');
        for i,(lab,val) in enumerate([('PRODUK',(self.run['document'].get('child_product') or {}).get('name',self.run['document']['data'].get('product_name','')) if getattr(self,'run',None) else self.store.get('product')),('BATCH',self.store.get('batch')),('TEMPLATE','')]):
            yy=727+i*34; self.text(29,yy,70,22,lab,10,MUTED); self.rect(101,yy,229,27,'#052a43','#031b2e','#355d74',3); self.text(108,yy+2,210,22,val,10,align=Qt.AlignmentFlag.AlignLeft)
        self.rect(29,824,301,31,'#087ac1','#004b80','#158ed4',4); self.text(29,826,301,26,'KUNCI '+self.stage,12,bold=True,align=Qt.AlignmentFlag.AlignCenter); self.text(29,858,301,19,f'● {self.filled}/{self.cfg["capacity"]} {self.cfg["child"]}   •   CACHE {self.filled}   •   READY',10,MUTED,align=Qt.AlignmentFlag.AlignCenter)
        self.panel(357,687,364,195,'DATA '+self.cfg['child']+' TER-SCAN • 5 TERAKHIR'); self.text(375,727,70,18,'WAKTU',9,MUTED); self.text(462,727,171,18,'KODE '+self.cfg['child'],9,MUTED); self.text(654,727,56,18,'STATUS',9,MUTED)
        for i,e in enumerate(self.recent_children if getattr(self,'run',None) else self.store.events(self.stage,limit=5)):
            yy=746+i*24; self.text(375,yy,78,20,e['ts'][11:19],10); self.text(462,yy,171,20,e['code'],10); self.dot(638,yy+4,GREEN if e['status']=='VALID' else RED,'check' if e['status']=='VALID' else 'cross',13); self.text(654,yy,56,20,e['status'],9,GREEN if e['status']=='VALID' else RED)
        self.panel(727,687,368,195,'HASIL AGREGASI '+self.stage); self.text(743,727,80,18,'WAKTU',9,MUTED); self.text(844,727,150,18,'KODE '+self.stage,9,MUTED); self.text(1031,727,50,18,'STATUS',9,MUTED)
        for i,e in enumerate([dict(row) for row in self.store.db.execute("SELECT * FROM events WHERE stage=? AND source='template' ORDER BY id DESC LIMIT 5",(self.stage,))] if getattr(self,'run',None) else self.store.events(self.stage,limit=5)):
            yy=746+i*24; self.text(743,yy,80,20,e['ts'][11:19],10); self.text(844,yy,180,20,e['code'],10); self.rect(1025,yy+2,54,18,'#15683c','#0c3b28','#37a950',4); self.text(1025,yy+2,54,18,'SELESAI',8,WHITE,True,Qt.AlignmentFlag.AlignCenter)
        self.panel(15,893,1080,97); self.text(30,907,100,22,'KONTROL LINE',11); self.rect(140,895,145,44,'#08743d','#003f2b','#39a853',4); self.text(140,903,145,28,self.cfg['action'],11,WHITE,True,Qt.AlignmentFlag.AlignCenter); self.rect(297,895,153,44,'#0678bd','#003c69','#2aa2ed',4); self.text(297,903,153,28,'PRINT LABEL',11,WHITE,True,Qt.AlignmentFlag.AlignCenter); self.rect(461,895,153,44,'#9e7104','#604200','#d8a71a',4); self.text(461,903,153,28,'RESET '+self.stage,11,WHITE,True,Qt.AlignmentFlag.AlignCenter); self.rect(623,895,155,44,'#0870b7','#00395f','#2494da',4); self.text(623,903,155,28,'START CONVEYOR',11,WHITE,True,Qt.AlignmentFlag.AlignCenter); self.text(790,906,115,22,'MODE: AGGREGATION',10,GREEN,True); self.rect(915,895,165,44,'#65449c','#322262','#8868c7',4); self.text(915,903,165,28,'UPLOAD INSTAN',11,WHITE,True,Qt.AlignmentFlag.AlignCenter); self.text(31,948,90,22,'MFD',11); self.text(362,946,716,34,self.message,10,GREEN if self.message.startswith(('VALID','Siap')) else YELLOW)


def __getattr__(name):
    if name == 'RevisionPage':
        from .revision_page import RevisionPage
        return RevisionPage
    if name == 'SendPage':
        from .upload_page import SendPage
        return SendPage
    if name == 'SettingsPage':
        from .settings_page import SettingsPage
        return SettingsPage
    raise AttributeError(name)
