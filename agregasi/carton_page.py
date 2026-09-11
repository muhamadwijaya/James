"""Complete CARTON workstation backed by saved aggregation sessions."""
import csv
import math
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt,QDate,QRectF
from PySide6.QtGui import QColor,QPen
from PySide6.QtWidgets import QDateEdit,QTableWidgetItem,QPushButton,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QSpinBox
from .pages import PageBase,OperationPage
from .upload_page import SendPage
from .carton_model import CartonRepository,product_key
from .dashboard import WHITE,MUTED,GREEN,RED,YELLOW,BLUE
from .sidebar_layout import fixed_sidebar,SIDEBAR
from .settings_model import VERSION
from .ui_dialogs import AppDialog,FileDialog,MessageBox


class CartonPage(OperationPage):
    button=SendPage.button
    def __init__(self,store):
        PageBase.__init__(self,store,'carton','Agregasi Carton','PENYUSUNAN BOX KE CARTON','CARTON')
        self.stage='CARTON';self.cfg=dict(self.CONFIG['CARTON']);self.filled=0;self.run=None;self.repo=None;self.grid_page=0;self.scanning=False
        self.child_codes=[];self.recent_children=[];self.result_rows=[];self.message='Pilih produk, batch dan template untuk memulai carton.';self.buttons={};self.verification_dialog=None
        self.product=self.combo(99,720,235,24,[]);self.product.setObjectName('carton_product')
        self.batch=self.combo(99,749,235,24,[store.get('batch')]);self.batch.setEditable(True);self.batch.setObjectName('carton_batch')
        self.target_list=self.combo(99,778,235,24,[]);self.target_list.setObjectName('carton_target_list')
        self.template_selector=self.combo(99,807,235,24,[]);self.template_selector.setObjectName('carton_template')
        self.button('stage_lock',28,838,306,29,'KUNCI CARTON','lock')
        self.scan_table=self.table(370,723,338,147,['WAKTU','KODE BOX','STATUS'],[67,188,75]);self.scan_table.verticalHeader().setDefaultSectionSize(23);self.scan_table.horizontalHeader().setFixedHeight(25)
        self.result_table=self.table(740,723,341,147,['WAKTU','KODE CARTON','STATUS'],[66,186,80]);self.result_table.verticalHeader().setDefaultSectionSize(23);self.result_table.horizontalHeader().setFixedHeight(25)
        self.scan_table.cellDoubleClicked.connect(self.scan_detail);self.result_table.cellDoubleClicked.connect(self.result_detail)
        for spec in [('stage_start_scan',139,899,146,43,'START SCAN BOX','play','green'),('stage_print_label',297,899,153,43,'PRINT LABEL','printer','blue'),('stage_reset',462,899,143,43,'RESET CARTON','sync','gold'),('stage_conveyor',617,899,161,43,'START CONVEYOR','conveyor','blue'),('stage_upload',923,899,158,43,'UPLOAD INSTAN','upload','blue')]:self.button(*spec)
        upload=self.buttons['stage_upload'];upload.setStyleSheet(upload.styleSheet().replace('#076fac','#7844a9').replace('#03426b','#442565').replace('#249bd2','#a678ce'))
        self.mfd=QDateEdit(QDate.currentDate(),self);self.mfd.setDisplayFormat('dd/MM/yyyy');self.mfd.setCalendarPopup(True);self.mfd.setGeometry(65,951,124,29);self.mfd.setStyleSheet('QDateEdit {color:#edf5ff;background:#04283f;border:1px solid #3f6780;padding:3px;}')
        self.scan_input=self.field(240,951,225,29,'','Scan serial box / Enter');self.scan_input.setMaxLength(500);self.scan_input.setObjectName('carton_scan_input');self.scan_input.returnPressed.connect(self.scan)
        for i,name in enumerate(('carton_targets','carton_scan_step','carton_print_step','carton_verify')):self.hotspot(name,15+i*274,84,258,94)
        self.button('grid_prev',937,199,27,25,'‹','',flat=True);self.button('grid_next',965,199,27,25,'›','',flat=True)
        self.cell_buttons=[]
        for i in range(12):
            row,col=divmod(i,4);b=self.hotspot('carton_cell_'+str(i),40+col*260,244+row*136,240,120);self.cell_buttons.append(b)
        self.product.currentIndexChanged.connect(self.product_changed);self.batch.currentTextChanged.connect(self.batch_changed)
        self.template_selector.currentIndexChanged.connect(self.start_template);self.action.connect(self.local_action)

    def configure_templates(self,runtime,print_callback):
        self.runtime=runtime;self.print_callback=print_callback;self.repo=CartonRepository(self.store,runtime)
        self.settings_runtime.changed.connect(self.refresh);self.settings_runtime.message.connect(self.notify)
        self.refresh()
        if self.template_selector.count()<=1:self.message='Lengkapi template Carton dan relasi child di Master Template terlebih dahulu.'
        identifier=self.store.get('carton_current_run')
        if identifier:
            try:
                run=runtime.get(identifier)
                if run['state']!='CANCELLED':self.update_run(run);self.message='Sesi carton sebelumnya dimuat kembali.'
            except ValueError:pass

    def notify(self,text):
        self.message=text;self.update()

    @staticmethod
    def fill_combo(combo,items,selected=None):
        previous=combo.currentData() if selected is None else selected
        combo.blockSignals(True);combo.clear()
        for label,data in items:combo.addItem(label,data)
        index=combo.findData(previous);combo.setCurrentIndex(index if index>=0 else 0);combo.blockSignals(False)

    def product_changed(self,*_):
        if self.run and self.run['state']=='OPEN':return
        self.run=None;self.refresh_choices();self.refresh()

    def batch_changed(self,*_):
        if self.repo and not (self.run and self.run['state']=='OPEN'):self.refresh_choices()

    def refresh_choices(self):
        if not self.repo:return
        docs=self.repo.templates()
        products={product_key(d['product']):d['product'] for d in docs}
        self.fill_combo(self.product,[(p['name'],p) for p in products.values()])
        product=self.product.currentData()
        templates=[('Pilih template carton…',None)]+[(r['name']+' • '+r['document']['child_level'],r['id']) for r in docs if r['product']==product]
        self.fill_combo(self.template_selector,templates)
        lists=self.repo.lists(product,self.batch.currentText())
        self.fill_combo(self.target_list,[('SEMUA BOX SIAP / SCAN LANGSUNG',None)]+[(f"{r['name']} | {r['quantity']} box",r['id']) for r in lists])

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
        self.buttons['stage_conveyor'].setText('STOP CONVEYOR' if self.settings_runtime.conveyor_running else 'START CONVEYOR')
        self.update()

    def start_template(self,*_):
        if not self.repo:return
        identifier=self.template_selector.currentData()
        if not identifier:
            self.run=None;self.filled=0;self.child_codes=[];self.scanning=False;self.update();return
        try:
            self.grid_page=0;self.update_run(self.repo.start(identifier,self.batch.currentText(),self.mfd.text(),self.target_list.currentData()))
            self.scanning=self.run['state']=='OPEN';self.message='Sesi siap. Scan '+self.cfg['child'].lower()+' dengan scanner atau ketik kode lalu Enter.'
            if self.scanning:
                try:self.settings_runtime.listen_scanner('CARTON')
                except ValueError as exc:self.message='Sesi siap untuk input manual. Scanner: '+str(exc)
            self.refresh()
        except ValueError as exc:self.run=None;self.message=str(exc);self.update()

    def update_run(self,run):
        self.run=run;doc=run['document'];self.filled=run['quantity'];self.cfg.update(capacity=doc['aggregation_max'],code=run['parent_code'] or '—',child=doc['child_level'])
        self.child_codes=[r[0] for r in self.store.db.execute('SELECT code FROM aggregation_children WHERE run_id=? ORDER BY rowid',(run['id'],))]
        meta=self.repo.meta(run['id'])
        self.scan_input.setPlaceholderText('Scan '+doc['child_level'].lower()+' / Enter')
        self.subtitle='PENYUSUNAN '+doc['child_level']+' KE CARTON'
        self.scan_table.setHorizontalHeaderLabels(['WAKTU','KODE '+doc['child_level'],'STATUS'])
        self.product.blockSignals(True);self.product.setCurrentIndex(self.product.findData(self.repo.product_for(doc)));self.product.blockSignals(False)
        self.batch.blockSignals(True);self.batch.setCurrentText(run['batch']);self.batch.blockSignals(False)
        self.refresh_choices()
        self.template_selector.blockSignals(True);self.template_selector.setCurrentIndex(self.template_selector.findData(run['template_id']));self.template_selector.blockSignals(False)
        self.target_list.blockSignals(True);self.target_list.setCurrentIndex(max(0,self.target_list.findData(meta.get('list_id'))));self.target_list.blockSignals(False)
        date=QDate.fromString(meta.get('mfd',doc['data']['mfg_date']),'dd/MM/yyyy')
        if date.isValid():self.mfd.setDate(date)
        # Session inputs are a snapshot; reset is the explicit route to another session.
        for widget in (self.product,self.batch,self.target_list,self.template_selector,self.mfd):widget.setEnabled(False)
        if run['state']!='OPEN':self.scanning=False
        self.buttons['stage_start_scan'].setText(('STOP SCAN' if self.scanning else 'START SCAN')+' '+self.cfg['child'])
        self.update()

    def scan(self):
        if self.verification_dialog:
            self.verification_dialog.code.setText(self.scan_input.text());self.scan_input.clear();return
        code=self.scan_input.text().strip()
        if not code:self.notify('Pindai barcode atau masukkan serial box terlebih dahulu.');return
        if not self.run:self.notify('Pilih template carton terlebih dahulu.');return
        if not self.scanning:self.notify('Scan dijeda. Tekan START SCAN untuk melanjutkan.');return
        try:
            self.update_run(self.repo.scan(self.run['id'],code));self.scan_input.clear();self.grid_page=(max(1,self.filled)-1)//12
            self.message=f'VALID • {self.filled}/{self.cfg["capacity"]} {self.cfg["child"].lower()}'
            if self.run['state']=='COMPLETE':
                if self.run['print_state']=='PENDING':self.print_run(automatic=True)
                else:self.message='Carton penuh dan dikunci. Cetak label untuk melanjutkan.'
        except ValueError as exc:self.message=str(exc);self.scan_input.selectAll()
        self.refresh();self.changed.emit()

    def local_action(self,name):
        if name in ('stage_start_scan','carton_scan_step'):
            if self.scan_input.text().strip():
                if self.run and self.run['state']=='OPEN':self.scanning=True
                self.scan();return
            if not self.run:self.start_template()
            if not self.run:self.notify('Pilih template carton terlebih dahulu.');return
            if self.run['state']!='OPEN':self.notify('Carton sudah selesai. Gunakan RESET CARTON untuk sesi berikutnya.');return
            self.scanning=not self.scanning
            if self.scanning:
                try:self.message=self.settings_runtime.listen_scanner('CARTON')
                except ValueError as exc:self.message=str(exc)+' • Input manual tetap tersedia.'
                self.scan_input.setFocus()
            else:
                self.settings_runtime.scanner_armed['CARTON']=False
                self.message='Scan dijeda. Data sesi tetap tersimpan.'
            self.buttons['stage_start_scan'].setText(('STOP SCAN' if self.scanning else 'START SCAN')+' '+self.cfg['child']);self.update()
        elif name=='stage_lock':
            if not self.run:self.notify('Pilih template dan scan box terlebih dahulu.');return
            try:self.update_run(self.repo.finish(self.run['id']));self.message='Carton dikunci. Cetak label lalu lakukan verifikasi.';self.refresh();self.changed.emit()
            except ValueError as exc:self.notify(str(exc))
        elif name in ('stage_print_label','carton_print_step'):self.print_run()
        elif name=='stage_reset':
            if self.run:
                try:self.runtime.reset_empty(self.run['id'])
                except ValueError as exc:self.notify(str(exc));return
            self.run=None;self.filled=0;self.child_codes=[];self.grid_page=0;self.scanning=False;self.cfg=dict(self.CONFIG["CARTON"]);self.buttons["stage_start_scan"].setText("START SCAN")
            for widget in (self.product,self.batch,self.target_list,self.template_selector,self.mfd):widget.setEnabled(True)
            with self.store.db:self.store.put('carton_current_run',None)
            self.refresh_choices();self.template_selector.blockSignals(True);self.template_selector.setCurrentIndex(0);self.template_selector.blockSignals(False);self.notify("Pilih target dan template untuk membuka carton berikutnya.");self.refresh()
        elif name=='stage_conveyor':self.settings_runtime.conveyor()
        elif name=='stage_upload':self.settings_runtime.upload(level='CARTON')
        elif name=='carton_targets':self.show_targets()
        elif name=='carton_verify':self.verify_dialog(self.run)
        elif name in ('grid_prev','grid_next'):
            self.grid_page=max(0,min(math.ceil(self.cfg['capacity']/12)-1,self.grid_page+(-1 if name=='grid_prev' else 1)));self.update()
        elif name.startswith('carton_cell_'):
            n=self.grid_page*12+int(name.rsplit('_',1)[1])
            if n<len(self.child_codes):MessageBox.information(self,'Detail box',f'Urutan: {n+1}\nSerial: {self.child_codes[n]}\nCarton: {self.cfg["code"]}\nBatch: {self.run["batch"]}\nStatus: VALID')

    def print_run(self,automatic=False):
        if not self.run:self.notify('Pilih carton terlebih dahulu.');return
        if self.run['state']!='COMPLETE':self.notify('Kunci carton sebelum mencetak label.');return
        if self.run['print_state']=='SENT' and not automatic:
            if MessageBox.question(self,'Cetak ulang','Cetak ulang label '+self.run['parent_code']+'?')!=MessageBox.StandardButton.Yes:return
            try:
                if self.print_callback(self.runtime.print_document(self.run['id']),self.run['template_id'],False):
                    with self.store.db:self.store.audit('REPRINT CARTON',self.run['parent_code'])
                    self.notify('Label carton dicetak ulang.')
            except Exception as exc:self.notify(str(exc))
        else:OperationPage.print_run(self,automatic)
        self.refresh();self.changed.emit()

    def scan_detail(self,row,*_):
        if row<len(self.recent_children):
            r=self.recent_children[row];MessageBox.information(self,'Detail scan',f"{r['code']}\n{r['ts']}\n{r['status']}\n{r['note']}")

    def result_detail(self,row,*_):
        if row>=len(self.result_rows):return
        run=self.runtime.get(self.result_rows[row]['id']);dialog=AppDialog(self);dialog.setWindowTitle('Hasil agregasi carton');dialog.resize(550,350);layout=QVBoxLayout(dialog)
        info=QLabel(f"{run['parent_code']}\nBatch: {run['batch']}\nIsi: {run['quantity']} {run['document']['child_level'].lower()}\nStatus: {run['state']} | Cetak: {run['print_state']}");layout.addWidget(info)
        children=self.store.db.execute('SELECT code FROM aggregation_children WHERE run_id=? ORDER BY rowid',(run['id'],)).fetchall();codes=QLabel('\n'.join(r[0] for r in children[:10])+ ('\n…' if len(children)>10 else ''));layout.addWidget(codes)
        rowcarton=QHBoxLayout();layout.addLayout(rowcarton)
        def pdf():
            path,_=FileDialog.getSaveFileName(dialog,'Simpan label PDF',run['parent_code']+'.pdf','PDF (*.pdf)')
            if path:
                try:
                    from .label_render import export_pdf
                    export_pdf(self.runtime.print_document(run['id']),path);self.notify('PDF label tersimpan.');dialog.accept()
                except Exception as exc:MessageBox.warning(dialog,'Label belum siap',str(exc))
        for label,call in [('Ekspor label PDF',pdf),('Verifikasi',lambda:self.verify_dialog(run)),('Tutup',dialog.accept)]:
            b=QPushButton(label);b.clicked.connect(call);rowcarton.addWidget(b)
        dialog.exec()

    def verify_dialog(self,run):
        if not run or run['state']!='COMPLETE':self.notify('Kunci carton lalu cetak label sebelum verifikasi.');return
        if run['print_state']!='SENT':self.notify('Cetak label carton sebelum verifikasi.');return
        dialog=AppDialog(self);dialog.setWindowTitle('Verifikasi kamera / label carton');dialog.resize(610,350);layout=QVBoxLayout(dialog)
        label=QLabel(f"Carton: {run['parent_code']}\nPeriksa gambar kamera dan isi carton, lalu scan ulang label. Verifikasi dicatat atas nama operator.");label.setWordWrap(True);layout.addWidget(label)
        dialog.code=QLineEdit();dialog.code.setPlaceholderText('Scan kode label carton');layout.addWidget(dialog.code)
        count=QSpinBox();count.setRange(0,1000000);count.setPrefix('Jumlah '+run['document']['child_level'].lower()+' diperiksa: ');layout.addWidget(count)
        error=QLabel();error.setWordWrap(True);layout.addWidget(error)
        def camera():
            from .settings_dialogs import CameraCalibration
            cam=CameraCalibration(self.settings_runtime,dialog);cam.start();cam.exec()
        def verify():
            try:self.repo.verify(run['id'],dialog.code.text(),count.value());dialog.accept();self.notify('Verifikasi carton VALID tersimpan.');self.refresh();self.changed.emit()
            except ValueError as exc:error.setText(str(exc))
        row=QHBoxLayout();layout.addLayout(row)
        for title,call in [('Buka kamera',camera),('Simpan verifikasi',verify),('Batal',dialog.reject)]:
            b=QPushButton(title);b.clicked.connect(call);row.addWidget(b)
        self.verification_dialog=dialog
        try:dialog.exec()
        finally:self.verification_dialog=None

    def show_targets(self):
        dialog=AppDialog(self);dialog.setWindowTitle('Data target box untuk carton');dialog.resize(840,570);layout=QVBoxLayout(dialog)
        info=QLabel('Box siap berasal dari sesi Box selesai dan label tercetak, sesuai produk/batch. Pilih box untuk membuat list atau impor daftar kode CSV.');info.setWordWrap(True);layout.addWidget(info)
        from PySide6.QtWidgets import QTableWidget,QAbstractItemView
        grid=QTableWidget(0,4);grid.setHorizontalHeaderLabels(['PILIH','KODE BOX','ISI UNIT','STATUS']);grid.setColumnWidth(0,52);grid.setColumnWidth(1,370);grid.setColumnWidth(2,100);grid.horizontalHeader().setStretchLastSection(True);grid.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);layout.addWidget(grid)
        name=QLineEdit('CARTON LIST');name.setPlaceholderText('Nama list target');layout.addWidget(name)
        rows=[]
        def load():
            nonlocal rows
            if self.target_list.currentData():
                rows=[dict(r) for r in self.store.db.execute("SELECT t.code,COALESCE(r.quantity,0) quantity,CASE WHEN c.code IS NULL THEN 'BELUM SCAN' ELSE 'TERAGREGASI' END state FROM carton_targets t LEFT JOIN aggregation_runs r ON r.level='BOX' AND r.parent_code=t.code LEFT JOIN aggregation_children c ON c.child_level='BOX' AND c.code=t.code WHERE t.list_id=? ORDER BY t.rowid",(self.target_list.currentData(),))]
            else:rows=self.repo.candidates(self.product.currentData(),self.batch.currentText())
            grid.setRowCount(min(1000,len(rows)))
            for i,r in enumerate(rows[:1000]):
                item=QTableWidgetItem();item.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(Qt.CheckState.Unchecked);grid.setItem(i,0,item)
                for j,value in enumerate((r['code'],r['quantity'],r['state']),1):grid.setItem(i,j,QTableWidgetItem(str(value)))
            info.setText(f"{len(rows)} box tersedia dalam tampilan ini. Centang box lalu Simpan List. Pratinjau maksimal 1.000 baris.")
        def require_idle():
            if self.run:MessageBox.warning(dialog,'Sesi aktif','Selesaikan / reset sesi terlebih dahulu sebelum mengganti list target.');return False
            return True
        def select_all():
            for i in range(grid.rowCount()):grid.item(i,0).setCheckState(Qt.CheckState.Checked)
        def save_list():
            if not require_idle():return
            codes=[rows[i]['code'] for i in range(grid.rowCount()) if grid.item(i,0).checkState()==Qt.CheckState.Checked]
            try:
                identifier=self.repo.create_targets(name.text(),codes,self.product.currentData(),self.batch.currentText());self.refresh_choices();self.target_list.setCurrentIndex(self.target_list.findData(identifier));load();self.notify('List target carton tersimpan.')
            except ValueError as exc:MessageBox.warning(dialog,'List belum tersimpan',str(exc))
        def import_file():
            if not require_idle():return
            path,_=FileDialog.getOpenFileName(dialog,'Impor target box','','CSV (*.csv)')
            if path:
                try:
                    identifier=self.repo.import_targets(path,self.product.currentData(),self.batch.currentText());self.refresh_choices();self.target_list.setCurrentIndex(self.target_list.findData(identifier));load();self.notify('List target carton berhasil diimpor.')
                except (ValueError,OSError,csv.Error) as exc:MessageBox.warning(dialog,'Impor gagal',str(exc))
        def export():
            path,_=FileDialog.getSaveFileName(dialog,'Ekspor target box','target-carton.csv','CSV (*.csv)')
            if path:
                try:
                    with open(path,'w',newline='',encoding='utf-8-sig') as handle:
                        writer=csv.writer(handle);writer.writerow(['code','product','batch'])
                        for r in rows:writer.writerow([r['code'],self.product.currentText(),self.batch.currentText()])
                    self.notify('Target carton diekspor.')
                except OSError as exc:MessageBox.warning(dialog,'Ekspor gagal',str(exc))
        row=QHBoxLayout();layout.addLayout(row)
        for label,call in [('Pilih semua',select_all),('Simpan list',save_list),('Impor CSV',import_file),('Ekspor CSV',export),('Tutup',dialog.accept)]:
            b=QPushButton(label);b.clicked.connect(call);row.addWidget(b)
        load();dialog.exec()

    def paint_content(self):
        steps=[('DATA TARGET','Memuat daftar '+self.cfg['child'].lower()+' target untuk satu carton.','revision'),('SCAN LABEL '+self.cfg['child'],'Memindai kode '+self.cfg['child'].lower()+' yang akan masuk ke carton.','barcode'),('PRINTER LABEL CARTON','Mencetak label carton / kode agregasi.','printer'),('VERIFIKASI KAMERA','Memeriksa gambar dan hasil scan label carton.','camera')]
        for i,(title,desc,ico) in enumerate(steps):
            x=15+i*274;self.panel(x,84,258,94);self.rect(x+12,96,24,24,'#eff7ff','#eff7ff','#7acaed',2)
            self.text(x+12,96,24,24,str(i+1),14,'#123d5c',True,Qt.AlignmentFlag.AlignCenter);self.text(x+45,97,203,23,title,12,WHITE,True)
            self.text(x+46,126,154,42,desc,11,MUTED,wrap=True);self.icon(ico,x+216,123,31)
            if i<3:self.text(x+259,117,15,24,'›',24,'#176282',True,Qt.AlignmentFlag.AlignCenter)
        self.panel(15,193,1080,483);self.text(28,198,350,26,'AGREGASI '+self.cfg['child']+' KE CARTON',14,WHITE,True)
        self.text(415,199,520,25,'KODE CARTON SAAT INI: '+(self.run['parent_code'] if self.run else 'BELUM DIBUKA'),11,GREEN,True)
        self.text(995,199,86,25,str(self.cfg['capacity'])+' '+self.cfg['child'],10,MUTED,align=Qt.AlignmentFlag.AlignRight);self.line(26,228,1057)
        for i in range(12):
            n=self.grid_page*12+i;row,col=divmod(i,4);x=40+col*260;y=244+row*136;filled=n<len(self.child_codes);exists=n<self.cfg['capacity'];scanning=exists and n==self.filled and self.scanning
            self.cell_buttons[i].setVisible(exists);self.cell_buttons[i].setToolTip(self.child_codes[n] if filled else f'Box {n+1}')
            if not exists:continue
            self.rect(x,y,240,120,'#09834a' if filled else '#095687' if scanning else '#466c85','#035330' if filled else '#023d67' if scanning else '#274c65','#57d061' if filled else '#29b7f5' if scanning else '#7497b0',4)
            self.text(x+12,y+8,60,26,str(n+1).zfill(2),18,WHITE,True)
            if filled:
                self.dot(x+209,y+12,GREEN,size=22);self.icon('barcode',x+83,y+31,74);self.text(x+5,y+91,230,24,self.child_codes[n],13,WHITE,True,Qt.AlignmentFlag.AlignCenter)
            elif scanning:
                self.icon('sync',x+100,y+40,40);self.text(x+1,y+91,238,24,'SCANNING…',12,WHITE,True,Qt.AlignmentFlag.AlignCenter)
            else:self.text(x,y+47,240,34,'—',24,MUTED,align=Qt.AlignmentFlag.AlignCenter)
        capacity=self.cfg['capacity'];ratio=self.filled/capacity
        self.text(28,651,116,19,'PROGRES AGREGASI',10,MUTED,True);self.rect(155,653,600,12,'#103a55','#09283d','#387392',6)
        if self.filled:self.rect(157,655,596*ratio,8,BLUE,'#0085c5',BLUE,4)
        self.text(768,648,214,23,f'{self.filled}/{capacity} {self.cfg["child"]} ({ratio*100:.1f}%)',11);self.text(982,648,101,23,f'CACHE: {self.filled}',10,align=Qt.AlignmentFlag.AlignRight)
        self.panel(15,685,336,202,'PILIH PRODUK / BATCH / LIST DATA');self.panel(357,685,364,202,'DATA '+self.cfg['child']+' TER-SCAN • 5 TERAKHIR');self.panel(727,685,368,202,'HASIL AGREGASI CARTON')
        for y,label in [(720,'PRODUK'),(749,'BATCH'),(778,'LIST DATA'),(807,'TEMPLATE')]:self.text(28,y,69,24,label,10,MUTED)
        self.text(28,866,306,19,f'● {self.filled}/{capacity} {self.cfg["child"].lower()}   •   CACHE {self.filled}   •   '+('READY' if self.scanning else 'SIAP' if self.run else 'PILIH TEMPLATE'),9,GREEN)
        self.panel(15,893,1080,97);self.text(29,908,106,25,'KONTROL LINE',11,WHITE,True);self.text(787,910,128,24,'MODE: '+self.store.get('mode','AGGREGATION'),10,GREEN,True)
        self.text(28,952,35,28,'MFD',11);self.text(198,952,40,28,'SCAN',10);self.text(478,948,603,36,self.message,10,GREEN if self.message.startswith(('VALID','Sesi siap','Verifikasi')) else YELLOW,wrap=True)

    def sidebar(self):
        from .shared_sidebar import paint_sidebar
        paint_sidebar(self)
