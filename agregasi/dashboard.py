from .sidebar_layout import fixed_sidebar, SIDEBAR
from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QPointF, QFile, QIODevice, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QLinearGradient, QPolygonF
from .responsive_surface import SurfaceSvgRenderer as QSvgRenderer, SurfacePainter
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QWidget, QPushButton, QComboBox

from .ui_controls import ThemedComboBox
from .typography import draw_text, ui_font
from .display_preferences import CURRENT, icon_rect
from .navigation import Navigation, ITEMS, button_rect, CANVAS_TOP, CANVAS_BOTTOM, PANEL_BORDER, PANEL_SHADOW_ALPHA

BASE = Path(__file__).resolve().parent.parent
WHITE, MUTED, GREEN, RED, YELLOW, BLUE = '#f0f5ff', '#c4d3e5', '#73e342', '#ff403e', '#ffc621', '#12afff'

def num(value):
    return f'{value:,}'.replace(',', '.')

class Dashboard(QWidget):
    action = Signal(str)
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.setFont(ui_font())
        self.setFixedSize(1448, 1086)
        self.icons = {p.stem: QSvgRenderer(str(p)) for p in (BASE/'assets/svg').glob('*.svg')}
        loader = QUiLoader()
        file = QFile(str(BASE/'ui/dashboard.ui'))
        file.open(QIODevice.OpenModeFlag.ReadOnly)
        self.controls = loader.load(file, self)
        file.close()
        self.controls.setGeometry(0, 0, 1448, 1086)
        self.controls.setAutoFillBackground(False)
        for b in self.controls.findChildren(QPushButton):
            # Keep accessibleName for keyboard/screen-reader use, but avoid the
            # native black tooltip bubble that makes painted cards feel like
            # a rigid overlay instead of independent UI objects.
            b.setToolTip('')
            b.clicked.connect(lambda checked=False, name=b.objectName(): self.action.emit(name))
        original=self.controls.findChild(QComboBox,'period')
        self.period=ThemedComboBox(self.controls);self.period.setObjectName('period')
        self.period.setGeometry(original.geometry());self.period.addItems([original.itemText(i) for i in range(original.count())]);self.period.setCurrentIndex(original.currentIndex())
        original.hide();original.setObjectName('replaced_period');original.deleteLater()
        self.period.setStyleSheet('QComboBox {font-size:11px;padding-top:0;padding-bottom:0;}')
        self.period.currentIndexChanged.connect(self.update)
        self.active = 'dashboard'
        self.navigation = Navigation(self, self.controls)

    def text(self, x, y, w, h, text, size=13, color=WHITE, bold=False,
             align=Qt.AlignmentFlag.AlignLeft, wrap=False):
        return draw_text(self.p, x, y, w, h, text, size, color, bold, align, wrap)

    def line(self,x,y,w,color='#29485f'):
        self.p.setPen(QPen(QColor(color),1))
        self.p.drawLine(QPointF(x,y),QPointF(x+w,y))

    def rect(self,x,y,w,h,c1='#062c4a',c2='#001b30',stroke='#385e78',radius=6,shadow=False):
        radius = radius * CURRENT['radius'] / 5 if radius else 0
        if self.store.get('configuration',{}).get('theme')=='HIGH CONTRAST' and c1=='#062c4a':
            c1=c2='#000814';stroke='#91b5cd'
        if shadow:
            self.p.setPen(Qt.PenStyle.NoPen)
            self.p.setBrush(QColor(20,40,60,PANEL_SHADOW_ALPHA))
            self.p.drawRoundedRect(QRectF(x,y+3,w,h),radius,radius)
        grad=QLinearGradient(x,y,x+w*.65,y+h)
        grad.setColorAt(0,QColor(c1)); grad.setColorAt(1,QColor(c2))
        self.p.setBrush(grad); self.p.setPen(QPen(QColor(stroke),1))
        self.p.drawRoundedRect(QRectF(x,y,w,h),radius,radius)

    def panel(self,x,y,w,h,title=None):
        self.rect(x,y,w,h,stroke=PANEL_BORDER,shadow=True)
        self.p.setBrush(Qt.BrushStyle.NoBrush)
        self.p.setPen(QPen(QColor('#476981'),.7))
        self.p.drawRoundedRect(QRectF(x+2,y+2,w-4,h-4),5,5)
        if title:
            self.text(x+12,y+7,w-24,26,title,14,bold=True)
            self.line(x+10,y+34,w-20)

    def icon(self,name,x,y,size=34):
        self.icons[name].render(self.p,icon_rect(x,y,size))

    def dot(self,x,y,color=GREEN,kind='check',size=14):
        self.p.setPen(Qt.PenStyle.NoPen); self.p.setBrush(QColor(color))
        if kind=='warning':
            self.p.drawPolygon(QPolygonF([QPointF(x+size/2,y),QPointF(x+size,y+size),QPointF(x,y+size)]))
        else:self.p.drawEllipse(QRectF(x,y,size,size))
        self.text(x,y-1,size,size+1,'!' if kind=='warning' else ('×' if kind=='cross' else '✓'),size-2,'#003347',True,Qt.AlignmentFlag.AlignCenter)

    def stage_card(self,index,x,w):
        stage=['BOX','CARTON','PALLET'][index]
        values=self.data['stages'][stage]
        self.rect(x,237,w,234,stroke='#5f9e8c' if index==0 else '#3ea7e2')
        self.icon(['units','carton','pallet'][index],x+11,247,29)
        self.text(x+46,242,w-50,25,f'TAHAP {index+1} / {stage}',13,bold=True)
        self.text(x+46,267,w-74,26,'PROSES SELESAI',10,GREEN,True)
        self.dot(x+w-24,273)
        self.text(x+14,291,w-28,33,num(values['total']),28,bold=True)
        self.text(x+14,322,w-28,17,stage.lower()+' terproses',10)
        self.line(x+9,338,w-18)
        for j,(label,key,col,kind) in enumerate([('VALID','valid',GREEN,'check'),('REJECT','reject',RED,'cross'),('DUPLIKAT','duplicate',YELLOW,'warning'),('SELESAI','total',BLUE,'check')]):
            y=348+j*32
            self.dot(x+14,y+2,col,kind)
            self.text(x+36,y-3,65,25,label,10)
            self.text(x+104,y-3,w-112,25,f'{values[key]} {stage.lower()}',10,align=Qt.AlignmentFlag.AlignRight)
            if j<3:self.line(x+9,y+25,w-18,'#1d435b')

    def progress(self,x,y,w,value,color):
        self.rect(x,y,w,12,'#0c3049','#0a273d','#28506b',2)
        n=16
        for j in range(n):
            left=x+2+j*(w-4)/n
            if j/n<value:
                self.rect(left,y+2,(w-4)/n-1,8,color,'#269817' if color==GREEN else '#037ebe',color,1)
                self.line(left+2,y+3,(w-4)/n-5,'#c5f7a9' if color==GREEN else '#7ee1ff')

    def chart_values(self):
        base=[650,1100,1770,1120,1900,530,2450,1990,1500,2090,1300,2450,1110,2090,1120,1180,1940,880,1880,1420,970,640]
        if self.period.currentIndex()==2:
            rows=[e for e in self.store.events(limit=100000) if e['source']!='reference']
            values={s:[0]*12 for s in ['VALID','REJECT','DUPLIKAT']}
            for e in rows:
                if e['status'] in values:values[e['status']][int(e['ts'][11:13])//2]+=1
            return values['VALID'],values['REJECT'],values['DUPLIKAT'],max([5]+[max(v) for v in values.values()]),[f'{i:02}:00' for i in range(0,24,2)]
        if self.period.currentIndex()==1:base=[450,310,230,180,540,950]+base[:-4]
        reject=[int(v*(.08+.015*(i%4))) for i,v in enumerate(base)]
        dup=[int(v*(.025+.012*(i%3))) for i,v in enumerate(base)]
        return base,reject,dup,3000,['06:00','08:00','10:00','12:00','14:00','16:00','18:00','20:00','22:00','24:00']

    def draw_chart(self):
        self.text(28,556,52,24,'PERIODE',11)
        for x,label,col in [(269,'VALID',GREEN),(339,'REJECT',RED),(413,'DUPLIKAT',YELLOW)]:
            self.rect(x,564,9,9,col,col,col,0)
            self.text(x+14,555,75,25,label,11)
        vs,rs,ds,maximum,labels=self.chart_values()
        x,y,w,h=75,592,423,95
        for i in range(5):
            yy=y+h-i*h/4
            self.line(x,yy,w,'#163f57')
            self.text(24,yy-9,38,18,num(round(maximum*i/4)),11,MUTED,align=Qt.AlignmentFlag.AlignRight)
        step=w/len(vs)
        for i in range(len(vs)):
            for j,(array,color,dark) in enumerate([(vs,GREEN,'#178339'),(rs,RED,'#b52619'),(ds,YELLOW,'#ba8900')]):
                bh=max(0,array[i]/maximum*h)
                if bh:self.rect(x+i*step+j*step*.20,y+h-bh,step*.36 if j==0 else step*.18,bh,color,dark,color,0)
        for i,label in enumerate(labels):
            xx=x+i*w/max(1,len(labels)-1)
            self.text(xx-25,690,50,26,label,11,align=Qt.AlignmentFlag.AlignCenter)
        for x,w,title,value,col,bg in [(25,156,'TOTAL VALID',17120,GREEN,'#003b2f'),(187,155,'TOTAL REJECT',1330,RED,'#281c38'),(348,156,'TOTAL DUPLIKAT',650,YELLOW,'#273029')]:
            self.rect(x,722,w,56,bg,bg,'#2b5360',4)
            self.text(x,726,w,20,title,12,col,align=Qt.AlignmentFlag.AlignCenter)
            self.text(x+8,750,w-54,23,num(value),21,bold=True,align=Qt.AlignmentFlag.AlignRight)
            self.text(x+w-41,750,34,23,'unit',12)

    def paintEvent(self,event):
        self.data=self.store.summary()
        self.p=SurfacePainter(self); self.p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        from .shell_layout import paint_header
        paint_header(self, 'MONITORING & RINGKASAN PROSES AGREGASI')
        for x,w,title,value,unit,ico,delta in [
            (15,209,'TOTAL UNIT HARI INI',self.data['units'],'unit','units','12,5%'),
            (233,196,'TOTAL BOX',self.data['stages']['BOX']['total'],'box','box','14,1%'),
            (438,198,'TOTAL CARTON',self.data['stages']['CARTON']['total'],'carton','carton','9,8%'),
            (644,179,'TOTAL PALLET',self.data['stages']['PALLET']['total'],'pallet','pallet','7,1%')]:
            self.panel(x,83,w,103)
            self.icon(ico,x+13,108,38)
            self.text(x+61,95,w-66,25,title,12,bold=True)
            self.text(x+61,120,w-73,36,num(value),28,bold=True)
            self.text(x+12,148,42,24,unit,10,MUTED,align=Qt.AlignmentFlag.AlignCenter)
            self.text(x+60,157,55,22,'↗ '+delta,12,GREEN,True)
            self.text(x+116,157,w-122,22,'vs kemarin',9)
        self.panel(832,83,263,103)
        for x,ico,label,value,delta in [(843,'shield','VALID RATE','92,8%','↗ 3,2%'),(980,'reject','REJECT RATE','7,2%','↘ -3,2%')]:
            self.icon(ico,x,109,34)
            self.text(x+39,95,74 if ico=='reject' else 86,24,label,10,bold=True)
            self.text(x+40,120,71 if ico=='reject' else 81,38,value,23,bold=True)
            self.text(x+6,157,56,20,delta,12,GREEN,True)
            self.text(x+60,157,53 if ico=='reject' else 66,20,'vs kemarin',9)
        self.p.setPen(QPen(QColor('#5c829d'),1));self.p.drawLine(969,100,969,171)
        self.panel(15,200,640,309)
        self.text(26,207,610,24,'RINGKASAN TAHAP AGREGASI',14,bold=True)
        for i,(x,w) in enumerate([(26,194),(250,189),(469,175)]):self.stage_card(i,x,w)
        for x in [226,446]:
            self.p.setPen(Qt.PenStyle.NoPen);self.p.setBrush(QColor('#40abe9'))
            self.p.drawPolygon(QPolygonF([QPointF(x,334),QPointF(x+9,334),QPointF(x+9,329),QPointF(x+18,338),QPointF(x+9,347),QPointF(x+9,342),QPointF(x,342)]))
        self.panel(664,200,431,309,'MONITORING PRODUK AKTIF')
        current=self.store.get('current')
        fields=[('PRODUK',self.store.get('product')),('BATCH',self.store.get('batch')),('BOX SAAT INI',current['BOX']),('CARTON SAAT INI',current['CARTON']),('PALLET SAAT INI',current['PALLET']),('MODE AGREGASI',self.store.get('mode'))]
        for i,(label,value) in enumerate(fields):
            self.text(679,243+27*i,118,23,label,12)
            self.text(798,243+27*i,282,23,value,14,GREEN if i==5 else WHITE,True)
        self.line(675,409,409)
        for i,(stage,amount,total) in enumerate([('BOX',256,256),('CARTON',42,42),('PALLET',14,15)]):
            local=self.data['stages'][stage]['total']-total
            completed=amount+local if stage!='PALLET' else self.data['stages'][stage]['valid']
            fraction=completed/(total+local)
            y=417+i*28
            self.text(679,y,112,25,f'TAHAP {i+1} / {stage}',12,bold=True)
            self.progress(792,y+7,156,fraction,GREEN if fraction==1 else BLUE)
            pct='100%' if fraction==1 else f'{fraction*100:.1f}%'.replace('.',',')
            self.text(958,y,45,25,pct,12,bold=True)
            self.text(1007,y,73,25,f'{completed} / {total+local} {stage.lower()}',11,align=Qt.AlignmentFlag.AlignRight)
        self.panel(15,520,499,268,'GRAFIK PRODUKSI / PROGRES SHIFT')
        self.draw_chart()
        self.panel(522,520,573,268,'AKTIVITAS TERKINI (SEMUA MODUL)')
        xs=[538,620,742,901,1026]
        for x,w,label in zip(xs,[75,116,148,118,55],['WAKTU','MODUL','KETERANGAN','DETAIL','STATUS']):self.text(x,557,w,20,label,10,MUTED)
        self.line(532,578,551)
        for i,e in enumerate(self.store.events(limit=8)):
            y=579+i*24
            stage_number={'BOX':1,'CARTON':2,'PALLET':3}.get(e['stage'],0)
            for x,w,val in zip(xs[:-1],[77,118,150,115],[e['ts'][11:19],f"TAHAP {stage_number} / {e['stage']}" if stage_number else 'REVISI UNIT',e['action'],e['code']]):self.text(x,y,w,23,val,11)
            col={'VALID':GREEN,'REJECT':RED,'DUPLIKAT':YELLOW}.get(e['status'],BLUE)
            self.dot(1017,y+6,col,'check' if e['status']=='VALID' else 'cross',13)
            self.text(1037,y,52,23,e['status'],11,col)
            self.line(532,y+23,551,'#173e56')
        self.panel(15,800,537,185,'STATUS PERANGKAT & KONEKSI')
        devices=self.store.get('devices')
        for name,x,label,sub in [('database',25,'DATABASE','Response: 18 ms'),('printer',131,'PRINTER LABEL','Queue: 0'),('camera',237,'KAMERA VERIFIKASI','Connection: OK'),('scanner',343,'SCANNER','Connection: OK'),('conveyor',449,'CONVEYOR','Status: RUNNING')]:
            self.rect(x,837,97,135,stroke='#3c5a71')
            self.text(x,842,97,23,label,10,align=Qt.AlignmentFlag.AlignCenter)
            self.icon(name,x+26,870,44)
            online=devices[name]
            self.rect(x+9,921,79,20,'#002c2a' if online else '#471f2c','#002c2a' if online else '#471f2c','#084448',5)
            self.text(x,919,97,23,'ONLINE' if online else 'OFFLINE',11,GREEN if online else RED,align=Qt.AlignmentFlag.AlignCenter)
            self.text(x,944,97,21,sub if online else 'Tidak terhubung',10,align=Qt.AlignmentFlag.AlignCenter)
        self.panel(560,800,535,185,'AKSI CEPAT')
        for x,w,c1,c2,stroke,ico,line1,line2 in [(570,118,'#1c7b37','#003c29','#3e9e4b','units','BUKA TAHAP 1','/ BOX'),(697,118,'#087acb','#02345b','#1b9cec','box','BUKA TAHAP 2','/ CARTON'),(824,120,'#12588f','#002b4d','#268ce0','pallet','BUKA TAHAP 3','/ PALLET'),(953,125,'#614091','#271f59','#7555b6','upload','UPLOAD INSTAN','')]:
            self.rect(x,843,w,114,c1,c2,stroke,5)
            self.icon(ico,x+w/2-19,862,38)
            self.text(x,902,w,24,line1,13,bold=True,align=Qt.AlignmentFlag.AlignCenter)
            self.text(x,925,w,24,line2,13,align=Qt.AlignmentFlag.AlignCenter)
        self.sidebar()
        self.navigation.paint(self.p)
        self.p.end()

    def rect_(self):
        return QRectF(0,0,1448,1086)

    def sidebar(self):
        from .shared_sidebar import paint_sidebar
        paint_sidebar(self)

    def side_panel(self,y,h,title):
        self.rect(1115,y,309,h,stroke='#2a526a',radius=4)
        self.text(1124,y+3,289,24,title,14,bold=True)
        self.line(1124,y+27,289,'#1b435c')
