"""Read real barcode frames for Pallet input or operator label verification."""
from PySide6.QtCore import Signal,QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QPushButton,QLabel
from .settings_dialogs import CameraCalibration


def decode_frame(image):
    if image is None or image.isNull():return []
    import zxingcpp
    from PIL import Image
    gray=image.convertToFormat(QImage.Format.Format_Grayscale8)
    frame=Image.frombytes('L',(gray.width(),gray.height()),bytes(gray.constBits()),'raw','L',gray.bytesPerLine())
    return list(dict.fromkeys(code.text for code in zxingcpp.read_barcodes(frame) if code.text))


class PalletCamera(CameraCalibration):
    decoded=Signal(str)
    def __init__(self,runtime,parent=None):
        self.closed=False;self.cleaned=False;self.last_code='';self.preview_started=False
        super().__init__(runtime,parent);self.setWindowTitle('Kamera Pallet • scan barcode / verifikasi label')
        self.decoded_label=QLabel('Kode terbaca: —');self.decoded_label.setWordWrap(True);self.layout().addWidget(self.decoded_label)
        button=QPushButton('BACA BARCODE FRAME');button.setObjectName('pallet_decode_frame');button.clicked.connect(lambda:self.read_barcode(force=True));self.layout().addWidget(button)
        self.scan_timer=QTimer(self);self.scan_timer.setInterval(300);self.scan_timer.timeout.connect(self.auto_read);self.scan_timer.start()
        self.snapshot_timer=QTimer(self);self.snapshot_timer.setInterval(1500);self.snapshot_timer.timeout.connect(self.next_snapshot);self.snapshot_timer.start()
    def start(self):
        if self.closed:return
        self.preview_started=True;super().start()
    def next_snapshot(self):
        if self.preview_started and not self.closed and not self.runtime.stopped and self.device.currentData() is None and not self.runtime.replies and self.runtime.repo.load()['camera']['trigger']=='AUTO':super().start()
    def auto_read(self):
        if self.closed or self.runtime.stopped:return
        if self.runtime.repo.load()['camera']['trigger']=='AUTO':self.read_barcode()
    def read_barcode(self,force=False):
        if self.closed:return
        if self.last_image is None:
            if force:self.decoded_label.setText('Belum ada frame. Jalankan preview kamera terlebih dahulu.')
            return
        try:codes=decode_frame(self.last_image)
        except Exception as exc:self.decoded_label.setText('Barcode tidak dapat dibaca: '+str(exc));return
        if len(codes)>1:
            self.decoded_label.setText('Beberapa barcode terlihat. Arahkan satu label carton/pallet ke kamera.');return
        if not codes:self.last_code='';self.decoded_label.setText('Belum terbaca. Dekatkan satu label dan pastikan fokus.');return
        code=codes[0];self.decoded_label.setText('Kode terbaca: '+code)
        if force or code!=self.last_code:self.last_code=code;self.decoded.emit(code)
    def show_image(self,image):
        if not self.closed:super().show_image(image)
    def stop_reader(self,*_):self.closed=True;self.scan_timer.stop();self.snapshot_timer.stop()
    def cleanup(self,*_):
        if self.cleaned:return
        self.cleaned=True;self.stop_reader();super().cleanup()
    def closeEvent(self,event):
        self.cleanup();super().closeEvent(event)
