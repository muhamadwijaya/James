"""Read the selected SQLite schema without changing the source database."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from PySide6.QtWidgets import (QVBoxLayout,QFormLayout,QHBoxLayout,QLabel,QLineEdit,
    QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView)
from .ui_controls import ThemedComboBox
from .ui_dialogs import AppDialog,FileDialog


@contextmanager
def connection(store,path=''):
    if not path or Path(path).resolve()==store.path.resolve():
        yield store.db
    else:
        source=Path(path).expanduser().resolve()
        if not source.is_file():raise ValueError('File database sumber tidak ditemukan.')
        db=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True,timeout=2)
        try:yield db
        finally:db.close()


def tables(store,path=''):
    with connection(store,path) as db:
        return [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def columns(store,config=None):
    config=store.get('template_data_source',{}) if config is None else config
    name=config.get('table','')
    if not name:return []
    with connection(store,config.get('path','')) as db:
        # Table-valued PRAGMA accepts a bound identifier and preserves cid order.
        result=[dict(position=row[0],name=row[1],type=row[2] or 'TEXT') for row in db.execute('SELECT cid,name,type FROM pragma_table_info(?) ORDER BY cid',(name,))]
    if not result:raise ValueError('Tabel sumber tidak tersedia. Pilih kembali tabel database.')
    return result


def product_source(store):
    return store.get('template_product_source') or {'path':str(store.path.resolve()),
        'table':'aggregation_products','id_column':'id','name_column':'name'}


def product_choices(store,config=None):
    config=product_source(store) if config is None else config
    available={col['name'] for col in columns(store,config)}
    if not {config.get('id_column'),config.get('name_column')} <= available:
        raise ValueError('Pilih kolom ID dan nama produk pada Sumber Produk.')
    def quoted(name):return '"'+name.replace('"','""')+'"'
    query='SELECT '+quoted(config['id_column'])+','+quoted(config['name_column'])+' FROM '+quoted(config['table'])
    result={}
    with connection(store,config.get('path','')) as db:
        for key,name in db.execute(query):
            if key is None or name is None or not str(name).strip():continue
            if not isinstance(key,(str,int)) or isinstance(key,bool):raise ValueError('ID produk harus teks atau bilangan bulat.')
            identity=(type(key).__name__,key)
            if identity in result and result[identity]['name']!=str(name):raise ValueError('ID produk tidak unik. Pilih kolom ID produk yang benar.')
            result[identity]={'id':key,'name':str(name),'source':dict(config)}
    return sorted(result.values(),key=lambda row:(row['name'].casefold(),str(row['id'])))


class DatabaseSourceDialog(AppDialog):
    def __init__(self,store,parent=None,product_mode=False):
        super().__init__(parent);self.store=store;self.product_mode=product_mode
        self.setWindowTitle('Sumber produk child' if product_mode else 'Database sumber field template');self.resize(650,600 if product_mode else 520)
        layout=QVBoxLayout(self);layout.setContentsMargins(20,18,20,18);layout.setSpacing(12)
        hint=QLabel('Pilih database SQLite dan tabel sumber. Field dicocokkan persis dengan nama kolom, mengikuti urutan kolom database.');hint.setWordWrap(True);layout.addWidget(hint)
        config=product_source(store) if product_mode else store.get('template_data_source',{})
        row=QHBoxLayout();self.path=QLineEdit(config.get('path','') or str(store.path));self.path.setReadOnly(True);row.addWidget(self.path,1)
        choose=QPushButton('Pilih file');choose.clicked.connect(self.choose);row.addWidget(choose)
        local=QPushButton('Database aplikasi');local.clicked.connect(lambda:self.use_path(str(store.path)));row.addWidget(local);layout.addLayout(row)
        form=QFormLayout();self.table=ThemedComboBox();self.table.setMinimumHeight(34);form.addRow('Tabel sumber',self.table);layout.addLayout(form)
        self.id_column=ThemedComboBox();self.name_column=ThemedComboBox()
        if product_mode:
            hint.setText('Pilih tabel master produk, kolom ID produk, dan kolom nama. Nama ditampilkan di pilihan child; ID dan sumbernya disimpan sebagai relasi.')
            form.addRow('Kolom ID produk',self.id_column);form.addRow('Kolom nama produk',self.name_column)
        self.grid=QTableWidget(0,3);self.grid.setHorizontalHeaderLabels(['URUTAN','NAMA KOLOM','TIPE']);self.grid.verticalHeader().hide()
        self.grid.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.grid.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch);layout.addWidget(self.grid,1)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        row=QHBoxLayout();row.addStretch();cancel=QPushButton('Batal');cancel.clicked.connect(self.reject);row.addWidget(cancel)
        self.submit=QPushButton('Gunakan sumber');self.submit.clicked.connect(self.apply);row.addWidget(self.submit);layout.addLayout(row)
        self.table.currentTextChanged.connect(self.inspect);self.use_path(self.path.text())
        if config.get('table'):self.table.setCurrentText(config['table'])
        if product_mode:
            self.id_column.setCurrentText(config.get('id_column',''));self.name_column.setCurrentText(config.get('name_column',''))

    def use_path(self,path):
        self.path.setText(path);self.table.blockSignals(True);self.table.clear()
        try:self.table.addItems(tables(self.store,path))
        except (ValueError,sqlite3.Error) as exc:self.status.setText(str(exc))
        self.table.blockSignals(False);self.inspect()

    def choose(self):
        path,_=FileDialog.getOpenFileName(self,'Pilih database SQLite','','SQLite (*.sqlite *.sqlite3 *.db);;Semua file (*)')
        if path:self.use_path(path)

    def inspect(self):
        self.grid.setRowCount(0)
        try:
            result=columns(self.store,{'path':self.path.text(),'table':self.table.currentText()})
            if self.product_mode:
                names=[c['name'] for c in result]
                for widget,candidates in ((self.id_column,('product_id','id','kode_produk','product_code','gtin')),(self.name_column,('product_name','nama_produk','name','product'))):
                    old=widget.currentText();widget.clear();widget.addItems(names)
                    widget.setCurrentText(old if old in names else next((key for key in candidates if key in names),names[0] if names else ''))
            self.grid.setRowCount(len(result))
            for i,col in enumerate(result):
                for j,value in enumerate((i+1,col['name'],col['type'])):self.grid.setItem(i,j,QTableWidgetItem(str(value)))
            self.status.setText(f'{len(result)} kolom tersedia • sumber hanya dibaca');self.submit.setEnabled(bool(result))
        except (ValueError,sqlite3.Error) as exc:self.status.setText(str(exc));self.submit.setEnabled(False)

    def apply(self):
        config={'path':str(Path(self.path.text()).resolve()),'table':self.table.currentText()}
        try:
            if not columns(self.store,config):return
            if self.product_mode:
                config.update(id_column=self.id_column.currentText(),name_column=self.name_column.currentText())
                product_choices(self.store,config)
            self.store.configure({'template_product_source' if self.product_mode else 'template_data_source':config});self.accept()
        except (ValueError,sqlite3.Error) as exc:self.status.setText(str(exc))
