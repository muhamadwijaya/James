"""Complete BOX workstation backed by saved aggregation sessions."""
import csv
import math
from copy import deepcopy
from PySide6.QtCore import Qt,QDate,QRectF
from PySide6.QtGui import QColor,QPainter,QPen,QPixmap
from PySide6.QtWidgets import QDateEdit,QTableWidgetItem,QPushButton,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QSpinBox
from .pages import PageBase,OperationPage
from .upload_page import SendPage
from .box_model import BoxRepository
from .dashboard import WHITE,MUTED,GREEN,RED,YELLOW,BLUE
from .label_render import render_image
from .ui_dialogs import AppDialog,FileDialog,MessageBox

GRID=dict(x=27,y=234,w=96,h=36,gap_x=7,gap_y=3,cols=5,rows=10)
PREVIEW=QRectF(577,253,506,168)


class BoxPage(OperationPage):
    button=SendPage.button
    def __init__(self,store):
        PageBase.__init__(self,store,'box','Agregasi Box','PEMINDAHAN & VERIFIKASI UNIT PRODUK','BOX')
        self.stage='BOX';self.cfg=dict(self.CONFIG['BOX']);self.filled=0;self.run=None;self.repo=None;self.grid_page=0;self.scanning=False
        self.child_codes=[];self.recent_children=[];self.result_rows=[];self.message='Pilih template aktif, batch dan list data lalu kunci data.';self.buttons={};self.verification_dialog=None
        self._preview_key=None;self._preview_image=None;self._preview_error=''
        self.template_selector=self.combo(99,720,235,24,[]);self.template_selector.setObjectName('box_template')
        self.product=self.field(99,749,235,24,'','Produk mengikuti template');self.product.setObjectName('box_product');self.product.setReadOnly(True)
        self.product.setStyleSheet(self.product.styleSheet()+' QLineEdit {color:#bcd8ec;background:#03202f;}')
        self.batch=self.combo(99,778,235,24,[store.get('batch')]);self.batch.setEditable(True);self.batch.setObjectName('box_batch')
        self.target_list=self.combo(99,807,235,24,[]);self.target_list.setObjectName('box_target_list')
        self.inputs=(self.template_selector,self.batch,self.target_list)
        self.button('stage_lock',28,838,306,29,'KUNCI DATA','lock')
        self.scan_table=self.table(370,723,338,147,['WAKTU','SERIAL UNIT','STATUS'],[67,188,75]);self.scan_table.verticalHeader().setDefaultSectionSize(23);self.scan_table.horizontalHeader().setFixedHeight(25)
        self.result_table=self.table(740,723,341,147,['WAKTU','KODE BOX','STATUS'],[66,186,80]);self.result_table.verticalHeader().setDefaultSectionSize(23);self.result_table.horizontalHeader().setFixedHeight(25)
        self.scan_table.cellDoubleClicked.connect(self.scan_detail);self.result_table.cellDoubleClicked.connect(self.result_detail)
        for spec in [('stage_start_scan',139,899,146,43,'START SCAN','play','green'),('stage_print_label',297,899,153,43,'PRINT LABEL','printer','blue'),('stage_reset',462,899,143,43,'RESET BOX','sync','gold'),('stage_close_box',617,899,161,43,'KUNCI BOX','lock','blue'),('stage_upload',923,899,158,43,'UPLOAD INSTAN','upload','blue')]:self.button(*spec)
        self.button('stage_verify',903,594,180,28,'VERIFIKASI BOX','check_circle','green')
        self.camera_view=QLabel('Menunggu gambar kamera scanner…',self);self.camera_view.setGeometry(577,489,506,114)
        self.camera_view.setAlignment(Qt.AlignmentFlag.AlignCenter);self.camera_view.setWordWrap(True)
        self.camera_view.setStyleSheet('QLabel {color:#bcd8ec;background:#04202f;border:1px solid #2c5a75;border-radius:4px;font-size:11px;}');self.camera_view.hide()
        self.mfd=QDateEdit(QDate.currentDate(),self);self.mfd.setDisplayFormat('dd/MM/yyyy');self.mfd.setCalendarPopup(True);self.mfd.setGeometry(65,951,124,29);self.mfd.setStyleSheet('QDateEdit {color:#edf5ff;background:#04283f;border:1px solid #3f6780;padding:3px;}')
        self.scan_input=self.field(240,951,225,29,'','Scan serial unit / Enter');self.scan_input.setMaxLength(500);self.scan_input.setObjectName('box_scan_input');self.scan_input.returnPressed.connect(self.scan)
        for i,name in enumerate(('box_targets','box_scan_step','box_print_step','box_verify')):self.hotspot(name,15+i*274,84,258,94)
        self.button('grid_prev',430,199,27,25,'‹','',flat=True);self.button('grid_next',458,199,27,25,'›','',flat=True)
        self.cell_buttons=[]
        for i in range(GRID['cols']*GRID['rows']):
            row,col=divmod(i,GRID['cols']);b=self.hotspot('box_cell_'+str(i),GRID['x']+col*(GRID['w']+GRID['gap_x']),GRID['y']+row*(GRID['h']+GRID['gap_y']),GRID['w'],GRID['h']);self.cell_buttons.append(b)
        self.template_selector.currentIndexChanged.connect(self.template_changed);self.batch.currentTextChanged.connect(self.batch_changed)
        self.action.connect(self.local_action)

    def configure_templates(self,runtime,print_callback):
        self.runtime=runtime;self.print_callback=print_callback;self.repo=BoxRepository(self.store,runtime)
        self.settings_runtime.changed.connect(self.refresh);self.settings_runtime.message.connect(self.notify)
        self.settings_runtime.camera_frame.connect(self.show_camera_frame)
        self.refresh()
        identifier=self.store.get('box_current_run')
        if identifier:
            try:
                run=runtime.get(identifier)
                if run['state']!='CANCELLED':self.update_run(run);self.message='Sesi box sebelumnya dimuat kembali.'
            except ValueError:pass

    def notify(self,text):
        self.message=text;self.update()

    @staticmethod
    def fill_combo(combo,items,selected=None):
        previous=combo.currentData() if selected is None else selected
        combo.blockSignals(True);combo.clear()
        for label,data in items:combo.addItem(label,data)
        index=combo.findData(previous);combo.setCurrentIndex(index if index>=0 else 0);combo.blockSignals(False)

    # ------------------------------------------------------------------ inputs
    def template_changed(self,*_):
        if self.run:return
        self.refresh_choices()
        self.message='Template dipilih. Tentukan batch dan list data, lalu tekan KUNCI DATA.' if self.template_selector.currentData() else 'Pilih template box aktif untuk memulai.'
        self.update()

    def batch_changed(self,*_):
        if self.repo and not self.run:self.refresh_choices()

    def template_document(self,identifier):
        try:return self.runtime.repo.get(identifier)['document']
        except ValueError:return None

    def current_product(self):
        if self.run:return self.run['document'].get('child_product')
        identifier=self.template_selector.currentData()
        doc=self.template_document(identifier) if identifier else None
        return doc.get('child_product') if doc else None

    def refresh_choices(self):
        if not self.repo:return
        docs=[self.runtime.repo.get(row['id']) for row in self.runtime.repo.list('BOX')]
        # Only saved, active templates with a child product can aggregate units.
        ready=[(d['name'],d['id']) for d in docs if d['document'].get('active',True) and d['document'].get('child_product')]
        self.fill_combo(self.template_selector,[('Pilih template box…',None)]+ready)
        product=self.current_product()
        self.product.setText(product['name'] if product else '');self.product.setCursorPosition(0)
        lists=self.repo.lists(product,self.batch.currentText())
        self.fill_combo(self.target_list,[('SCAN LANGSUNG (tanpa list)',None)]+[(f"{r['name']} | {r['quantity']} unit",r['id']) for r in lists])
        identifier=self.template_selector.currentData()
        doc=self.run['document'] if self.run else (self.template_document(identifier) if identifier else None)
        if doc and not self.run:self.cfg.update(capacity=doc['aggregation_max'])

    def refresh(self):
        if not self.repo:return
        self.refresh_choices()
        if self.run:self.update_run(self.runtime.get(self.run['id']))
        self.recent_children=self.repo.recent();self.result_rows=self.repo.results()
        for table,rows,kind in [(self.scan_table,self.recent_children,'scan'),(self.result_table,self.result_rows,'result')]:
            table.setRowCount(len(rows))
            for i,row in enumerate(rows):
                status=row['status'] if kind=='scan' else ('AKTIF' if row['state']=='OPEN' else 'VALID' if row['verified'] else 'SELESAI')
                values=[row['ts'][11:19] if kind=='scan' else row['created_at'][11:19],row['code'] if kind=='scan' else row['parent_code'] or 'Belum bernomor',status]
                for j,value in enumerate(values):
                    item=QTableWidgetItem(str(value));item.setToolTip(str(value));table.setItem(i,j,item)
                    if j==2:item.setForeground(QColor(GREEN if status in ('VALID','SELESAI') else BLUE if status=='AKTIF' else YELLOW if status=='DUPLIKAT' else RED))
        self.apply_scan_mode()
        self.buttons['stage_lock'].setText('BUKA KUNCI DATA' if self.run else 'KUNCI DATA')
        self.update()

    # ----------------------------------------------------------------- scanner
    def scan_mode(self):
        runtime=getattr(self,'settings_runtime',None)
        if runtime is None:return 'SCANNER GUN'
        return runtime.repo.load()['scanners']['BOX'].get('mode','SCANNER GUN')

    def apply_scan_mode(self):
        camera=self.scan_mode()=='KAMERA IP'
        self.camera_view.setVisible(camera);self.buttons['stage_verify'].setVisible(not camera)

    def start_scanner(self):
        try:return self.settings_runtime.listen_scanner('BOX')
        except ValueError as exc:return str(exc)+' • Input manual tetap tersedia.'

    def stop_scanner(self):
        runtime=getattr(self,'settings_runtime',None)
        if runtime is None:return
        runtime.scanner_armed['BOX']=False;runtime.stop_scanner_camera('BOX')

    def show_camera_frame(self,level,image):
        if level!='BOX' or self.scan_mode()!='KAMERA IP' or image.isNull():return
        self.camera_view.setPixmap(QPixmap.fromImage(image).scaled(self.camera_view.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))

    # -------------------------------------------------------------- lock cycle
    def toggle_lock(self):
        if self.run:self.release_session('Data dibuka. Pilih template, batch dan list data untuk sesi berikutnya.');return
        identifier=self.template_selector.currentData()
        if not identifier:self.notify('Pilih template box aktif terlebih dahulu.');return
        try:
            self.grid_page=0;self.update_run(self.repo.start(identifier,self.batch.currentText(),self.mfd.text(),self.target_list.currentData()))
        except (ValueError,OverflowError) as exc:self.message=str(exc);self.update();return
        self.scanning=self.run['state']=='OPEN'
        self.message='Data terkunci pada template '+self.run['document']['name']+'. Scanner memverifikasi otomatis setiap unit yang benar.'
        if self.scanning:self.message=self.start_scanner()
        self.refresh();self.changed.emit()

    def release_session(self,message):
        if self.run:
            try:self.runtime.reset_empty(self.run['id'])
            except ValueError as exc:self.notify(str(exc));return False
        self.stop_scanner()
        self.run=None;self.filled=0;self.child_codes=[];self.grid_page=0;self.scanning=False;self.cfg=dict(self.CONFIG['BOX'])
        self.buttons['stage_start_scan'].setText('START SCAN');self._preview_key=None;self._preview_image=None
        for widget in self.inputs+(self.mfd,):widget.setEnabled(True)
        with self.store.db:self.store.put('box_current_run',None)
        self.refresh_choices();self.template_selector.blockSignals(True);self.template_selector.setCurrentIndex(0);self.template_selector.blockSignals(False)
        self.notify(message);self.refresh();self.changed.emit();return True

    def update_run(self,run):
        self.run=run;doc=run['document'];self.filled=run['quantity'];self.cfg.update(capacity=doc['aggregation_max'],code=run['parent_code'] or '—',child='UNIT')
        self.child_codes=[r[0] for r in self.store.db.execute('SELECT code FROM aggregation_children WHERE run_id=? ORDER BY rowid',(run['id'],))]
        meta=self.repo.meta(run['id'])
        self.refresh_choices()
        self.template_selector.blockSignals(True);self.template_selector.setCurrentIndex(self.template_selector.findData(run['template_id']));self.template_selector.blockSignals(False)
        self.product.setText((doc.get('child_product') or {}).get('name',doc['data'].get('product_name','')));self.product.setCursorPosition(0)
        self.batch.blockSignals(True);self.batch.setCurrentText(run['batch']);self.batch.blockSignals(False)
        self.target_list.blockSignals(True);self.target_list.setCurrentIndex(max(0,self.target_list.findData(meta.get('list_id'))));self.target_list.blockSignals(False)
        date=QDate.fromString(meta.get('mfd',doc['data']['mfg_date']),'dd/MM/yyyy')
        if date.isValid():self.mfd.setDate(date)
        # Locked session inputs are a snapshot; unlock is the explicit route out.
        for widget in self.inputs+(self.mfd,):widget.setEnabled(False)
        if run['state']!='OPEN':self.scanning=False
        self.buttons['stage_start_scan'].setText('STOP SCAN' if self.scanning else 'START SCAN')
        self.buttons['stage_lock'].setText('BUKA KUNCI DATA')
        self.update()

    def scan(self):
        if self.verification_dialog:
            self.verification_dialog.code.setText(self.scan_input.text());self.scan_input.clear();return
        code=self.scan_input.text().strip()
        if not code:self.notify('Pindai barcode atau masukkan serial unit terlebih dahulu.');return
        if not self.run:self.notify('Kunci data template terlebih dahulu sebelum memindai.');return
        if not self.scanning:self.notify('Scan dijeda. Tekan START SCAN untuk melanjutkan.');return
        try:
            self.update_run(self.repo.scan(self.run['id'],code));self.scan_input.clear();self.grid_page=(max(1,self.filled)-1)//(GRID['cols']*GRID['rows'])
            self.message=f'VALID • {self.filled}/{self.cfg["capacity"]} unit'
            if self.run['state']=='COMPLETE':
                if self.run['print_state']=='PENDING':
                    self.print_run(automatic=True)
                    if self.run['print_state']=='SENT':self.message=f'Target maksimum {self.cfg["capacity"]} unit tercapai • label agregasi dicetak otomatis.'
                else:self.message='Box penuh dan dikunci. Cetak label untuk melanjutkan.'
        except ValueError as exc:self.message=str(exc);self.scan_input.selectAll()
        self.refresh();self.changed.emit()

    def local_action(self,name):
        if name in ('stage_start_scan','box_scan_step'):
            if self.scan_input.text().strip():
                if self.run and self.run['state']=='OPEN':self.scanning=True
                self.scan();return
            if not self.run:self.notify('Kunci data template terlebih dahulu.');return
            if self.run['state']!='OPEN':self.notify('Box sudah selesai. Gunakan RESET BOX untuk sesi berikutnya.');return
            self.scanning=not self.scanning
            if self.scanning:
                self.message=self.start_scanner();self.scan_input.setFocus()
            else:
                self.stop_scanner();self.message='Scan dijeda. Data sesi tetap tersimpan.'
            self.buttons['stage_start_scan'].setText('STOP SCAN' if self.scanning else 'START SCAN');self.update()
        elif name=='stage_lock':self.toggle_lock()
        elif name=='stage_close_box':
            if not self.run:self.notify('Kunci data dan scan unit terlebih dahulu.');return
            try:
                self.update_run(self.runtime.finish_partial(self.run['id']));self.stop_scanner()
                self.message='Box dikunci. Cetak label lalu lakukan verifikasi.'
                if self.run['print_state']=='PENDING':self.print_run(automatic=True)
                self.refresh();self.changed.emit()
            except ValueError as exc:self.notify(str(exc))
        elif name in ('stage_print_label','box_print_step'):self.print_run()
        elif name=='stage_reset':self.release_session('Pilih template dan list data untuk membuka box berikutnya.')
        elif name=='stage_upload':self.settings_runtime.upload(level='BOX')
        elif name=='box_targets':self.show_targets()
        elif name in ('stage_verify','box_verify'):self.verify_dialog(self.pending_box() or self.run)
        elif name in ('grid_prev','grid_next'):
            per_page=GRID['cols']*GRID['rows']
            self.grid_page=max(0,min(math.ceil(self.cfg['capacity']/per_page)-1,self.grid_page+(-1 if name=='grid_prev' else 1)));self.update()
        elif name.startswith('box_cell_'):
            n=self.grid_page*GRID['cols']*GRID['rows']+int(name.rsplit('_',1)[1])
            if n<len(self.child_codes):MessageBox.information(self,'Detail unit',f'Urutan: {n+1}\nSerial: {self.child_codes[n]}\nBox: {self.cfg["code"]}\nBatch: {self.run["batch"]}\nStatus: VALID')

    def print_run(self,automatic=False):
        if not self.run:self.notify('Pilih box terlebih dahulu.');return
        if self.run['state']!='COMPLETE':self.notify('Kunci box sebelum mencetak label.');return
        if self.run['print_state']=='SENT' and not automatic:
            if MessageBox.question(self,'Cetak ulang','Cetak ulang label '+self.run['parent_code']+'?')!=MessageBox.StandardButton.Yes:return
            try:
                if self.print_callback(self.runtime.print_document(self.run['id']),self.run['template_id'],False):
                    with self.store.db:self.store.audit('REPRINT BOX',self.run['parent_code'])
                    self.notify('Label box dicetak ulang.')
            except Exception as exc:self.notify(str(exc))
        else:OperationPage.print_run(self,automatic)
        self.refresh();self.changed.emit()

    # ------------------------------------------------------- verification data
    def pending_box(self):
        """The locked box whose master data still waits for operator verification."""
        if not self.repo:return None
        if self.run and self.run['state']=='COMPLETE' and not self.repo.meta(self.run['id']).get('verified'):return self.run
        for row in self.result_rows:
            if row['state']=='COMPLETE' and not row['verified']:
                try:return self.runtime.get(row['id'])
                except ValueError:return None
        return None

    def master_rows(self,run):
        doc=run['document'];meta=self.repo.meta(run['id'])
        product=(doc.get('child_product') or {}).get('name') or doc['data'].get('product_name','—')
        state={'WAITING':'MENUNGGU CETAK','PENDING':'ANTRE CETAK OTOMATIS','SENDING':'SEDANG DICETAK','SENT':'LABEL TERCETAK','ERROR':'CETAK GAGAL'}.get(run['print_state'],run['print_state'])
        return [('KODE BOX',run['parent_code'] or 'Belum bernomor'),('PRODUK',product),('BATCH / MFD',run['batch']+'  •  '+meta.get('mfd',doc['data']['mfg_date'])),
                ('ISI BOX',f"{run['quantity']} / {doc['aggregation_max']} UNIT"),
                ('STATUS','TERVERIFIKASI' if meta.get('verified') else state+' • MENUNGGU VERIFIKASI')]

    # ------------------------------------------------------------ print preview
    def preview_image(self):
        if not self.run:return None
        key=(self.run['id'],self.run['parent_code'],self.filled,self.run['document']['name'],self.run['document']['width_mm'],self.run['document']['height_mm'])
        if key!=self._preview_key:
            self._preview_key=key;self._preview_image=None;self._preview_error=''
            doc=deepcopy(self.run['document'])
            doc['data'].update(serial=self.run['parent_code'] or doc['data'].get('serial',''),batch=self.run['batch'],quantity=f"{self.filled} {doc['child_level']}")
            try:self._preview_image=render_image(doc,150)
            except Exception as exc:self._preview_error='Label belum dapat dirender: '+str(exc)
        return self._preview_image

    def draw_preview(self):
        image=self.preview_image()
        if image is None or image.isNull():
            self.text(PREVIEW.x(),PREVIEW.y()+PREVIEW.height()/2-26,PREVIEW.width(),52,self._preview_error or 'Kunci data template untuk menampilkan label print yang akan dicetak.',11,MUTED,wrap=True,align=Qt.AlignmentFlag.AlignCenter);return
        size=image.size().scaled(int(PREVIEW.width()-16),int(PREVIEW.height()-16),Qt.AspectRatioMode.KeepAspectRatio)
        target=QRectF(PREVIEW.center().x()-size.width()/2,PREVIEW.center().y()-size.height()/2,size.width(),size.height())
        self.p.save();self.p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,True)
        self.p.fillRect(target,Qt.GlobalColor.white);self.p.drawImage(target,image)
        self.p.setPen(QPen(QColor('#8fc7e6'),1));self.p.setBrush(Qt.BrushStyle.NoBrush);self.p.drawRect(target);self.p.restore()

    # ------------------------------------------------------------------ dialogs
    def scan_detail(self,row,*_):
        if row<len(self.recent_children):
            r=self.recent_children[row];MessageBox.information(self,'Detail scan',f"{r['code']}\n{r['ts']}\n{r['status']}\n{r['note']}")

    def result_detail(self,row,*_):
        if row>=len(self.result_rows):return
        run=self.runtime.get(self.result_rows[row]['id']);dialog=AppDialog(self);dialog.setWindowTitle('Hasil agregasi box');dialog.resize(550,350);layout=QVBoxLayout(dialog)
        info=QLabel(f"{run['parent_code']}\nBatch: {run['batch']}\nIsi: {run['quantity']} unit\nStatus: {run['state']} | Cetak: {run['print_state']}");layout.addWidget(info)
        children=self.store.db.execute('SELECT code FROM aggregation_children WHERE run_id=? ORDER BY rowid',(run['id'],)).fetchall();codes=QLabel('\n'.join(r[0] for r in children[:10])+ ('\n…' if len(children)>10 else ''));layout.addWidget(codes)
        rowbox=QHBoxLayout();layout.addLayout(rowbox)
        def pdf():
            path,_=FileDialog.getSaveFileName(dialog,'Simpan label PDF',run['parent_code']+'.pdf','PDF (*.pdf)')
            if path:
                try:
                    from .label_render import export_pdf
                    export_pdf(self.runtime.print_document(run['id']),path);self.notify('PDF label tersimpan.');dialog.accept()
                except Exception as exc:MessageBox.warning(dialog,'Label belum siap',str(exc))
        for label,call in [('Ekspor label PDF',pdf),('Verifikasi',lambda:self.verify_dialog(run)),('Tutup',dialog.accept)]:
            b=QPushButton(label);b.clicked.connect(call);rowbox.addWidget(b)
        dialog.exec()

    def verify_dialog(self,run):
        if not run or run['state']!='COMPLETE':self.notify('Kunci box lalu cetak label sebelum verifikasi.');return
        if run['print_state']!='SENT':self.notify('Cetak label box sebelum verifikasi.');return
        dialog=AppDialog(self);dialog.setWindowTitle('Verifikasi kamera / label box');dialog.resize(610,350);layout=QVBoxLayout(dialog)
        label=QLabel(f"Box: {run['parent_code']}\nPeriksa gambar kamera dan isi box, lalu scan ulang label. Verifikasi dicatat atas nama operator.");label.setWordWrap(True);layout.addWidget(label)
        dialog.code=QLineEdit();dialog.code.setPlaceholderText('Scan kode label box');layout.addWidget(dialog.code)
        count=QSpinBox();count.setRange(0,1000000);count.setPrefix('Jumlah unit diperiksa: ');layout.addWidget(count)
        error=QLabel();error.setWordWrap(True);layout.addWidget(error)
        def camera():
            from .settings_dialogs import CameraCalibration
            cam=CameraCalibration(self.settings_runtime,dialog);cam.start();cam.exec()
        def verify():
            try:self.repo.verify(run['id'],dialog.code.text(),count.value());dialog.accept();self.notify('Verifikasi box VALID tersimpan.');self.refresh();self.changed.emit()
            except ValueError as exc:error.setText(str(exc))
        row=QHBoxLayout();layout.addLayout(row)
        for title,call in [('Buka kamera',camera),('Simpan verifikasi',verify),('Batal',dialog.reject)]:
            b=QPushButton(title);b.clicked.connect(call);row.addWidget(b)
        self.verification_dialog=dialog
        try:dialog.exec()
        finally:self.verification_dialog=None

    def show_targets(self):
        dialog=AppDialog(self);dialog.setWindowTitle('Data target serial unit');dialog.resize(780,530);layout=QVBoxLayout(dialog)
        info=QLabel('Impor CSV dengan kolom serial. Produk mengikuti template terpilih dan batch mengikuti halaman Box. Pilih list untuk membatasi serial yang boleh dipindai.');info.setWordWrap(True);layout.addWidget(info)
        from PySide6.QtWidgets import QTableWidget
        grid=QTableWidget(0,2);grid.setHorizontalHeaderLabels(['SERIAL UNIT','STATUS']);grid.horizontalHeader().setStretchLastSection(True);grid.setColumnWidth(0,510);layout.addWidget(grid)
        def load():
            rows=self.store.db.execute("SELECT t.serial,CASE WHEN c.code IS NULL THEN 'BELUM SCAN' ELSE 'TERAGREGASI' END status FROM box_targets t LEFT JOIN aggregation_children c ON c.child_level='UNIT' AND c.code=t.serial WHERE t.list_id=? ORDER BY t.rowid LIMIT 1000",(self.target_list.currentData(),)).fetchall();grid.setRowCount(len(rows))
            for i,r in enumerate(rows):
                for j in range(2):grid.setItem(i,j,QTableWidgetItem(r[j]))
            grid.setEditTriggers(grid.EditTrigger.NoEditTriggers)
        def import_file():
            if self.run:self.notify('Buka kunci data terlebih dahulu sebelum mengganti target.');dialog.accept();return
            path,_=FileDialog.getOpenFileName(dialog,'Impor target unit','','CSV (*.csv)')
            if path:
                try:
                    identifier=self.repo.import_targets(path,self.current_product(),self.batch.currentText());self.refresh_choices();self.target_list.setCurrentIndex(self.target_list.findData(identifier));load();self.notify('List target berhasil diimpor.')
                except (ValueError,OSError,csv.Error) as exc:MessageBox.warning(dialog,'Impor gagal',str(exc))
        def export():
            path,_=FileDialog.getSaveFileName(dialog,'Ekspor target unit','target-unit.csv','CSV (*.csv)')
            if path:
                try:
                    with open(path,'w',newline='',encoding='utf-8-sig') as handle:
                        writer=csv.writer(handle);writer.writerow(['serial','product','batch'])
                        for r in self.store.db.execute('SELECT serial FROM box_targets WHERE list_id=? ORDER BY rowid',(self.target_list.currentData(),)):writer.writerow([r[0],self.product.text(),self.batch.currentText()])
                    self.notify('Target unit diekspor.')
                except OSError as exc:MessageBox.warning(dialog,'Ekspor gagal',str(exc))
        row=QHBoxLayout();layout.addLayout(row)
        for label,call in [('Impor CSV',import_file),('Ekspor CSV',export),('Tutup',dialog.accept)]:
            b=QPushButton(label);b.clicked.connect(call);row.addWidget(b)
        layout.addWidget(QLabel('Pratinjau maksimal 1.000 serial; seluruh serial tetap digunakan untuk validasi.'));load();dialog.exec()

    # -------------------------------------------------------------------- paint
    def paint_content(self):
        steps=[('DATA TARGET','Memuat daftar serial unit untuk proses agregasi box.','revision'),('SCAN UNIT','Memindai serial number unit satu per satu.','barcode'),('PRINTER LABEL BOX','Mencetak label box / kode agregasi.','printer'),('VERIFIKASI KAMERA','Memeriksa gambar dan hasil scan label box.','camera')]
        for i,(title,desc,ico) in enumerate(steps):
            x=15+i*274;self.panel(x,84,258,94);self.rect(x+12,96,24,24,'#eff7ff','#eff7ff','#7acaed',2)
            self.text(x+12,96,24,24,str(i+1),14,'#123d5c',True,Qt.AlignmentFlag.AlignCenter);self.text(x+45,97,203,23,title,12,WHITE,True)
            self.text(x+46,126,154,42,desc,11,MUTED,wrap=True);self.icon(ico,x+216,123,31)
            if i<3:self.text(x+259,117,15,24,'›',24,'#176282',True,Qt.AlignmentFlag.AlignCenter)
        per_page=GRID['cols']*GRID['rows']
        self.panel(15,193,540,440);self.text(28,198,290,26,'AGREGASI UNIT KE BOX',14,WHITE,True)
        self.text(330,199,95,25,str(self.cfg['capacity'])+' UNIT',10,MUTED,align=Qt.AlignmentFlag.AlignRight)
        self.text(490,199,53,25,f'{self.grid_page+1}/{max(1,math.ceil(self.cfg["capacity"]/per_page))}',9,MUTED,align=Qt.AlignmentFlag.AlignRight);self.line(26,228,516)
        for i in range(per_page):
            n=self.grid_page*per_page+i;row,col=divmod(i,GRID['cols']);x=GRID['x']+col*(GRID['w']+GRID['gap_x']);y=GRID['y']+row*(GRID['h']+GRID['gap_y'])
            filled=n<len(self.child_codes);exists=n<self.cfg['capacity'];scanning=exists and n==self.filled and self.scanning
            self.cell_buttons[i].setVisible(exists);self.cell_buttons[i].setToolTip(self.child_codes[n] if filled else f'Unit {n+1}')
            if not exists:continue
            self.rect(x,y,GRID['w'],GRID['h'],'#09834a' if filled else '#095687' if scanning else '#466c85','#035330' if filled else '#023d67' if scanning else '#274c65','#57d061' if filled else '#29b7f5' if scanning else '#7497b0',4)
            self.text(x+6,y+2,26,15,str(n+1).zfill(2),9,WHITE,True)
            if filled:
                self.dot(x+GRID['w']-17,y+3,GREEN,size=12);self.text(x+3,y+17,GRID['w']-6,16,self.child_codes[n],8,WHITE,True,Qt.AlignmentFlag.AlignCenter)
            elif scanning:
                self.icon('sync',x+GRID['w']/2-8,y+3,16);self.text(x+2,y+19,GRID['w']-4,15,'SCANNING…',8,WHITE,True,Qt.AlignmentFlag.AlignCenter)
            else:self.text(x,y+9,GRID['w'],18,'—',14,MUTED,align=Qt.AlignmentFlag.AlignCenter)
        self.paint_print_template();self.paint_master_data()
        capacity=self.cfg['capacity'];ratio=min(1,self.filled/capacity)
        self.panel(15,637,1080,42)
        self.text(28,647,150,22,'PROGRES AGREGASI',10,MUTED,True);self.rect(185,651,560,12,'#103a55','#09283d','#387392',6)
        if self.filled:self.rect(187,653,556*ratio,8,BLUE,'#0085c5',BLUE,4)
        self.text(757,645,200,23,f'{self.filled}/{capacity} UNIT ({ratio*100:.1f}%)',11)
        self.text(950,645,133,23,f'MAX TEMPLATE {capacity}',10,GREEN if self.filled>=capacity else MUTED,True,Qt.AlignmentFlag.AlignRight)
        self.panel(15,685,336,202,'PILIH TEMPLATE / BATCH / LIST DATA');self.panel(357,685,364,202,'DATA SCAN • 5 TERAKHIR');self.panel(727,685,368,202,'HASIL AGREGASI BOX')
        for y,label in [(720,'TEMPLATE'),(749,'PRODUK'),(778,'BATCH'),(807,'LIST DATA')]:self.text(28,y,69,24,label,10,MUTED)
        self.text(28,866,306,19,f'● {self.filled}/{capacity} unit   •   '+('TERKUNCI' if self.run else 'BELUM DIKUNCI')+'   •   '+('READY' if self.scanning else 'SIAP' if self.run else 'PILIH TEMPLATE'),9,GREEN if self.run else YELLOW)
        self.panel(15,893,1080,97);self.text(29,908,106,25,'KONTROL LINE',11,WHITE,True);self.text(787,910,128,24,'MODE: '+self.store.get('mode','AGGREGATION'),10,GREEN,True)
        self.text(28,952,35,28,'MFD',11);self.text(198,952,40,28,'SCAN',10);self.text(478,948,603,36,self.message,10,GREEN if self.message.startswith(('VALID','Sesi siap','Verifikasi','Data terkunci','Target maksimum')) else YELLOW,wrap=True)

    def paint_print_template(self):
        doc=self.run['document'] if self.run else None
        self.panel(565,193,530,258,'TEMPLATE PRINT TERKUNCI')
        title=doc['name'] if doc else 'Belum ada template terkunci'
        self.text(577,232,330,18,title,10,WHITE if doc else MUTED,True)
        self.text(907,232,176,18,'KODE BOX: '+(self.run['parent_code'] if self.run and self.run['parent_code'] else 'BELUM DIBUKA'),9,GREEN if self.run else MUTED,align=Qt.AlignmentFlag.AlignRight)
        self.rect(PREVIEW.x(),PREVIEW.y(),PREVIEW.width(),PREVIEW.height(),'#0a2b41','#041c2c','#2f5b76',4)
        self.draw_preview()
        if doc:
            printer='TIJ '+(doc.get('printer_host') or '—')+':'+str(doc.get('printer_port',9100)) if doc.get('printer_kind')=='TIJ' else 'PRINTER LABEL'
            self.text(577,426,506,18,f"{doc['width_mm']:g} × {doc['height_mm']:g} mm • {doc['dpi']} DPI • {printer} • CETAK OTOMATIS SAAT MAX",9,MUTED)

    def paint_master_data(self):
        camera=self.scan_mode()=='KAMERA IP'
        if camera:
            profile=self.settings_runtime.repo.load()['scanners']['BOX']
            self.panel(565,459,530,174,'KAMERA SCANNER • '+str(profile.get('camera_ip',''))+':'+str(profile.get('camera_port','')))
            status=self.settings_runtime.status.get('scanner_BOX',{})
            self.text(577,608,506,18,'STATUS KAMERA: '+status.get('status','BELUM DITES'),9,GREEN if status.get('status')=='KAMERA ONLINE' else MUTED);return
        self.panel(565,459,530,174,'DATA MASTER BOX • MENUNGGU VERIFIKASI')
        run=self.pending_box()
        if not run:
            self.text(577,520,506,40,'Belum ada box menunggu verifikasi. Kunci box atau capai target maksimum untuk membuat data master.',10,MUTED,wrap=True,align=Qt.AlignmentFlag.AlignCenter);return
        for i,(label,value) in enumerate(self.master_rows(run)):
            y=496+i*23;self.text(577,y,110,20,label,9,MUTED)
            self.text(693,y,320 if i<4 else 200,20,str(value),10,GREEN if label=='STATUS' and 'TERVERIFIKASI' in str(value) else WHITE)

    def sidebar(self):
        from .shared_sidebar import paint_sidebar
        paint_sidebar(self)
