"""Complete settings surface matching the supplied industrial UI reference."""
from .sidebar_layout import fixed_sidebar, SETTINGS_SOURCE, remap_sidebar_controls
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt, QDate, QTime, QRectF, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QIcon
from PySide6.QtWidgets import (QCheckBox, QPushButton, QLineEdit, QSpinBox,
    QDoubleSpinBox, QDateEdit, QTimeEdit, QLabel, QTableWidgetItem, QDialog,
    QVBoxLayout, QHBoxLayout, QPlainTextEdit)
from PySide6.QtPrintSupport import QPrinterInfo
from PySide6.QtSerialPort import QSerialPortInfo
from .pages import PageBase
from .dashboard import BASE, WHITE, MUTED, GREEN, BLUE, YELLOW, RED
from .ui_controls import ThemedComboBox
from .ui_dialogs import FileDialog, MessageBox, AppDialog
from .settings_model import defaults, VERSION, LEVELS, SCAN_MODES

# Device rows share one 28 px grid so scanner and camera columns stay aligned.
SCANNER_ROWS=tuple(525+i*28 for i in range(9))
CAMERA_ROWS=tuple(525+i*28 for i in range(6))
SCANNER_COLUMNS=(('BOX',110),('CARTON',224),('PALLET',338))
from .settings_runtime import SettingsRuntime
from .settings_dialogs import UserEditor, ScannerCalibration, CameraCalibration

TRANSLATIONS = {
 'PENGATURAN LINE PRODUKSI':'PRODUCTION LINE SETTINGS','KONEKSI DATABASE / API':'DATABASE / API CONNECTION',
 'PENGATURAN PRINTER':'PRINTER SETTINGS','PENGATURAN SCANNER & KAMERA':'SCANNER & CAMERA SETTINGS',
 'MANAJEMEN USER & AKSES':'USER & ACCESS MANAGEMENT','BACKUP, LOG, & MAINTENANCE':'BACKUP, LOG, & MAINTENANCE',
 'NAMA LINE':'LINE NAME','SHIFT DEFAULT':'DEFAULT SHIFT','MODE AGREGASI':'AGGREGATION MODE',
 'WAKTU CONVEYOR (DETIK)':'CONVEYOR TIME (SECONDS)','LIMIT CACHE DATA':'CACHE DATA LIMIT',
 'AUTO UPLOAD DATA':'AUTO UPLOAD DATA','TIMEOUT UPLOAD (DETIK)':'UPLOAD TIMEOUT (SECONDS)',
 'DEFAULT MFD':'DEFAULT MFD','BAHASA SISTEM':'SYSTEM LANGUAGE','TEMA SISTEM':'SYSTEM THEME',
 'SYNC INTERVAL (DETIK)':'SYNC INTERVAL (SECONDS)','TEST KONEKSI TERAKHIR':'LAST CONNECTION TEST',
 'STATUS KONEKSI':'CONNECTION STATUS','TEST KONEKSI SEKARANG':'TEST CONNECTION NOW',
 'TEST PRINT SEMUA PRINTER':'TEST PRINT ALL PRINTERS','UKURAN LABEL':'LABEL SIZE',
 'KAMERA VERIFIKASI':'VERIFICATION CAMERA','KONEKSI (COM)':'CONNECTION (COM)','ALAMAT':'ADDRESS','FOKUS':'FOCUS','DEVICE':'DEVICE',
 'MODE SCAN':'SCAN MODE','IP KAMERA':'CAMERA IP','PORT KAMERA':'CAMERA PORT','STATUS':'STATUS',
 'RESOLUSI':'RESOLUTION','KALIBRASI SCANNER':'CALIBRATE SCANNER','KALIBRASI KAMERA':'CALIBRATE CAMERA',
 'TAMBAH USER':'ADD USER','EDIT ROLE':'EDIT ROLE','BACKUP OTOMATIS':'AUTO BACKUP',
 'SIMPAN BACKUP':'KEEP BACKUPS','RESTORE KONFIGURASI':'RESTORE CONFIGURATION',
 'BERSIHKAN FILE TEMP':'CLEAR TEMP FILES','EXPORT LOG SISTEM':'EXPORT SYSTEM LOG',
 'VERSI SISTEM':'SYSTEM VERSION','CEK UPDATE':'CHECK UPDATE','CEK SEKARANG':'CHECK NOW',
 'SIMPAN PENGATURAN':'SAVE SETTINGS','MUAT ULANG':'RELOAD','RESET DEFAULT':'RESET DEFAULTS',
 'TEST SEMUA DEVICE':'TEST ALL DEVICES','BERSIHKAN':'CLEAR','EXPORT KONFIG':'EXPORT CONFIG',
 'RINGKASAN PENGATURAN':'SETTINGS SUMMARY','STATUS DEVICE':'DEVICE STATUS',
 'INFORMASI SISTEM':'SYSTEM INFORMATION','AKUN LOGIN':'CURRENT ACCOUNT','SHORTCUT KONEKSI':'CONNECTION SHORTCUTS',
 'TOTAL POSTING HARI INI':'TOTAL SENT TODAY','TERAKHIR DIUBAH':'LAST MODIFIED','KONFIGURASI SISTEM & PERANGKAT':'SYSTEM & DEVICE CONFIGURATION',
}
CONTROL_STYLE='''QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox,QDateEdit,QTimeEdit {
 color:#e8f3fc;background:#03273e;border:1px solid #36607a;border-radius:3px;
 padding:2px 6px;font-size:12px;min-height:0px;}
 QLineEdit:focus,QComboBox:focus,QAbstractSpinBox:focus{border:1px solid #66caff;}
 QAbstractSpinBox::up-button,QAbstractSpinBox::down-button{width:13px;border:0;background:#08364f;}
 QAbstractSpinBox::up-arrow{image:url("@UP@");width:7px;height:4px;}
 QAbstractSpinBox::down-arrow{image:url("@DOWN@");width:7px;height:4px;}
 QCalendarWidget QWidget{background:#07304b;color:#e8f4ff;}
'''.replace('@UP@',(BASE/'assets/svg/chevron_up.svg').as_posix()).replace('@DOWN@',(BASE/'assets/svg/chevron_down.svg').as_posix())


class Toggle(QCheckBox):
    def __init__(self,parent=None):
        super().__init__(parent);self.setCursor(Qt.CursorShape.PointingHandCursor)
    def hitButton(self,point):return self.rect().contains(point)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#339b53' if self.isChecked() else '#354d60'))
        p.drawRoundedRect(QRectF(0,5,35,18),9,9);p.setBrush(QColor('#eafaff'));p.drawEllipse(QRectF(19 if self.isChecked() else 3,8,12,12))
        p.setPen(QColor(GREEN if self.isChecked() else MUTED));font=p.font();font.setPixelSize(11);p.setFont(font)
        if self.width()>75:p.drawText(42,0,max(0,self.width()-42),28,Qt.AlignmentFlag.AlignVCenter,'AKTIF' if self.isChecked() else 'NONAKTIF')
        if self.hasFocus():p.setPen(QPen(QColor(BLUE),1));p.setBrush(Qt.BrushStyle.NoBrush);p.drawRoundedRect(self.rect().adjusted(0,0,-1,-1),3,3)
        p.end()


class SettingsPage(PageBase):
    def __init__(self,store):
        super().__init__(store,'settings','Pengaturan','KONFIGURASI SISTEM & PERANGKAT','settings')
        self.runtime=SettingsRuntime(store,self);self.repo=self.runtime.repo
        self.controls={};self.buttons={};self.dirty=False;self.loading=True;self.message='Pengaturan siap.';self.message_error=False
        self._english=False;self.high_contrast=False
        self.build_line();self.build_api();self.build_printers();self.build_devices();self.build_users();self.build_maintenance()
        for name,x,w,label,color,icon in [
            ('save_settings',16,269,'SIMPAN PENGATURAN','#087942','template'),
            ('reload_settings',295,263,'MUAT ULANG','#096caf','revision'),
            ('reset_settings',568,259,'RESET DEFAULT','#9a6b05','revision'),
            ('test_devices',837,265,'TEST SEMUA DEVICE','#603b92','settings')]:
            self.button(name,x,917,w,47,label,color,icon)
        self.runtime.message.connect(self.notify);self.runtime.changed.connect(self.refresh)
        self.runtime.camera_image.connect(self.show_camera_image)
        self.action.connect(self.local_action);self.load()
        for index,key in enumerate(('database','printer','camera','scanner','logout')):
            self.findChild(QPushButton,'shortcut_'+key).setGeometry(1139+index*57,925,52,51)
        remap_sidebar_controls([self.findChild(QPushButton, "shortcut_"+key) for key in ("database","printer","camera","scanner","logout")], SETTINGS_SOURCE)
        self.build_display_tab()

    def build_display_tab(self):
        from .appearance_panel import AppearancePanel
        from .shell_layout import BODY
        self.appearance_panel=AppearancePanel(self.repo,self)
        self.appearance_panel.setGeometry(BODY.toRect())
        self.appearance_panel.applied.connect(lambda cfg:self.changed.emit())
        self.display_tabs=[]
        for x,w,label,active in [(641,223,'PERANGKAT DAN SISTEM',False),(872,223,'TAMPILAN',True)]:
            b=QPushButton(label,self);b.setGeometry(x,37,w,28);b.setCheckable(True)
            b.setStyleSheet('QPushButton {background:#123b57;color:#d4e8f6;border:1px solid #477895;border-radius:4px;font-size:11px;padding:2px;} QPushButton:checked {background:#0b6aa4;color:white;border-color:#60b9e6;}')
            b.clicked.connect(lambda checked=False,value=active:self.show_display_tab(value));self.display_tabs.append(b)
        self.show_display_tab(False)
    def show_display_tab(self,active):
        from PySide6.QtWidgets import QWidget
        if active and not getattr(self,'_display_tab_active',False):
            self._hidden_device_widgets=[]
            for w in self.findChildren(QWidget,options=Qt.FindChildOption.FindDirectChildrenOnly):
                rect=w.property('design_geometry') or w.geometry()
                if w is not self.appearance_panel and rect.x()<1106 and 75 <= rect.y() < 996:
                    self._hidden_device_widgets.append((w,w.isHidden()));w.hide()
        elif not active and getattr(self,'_display_tab_active',False):
            for w,hidden in self._hidden_device_widgets:w.setVisible(not hidden)
        self._display_tab_active=active
        self.appearance_panel.setVisible(active)
        if active:self.appearance_panel.raise_()
        self.update()
        self.display_tabs[0].setChecked(not active);self.display_tabs[1].setChecked(active)

    def tr(self,value):return TRANSLATIONS.get(value,value) if self._english else value
    def text(self,x,y,w,h,value,*args,**kwargs):return super().text(x,y,w,h,self.tr(str(value)),*args,**kwargs)
    def notify(self,text,error=False):
        self.message=text;self.message_error=error;self.update()
    def edited(self,*_):
        if not self.loading:self.dirty=True;self.notify('Ada perubahan yang belum disimpan.')

    def control(self,key,x,y,w,kind='text',options=(),minimum=0,maximum=100000):
        if kind=='combo':
            widget=ThemedComboBox(self);widget.addItems([str(v) for v in options]);widget.currentTextChanged.connect(self.edited)
        elif kind=='editable':
            widget=ThemedComboBox(self);widget.setEditable(True);widget.addItems([str(v) for v in options]);widget.currentTextChanged.connect(self.edited)
        elif kind in ('int','float'):
            widget=QSpinBox(self) if kind=='int' else QDoubleSpinBox(self)
            widget.setRange(minimum,maximum);widget.valueChanged.connect(self.edited)
            if kind=='float':widget.setDecimals(1);widget.setSingleStep(.1)
        elif kind=='date':
            widget=QDateEdit(self);widget.setCalendarPopup(True);widget.setDisplayFormat('dd/MM/yyyy');widget.dateChanged.connect(self.edited)
        elif kind=='time':
            widget=QTimeEdit(self);widget.setDisplayFormat('HH:mm');widget.timeChanged.connect(self.edited)
        elif kind=='toggle':
            widget=Toggle(self);widget.toggled.connect(self.edited)
        else:
            widget=QLineEdit(self);widget.setMaxLength(2048);widget.textChanged.connect(self.edited)
        widget.setGeometry(x,y,w,27);widget.setObjectName('setting_'+key.replace('.','_'));widget.setAccessibleName(key)
        widget.setStyleSheet(CONTROL_STYLE);self.controls[key]=widget;return widget

    def button(self,name,x,y,w,h,label,color='#096caf',icon=None):
        b=QPushButton(self.tr(label),self);b.setObjectName(name);b.setProperty('label_key',label);b.setProperty('button_color',color)
        b.setGeometry(x,y,w,h);b.setCursor(Qt.CursorShape.PointingHandCursor);b.setAccessibleName(label)
        b.setStyleSheet(f'QPushButton{{color:#f2f8ff;background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {color},stop:1 #043249);border:1px solid {color};border-radius:4px;padding:2px 5px;font-size:11px;}} QPushButton:hover{{border-color:#8fd9ff;background:{color};}} QPushButton:focus{{border:2px solid #9ddbff;}} QPushButton:disabled{{color:#8299ab;background:#17374a;}}')
        if icon:b.setIcon(QIcon(str(BASE/'assets/svg'/f'{icon}.svg')));b.setIconSize(QSize(23,23))
        b.clicked.connect(lambda _,n=name:self.action.emit(n));self.buttons[name]=b;return b

    def build_line(self):
        c=self.control
        line=c('line',159,127,183,'editable',['AGGREGATION-01','AGGREGATION-02']);self.line_name=line.lineEdit()
        self.shift=c('shift',159,158,183,'combo',['A (06:00 - 14:00)','B (14:00 - 22:00)','C (22:00 - 06:00)'])
        self.mode=c('mode',159,189,128,'combo',['AGGREGATION','SERIALIZATION'])
        c('line_active',292,189,57,'toggle').setToolTip('Aktif/nonaktif penerimaan scan pada line.')
        c('start_delay',159,238,87,'float',minimum=0,maximum=600);c('stop_delay',253,238,89,'float',minimum=0,maximum=600)
        c('cache_limit',159,268,183,'int',minimum=1,maximum=100000)
        c('auto_upload',159,297,170,'toggle')
        c('upload_timeout',159,327,183,'int',minimum=1,maximum=120)
        c('mfd',159,356,183,'date');c('language',159,385,183,'combo',['BAHASA INDONESIA','ENGLISH'])
        c('theme',159,414,183,'combo',['DARK BLUE','HIGH CONTRAST'])

    def build_api(self):
        self.host=self.control('server_host',496,127,178)
        self.host.setToolTip('Host atau host:port untuk tes jangkauan TCP. Database aplikasi menggunakan SQLite lokal.')
        self.url=self.control('project_url',496,167,178);self.url.setToolTip('Base URL server. Tes: /health, unggah: /v1/upload, versi: /version.json.')
        self.token=self.control('api_token',496,207,145);self.token.setEchoMode(QLineEdit.EchoMode.Password)
        self.button('reveal_token',646,207,28,27,'◉').setToolTip('Tampilkan/sembunyikan API token')
        self.interval=self.control('sync_interval',496,247,178,'int',minimum=5,maximum=86400)
        self.retry=self.control('retry_count',496,287,178,'int',minimum=0,maximum=10)
        self.button('test_connection',382,380,292,46,'TEST KONEKSI SEKARANG',icon='database')

    def build_printers(self):
        names=[p.printerName() for p in QPrinterInfo.availablePrinters()]
        ref=defaults()['printers'];xs=(790,894,998)
        for level,x in zip(LEVELS,xs):
            base='printers.'+level+'.'
            device=self.control(base+'device',x,155,98,'editable',list(dict.fromkeys([ref[level]['device']]+names)))
            device.setToolTip('Nama driver printer OS, atau tcp://192.168.x.x:9100 untuk Zebra ZPL.')
            setattr(self,'printer_'+level.lower(),device)
            self.control(base+'dpi',x,190,98,'combo',[203,300,600])
            self.control(base+'darkness',x,225,98,'int',minimum=0,maximum=30).setToolTip('Diterapkan pada ZPL TCP. Untuk driver OS gunakan preferensi driver.')
            self.control(base+'speed',x,260,98,'int',minimum=1,maximum=14).setSuffix(' IPS')
            self.control(base+'label',x,295,98,'editable',['60 x 40 mm','100 x 60 mm','100 x 150 mm'])
        self.button('test_print_all',714,380,380,46,'TEST PRINT SEMUA PRINTER',icon='printer')

    def build_devices(self):
        ports=[p.portName() for p in QSerialPortInfo.availablePorts()]
        for level,x in SCANNER_COLUMNS:
            key='scanners.'+level+'.';ref=defaults()['scanners'][level];y=SCANNER_ROWS
            self.control(key+'device',x,y[0],105)
            if level!='PALLET':
                # PALLET reads with a scanner gun only, so it has no camera rows.
                mode=self.control(key+'mode',x,y[1],105,'combo',list(SCAN_MODES))
                mode.setToolTip('SCANNER GUN membaca dari port COM/keyboard. KAMERA IP membaca barcode dari snapshot kamera jaringan.')
                setattr(self,'scan_mode_'+level.lower(),mode)
            widget=self.control(key+'port',x,y[2],105,'editable',list(dict.fromkeys([ref['port'],'KEYBOARD']+ports)))
            setattr(self,'scanner_'+level.lower(),widget)
            if level!='PALLET':
                self.control(key+'camera_ip',x,y[3],105).setToolTip('IP atau http://IP kamera scanner. Path opsional, contoh 192.168.10.31/snapshot.jpg.')
                self.control(key+'camera_port',x,y[4],105,'int',minimum=1,maximum=65535).setToolTip('Port HTTP kamera scanner, contoh 8080.')
            self.control(key+'trigger',x,y[5],105,'combo',['AUTO','MANUAL'])
            self.control(key+'autofocus',x,y[6],105,'toggle')
            self.control(key+'exposure',x,y[7],105,'int',minimum=1,maximum=10000).setSuffix(' ms')
            self.control(key+'resolution',x,y[8],105,'combo',['640 x 480','1280 x 720','1920 x 1080'])
        y=CAMERA_ROWS
        self.control('camera.device',515,y[0],97)
        self.camera_ip=self.control('camera.address',515,y[1],97)
        self.camera_ip.setToolTip('Alamat IP/URL snapshot atau ID kamera USB. Pilih perangkat melalui Kalibrasi Kamera.')
        self.control('camera.trigger',515,y[2],97,'combo',['AUTO','MANUAL'])
        self.control('camera.autofocus',515,y[3],97,'toggle')
        self.control('camera.exposure',515,y[4],97,'int',minimum=1,maximum=10000).setSuffix(' ms')
        self.control('camera.resolution',515,y[5],97,'combo',['640 x 480','1280 x 720','1920 x 1080'])
        self.camera_preview=QLabel(self);self.camera_preview.setGeometry(452,700,160,145);self.camera_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.button('calibrate_scanner',26,859,301,31,'KALIBRASI SCANNER',icon='scanner')
        self.button('calibrate_camera',349,859,263,31,'KALIBRASI KAMERA',icon='camera')

    def build_users(self):
        self.button('add_user',884,462,104,26,'TAMBAH USER');self.button('edit_user',997,462,96,26,'EDIT ROLE')
        self.users_grid=self.table(649,497,445,180,['USERNAME','ROLE','SHIFT','STATUS'],[145,145,60,95])
        self.users_grid.setObjectName('settings_users');self.users_grid.verticalHeader().setDefaultSectionSize(21)
        self.users_grid.horizontalHeader().setFixedHeight(24)
        self.users_grid.setStyleSheet(self.users_grid.styleSheet()+' QTableWidget::item{padding:1px 4px;font-size:11px;} QHeaderView::section{padding:2px;font-size:10px;}')
        self.users_grid.doubleClicked.connect(lambda:self.local_action('edit_user'))

    def build_maintenance(self):
        self.button('backup_now',1009,696,84,23,'BACKUP',icon='database')
        self.control('backup_frequency',786,730,154,'combo',['SETIAP HARI','SETIAP MINGGU','NONAKTIF'])
        self.control('backup_time',948,730,139,'time')
        self.control('backup_days',786,758,116,'int',minimum=1,maximum=3650)
        self.button('restore_config',786,787,117,23,'RESTORE','#9a6b05')
        self.button('export_config',920,787,168,23,'EXPORT KONFIG')
        self.button('clear_temp',786,813,117,23,'BERSIHKAN','#ab3831')
        self.button('export_log',786,839,117,23,'EXPORT LOG')
        self.button('check_update',786,882,117,21,'CEK SEKARANG')

    def collect(self):
        cfg=deepcopy(self.repo.load())
        for key,widget in self.controls.items():
            parts=key.split('.');obj=cfg
            for part in parts[:-1]:obj=obj[part]
            leaf=parts[-1]
            if isinstance(widget,Toggle):value=widget.isChecked()
            elif isinstance(widget,QDateEdit):value=widget.date().toString('yyyy-MM-dd')
            elif isinstance(widget,QTimeEdit):value=widget.time().toString('HH:mm')
            elif isinstance(widget,(QSpinBox,QDoubleSpinBox)):value=widget.value()
            elif isinstance(widget,ThemedComboBox):value=widget.currentText()
            else:value=widget.text().strip()
            if key=='shift':value=value.split()[0]
            if leaf=='dpi':value=int(value)
            obj[leaf]=value
        return cfg

    def populate(self,cfg):
        self.loading=True
        for key,widget in self.controls.items():
            value=cfg
            for part in key.split('.'):value=value[part]
            if isinstance(widget,Toggle):widget.setChecked(value)
            elif isinstance(widget,QDateEdit):widget.setDate(QDate.fromString(value,'yyyy-MM-dd'))
            elif isinstance(widget,QTimeEdit):widget.setTime(QTime.fromString(value,'HH:mm'))
            elif isinstance(widget,(QSpinBox,QDoubleSpinBox)):widget.setValue(value)
            elif isinstance(widget,ThemedComboBox):
                if key=='shift':widget.setCurrentIndex(['A','B','C'].index(value))
                else:widget.setCurrentText(str(value))
                if widget.isEditable():widget.lineEdit().setCursorPosition(0)
                widget.setToolTip(widget.toolTip() or str(value))
            else:widget.setText(str(value));widget.setCursorPosition(0)
        self.loading=False

    def load(self):
        cfg=self.repo.load();self.populate(cfg);self.dirty=False;self.apply_appearance(cfg);self.refresh()
        if hasattr(self,'appearance_panel'):self.appearance_panel.reload()
    def apply_appearance(self,cfg):
        from .localization import set_language
        set_language(cfg['language'],TRANSLATIONS)
        self._english=cfg['language']=='ENGLISH';self.high_contrast=cfg['theme']=='HIGH CONTRAST'
        self.subtitle=self.tr('KONFIGURASI SISTEM & PERANGKAT')
        for button in self.buttons.values():button.setText(self.tr(button.property('label_key')))
        style=CONTROL_STYLE+(' QLineEdit,QComboBox,QAbstractSpinBox {background:#000;color:#fff;border:1px solid #c9e6ff;}' if self.high_contrast else '')
        for key,control in self.controls.items():
            compact=' QComboBox,QLineEdit,QAbstractSpinBox{font-size:10px;padding-left:3px;padding-right:3px;} QComboBox::drop-down{width:14px;}' if key.startswith('printers.') or key.endswith(('.resolution','.device','.mode','.camera_ip','.camera_port')) or key=='mode' else ''
            control.setStyleSheet(style+compact)
            if isinstance(control,ThemedComboBox):
                # The shared combo stylesheet reserves arrow space already.
                # Avoid applying that padding a second time to its line edit.
                from PySide6.QtWidgets import QComboBox
                QComboBox.setStyleSheet(control,control.styleSheet()+' QComboBox{padding:2px 0px 2px 4px;} QComboBox::drop-down{width:14px;}')
                if control.isEditable():
                    control.lineEdit().setStyleSheet('QLineEdit{padding:0;margin:0;border:0;background:transparent;font-size:'+('10' if compact else '12')+'px;}')
                    control.lineEdit().setTextMargins(0,0,0,0);control.lineEdit().setCursorPosition(0)
            control.setProperty('_display_base_style',control.styleSheet())
            if isinstance(control,ThemedComboBox) and control.isEditable():
                control.lineEdit().setProperty('_display_base_style',control.lineEdit().styleSheet())
        self.update()
    def save(self):
        try:
            cfg=self.repo.save(self.collect());self.dirty=False;self.runtime.apply();self.apply_appearance(cfg)
            self.notify('Semua pengaturan tersimpan di database lokal.');self.changed.emit();return True
        except (ValueError,TypeError,KeyError) as exc:self.notify(str(exc),True);return False
    def ready(self):return self.save() if self.dirty else True

    def refresh(self):
        if not hasattr(self,'users_grid'):return
        if not self.dirty and not self.loading:
            cfg=self.repo.load()
            self.populate(cfg)
            if self._english!=(cfg['language']=='ENGLISH') or self.high_contrast!=(cfg['theme']=='HIGH CONTRAST'):self.apply_appearance(cfg)
        selected=self.users_grid.currentRow();self.user_rows=self.repo.users();self.users_grid.setRowCount(len(self.user_rows))
        for i,row in enumerate(self.user_rows):
            for j,value in enumerate((row['username'],row['role'],row['shift'],'AKTIF' if row['active'] else 'NONAKTIF')):
                item=QTableWidgetItem(value)
                if j==3:item.setForeground(QColor(GREEN if row['active'] else MUTED))
                self.users_grid.setItem(i,j,item)
        if 0<=selected<len(self.user_rows):self.users_grid.selectRow(selected)
        self.update()

    def local_action(self,name):
        try:
            if name=='save_settings':self.save()
            elif name=='reload_settings':
                if self.dirty and MessageBox.question(self,'Muat ulang','Abaikan perubahan yang belum disimpan?')!=MessageBox.StandardButton.Yes:return
                self.load();self.notify('Pengaturan dimuat ulang dari database.')
            elif name=='reset_settings':
                if MessageBox.question(self,'Reset default','Kembalikan seluruh form ke nilai default? Tekan Simpan untuk menerapkannya.')!=MessageBox.StandardButton.Yes:return
                self.populate(defaults());self.edited();self.notify('Form dikembalikan ke default. Tekan Simpan untuk menerapkan.')
            elif name=='reveal_token':self.token.setEchoMode(QLineEdit.EchoMode.Normal if self.token.echoMode()==QLineEdit.EchoMode.Password else QLineEdit.EchoMode.Password)
            elif name in ('test_connection','test_devices','test_print_all','calibrate_scanner','calibrate_camera','backup_now','check_update'):
                if not self.ready():return
                if name=='test_connection':self.runtime.test_connection()
                elif name=='test_devices':self.runtime.test_all();self.notify('Pemeriksaan device berjalan. Lihat hasil pada panel kanan.')
                elif name=='test_print_all':self.test_print()
                elif name=='calibrate_scanner':
                    for serial in self.runtime.scanner_ports.values():serial.close()
                    ScannerCalibration(self.runtime,self).exec();self.load()
                elif name=='calibrate_camera':CameraCalibration(self.runtime,self).exec();self.load()
                elif name=='backup_now':path=self.repo.backup();self.notify('Backup tersimpan: '+str(path))
                elif name=='check_update':self.runtime.check_update()
            elif name in ('add_user','edit_user'):
                row=self.users_grid.currentRow()
                if name=='edit_user' and row<0:self.notify('Pilih user yang akan diubah.',True);return
                dialog=UserEditor(self.repo,self,self.user_rows[row] if name=='edit_user' else None)
                if dialog.exec()==QDialog.DialogCode.Accepted:self.refresh();self.changed.emit();self.notify('Profil user tersimpan.')
            elif name=='restore_config':
                path,_=FileDialog.getOpenFileName(self,'Restore konfigurasi',str(self.repo.root/'backups'),'Konfigurasi (*.json *.sqlite3 *.db)')
                if not path:return
                if MessageBox.question(self,'Restore konfigurasi','Terapkan konfigurasi dari berkas ini? Konfigurasi sekarang dicadangkan terlebih dahulu; data produksi tetap dipertahankan.')!=MessageBox.StandardButton.Yes:return
                self.repo.restore(path);self.load();self.runtime.apply();self.changed.emit();self.notify('Konfigurasi berhasil dipulihkan.')
            elif name=='export_config':
                if not self.ready():return
                path,_=FileDialog.getSaveFileName(self,'Export konfigurasi','konfigurasi-agregasi.json','JSON (*.json)')
                if path:self.repo.export_configuration(path);self.notify('Konfigurasi diekspor tanpa API token.')
            elif name=='clear_temp':
                count,size=self.repo.clear_temp();self.notify(f'{count} berkas sementara ({size:,} byte) dibersihkan. Data produksi dan backup tetap tersimpan.')
            elif name=='export_log':
                path,_=FileDialog.getSaveFileName(self,'Export log sistem','log-agregasi.csv','CSV (*.csv)')
                if path:self.repo.export_log(path);self.notify('Log sistem berhasil diekspor.')
        except Exception as exc:self.notify(str(exc),True)
        self.update()

    def test_print(self):
        from .template_model import default_document,new_element
        from .label_render import export_pdf
        from .ui_dialogs import dialog_parent
        owner=dialog_parent(self);results=[];cfg=self.repo.load()
        for level in LEVELS:
            profile=cfg['printers'][level];doc=default_document(level)
            doc['dpi']=profile['dpi'];doc['width_mm'],doc['height_mm']=map(float,profile['label'].removesuffix(' mm').split(' x '))
            # A bounded test pattern fits every selected label size.
            doc['elements']=[new_element('text',3,3,doc['width_mm']-6,8,text='TEST PRINTER '+level,font=12),
                             new_element('text',3,14,doc['width_mm']-6,8,text=f'{profile["dpi"]} DPI / {profile["speed"]} IPS / MD {profile["darkness"]}',font=9)]
            try:
                if profile['device'].startswith('tcp://'):self.runtime.print_zpl(doc)
                else:
                    printer=self.runtime.configured_printer(level)
                    if not hasattr(owner,'pages'):raise ValueError('Host aplikasi belum tersedia.')
                    owner.pages['template'].print_document(doc,printer=printer,confirm=False)
                results.append(level+': tugas dikirim.');self.runtime.set_status('printer_'+level,'TERKIRIM','Periksa label fisik pada printer.')
            except Exception as exc:
                results.append(level+': '+str(exc));self.runtime.set_status('printer_'+level,'GAGAL',str(exc))
        with self.store.db:self.store.audit('TEST PRINT',' | '.join(results))
        dialog=AppDialog(self);dialog.setWindowTitle('Hasil test print');dialog.resize(640,390);layout=QVBoxLayout(dialog)
        output=QPlainTextEdit('\n\n'.join(results));output.setReadOnly(True);layout.addWidget(output)
        row=QHBoxLayout();pdf=QPushButton('Simpan pola tes PDF');close=QPushButton('Tutup');row.addWidget(pdf);row.addWidget(close);layout.addLayout(row)
        def save_pdf():
            path,_=FileDialog.getSaveFileName(dialog,'Simpan pola tes PDF','test-printer.pdf','PDF (*.pdf)')
            if path:
                try:export_pdf(doc,path);self.notify('Pola tes PDF disimpan.')
                except Exception as exc:self.notify(str(exc),True)
        pdf.clicked.connect(save_pdf);close.clicked.connect(dialog.accept);dialog.exec()

    def show_camera_image(self,image):
        from PySide6.QtGui import QPixmap
        self.camera_preview.setPixmap(QPixmap.fromImage(image).scaled(self.camera_preview.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))

    def rect(self,x,y,w,h,c1='#062c4a',c2='#001b30',stroke='#385e78',radius=6,shadow=False):
        if getattr(self,'high_contrast',False) and c1 in ('#062c4a','#04283f','#042b40'):
            c1=c2='#000814';stroke='#8bb1c8'
        return super().rect(x,y,w,h,c1,c2,stroke,radius,shadow)

    def paint_content(self):
        if getattr(self,'_display_tab_active',False):return
        for x,y,w,h,title,icon in [(15,75,342,372,'PENGATURAN LINE PRODUKSI','settings'),(368,75,321,372,'KONEKSI DATABASE / API','database'),
            (700,75,407,372,'PENGATURAN PRINTER','printer'),(15,456,611,445,'PENGATURAN SCANNER & KAMERA','camera'),
            (637,456,470,230,'MANAJEMEN USER & AKSES','user'),(637,692,470,215,'BACKUP, LOG, & MAINTENANCE','settings')]:
            self.panel(x,y,w,h);self.icon(icon,x+14,y+12,22);self.text(x+48,y+9,194 if title=='MANAJEMEN USER & AKSES' else w-148 if title=='BACKUP, LOG, & MAINTENANCE' else w-60,27,title,11 if title=='MANAJEMEN USER & AKSES' else 12,bold=True);self.line(x+12,y+38,w-24)
        for key,y in [('NAMA LINE',127),('SHIFT DEFAULT',158),('MODE AGREGASI',189),('WAKTU CONVEYOR (DETIK)',234),('LIMIT CACHE DATA',268),('AUTO UPLOAD DATA',297),('TIMEOUT UPLOAD (DETIK)',327),('DEFAULT MFD',356),('BAHASA SISTEM',385),('TEMA SISTEM',414)]:self.text(29,y,124,27,key,10,MUTED)
        self.text(159,219,90,19,'START DELAY',9,MUTED);self.text(253,219,90,19,'STOP DELAY',9,MUTED)
        for key,y in [('SERVER HOST',127),('PROJECT URL',167),('TOKEN / API KEY',207),('SYNC INTERVAL (DETIK)',247),('RETRY COUNT',287)]:self.text(382,y,108,27,key,10,MUTED,wrap=True)
        self.line(382,324,292);self.text(382,328,127,20,'TEST KONEKSI TERAKHIR',9,MUTED);self.text(510,328,164,20,self.runtime.last_test or 'Belum dites',10)
        self.text(382,351,122,20,'STATUS KONEKSI',10,MUTED);api=self.runtime.status.get('api',{});self.text(505,351,169,20,api.get('status','BELUM DITES'),11,GREEN if api.get('status')=='ONLINE' else YELLOW)
        for level,x,color in [('BOX',790,BLUE),('CARTON',894,GREEN),('PALLET',998,'#b985ef')]:self.text(x,126,98,24,level,11,color,True,Qt.AlignmentFlag.AlignCenter)
        for key,y in [('PRINTER DEVICE',155),('DPI',190),('DARKNESS',225),('PRINT SPEED',260),('UKURAN LABEL',295)]:self.text(714,y,73,27,key,10,MUTED,wrap=True)
        self.text(716,332,377,32,'ZPL TCP: darkness & speed • Driver OS: preferensi printer',10,MUTED,wrap=True)
        for x,w,label,color in [(110,105,'BOX','#086fb3'),(224,105,'CARTON','#087c48'),(338,105,'PALLET','#0a6a8f'),(452,160,'KAMERA VERIFIKASI','#553878')]:self.rect(x,499,w,22,color,color,color,2);self.text(x,499,w,22,label,10,WHITE,True,Qt.AlignmentFlag.AlignCenter)
        for label,y in zip(('DEVICE NAME','MODE SCAN','KONEKSI (COM)','IP KAMERA','PORT KAMERA','TRIGGER MODE','AUTOFOCUS','EXPOSURE','RESOLUSI'),SCANNER_ROWS):self.text(28,y,80,27,label,10,MUTED)
        self.text(28,782,80,27,'STATUS',10,MUTED)
        for label,y in zip(('DEVICE','ALAMAT','TRIGGER','FOKUS','EXPOSURE','RESOLUSI'),CAMERA_ROWS):self.text(452,y,60,27,label,9,MUTED)
        for level,x in SCANNER_COLUMNS:
            self.rect(x,782,105,63,'#112936','#041d2c','#426176');self.icon('scanner',x+42,787,21)
            value=self.runtime.status.get('scanner_'+level,{}).get('status','BELUM DITES');self.text(x+4,810,97,32,value,9,MUTED,align=Qt.AlignmentFlag.AlignCenter,wrap=True)
        self.rect(452,700,160,145,'#112936','#041d2c','#426176')
        if self.camera_preview.pixmap().isNull():self.icon('camera',505,745,46)
        for title,y in [('BACKUP OTOMATIS',730),('SIMPAN BACKUP',758),('RESTORE KONFIGURASI',787),('BERSIHKAN FILE TEMP',813),('EXPORT LOG SISTEM',839),('VERSI SISTEM',862),('CEK UPDATE',882)]:self.text(652,y,132,24,title,10,MUTED)
        self.text(910,758,40,27,'hari',10,MUTED);self.text(786,862,115,21,'v'+VERSION,11)
        self.text(917,857,175,45,self.runtime.last_update,9,GREEN if 'terbaru' in self.runtime.last_update else MUTED,wrap=True)
        self.text(16,973,1089,23,self.message,11,'#9e281f' if self.message_error else '#174367',align=Qt.AlignmentFlag.AlignCenter)

    def sidebar(self):
        from .shared_sidebar import paint_sidebar
        paint_sidebar(self)

    def may_close(self):
        if not self.dirty:return True
        choice=MessageBox.question(self,'Pengaturan belum disimpan','Simpan perubahan pengaturan sebelum menutup aplikasi?',MessageBox.StandardButton.Save|MessageBox.StandardButton.Discard|MessageBox.StandardButton.Cancel,MessageBox.StandardButton.Save)
        if choice==MessageBox.StandardButton.Save:return self.save()
        return choice==MessageBox.StandardButton.Discard
    def shutdown(self):self.runtime.shutdown()
