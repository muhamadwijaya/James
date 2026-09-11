"""Three persistent template editors in the shared AGREGASI application shell."""
from .sidebar_layout import fixed_sidebar, TEMPLATE_SOURCE, remap_sidebar_controls
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path

from PySide6.QtCore import QRectF,QSizeF,QMarginsF,QTimer,Qt,QVariantAnimation,QEasingCurve
from PySide6.QtGui import QColor,QPainter,QPen,QLinearGradient,QPixmap,QPageSize
from PySide6.QtWidgets import (QPushButton,QButtonGroup,QStackedWidget,QDialog,QVBoxLayout,QHBoxLayout,
    QLabel,QWidget,QSizePolicy,QScrollArea,QFileDialog,QMessageBox,QLineEdit,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView)
from PySide6.QtPrintSupport import QPrinter,QPrinterInfo,QPrintDialog

from .ui_controls import ThemedComboBox as QComboBox
from .ui_dialogs import AppDialog as QDialog, MessageBox as QMessageBox, FileDialog as QFileDialog, dialog_parent
from .pages import PageBase
from .dashboard import GREEN,MUTED,WHITE,BLUE
from .navigation import ACTIVE_TOP,ACTIVE_BOTTOM
from .typography import ui_font,draw_text
from .editor_icons import icon
from .template_model import TemplateRepository,LEVELS,validate_document
from .label_render import check_renderable,render_image,paint_document,export_pdf
from .template_workspace import TemplateWorkspace,CONTROL_STYLE
from .template_style import GlassButton,surface
from .navigation import CANVAS_TOP,CANVAS_BOTTOM


class TemplateSelector(GlassButton):
    def __init__(self,level,parent):
        super().__init__('',parent);self.level=level;self.setCheckable(True);self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(level+' TEMPLATE');self.setObjectName('template_'+level.lower())
        self.setStyleSheet('QPushButton {background:transparent;border:0;}')
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);r=QRectF(self.rect()).adjusted(1,1,-1,-1)
        surface(p,r,'blue' if self.isChecked() else 'navy',self.hover,self.isDown())
        name={'BOX':'box_level','CARTON':'carton_level','PALLET':'pallet_level'}[self.level];icon(name,32).paint(p,17,8,32,32)
        draw_text(p,61,4,self.width()-72,22,self.level+' TEMPLATE',11,'#e6f0fb',True,Qt.AlignmentFlag.AlignLeft)
        draw_text(p,61,24,self.width()-72,18,'Template untuk level '+self.level,9,'#aac0d5',False,Qt.AlignmentFlag.AlignLeft)
        p.end()


class FitPreview(QWidget):
    def __init__(self,document,parent=None):
        super().__init__(parent);self.image=render_image(document,200);self.target=QRectF()
        self.setMinimumSize(200,140);self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(),QColor('#032134'))
        bounds=QRectF(self.rect()).adjusted(14,14,-14,-14)
        size=self.image.size().scaled(bounds.size().toSize(),Qt.AspectRatioMode.KeepAspectRatio)
        self.target=QRectF(bounds.center().x()-size.width()/2,bounds.center().y()-size.height()/2,size.width(),size.height())
        p.drawImage(self.target,self.image);p.end()


class PreviewDialog(QDialog):
    def __init__(self,owner,document,identifier):
        super().__init__(owner);self.owner=owner;self.document=deepcopy(document);self.identifier=identifier
        self.setObjectName('print_preview_dialog')
        self.setWindowTitle('Preview label • '+document['name']);self.resize(760,790 if document['height_mm']>document['width_mm'] else 570);self.setMinimumSize(460,340)
        layout=QVBoxLayout(self);layout.setContentsMargins(18,16,18,16);layout.setSpacing(12)
        heading=QLabel(f"{document['name']}  •  {document['width_mm']:g} × {document['height_mm']:g} mm  •  {document['dpi']} DPI");heading.setWordWrap(True);layout.addWidget(heading)
        self.preview=FitPreview(document);layout.addWidget(self.preview,1)
        row=QHBoxLayout();row.setSpacing(8)
        for title,callback in [('Simpan PNG',lambda:self.save('png')),('Simpan PDF',lambda:self.save('pdf')),('Cetak',lambda:owner.active_editor.guard(lambda:owner.print_document(self.document,self.identifier))),('Tutup',self.accept)]:
            b=QPushButton(title);b.setMinimumHeight(36);b.clicked.connect(callback);row.addWidget(b)
        layout.addLayout(row)
    def save(self,kind):
        path,_=QFileDialog.getSaveFileName(self,'Simpan label','label.'+kind,kind.upper()+' (*.'+kind+')')
        if not path:return
        if not path.lower().endswith('.'+kind):path+='.'+kind
        try:
            if kind=='pdf':export_pdf(self.document,path)
            elif not render_image(self.document).save(path,'PNG'):raise ValueError('PNG gagal disimpan.')
            self.owner.repo.record(self.identifier,self.document['level'],'EKSPOR',Path(path).name);self.owner.schedule_refresh()
        except Exception as exc:QMessageBox.warning(self,'Ekspor label',str(exc))


class TemplatePage(PageBase):
    SIDEBAR_ICON_SIZE=14
    SYSTEM_ICON_SIZE=(48,58)
    ACCOUNT_ICON_SIZE=48
    def __init__(self,store):
        super().__init__(store,'template','Master Template','MASTER TEMPLATE LABEL & DESIGN CANVAS','template')
        self.repo=TemplateRepository(store);self.editors={};self.template_kind='PALLET';self.preview_dialog=None
        self.refresh_timer=QTimer(self);self.refresh_timer.setSingleShot(True);self.refresh_timer.setInterval(70);self.refresh_timer.timeout.connect(self.refresh_shared)
        self.stack=QStackedWidget(self);self.stack.setGeometry(8,124,1070,862);self.stack.setStyleSheet('QStackedWidget {background:transparent;}')
        self.selector_group=QButtonGroup(self);self.selector_group.setExclusive(True);self.selectors={}
        for i,level in enumerate(LEVELS):
            selector=TemplateSelector(level,self);selector.setGeometry(258+i*252,69,246,45);self.selector_group.addButton(selector);self.selectors[level]=selector
            selector.clicked.connect(lambda checked=False,key=level:self.select_level(key))
            editor=TemplateWorkspace(self,level);self.editors[level]=editor;self.stack.addWidget(editor)
        self.ring_fraction=0.0;self.ring_target=0.0;self.ring_animation=QVariantAnimation(self);self.ring_animation.setDuration(380);self.ring_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.ring_animation.valueChanged.connect(self.animate_ring)
        self._make_sidebar_controls()
        self.live_timer=QTimer(self);self.live_timer.setInterval(3000);self.live_timer.timeout.connect(self.refresh_shared);self.live_timer.start()
        self.select_level('PALLET');self.refresh_shared()
    @property
    def active_editor(self):return self.editors[self.template_kind]
    def select_level(self,level):
        if level not in self.editors:return
        self.template_kind=level;self.selectors[level].setChecked(True)
        self.editors[level].refresh_sources();self.editors[level].refresh_field_schema();self.editors[level].refresh_previews();self.stack.setCurrentWidget(self.editors[level]);self.schedule_refresh();self.update()
    def cycle_level(self,direction):self.select_level(LEVELS[(LEVELS.index(self.template_kind)+direction)%len(LEVELS)])
    def animate_ring(self,value):self.ring_fraction=float(value);self.update(1298,95,126,90)
    def schedule_refresh(self):
        if not getattr(self,'stopped',False):self.refresh_timer.start()
    def shutdown(self):
        self.stopped=True;self.live_timer.stop();self.refresh_timer.stop();self.ring_animation.stop()
    def refresh(self):
        for editor in self.editors.values():editor.refresh_list()
        self.schedule_refresh();self.update()
    def refresh_shared(self):
        if getattr(self,'stopped',False):return
        if len(self.editors)!=3:return
        rows=self.repo.list();active=sum(json.loads(r['document']).get('active',True) for r in rows)
        self.active_editor.refresh_previews([row for row in rows if row['level']==self.template_kind])
        target=active/max(1,len(rows))
        if target!=self.ring_target:
            self.ring_target=target;self.ring_animation.stop();self.ring_animation.setStartValue(self.ring_fraction);self.ring_animation.setEndValue(target);self.ring_animation.start()
        self.update()
    def reference_panel(self,x,y,w,h,title=None):
        self.rect(x,y,w,h,'#063550','#001f34','#256080',5,True)
        if title:self.text(x+18,y+9,w-36,24,title,12,'#eaf3ff',True)
    def paint_content(self):
        self.reference_panel(8,60,1070,60)
        self.reference_panel(8,124,374,618)
        icon('template',24).paint(self.p,25,136,22,22);self.text(53,135,273,22,'CREATE MASTER TEMPLATE',12,bold=True)
        self.rect(23,161,344,444,'#052e46','#01283e','#15516e',4)
        self.reference_panel(8,748,374,238,'DAFTAR MASTER TEMPLATE '+self.template_kind)
        self.reference_panel(390,124,688,862,'CANVAS DESIGN TEMPLATE PRINT')
        self.text(406,726,390,22,'LIVE PREVIEW TEMPLATE',11,bold=True)
        if hasattr(self,'editors') and self.template_kind in self.editors:
            self.text(882,134,177,22,'● DRAFT' if self.active_editor.dirty else '● TERSIMPAN',9,'#ffc55a' if self.active_editor.dirty else '#85d7a0',align=Qt.AlignmentFlag.AlignRight)
    def _make_sidebar_controls(self):
        for widget in self.widgets:
            if widget.objectName().startswith('shortcut_'):widget.hide()
        self.shortcut_buttons={}
        for i,(key,label,palette) in enumerate([('database','DATABASE','green'),('printer','PRINTER','blue'),('camera','KAMERA','blue'),('scanner','SCANNER','navy'),('logout','LOGOUT','red')]):
            button=GlassButton(label,self,palette,8);button.setObjectName('template_connection_'+key);button.setGeometry(1110+i*62,956,58,23)
            button.clicked.connect(lambda checked=False,k=key:self.action.emit('template_logout' if k=='logout' else 'shortcut_'+k));self.shortcut_buttons[key]=button
        self.history_button=QPushButton('Lihat semua  ›',self);self.history_button.setGeometry(1309,698,108,18);self.history_button.setStyleSheet('QPushButton {background:transparent;border:0;color:#78bfe8;font-size:10px;padding:0;} QPushButton:hover {color:white;}');self.history_button.clicked.connect(self.show_history)
        self.summary_buttons={}
        for i,level in enumerate(LEVELS):
            b=QPushButton(self);b.setGeometry(1108,221+i*20,310,19);b.setStyleSheet('QPushButton {background:transparent;border:0;} QPushButton:hover {background:rgba(40,145,215,30);border:1px solid #256b94;}');b.setToolTip('Buka '+level+' TEMPLATE');b.clicked.connect(lambda checked=False,k=level:self.select_level(k));self.summary_buttons[level]=b
        remap_sidebar_controls([*self.shortcut_buttons.values(), self.history_button, *self.summary_buttons.values()], TEMPLATE_SOURCE)
    def sidebar_metrics(self):
        rows=self.repo.list();docs=[json.loads(row['document']) for row in rows];active=sum(doc.get('active',True) for doc in docs)
        counts={level:sum(doc['level']==level for doc in docs) for level in LEVELS};usage={level:0 for level in LEVELS};today=datetime.now().date().isoformat()
        for record in self.store.db.execute("SELECT level,COUNT(*) n FROM template_activity WHERE substr(ts,1,10)=? AND action IN ('PREVIEW','PRINT JOB','CETAK PDF') GROUP BY level",(today,)):usage[record['level']]=record['n']
        return dict(total=len(rows),active=active,counts=counts,usage=usage,defaults=sum(row['is_default'] for row in rows),edited=max((row['updated_at'] for row in rows),default=''))
    def sidebar(self):
        from .shared_sidebar import paint_sidebar
        paint_sidebar(self)
    def show_history(self):
        dialog=QDialog(self);dialog.setWindowTitle('Seluruh aktivitas template');dialog.resize(920,540);dialog.setStyleSheet(dialog.styleSheet()+CONTROL_STYLE);layout=QVBoxLayout(dialog)
        search=QLineEdit();search.setPlaceholderText('Cari template, aktivitas, level, atau operator…');layout.addWidget(search)
        table=QTableWidget(0,5);table.setHorizontalHeaderLabels(['WAKTU','LEVEL','AKTIVITAS','DETAIL','OPERATOR']);table.verticalHeader().hide();table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);table.setAlternatingRowColors(True)
        for index,width in enumerate((153,80,110,380,130)):table.setColumnWidth(index,width)
        table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.Stretch);layout.addWidget(table)
        count=QLabel();layout.addWidget(count)
        def populate():
            query=search.text().lower();rows=[dict(row) for row in self.store.db.execute('SELECT * FROM template_activity ORDER BY id DESC')];rows=[row for row in rows if query in ' '.join(str(v) for v in row.values()).lower()]
            table.setRowCount(len(rows))
            for i,row in enumerate(rows):
                for j,key in enumerate(('ts','level','action','detail','operator')):
                    value=str(row[key]).replace('T',' ') if key=='ts' else str(row[key]);item=QTableWidgetItem(value);item.setToolTip(value);table.setItem(i,j,item)
            count.setText(str(len(rows))+' aktivitas')
        search.textChanged.connect(populate);populate();close=QPushButton('TUTUP');close.clicked.connect(dialog.accept);layout.addWidget(close);self.history_dialog=dialog;dialog.exec()
    def import_template(self,path=None):
        if not path:path,_=QFileDialog.getOpenFileName(self.window(),'Impor template','','Template JSON (*.json)')
        if not path:return False
        path=Path(path)
        if path.stat().st_size>12_000_000:raise ValueError('File template maksimal 12 MB.')
        try:payload=json.loads(path.read_text(encoding='utf-8'))
        except (ValueError,UnicodeDecodeError):raise ValueError('File JSON tidak valid.') from None
        if not isinstance(payload,dict) or payload.get('format')!='AGREGASI_LABEL_TEMPLATE' or payload.get('version')!=1:raise ValueError('Pilih file hasil Export Template versi 1.')
        document=check_renderable(payload.get('document'));level=document['level'];editor=self.editors[level]
        if not editor.confirm_discard():return False
        identifier=self.repo.save(document);self.select_level(level);editor.load_template(identifier);self.repo.record(identifier,level,'IMPOR',path.name);editor.message('Template berhasil diimpor.');self.schedule_refresh();return identifier
    def show_preview(self,document,identifier):
        doc=check_renderable(document);self.repo.record(identifier,doc['level'],'PREVIEW',doc['name']);self.schedule_refresh()
        self.preview_dialog=PreviewDialog(self,doc,identifier);self.preview_dialog.exec()
    def print_document(self,document,identifier=None,printer=None,confirm=True,pdf_path=None):
        doc=check_renderable(document)
        if doc.get('printer_kind')=='TIJ' and printer is None and not pdf_path:
            runtime=getattr(self,'settings_runtime',None)
            if runtime is None:raise ValueError('Koneksi printer TIJ belum siap pada sesi ini.')
            runtime.print_tij(doc);self.repo.record(identifier,doc['level'],'PRINT JOB','TIJ '+doc['printer_host']+':'+str(doc['printer_port']))
            self.schedule_refresh();self.active_editor.message('Tugas cetak dikirim ke printer TIJ.');return True
        if pdf_path:
            export_pdf(doc,pdf_path);self.repo.record(identifier,doc['level'],'CETAK PDF',Path(pdf_path).name);self.schedule_refresh();return True
        if printer is None:
            if not QPrinterInfo.availablePrinters():
                path,_=QFileDialog.getSaveFileName(self.window(),'Printer belum tersedia — simpan label sebagai PDF','label_'+doc['level'].lower()+'.pdf','PDF (*.pdf)')
                if not path:return False
                if not path.lower().endswith('.pdf'):path+='.pdf'
                return self.print_document(doc,identifier,pdf_path=path)
            printer=QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setResolution(int(doc['dpi']));printer.setPageSize(QPageSize(QSizeF(doc['width_mm'],doc['height_mm']),QPageSize.Unit.Millimeter,'Label',QPageSize.SizeMatchPolicy.ExactMatch));printer.setPageMargins(QMarginsF(0,0,0,0));printer.setFullPage(True)
        if confirm:
            dialog=QPrintDialog(printer,dialog_parent(self));dialog.setWindowTitle('Cetak label '+doc['level'])
            if dialog.exec()!=QDialog.DialogCode.Accepted:return False
        # Keep the label's physical size even if the print dialog selects A4.
        # Qt rounds custom PDF paper dimensions to whole PostScript points.
        available=printer.pageRect(QPrinter.Unit.DevicePixel)
        width=doc['width_mm']/25.4*printer.resolution();height=doc['height_mm']/25.4*printer.resolution()
        tolerance=printer.resolution()/72
        if available.width()+tolerance<width or available.height()+tolerance<height:
            raise ValueError('Kertas printer lebih kecil dari label. Pilih ukuran kertas yang sesuai.')
        target=QRectF(available.x(),available.y(),min(width,available.width()),min(height,available.height()))
        painter=QPainter(printer)
        if not painter.isActive():raise ValueError('Printer tidak dapat menerima tugas cetak.')
        try:paint_document(painter,doc,target)
        finally:painter.end()
        if printer.printerState()==QPrinter.PrinterState.Error:raise ValueError('Driver printer melaporkan kesalahan.')
        self.repo.record(identifier,doc['level'],'PRINT JOB',printer.printerName() or printer.outputFileName());self.schedule_refresh();self.active_editor.message('Tugas cetak dikirim ke driver printer.');return True
    def may_close(self):
        for editor in self.editors.values():
            if editor.dirty and not editor.confirm_discard():return False
        return True
