"""Complete PALLET workstation backed by saved aggregation sessions."""
import csv
import math
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt,QDate,QRectF,QTimer,QPointF
from PySide6.QtGui import QColor,QPen,QPainterPath,QPolygonF
from PySide6.QtWidgets import QDateEdit,QTableWidgetItem,QPushButton,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QSpinBox
from .pages import PageBase,OperationPage
from .upload_page import SendPage
from .pallet_model import PalletRepository
from .dashboard import WHITE,MUTED,GREEN,RED,YELLOW,BLUE
from .sidebar_layout import fixed_sidebar,SIDEBAR
from .settings_model import VERSION
from .ui_dialogs import AppDialog,FileDialog,MessageBox


class PalletPage(OperationPage):
    button=SendPage.button
    GRID_SIZE=24
    def __init__(self,store):
        PageBase.__init__(self,store,'pallet','Agregasi Pallet','PENYUSUNAN CARTON KE PALLET','PALLET')
        self.stage='PALLET';self.cfg=dict(self.CONFIG['PALLET']);self.filled=0;self.run=None;self.repo=None;self.grid_page=0;self.scanning=False;self.cache_count=0
        self.child_codes=[];self.recent_children=[];self.result_rows=[];self.message='Pilih produk, batch dan template untuk memulai pallet.';self.buttons={};self.verification_dialog=None;self.phase=0
        self.template_selector=self.combo(99,720,235,24,[]);self.template_selector.setObjectName('pallet_template')
        self.product=self.field(99,749,235,24,'','Produk mengikuti template');self.product.setObjectName('pallet_product');self.product.setReadOnly(True)
        self.product.setStyleSheet(self.product.styleSheet()+' QLineEdit {color:#bcd8ec;background:#03202f;}')
        self.batch=self.combo(99,778,235,24,[store.get('batch')]);self.batch.setObjectName('pallet_batch')
        self.target_list=self.combo(99,807,235,24,[]);self.target_list.setObjectName('pallet_target_list')
        self.inputs=(self.template_selector,self.batch,self.target_list)
        self.button('stage_lock',28,838,306,29,'KUNCI DATA','lock')
        self.scan_table=self.table(370,723,338,147,['WAKTU','KODE CARTON','STATUS'],[67,188,75]);self.scan_table.verticalHeader().setDefaultSectionSize(23);self.scan_table.horizontalHeader().setFixedHeight(25)
        self.result_table=self.table(740,723,341,147,['WAKTU','KODE PALLET','STATUS'],[66,186,80]);self.result_table.verticalHeader().setDefaultSectionSize(23);self.result_table.horizontalHeader().setFixedHeight(25)
        self.scan_table.cellDoubleClicked.connect(self.scan_detail);self.result_table.cellDoubleClicked.connect(self.result_detail)
        for spec in [('stage_start_scan',139,899,146,43,'START SCAN CARTON','play','green'),('stage_print_label',297,899,153,43,'PRINT LABEL','printer','blue'),('stage_reset',462,899,143,43,'RESET PALLET','sync','gold'),('stage_upload',923,899,158,43,'UPLOAD INSTAN','upload','blue')]:self.button(*spec)
        upload=self.buttons['stage_upload'];upload.setStyleSheet(upload.styleSheet().replace('#076fac','#7844a9').replace('#03426b','#442565').replace('#249bd2','#a678ce'))
        self.mfd=QDateEdit(QDate.currentDate(),self);self.mfd.setDisplayFormat('dd/MM/yyyy');self.mfd.setCalendarPopup(True);self.mfd.setGeometry(65,951,124,29);self.mfd.setStyleSheet('QDateEdit {color:#edf5ff;background:#04283f;border:1px solid #3f6780;padding:3px;}')
        self.scan_input=self.field(240,951,225,29,'','Scan serial carton / Enter');self.scan_input.setMaxLength(500);self.scan_input.setObjectName('pallet_scan_input');self.scan_input.returnPressed.connect(self.scan)
        for i,name in enumerate(('pallet_targets','pallet_scan_step','pallet_print_step','pallet_verify')):self.hotspot(name,15+i*274,84,258,94)
        self.button('grid_prev',937,199,27,25,'‹','',flat=True);self.button('grid_next',965,199,27,25,'›','',flat=True)
        self.cell_buttons=[]
        for i in range(self.GRID_SIZE):
            row,col=divmod(i,6);b=self.hotspot('pallet_cell_'+str(i),32+col*175,234+row*102,168,96);self.cell_buttons.append(b)
        self.batch.currentTextChanged.connect(self.batch_changed)
        self.template_selector.currentIndexChanged.connect(self.template_changed);self.action.connect(self.local_action)
        self.animation=QTimer(self);self.animation.setInterval(80);self.animation.timeout.connect(self.animate)
    def animate(self):
        if self.scanning and self.isVisible():self.phase=(self.phase+1)%24;self.update(25,229,1060,441)
    def showEvent(self,event):super().showEvent(event);self.animation.start()
    def hideEvent(self,event):self.animation.stop();super().hideEvent(event)

    def configure_templates(self,runtime,print_callback):
        self.runtime=runtime;self.print_callback=print_callback;self.repo=PalletRepository(self.store,runtime)
        self.settings_runtime.changed.connect(self.refresh);self.settings_runtime.message.connect(self.notify)
        self.refresh()
        if self.template_selector.count()<=1:self.message='Lengkapi template Pallet dan relasi child di Master Template terlebih dahulu.'
        identifier=self.store.get('pallet_current_run')
        if identifier:
            try:
                run=runtime.get(identifier)
                if run['state']!='CANCELLED':self.update_run(run);self.message='Sesi pallet sebelumnya dimuat kembali.'
            except ValueError:pass

    def notify(self,text):
        self.message=text;self.update()

    @staticmethod
    def fill_combo(combo,items,selected=None):
        previous=combo.currentData() if selected is None else selected
        combo.blockSignals(True);combo.clear()
        for label,data in items:combo.addItem(label,data)
        index=combo.findData(previous);combo.setCurrentIndex(index if index>=0 else 0);combo.blockSignals(False)

    def template_changed(self,*_):
        if self.run:return
        self.refresh_choices()
        self.message='Template dipilih. Pilih batch dan list carton hasil Tahap 2, lalu tekan KUNCI DATA.' if self.template_selector.currentData() else 'Pilih template pallet aktif untuk memulai.'
        self.update()

    def batch_changed(self,*_):
        if self.repo and not (self.run and self.run['state']=='OPEN'):self.refresh_choices()

    def current_document(self):
        if self.run:return self.run['document']
        identifier=self.template_selector.currentData()
        if not identifier:return None
        try:return self.runtime.repo.get(identifier)['document']
        except ValueError:return None

    def current_product(self):
        doc=self.current_document()
        return self.repo.product_for(doc) if doc else None

    def child_template_id(self):
        doc=self.current_document()
        return doc.get('child_template_id') if doc else None

    def refresh_choices(self):
        if not self.repo:return
        docs=self.repo.templates()
        templates=[('Pilih template pallet…',None)]+[(r['name']+' • '+r['document']['child_level'],r['id']) for r in docs]
        if self.run and not any(value==self.run['template_id'] for _,value in templates):templates.append((self.run['document']['name']+' • sesi tersimpan',self.run['template_id']))
        self.fill_combo(self.template_selector,templates)
        doc=self.current_document();product=self.current_product()
        self.product.setText(product['name'] if product else '');self.product.setCursorPosition(0)
        # Batches and lists follow the cartons that stage 2 has finished.
        pending=self.repo.pending_batches(product,self.child_template_id()) if doc else []
        batches=[self.run['batch']] if self.run else [row['batch'] for row in pending]
        current=self.batch.currentText();self.batch.blockSignals(True);self.batch.clear();self.batch.addItems(batches)
        if current in batches:self.batch.setCurrentText(current)
        self.batch.blockSignals(False)
        ready=next((row['quantity'] for row in pending if row['batch']==self.batch.currentText()),0)
        lists=self.repo.lists(product,self.batch.currentText())
        self.fill_combo(self.target_list,[(f'SEMUA CARTON SIAP TAHAP 2 ({ready} carton)',None)]+[(f"{r['name']} | {r['quantity']} carton",r['id']) for r in lists])
        locked=bool(self.run)
        self.batch.setEnabled(not locked);self.target_list.setEnabled(not locked)

    def refresh(self):
        if not self.repo:return
        self.refresh_choices()
        if self.run:self.update_run(self.runtime.get(self.run['id']))
        self.recent_children=self.repo.recent();self.result_rows=self.repo.results()
        self.cache_count=sum(1 for row in self.settings_runtime.delivery.rows() if row['stage']=='PALLET' and row['delivery_status'] in ('PENDING','FAILED','SENDING'))
        for table,rows,kind in [(self.scan_table,self.recent_children,'scan'),(self.result_table,self.result_rows,'result')]:
            table.setRowCount(len(rows))
            for i,row in enumerate(rows):
                status=row['status'] if kind=='scan' else ('AKTIF' if row['state']=='OPEN' else 'VALID' if row['verified'] else 'SELESAI')
                values=[row['ts'][11:19] if kind=='scan' else row['created_at'][11:19],row['code'] if kind=='scan' else row['parent_code'] or 'Belum bernomor',status]
                for j,value in enumerate(values):
                    item=QTableWidgetItem(str(value));item.setToolTip(str(value));table.setItem(i,j,item)
                    if j==2:item.setForeground(QColor(GREEN if status in ('VALID','SELESAI') else BLUE if status=='AKTIF' else YELLOW if status=='DUPLIKAT' else RED))
        self.grid_page=max(0,min(self.grid_page,math.ceil(self.cfg['capacity']/self.GRID_SIZE)-1))
        self.buttons['grid_prev'].setEnabled(self.grid_page>0);self.buttons['grid_next'].setEnabled((self.grid_page+1)*self.GRID_SIZE<self.cfg['capacity'])
        for name in ('grid_prev','grid_next'):self.buttons[name].setVisible(self.cfg['capacity']>self.GRID_SIZE)
        self.buttons['stage_lock'].setText('BUKA KUNCI DATA' if self.run else 'KUNCI DATA')
        self.update()

    def toggle_lock(self):
        if self.run:self.release_session('Data dibuka. Pilih template, batch dan list carton untuk sesi berikutnya.');return
        if not self.template_selector.currentData():self.notify('Pilih template pallet aktif terlebih dahulu.');return
        self.start_template()

    def release_session(self,message):
        if self.run:
            try:self.runtime.reset_empty(self.run['id'])
            except ValueError as exc:self.notify(str(exc));return False
        if hasattr(self,'settings_runtime'):self.settings_runtime.scanner_armed['PALLET']=False
        self.run=None;self.filled=0;self.child_codes=[];self.grid_page=0;self.scanning=False;self.cfg=dict(self.CONFIG['PALLET'])
        self.buttons['stage_start_scan'].setText('START SCAN')
        for widget in self.inputs+(self.mfd,):widget.setEnabled(True)
        with self.store.db:self.store.put('pallet_current_run',None)
        self.refresh_choices();self.template_selector.blockSignals(True);self.template_selector.setCurrentIndex(0);self.template_selector.blockSignals(False)
        self.notify(message);self.refresh();self.changed.emit();return True

    def start_template(self,*_):
        if not self.repo:return
        identifier=self.template_selector.currentData()
        if not identifier:
            self.run=None;self.filled=0;self.child_codes=[];self.scanning=False;self.update();return
        self.refresh_choices()
        if not self.batch.currentText():
            self.run=None;self.message='Belum ada carton Tahap 2 yang siap untuk pallet ini. Selesaikan dan cetak label carton terlebih dahulu.';self.update();return
        try:
            self.grid_page=0;self.update_run(self.repo.start(identifier,self.batch.currentText(),self.mfd.text(),self.target_list.currentData()))
            self.scanning=self.run['state']=='OPEN';self.message='Sesi siap. Scan '+self.cfg['child'].lower()+' dengan scanner atau ketik kode lalu Enter.'
            if self.scanning:
                try:self.settings_runtime.listen_scanner('PALLET')
                except ValueError as exc:self.message='Sesi siap untuk input manual. Scanner: '+str(exc)
            self.refresh()
        except ValueError as exc:self.run=None;self.message=str(exc);self.update()

    def update_run(self,run):
        self.run=run;doc=run['document'];self.filled=run['quantity'];self.cfg.update(capacity=doc['aggregation_max'],code=run['parent_code'] or '—',child=doc['child_level'])
        self.child_codes=[r[0] for r in self.store.db.execute('SELECT code FROM aggregation_children WHERE run_id=? ORDER BY rowid',(run['id'],))]
        meta=self.repo.meta(run['id'])
        self.scan_input.setPlaceholderText('Scan '+doc['child_level'].lower()+' / Enter')
        self.subtitle='PENYUSUNAN '+doc['child_level']+' KE PALLET'
        self.scan_table.setHorizontalHeaderLabels(['WAKTU','KODE '+doc['child_level'],'STATUS'])
        self.batch.blockSignals(True);self.batch.setCurrentText(run['batch']);self.batch.blockSignals(False)
        self.refresh_choices()
        product=self.repo.product_for(doc)
        self.product.setText(product['name'] if product else doc['data'].get('product_name',''));self.product.setCursorPosition(0)
        self.template_selector.blockSignals(True);self.template_selector.setCurrentIndex(self.template_selector.findData(run['template_id']));self.template_selector.blockSignals(False)
        self.target_list.blockSignals(True);self.target_list.setCurrentIndex(max(0,self.target_list.findData(meta.get('list_id'))));self.target_list.blockSignals(False)
        date=QDate.fromString(meta.get('mfd',doc['data']['mfg_date']),'dd/MM/yyyy')
        if date.isValid():self.mfd.setDate(date)
        # Session inputs are a snapshot; reset is the explicit route to another session.
        for widget in self.inputs+(self.mfd,):widget.setEnabled(False)
        if run['state']!='OPEN':self.scanning=False
        self.buttons['stage_start_scan'].setText(('STOP SCAN' if self.scanning else 'START SCAN')+' '+self.cfg['child'])
        self.buttons['stage_lock'].setText('BUKA KUNCI DATA')
        self.update()

    def scan(self):
        if self.verification_dialog:
            self.verification_dialog.code.setText(self.scan_input.text());self.scan_input.clear();return
        code=self.scan_input.text().strip()
        if not code:self.notify('Pindai barcode atau masukkan serial carton terlebih dahulu.');return
        if not self.run:self.notify('Pilih template pallet terlebih dahulu.');return
        if not self.scanning:self.notify('Scan dijeda. Tekan START SCAN untuk melanjutkan.');return
        try:
            self.update_run(self.repo.scan(self.run['id'],code));self.scan_input.clear();self.grid_page=min(self.filled//self.GRID_SIZE,(self.cfg['capacity']-1)//self.GRID_SIZE)
            self.message=f'VALID • {self.filled}/{self.cfg["capacity"]} {self.cfg["child"].lower()}'
            if self.run['state']=='COMPLETE':
                if self.run['print_state']=='PENDING':self.print_run(automatic=True)
                else:self.message='Pallet penuh dan dikunci. Cetak label untuk melanjutkan.'
        except ValueError as exc:self.message=str(exc);self.scan_input.selectAll()
        self.refresh();self.changed.emit()

    def local_action(self,name):
        if name in ('stage_start_scan','pallet_scan_step'):
            if self.scan_input.text().strip():
                if self.run and self.run['state']=='OPEN':self.scanning=True
                self.scan();return
            if not self.run:self.start_template()
            if not self.run:self.notify('Pilih template pallet terlebih dahulu.');return
            if self.run['state']!='OPEN':self.notify('Pallet sudah selesai. Gunakan RESET PALLET untuk sesi berikutnya.');return
            self.scanning=not self.scanning
            if self.scanning:
                try:self.message=self.settings_runtime.listen_scanner('PALLET')
                except ValueError as exc:self.message=str(exc)+' • Input manual tetap tersedia.'
                self.scan_input.setFocus()
            else:
                self.settings_runtime.scanner_armed['PALLET']=False
                self.message='Scan dijeda. Data sesi tetap tersimpan.'
            self.buttons['stage_start_scan'].setText(('STOP SCAN' if self.scanning else 'START SCAN')+' '+self.cfg['child']);self.update()
        elif name=='stage_lock':self.toggle_lock()
        elif name=='stage_close_pallet':
            if not self.run:self.notify('Kunci data dan scan carton terlebih dahulu.');return
            try:
                self.update_run(self.repo.finish(self.run['id']));self.message='Pallet dikunci. Cetak label lalu lakukan verifikasi.'
                if self.run['print_state']=='PENDING':self.print_run(automatic=True)
                self.refresh();self.changed.emit()
            except ValueError as exc:self.notify(str(exc))
        elif name in ('stage_print_label','pallet_print_step'):self.print_run()
        elif name=='stage_reset':self.release_session('Pilih template, batch dan list carton untuk membuka pallet berikutnya.')
        elif name=='stage_upload':self.settings_runtime.upload(level='PALLET')
        elif name=='pallet_targets':self.show_targets()
        elif name=='pallet_verify':self.verify_dialog(self.run)
        elif name in ('grid_prev','grid_next'):
            self.grid_page=max(0,min(math.ceil(self.cfg['capacity']/self.GRID_SIZE)-1,self.grid_page+(-1 if name=='grid_prev' else 1)));self.refresh()
        elif name.startswith('pallet_cell_'):
            n=self.grid_page*self.GRID_SIZE+int(name.rsplit('_',1)[1])
            if n<len(self.child_codes):MessageBox.information(self,'Detail carton',f'Urutan: {n+1}\nSerial: {self.child_codes[n]}\nPallet: {self.cfg["code"]}\nBatch: {self.run["batch"]}\nStatus: VALID')

    def print_run(self,automatic=False):
        if not self.run:self.notify('Pilih pallet terlebih dahulu.');return
        if self.run['state']!='COMPLETE':
            if automatic:return
            minimum=self.run['document']['aggregation_min']
            if self.filled<minimum:self.notify(f'Isi pallet baru {self.filled}; target minimum template {minimum}.');return
            if MessageBox.question(self,'Kunci pallet',f'Pallet berisi {self.filled} dari {self.cfg["capacity"]} {self.cfg["child"].lower()}. Kunci pallet sekarang lalu cetak label?')!=MessageBox.StandardButton.Yes:return
            try:self.update_run(self.repo.finish(self.run['id']))
            except ValueError as exc:self.notify(str(exc));return
        try:self.repo.validate_print(self.run['id'])
        except ValueError as exc:self.notify(str(exc));return
        sent=False
        if self.run['print_state']=='SENT' and not automatic:
            if MessageBox.question(self,'Cetak ulang','Cetak ulang label '+self.run['parent_code']+'?')!=MessageBox.StandardButton.Yes:return
            try:
                if self.print_callback(self.runtime.print_document(self.run['id']),self.run['template_id'],False):
                    sent=True
                    with self.store.db:self.store.audit('REPRINT PALLET',self.run['parent_code'])
                    self.notify('Label pallet dicetak ulang.')
            except Exception as exc:self.notify(str(exc))
        else:
            OperationPage.print_run(self,automatic)
            sent=self.runtime.get(self.run['id'])['print_state']=='SENT'
        if sent:self.repo.revisions.record_print(('PALLET',self.run['parent_code']),'Cetak label melalui Tahap 3 / Pallet','TERKIRIM KE PRINTER')
        self.refresh();self.changed.emit()

    def scan_detail(self,row,*_):
        if row<len(self.recent_children):
            r=self.recent_children[row];MessageBox.information(self,'Detail scan',f"{r['code']}\n{r['ts']}\n{r['status']}\n{r['note']}")

    def result_detail(self,row,*_):
        if row>=len(self.result_rows):return
        run=self.runtime.get(self.result_rows[row]['id']);dialog=AppDialog(self);dialog.setWindowTitle('Hasil agregasi pallet');dialog.resize(550,350);layout=QVBoxLayout(dialog)
        info=QLabel(f"{run['parent_code']}\nBatch: {run['batch']}\nIsi: {run['quantity']} {run['document']['child_level'].lower()}\nStatus: {run['state']} | Cetak: {run['print_state']}");layout.addWidget(info)
        children=self.store.db.execute('SELECT code FROM aggregation_children WHERE run_id=? ORDER BY rowid',(run['id'],)).fetchall();codes=QLabel('\n'.join(r[0] for r in children[:10])+ ('\n…' if len(children)>10 else ''));layout.addWidget(codes)
        rowpallet=QHBoxLayout();layout.addLayout(rowpallet)
        def pdf():
            path,_=FileDialog.getSaveFileName(dialog,'Simpan label PDF',run['parent_code']+'.pdf','PDF (*.pdf)')
            if path:
                try:
                    from .label_render import export_pdf
                    self.repo.validate_print(run['id'])
                    export_pdf(self.runtime.print_document(run['id']),path);self.notify('PDF label tersimpan.');dialog.accept()
                except Exception as exc:MessageBox.warning(dialog,'Label belum siap',str(exc))
        for label,call in [('Ekspor label PDF',pdf),('Verifikasi',lambda:self.verify_dialog(run)),('Tutup',dialog.accept)]:
            b=QPushButton(label);b.clicked.connect(call);rowpallet.addWidget(b)
        dialog.exec()

    def verify_dialog(self,run):
        if not run or run['state']!='COMPLETE':self.notify('Kunci pallet lalu cetak label sebelum verifikasi.');return
        if run['print_state']!='SENT':self.notify('Cetak label pallet sebelum verifikasi.');return
        dialog=AppDialog(self);dialog.setWindowTitle('Verifikasi kamera / label pallet');dialog.resize(610,350);layout=QVBoxLayout(dialog)
        label=QLabel(f"Pallet: {run['parent_code']}\nPeriksa gambar kamera dan isi pallet, lalu scan ulang label. Verifikasi dicatat atas nama operator.");label.setWordWrap(True);layout.addWidget(label)
        dialog.code=QLineEdit();dialog.code.setPlaceholderText('Scan kode label pallet');layout.addWidget(dialog.code)
        count=QSpinBox();count.setRange(0,1000000);count.setPrefix('Jumlah '+run['document']['child_level'].lower()+' diperiksa: ');layout.addWidget(count)
        error=QLabel();error.setWordWrap(True);layout.addWidget(error)
        def camera():
            from .settings_dialogs import CameraCalibration
            cam=CameraCalibration(self.settings_runtime,dialog);cam.start();cam.exec()
        def verify():
            try:self.repo.verify(run['id'],dialog.code.text(),count.value());dialog.accept();self.notify('Verifikasi pallet VALID tersimpan.');self.refresh();self.changed.emit()
            except ValueError as exc:error.setText(str(exc))
        row=QHBoxLayout();layout.addLayout(row)
        for title,call in [('Buka kamera',camera),('Simpan verifikasi',verify),('Batal',dialog.reject)]:
            b=QPushButton(title);b.clicked.connect(call);row.addWidget(b)
        self.verification_dialog=dialog
        try:dialog.exec()
        finally:self.verification_dialog=None

    def show_targets(self):
        dialog=AppDialog(self);dialog.setWindowTitle('Data target carton untuk pallet');dialog.resize(840,570);layout=QVBoxLayout(dialog)
        info=QLabel('Carton siap berasal dari sesi Carton selesai dan label tercetak, sesuai produk/batch. Pilih carton untuk membuat list atau impor daftar kode CSV.');info.setWordWrap(True);layout.addWidget(info)
        from PySide6.QtWidgets import QTableWidget,QAbstractItemView
        grid=QTableWidget(0,4);grid.setHorizontalHeaderLabels(['PILIH','KODE CARTON','QTY CHILD','STATUS']);grid.setColumnWidth(0,52);grid.setColumnWidth(1,370);grid.setColumnWidth(2,100);grid.horizontalHeader().setStretchLastSection(True);grid.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);layout.addWidget(grid)
        name=QLineEdit('PALLET LIST');name.setPlaceholderText('Nama list target');layout.addWidget(name)
        rows=[]
        def load():
            nonlocal rows
            if self.target_list.currentData():
                rows=[dict(r) for r in self.store.db.execute("SELECT t.code,COALESCE(r.quantity,0) quantity,CASE WHEN c.code IS NULL THEN 'BELUM SCAN' ELSE 'TERAGREGASI' END state FROM pallet_targets t LEFT JOIN aggregation_runs r ON r.level='CARTON' AND r.parent_code=t.code LEFT JOIN aggregation_children c ON c.child_level='CARTON' AND c.code=t.code WHERE t.list_id=? ORDER BY t.rowid",(self.target_list.currentData(),))]
            else:rows=self.repo.candidates(self.current_product(),self.batch.currentText(),self.child_template_id())
            grid.setRowCount(min(1000,len(rows)))
            for i,r in enumerate(rows[:1000]):
                item=QTableWidgetItem();item.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(Qt.CheckState.Unchecked);grid.setItem(i,0,item)
                for j,value in enumerate((r['code'],r['quantity'],r['state']),1):grid.setItem(i,j,QTableWidgetItem(str(value)))
            info.setText(f"{len(rows)} carton tersedia dalam tampilan ini. Centang carton lalu Simpan List. Pratinjau maksimal 1.000 baris.")
        def require_idle():
            if self.run:MessageBox.warning(dialog,'Sesi aktif','Selesaikan / reset sesi terlebih dahulu sebelum mengganti list target.');return False
            return True
        def select_all():
            for i in range(grid.rowCount()):grid.item(i,0).setCheckState(Qt.CheckState.Checked)
        def save_list():
            if not require_idle():return
            codes=[rows[i]['code'] for i in range(grid.rowCount()) if grid.item(i,0).checkState()==Qt.CheckState.Checked]
            try:
                identifier=self.repo.create_targets(name.text(),codes,self.current_product(),self.batch.currentText());self.refresh_choices();self.target_list.setCurrentIndex(self.target_list.findData(identifier));load();self.notify('List target pallet tersimpan.')
            except ValueError as exc:MessageBox.warning(dialog,'List belum tersimpan',str(exc))
        def import_file():
            if not require_idle():return
            path,_=FileDialog.getOpenFileName(dialog,'Impor target carton','','CSV (*.csv)')
            if path:
                try:
                    identifier=self.repo.import_targets(path,self.current_product(),self.batch.currentText());self.refresh_choices();self.target_list.setCurrentIndex(self.target_list.findData(identifier));load();self.notify('List target pallet berhasil diimpor.')
                except (ValueError,OSError,csv.Error) as exc:MessageBox.warning(dialog,'Impor gagal',str(exc))
        def export():
            path,_=FileDialog.getSaveFileName(dialog,'Ekspor target carton','target-pallet.csv','CSV (*.csv)')
            if path:
                try:
                    with open(path,'w',newline='',encoding='utf-8-sig') as handle:
                        writer=csv.writer(handle);writer.writerow(['code','product','batch'])
                        for r in rows:writer.writerow([r['code'],self.product.text(),self.batch.currentText()])
                    self.notify('Target pallet diekspor.')
                except OSError as exc:MessageBox.warning(dialog,'Ekspor gagal',str(exc))
        row=QHBoxLayout();layout.addLayout(row)
        for label,call in [('Pilih semua',select_all),('Simpan list',save_list),('Impor CSV',import_file),('Ekspor CSV',export),('Tutup',dialog.accept)]:
            b=QPushButton(label);b.clicked.connect(call);row.addWidget(b)
        load();dialog.exec()

    def paint_content(self):
        steps=[('DATA TARGET','Memuat daftar '+self.cfg['child'].lower()+' target untuk satu pallet.','revision'),('SCAN LABEL '+self.cfg['child'],'Memindai kode '+self.cfg['child'].lower()+' yang akan masuk ke pallet.','barcode'),('PRINTER LABEL PALLET','Mencetak label pallet / kode agregasi.','printer'),('VERIFIKASI KAMERA','Memeriksa gambar dan hasil scan label pallet.','camera')]
        for i,(title,desc,ico) in enumerate(steps):
            x=15+i*274;self.panel(x,84,258,94);self.rect(x+12,96,24,24,'#eff7ff','#eff7ff','#7acaed',2)
            self.text(x+12,96,24,24,str(i+1),14,'#123d5c',True,Qt.AlignmentFlag.AlignCenter);self.text(x+45,97,203,23,title,12,WHITE,True)
            self.text(x+46,126,154,42,desc,11,MUTED,wrap=True);self.icon(ico,x+216,123,31)
            if i<3:self.text(x+259,117,15,24,'›',24,'#176282',True,Qt.AlignmentFlag.AlignCenter)
        self.panel(15,193,1080,483);self.text(28,198,350,26,'AGREGASI '+self.cfg['child']+' KE PALLET',14,WHITE,True)
        self.text(415,199,520,25,'KODE PALLET SAAT INI: '+(self.run['parent_code'] if self.run else 'BELUM DIBUKA'),11,GREEN,True)
        self.text(995,199,86,25,str(self.cfg['capacity'])+' '+self.cfg['child'],10,MUTED,align=Qt.AlignmentFlag.AlignRight);self.line(26,228,1057)
        for i in range(self.GRID_SIZE):
            n=self.grid_page*self.GRID_SIZE+i;row,col=divmod(i,6);x=32+col*175;y=234+row*102;filled=n<len(self.child_codes);exists=n<self.cfg['capacity'];scanning=exists and n==self.filled and self.scanning
            self.cell_buttons[i].setVisible(exists);self.cell_buttons[i].setToolTip(self.child_codes[n] if filled else f'Carton {n+1}')
            if not exists:continue
            self.rect(x,y,168,96,'#09834a' if filled else '#095687' if scanning else '#466c85','#035330' if filled else '#023d67' if scanning else '#274c65','#57d061' if filled else '#29b7f5' if scanning else '#7497b0',4)
            self.text(x+10,y+5,46,22,str(n+1).zfill(2),16,WHITE,True)
            if filled:
                self.dot(x+141,y+9,GREEN,size=18)
                try:
                    from .label_render import encoded_symbol
                    pattern=encoded_symbol('barcode',self.child_codes[n]);unit=126/len(pattern)
                    self.p.setPen(Qt.PenStyle.NoPen);self.p.setBrush(QColor('#ecf8ef'))
                    for bit,value in enumerate(pattern):
                        if value=='1':self.p.drawRect(QRectF(x+21+bit*unit,y+35,unit,27))
                except ValueError:self.icon('barcode',x+66,y+30,40)
                self.text(x+5,y+70,158,22,self.child_codes[n],11,WHITE,True,Qt.AlignmentFlag.AlignCenter)
            elif scanning:
                self.p.setPen(QPen(QColor('#34cfff'),2,Qt.PenStyle.DashLine));self.p.setBrush(Qt.BrushStyle.NoBrush);self.p.drawRoundedRect(QRectF(x+1,y+1,166,94),4,4)
                for dot in range(10):
                    a=(dot+self.phase)*math.pi/5;color=QColor('#f1f8ff');color.setAlpha(60+dot*19);self.p.setBrush(color);self.p.setPen(Qt.PenStyle.NoPen)
                    self.p.drawEllipse(QPointF(x+84+15*math.cos(a),y+44+15*math.sin(a)),2,2)
                self.text(x+1,y+70,166,22,'SCANNING…',11,WHITE,True,Qt.AlignmentFlag.AlignCenter)
            else:self.text(x,y+34,168,32,'—',23,MUTED,align=Qt.AlignmentFlag.AlignCenter)
        capacity=self.cfg['capacity'];ratio=self.filled/capacity
        self.text(28,651,116,19,'PROGRES AGREGASI',10,MUTED,True);self.rect(155,653,600,12,'#103a55','#09283d','#387392',6)
        if self.filled:self.rect(157,655,596*ratio,8,BLUE,'#0085c5',BLUE,4)
        if self.filled:
            self.p.save();clip=QPainterPath();clip.addRoundedRect(QRectF(157,655,596*ratio,8),4,4);self.p.setClipPath(clip,Qt.ClipOperation.IntersectClip)
            self.p.setPen(Qt.PenStyle.NoPen);self.p.setBrush(QColor(160,227,255,75))
            for stripe in range(148,755,20):self.p.drawPolygon(QPolygonF([QPointF(stripe,663),QPointF(stripe+8,655),QPointF(stripe+18,655),QPointF(stripe+10,663)]))
            self.p.restore()
        self.text(768,648,214,23,f'{self.filled}/{capacity} {self.cfg["child"]} ({ratio*100:.1f}%)',11);self.text(982,648,101,23,f'CACHE: {self.cache_count}',10,align=Qt.AlignmentFlag.AlignRight)
        self.panel(15,685,336,202,'PILIH TEMPLATE / BATCH / LIST DATA');self.panel(357,685,364,202,'DATA '+self.cfg['child']+' TER-SCAN • 5 TERAKHIR');self.panel(727,685,368,202,'HASIL AGREGASI PALLET')
        for y,label in [(720,'TEMPLATE'),(749,'PRODUK'),(778,'BATCH'),(807,'LIST DATA')]:self.text(28,y,69,24,label,10,MUTED)
        self.text(28,866,306,19,f'● {self.filled}/{capacity} {self.cfg["child"].lower()}   •   CACHE {self.cache_count}   •   '+('READY' if self.scanning else 'SIAP' if self.run else 'PILIH TEMPLATE'),9,GREEN)
        self.panel(15,893,1080,97);self.text(29,908,106,25,'KONTROL LINE',11,WHITE,True);self.text(787,910,128,24,'MODE: '+self.store.get('mode','AGGREGATION'),10,GREEN,True)
        self.text(28,952,35,28,'MFD',11);self.text(198,952,40,28,'SCAN',10);self.text(514,948,567,36,self.message,10,GREEN if self.message.startswith(('VALID','Sesi siap','Verifikasi')) else YELLOW,wrap=True)

    def sidebar(self):
        from .shared_sidebar import paint_sidebar
        paint_sidebar(self)
