"""Operator editing and real scanner/camera calibration tools."""
from PySide6.QtCore import Qt, QIODevice, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QCheckBox, QPushButton, QPlainTextEdit, QSpinBox)
from PySide6.QtSerialPort import QSerialPort, QSerialPortInfo
from .ui_controls import ThemedComboBox
from .ui_dialogs import AppDialog, MessageBox
from .settings_model import ROLES


class UserEditor(AppDialog):
    def __init__(self, repo, parent=None, record=None):
        super().__init__(parent); self.repo=repo; self.record=record
        self.setWindowTitle('Edit role & profil' if record else 'Tambah user')
        self.resize(470,340)
        layout=QVBoxLayout(self); form=QFormLayout()
        self.username=QLineEdit(record['username'] if record else '')
        self.role=ThemedComboBox(); self.role.addItems(ROLES)
        self.shift=ThemedComboBox(); self.shift.addItems(['ALL','A','B','C'])
        self.active=QCheckBox('AKTIF'); self.active.setChecked(bool(record['active']) if record else True)
        if record:self.role.setCurrentText(record['role']); self.shift.setCurrentText(record['shift'])
        for label,widget in [('Username',self.username),('Role',self.role),('Shift',self.shift),('Status',self.active)]:form.addRow(label,widget)
        layout.addLayout(form)
        note=QLabel('Profil operator lokal digunakan untuk identitas dan pencatatan aktivitas. Autentikasi server belum dikonfigurasi.'); note.setWordWrap(True); layout.addWidget(note)
        self.error=QLabel(); self.error.setWordWrap(True); self.error.setStyleSheet('color:#ffc76b');layout.addWidget(self.error)
        row=QHBoxLayout(); save=QPushButton('Simpan'); cancel=QPushButton('Batal'); row.addWidget(save);row.addWidget(cancel);layout.addLayout(row)
        save.clicked.connect(self.save); cancel.clicked.connect(self.reject)
    def save(self):
        try:
            self.repo.save_user(self.username.text(),self.role.currentText(),self.shift.currentText(),self.active.isChecked(),self.record['username'] if self.record else None)
            self.accept()
        except ValueError as exc:self.error.setText(str(exc))


class ScannerCalibration(AppDialog):
    def __init__(self,runtime,parent=None):
        super().__init__(parent); self.runtime=runtime; self.serial=QSerialPort(self); self.buffer=bytearray(); self.armed=False
        self.setWindowTitle('Kalibrasi scanner BOX / CARTON / PALLET'); self.resize(680,510)
        layout=QVBoxLayout(self); form=QFormLayout()
        self.level=ThemedComboBox();self.level.addItems(['BOX','CARTON','PALLET'])
        self.port=ThemedComboBox();self.port.setEditable(True)
        self.port.addItems(['KEYBOARD']+[p.portName() for p in QSerialPortInfo.availablePorts()])
        self.baud=ThemedComboBox();self.baud.addItems(['9600','19200','38400','57600','115200'])
        for title,widget in [('Scanner',self.level),('Port',self.port),('Baud rate (8-N-1)',self.baud)]:form.addRow(title,widget)
        layout.addLayout(form)
        self.note=QLabel('Hubungkan scanner, lalu pindai satu barcode. Untuk USB HID pilih KEYBOARD.');self.note.setWordWrap(True);layout.addWidget(self.note)
        self.input=QLineEdit();self.input.setPlaceholderText('Hasil scan keyboard / Enter');layout.addWidget(self.input)
        self.output=QPlainTextEdit();self.output.setReadOnly(True);layout.addWidget(self.output)
        note=QLabel('Autofocus, exposure dan resolusi adalah profil perangkat. Pengaturan optik scanner memerlukan SDK vendor; port serial/HID hanya menyediakan data barcode.');note.setWordWrap(True);layout.addWidget(note)
        row=QHBoxLayout()
        for title,call in [('Hubungkan',self.connect_port),('Terima 1 scan',self.arm),('Tutup',self.accept)]:
            button=QPushButton(title);button.clicked.connect(call);row.addWidget(button)
        layout.addLayout(row)
        self.serial.readyRead.connect(self.read)
        self.serial.errorOccurred.connect(self.serial_error)
        self.input.returnPressed.connect(lambda:self.receive(self.input.text()))
        self.level.currentTextChanged.connect(self.load);self.finished.connect(lambda _:self.serial.close());self.load()
    def load(self):
        self.serial.close(); self.buffer.clear(); self.armed=False
        cfg=self.runtime.repo.load()['scanners'][self.level.currentText()]
        self.port.setCurrentText(cfg['port']);self.baud.setCurrentText(str(cfg['baud']))
    def arm(self):
        self.armed=True;self.input.setFocus();self.note.setText('Siap menerima satu barcode untuk kalibrasi.')
    def connect_port(self):
        self.serial.close(); self.buffer.clear()
        cfg=self.runtime.repo.load(); level=self.level.currentText();profile=cfg['scanners'][level]
        profile['port']=self.port.currentText().strip();profile['baud']=int(self.baud.currentText())
        if profile['port']!='KEYBOARD':
            self.serial.setPortName(profile['port']);self.serial.setBaudRate(profile['baud'])
            self.serial.setDataBits(QSerialPort.DataBits.Data8);self.serial.setParity(QSerialPort.Parity.NoParity)
            self.serial.setStopBits(QSerialPort.StopBits.OneStop);self.serial.setFlowControl(QSerialPort.FlowControl.NoFlowControl)
            if not self.serial.open(QIODevice.OpenModeFlag.ReadOnly):
                self.note.setText(self.serial.errorString());self.runtime.set_status('scanner_'+level,'GAGAL',self.serial.errorString());return
        self.runtime.repo.save(cfg);self.runtime.set_status('scanner_'+level,'MENUNGGU SCAN',profile['port'])
        self.arm();self.note.setText('Port siap. Pindai barcode untuk memverifikasi hasil baca.')
    def read(self):
        self.buffer.extend(bytes(self.serial.readAll()))
        if len(self.buffer)>8192:self.buffer.clear();self.note.setText('Data terlalu panjang; periksa baud rate dan terminator.');return
        while b'\n' in self.buffer or b'\r' in self.buffer:
            indexes=[self.buffer.index(c) for c in (b'\n',b'\r') if c in self.buffer]
            end=min(indexes);raw=bytes(self.buffer[:end]);del self.buffer[:end+1]
            if raw:self.receive(raw.decode('utf-8',errors='replace'))
    def receive(self,value):
        value=value.strip();level=self.level.currentText();profile=self.runtime.repo.load()['scanners'][level]
        if not value:return
        if profile['trigger']=='MANUAL' and not self.armed:self.note.setText('Tekan Terima 1 scan sebelum memindai.');return
        self.armed=False;self.input.clear();self.output.appendPlainText(level+' • '+value)
        self.runtime.set_status('scanner_'+level,'ONLINE','Barcode berhasil diterima.')
        with self.runtime.store.db:self.runtime.store.audit('KALIBRASI SCANNER',level+'; '+str(len(value))+' karakter terbaca')
        self.note.setText('Barcode terbaca. Kalibrasi tidak menambah data produksi.')
    def serial_error(self,error):
        if error not in (QSerialPort.SerialPortError.NoError,QSerialPort.SerialPortError.NotOpenError):self.note.setText(self.serial.errorString())


class CameraCalibration(AppDialog):
    def __init__(self,runtime,parent=None):
        super().__init__(parent); self.runtime=runtime;self.camera=None;self.session=None;self.sink=None;self.last_image=None;self.devices=[]
        self.setWindowTitle('Kalibrasi kamera pallet');self.resize(760,650)
        layout=QVBoxLayout(self);form=QFormLayout()
        self.device=ThemedComboBox();self.device.addItem('Kamera IP / snapshot URL',None)
        try:
            from PySide6.QtMultimedia import QMediaDevices
            self.devices=QMediaDevices.videoInputs()
        except ImportError:pass
        for i,d in enumerate(self.devices):self.device.addItem(d.description(),i)
        cfg=runtime.repo.load()['camera']
        self.address=QLineEdit(cfg['address'])
        for i,d in enumerate(self.devices):
            if d.description()==cfg['device']:self.device.setCurrentIndex(i+1)
        form.addRow('Perangkat',self.device);form.addRow('URL snapshot / ID',self.address);layout.addLayout(form)
        self.preview=QLabel('Preview kamera');self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter);self.preview.setMinimumSize(600,330);self.preview.setStyleSheet('background:#011825;border:1px solid #37617b;');layout.addWidget(self.preview,1)
        self.note=QLabel('Untuk kamera IP, gunakan URL yang langsung mengembalikan JPEG/PNG. Kamera USB memakai driver OS.');self.note.setWordWrap(True);layout.addWidget(self.note)
        row=QHBoxLayout()
        for label,call in [('Mulai preview',self.start),('Ambil frame',self.capture),('Simpan kalibrasi',self.save),('Tutup',self.accept)]:
            b=QPushButton(label);b.clicked.connect(call);row.addWidget(b)
        layout.addLayout(row)
        runtime.camera_image.connect(self.show_image);self.finished.connect(self.cleanup)
    def start(self):
        if self.camera:self.camera.stop();self.camera.deleteLater();self.camera=None
        cfg=self.runtime.repo.load()['camera'];index=self.device.currentData()
        if index is None:
            url=self.address.text().strip()
            if not url.startswith(('http://','https://')):self.note.setText('Masukkan URL snapshot lengkap, misalnya http://IP/snapshot.jpg.');return
            self.note.setText('Mengambil snapshot…')
            def result(code,body,error):
                from PySide6.QtGui import QImage
                image=QImage.fromData(body)
                if not (200<=code<300) or error or image.isNull():self.note.setText('Gambar tidak diterima. Periksa URL, autentikasi dan koneksi kamera.');return
                self.show_image(image);self.runtime.set_status('camera','ONLINE','Snapshot diterima.');self.note.setText('Snapshot diterima. Kontrol optik kamera IP memerlukan API vendor.')
            self.runtime.request(url,result);return
        from PySide6.QtMultimedia import QCamera,QMediaCaptureSession,QVideoSink
        device=self.devices[index];self.camera=QCamera(device,self);self.session=QMediaCaptureSession(self);self.sink=QVideoSink(self)
        self.session.setCamera(self.camera);self.session.setVideoSink(self.sink)
        self.sink.videoFrameChanged.connect(lambda frame:self.show_image(frame.toImage()))
        self.camera.errorOccurred.connect(lambda _,text:self.note.setText(text))
        desired=tuple(map(int,cfg['resolution'].split(' x ')))
        matching=next((f for f in device.videoFormats() if (f.resolution().width(),f.resolution().height())==desired),None)
        unsupported=[]
        if matching:self.camera.setCameraFormat(matching)
        else:unsupported.append('resolusi')
        mode=QCamera.FocusMode.FocusModeAuto if cfg['autofocus'] else QCamera.FocusMode.FocusModeManual
        if self.camera.isFocusModeSupported(mode):self.camera.setFocusMode(mode)
        else:unsupported.append('focus mode')
        if self.camera.isExposureModeSupported(QCamera.ExposureMode.ExposureManual):
            self.camera.setExposureMode(QCamera.ExposureMode.ExposureManual);self.camera.setManualExposureTime(cfg['exposure']/1000)
        else:unsupported.append('exposure manual')
        self.camera.start();self.note.setText('Preview aktif.'+(' Driver tidak mendukung: '+', '.join(unsupported)+'.' if unsupported else ''))
    def show_image(self,image):
        if image.isNull():return
        first=self.last_image is None
        self.last_image=image.copy();self.preview.setPixmap(QPixmap.fromImage(image).scaled(self.preview.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        self.runtime.set_status('camera','ONLINE','Frame diterima.')
        if first and self.runtime.repo.load()['camera']['trigger']=='AUTO':self.capture()
    def capture(self):
        if self.last_image is None:self.note.setText('Jalankan preview dan tunggu frame kamera terlebih dahulu.');return
        folder=self.runtime.repo.root/'temp';folder.mkdir(exist_ok=True)
        path=folder/'camera-calibration.png'
        if self.last_image.save(str(path)):self.note.setText('Frame kalibrasi disimpan sementara: '+path.name)
        else:self.note.setText('Frame tidak dapat disimpan.')
    def save(self):
        if self.last_image is None:self.note.setText('Kalibrasi harus menerima frame sebelum disimpan.');return
        cfg=self.runtime.repo.load();index=self.device.currentData()
        if index is None:cfg['camera']['address']=self.address.text().strip()
        else:
            device=self.devices[index];cfg['camera']['device']=device.description();cfg['camera']['address']=bytes(device.id()).decode(errors='replace')
        try:
            self.runtime.repo.save(cfg)
            with self.runtime.store.db:self.runtime.store.audit('KALIBRASI KAMERA',cfg['camera']['device'])
            self.note.setText('Profil kamera dan hasil kalibrasi tersimpan.');self.runtime.changed.emit()
        except ValueError as exc:self.note.setText(str(exc))
    def cleanup(self,*_):
        if self.camera:self.camera.stop()
        try:self.runtime.camera_image.disconnect(self.show_image)
        except (RuntimeError,TypeError):pass
