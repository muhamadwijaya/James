"""Revision screen: searches, trace hierarchy and audited corrective actions."""
from .sidebar_layout import fixed_sidebar, SIDEBAR
import json
from datetime import datetime
from io import BytesIO
from pathlib import Path
from PySide6.QtCore import Qt,QDate,QRectF
from PySide6.QtGui import QColor,QIcon,QPainter,QPen,QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QDateEdit,QLabel,QLineEdit,QPushButton,QStyle,QStyledItemDelegate,QVBoxLayout,QHBoxLayout,QFormLayout,QComboBox,QPlainTextEdit,QTableWidget,QTableWidgetItem,QTreeWidget,QTreeWidgetItem,QTabWidget,QHeaderView,QAbstractItemView)
from .pages import PageBase
from .dashboard import BASE,WHITE,MUTED,GREEN,RED,YELLOW,BLUE,num
from .revision_model import RevisionRepository,LEVELS,STATES
from .upload_page import SendPage,stamp
from .ui_dialogs import AppDialog,MessageBox,FileDialog
from .settings_model import VERSION
COLORS={'UNIT':'#15813b','BOX':'#067cb5','CARTON':'#69429e','PALLET':'#9c720d','VALID':GREEN,'REJECT':RED,'DUPLIKAT':YELLOW,'PENDING':BLUE}
PRINT_STATES={'SENT':'TERCETAK','WAITING':'BELUM DICETAK','PENDING':'ANTRE CETAK','SENDING':'SEDANG DICETAK','ERROR':'CETAK GAGAL'}
CHILD_LEVEL={'BOX':'UNIT','CARTON':'BOX','PALLET':'CARTON'}


class ChipDelegate(QStyledItemDelegate):
    """Rounded level pills and status marks, matching the revision reference."""
    GLYPH={'VALID':'✓','REJECT':'!','DUPLIKAT':'×','PENDING':'•','SCAN':'✓'}
    def __init__(self,parent=None,pill=(),mark=()):
        super().__init__(parent);self.pill=set(pill);self.mark=set(mark)
    def paint(self,painter,option,index):
        color=index.data(Qt.ItemDataRole.UserRole);column=index.column()
        if not color or column not in self.pill|self.mark:return super().paint(painter,option,index)
        text=str(index.data(Qt.ItemDataRole.DisplayRole) or '')
        painter.save();painter.setRenderHint(QPainter.RenderHint.Antialiasing,True)
        if option.state & QStyle.StateFlag.State_Selected:painter.fillRect(option.rect,QColor('#0a6390'))
        rect=QRectF(option.rect);font=painter.font();font.setBold(True);font.setPixelSize(max(8,min(11,int(rect.height()*0.42))));painter.setFont(font)
        if column in self.pill:
            width=min(rect.width()-8,max(46,painter.fontMetrics().horizontalAdvance(text)+18))
            chip=QRectF(rect.x()+4,rect.center().y()-9,width,18)
            painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor(color));painter.drawRoundedRect(chip,9,9)
            painter.setPen(QColor('#f4fbff'));painter.drawText(chip,Qt.AlignmentFlag.AlignCenter,text)
        else:
            size=min(14,rect.height()-6);mark=QRectF(rect.x()+5,rect.center().y()-size/2,size,size)
            painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor(color));painter.drawEllipse(mark)
            painter.setPen(QColor('#02243a'));painter.drawText(mark,Qt.AlignmentFlag.AlignCenter,self.GLYPH.get(text,'•'))
            painter.setPen(QColor(color));painter.drawText(QRectF(rect.x()+size+10,rect.y(),rect.width()-size-12,rect.height()),int(Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft),text)
        painter.restore()

class RevisionPage(PageBase):
    button=SendPage.button
    ring=SendPage.ring
    def __init__(self,store):
        super().__init__(store,'revision','Revisi','REVISION DATA & PENELUSURAN AGREGASI','revision')
        self.repo=RevisionRepository(store);self.buttons={};self.key=None;self.item=None;self.page_index=0;self.rows=[];self.visible=[];self.barcode_cache={};self.message='Pastikan data yang dipilih sudah diverifikasi sebelum melakukan revision.';self.runtime=None
        self.serial=self.field(29,105,250,29,placeholder='Masukkan serial unit');self.box=self.field(300,105,250,29,placeholder='Masukkan kode box')
        self.carton=self.field(569,105,250,29,placeholder='Masukkan kode carton');self.pallet=self.field(839,105,241,29,placeholder='Masukkan kode pallet')
        for edit in (self.serial,self.box,self.carton,self.pallet):edit.addAction(QIcon(str(BASE/'assets/svg/barcode.svg')),QLineEdit.ActionPosition.TrailingPosition)
        self.batch=self.combo(29,158,250,29,['Pilih batch']);self.status_filter=self.combo(569,158,250,29,['Semua Status',*STATES])
        self.date_active=False
        self.date_start=QDateEdit(QDate.currentDate(),self);self.date_end=QDateEdit(QDate.currentDate(),self)
        for widget,x,w in ((self.date_start,300,110),(self.date_end,429,110)):
            widget.setGeometry(x,158,w,29);widget.setCalendarPopup(True);widget.setDisplayFormat('dd/MM/yyyy');widget.setStyleSheet('QDateEdit{color:#eaf4ff;background:#04283f;border:1px solid #3f6780;border-radius:3px;padding:3px;font-size:11px;} QDateEdit:disabled{color:#6f8ea3;}')
            widget.dateChanged.connect(self.date_picked)
        self.date_toggle=self.button('date_filter',541,158,28,29,'','clock',flat=True)
        self.date_toggle.setToolTip('Aktifkan / matikan filter rentang tanggal')
        self.search_button=self.button('revision_search',839,147,241,40,'CARI DATA','search')
        self.grid=self.table(28,237,674,267,['WAKTU ↕','LEVEL ↕','KODE ↕','PARENT ↕','STATUS ↕','USER ↕'],[142,63,158,133,80,90]);self.grid.verticalHeader().setDefaultSectionSize(29);self.grid.horizontalHeader().setFixedHeight(30)
        self.grid.itemSelectionChanged.connect(self.selected);self.grid.horizontalHeader().sectionClicked.connect(self.sort_by);self.sort_column=0;self.sort_reverse=True
        self.grid.setItemDelegate(ChipDelegate(self.grid,pill=(1,),mark=(4,)))
        self.button('export_search',670,203,32,26,'↓',None)
        self.button('first',150,521,32,29,'«',None,flat=True);self.button('prev',185,521,35,29,'‹',None,flat=True)
        self.button('next',480,521,35,29,'›',None,flat=True);self.button('last',516,521,32,29,'»',None,flat=True)
        self.page_buttons=[]
        for i in range(7):self.page_buttons.append(self.button('page_'+str(i),225+i*36,521,32,29,str(i+1),None,flat=True))
        self.button('details',748,531,331,28,'LIHAT SEMUA DETAIL',None)
        for name,x,y,label,icon,color in [('rev_reprint',29,808,'REPRINT LABEL','printer','blue'),('rev_unlock',151,808,'UNLOCK DATA','shield','blue'),('rev_reject',273,808,'TANDAI REJECT','reject','red'),('rev_valid',29,879,'PULIHKAN VALID','check_circle','green'),('rev_move',151,879,'PINDAH BOX/CARTON','send','blue'),('rev_update',273,879,'UPDATE STATUS','sync','gold')]:
            self.button(name,x,y,113,62,label,icon,color,stacked=True)
        self.logs_grid=self.table(424,808,657,148,['WAKTU','AKTIVITAS','LEVEL','KODE','DARI STATUS','KE STATUS','USER','CATATAN'],[116,104,60,112,70,70,56,128]);self.logs_grid.verticalHeader().setDefaultSectionSize(23);self.logs_grid.horizontalHeader().setFixedHeight(29)
        self.logs_grid.setItemDelegate(ChipDelegate(self.logs_grid,pill=(2,4,5)))
        self.logs_grid.setStyleSheet(self.logs_grid.styleSheet().replace('font-size:11px','font-size:9px').replace('font-size:10px','font-size:8px').replace('padding:4px','padding:2px'))
        self.logs_grid.cellDoubleClicked.connect(self.log_detail)
        self.button('export_logs',1047,773,33,25,'↓',None);self.button('all_logs',915,958,165,24,'LIHAT SEMUA LOG  ›',None,flat=True)
        self.action.connect(self.local_action)
        for edit in (self.serial,self.box,self.carton,self.pallet):edit.returnPressed.connect(self.search_now)
        self.batch.currentTextChanged.connect(self.search_now);self.status_filter.currentTextChanged.connect(self.search_now)
        self.refresh()
    def attach(self,runtime,aggregation,templates):self.runtime=runtime;self.aggregation=aggregation;self.templates=templates;runtime.changed.connect(self.update);self.refresh()
    def date_picked(self,*_):
        """Touching a date turns the range filter on; the clock button switches it off."""
        self.date_active=True;self.search_now()
    def toggle_dates(self,value=None):
        self.date_active=bool(value) if value is not None else not self.date_active
        self.message=('Filter tanggal aktif: '+self.date_start.date().toString('dd/MM/yyyy')+' – '+self.date_end.date().toString('dd/MM/yyyy')) if self.date_active else 'Filter tanggal dimatikan; seluruh tanggal ditampilkan.'
        self.search_now()
    def search_now(self,*args):self.page_index=0;self.refresh()
    def sort_by(self,column):self.sort_reverse=not self.sort_reverse if self.sort_column==column else False;self.sort_column=column;self.page_index=0;self.refresh()
    def refresh(self):
        oldbatch=self.batch.currentText();batches=['Pilih batch']+sorted({r['batch'] for r in self.repo.rows()})
        if batches!=[self.batch.itemText(i) for i in range(self.batch.count())]:
            self.batch.blockSignals(True);self.batch.clear();self.batch.addItems(batches);self.batch.setCurrentText(oldbatch if oldbatch in batches else batches[0]);self.batch.blockSignals(False)
        try:self.rows=self.repo.search(dict(zip(LEVELS,(self.serial.text(),self.box.text(),self.carton.text(),self.pallet.text()))),'' if self.batch.currentIndex()==0 else self.batch.currentText(),self.date_start.date().toString('yyyy-MM-dd') if self.date_active else '',self.date_end.date().toString('yyyy-MM-dd') if self.date_active else '',self.status_filter.currentText() if self.status_filter.currentIndex() else '')
        except ValueError as exc:self.message=str(exc);self.update();return
        key=('ts','level','code','parent','status','operator')[self.sort_column];self.rows.sort(key=lambda r:str(r[key]),reverse=self.sort_reverse)
        self.page_count=max(1,(len(self.rows)+7)//8);self.page_index=min(self.page_index,self.page_count-1);self.visible=self.rows[self.page_index*8:(self.page_index+1)*8]
        self.grid.blockSignals(True);self.grid.setRowCount(len(self.visible))
        for i,r in enumerate(self.visible):
            for j,value in enumerate((stamp(r['ts']),r['level'],r['code'],r['parent'] or '—',r['status'],r['operator'] or '—')):
                cell=QTableWidgetItem(str(value));cell.setToolTip(str(value));cell.setForeground(QColor(COLORS.get(value,WHITE)))
                if j in (1,4):cell.setData(Qt.ItemDataRole.UserRole,COLORS.get(value,'#2d6f96'))
                self.grid.setItem(i,j,cell)
        selected=next((i for i,r in enumerate(self.visible) if (r['level'],r['code'])==self.key),0 if self.visible else -1)
        if selected>=0:self.grid.selectRow(selected)
        self.grid.blockSignals(False);self.selected()
        start=max(0,min(self.page_index-3,self.page_count-7))
        for i,b in enumerate(self.page_buttons):
            idx=start+i;b.setVisible(idx<self.page_count);b.setText(str(idx+1));b.setProperty('page',idx);b.setCheckable(True);b.setChecked(idx==self.page_index);b.setEnabled(True)
            # Far pages stay reachable through an ellipsis and the last page number.
            if self.page_count>7 and i==5 and start+6<self.page_count-1:b.setText('…');b.setProperty('page',self.page_index);b.setEnabled(False);b.setChecked(False)
            if self.page_count>7 and i==6 and start+6<self.page_count-1:b.setText(str(self.page_count));b.setProperty('page',self.page_count-1);b.setChecked(self.page_index==self.page_count-1)
        for name,enabled in (('first',self.page_index>0),('prev',self.page_index>0),('next',self.page_index+1<self.page_count),('last',self.page_index+1<self.page_count)):
            self.buttons[name].setEnabled(enabled);self.buttons[name].setVisible(self.page_count>1)
        self.log_rows=self.repo.logs();self.fill_logs(self.logs_grid,self.log_rows[:5]);self.update()
    def selected(self):
        i=self.grid.currentRow();self.item=self.visible[i] if 0<=i<len(self.visible) else None;self.key=(self.item['level'],self.item['code']) if self.item else None
        self.family=self.repo.family(self.key) if self.key else []
        self.trace_path={}
        if self.item:
            nodes={(r['level'],r['code']):r for r in self.family};current=self.item;seen=set()
            while current and (current['level'],current['code']) not in seen:
                seen.add((current['level'],current['code']));self.trace_path[current['level']]=current;current=nodes.get((current['parent_level'],current['parent']))
            current=self.item
            while current:
                children=sorted((r for r in self.family if (r['parent_level'],r['parent'])==(current['level'],current['code'])),key=lambda r:r['code'])
                current=children[0] if children else None
                if current:self.trace_path[current['level']]=current
        for name in ('rev_reprint','rev_unlock','rev_reject','rev_valid','rev_move','rev_update','details'):self.buttons[name].setEnabled(bool(self.item))
        self.update()
    def fill_logs(self,grid,rows):
        grid.setRowCount(len(rows))
        for i,r in enumerate(rows):
            a=json.loads(r['before_json']);b=json.loads(r['after_json'])
            before=a['parent'] or '—' if r['action']=='PINDAH PARENT' else a['status'];after=b['parent'] or '—' if r['action']=='PINDAH PARENT' else b['status']
            for j,value in enumerate((stamp(r['ts']),r['action'],r['level'],r['code'],before,after,r['operator'],r['note'])):
                cell=QTableWidgetItem(str(value));cell.setToolTip(str(value));cell.setForeground(QColor(COLORS.get(value,WHITE)))
                if j in (2,4,5) and str(value) not in ('—',''):cell.setData(Qt.ItemDataRole.UserRole,COLORS.get(value,'#2d6f96'))
                grid.setItem(i,j,cell)
    def edit_dialog(self,action):
        r=self.repo.get(self.key);dialog=AppDialog(self);dialog.setWindowTitle(action);dialog.resize(540,330);layout=QVBoxLayout(dialog)
        label=QLabel(r['level']+' • '+r['code']);label.setWordWrap(True);layout.addWidget(label);form=QFormLayout();choice=None;targets=[]
        if action=='UPDATE STATUS':choice=QComboBox();choice.addItems(STATES);choice.setCurrentText(r['status']);form.addRow('Status baru',choice)
        if action=='PINDAH PARENT':
            targets=self.repo.candidates(self.key);choice=QComboBox();choice.addItems([x['level']+' • '+x['code'] for x in targets]);form.addRow('Parent tujuan',choice)
            if not targets:self.message='Belum ada parent valid dengan level/batch yang sesuai.';return None
        note=QPlainTextEdit();note.setPlaceholderText('Alasan perubahan / hasil verifikasi (wajib)');note.setMaximumHeight(100);form.addRow('Alasan',note);layout.addLayout(form)
        error=QLabel();error.setWordWrap(True);layout.addWidget(error);bar=QHBoxLayout();cancel=QPushButton('Batal');save=QPushButton('Simpan perubahan');bar.addWidget(cancel);bar.addWidget(save);layout.addLayout(bar);cancel.clicked.connect(dialog.reject)
        def accept():
            try:self.repo.reason(note.toPlainText())
            except ValueError as exc:error.setText(str(exc));return
            dialog.accept()
        save.clicked.connect(accept)
        if not dialog.exec():return None
        result=(note.toPlainText(),choice.currentText() if choice else None,targets[choice.currentIndex()] if targets else None);dialog.deleteLater();return result
    def local_action(self,name):
        try:
            if name=='revision_search':self.search_now();return
            if name=='date_filter':self.toggle_dates();return
            if name in ('first','last','prev','next') or name.startswith('page_'):
                self.page_index={'first':0,'last':self.page_count-1,'prev':self.page_index-1,'next':self.page_index+1}.get(name,self.buttons[name].property('page') if name.startswith('page_') else self.page_index)
                self.page_index=max(0,min(self.page_index,self.page_count-1));self.refresh();return
            if name in ('export_search','export_logs'):
                logs=name=='export_logs';path,_=FileDialog.getSaveFileName(self,'Ekspor log revisi' if logs else 'Ekspor hasil pencarian','log-revisi.csv' if logs else 'hasil-revisi.csv','CSV (*.csv)')
                if path:self.repo.export(path,self.log_rows if logs else self.rows,logs);self.message='Ekspor CSV selesai.'
            elif name=='all_logs':self.all_logs()
            elif self.key and name=='details':self.details()
            elif self.key and name=='rev_reprint':self.reprint()
            elif self.key and name.startswith('rev_'):
                action={'rev_unlock':'UNLOCK DATA','rev_reject':'TANDAI REJECT','rev_valid':'PULIHKAN VALID','rev_move':'PINDAH PARENT','rev_update':'UPDATE STATUS'}[name]
                if name!='rev_unlock':self.repo.require_unlocked(self.repo.get(self.key))
                values=self.edit_dialog(action)
                if values:
                    note,status,target=values
                    if name=='rev_unlock':self.repo.unlock(self.key,note)
                    elif name=='rev_move':self.repo.move(self.key,(target['level'],target['code']),note)
                    else:self.repo.change_status(self.key,'REJECT' if name=='rev_reject' else 'VALID' if name=='rev_valid' else status,note)
                    self.message=action+' tersimpan dengan log sebelum–sesudah.';self.changed.emit()
        except Exception as exc:self.message=str(exc);MessageBox.warning(self,'Periksa revisi',self.message)
        self.refresh()
    def details(self):
        dialog=AppDialog(self);dialog.setWindowTitle('Detail & seluruh traceability');dialog.resize(1060,620);layout=QVBoxLayout(dialog);tabs=QTabWidget();layout.addWidget(tabs)
        tree=QTreeWidget();tree.setHeaderLabels(['LEVEL / KODE','BATCH','STATUS','JUMLAH','PARENT']);tree.setColumnWidth(0,330)
        nodes={(r['level'],r['code']):r for r in self.family};items={}
        def insert(key,seen=None):
            if key in items:return items[key]
            seen=set() if seen is None else seen
            if key in seen:return None
            seen.add(key);r=nodes[key];parent_key=(r['parent_level'],r['parent']);parent=insert(parent_key,seen) if parent_key in nodes else tree
            item=QTreeWidgetItem(parent or tree,[r['level']+' • '+r['code'],r['batch'],r['status'],str(r['quantity']),r['parent'] or '—']);items[key]=item;return item
        for key in nodes:insert(key)
        tree.expandAll();tabs.addTab(tree,'Seluruh relasi ('+str(len(nodes))+')')
        info=QPlainTextEdit();info.setReadOnly(True);info.setPlainText(json.dumps(self.repo.get(self.key),indent=2,ensure_ascii=False));tabs.addTab(info,'Detail record')
        events=QTableWidget();events.setColumnCount(5);events.setHorizontalHeaderLabels(['WAKTU','AKTIVITAS','STATUS','USER','CATATAN']);events.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        rows=list(self.store.db.execute('SELECT * FROM events WHERE stage=? AND code=? ORDER BY id DESC',self.key));events.setRowCount(len(rows))
        for i,r in enumerate(rows):
            for j,key in enumerate(('ts','action','status','operator','note')):events.setItem(i,j,QTableWidgetItem(str(r[key])))
        events.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents);tabs.addTab(events,'Riwayat record')
        close=QPushButton('Tutup');close.clicked.connect(dialog.accept);layout.addWidget(close);dialog.exec();dialog.deleteLater()
    def all_logs(self):
        dialog=AppDialog(self);dialog.setWindowTitle('Seluruh log revisi');dialog.resize(1100,580);layout=QVBoxLayout(dialog);search=QLineEdit();search.setPlaceholderText('Cari kode, aktivitas, operator atau catatan');layout.addWidget(search)
        grid=QTableWidget();grid.setColumnCount(8);grid.setHorizontalHeaderLabels(['WAKTU','AKTIVITAS','LEVEL','KODE','DARI','KE','USER','CATATAN']);grid.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);layout.addWidget(grid)
        def render():
            q=search.text().casefold();self.fill_logs(grid,[r for r in self.repo.logs() if q in ' '.join(str(x) for x in r.values()).casefold()]);grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        search.textChanged.connect(render);render();close=QPushButton('Tutup');close.clicked.connect(dialog.accept);layout.addWidget(close);dialog.exec();dialog.deleteLater()
    def log_detail(self,index,column):
        if index<len(self.log_rows):
            r=self.log_rows[index];MessageBox.information(self,r['action'],r['note']+'\n\nSEBELUM\n'+json.dumps(json.loads(r['before_json']),ensure_ascii=False,indent=2)+'\n\nSESUDAH\n'+json.dumps(json.loads(r['after_json']),ensure_ascii=False,indent=2))
    def reprint(self):
        if not self.runtime:raise ValueError('Runtime printer belum tersedia.')
        key=self.key;doc=self.repo.label(key,self.aggregation,self.templates.repo)
        from .label_render import render_image,export_pdf
        dialog=AppDialog(self);dialog.setWindowTitle('Reprint label • '+key[1]);dialog.resize(650,610);layout=QVBoxLayout(dialog)
        preview=QLabel();preview.setAlignment(Qt.AlignmentFlag.AlignCenter);pix=QPixmap.fromImage(render_image(doc,150));preview.setPixmap(pix.scaled(570,410,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation));layout.addWidget(preview)
        note=QLineEdit();note.setPlaceholderText('Alasan cetak ulang (wajib)');layout.addWidget(note);message=QLabel('Periksa isi label sebelum mencetak.');message.setWordWrap(True);layout.addWidget(message);bar=QHBoxLayout();layout.addLayout(bar)
        def save_pdf():
            try:
                reason=self.repo.reason(note.text());path,_=FileDialog.getSaveFileName(dialog,'Simpan label PDF','label-revisi.pdf','PDF (*.pdf)')
                if path:export_pdf(doc,path);self.repo.record_print(key,reason,'PDF TERSIMPAN');message.setText('PDF tersimpan; belum dicetak ke perangkat.');self.changed.emit()
            except Exception as exc:message.setText(str(exc))
        def print_now():
            try:
                reason=self.repo.reason(note.text());level=doc['level'];profile=self.runtime.repo.load()['printers'][level]
                if profile['device'].startswith('tcp://'):ok=self.runtime.print_zpl(doc)
                else:ok=self.templates.print_document(doc,None,printer=self.runtime.configured_printer(level),confirm=True)
                if ok:self.repo.record_print(key,reason,'TERKIRIM KE PRINTER');message.setText('Tugas terkirim. Periksa hasil fisik pada printer.');self.changed.emit()
            except Exception as exc:message.setText(str(exc))
        for label,callback in [('Simpan PDF',save_pdf),('Cetak ke printer',print_now),('Tutup',dialog.accept)]:b=QPushButton(label);b.clicked.connect(callback);bar.addWidget(b)
        dialog.exec();dialog.deleteLater()
    def barcode(self,code,x,y,w,h):
        from .label_render import encoded_symbol
        try:
            bits=encoded_symbol('barcode',code);cell=w/(len(bits)+20)
            self.p.save();self.p.setPen(Qt.PenStyle.NoPen);self.p.setBrush(QColor(WHITE))
            for i,bit in enumerate(bits):
                if bit=='1':self.p.drawRect(QRectF(x+(i+10)*cell,y,cell,h))
            self.p.restore()
        except ValueError:self.text(x,y,w,h,code,10,MUTED,align=Qt.AlignmentFlag.AlignCenter)
    def quantity_label(self,r):
        if r['level']=='UNIT':return '1 unit'
        child=CHILD_LEVEL[r['level']];count=self.child_count(r)
        if not count:return 'Belum tercatat'
        units=self.unit_count(r)
        return f'{count} {child.lower()}'+(f' ({units} unit)' if units and child!='UNIT' else '')

    def child_count(self,r):
        count=sum((x['parent_level'],x['parent'])==(r['level'],r['code']) for x in getattr(self,'family',[]))
        return count or (r['quantity'] if r.get('run_id') else 0)

    def unit_count(self,r):
        """Units recorded below this package in the loaded relation tree."""
        if r['level']=='UNIT':return 1
        children=[x for x in getattr(self,'family',[]) if (x['parent_level'],x['parent'])==(r['level'],r['code'])]
        if not children:return 0
        return sum(self.unit_count(child) or (child['quantity'] if child['level']=='BOX' else 0) for child in children)

    def mark(self,right,y,text,color):
        """Status icon plus right aligned label, like the reference detail panel."""
        from PySide6.QtGui import QFontMetricsF
        from .typography import ui_font
        width=QFontMetricsF(ui_font(10,True)).horizontalAdvance(str(text))+2
        self.dot(right-width-19,y+3,color,'check' if color==GREEN else 'warning' if color==YELLOW else 'cross' if color==RED else 'check',14)
        self.text(right-width,y,width,20,text,10,color,True,Qt.AlignmentFlag.AlignRight)

    def chip(self,x,y,w,h,text,color,size=10):
        self.rect(x,y,w,h,color,color,color,int(h/2));self.text(x,y,w,h,text,size,'#f4fbff',True,Qt.AlignmentFlag.AlignCenter)
    def paint_content(self):
        self.panel(15,75,1080,120)
        for x,label in [(29,'SERIAL UNIT'),(300,'KODE BOX'),(569,'KODE CARTON'),(839,'KODE PALLET')]:self.text(x,81,240,22,label,11,MUTED,True)
        for x,label in [(29,'BATCH'),(300,'TANGGAL'),(569,'STATUS')]:self.text(x,134,112,23,label,11,MUTED)
        self.text(410,158,19,29,'—',12,MUTED,align=Qt.AlignmentFlag.AlignCenter)
        # The clock button switches the range filter; a lit frame marks it active.
        self.rect(541,158,28,29,'#0c5c3a' if self.date_active else '#04283f','#03321f' if self.date_active else '#031b2e',GREEN if self.date_active else '#3f6780',4)
        self.panel(15,202,699,366,'HASIL PENCARIAN / DATA AGREGASI');self.text(516,206,148,24,'TOTAL '+num(len(self.rows))+' DATA',10,MUTED,align=Qt.AlignmentFlag.AlignRight)
        self.text(30,543,340,22,f'{self.page_index*8+1 if self.rows else 0} – {min((self.page_index+1)*8,len(self.rows))} dari {len(self.rows)} data',10,MUTED)
        if not self.rows:self.text(43,345,620,40,'Tidak ada data yang cocok dengan pencarian.',13,MUTED,align=Qt.AlignmentFlag.AlignCenter)
        self.panel(728,202,367,366,'DETAIL DATA TERPILIH')
        r=self.item
        if r:
            self.text(745,236,120,22,'TIPE DATA',10,MUTED);self.chip(1002,237,78,20,r['level'],COLORS[r['level']])
            for i,(label,value) in enumerate([('KODE '+r['level'],r['code']),('PRODUK',r['product']),('BATCH',r['batch']),('KAPASITAS '+r['level'],self.quantity_label(r))],1):
                self.text(745,236+i*23,150,21,label,10,MUTED);self.text(880,236+i*23,200,21,value,11,WHITE,align=Qt.AlignmentFlag.AlignRight)
            parent_level=r['parent_level'] if r['parent'] else ''
            self.text(745,354,200,20,'PARENT'+(' ('+parent_level+')' if parent_level else ''),10,MUTED)
            if r['parent']:
                self.chip(745,376,150,22,parent_level+' '+r['parent'],COLORS.get(parent_level,'#2d6f96'),9)
                self.text(897,376,26,22,'→',13,MUTED,align=Qt.AlignmentFlag.AlignCenter)
                self.chip(925,376,155,22,r['level']+' '+r['code'],COLORS[r['level']],9)
            else:self.text(745,376,335,22,'Belum terhubung ke parent mana pun.',10,MUTED)
            self.line(745,406,333)
            for i,(label,value) in enumerate([('STATUS VERIFIKASI',r['status']),('STATUS CETAK LABEL',PRINT_STATES.get(r['print_state'],r['print_state'])),('WAKTU SCAN TERAKHIR',stamp(r['ts'])),('OPERATOR',r['operator'] or '—')]):
                y=412+i*20;self.text(745,y,165,20,label,10,MUTED)
                if i<2:
                    color=COLORS.get(r['status'] if i==0 else ('VALID' if r['print_state']=='SENT' else 'PENDING'),WHITE)
                    self.mark(1080,y,value,color)
                else:self.text(910,y,170,20,value,10,WHITE,align=Qt.AlignmentFlag.AlignRight)
            self.text(745,494,165,18,'CATATAN',10,MUTED)
            self.text(745,510,335,18,(r['note'] or 'Tanpa catatan')+('  •  AKSES '+('TERKUNCI' if r['locked'] else 'TERBUKA')),10,MUTED)
        else:self.text(745,300,330,80,'Pilih baris hasil pencarian untuk melihat detail.',13,MUTED,wrap=True)
        self.panel(15,579,1080,175,'RIWAYAT TRACEABILITY')
        family=getattr(self,'family',[])
        for i,level in enumerate(LEVELS):
            x=28+i*273;group=[v for v in family if v['level']==level];v=getattr(self,'trace_path',{}).get(level)
            self.text(x,612,242,21,level,12,COLORS[level],True,Qt.AlignmentFlag.AlignCenter);self.rect(x,636,233,107,'#075036' if level=='UNIT' else '#06364e','#02253b',COLORS[level],4)
            if v:
                self.text(x+5,640,221,19,v['code'],11,WHITE,True,Qt.AlignmentFlag.AlignCenter);self.barcode(v['code'],x+39,662,157,27)
                self.dot(x+212,640,COLORS.get(v['status'],WHITE),'check' if v['status']=='VALID' else 'warning' if v['status']=='REJECT' else 'cross',14)
                self.text(x+5,692,221,17,v['product'] if level=='UNIT' else self.quantity_label(v),10,COLORS[level],True,Qt.AlignmentFlag.AlignCenter)
                self.text(x+5,709,221,16,v['batch'],10,MUTED,align=Qt.AlignmentFlag.AlignCenter)
                self.text(x+5,725,221,16,stamp(v['ts'])+('  •  '+v['operator'] if v['operator'] else ''),9,MUTED,align=Qt.AlignmentFlag.AlignCenter)
            else:self.text(x+8,663,217,48,'Belum ada relasi '+level,11,MUTED,align=Qt.AlignmentFlag.AlignCenter,wrap=True)
            if i<3:self.text(x+238,663,33,35,'→',26,MUTED,align=Qt.AlignmentFlag.AlignCenter)
        self.panel(15,768,382,218,'AKSI REVISION');self.text(28,948,354,30,self.message,10,MUTED,wrap=True)
        self.panel(411,768,684,218,'LOG REVISION');self.text(891,773,147,22,'TOTAL '+str(len(getattr(self,'log_rows',[])))+' AKSI',10,MUTED,align=Qt.AlignmentFlag.AlignRight)
    def sidebar(self):
        from .shared_sidebar import paint_sidebar
        paint_sidebar(self)
    def side_row(self,y,label,value):self.text(1126,y,153,19,label,10,MUTED);self.text(1280,y,134,19,value,10,COLORS.get(value,WHITE),align=Qt.AlignmentFlag.AlignRight)
