import csv
from collections import Counter
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QLineEdit,QComboBox,
    QPushButton,QDialogButtonBox,QTableWidget,QTableWidgetItem,QHeaderView,
    QAbstractItemView,QMessageBox,QFileDialog,QGroupBox,QCheckBox,QPlainTextEdit,
    QTabWidget,QWidget,QSpinBox)
from .ui_controls import ThemedComboBox as QComboBox
from .ui_dialogs import AppDialog as QDialog, MessageBox as QMessageBox, FileDialog as QFileDialog, dialog_parent
from .store import STAGES, PREFIX

class BaseDialog(QDialog):
    changed=Signal()
    def __init__(self,store,parent,title,width=860,height=570):
        super().__init__(parent)
        self.store=store
        self.setWindowTitle('AGREGASI • '+title)
        self.resize(width,height)
        self.layout=QVBoxLayout(self)
        self.layout.setContentsMargins(24,20,24,20)
        self.layout.setSpacing(14)
        heading=QLabel(title);heading.setObjectName('dialogTitle')
        self.layout.addWidget(heading)
    def note(self,text):
        label=QLabel(text);label.setWordWrap(True);label.setObjectName('help')
        self.layout.addWidget(label)
        return label
    def close_button(self):
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject);self.layout.addWidget(buttons)
    def error(self,exc):
        QMessageBox.warning(self,'Periksa data',str(exc))


def table(headers):
    t=QTableWidget(0,len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.verticalHeader().setVisible(False)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setAlternatingRowColors(True)
    return t

def fill_table(t,rows):
    t.setRowCount(len(rows))
    for i,row in enumerate(rows):
        for j,val in enumerate(row):
            item=QTableWidgetItem(str(val))
            if val in ('VALID','ONLINE'):item.setForeground(QColor('#79e95a'))
            if val in ('REJECT','OFFLINE'):item.setForeground(QColor('#ff6a66'))
            if val=='DUPLIKAT':item.setForeground(QColor('#ffc846'))
            t.setItem(i,j,item)

class StageDialog(BaseDialog):
    def __init__(self,store,parent,stage):
        self.stage=stage
        super().__init__(store,parent,f'Tahap {STAGES.index(stage)+1} / {stage}',960,710)
        self.note('Operasi lokal • Scan kemasan, periksa duplikat, lalu hubungkan ke kemasan induk. Tata letak halaman penuh dapat diganti saat referensi berikutnya diberikan.')
        self.context=QLabel(f"{store.get('product')}   /   {store.get('batch')}")
        self.layout.addWidget(self.context)
        row=QHBoxLayout()
        self.code=QLineEdit();self.code.setObjectName('scanCode')
        self.code.setPlaceholderText(PREFIX[stage]+'-250501-0008')
        self.code.setMaxLength(100)
        self.scan_btn=QPushButton('SCAN / ENTER');self.scan_btn.setObjectName('scanSubmit')
        self.scan_btn.setDefault(True)
        self.scan_btn.clicked.connect(self.scan)
        self.code.returnPressed.connect(self.scan)
        # Avoid a second default-button activation from the same Enter event.
        self.scan_btn.setAutoDefault(False);self.scan_btn.setDefault(False)
        sample=QPushButton('Kode contoh');sample.setAutoDefault(False)
        sample.clicked.connect(lambda:self.code.setText(store.next_code(stage)))
        row.addWidget(self.code,1);row.addWidget(sample);row.addWidget(self.scan_btn)
        self.layout.addLayout(row)
        self.reject_check=QCheckBox('Simulasikan hasil verifikasi REJECT')
        self.layout.addWidget(self.reject_check)
        self.result=QLabel('Siap menerima kode. Prefix: '+PREFIX[stage]+'-')
        self.result.setObjectName('result');self.layout.addWidget(self.result)
        self.activity=table(['Waktu','Kode','Status','Catatan'])
        self.layout.addWidget(self.activity,1)
        self.link_box=QGroupBox('Hubungan kemasan')
        form=QFormLayout(self.link_box)
        self.child=QComboBox();self.parent_code=QComboBox()
        if stage!='PALLET':
            form.addRow(stage+' valid',self.child)
            form.addRow(STAGES[STAGES.index(stage)+1]+' induk',self.parent_code)
            link=QPushButton('Hubungkan kemasan');link.setAutoDefault(False);link.clicked.connect(self.link)
            form.addRow(link)
        else:
            info=QLabel('Pallet adalah tingkat tertinggi. Hubungkan carton ke pallet melalui Tahap 2 / Carton.');info.setWordWrap(True)
            form.addRow(info)
        self.links=QLabel();self.links.setWordWrap(True);form.addRow(self.links)
        self.layout.addWidget(self.link_box)
        self.close_button();self.refresh();self.code.setFocus()

    def refresh(self):
        fill_table(self.activity,[(e['ts'][11:19],e['code'],e['status'],e['note']) for e in self.store.events(self.stage,limit=100)])
        if self.stage!='PALLET':
            self.child.clear();self.parent_code.clear()
            self.child.addItems([x['code'] for x in self.store.available(self.stage) if not x['parent']])
            self.parent_code.addItems([x['code'] for x in self.store.available(STAGES[STAGES.index(self.stage)+1])])
        count=self.store.db.execute('SELECT COUNT(*) FROM packages WHERE stage=? AND parent IS NOT NULL',(self.stage,)).fetchone()[0]
        self.links.setText(f'{count} {self.stage.lower()} telah terhubung ke induk.' if self.stage!='PALLET' else f"{len(self.store.available('PALLET'))} pallet valid tersedia pada daftar lokal.")
    def scan(self):
        if not self.store.get('devices')['scanner']:
            self.result.setText('Scanner simulasi OFFLINE. Aktifkan pada Status Perangkat.');return
        try:
            code=self.code.text().strip().upper()
            _,status=self.store.scan(self.stage,code,self.reject_check.isChecked())
            self.result.setText(f'{status} • {code}')
            self.result.setStyleSheet('color:'+{'VALID':'#79e95a','REJECT':'#ff6a66','DUPLIKAT':'#ffc846'}[status])
            self.code.clear();self.code.setFocus();self.refresh();self.changed.emit()
        except Exception as exc:self.error(exc)
    def link(self):
        try:
            self.store.link(self.stage,self.child.currentText(),self.parent_code.currentText())
            self.result.setText('Hubungan kemasan tersimpan.')
            self.refresh();self.changed.emit()
        except ValueError as exc:self.error(exc)

class ActivityDialog(BaseDialog):
    def __init__(self,store,parent,status=None,stage=None,revision=False):
        super().__init__(store,parent,'Revision & Jejak Audit' if revision else 'Riwayat aktivitas',1050,650)
        self.revision=revision
        self.note('Data awal bertanda reference berasal dari contoh desain. Aktivitas scan baru tersimpan lokal. Revisi mengubah catatan dengan jejak audit; kode dan hasil scan tetap dipertahankan.')
        filters=QHBoxLayout()
        self.search=QLineEdit();self.search.setPlaceholderText('Cari kode, batch, operator, atau catatan…')
        self.stage_filter=QComboBox();self.stage_filter.addItems(['SEMUA TAHAP']+list(STAGES))
        self.status_filter=QComboBox();self.status_filter.addItems(['SEMUA STATUS','VALID','REJECT','DUPLIKAT'])
        if stage:self.stage_filter.setCurrentText(stage)
        if status:self.status_filter.setCurrentText(status)
        filters.addWidget(self.search,1);filters.addWidget(self.stage_filter);filters.addWidget(self.status_filter)
        self.layout.addLayout(filters)
        self.grid=table(['ID','Waktu','Tahap','Kode','Status','Batch','Sumber'])
        self.grid.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents)
        self.layout.addWidget(self.grid,1)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);self.details.setMaximumHeight(100)
        self.layout.addWidget(self.details)
        self.grid.itemSelectionChanged.connect(self.show_detail)
        self.note_edit=QLineEdit();self.note_edit.setPlaceholderText('Catatan / alasan revisi aktivitas terpilih')
        if revision:self.layout.addWidget(self.note_edit)
        row=QHBoxLayout()
        if revision:
            save=QPushButton('Simpan revisi catatan');save.clicked.connect(self.revise);row.addWidget(save)
            audit=QPushButton('Lihat jejak audit');audit.clicked.connect(self.audit);row.addWidget(audit)
        export=QPushButton('Ekspor hasil filter ke CSV');export.clicked.connect(self.export);row.addWidget(export)
        close=QPushButton('Tutup');close.clicked.connect(self.accept);row.addStretch();row.addWidget(close)
        self.layout.addLayout(row)
        for widget in [self.stage_filter,self.status_filter]:widget.currentTextChanged.connect(self.refresh)
        self.search.textChanged.connect(self.refresh);self.refresh()
    def refresh(self):
        stage=self.stage_filter.currentText();status=self.status_filter.currentText()
        rows=self.store.events(None if stage.startswith('SEMUA') else stage,None if status.startswith('SEMUA') else status,1000000)
        query=self.search.text().casefold()
        self.rows=[e for e in rows if query in ' '.join(str(x) for x in e.values()).casefold()]
        fill_table(self.grid,[(e['id'],e['ts'].replace('T',' '),e['stage'],e['code'],e['status'],e['batch'],e['source']) for e in self.rows])
        self.details.clear()
    def selected(self):
        i=self.grid.currentRow()
        return self.rows[i] if 0<=i<len(self.rows) else None
    def show_detail(self):
        e=self.selected()
        if e:
            self.details.setPlainText(f"Produk: {e['product']} | Operator: {e['operator']} | Aktivitas: {e['action']}\nCatatan: {e['note'] or '—'}")
            self.note_edit.setText(e['note'])
    def revise(self):
        e=self.selected()
        try:
            self.store.revise(e['id'] if e else None,self.note_edit.text())
            self.refresh();self.changed.emit()
        except ValueError as exc:self.error(exc)
    def audit(self):
        dialog=BaseDialog(self.store,self,'Jejak audit',900,480)
        grid=table(['Waktu','Aksi','Detail','Operator'])
        rows=self.store.db.execute('SELECT ts,action,detail,operator FROM audit ORDER BY id DESC').fetchall()
        fill_table(grid,rows);dialog.layout.addWidget(grid);dialog.close_button();dialog.exec()
    def export(self):
        path,_=QFileDialog.getSaveFileName(self,'Simpan CSV','aktivitas_agregasi.csv','CSV (*.csv)')
        if not path:return
        try:
            with open(path,'w',newline='',encoding='utf-8-sig') as handle:
                writer=csv.DictWriter(handle,fieldnames=['id','ts','stage','action','code','status','note','batch','product','operator','source'])
                writer.writeheader()
                for e in self.rows:
                    writer.writerow({k: "'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v for k,v in e.items()})
            self.details.setPlainText(f'{len(self.rows)} aktivitas diekspor ke {path}')
        except OSError as exc:self.error(exc)

class SettingsDialog(BaseDialog):
    def __init__(self,store,parent):
        super().__init__(store,parent,'Pengaturan produk & operator',750,620)
        self.note('Pengaturan berlaku untuk aktivitas berikutnya. Identitas operator merupakan sesi lokal, belum autentikasi server.')
        form=QFormLayout();self.inputs={}
        for key,label,maxlen in [('product','Nama produk',32),('batch','Batch',24),('line','Line produksi',20),('user','Nama operator',20)]:
            edit=QLineEdit(store.get(key));edit.setMaxLength(maxlen);edit.setObjectName('setting_'+key)
            form.addRow(label,edit);self.inputs[key]=edit
        shift=QComboBox();shift.addItems(['A','B','C']);shift.setCurrentText(store.get('shift'))
        form.addRow('Shift',shift);self.inputs['shift']=shift
        form.addRow('Mode agregasi',QLabel('AGGREGATION'))
        form.addRow('Penyimpanan',QLabel('SQLite lokal (otomatis)'))
        self.layout.addLayout(form)
        self.note('Data unit 18.450, valid 17.120, reject 1.330, duplikat 650, dan grafik awal adalah snapshot contoh. Scan di jendela tahap menambah jumlah kemasan; jumlah unit tidak dihitung tanpa isi unit per kemasan.')
        self.layout.addStretch()
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save);buttons.rejected.connect(self.reject);self.layout.addWidget(buttons)
    def save(self):
        values={k:(w.currentText() if isinstance(w,QComboBox) else w.text().strip()) for k,w in self.inputs.items()}
        if not all(values.values()):self.error('Semua kolom wajib diisi.');return
        # A batch change must not retain current container identifiers from the old batch.
        if values['batch']!=self.store.get('batch'):
            values['current']={s:'—' for s in STAGES}
        self.store.configure(values);self.changed.emit();self.accept()

class DeviceDialog(BaseDialog):
    def __init__(self,store,parent,key):
        super().__init__(store,parent,'Koneksi '+key.upper(),640,410)
        self.key=key
        self.note('MODE SIMULASI • Kontrol ini mengubah status perangkat virtual. Koneksi printer, kamera, scanner, dan conveyor fisik belum dikonfigurasi.')
        self.status=QLabel();self.status.setObjectName('result');self.layout.addWidget(self.status)
        self.result=QLabel('Siap melakukan pemeriksaan lokal.');self.result.setWordWrap(True)
        self.layout.addWidget(self.result)
        row=QHBoxLayout()
        self.toggle=QPushButton();self.toggle.clicked.connect(self.toggle_device)
        test=QPushButton('Tes koneksi lokal' if key=='database' else 'Tes simulasi');test.clicked.connect(self.test)
        row.addWidget(self.toggle);row.addWidget(test);self.layout.addLayout(row)
        self.layout.addStretch();self.close_button();self.refresh()
    def refresh(self):
        online=self.store.get('devices')[self.key]
        self.status.setText(('ONLINE' if online else 'OFFLINE')+' • SIMULASI')
        self.toggle.setText('Putuskan simulasi' if online else 'Aktifkan simulasi')
    def toggle_device(self):
        devices=self.store.get('devices');devices[self.key]=not devices[self.key]
        self.store.configure({'devices':devices});self.refresh();self.changed.emit()
        self.result.setText('Status virtual diperbarui. Database penyimpanan aplikasi tetap aktif.')
    def test(self):
        if not self.store.get('devices')[self.key]:self.result.setText('OFFLINE: aktifkan simulasi perangkat terlebih dahulu.');return
        if self.key=='database':
            self.store.db.execute('SELECT 1').fetchone()
            self.result.setText('Berhasil: database SQLite lokal dapat dibaca. Status indikator produksi bersifat simulasi.')
        else:self.result.setText('Simulasi '+self.key+': OK. Tidak ada perintah yang dikirim ke perangkat fisik.')

class ImportDialog(BaseDialog):
    def __init__(self,store,parent):
        super().__init__(store,parent,'Upload instan • Impor CSV',880,590)
        self.rows=[]
        self.note('Kolom wajib: stage,code. Tahap: BOX, CARTON, atau PALLET. Data diperiksa dahulu, lalu diimpor ke database lokal. Kode berulang dicatat DUPLIKAT dan tidak menambah kemasan valid.')
        row=QHBoxLayout();choose=QPushButton('Pilih CSV');choose.clicked.connect(self.choose)
        template=QPushButton('Simpan template CSV');template.clicked.connect(self.template)
        row.addWidget(choose);row.addWidget(template);row.addStretch();self.layout.addLayout(row)
        self.status=QLabel('Belum ada file dipilih.');self.status.setWordWrap(True);self.layout.addWidget(self.status)
        self.grid=table(['Tahap','Kode','Perkiraan hasil']);self.layout.addWidget(self.grid,1)
        self.submit=QPushButton('Impor ke data lokal');self.submit.setEnabled(False);self.submit.clicked.connect(self.submit_import)
        self.layout.addWidget(self.submit);self.close_button()
    def template(self):
        path,_=QFileDialog.getSaveFileName(self,'Simpan template','template_agregasi.csv','CSV (*.csv)')
        if path:
            try:Path(path).write_text('stage,code\nBOX,BOX-DEMO-0001\nCARTON,CTN-DEMO-0001\nPALLET,PLT-DEMO-0001\n',encoding='utf-8')
            except OSError as exc:self.error(exc)
    def load_path(self,path):
        self.rows=[];self.submit.setEnabled(False);self.grid.setRowCount(0)
        self.rows=self.store.read_import(path)
        seen={(x['stage'],x['code']) for x in self.store.db.execute('SELECT stage,code FROM packages')}
        preview=[];counts=Counter()
        for row in self.rows:
            key=(row['stage'],row['code'])
            status='DUPLIKAT' if key in seen else 'VALID' if self.store.valid_code(*key) else 'REJECT'
            if status=='VALID':seen.add(key)
            counts[status]+=1;preview.append((*key,status))
        fill_table(self.grid,preview)
        self.status.setText(f'{Path(path).name} • {len(self.rows)} baris • Valid {counts["VALID"]} / Reject {counts["REJECT"]} / Duplikat {counts["DUPLIKAT"]}')
        self.submit.setEnabled(True)
    def choose(self):
        path,_=QFileDialog.getOpenFileName(self,'Pilih CSV','','CSV (*.csv)')
        if path:
            try:self.load_path(path)
            except (OSError,ValueError,UnicodeError,csv.Error) as exc:self.error(exc)
    def submit_import(self):
        try:
            results=self.store.import_rows(self.rows)
            counts=Counter(status for _,status in results)
            self.status.setText(f'Impor selesai: {len(results)} baris. Valid {counts["VALID"]}, reject {counts["REJECT"]}, duplikat {counts["DUPLIKAT"]}.')
            self.submit.setEnabled(False);self.rows=[];self.changed.emit()
        except Exception as exc:self.error(exc)

class ExportDialog(BaseDialog):
    def __init__(self,store,parent):
        super().__init__(store,parent,'Kirim data • Paket ekspor',700,400)
        self.note('Tujuan server belum dikonfigurasi. Buat paket JSON berisi ringkasan, aktivitas, hubungan kemasan, dan audit untuk integrasi backend berikutnya.')
        self.status=QLabel('Data belum dikirim ke server.');self.status.setWordWrap(True);self.layout.addWidget(self.status)
        save=QPushButton('Simpan paket data JSON');save.clicked.connect(self.export);self.layout.addWidget(save)
        self.layout.addStretch();self.close_button()
    def export(self):
        path,_=QFileDialog.getSaveFileName(self,'Simpan paket data','agregasi_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.json','JSON (*.json)')
        if path:
            try:
                self.store.export_json(path)
                self.status.setText('Paket JSON tersimpan: '+path+'\nStatus: diekspor lokal, belum dikirim ke server.')
            except OSError as exc:self.error(exc)

class SummaryDialog(BaseDialog):
    def __init__(self,store,parent):
        super().__init__(store,parent,'Ringkasan & sumber data',820,580)
        self.note('Dashboard memuat snapshot referensi ditambah aktivitas kemasan lokal. Angka contoh pada gambar bukan hasil pembacaan mesin langsung.')
        grid=table(['Metrik unit (snapshot)','Nilai'])
        fill_table(grid,[('Unit terproses','18.450'),('Valid','17.120'),('Reject','1.330'),('Duplikat (indikator terpisah)','650'),('Valid rate','92,8%')])
        self.layout.addWidget(grid)
        stages=table(['Tahap','Terproses','Valid','Reject','Duplikat'])
        fill_table(stages,[(s,v['total'],v['valid'],v['reject'],v['duplicate']) for s,v in store.summary()['stages'].items()])
        self.layout.addWidget(stages)
        self.note('Snapshot box menampilkan total 256, valid 210, reject 18, dan duplikat 10 sesuai gambar. Selisih 18 tidak diberi kategori pada sumber. Aktivitas baru ditambahkan menurut hasilnya. Grafik shift/hari adalah contoh visual; pilih SESI LOKAL untuk jumlah scan aktual per 2 jam.')
        self.close_button()
