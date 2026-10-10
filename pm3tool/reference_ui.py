"""Native Qt controls arranged against the seven supplied 1536 × 1024 references.

Only logo, icons and unlabeled frame skins use cropped artwork. All text, forms,
buttons, tables, navigation and output are live widgets connected to the original
application. This module does not issue hardware commands.
"""
from pathlib import Path
from functools import lru_cache
from PySide6 import QtCore as C, QtGui as G, QtWidgets as W

ASSETS=Path(__file__).with_name('ui_assets')

@lru_cache(maxsize=80)
def pixmap(name):
    return G.QPixmap(str(ASSETS/(name+'.png')))

def icon(name):return G.QIcon(pixmap(name))

def nine(p,rect,name,n=10):
    pm=pixmap(name);sw,sh=pm.width(),pm.height();x,y,r,b=rect.x(),rect.y(),rect.right()+1,rect.bottom()+1
    xs=[x,x+n,r-n,r];ys=[y,y+n,b-n,b];us=[0,n,sw-n,sw];vs=[0,n,sh-n,sh]
    for i in range(3):
        for j in range(3):p.drawPixmap(C.QRect(xs[i],ys[j],xs[i+1]-xs[i],ys[j+1]-ys[j]),pm,C.QRect(us[i],vs[j],us[i+1]-us[i],vs[j+1]-vs[j]))

STYLE='''
QWidget { color:#e0eaff; font-family:"PM3 Reference Sans"; font-size:18px; background:transparent; }
QMainWindow,QDialog,QMessageBox { background:#00111c; }
QLabel { background:transparent; border:0; }
QLabel[role="title"] { font-size:26px;font-weight:700; }
QLabel[role="section"] { font-size:24px;font-weight:700; }
QLabel[role="subtitle"] { color:#bfdfff; font-size:17px; }
QLabel[role="muted"] { color:#9bc4e8;font-size:16px; }
QLabel[role="metric"] { color:#00e3ef;font-size:26px;font-weight:700; }
QLabel[role="badge"] { background:#06292b;border:1px solid #00b6b6;border-radius:8px;color:#00ffd0; }
QLineEdit,QComboBox,QDateEdit,QSpinBox { border:7px solid transparent;border-image:url(__ASSETS__/field.png) 7 7 7 7 stretch; padding:0px 8px;selection-background-color:#087c63; }
QLineEdit:focus,QComboBox:focus,QDateEdit:focus { background:#052a35; }
QLineEdit:disabled,QComboBox:disabled { color:#839ab7; }
QLineEdit:read-only { color:#bfdfff; }
QComboBox::drop-down,QDateEdit::drop-down { border:0;width:26px; }
QComboBox::down-arrow,QDateEdit::down-arrow { image:url(__ASSETS__/arrow.svg);width:14px;height:9px; }
QDateEdit::down-arrow { image:url(__ASSETS__/calendar.png);width:20px;height:20px; }
QComboBox QAbstractItemView { background:#052332;color:#e9f3ff;selection-background-color:#007759; }
QPushButton { border:10px solid transparent;border-image:url(__ASSETS__/button.png) 10 10 10 10 stretch;padding:0px 7px; }
QPushButton[primary="true"] { border-image:url(__ASSETS__/primary.png) 10 10 10 10 stretch;color:#fff; }
QPushButton[danger="true"] { border-image:url(__ASSETS__/danger.png) 10 10 10 10 stretch; }
QPushButton:hover { background:#093740; }
QPushButton:pressed { background:#008c69; }
QPushButton:disabled { border-image:url(__ASSETS__/disabled.png) 10 10 10 10 stretch;color:#9fb4d8; }
QPushButton[chrome="true"] { border:0;border-image:none;background:transparent;padding:0;font-size:24px; }
QPushButton[chrome="true"]:hover { background:#164456; }
QTabWidget::pane { border:0; background:transparent; }
QTabBar::tab { border:7px solid transparent;border-image:url(__ASSETS__/tab.png) 7 7 7 7 stretch;padding:3px 14px;margin-right:5px; }
QTabBar::tab:selected { border-image:url(__ASSETS__/tab_selected.png) 7 7 7 7 stretch; }
QTableWidget,QTableView { background:#00111d;alternate-background-color:#002031;gridline-color:#174c62;border:1px solid #00a8c7;border-radius:5px;selection-background-color:#00644e;selection-color:white; }
QTableWidget::item,QTableView::item { padding:2px 8px; }
QHeaderView::section { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #032d46,stop:1 #001e34);border:0;border-bottom:1px solid #128cab;border-right:1px solid #1c5b7b;padding:3px 6px; }
QTableCornerButton::section { background:#00293d;border:0; }
QPlainTextEdit,QTextEdit { background:#000e18;border:1px solid #076584;border-radius:5px;color:#dce5ff; padding:7px 10px;selection-background-color:#055d4a;font-family:"DejaVu Sans Mono";font-size:14px; }
QCheckBox { spacing:10px; }
QCheckBox::indicator { width:19px;height:19px;border:2px solid #b0dcff;border-radius:3px;background:#001624; }
QCheckBox::indicator:checked { image:url(__ASSETS__/check.svg);background:#00bf86;border-color:#00e7ae; }
QScrollArea { border:0;background:transparent; }
QScrollBar:vertical { background:#061828;width:9px;margin:2px; }
QScrollBar::handle:vertical { background:#5383ae;border-radius:4px;min-height:24px; }
QScrollBar:horizontal { background:#061828;height:9px;margin:2px; }
QScrollBar::handle:horizontal { background:#5383ae;border-radius:4px;min-width:24px; }
QScrollBar::add-line,QScrollBar::sub-line { width:0;height:0; }
QProgressBar { background:#0b2033;border:1px solid #2b789c;border-radius:8px;color:#d8eaff;text-align:center; }
QProgressBar::chunk { background:#00e59b;border-radius:7px; }
QToolTip { background:#093040;color:#e0f8ff;border:1px solid #00bfac;padding:8px; }
'''

class Canvas(W.QWidget):
    """Reference coordinates, resized with the window; widget events stay native."""
    def __init__(self,width,height,skin=False,parent=None):
        super().__init__(parent);self.base=C.QSize(width,height);self.items=[];self.skin=skin;self.rules=[];self.font_scale=1
        self.setMinimumSize(0,0)
    def put(self,widget,x,y,width,height,visible=True):
        widget.setParent(self);widget.setMinimumSize(0,0);widget.setMaximumSize(16777215,16777215)
        rect=C.QRect(x,y,width,height);self.items.append((widget,rect));widget.setGeometry(rect);widget.setVisible(visible);return widget
    def rule(self,x,y,width,color='#13809a'):
        self.rules.append((x,y,width,color));self.update()
    def resizeEvent(self,event):
        super().resizeEvent(event);sx=self.width()/self.base.width();sy=self.height()/self.base.height()
        for w,r in self.items:
            w.setGeometry(round(r.x()*sx),round(r.y()*sy),max(1,round(r.width()*sx)),max(1,round(r.height()*sy)))
            if isinstance(w,(W.QLabel,W.QAbstractButton,W.QLineEdit,W.QComboBox,W.QDateEdit,W.QSpinBox)):
                import re
                initial=w.property('referenceStyle')
                if initial is None:initial=w.styleSheet();w.setProperty('referenceStyle',initial)
                if 'font-size:' in initial:
                    updated=re.sub(r'font-size:(\d+)px',lambda m:'font-size:'+str(max(10,round(int(m[1])*min(1,sx))))+'px',initial)
                    if w.styleSheet()!=updated:w.setStyleSheet(updated)
                if isinstance(w,W.QAbstractButton):
                    base=w.property('referenceIconSize')
                    if base is None:base=w.iconSize();w.setProperty('referenceIconSize',base)
                    w.setIconSize(C.QSize(max(16,round(base.width()*min(1,sx))),max(16,round(base.height()*min(1,sx)))))
    def paintEvent(self,event):
        p=G.QPainter(self);p.setRenderHint(G.QPainter.SmoothPixmapTransform)
        if self.skin:nine(p,self.rect(),'panel')
        p.scale(self.width()/self.base.width(),self.height()/self.base.height())
        for x,y,width,color in self.rules:p.setPen(G.QColor(color));p.drawLine(x,y,x+width,y)

class Shell(Canvas):
    def resizeEvent(self,e):
        import re
        scale=min(1,self.width()/1536)
        if abs(scale-self.font_scale)>.01:
            self.font_scale=scale
            style=re.sub(r'font-size:(\d+)px',lambda m:'font-size:'+str(max(10,round(int(m[1])*scale)))+'px',STYLE)
            self.window().setStyleSheet(style.replace('__ASSETS__',ASSETS.as_posix()))
        super().resizeEvent(e)
    def paintEvent(self,event):
        p=G.QPainter(self);p.setRenderHint(G.QPainter.Antialiasing);p.scale(self.width()/1536,self.height()/1024)
        grad=G.QLinearGradient(0,0,1536,1024);grad.setColorAt(0,G.QColor('#000e18'));grad.setColorAt(.6,G.QColor('#001724'));grad.setColorAt(1,G.QColor('#00101a'))
        p.fillRect(C.QRect(0,0,1536,1024),grad);p.setPen(G.QPen(G.QColor('#00c6df'),1));p.setBrush(C.Qt.NoBrush)
        p.drawRoundedRect(C.QRectF(11.5,77.5,1512,933),8,8);p.drawRoundedRect(C.QRectF(12.5,87.5,1510,923),8,8)
        p.drawLine(378,13,378,65);p.drawLine(27,199,1509,199)

class Navigation(W.QTabBar):
    widths=[164,199,172,266,175,220,286]
    assets=['nav_reader','nav_dump','nav_clone','nav_edit','nav_firmware','nav_key','nav_ink']
    def __init__(self,parent=None):
        super().__init__(parent);self.setExpanding(False);self.setUsesScrollButtons(False);self.setDrawBase(False)
    def tabSizeHint(self,index):
        total=sum(self.widths);s=self.width()/total if self.width() else 1
        return C.QSize(round(self.widths[index]*s),48)
    def resizeEvent(self,e):super().resizeEvent(e);self.updateGeometry()
    def paintEvent(self,e):
        p=G.QPainter(self);p.setRenderHint(G.QPainter.SmoothPixmapTransform)
        for i in range(self.count()):
            r=self.tabRect(i).adjusted(0,0,0 if i==self.count()-1 else -8,0);nine(p,r,'tab_selected' if i==self.currentIndex() else 'tab',7)
            scale=min(1,self.width()/sum(self.widths));sz=round(32*scale);im=pixmap(self.assets[i]);ir=C.QRect(r.x()+round(17*scale),r.y()+(r.height()-sz)//2,sz,sz);p.drawPixmap(ir,im)
            font=G.QFont('PM3 Reference Sans');font.setPixelSize(max(11,round(18*scale)));font.setBold(i==self.currentIndex());p.setFont(font);p.setPen(G.QColor('#f0f0ff'))
            p.drawText(r.adjusted(round(60*scale),0,-7,0),C.Qt.AlignCenter,self.tabText(i))

def label(text,role=None):
    w=W.QLabel(text)
    if role:w.setProperty('role',role)
    return w

def text(canvas,txt,x,y,width,height,role=None):return canvas.put(label(txt,role),x,y,width,height)

def artwork(canvas,name,x,y,width,height=None):
    l=W.QLabel();l.setPixmap(pixmap(name));l.setScaledContents(True)
    return canvas.put(l,x,y,width,height or width)

def action(canvas,b,x,y,width,height,txt=None,kind=None,primary=False,danger=False):
    if txt is not None and txt!=b.text():b.setToolTip(b.toolTip() or b.text());b.setText(txt)
    b.setProperty('primary',primary);b.setProperty('danger',danger);b.setStyleSheet('')
    if kind:b.setIcon(icon(kind));b.setIconSize(C.QSize(33,33))
    else:b.setIcon(G.QIcon())
    return canvas.put(b,x,y,width,height)

def new_action(canvas,w,txt,callback,x,y,width,height,kind=None,primary=False):
    b=W.QPushButton(txt);b.clicked.connect(callback);return action(canvas,b,x,y,width,height,kind=kind,primary=primary)

def field(canvas,widget,x,y,width,height):
    widget.setStyleSheet('');return canvas.put(widget,x,y,width,height)

def panel(canvas,x,y,width,height,title=None,kind='file',subtitle=None,title_x=82):
    p=Canvas(width,height,True);canvas.put(p,x,y,width,height)
    if title:
        artwork(p,kind,16 if title_x<75 else 20,10,37 if title_x<75 else 46,36 if title_x<75 else 44);text(p,title,title_x,12,width-title_x-18,29,'section')
        if subtitle:text(p,subtitle,title_x,42,width-title_x-20,22,'subtitle')
    return p

def page(w,page,height):
    body=Canvas(1487,height);scroll=W.QScrollArea();scroll.setWidgetResizable(True);scroll.setHorizontalScrollBarPolicy(C.Qt.ScrollBarAlwaysOff);scroll.setVerticalScrollBarPolicy(C.Qt.ScrollBarAlwaysOff);scroll.setWidget(body)
    page.layout().setContentsMargins(0,0,0,0);page.layout().setSpacing(0);page.layout().addWidget(scroll);body.show();scroll.show();return body

def heading(body,title,sub,kind,title_x=89):
    artwork(body,kind,18,10,56,53);text(body,title,title_x,10,1000,32,'title');text(body,sub,title_x,42,1000,25,'subtitle')

def table_style(t,row_height=29,mono=False):
    t.setMinimumSize(0,0);t.setAlternatingRowColors(True);t.setEditTriggers(W.QAbstractItemView.NoEditTriggers);t.verticalHeader().hide();t.verticalHeader().setDefaultSectionSize(row_height);t.horizontalHeader().setFixedHeight(30)
    t.setSelectionBehavior(W.QAbstractItemView.SelectRows);t.setWordWrap(False)
    if mono:t.setStyleSheet('QTableWidget,QTableView{font-family:"DejaVu Sans Mono";font-size:13px;}QHeaderView::section{font-family:"PM3 Reference Sans";font-size:17px;}')
    t.horizontalHeader().setSectionResizeMode(W.QHeaderView.Interactive);t.horizontalHeader().setStretchLastSection(True)

def find(page,prefix):return next(b for b in page.findChildren(W.QPushButton) if b.text().startswith(prefix))

def empty_layout(lay,parking):
    while lay.count():
        item=lay.takeAt(0)
        if item.widget():item.widget().setParent(parking);item.widget().hide()
        elif item.layout():empty_layout(item.layout(),parking);item.layout().setParent(None)

def export_text(w,value,name):
    path,_=W.QFileDialog.getSaveFileName(w,'Simpan',name,'Teks (*.txt *.log);;Semua file (*)')
    if path:
        try:Path(path).write_text(value,encoding='utf-8')
        except OSError as exc:W.QMessageBox.warning(w,'Simpan gagal',str(exc))

def current_folder(w):
    i=w.tabs.currentIndex()
    if i==6:return w.ink_panel.folder.text()
    if i==3:return w.recycle_backup.text()
    return (w.recovery_panel.last_report or {}).get('session_dir',w.recovery_panel.output.text())

def file_open(w,path):
    if path and Path(path).is_dir():G.QDesktopServices.openUrl(C.QUrl.fromLocalFile(str(Path(path).resolve())))
    else:w.statusBar().showMessage('Folder hasil belum tersedia.')

class RecoveryRows(C.QAbstractTableModel):
    """Read-only presentation of the existing recovery model, with reference columns."""
    def __init__(self,source,reader=False):
        super().__init__(source);self.source=source;self.reader=reader
        for sig in (source.modelReset,source.rowsInserted,source.rowsRemoved,source.dataChanged):sig.connect(self.refresh)
    def refresh(self,*args):self.beginResetModel();self.endResetModel()
    def rowCount(self,parent=C.QModelIndex()):
        if parent.isValid():return 0
        if not self.reader:return self.source.rowCount()
        return len(self.sectors())
    def sectors(self):return sorted(set(str(self.source.data(self.source.index(r,0))) for r in range(self.source.rowCount())),key=lambda v:int(v) if v.isdigit() else 999)
    def columnCount(self,parent=C.QModelIndex()):return 4 if self.reader else 5
    def headerData(self,section,orientation,role=C.Qt.DisplayRole):
        if role==C.Qt.DisplayRole and orientation==C.Qt.Horizontal:return (['Sektor','Key A','Key B','Status'] if self.reader else ['#','Sektor','Tipe','Key Ditemukan','Status'])[section]
    def data(self,index,role=C.Qt.DisplayRole):
        if not index.isValid():return None
        r,c=index.row(),index.column()
        if role==C.Qt.TextAlignmentRole:return int(C.Qt.AlignCenter)
        if role==C.Qt.ForegroundRole and c==self.columnCount()-1:return G.QColor('#00ffb8')
        if role!=C.Qt.DisplayRole:return None
        if not self.reader:return str(r+1) if c==0 else '●  Ditemukan' if c==4 else self.source.data(self.source.index(r,c-1))
        sec=self.sectors()[r]
        if c==0:return sec.zfill(2)
        if c==3:
            kinds={str(self.source.data(self.source.index(n,1))).upper() for n in range(self.source.rowCount()) if str(self.source.data(self.source.index(n,0)))==sec}
            return 'Recovered' if {'A','B'}<=kinds else 'Sebagian'
        kind='A' if c==1 else 'B'
        for n in range(self.source.rowCount()):
            if str(self.source.data(self.source.index(n,0)))==sec and str(self.source.data(self.source.index(n,1))).upper()==kind:return self.source.data(self.source.index(n,2))
        return '—'

def reader(w,p,bs):
    body=page(w,p,420);actions=panel(body,0,0,1487,214,'Reader Actions','radio','Pembacaan kartu dan pemulihan key',91)
    titles=['Check Device','Scan (LF + HF)','Read HF','Read LF','Recover Keys dari Kartu','Dump'];icons=['monitor_button','search','wave','wave','key_button','file_button']
    for i,b in enumerate(w.reader_buttons[:6]):
        x,width=[(20,481),(512,463),(985,482)][i%3];action(actions,b,x,73+(i//3)*69,width,58,titles[i],icons[i]);b.setIconSize(C.QSize(48,44));b.setStyleSheet('font-size:18px;')
    rec=panel(body,0,225,1487,195,'Recover Key via Reader','key','Gunakan reader milik Anda untuk pemulihan key.',90);rec.rule(20,67,1447)
    text(rec,'UID untuk simulasi:',20,75,165,40);w.sim_uid_edit.setPlaceholderText('Kosong = default');field(rec,w.sim_uid_edit,190,75,1277,40)
    action(rec,w.reader_buttons[6],20,126,715,55,'Recovery via Reader','reader_key',True);w.reader_buttons[6].setIconSize(C.QSize(44,44));action(rec,w.reader_buttons[7],752,126,715,55,'Sniff / Trace','trace')

def viewer(w,p,bs):
    body=page(w,p,521);frame=panel(body,0,0,1487,521);heading(frame,'Dump Viewer','Lihat isi dump (.bin / .eml / .json) dalam Hex dan ASCII','file',86)
    text(frame,'Dump File:',32,68,90,40);field(frame,w.view_dump_edit,118,68,540,40);action(frame,bs['pick'],670,68,117,40,'Pilih File')
    text(frame,'Sektor:',822,68,66,40);field(frame,w.view_sectors_edit,884,68,124,40)
    sector_menu=W.QMenu(w.view_sectors_edit)
    for title,value in [('Semua sektor',''),('Sektor 0','0'),('Sektor 1 – 4','1-4')]:
        a=sector_menu.addAction(title);a.triggered.connect(lambda checked=False,v=value:w.view_sectors_edit.setText(v))
    arrow=w.view_sectors_edit.addAction(G.QIcon(str(ASSETS/'arrow.svg')),W.QLineEdit.TrailingPosition);arrow.triggered.connect(lambda:sector_menu.popup(w.view_sectors_edit.mapToGlobal(C.QPoint(0,w.view_sectors_edit.height()))))
    text(frame,'Format:',1032,68,62,40);field(frame,w.view_format,1090,68,181,40);action(frame,bs['show'],1286,68,182,40,'Tampilkan','eye',True)
    mem=panel(frame,15,120,1060,400);artwork(mem,'database',12,8,32,30);text(mem,'Isi Dump',60,8,110,29,'section');text(mem,'Read Only',162,10,80,25,'muted')
    w.neon_view_table=W.QTableWidget(0,4);w.neon_view_table.setHorizontalHeaderLabels(['Sektor','Blok','Hex Data (16 bytes)','ASCII']);table_style(w.neon_view_table,21,True);mem.put(w.neon_view_table,11,45,1035,345)
    w.view_out.setParent(w.neon_parking);w.view_out.hide()
    def toggle():
        show=w.view_out.isHidden();mem.put(w.view_out,11,45,1035,345,show);w.neon_view_table.setVisible(not show)
    new_action(mem,w,'Teks / Tabel',toggle,855,7,188,32,'file_button')
    info=panel(frame,1087,120,386,391,'Informasi File','file',title_x=59);stats=panel(info,15,48,357,157);w.neon_dump_values=[]
    for i,name in enumerate(['Format','Ukuran','Total Sektor','Total Blok','Ditampilkan Sektor']):
        text(stats,name,14,12+i*28,165,24);v=text(stats,':  —',164,12+i*28,178,24);w.neon_dump_values.append(v)
    info.rule(15,213,357);text(info,'Legenda',15,225,220,27);text(info,'■',20,257,35,30).setStyleSheet('color:#00e7ee;font-size:28px;');text(info,'Data block (blok 0 – 2)',59,257,300,30)
    text(info,'■',20,289,35,30).setStyleSheet('color:#ffbf42;font-size:28px;');text(info,'Sector trailer (blok 3 / trailer)',59,289,317,30).setStyleSheet('color:#ffcb63;')
    new_action(info,w,'Salin Data',lambda:W.QApplication.clipboard().setText(w.view_out.toPlainText()),15,329,174,51,'copy');new_action(info,w,'Ekspor',lambda:export_text(w,w.view_out.toPlainText(),'dump-view.txt'),200,329,174,51,'download')
    def update():
        from . import dumpview
        try:
            path=w.view_dump_edit.text();data=dumpview.load_dump(path);layout=dumpview.sector_layout(len(data));selected=dumpview.parse_sectors_arg(w.view_sectors_edit.text(),len(layout)-1)
            rows=[(s,b,blocks) for s,blocks in layout if selected is None or s in selected for b in blocks];t=w.neon_view_table;t.setRowCount(len(rows));t.clearSpans()
            last=None;start=0
            for r,(sec,b,blocks) in enumerate(rows):
                raw=data[b*16:(b+1)*16];values=[str(sec),'Trailer' if b==blocks[-1] else str(b-blocks[0]),dumpview.block_hex(raw),dumpview.block_ascii(raw)]
                for c,txt in enumerate(values):
                    item=W.QTableWidgetItem(txt)
                    if b==blocks[-1] and c:item.setForeground(G.QColor('#ffd158'))
                    if c<2:item.setTextAlignment(C.Qt.AlignCenter)
                    t.setItem(r,c,item)
                if last is not None and sec!=last:
                    if r-start>1:t.setSpan(start,0,r-start,1)
                    start=r
                last=sec
            if rows and len(rows)-start>1:t.setSpan(start,0,len(rows)-start,1)
            for c,width in [(0,83),(1,98),(2,569),(3,277)]:t.setColumnWidth(c,width)
            t.setColumnHidden(2,w.view_format.currentText()=='ASCII');t.setColumnHidden(3,w.view_format.currentText()=='Hex')
            vals=[Path(path).suffix[1:].upper(),f'{len(data)} bytes',str(len(layout)),str(len(data)//16),w.view_sectors_edit.text() or 'Semua']
        except (OSError,ValueError):vals=['—']*5;w.neon_view_table.setRowCount(0)
        for l,v in zip(w.neon_dump_values,vals):l.setText(':  '+v)
    bs['show'].clicked.connect(update)

def clone(w,p,bs):
    body=page(w,p,497);head=panel(body,0,0,1487,79);heading(head,'Clone','Pindahkan isi kartu ke chip baru','layers',90);action(head,w.clone_buttons[0],929,14,261,54,'Deteksi Kartu Magic','magic');action(head,w.clone_buttons[1],1202,14,267,54,'Wipe Gen1a','trash',danger=True)
    src=panel(body,0,90,822,179,'File Dump Sumber','file','.bin / .eml / .json dari Recover Keys',82)
    for i,(name,edit,pick) in enumerate([('Dump:',w.dump_edit,bs['dump']),('Key File:',w.key_edit,bs['key'])]):
        text(src,name,24,71+i*54,80,44);field(src,edit,106,71+i*54,535,44);action(src,pick,708,71+i*54,98,44,'Pilih…');new_action(src,w,'',pick.click,650,71+i*54,50,44,'folder')
    wr=panel(body,0,281,822,216,'Tulis ke Chip Baru','edit',title_x=80);action(wr,w.clone_buttons[2],18,50,787,55,'Clone ke MAGIC Gen1a','clone_copy',True);w.clone_buttons[2].setIconSize(C.QSize(44,44));w.clone_buttons[2].setStyleSheet('font-size:21px;')
    w.wb0_check.setToolTip(w.wb0_check.text());w.wb0_check.setText('Ikut tulis blok 0 / UID');wr.put(w.wb0_check,19,110,211,35);text(wr,'Kartu Gen2 / CUID yang mendukung',233,110,545,35,'subtitle')
    action(wr,w.clone_buttons[3],18,151,389,51,'Restore Pakai Key','key_button');action(wr,w.clone_buttons[4],417,151,388,51,'Verifikasi Isi Kartu','search')
    dest=panel(body,833,90,654,247,'Kartu Tujuan','target',title_x=74);card=panel(dest,20,60,197,173);artwork(card,'card',42,29,120,93)
    w.neon_target_badge=text(dest,'●  Belum diperiksa',251,62,185,37,'badge');text(dest,'Jenis',251,116,79,30);text(dest,'—',334,116,290,30);text(dest,'UID',251,150,79,30);text(dest,'—',334,150,290,30);text(dest,'Status',251,184,79,30);text(dest,'Menunggu deteksi',334,184,292,30)
    uid=panel(body,833,349,654,148,'Set UID · Gen1a','gear',title_x=74);field(uid,w.uid_edit,19,51,483,47);action(uid,w.clone_buttons[5],513,51,126,47,'Set UID')

def recycle(w,p,bs):
    body=page(w,p,563);files=panel(body,0,0,980,315,'File & Data Sumber','file','Siapkan data acuan dan tinjau perubahan sebelum penulisan.',82)
    w.recycle_reference.setPlaceholderText('Pilih dump acuan...');w.recycle_target.setPlaceholderText('Pilih backup target...');w.recycle_keys.setPlaceholderText('Pilih key file...')
    titles=['Data acuan:','Backup chip target:','Key chip target:','Profil khusus (opsional):','Folder hasil:'];edits=[w.recycle_reference,w.recycle_target,w.recycle_keys,w.recycle_profile,w.recycle_backup]
    for i,(title,edit) in enumerate(zip(titles,edits)):
        y=[69,114,162,209,259][i];text(files,title,22,y,171,38);field(files,edit,194,y,693,38);action(files,w.recycle_buttons[i],899,y,59,38,'','folder')
    settings=panel(body,991,0,496,315,'Pengaturan Penulisan','gear',title_x=70);text(settings,'Autentikasi:',21,53,175,40);field(settings,w.recycle_key_type,192,53,283,40);action(settings,w.recycle_buttons[5],21,105,454,52,'Buat Profil dari Daftar Blok','file_button');settings.rule(21,175,454)
    for i,(kind,txt) in enumerate([('shield','UID, key, dan access bits dipertahankan'),('file_button','Backup sebelum penulisan'),('search','Verifikasi setelah penulisan')]):
        artwork(settings,kind,28,192+i*38,32,32);text(settings,txt,81,192+i*38,393,32,'muted')
    prev=panel(body,0,326,1487,237,'Preview Perubahan','key',None,85);action(prev,w.recycle_buttons[6],1062,13,223,46,'Preview Perubahan','key_button',True);action(prev,w.recycle_write,1296,13,178,46,'Write Data','nav_firmware')
    prev.put(w.recycle_table,13,68,1461,161);table_style(w.recycle_table,29,True)
    for col,width in [(0,92),(1,136),(2,699),(3,523)]:w.recycle_table.setColumnWidth(col,width)
    w.neon_empty_group=[];w.neon_empty_group.append(artwork(prev,'empty',714,116,61,60));w.neon_empty_group.append(text(prev,'Belum ada preview',0,174,1487,27));w.neon_empty_group[-1].setAlignment(C.Qt.AlignCenter)
    w.neon_empty_group.append(text(prev,'Perubahan blok akan ditampilkan di sini.',0,202,1487,21,'muted'));w.neon_empty_group[-1].setAlignment(C.Qt.AlignCenter)
    prev.put(w.recycle_summary,85,40,950,24);w.recycle_summary.setWordWrap(False);w.recycle_summary.setProperty('role','muted')

def firmware(w,p,bs):
    body=page(w,p,550);frame=panel(body,0,0,1487,550);heading(frame,'Firmware','Kelola firmware Proxmark3 dengan tool Iceman / RRG.','chip',91)
    warning=text(frame,'',15,68,1458,41);warning.setStyleSheet('background:#1b2725;border:1px solid #ffc23a;border-radius:8px;');artwork(frame,'warning',35,72,31,30);text(frame,'Jangan cabut perangkat saat proses flash berjalan.',74,69,1280,39).setStyleSheet('color:#ffdc77;')
    acts=panel(frame,15,120,1458,120);artwork(acts,'trace',14,5,33,35);text(acts,'Aksi Firmware',59,7,600,30,'section')
    for i,(b,title,kind) in enumerate(zip(w.fw_buttons[:4],['Temukan Firmware','Flash ALL\nbootrom + fullimage','Flash Fullimage','Flash Bootrom'],['search','database','file_button','nav_firmware'])):action(acts,b,15+i*360,44,347,62,title,kind);b.setIconSize(C.QSize(48,44))
    custom=panel(frame,15,250,943,204,'Flash File .elf Kustom','file',title_x=65)
    for i,(name,edit,pick) in enumerate([('bootrom.elf:',w.boot_edit,bs['boot']),('fullimage.elf:',w.full_edit,bs['full'])]):
        y=45+i*49;text(custom,name,18,y,115,40);field(custom,edit,137,y,655,40);action(custom,pick,804,y,121,40,'Pilih','folder')
    action(custom,w.fw_buttons[4],17,149,908,44,'Flash File .elf Terpilih','nav_firmware')
    status=panel(frame,968,250,505,204,'Status Perangkat','chip',title_x=65);artwork(status,'device',47,51,91,90);w.neon_firmware_status=text(status,'●  Belum terdeteksi',18,143,147,36,'badge')
    w.neon_device_values=[]
    for i,name in enumerate(['Perangkat','Port','Firmware','Status']):
        text(status,name,183,43+i*39,111,29);v=text(status,'—',295,43+i*39,189,29);w.neon_device_values.append(v)
        if i<3:status.rule(183,75+i*39,303)
    build=panel(frame,15,465,1458,85);artwork(build,'layers',15,10,48,47);text(build,'Download & Build Firmware',81,8,940,26,'section');text(build,'Sumber: RfidResearchGroup / proxmark3',81,35,970,24,'subtitle');text(build,'Dependensi: Git, Make, ARM toolchain',81,58,970,19,'muted');action(build,w.fw_buttons[5],1203,16,239,52,'Download & Build','download',True)

def metric(body,x,width,value,title,kind):
    p=panel(body,x,84,width,70);artwork(p,kind,25,10,48,46);v=text(p,value,111,9,width-119,27,'section');text(p,title,111,39,width-119,24,'subtitle');return v

def recovery(w,p,bs):
    body=page(w,p,543);frame=panel(body,0,0,1487,543);heading(frame,'Recovery Keys','Pemulihan key dan ringkasan hasil sesi.','key',91);frame.rule(15,73,1457)
    action(frame,p.auto_button,574,17,380,43,'Recover Otomatis','play',True);action(frame,p.stop,966,17,241,43,'Hentikan','stop');p.advanced_toggle.setText('Metode lanjutan (opsional)');frame.put(p.advanced_toggle,1250,17,235,43)
    w.neon_metrics=[]
    for x,width,value,title,kind in [(15,358,'Siap','Belum ada proses recovery','check'),(386,351,'0','Key Sektor','database'),(750,350,'0','Key Unik','key'),(1114,358,'—','Belum Pulih','file')]:w.neon_metrics.append(metric(frame,x,width,value,title,kind))
    results=panel(frame,15,164,1009,379,'Hasil Recovery','file',title_x=65)
    w.neon_recovery_table=W.QTableView();w.neon_recovery_table.setModel(RecoveryRows(p.results.model()));table_style(w.neon_recovery_table,31);results.put(w.neon_recovery_table,10,50,988,289)
    for c,width in [(0,64),(1,174),(2,169),(3,318),(4,243)]:w.neon_recovery_table.setColumnWidth(c,width)
    p.results.setParent(w.neon_parking);p.results.hide();results.put(p.summary,17,341,972,30);p.summary.setWordWrap(False);p.summary.setProperty('role','muted')
    new_action(results,w,'',lambda:toggle_keys(w),950,10,44,31,'eye')
    session=panel(frame,1034,164,438,379,'Informasi Sesi','chip',title_x=60);artwork(session,'device',40,53,78,89)
    text(session,'Perangkat',158,46,105,28);text(session,'Proxmark3',260,46,171,28);w.neon_session_port=text(session,'—',260,78,164,28);text(session,'Port',158,78,103,28);text(session,'Durasi',158,110,103,28);w.neon_duration=text(session,'—',260,110,164,28);text(session,'Status',158,142,103,28);w.neon_session_status=text(session,'Siap',260,142,164,28)
    for y in (79,110,141):session.rule(158,y,263)
    session.rule(13,178,410,'#00cbd4');artwork(session,'file_button',16,184,28,30);text(session,'File Hasil',50,184,380,31,'section');w.neon_session_files=[]
    for i in range(3):
        f=text(session,'—',47,222+i*35,375,31);f.setStyleSheet('background:#032033;border:1px solid #097c9e;border-radius:4px;padding-left:43px;');artwork(session,'nav_dump',57,226+i*35,23,23);w.neon_session_files.append(f)
    new_action(session,w,'Buka Folder',lambda:file_open(w,(p.last_report or {}).get('session_dir')),15,329,407,40,'folder')
    # Existing advanced form remains in the same panel and retains all callbacks.
    frame.put(p.advanced,15,164,1009,379,False);p.advanced.setStyleSheet('QWidget#referenceAdvanced { background:#02202d;border:1px solid #00bfc9;border-radius:7px; }');p.advanced.setObjectName('referenceAdvanced')
    def advanced(on):
        p.advanced.setVisible(on);results.setVisible(not on)
        if on:p.advanced.raise_()
    p.advanced_toggle.toggled.connect(advanced);advanced(p.advanced_toggle.isChecked())

class KeyMask(C.QIdentityProxyModel):
    def __init__(self,parent=None):super().__init__(parent);self.mask=False
    def data(self,index,role=C.Qt.DisplayRole):
        val=super().data(index,role)
        if self.mask and role==C.Qt.DisplayRole and index.column()==3 and val:return '••••••••••••'
        return val

def toggle_keys(w):
    t=w.neon_recovery_table
    if isinstance(t.model(),KeyMask):t.model().mask=not t.model().mask;t.viewport().update()
    else:
        model=KeyMask(t);model.setSourceModel(t.model());model.mask=True;t.setModel(model)

def ink(w,p,bs):
    body=page(w,p,628);frame=panel(body,0,0,1487,628);heading(frame,'Write Chip Ink Baru','Siapkan data chip baru dengan kode produk dan tanggal kustom.','ink',98);frame.rule(14,68,1458,'#00d0d5')
    params=panel(frame,14,77,1459,327);artwork(params,'chip',12,7,30,29);text(params,'Data Acuan & Parameter',52,6,1340,30,'section')
    left=[('Acuan:',p.preset),('Mode:',p.mode),('Kode BK / Produk:',p.product),('Tanggal Chip:',p.date_entry),('ASCII Blok 5:',p.ascii_entry)];right=[('Dump Acuan:',p.file),('Folder Hasil:',p.folder),('UID Acuan:',p.source_uid),('Tanggal YYMMDD:',p.date_ascii),('Key Acuan:',p.key_entry)]
    for i,((a,x),(b,y)) in enumerate(zip(left,right)):
        yy=[40,78,116,154,195][i];text(params,a,25,yy,141,32);field(params,x,166,yy,551 if i<4 else 584,32);text(params,b,764,yy,141,32);field(params,y,907,yy,481 if i<2 else 537,32)
        if i<2:action(params,p.browse if i==0 else p.pick_folder_button,1395,yy,49,32,'','folder')
    actions=[(p.preview_button,11,384,'1. Baca Chip + Preview','play',True),(p.write_button,405,366,'2. Write Chip Baru','nav_edit',False),(p.stop_button,781,314,'Hentikan','stop',False),(p.export_button,1105,345,'Simpan Data + Key','save',False)]
    for b,x,width,title,kind,pri in actions:action(params,b,x,235,width,42,title,kind,pri)
    params.put(p.summary,11,283,1439,36);p.summary.setWordWrap(False);p.summary.setStyleSheet('border:1px solid #00a595;border-radius:5px;padding-left:12px;font-size:15px;color:#94e2d4;');p.summary.setToolTip(p.summary.text());p.field_note.setParent(w.neon_parking);p.field_note.hide()
    # Native subtabs and native original tables contain actual source/target data.
    frame.put(p.details,14,413,1459,207);p.details.setIconSize(C.QSize(21,21));p.details.setTabIcon(0,icon('nav_ink'));p.details.setTabIcon(1,icon('layers'));p.details.setTabIcon(2,icon('database'));p.details.tabBar().setExpanding(False)
    for t in (p.data_table,p.keys_table,p.preview_table):table_style(t,27,True)
    p.details.setStyleSheet('QTabBar::tab{height:19px;padding:3px 12px;font-size:15px;}QTabWidget::pane{border-top:1px solid #00bed2;top:7px;}')
    p.data_table.setColumnWidth(0,80);p.data_table.setColumnWidth(2,292);p.data_table.horizontalHeader().setSectionResizeMode(1,W.QHeaderView.Stretch);p.preview_table.horizontalHeader().setSectionResizeMode(1,W.QHeaderView.Stretch);p.preview_table.horizontalHeader().setSectionResizeMode(2,W.QHeaderView.Stretch)
    p.preview_table.setColumnWidth(0,80);p.preview_table.setColumnWidth(3,292)

def install(w):
    for f in [*ASSETS.glob('*.otf'),*ASSETS.glob('*.ttf')]:G.QFontDatabase.addApplicationFont(str(f))
    w.resize(1536,1024);w.setMinimumSize(1100,760);w.setWindowIcon(icon('nav_reader'));w.setWindowFlag(C.Qt.FramelessWindowHint,True)
    pages=[w.tabs.widget(i) for i in range(7)]
    specs=[{}, {'pick':find(pages[1],'Pilih'),'show':find(pages[1],'Tampilkan')},
           {'dump':find(pages[2],'Pilih'),'key':[b for b in pages[2].findChildren(W.QPushButton) if b.text().startswith('Pilih')][1]}, {},
           {'boot':find(pages[4],'Pilih'),'full':[b for b in pages[4].findChildren(W.QPushButton) if b.text().startswith('Pilih')][1]}, {}, {}]
    parking=W.QWidget(w);parking.hide();w.neon_parking=parking
    w.tabs.currentChanged.disconnect();empty_layout(w.centralWidget().layout(),parking)
    for p in pages:empty_layout(p.layout(),parking)
    w.setStyleSheet(STYLE.replace('__ASSETS__',ASSETS.as_posix()))
    shell=Shell(1536,1024);w.setCentralWidget(shell);w.neon_shell=shell
    # Header's artwork is the exact crop, while caption/status/window controls are live.
    header=Canvas(1536,77);shell.put(header,0,0,1536,77);artwork(header,'brand',24,3,331,74)
    text(header,'Kode BK / Tanggal Kustom + Recovery otomatis',410,18,690,41).setStyleSheet('font-size:22px;')
    w.neon_status=text(header,'●  Belum terdeteksi\n     Proxmark3',1126,13,191,53,'badge');w.neon_status.setStyleSheet('font-size:14px;padding-left:13px;background:#00121e;border:1px solid #00a8d5;border-radius:7px;color:#00e3e7;')
    for caption,x,callback in [('—',1356,w.showMinimized),('□',1415,lambda:w.showNormal() if w.isMaximized() else w.showMaximized()),('×',1476,w.close)]:
        b=W.QPushButton(caption);b.setProperty('chrome',True);b.clicked.connect(callback);header.put(b,x,16,40,40)
    def start_drag(e):
        if e.button()==C.Qt.LeftButton and w.windowHandle():w.windowHandle().startSystemMove()
    def maximize(e):
        if e.button()==C.Qt.LeftButton:w.showNormal() if w.isMaximized() else w.showMaximized()
    header.mousePressEvent=start_drag;header.mouseDoubleClickEvent=maximize
    def resize_window(e):
        if e.button()!=C.Qt.LeftButton or not w.windowHandle():return
        q=e.position();edge=C.Qt.Edge(0)
        if q.x()<8:edge|=C.Qt.LeftEdge
        elif q.x()>shell.width()-8:edge|=C.Qt.RightEdge
        if q.y()<8:edge|=C.Qt.TopEdge
        elif q.y()>shell.height()-8:edge|=C.Qt.BottomEdge
        if edge:w.windowHandle().startSystemResize(edge)
    shell.mousePressEvent=resize_window
    text(shell,'PM3 executable:',36,94,112,41).setStyleSheet('font-size:16px;');field(shell,w.binary_edit,153,94,773,41);action(shell,w.browse_button,934,94,135,42,'Browse…');text(shell,'Port:',1098,94,45,41);field(shell,w.port_edit,1146,94,189,41);action(shell,w.detect_button,1344,94,165,42,'Auto Detect','refresh')
    # A trailing file action uses the same existing Browse callback.
    folder=new_action(shell,w,'',w.browse_button.click,879,97,43,36,'folder');folder.setProperty('chrome',True);folder.setIconSize(C.QSize(34,34));w.binary_edit.setTextMargins(0,0,43,0)
    a=w.port_edit.addAction(G.QIcon(str(ASSETS/'arrow.svg')),W.QLineEdit.TrailingPosition)
    a.triggered.connect(lambda:w.port_edit.completer().complete() if w.port_edit.completer() else None)
    nav=Navigation();shell.put(nav,27,151,1482,48);w.neon_navigation=nav
    for i in range(7):nav.addTab(w.tabs.tabText(i))
    nav.currentChanged.connect(w.tabs.setCurrentIndex);w.tabs.currentChanged.connect(nav.setCurrentIndex)
    w.tabs.setDocumentMode(True);w.tabs.tabBar().hide();shell.put(w.tabs,25,210,1487,420)
    for build,p,bs in zip([reader,viewer,clone,recycle,firmware,recovery,ink],pages,specs):build(w,p,bs)
    # One original output widget serves every tab; no mock messages are inserted.
    console=panel(shell,25,641,1487,369);w.neon_console=console;artwork(console,'terminal',17,9,53,46)
    console_title=text(console,'Console / Recovery Results',88,8,865,41,'section');w.neon_console_title=console_title
    w.neon_console_badge=text(console,'●  Siap',943,10,123,38,'badge');w.neon_console_badge.setAlignment(C.Qt.AlignCenter)
    w.neon_console_actions=[]
    for txt,kind,callback,x in [('Copy','copy',lambda:W.QApplication.clipboard().setText(w.output.toPlainText()),1103),('Clear','trash',w.output_clear,1230),('Save','save',lambda:export_text(w,w.output.toPlainText(),'pm3tool-session.log'),1353)]:w.neon_console_actions.append(new_action(console,w,txt,callback,x,10,117,39,kind))
    w.output.setStyleSheet('');console.put(w.output,752,60,717,178)
    w.neon_reader_table=W.QTableView();w.neon_reader_table.setModel(RecoveryRows(w.recovery_panel.results.model(),True));table_style(w.neon_reader_table,26);console.put(w.neon_reader_table,19,60,717,187)
    for c,width in [(0,89),(1,221),(2,213),(3,191)]:w.neon_reader_table.setColumnWidth(c,width)
    summary_caption=text(console,'Ringkasan sesi sebelumnya',20,246,805,25,'muted');w.neon_summary_caption=summary_caption
    w.neon_reader_metrics=[];w.neon_reader_cards=[]
    for x,kind,title,value in [(19,'database','Key Sektor','0'),(289,'key','Key Unik','0'),(561,'missing','Belum Pulih','—')]:
        card=panel(console,x,269,260,74);artwork(card,kind,21,14,48,46);v=text(card,value,92,11,155,31,'metric');text(card,title,92,44,155,25,'subtitle');w.neon_reader_metrics.append(v);w.neon_reader_cards.append(card)
    w.neon_result_path=text(console,'Hasil: belum ada sesi',871,284,375,36,'subtitle');w.neon_console_folder=new_action(console,w,'Buka Folder',lambda:file_open(w,current_folder(w)),1265,282,203,52,'folder')
    footer=panel(shell,25,933,1487,78);w.neon_footer_panel=footer;w.neon_footer=text(footer,'●   Siap  ·  Belum ada proses penulisan',23,13,1095,52);w.neon_footer.setStyleSheet('font-size:16px;');w.neon_footer_folder=new_action(footer,w,'Buka Folder',lambda:file_open(w,current_folder(w)),1291,8,186,51,'folder')
    # Original indeterminate progress is retained. The idle track has no fake success.
    w.statusBar().removeWidget(w.progress);w.progress.setParent(footer);footer.put(w.progress,330,21,775,19,False)
    w.neon_idle_progress=W.QProgressBar();w.neon_idle_progress.setRange(0,100);w.neon_idle_progress.setValue(0);w.neon_idle_progress.setTextVisible(False);footer.put(w.neon_idle_progress,330,21,775,19,False)
    w.statusBar().hide()
    geometry=[(420,641,369,None),(521,742,268,None),(497,718,204,(933,78)),(563,784,167,(957,54)),(550,779,160,(949,63)),(543,767,176,(950,61)),(628,849,162,None)]
    titles=['Console / Recovery Results','Console / Session Log','Console / Session Log','Console / Session Log','Console / Firmware Log','Console / Recovery Log','Console / Session Log']
    def move_on_shell(widget,rect):
        for i,(child,_) in enumerate(shell.items):
            if child is widget:shell.items[i]=(child,C.QRect(*rect));break
        sx=shell.width()/1536;sy=shell.height()/1024;widget.setGeometry(*(round(v*(sx if n%2==0 else sy)) for n,v in enumerate(rect)))
    def position(canvas,widget,rect,visible=True):
        for i,(child,_) in enumerate(canvas.items):
            if child is widget:canvas.items[i]=(child,C.QRect(*rect));break
        sx=canvas.width()/canvas.base.width();sy=canvas.height()/canvas.base.height();widget.setGeometry(*(round(v*(sx if n%2==0 else sy)) for n,v in enumerate(rect)));widget.setVisible(visible)
    def changed(i):
        h,y,ch,foot=geometry[i];move_on_shell(w.tabs,(25,210,1487,h));console.base=C.QSize(1487,ch);move_on_shell(console,(25,y,1487,ch));console_title.setText(titles[i]);reader_page=i==0;summary=i in (0,1)
        position(console,w.neon_reader_table,(19,60,717,187),reader_page)
        logs={0:(752,60,717,178),1:(15,48,1454,107),2:(19,61,1449,133),3:(18,57,1450,102),4:(18,50,1450,102),5:(18,48,1450,123),6:(14,43,1458,95)}
        position(console,w.output,logs[i]);w.neon_console_badge.setVisible(summary)
        for j,b in enumerate(w.neon_console_actions):position(console,b,(1103+j*127,6 if i==6 else 10,117,39))
        position(console,summary_caption,(20,246 if reader_page else 161,805,25),summary)
        for card,x in zip(w.neon_reader_cards,[19,289,561]):position(console,card,(x,269 if reader_page else 181,260,74 if reader_page else 65),summary)
        position(console,w.neon_result_path,(871,284 if reader_page else 193,375,36),summary or i==6)
        position(console,w.neon_console_folder,(1265,282 if reader_page else 187 if i==1 else 123,203,52 if summary else 36),summary or i==6)
        if i==6:position(console,w.neon_result_path,(1028,123,300,36))
        footer.setVisible(foot is not None)
        if foot:
            fy,fh=foot;footer.base=C.QSize(1487,fh);move_on_shell(footer,(25,fy,1487,fh));position(footer,w.neon_footer,(23,0,1095,fh))
            position(footer,w.neon_footer_folder,(1291,8 if i==2 else 3,186,51 if i==2 else fh-6))
            for prog in (w.progress,w.neon_idle_progress):position(footer,prog,(330,21,775,19),bool(i in (4,5)))
        update_live(w);pages[i].show()
    w.tabs.currentChanged.connect(changed);changed(w.tabs.currentIndex())
    # Existing advanced descendants have explicit visibility flags from parking.
    def show_layout_children(widget):
        lay=widget.layout()
        if lay:
            def show_l(l):
                for i in range(l.count()):
                    it=l.itemAt(i)
                    if it.widget():it.widget().show();show_layout_children(it.widget())
                    elif it.layout():show_l(it.layout())
            show_l(lay)
    show_layout_children(w.recovery_panel.advanced);w.recovery_panel.advanced.setVisible(w.recovery_panel.advanced_toggle.isChecked())
    # Original native subtabs need their contained tables explicitly restored.
    for table in (w.ink_panel.data_table,w.ink_panel.keys_table,w.ink_panel.preview_table):table.show()
    timer=C.QTimer(w);timer.setInterval(200);timer.timeout.connect(lambda:update_live(w));timer.start();w.neon_timer=timer;w.statusBar().messageChanged.connect(lambda _:update_live(w))
    if W.QApplication.platformName()!='offscreen' and w.screen():
        r=w.screen().availableGeometry();w.resize(min(1536,r.width()),min(1024,r.height()))
    shell.show();w.tabs.show();nav.show()

def update_live(w):
    port=w.port_edit.text().strip();w.neon_status.setText(('●  Port: '+port if port else '●  Belum terdeteksi')+'\n     Proxmark3')
    w.neon_firmware_status.setText('●  Port diatur' if port else '●  Belum terdeteksi');w.neon_device_values[1].setText(port or '—');w.neon_device_values[3].setText('Belum diperiksa' if port else 'Belum terdeteksi');w.neon_session_port.setText(port or '—')
    worker=bool(w._worker and w._worker.isRunning());w.neon_idle_progress.setVisible(not worker and w.tabs.currentIndex() in (4,5));w.progress.setVisible(worker and w.tabs.currentIndex() in (4,5))
    msg=w.statusBar().currentMessage() or 'Siap';w.neon_footer.setText('●   '+msg);w.neon_footer.setToolTip(msg)
    report=w.recovery_panel.last_report
    if report:
        state={'keys_found':'Selesai','completed':'Selesai','failed':'Gagal','timeout':'Timeout','cancelled':'Dihentikan'}.get(report.get('status'),'Selesai')
        vals=[state,str(len(report.get('keys',[]))),str(len(report.get('unique_keys',[]))),str(len(report.get('missing',[])))];folder=Path(report.get('session_dir',''));files=sorted(p.name for p in folder.glob('*') if p.is_file() and p.suffix in ('.bin','.json','.eml')) if folder.is_dir() else []
        for l,v in zip(w.neon_session_files,(files+['—']*3)[:3]):l.setText(v)
        w.neon_session_status.setText(state);w.neon_result_path.setText('Hasil: '+str(folder));w.neon_result_path.setToolTip(str(folder))
        w.neon_duration.setText(str(report.get('duration','—')))
    else:
        vals=['Berjalan' if worker and w.recovery_panel._is_recovery else 'Siap','0','0','—']
        w.neon_session_status.setText(vals[0]);w.neon_duration.setText('—');w.neon_result_path.setText('Hasil: belum ada sesi')
        for f in w.neon_session_files:f.setText('—')
    for l,v in zip(w.neon_metrics,vals):l.setText(v)
    for l,v in zip(w.neon_reader_metrics,vals[1:]):l.setText(v)
    w.neon_console_badge.setText('●  '+vals[0])
    w.neon_idle_progress.setValue(100 if w.tabs.currentIndex()==5 and report and report.get('status') in ('completed','keys_found') else 0)
    for l in w.neon_empty_group:l.setVisible(w.recycle_table.rowCount()==0)
    w.ink_panel.summary.setToolTip(w.ink_panel.summary.text()+'\n'+w.ink_panel.field_note.text());w.neon_console_folder.setToolTip(current_folder(w))
    if w.tabs.currentIndex()==6:
        path=w.ink_panel.folder.text();w.neon_result_path.setText('Hasil: '+path);w.neon_result_path.setToolTip(path)

