"""One independent template workspace per packaging level."""
import base64
from copy import deepcopy
from collections import Counter
import json
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import QByteArray,QBuffer,QIODevice,QRectF,QSize,Qt
from PySide6.QtGui import QColor,QImageReader,QPainter,QPixmap
from PySide6.QtWidgets import (QWidget,QTabWidget,QFormLayout,QVBoxLayout,QHBoxLayout,QGridLayout,
    QLabel,QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox,QCheckBox,QPushButton,QToolButton,QMenu,QRadioButton,QStackedWidget,QDialog,QFrame,
    QPlainTextEdit,QTableWidget,QTableWidgetItem,QAbstractItemView,QHeaderView,QFileDialog,QMessageBox)

from .ui_controls import ThemedComboBox as QComboBox
from .ui_dialogs import AppDialog as QDialog, MessageBox as QMessageBox, FileDialog as QFileDialog, dialog_parent
from .template_database import columns as database_columns, DatabaseSourceDialog, product_choices, product_source
from .editor_icons import icon
from .template_style import GlassButton, surface
from .typography import ui_font
from .label_canvas import LabelCanvas
from .label_render import check_renderable,render_image,export_pdf
from .template_model import LEVELS,FIELDS,default_document,validate_document

CONTROL_STYLE='''
QLabel {color:#bfd0e2;font-size:10px;}
QPushButton {color:#e7f3ff;background:#084b79;border:1px solid #246a94;border-radius:4px;padding:3px 6px;font-size:11px;}
QPushButton:hover {background:#11649b;}
QPushButton:focus {border:1px solid #83bee7;}
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox,QPlainTextEdit {color:#edf5ff;background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #032b45,stop:1 #001c30);border:1px solid #14648e;border-radius:3px;padding:2px 5px;font-size:11px;}
QComboBox::drop-down {width:17px;border:0;}
QTabWidget,QTabBar {background:#04253b;}
QTabWidget::pane {border:1px solid #2a526c;background:#04253b;}
QTabBar::tab {background:#062b43;color:#afc5da;padding:7px 15px;border:0;font-size:11px;}
QTabBar::tab:selected {background:#084f80;color:#f3f8ff;}
QToolButton {background:transparent;color:#c6d7e8;border:1px solid transparent;border-radius:3px;padding:3px;font-size:10px;}
QToolButton:hover {background:#103d5c;border-color:#355f7e;}
QToolButton:checked {background:#07578d;border-color:#247cac;}
QToolButton:disabled {color:#52697d;}
QCheckBox {color:#c1d4e7;font-size:10px;}
QTableWidget {background:#032339;alternate-background-color:#082c44;color:#d8e8f7;gridline-color:#23475e;border:1px solid #31566d;font-size:10px;}
QHeaderView::section {background:#0a324c;color:#bad1e5;padding:5px;border:0;font-size:9px;}
QTableWidget::item {padding:3px;}
QScrollBar:horizontal {background:#092d42;height:10px;}
QScrollBar::handle:horizontal {background:#3b6b87;min-width:25px;border-radius:4px;}
QRadioButton {color:#c8dbec;font-size:11px;spacing:7px;}
QRadioButton:checked {color:#8deb45;}
QRadioButton::indicator {width:10px;height:10px;border:1px solid #738a9c;border-radius:6px;background:#06283e;}
QRadioButton::indicator:checked {background:#8bf251;border:1px solid #8bf251;}
QRadioButton:focus {color:#edf5ff;}
QFrame#templateInfo {border:1px solid #126084;border-radius:4px;background:#042a42;}
QMenu {background:#062b43;color:#e0efff;border:1px solid #345d78;}
QMenu::item:selected {background:#075b91;}
'''

_ARROW_ROOT=(Path(__file__).resolve().parent.parent/'assets/svg').as_posix()
CONTROL_STYLE += """
QSpinBox::up-button,QDoubleSpinBox::up-button {subcontrol-origin:border;subcontrol-position:top right;width:14px;border:0;border-left:1px solid #175575;background:#06334d;}
QSpinBox::down-button,QDoubleSpinBox::down-button {subcontrol-origin:border;subcontrol-position:bottom right;width:14px;border:0;border-left:1px solid #175575;background:#06334d;}
QSpinBox::up-arrow,QDoubleSpinBox::up-arrow {image:url("@ROOT@/chevron_up.svg");width:7px;height:5px;}
QSpinBox::down-arrow,QDoubleSpinBox::down-arrow,QComboBox::down-arrow {image:url("@ROOT@/chevron_down.svg");width:7px;height:5px;}
""".replace('@ROOT@',_ARROW_ROOT)


class Thumbnail(GlassButton):
    def __init__(self,level,parent):
        super().__init__('',parent,'navy');self.level=level;self.image=None;self.current=False;self.document=None;self.identifier=None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet('QPushButton {background:transparent;border:0;}')
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        surface(p,QRectF(self.rect()).adjusted(1,1,-1,-1),'navy',self.hover)
        if self.current or self.hasFocus():
            from PySide6.QtGui import QPen
            p.setPen(QPen(QColor('#559fdb'),2));p.setBrush(Qt.BrushStyle.NoBrush);p.drawRoundedRect(QRectF(self.rect()).adjusted(2,2,-2,-2),4,4)
        p.setFont(ui_font(9));p.setPen(QColor('#d3e5f5'))
        name=self.document['name'] if self.document else ''
        name=p.fontMetrics().elidedText(name,Qt.TextElideMode.ElideRight,self.width()-16)
        p.drawText(QRectF(8,7,self.width()-16,15),int(Qt.AlignmentFlag.AlignCenter),name)
        p.setFont(ui_font(8));p.setPen(QColor('#aac7dd'))
        dims=f"{self.document['width_mm']:g} x {self.document['height_mm']:g} mm" if self.document else ''
        p.drawText(QRectF(8,23,self.width()-16,13),int(Qt.AlignmentFlag.AlignCenter),dims)
        if self.image is not None:
            r=QRectF(8,43,self.width()-16,self.height()-53);size=self.image.size().scaled(r.size().toSize(),Qt.AspectRatioMode.KeepAspectRatio)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform);p.drawImage(QRectF(r.center().x()-size.width()/2,r.center().y()-size.height()/2,size.width(),size.height()),self.image)
        elif self.document:
            p.drawText(QRectF(8,43,self.width()-16,self.height()-53),int(Qt.AlignmentFlag.AlignCenter|Qt.TextFlag.TextWordWrap),'Pratinjau tidak tersedia')
        p.end()


class SerialChoice(QWidget):
    from PySide6.QtCore import Signal
    currentTextChanged=Signal(str)
    def __init__(self,names=None):
        super().__init__();layout=QHBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(7)
        names=names or {'SERIAL':'SERIAL','UNIX':'UNIX'}
        self.choices={}
        for name,label in names.items():
            radio=QRadioButton(label,self);self.choices[name]=radio;layout.addWidget(radio)
            radio.toggled.connect(lambda on,n=name:self.currentTextChanged.emit(n) if on else None)
        self.choices[next(iter(self.choices))].setChecked(True)
    def currentText(self):return next((name for name,radio in self.choices.items() if radio.isChecked()),'SERIAL')
    def setCurrentText(self,value):
        if value in self.choices:self.choices[value].setChecked(True)


class TemplateWorkspace(QWidget):
    PAGE_SIZE=4
    PREVIEW_PAGE_SIZE=5
    def __init__(self,owner,level):
        super().__init__(owner.stack);self.owner=owner;self.level=level;self.repo=owner.repo;self.syncing=False;self.identifier=None;self.list_page=0
        rows=self.repo.list(level);doc=self.repo.get(rows[0]['id'])['document'] if rows else default_document(level)
        if rows:self.identifier=rows[0]['id']
        self.setObjectName('TemplateWorkspace');self.setStyleSheet(CONTROL_STYLE)
        self.canvas=LabelCanvas(doc,self);self.canvas.setGeometry(484,71,572,478)
        self.tabs=QTabWidget(self);self.tabs.setObjectName('template_editor_tabs')
        self.tabs.setGeometry(18,43,340,433)
        self._make_metadata();self._make_properties();self._make_data();self._make_toolbar();self._make_tools();self._make_actions()
        self.list_table=QTableWidget(0,6,self);self.list_table.setGeometry(18,663,340,135)
        self.list_table.setHorizontalHeaderLabels(['NAMA TEMPLATE','PREFIX','TIPE','MIN–MAX','CHILD','STATUS']);self.list_table.verticalHeader().hide()
        self.list_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.list_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.list_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection);self.list_table.setAlternatingRowColors(True);self.list_table.setWordWrap(False)
        self.list_table.setStyleSheet('QTableWidget {font-size:8px;border:1px solid #145b7e;} QTableWidget::item {padding:2px;} QHeaderView::section {font-size:7px;padding:3px 1px;background:#074168;}')
        header=self.list_table.horizontalHeader();header.setMinimumSectionSize(25);header.setStretchLastSection(False)
        for i,width in enumerate((98,32,39,44,70,55)):self.list_table.setColumnWidth(i,width)
        header.setSectionResizeMode(5,QHeaderView.ResizeMode.Stretch)
        self.list_table.verticalHeader().setDefaultSectionSize(29);self.list_table.cellClicked.connect(self.choose_row)
        self.list_table.cellDoubleClicked.connect(lambda row,col:self.guard(lambda:self.toggle_active(row)) if col==5 else None)
        self.list_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu);self.list_table.customContextMenuRequested.connect(self.list_menu)
        self.page_info=QLabel(self);self.page_info.setGeometry(22,814,213,24);self.page_info.setStyleSheet('font-size:9px;color:#c7dce9;')
        self.previous_button=self.action_button('previous','‹',lambda:self.turn_page(-1),249,814,25,height=25)
        self.page_number=QLabel(self);self.page_number.setGeometry(277,814,37,25);self.page_number.setAlignment(Qt.AlignmentFlag.AlignCenter);self.page_number.setStyleSheet('background:#0763a4;border:1px solid #2187c4;border-radius:3px;color:white;')
        self.next_button=self.action_button('next','›',lambda:self.turn_page(1),317,814,25,height=25)
        self.status=QLabel(self);self.status.setGeometry(18,481,340,11)
        self.preview_page=0;self.preview_cache={};self.thumbnails=[];self._thumbnail_slots=[]
        for i in range(self.PREVIEW_PAGE_SIZE):
            thumb=Thumbnail(self.level,self);thumb.setGeometry(398+i*133,626,126,186)
            thumb.setObjectName(f'saved_preview_{self.level}_{i}')
            thumb.clicked.connect(lambda checked=False,t=thumb:self.guard(lambda:self.choose_preview(t.identifier)))
            self._thumbnail_slots.append(thumb)
        self.preview_empty=QLabel('Belum ada template '+self.level+' tersimpan.\nBuat template, lalu klik Simpan.',self)
        self.preview_empty.setGeometry(398,626,658,186);self.preview_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_page_info=QLabel(self);self.preview_page_info.setGeometry(398,820,340,25)
        self.preview_page_info.setStyleSheet('color:#afc9dd;font-size:9px;')
        self.preview_previous=self.action_button('preview_previous','‹ Sebelumnya',lambda:self.turn_preview_page(-1),766,820,100,'navy',25)
        self.preview_number=QLabel(self);self.preview_number.setGeometry(873,820,70,25);self.preview_number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_next=self.action_button('preview_next','Berikutnya ›',lambda:self.turn_preview_page(1),950,820,106,'blue',25)
        self.preview_previous.setAccessibleName('Halaman preview sebelumnya');self.preview_next.setAccessibleName('Halaman preview berikutnya')
        self.canvas.changed.connect(self.document_changed);self.canvas.selection_changed.connect(self.populate_properties)
        self.canvas.edit_requested.connect(lambda identifier:self.tabs.setCurrentIndex(1))
        self.canvas.undo.canUndoChanged.connect(self.undo_button.setEnabled);self.canvas.undo.canRedoChanged.connect(self.redo_button.setEnabled)
        self.undo_button.setEnabled(False);self.redo_button.setEnabled(False)
        self.populate_metadata();self.populate_data();self.refresh_list();self.populate_properties()
    @property
    def document(self):return self.canvas.document
    @property
    def dirty(self):return not self.canvas.undo.isClean() or self.identifier is None or getattr(self,'_data_dirty',False)
    def message(self,text,error=False):
        self.status.setText(text);self.status.setToolTip(text);self.status.setStyleSheet('color:'+('#ff8e8e' if error else '#9cddb5')+';font-size:9px;')
    def guard(self,callback):
        try:return callback()
        except Exception as exc:
            self.message(str(exc),True);QMessageBox.warning(self,'Periksa data',str(exc));return False
    def tool_button(self,parent,name,label,callback,width=28):
        b=QToolButton(parent);b.setIcon(icon(name));b.setIconSize(QSize(18,18));b.setToolTip(label);b.setAccessibleName(label);b.setFixedSize(width,28)
        b.clicked.connect(lambda checked=False:self.guard(callback));return b
    def action_button(self,name,text,callback,x,y,w=166,color='blue',height=34):
        palette={'#075937':'green','#7b2d2c':'red','#70570d':'gold','#084b79':'blue','#735614':'gold','#085d3c':'green'}.get(color,color)
        if palette not in ('blue','green','red','gold','navy'):palette='blue'
        button=GlassButton(text,self,palette,10 if w>=130 else 8);button.setObjectName(name+'_'+self.level);button.setGeometry(x,y,w,height)
        key=name.removeprefix('template_')
        if key in ('new','save','duplicate','delete','default','preview','import','export','publish'):
            button.setIcon(icon(key));button.setIconSize(QSize(21 if w>=130 else 16,21 if w>=130 else 16))
        button.setToolTip(text);button.clicked.connect(lambda checked=False:self.guard(callback));return button

    def _make_metadata(self):
        panel=QWidget();layout=QVBoxLayout(panel);layout.setContentsMargins(9,8,9,7);layout.setSpacing(6)
        form=QFormLayout();form.setSpacing(4);form.setLabelAlignment(Qt.AlignmentFlag.AlignVCenter);layout.addLayout(form)
        self.name_edit=QLineEdit();self.name_edit.setMaxLength(120);self.gtin=QLineEdit();self.gtin.setMaxLength(14)
        self.nie=QLineEdit();self.nie.setMaxLength(80);self.nie.setPlaceholderText("Nomor izin edar")
        self.product_name=QLineEdit();self.product_name.setMaxLength(120)
        self.target_min=QSpinBox();self.target_max=QSpinBox()
        for widget in (self.target_min,self.target_max):widget.setRange(1,1000000);widget.setFixedHeight(25)
        self.print_mode=SerialChoice({'AUTO':'Auto print','MANUAL':'Manual print'});self.print_mode.setCurrentText('MANUAL')
        self.print_mode.setToolTip('Setelah target maksimum tercapai: Auto mengirim label, Manual menunggu tombol Print Label.')
        self.prefix=QComboBox();self.prefix.setEditable(True);self.prefix.addItems([{'BOX':'BOX','CARTON':'CTN','PALLET':'PLT'}[self.level]])
        self.prefix.lineEdit().setMaxLength(20);prefix_row=QWidget();pl=QVBoxLayout(prefix_row);pl.setContentsMargins(0,0,0,0);pl.setSpacing(1);pl.addWidget(self.prefix)
        self.prefix_counter=QLabel();self.prefix_counter.setFixedHeight(11);self.prefix_counter.setAlignment(Qt.AlignmentFlag.AlignRight);self.prefix_counter.setStyleSheet('color:#98b4ca;font-size:8px;');self.prefix_counter.hide()
        self.serial_type=SerialChoice();self.min_digits=QSpinBox();self.max_digits=QSpinBox()
        for w in (self.min_digits,self.max_digits):w.setRange(1,50)
        self.width_mm_edit=QDoubleSpinBox();self.height_mm_edit=QDoubleSpinBox()
        for w in (self.width_mm_edit,self.height_mm_edit):w.setRange(20,300);w.setDecimals(1);w.setSuffix(' mm')
        self.dpi=QComboBox();self.dpi.addItems(['203','300','600']);self.dpi.setEditable(True)
        self.paper_dialog=QDialog(self);self.paper_dialog.setWindowTitle('Ukuran label dan resolusi');self.paper_dialog.setStyleSheet(self.paper_dialog.styleSheet()+CONTROL_STYLE);self.paper_dialog.resize(350,205)
        paper_layout=QFormLayout(self.paper_dialog)
        for title,widget in [('Lebar',self.width_mm_edit),('Tinggi',self.height_mm_edit),('DPI',self.dpi)]:paper_layout.addRow(title,widget)
        done=QPushButton('TERAPKAN');done.clicked.connect(lambda:self.paper_dialog.accept() if self.guard(self.apply_metadata) else None);paper_layout.addRow(done)
        self.meta_widgets={'name':self.name_edit,'gtin':self.gtin,'nie':self.nie,'prefix':self.prefix,'serial_type':self.serial_type,'min_digits':self.min_digits,'max_digits':self.max_digits,'width_mm':self.width_mm_edit,'height_mm':self.height_mm_edit,'dpi':self.dpi}
        digits=QWidget();dl=QHBoxLayout(digits);dl.setContentsMargins(0,0,0,0);dl.setSpacing(5)
        for caption,widget in [('Min',self.min_digits),('Max',self.max_digits)]:dl.addWidget(QLabel(caption));dl.addWidget(widget,1)
        fields=[('NAMA '+self.level+' *',self.name_edit),('NAMA PRODUK',self.product_name),('GTIN *',self.gtin),('NIE',self.nie),('PREFIX *',prefix_row),('TIPE SERIAL *',self.serial_type),('DIGIT SERIAL *',digits)]
        for label,widget in fields:
            widget.setFixedHeight(25);form.addRow(label,widget)
        self.product_name.editingFinished.connect(lambda:self.guard(self.apply_metadata) if not self.syncing else None)
        self.child=QComboBox();self.child.setFixedHeight(26)
        self.child_product=QComboBox();self.child_product.setFixedHeight(26);self.child_product.setToolTip('Pilih produk child dari database; relasi ID akan disimpan.')
        self.child_mode=SerialChoice({'BOX':'Lewat BOX','UNIT':'Produk child'}) if self.level=='CARTON' else None
        if self.child_mode:
            self.child_mode.setFixedHeight(25);form.addRow('SUMBER CHILD',self.child_mode)
            self.child_mode.currentTextChanged.connect(lambda:self.guard(self.apply_metadata) if not self.syncing else None)
        product_row=QWidget();pr=QHBoxLayout(product_row);pr.setContentsMargins(0,0,0,0);pr.setSpacing(4);pr.addWidget(self.child_product,1)
        self.product_source_button=QPushButton('…');self.product_source_button.setFixedSize(26,26);self.product_source_button.setToolTip('Pilih database, tabel, kolom ID dan nama produk child');self.product_source_button.clicked.connect(self.configure_product_source);pr.addWidget(self.product_source_button)
        self.child_stack=QStackedWidget();self.child_stack.setFixedHeight(26);self.child_stack.addWidget(self.child);self.child_stack.addWidget(product_row)
        self.child_caption=QLabel();form.addRow(self.child_caption,self.child_stack)
        targets=QWidget();tl=QHBoxLayout(targets);tl.setContentsMargins(0,0,0,0);tl.setSpacing(5)
        for caption,widget in [('Min',self.target_min),('Max',self.target_max)]:tl.addWidget(QLabel(caption));tl.addWidget(widget,1)
        form.addRow('TARGET QTY *',targets);self.print_mode.setFixedHeight(25);form.addRow('CETAK LABEL',self.print_mode)
        for widget in (self.target_min,self.target_max):widget.editingFinished.connect(lambda:self.guard(self.apply_metadata) if not self.syncing else None)
        self.print_mode.currentTextChanged.connect(lambda:self.guard(self.apply_metadata) if not self.syncing else None)
        self.child.currentIndexChanged.connect(lambda:self.guard(self.apply_metadata) if not self.syncing else None)
        self.child_product.currentIndexChanged.connect(lambda:self.guard(self.apply_metadata) if not self.syncing else None)
        self.info=QFrame();self.info.setObjectName('templateInfo');info_layout=QGridLayout(self.info);info_layout.setContentsMargins(8,5,8,5);info_layout.setVerticalSpacing(1)
        title=QLabel('INFORMASI TEMPLATE TERPILIH');title.setStyleSheet('font-size:9px;color:#dcefff;');info_layout.addWidget(title,0,0)
        self.enabled_check=QCheckBox('Aktif');self.enabled_check.setChecked(True);info_layout.addWidget(self.enabled_check,0,1,Qt.AlignmentFlag.AlignRight)
        self.info_values={}
        for i,(key,label) in enumerate([('child','Child terikat'),('target','Target agregasi'),('print','Cetak saat max')],1):
            caption=QLabel(label);caption.setStyleSheet('font-size:9px;');value=QLabel();value.setStyleSheet('font-size:9px;color:#e8f2fb;');info_layout.addWidget(caption,i,0);info_layout.addWidget(value,i,1);self.info_values[key]=value
        info_layout.setColumnStretch(1,1);layout.addWidget(self.info);layout.addStretch();self.tabs.addTab(panel,'Template')
        for widget in self.meta_widgets.values():
            if isinstance(widget,(QComboBox,SerialChoice)):widget.currentTextChanged.connect(lambda value:self.guard(self.apply_metadata) if not self.syncing else None)
            else:widget.editingFinished.connect(lambda:self.guard(self.apply_metadata) if not self.syncing else None)
        self.enabled_check.toggled.connect(lambda on:self.guard(self.apply_metadata) if not self.syncing else None)

    def populate_metadata(self):
        self.syncing=True
        try:
            for key,w in self.meta_widgets.items():
                if isinstance(w,(QComboBox,SerialChoice)):w.setCurrentText(str(self.document.get(key,'')))
                elif isinstance(w,(QSpinBox,QDoubleSpinBox)):w.setValue(self.document[key])
                else:w.setText(str(self.document.get(key,'')));w.setCursorPosition(0)
            self.product_name.setText(self.document['data'].get('product_name',''));self.product_name.setCursorPosition(0)
            self.target_min.setValue(self.document.get('aggregation_min',1));self.target_max.setValue(self.document.get('aggregation_max',{'BOX':50,'CARTON':12,'PALLET':16}[self.level]));self.print_mode.setCurrentText(self.document.get('print_mode','MANUAL'))
            if self.child_mode:self.child_mode.setCurrentText(self.document['child_level'])
            self.enabled_check.setChecked(self.document.get('active',True));self.refresh_sources();self.update_info()
        finally:self.syncing=False
    def apply_metadata(self):
        if self.syncing:return True
        doc=deepcopy(self.document)
        for key,w in self.meta_widgets.items():
            if isinstance(w,(QComboBox,SerialChoice)):val=w.currentText()
            elif isinstance(w,(QSpinBox,QDoubleSpinBox)):val=w.value()
            else:val=w.text().strip()
            doc[key]=int(val) if key in ('dpi','min_digits','max_digits') else val
        doc['data']['product_name']=self.product_name.text().strip();doc['data']['nie']=doc['nie']
        doc.pop('print_template_id',None);doc.pop('print_template_name',None)
        doc['active']=self.enabled_check.isChecked()
        doc['aggregation_min']=self.target_min.value();doc['aggregation_max']=self.target_max.value();doc['print_mode']=self.print_mode.currentText()
        doc['child_level']=self.child_mode.currentText() if self.child_mode else ('UNIT' if self.level=='BOX' else 'CARTON')
        if doc['child_level']=='UNIT':
            doc['child_product']=deepcopy(self.child_product.currentData());doc['child_template_id']=None
            doc['child_template_name']=doc['child_product']['name'] if doc['child_product'] else ''
        else:
            doc['child_product']=None;doc['child_template_id']=self.child.currentData()
            doc['child_template_name']=self.child.currentText() if doc['child_template_id'] else ''
        if doc['aggregation_max']!=self.document.get('aggregation_max') or doc['child_level']!=self.document['child_level']:
            doc['data']['quantity']=str(doc['aggregation_max'])+' '+doc['child_level']
        if 'gtin' in doc['data']:doc['data']['gtin']=doc['gtin']
        old_w=self.document['width_mm'];old_h=self.document['height_mm']
        if doc['width_mm']!=old_w or doc['height_mm']!=old_h:
            for e in doc['elements']:
                for key in ('x','w'):e[key]*=doc['width_mm']/old_w
                for key in ('y','h'):e[key]*=doc['height_mm']/old_h
        validate_document(doc);self.canvas.change(doc,'Ubah pengaturan template');return True
    def _make_properties(self):
        panel=QWidget();layout=QVBoxLayout(panel);layout.setContentsMargins(9,9,9,9);layout.setSpacing(7)
        self.selected_label=QLabel('Pilih objek pada canvas.');layout.addWidget(self.selected_label)
        self.object_text=QPlainTextEdit();self.object_text.setFixedHeight(62);self.object_text.setPlaceholderText('Teks atau {{nama_field}}');layout.addWidget(self.object_text)
        g=QGridLayout();self.object_dimensions={}
        for i,key in enumerate(('x','y','w','h')):
            spin=QDoubleSpinBox();spin.setRange(0 if key in ('x','y') else .1,300);spin.setDecimals(2);spin.setSuffix(' mm');spin.setFixedHeight(27)
            g.addWidget(QLabel({'x':'X','y':'Y','w':'Lebar','h':'Tinggi'}[key]),i//2,(i%2)*2);g.addWidget(spin,i//2,(i%2)*2+1);self.object_dimensions[key]=spin
        layout.addLayout(g)
        row=QHBoxLayout();self.font_size=QDoubleSpinBox();self.font_size.setRange(3,72);self.font_size.setSuffix(' pt');self.font_size.setDecimals(1);self.bold=QCheckBox('Bold');row.addWidget(QLabel('Font'));row.addWidget(self.font_size);row.addWidget(self.bold);layout.addLayout(row)
        row=QHBoxLayout();self.align=QComboBox();self.align.addItems(['left','center','right']);self.object_color=QLineEdit('#111820');row.addWidget(self.align);row.addWidget(self.object_color);layout.addLayout(row)
        row=QHBoxLayout();self.stroke=QDoubleSpinBox();self.stroke.setRange(.05,5);self.stroke.setDecimals(2);self.stroke.setSuffix(' mm');self.fill=QLineEdit('none');row.addWidget(QLabel('Garis'));row.addWidget(self.stroke);row.addWidget(self.fill);layout.addLayout(row)
        self.binding=QComboBox();self.binding.addItems(['Sisipkan field…']+list(FIELDS));self.binding.currentTextChanged.connect(self.insert_binding);layout.addWidget(self.binding)
        row=QHBoxLayout();self.locked=QCheckBox('Kunci posisi');self.human=QCheckBox('Teks barcode');row.addWidget(self.locked);row.addWidget(self.human);layout.addLayout(row)
        self.apply_object=QPushButton('TERAPKAN PROPERTI');self.apply_object.setFixedHeight(30);self.apply_object.clicked.connect(lambda:self.guard(self.apply_properties));layout.addWidget(self.apply_object)
        hint=QLabel('Geser objek dengan mouse. Tarik sudut kanan bawah untuk mengubah ukuran. Ctrl+klik untuk memilih beberapa objek.');hint.setWordWrap(True);layout.addWidget(hint);layout.addStretch()
        self.tabs.addTab(panel,'Objek')
    def insert_binding(self,value):
        if self.binding.currentIndex()>0:
            self.object_text.insertPlainText('{{'+value+'}}');self.binding.setCurrentIndex(0)
    def populate_properties(self):
        selected=self.canvas.selected_elements();self.apply_object.setEnabled(bool(selected))
        if not selected:self.selected_label.setText('Pilih objek pada canvas.');self._last_selection=set();return
        e=selected[-1];self.selected_label.setText(e['type'].upper()+f' • {len(selected)} objek dipilih')
        self.object_text.setPlainText(e.get('text',''))
        for key,w in self.object_dimensions.items():w.setValue(e[key])
        self.font_size.setValue(e.get('font',7));self.bold.setChecked(e.get('bold',False));self.object_color.setText(e.get('color','#111820'))
        self.fill.setText(e.get('fill','none'));self.stroke.setValue(e.get('stroke',.25));self.align.setCurrentText(e.get('align','left'));self.locked.setChecked(e.get('locked',False));self.human.setChecked(e.get('human',True))
        ids=set(self.canvas.selected_ids())
        if ids!=getattr(self,'_last_selection',set()):self.tabs.setCurrentIndex(1)
        self._last_selection=ids
    def apply_properties(self):
        selected=self.canvas.selected_elements()
        if not selected:return
        values={'text':self.object_text.toPlainText(),'font':self.font_size.value(),'bold':self.bold.isChecked(),'color':self.object_color.text().strip(),
                'fill':self.fill.text().strip(),'stroke':self.stroke.value(),'align':self.align.currentText(),'locked':self.locked.isChecked(),'human':self.human.isChecked()}
        if len(selected)==1:values.update({key:w.value() for key,w in self.object_dimensions.items()})
        doc=deepcopy(self.document);ids=set(self.canvas.selected_ids())
        for e in doc['elements']:
            if e['id'] in ids:e.update(values)
        check_renderable(doc);self.canvas.change(doc,'Ubah properti objek');self.message('Properti objek diperbarui.')
    def _make_data(self):
        panel=QWidget();layout=QVBoxLayout(panel);layout.setContentsMargins(8,8,8,8)
        self._data_dirty=False;self._filling_data=False
        self.schema_columns=[];self.schema_error='';self.schema_configured=False
        source_row=QHBoxLayout();self.source_status=QLabel('Pilih tabel database sumber.');self.source_status.setWordWrap(True);source_row.addWidget(self.source_status,1)
        source_button=QPushButton('Database');source_button.setFixedSize(74,27);source_button.clicked.connect(self.configure_source);source_row.addWidget(source_button);layout.addLayout(source_row)
        self.data_table=QTableWidget(0,2);self.data_table.setHorizontalHeaderLabels(['FIELD','NILAI']);self.data_table.verticalHeader().hide();self.data_table.setColumnWidth(0,98);self.data_table.horizontalHeader().setStretchLastSection(True);self.data_table.setWordWrap(False);self.data_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.data_table.itemChanged.connect(self.data_item_changed);layout.addWidget(self.data_table)
        controls=QHBoxLayout()
        for title,fn in [('Tambah field',self.add_data_field),('Hapus field',self.delete_data_field)]:
            control=QPushButton(title);control.setFixedHeight(27);control.clicked.connect(fn);controls.addWidget(control)
        layout.addLayout(controls)
        button=QPushButton('TERAPKAN DATA');button.setFixedHeight(30);button.clicked.connect(lambda:self.guard(self.apply_data));layout.addWidget(button)
        button=QPushButton('BUAT CONTOH SERIAL BERIKUTNYA');button.setFixedHeight(30);button.clicked.connect(lambda:self.guard(self.next_serial));layout.addWidget(button)
        self.tabs.addTab(panel,'Data')
    def read_schema(self):
        config=self.owner.store.get('template_data_source',{})
        self.schema_configured=bool(config.get('table'));self.schema_error=''
        try:self.schema_columns=[col['name'] for col in database_columns(self.owner.store)]
        except Exception as exc:self.schema_columns=[];self.schema_error=str(exc)
        self.source_status.setText(self.schema_error or ('Tabel: '+config['table'] if self.schema_configured else 'Pilih tabel database sumber.'))
        self.source_status.setToolTip(self.schema_error or ('Merah: field tidak ditemukan. Urutan mengikuti kolom database.' if self.schema_configured else 'Field belum diverifikasi karena tabel belum dipilih.'))
        self.source_status.setStyleSheet('font-size:9px;color:'+('#f1bd73' if self.schema_error or not self.schema_configured else '#9ed2bc')+';')

    def configure_source(self):
        dialog=DatabaseSourceDialog(self.owner.store,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            for editor in self.owner.editors.values():editor.refresh_field_schema()

    def refresh_field_schema(self):
        self.read_schema()
        # Preserve unsaved values when changing the source or refreshing its schema.
        rows=self.table_data() if self._data_dirty else dict(self.document['data'])
        self.populate_data(rows=rows,force=True)
        if self.table_data()!=self.document['data']:self._data_dirty=True

    def table_data(self):
        return {self.data_table.item(i,0).text().strip():self.data_table.item(i,1).text()
                for i in range(self.data_table.rowCount()) if self.data_table.item(i,0) and self.data_table.item(i,1)}

    def populate_data(self,rows=None,force=False):
        if self._data_dirty and not force:return
        self.read_schema();values=dict(self.document['data'] if rows is None else rows)
        for key in self.schema_columns:values.setdefault(key,'')
        order=[key for key in self.schema_columns if key in values]+[key for key in values if key not in self.schema_columns]
        self._filling_data=True;self.data_table.blockSignals(True);self.data_table.setRowCount(len(order))
        try:
            for i,key in enumerate(order):
                self.data_table.setItem(i,0,QTableWidgetItem(key));item=QTableWidgetItem(values[key]);item.setToolTip(values[key]);self.data_table.setItem(i,1,item)
                if key=='gtin':
                    self.data_table.item(i,0).setFlags(self.data_table.item(i,0).flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable);item.setToolTip('Ubah GTIN melalui tab Template.')
            self.mark_fields()
        finally:self.data_table.blockSignals(False);self._filling_data=False
        self.binding.blockSignals(True);self.binding.clear();self.binding.addItems(['Sisipkan field…']+list(dict.fromkeys(order+list(FIELDS))));self.binding.blockSignals(False)

    def mark_fields(self):
        was=self.data_table.blockSignals(True)
        try:
            for i in range(self.data_table.rowCount()):
                item=self.data_table.item(i,0)
                if item is None:continue
                key=item.text().strip();known=key in self.schema_columns
                state='pending' if self.schema_error or not self.schema_configured else ('matched' if known else 'missing')
                item.setData(Qt.ItemDataRole.UserRole,state)
                item.setForeground(QColor({'missing':'#ff8e9c','matched':'#ccece7','pending':'#c6d6e4'}[state]))
                item.setBackground(QColor('#452c3d' if state=='missing' else '#04283f'))
                item.setToolTip({'missing':'Tidak ditemukan pada kolom tabel database sumber.','matched':'Sesuai kolom database • urutan '+str(self.schema_columns.index(key)+1 if known else 0),'pending':self.schema_error or 'Belum diverifikasi: pilih tabel database sumber.'}[state])
                if state=='missing':item.setIcon(icon('field_error',14))
                else:
                    from PySide6.QtGui import QIcon
                    item.setIcon(QIcon())
        finally:self.data_table.blockSignals(was)

    def data_item_changed(self,item):
        if self._filling_data:return
        self._data_dirty=True;self.read_schema();self.mark_fields()

    def add_data_field(self):
        keys=set(self.table_data());number=1
        while 'field_'+str(number) in keys:number+=1
        i=self.data_table.rowCount();self.data_table.insertRow(i);self.data_table.setItem(i,0,QTableWidgetItem('field_'+str(number)));self.data_table.setItem(i,1,QTableWidgetItem('Nilai baru'));self.data_table.setCurrentCell(i,0)
        self._data_dirty=True;self.mark_fields()
    def delete_data_field(self):
        i=self.data_table.currentRow()
        if i>=0:self.data_table.removeRow(i);self._data_dirty=True
    def apply_data(self):
        keys=[self.data_table.item(i,0).text().strip() for i in range(self.data_table.rowCount())]
        if len(set(keys))!=len(keys):raise ValueError('Nama field tidak boleh ganda.')
        doc=deepcopy(self.document);doc['data']=self.table_data()
        doc['data']['gtin']=doc['gtin']
        if 'nie' in doc['data']:doc['nie']=doc['data']['nie']
        check_renderable(doc);self._data_dirty=False;self.canvas.change(doc,'Ubah data label');self.populate_data();self.message('Data label diperbarui.')
    def next_serial(self):
        doc=deepcopy(self.document);lo=int(doc['min_digits']);hi=int(doc['max_digits'])
        if doc['serial_type']=='UNIX':serial=str(int(datetime.now().timestamp()))
        else:
            current=doc['data'].get('serial','0');serial=str(int(current)+1) if current.isdigit() else '1'
            if len(serial)>hi:serial='1'
        if len(serial)>hi:raise ValueError('Max digit terlalu kecil untuk nilai UNIX saat ini.')
        doc['data']['serial']=serial.zfill(lo);self.canvas.change(doc,'Buat contoh serial');self.populate_data()
    def _make_toolbar(self):
        bar=QWidget(self);bar.setObjectName('editorToolbar');bar.setGeometry(398,35,658,30);bar.setStyleSheet('QWidget#editorToolbar {background:#043452;border:1px solid #154f70;border-radius:4px;}')
        layout=QHBoxLayout(bar);layout.setContentsMargins(3,0,3,0);layout.setSpacing(1)
        self.undo_button=self.tool_button(bar,'undo','Undo • Ctrl+Z',self.canvas.undo.undo,26);self.redo_button=self.tool_button(bar,'redo','Redo • Ctrl+Y',self.canvas.undo.redo,26);layout.addWidget(self.undo_button);layout.addWidget(self.redo_button)
        for name,label,fn in [('cut','Potong • Ctrl+X',self.canvas.cut),('copy','Salin • Ctrl+C',self.canvas.copy),('paste','Tempel • Ctrl+V',self.canvas.paste),('duplicate','Duplikasi • Ctrl+D',self.canvas.duplicate),('delete','Hapus objek • Delete',self.canvas.delete)]:layout.addWidget(self.tool_button(bar,name,label,fn,26))
        for name,label,options in [('align','Ratakan objek',[(m,lambda mode=m:self.canvas.align(mode)) for m in ('left','center','right','top','middle','bottom')]),('distribute','Samakan jarak',[('Horizontal',lambda:self.canvas.distribute(True)),('Vertikal',lambda:self.canvas.distribute(False))]),('layer','Urutan lapisan',[('Bawa ke depan',lambda:self.canvas.reorder(True)),('Kirim ke belakang',lambda:self.canvas.reorder(False))])]:
            b=QToolButton(bar);b.setIcon(icon(name));b.setToolTip(label);b.setFixedSize(29,28);b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup);menu=QMenu(b)
            for title,fn in options:menu.addAction(title).triggered.connect(lambda checked=False,f=fn:self.guard(f))
            b.setMenu(menu);layout.addWidget(b)
        self.grid_button=self.tool_button(bar,'grid','Tampilkan grid',self.set_grid,26);self.grid_button.setCheckable(True);self.grid_button.setChecked(True);layout.addWidget(self.grid_button)
        self.snap_button=self.tool_button(bar,'snap','Snap 0,5 mm',self.set_snap,26);self.snap_button.setCheckable(True);self.snap_button.setChecked(True);layout.addWidget(self.snap_button)
        self.paper_button=self.tool_button(bar,'paper','Ukuran label / DPI',self.paper_dialog.exec,26);layout.addWidget(self.paper_button)
        for name,title,index in [('save','Form template',0),('settings','Properti objek',1),('dynamic','Data dinamis',2)]:layout.addWidget(self.tool_button(bar,name,title,lambda i=index:self.tabs.setCurrentIndex(i),26))
        layout.addStretch()
        for name,direction in [('zoom_out',-1),('zoom_in',1)]:layout.addWidget(self.tool_button(bar,name,'Perkecil' if direction<0 else 'Perbesar',lambda d=direction:self.step_zoom(d),24))
        self.zoom=QComboBox();self.zoom.addItems(['Fit','50%','75%','100%','125%','150%','200%','300%']);self.zoom.setFixedSize(70,25);self.zoom.currentTextChanged.connect(self.canvas.view.set_zoom);layout.addWidget(self.zoom)

    def set_grid(self):self.canvas.grid=self.grid_button.isChecked();self.canvas.view.viewport().update()
    def set_snap(self):self.canvas.snap=self.snap_button.isChecked()
    def _make_tools(self):
        title=QLabel('TOOLBOX',self);title.setGeometry(399,70,78,16);title.setStyleSheet('font-size:8px;color:#acc2d7;')
        tools=[('text','Text','text','Teks baru'),('barcode','Barcode 1D','barcode','{{serial}}'),('datamatrix','Barcode 2D','datamatrix','{{serial}}'),('qr','QR Code','qr','{{serial}}'),('rectangle','Rectangle','rectangle',''),('line','Line','line',''),('image','Image / Logo','image',''),('date','Date','text','{{mfg_date}}'),('serial','Serial (SN)','text','{{serial}}'),('batch','Batch (LOT)','text','{{batch}}'),('dynamic','Dynamic Field','text','{{product_name}}')]
        for i,(ico,label,kind,value) in enumerate(tools):
            b=QToolButton(self);b.setObjectName('tool_'+ico);b.setGeometry(398,89+i*34,83,32);b.setIcon(icon(ico));b.setIconSize(QSize(16,16));b.setText(label);b.setToolTip(label);b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            b.setStyleSheet('QToolButton {font-size:8px;padding:2px;background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #063854,stop:1 #032b43);border:1px solid #175270;border-radius:3px;} QToolButton:hover {background:#075680;border-color:#3396cd;}')
            fn=self.add_image if kind=='image' else lambda k=kind,t=value:self.canvas.add(k,text=t)
            b.clicked.connect(lambda checked=False,f=fn:self.guard(f))
        b=QToolButton(self);b.setGeometry(398,467,79,31);b.setText('Simbol');b.setIcon(icon('box_level'));b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon);b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup);menu=QMenu(b)
        for name,label in [('dry','Keep dry'),('stack','Do not stack'),('up','This side up'),('care','Handle with care'),('weight','Berat'),('package','Kemasan')]:menu.addAction(label).triggered.connect(lambda checked=False,n=name:self.guard(lambda:self.canvas.add('symbol',symbol=n)))
        b.setMenu(menu)
        back=QToolButton(self);back.setGeometry(325,5,30,28);back.setIcon(icon('save'));back.setToolTip('Kembali ke form template');back.clicked.connect(lambda:self.tabs.setCurrentIndex(0))

    def add_image(self,path=None):
        if not path:path,_=QFileDialog.getOpenFileName(self,'Pilih gambar / logo','','Gambar (*.png *.jpg *.jpeg *.bmp *.webp)')
        if not path:return False
        reader=QImageReader(str(path));size=reader.size()
        if size.width()*size.height()>16_000_000:raise ValueError('Gambar maksimal 16 megapiksel.')
        image=reader.read()
        if image.isNull():raise ValueError('Gambar tidak dapat dibuka.')
        image=image.scaled(1200,1200,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
        raw=QByteArray();buffer=QBuffer(raw);buffer.open(QIODevice.OpenModeFlag.WriteOnly);image.save(buffer,'PNG');buffer.close()
        self.canvas.add('image',image=base64.b64encode(bytes(raw)).decode());return True
    def _make_actions(self):
        self.new_button=self.action_button('template_new','BARU',self.new_template,18,494)
        self.save_button=self.action_button('template_save','SIMPAN TEMPLATE',self.save,192,494,color='green')
        self.action_button('template_duplicate','DUPLIKASI',self.duplicate_template,18,536)
        self.action_button('template_delete','HAPUS',self.delete_template,192,536,color='red')
        self.action_button('template_default','SET DEFAULT',self.make_default,18,578,color='gold')
        self.action_button('template_preview','PREVIEW',self.preview,192,578)
        x=398
        for i,(name,label,callback,color) in enumerate([('preview','PREVIEW PRINT',self.preview,'blue'),('print','TEST PRINT',lambda:self.print_current(),'blue'),('import','IMPORT TEMPLATE',self.owner.import_template,'blue'),('export','EXPORT TEMPLATE',self.export_template,'blue'),('reset','RESET CANVAS',self.reset_canvas,'gold'),('publish','PUBLISH TEMPLATE',self.publish,'green')]):
            width=(99,85,115,116,105,123)[i]
            b=self.action_button('template_'+name,label,callback,x,559,width,color,37);x+=width+3
            if name=='print':b.setIcon(icon('printer'));b.setIconSize(QSize(16,16))
            if name=='reset':b.setIcon(icon('undo'));b.setIconSize(QSize(16,16))

    def document_changed(self):
        if not hasattr(self,'tabs'):return
        self.populate_metadata();self.populate_data();self.owner.schedule_refresh();self.owner.update()
    def refresh_list(self,focus=False):
        all_rows=self.repo.list(self.level);self.all_rows=all_rows
        if focus:
            self.list_page=next((i//self.PAGE_SIZE for i,row in enumerate(all_rows) if row['id']==self.identifier),0)
        last=max(0,(len(all_rows)-1)//self.PAGE_SIZE);self.list_page=max(0,min(last,self.list_page))
        start=self.list_page*self.PAGE_SIZE;self.rows=all_rows[start:start+self.PAGE_SIZE]
        self.list_table.blockSignals(True);self.list_table.setRowCount(len(self.rows))
        for i,row in enumerate(self.rows):
            doc=json.loads(row['document']);active=doc.get('active',True)
            vals=[row['name'],doc['prefix'],doc['serial_type'],str(doc['min_digits'])+' – '+str(doc['max_digits']),doc.get('child_template_name') or doc['child_level'],('AKTIF' if active else 'NONAKTIF')+(' ★' if row['is_default'] else '')]
            for j,value in enumerate(vals):
                item=QTableWidgetItem(value);item.setToolTip(value);self.list_table.setItem(i,j,item)
                if j==5:item.setForeground(QColor('#92eb3f' if active else '#f55856'))
            if row['id']==self.identifier:self.list_table.selectRow(i)
        self.list_table.blockSignals(False)
        self.page_info.setText(f'Menampilkan {start+1 if all_rows else 0}–{start+len(self.rows)} dari {len(all_rows)} template')
        self.page_number.setText(str(self.list_page+1));self.previous_button.setEnabled(self.list_page>0);self.next_button.setEnabled(self.list_page<last)
        self.refresh_sources()
        self.refresh_previews(all_rows,focus=focus)

    def refresh_previews(self,rows=None,focus=False):
        """Show saved snapshots only; paging is independent of the master table."""
        rows=self.repo.list(self.level) if rows is None else rows
        if focus:
            self.preview_page=next((i//self.PREVIEW_PAGE_SIZE for i,row in enumerate(rows) if row['id']==self.identifier),0)
        last=max(0,(len(rows)-1)//self.PREVIEW_PAGE_SIZE)
        self.preview_page=max(0,min(last,self.preview_page));start=self.preview_page*self.PREVIEW_PAGE_SIZE
        visible=rows[start:start+self.PREVIEW_PAGE_SIZE];self.thumbnails=[];cache={}
        for i,thumb in enumerate(self._thumbnail_slots):
            if i>=len(visible):
                thumb.hide();thumb.identifier=None;thumb.document=None;thumb.image=None;thumb.current=False
                continue
            row=visible[i];identifier=row['id'];payload=row['document'];cached=self.preview_cache.get(identifier)
            doc=validate_document(json.loads(payload))
            if cached is not None and cached[0]==payload:image=cached[1]
            else:
                try:image=render_image(doc,100)
                except Exception:image=None
            cache[identifier]=(payload,image);thumb.identifier=identifier;thumb.document=doc;thumb.image=image
            thumb.current=identifier==self.identifier;thumb.setToolTip('Buka template tersimpan: '+doc['name'])
            thumb.setAccessibleName('Buka '+self.level+' '+doc['name']);thumb.show();thumb.update();self.thumbnails.append(thumb)
        self.preview_cache=cache;self.preview_empty.setVisible(not rows)
        self.preview_page_info.setText(f'{start+1 if rows else 0}–{start+len(visible)} dari {len(rows)} template {self.level} tersimpan')
        self.preview_number.setText(f'{self.preview_page+1} / {last+1}')
        for control in (self.preview_previous,self.preview_number,self.preview_next):control.setVisible(last>0)
        self.preview_previous.setEnabled(self.preview_page>0);self.preview_next.setEnabled(self.preview_page<last)

    def turn_preview_page(self,direction):
        self.preview_page+=direction;self.refresh_previews()

    def choose_preview(self,identifier):
        if identifier and identifier!=self.identifier and self.confirm_discard():self.load_template(identifier)

    def confirm_discard(self):
        if not self.dirty:return True
        answer=QMessageBox.question(self,'Perubahan belum disimpan','Simpan perubahan template sebelum melanjutkan?',QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel)
        if answer==QMessageBox.StandardButton.Cancel:return False
        return bool(self.guard(self.save)) if answer==QMessageBox.StandardButton.Save else True
    def choose_row(self,row,column):
        if 0<=row<len(self.rows) and self.rows[row]['id']!=self.identifier:
            identifier=self.rows[row]['id']
            if self.confirm_discard():self.load_template(identifier)
            else:self.refresh_list()
    def load_template(self,identifier):
        self._data_dirty=False
        row=self.repo.get(identifier)
        if row['level']!=self.level:raise ValueError('Template berasal dari level lain.')
        self.identifier=identifier;self.canvas.set_document(row['document']);self.populate_metadata();self.populate_data();self.refresh_list(focus=True);self.tabs.setCurrentIndex(0);self.message('Template dimuat.')
    def new_template(self):
        if not self.confirm_discard():return False
        self._data_dirty=False
        doc=default_document(self.level)
        cfg=self.owner.store.get('configuration',{})
        if cfg:
            from datetime import datetime
            doc['data']['mfg_date']=datetime.strptime(cfg['mfd'],'%Y-%m-%d').strftime('%d/%m/%Y')
            doc['dpi']=cfg['printers'][self.level]['dpi']
        doc['name']='TEMPLATE '+self.level+' BARU';self.identifier=None;self.canvas.set_document(doc);self.tabs.setCurrentIndex(0);self.refresh_list();self.message('Template baru siap diedit; tekan Simpan.');return True
    def configure_product_source(self):
        dialog=DatabaseSourceDialog(self.owner.store,self,product_mode=True)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            for editor in self.owner.editors.values():editor.refresh_sources()

    def refresh_sources(self):
        was=self.syncing;self.syncing=True
        try:
            child_id=self.document.get('child_template_id');child_level='BOX' if self.level=='CARTON' else 'CARTON'
            self.child.clear();self.child.addItem('Pilih template '+child_level+'…',None)
            for row in self.repo.list(child_level):self.child.addItem(row['name'],row['id'])
            if child_id and self.child.findData(child_id)<0:
                self.child.addItem((self.document.get('child_template_name') or child_id)+' [tidak tersedia]',child_id)
            self.child.setCurrentIndex(max(0,self.child.findData(child_id)))
            selected=self.document.get('child_product');self.child_product.clear();self.child_product.addItem('Pilih produk child…',None)
            self.product_error=''
            try:products=product_choices(self.owner.store)
            except Exception as exc:products=[];self.product_error=str(exc)
            selected_index=0;name_counts=Counter(p['name'] for p in products)
            for product in products:
                label=product['name']
                if name_counts[product['name']]>1:label+=' • '+str(product['id'])
                self.child_product.addItem(label,product)
                if selected and product['id']==selected['id'] and product['source']==selected['source']:selected_index=self.child_product.count()-1
            if selected and not selected_index:
                self.child_product.addItem(selected['name']+' [sumber tersimpan]',selected);selected_index=self.child_product.count()-1
            self.child_product.setCurrentIndex(selected_index)
            self.child_product.setToolTip(self.product_error or 'Pilih produk child dari database. Gunakan tombol … untuk mengatur sumber.')
            unit=self.document['child_level']=='UNIT';self.child_stack.setCurrentIndex(1 if unit else 0)
            self.child_caption.setText('LINK CHILD (UNIT)' if unit else 'LINK CHILD ('+child_level+')')
        finally:self.syncing=was

    def validate_child_binding(self):
        doc=self.document
        if doc['child_level']=='UNIT':
            selected=doc.get('child_product')
            if not selected:raise ValueError('Pilih produk child dari database sebelum menyimpan template.')
            choices=product_choices(self.owner.store,selected['source'])
            if not any(p['id']==selected['id'] for p in choices):raise ValueError('Produk child sudah tidak tersedia pada sumber database.')
        elif doc.get('child_template_id'):
            child=self.repo.get(doc['child_template_id'])
            if child['level']!=doc['child_level']:raise ValueError('Level template child tidak sesuai.')

    def update_info(self):
        from PySide6.QtGui import QFontMetrics
        d=self.document;self.prefix_counter.setText(str(len(d['prefix']))+' / 20')
        child=(d.get('child_product') or {}).get('name') if d['child_level']=='UNIT' else d.get('child_template_name')
        values={'child':child or 'Belum dipilih','target':f"{d.get('aggregation_min',1)} – {d.get('aggregation_max',1)} {d['child_level']}",'print':'AUTO PRINT' if d.get('print_mode')=='AUTO' else 'MANUAL PRINT'}
        for key,value in values.items():
            widget=self.info_values[key];widget.setToolTip(str(value));widget.setText(QFontMetrics(ui_font(9)).elidedText(': '+str(value),Qt.TextElideMode.ElideRight,166))
    def turn_page(self,direction):self.list_page+=direction;self.refresh_list()
    def toggle_active(self,row):
        if not 0<=row<len(self.rows):return
        identifier=self.rows[row]['id'];doc=deepcopy(self.document) if identifier==self.identifier else self.repo.get(identifier)['document']
        doc['active']=not doc.get('active',True)
        if identifier==self.identifier:self.canvas.change(doc,'Ubah status aktif');self.save()
        else:self.repo.save(doc,identifier);self.refresh_list();self.owner.schedule_refresh()
    def list_menu(self,position):
        row=self.list_table.rowAt(position.y())
        if row<0:return
        menu=QMenu(self);action=menu.addAction('Aktifkan / nonaktifkan template');action.triggered.connect(lambda:self.guard(lambda:self.toggle_active(row)));menu.exec(self.list_table.viewport().mapToGlobal(position))
    def step_zoom(self,direction):
        modes=['50%','75%','100%','125%','150%','200%','300%'];current=self.zoom.currentText();index=modes.index(current) if current in modes else 2
        self.zoom.setCurrentText(modes[max(0,min(len(modes)-1,index+direction))])
    def save(self):
        if self._data_dirty:self.apply_data()
        self.apply_metadata();self.validate_child_binding();doc=check_renderable(self.document);self.identifier=self.repo.save(doc,self.identifier);self.canvas.undo.setClean();self.refresh_list(focus=True);self.owner.schedule_refresh();self.message('Template tersimpan di database.');return True
    def duplicate_template(self):
        if self._data_dirty:self.apply_data()
        self.apply_metadata();check_renderable(self.document);identifier=self.repo.duplicate(self.document);self.load_template(identifier);self.message('Salinan template berhasil dibuat.');return True
    def delete_template(self,confirmed=False):
        if not self.identifier:self.message('Template baru belum tersimpan.');return False
        if not confirmed and QMessageBox.question(self,'Hapus template','Hapus template "'+self.document['name']+'" dari daftar?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return False
        self.repo.delete(self.identifier);rows=self.repo.list(self.level)
        if rows:self.load_template(rows[0]['id'])
        else:self._data_dirty=False;self.identifier=None;self.canvas.set_document(default_document(self.level));self.refresh_list()
        self.owner.schedule_refresh();self.message('Template dihapus dari daftar.');return True
    def make_default(self):
        self.save();self.repo.set_default(self.identifier);self.refresh_list();self.owner.schedule_refresh();self.message('Default untuk '+self.level+' diperbarui.');return True
    def publish(self):
        if self._data_dirty:self.apply_data()
        self.apply_metadata();self.validate_child_binding();doc=check_renderable(self.document);self.identifier=self.repo.publish(doc,self.identifier);self.canvas.undo.setClean();self.refresh_list();self.owner.schedule_refresh();revision=self.repo.get(self.identifier)['revision'];self.message(f'Template dipublikasikan lokal • revisi {revision}.');return True
    def reset_canvas(self,confirmed=False):
        if not confirmed and QMessageBox.question(self,'Reset canvas','Kembalikan objek canvas ke desain awal '+self.level+'? Perubahan ini dapat di-undo.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return False
        doc=deepcopy(self.document);starter=default_document(self.level);sx=doc['width_mm']/starter['width_mm'];sy=doc['height_mm']/starter['height_mm']
        doc['elements']=starter['elements']
        for e in doc['elements']:
            for key in ('x','w'):e[key]*=sx
            for key in ('y','h'):e[key]*=sy
        self.canvas.change(doc,'Reset canvas');self.message('Canvas dikembalikan; Undo tersedia.');return True
    def print_current(self):
        if self._data_dirty:self.apply_data()
        self.apply_metadata();return self.owner.print_document(self.document,self.identifier)
    def preview(self):
        if self._data_dirty:self.apply_data()
        self.apply_metadata();doc=check_renderable(self.document);self.owner.show_preview(doc,self.identifier);return True
    def export_template(self,path=None):
        if self._data_dirty:self.apply_data()
        self.apply_metadata();doc=check_renderable(self.document)
        selected='Template JSON (*.json)'
        if not path:path,selected=QFileDialog.getSaveFileName(self,'Ekspor template',self.level.lower()+'_template.json','Template JSON (*.json);;Label PDF (*.pdf);;Label PNG (*.png)')
        if not path:return False
        path=Path(path);suffix=path.suffix.lower()
        if suffix not in ('.json','.pdf','.png'):
            suffix='.pdf' if 'PDF' in selected else '.png' if 'PNG' in selected else '.json';path=path.with_suffix(suffix)
        if suffix=='.pdf':export_pdf(doc,path)
        elif suffix=='.png':
            if not render_image(doc).save(str(path),'PNG'):raise ValueError('Gambar gagal disimpan.')
        else:
            from PySide6.QtCore import QSaveFile
            out=QSaveFile(str(path))
            if not out.open(QIODevice.OpenModeFlag.WriteOnly):raise ValueError(out.errorString())
            payload=json.dumps({'format':'AGREGASI_LABEL_TEMPLATE','version':1,'document':doc},ensure_ascii=False,indent=2).encode()
            if out.write(payload)!=len(payload) or not out.commit():raise ValueError('Template gagal disimpan.')
        self.repo.record(self.identifier,self.level,'EKSPOR',path.name);self.owner.schedule_refresh();self.message('Ekspor selesai: '+path.name);return str(path)
