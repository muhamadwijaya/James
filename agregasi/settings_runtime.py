"""Real, bounded Qt network/device operations. No fabricated success states."""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from urllib.parse import urlparse
import json
import socket
from time import perf_counter
from .upload_model import UploadRepository

from PySide6.QtCore import QObject, Signal, QTimer, QUrl, QByteArray, QSizeF, QIODevice
from PySide6.QtGui import QImage, QPageSize
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply, QTcpSocket
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
from PySide6.QtSerialPort import QSerialPortInfo, QSerialPort

from .settings_model import SettingsRepository, LEVELS, VERSION


class SettingsRuntime(QObject):
    changed = Signal()
    message = Signal(str)
    camera_image = Signal(QImage)
    scan_received = Signal(str,str)

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store; self.repo = SettingsRepository(store)
        self.delivery = UploadRepository(store, self.repo)
        self.upload_metrics = store.get("upload_metrics", {})
        self._upload_queue = []; self._session_success = 0; self._session_failed = 0
        self.manager = QNetworkAccessManager(self)
        self.replies = set(); self.sockets = set(); self.stopped = False
        self.scanner_ports={};self.scanner_buffers={};self.scanner_armed={}
        self.uploading = False; self.paused = False; self.conveyor_running = False
        with self.store.db:
            self.store.db.execute("UPDATE delivery_ledger SET status='FAILED',detail='Sesi sebelumnya berakhir sebelum konfirmasi server.' WHERE status='SENDING'")
        self.status = {}; self.last_test = ''; self.last_upload = self.upload_metrics.get('time',''); self.last_update = 'Belum diperiksa'
        self.auto_timer = QTimer(self); self.auto_timer.timeout.connect(self.auto_tick)
        self.backup_timer = QTimer(self); self.backup_timer.setInterval(60000)
        self.backup_timer.timeout.connect(self.backup_tick); self.backup_timer.start()
        self.apply()

    def set_status(self, key, value, detail=''):
        previous=self.status.get(key,{})
        if previous.get('status')==value and previous.get('detail')==detail:return
        self.status[key] = {'status': value, 'detail': detail, 'time': datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
        if key in ('database','camera','conveyor') or key.startswith(('printer_','scanner_')):
            group=key.split('_')[0]
            with self.store.db:
                devices=self.store.get('devices',{})
                if group in ('printer','scanner'):
                    devices[group]=any(v['status'] in ('ONLINE','DRIVER SIAP','TERDETEKSI','TERKIRIM','PORT TERJANGKAU') for k,v in self.status.items() if k.startswith(group+'_'))
                else:devices[group]=value in ('ONLINE','BERJALAN')
                self.store.put('devices',devices)
        self.changed.emit()

    def apply(self):
        for serial in self.scanner_ports.values():serial.close();serial.deleteLater()
        self.scanner_ports.clear();self.scanner_buffers.clear()
        self.auto_timer.setInterval(self.repo.load()['sync_interval'] * 1000)
        self.auto_timer.start()
        self.status.clear()
        self.set_status('database', 'ONLINE', str(self.store.path))
        self.detect_devices()

    def detect_devices(self):
        cfg = self.repo.load()
        printers = {p.printerName(): p for p in QPrinterInfo.availablePrinters()}
        ports = {p.portName() for p in QSerialPortInfo.availablePorts()}
        for level in LEVELS:
            device = cfg['printers'][level]['device']
            info = printers.get(device)
            ready = info and info.state() in (QPrinter.PrinterState.Idle, QPrinter.PrinterState.Active)
            state = 'DRIVER SIAP' if ready else 'PERIKSA DRIVER' if info else 'BELUM DITES' if device.startswith('tcp://') else 'TIDAK TERDETEKSI'
            self.set_status('printer_'+level, state, device)
        for level in ('BOX','CARTON'):
            port = cfg['scanners'][level]['port']
            self.set_status('scanner_'+level, 'TERDETEKSI' if port in ports else 'MODE KEYBOARD' if port == 'KEYBOARD' else 'TIDAK TERDETEKSI', port)
        if 'camera' not in self.status:
            self.set_status('camera', 'BELUM DITES')
        if 'api' not in self.status:
            self.set_status('api', 'BELUM DITES')
        with self.store.db:
            devices = self.store.get('devices', {})
            devices.update(database=True, printer=any(self.status['printer_'+x]['status']=='DRIVER SIAP' for x in LEVELS),
                           scanner=any(self.status['scanner_'+x]['status']=='TERDETEKSI' for x in ('BOX','CARTON')),
                           camera=self.status['camera']['status']=='ONLINE', conveyor=self.conveyor_running)
            self.store.put('devices', devices)

    def request(self, url, callback, payload=None, token='', timeout=None):
        if self.stopped:
            return
        request = QNetworkRequest(QUrl(url))
        request.setTransferTimeout(int(timeout or self.repo.load()['upload_timeout']) * 1000)
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        request.setRawHeader(b'Accept', b'application/json, image/*')
        if token:
            request.setRawHeader(b'Authorization', ('Bearer '+token).encode())
        if payload is not None:
            request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, 'application/json')
            if isinstance(payload, dict) and 'request_id' in payload:
                request.setRawHeader(b'Idempotency-Key', payload['request_id'].encode())
            reply = self.manager.post(request, QByteArray(json.dumps(payload).encode()))
        else:
            reply = self.manager.get(request)
        self.replies.add(reply)
        chunks = bytearray(); too_large = [False]
        def read():
            chunks.extend(bytes(reply.readAll()))
            if len(chunks) > 8 * 1024 * 1024:
                too_large[0] = True; reply.abort()
        reply.readyRead.connect(read)
        # A wall-clock deadline also bounds peers that continually drip bytes.
        deadline = QTimer(reply); deadline.setSingleShot(True)
        deadline.timeout.connect(reply.abort); deadline.start(int(timeout or self.repo.load()['upload_timeout']) * 1000)
        def finished():
            read(); deadline.stop(); self.replies.discard(reply)
            code = int(reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) or 0)
            error = 'Respons melebihi batas 8 MB.' if too_large[0] else (reply.errorString() if reply.error()!=QNetworkReply.NetworkError.NoError else '')
            body = bytes(chunks); reply.deleteLater()
            if not self.stopped:
                callback(code, body, error)
        reply.finished.connect(finished)

    def api_url(self, path):
        return self.repo.load()['project_url'].rstrip('/') + path

    def test_connection(self):
        self.last_test = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
        try:
            self.store.db.execute('SELECT 1').fetchone()
            self.set_status('database', 'ONLINE', 'SQLite merespons.')
        except Exception as exc:
            self.set_status('database', 'ERROR', str(exc))
        cfg = self.repo.load()
        if not cfg['project_url']:
            self.set_status('api', 'BELUM DIATUR'); return
        self.set_status('api', 'MENGUJI')
        started = perf_counter()
        def result(code, body, error):
            self.health_ms = round((perf_counter()-started)*1000)
            try:
                info=json.loads(body);self.server_info={k:info[k] for k in ('version','uptime') if k in info} if isinstance(info,dict) else {}
            except (ValueError,TypeError):self.server_info={}
            ok = 200 <= code < 300 and not error
            text = f'HTTP {code}' if code else error or 'Tidak ada respons.'
            self.set_status('api', 'ONLINE' if ok else 'GAGAL', text)
            self.message.emit('Tes koneksi API: '+text)
            with self.store.db:
                self.store.audit('TEST API', text)
        self.request(self.api_url('/health'), result, token=cfg['api_token'])
        host = cfg['server_host']
        if host:
            endpoint = urlparse(host if '://' in host else '//'+host)
            try:
                port = endpoint.port or (443 if cfg['project_url'].startswith('https:') else 80)
            except ValueError:
                self.set_status('server', 'ALAMAT TIDAK VALID'); return
            conn = QTcpSocket(self); self.sockets.add(conn)
            done = [False]
            def finish(ok):
                if done[0]: return
                done[0] = True
                self.set_status('server', 'TERJANGKAU' if ok else 'TIDAK TERJANGKAU', f'{endpoint.hostname}:{port} (TCP)')
                self.sockets.discard(conn); conn.abort(); conn.deleteLater()
            conn.connected.connect(lambda: finish(True))
            conn.errorOccurred.connect(lambda _: finish(False))
            timer = QTimer(conn); timer.setSingleShot(True); timer.timeout.connect(lambda: finish(False)); timer.start(5000)
            conn.connectToHost(endpoint.hostname or host, port)

    def test_all(self):
        self.detect_devices(); self.test_connection()
        cfg = self.repo.load()
        for level in LEVELS:
            target = cfg['printers'][level]['device']
            if target.startswith('tcp://'):
                parsed = urlparse(target); conn = QTcpSocket(self); self.sockets.add(conn); done=[False]
                def finish(ok, sock=conn, key=level, completed=done):
                    if completed[0]: return
                    completed[0]=True; self.set_status('printer_'+key, 'PORT TERJANGKAU' if ok else 'GAGAL', 'Pemeriksaan TCP, belum mencetak.')
                    self.sockets.discard(sock); sock.abort(); sock.deleteLater()
                conn.connected.connect(lambda f=finish:f(True)); conn.errorOccurred.connect(lambda _,f=finish:f(False))
                timer=QTimer(conn); timer.setSingleShot(True); timer.timeout.connect(lambda f=finish:f(False)); timer.start(5000)
                conn.connectToHost(parsed.hostname, parsed.port)
        self.test_camera()

    def test_camera(self):
        cfg = self.repo.load()['camera']; address = cfg['address']
        if address.startswith('http://') or address.startswith('https://'):
            self.set_status('camera', 'MENGUJI')
            def result(code, body, error):
                image = QImage.fromData(body)
                ok = 200 <= code < 300 and not error and not image.isNull()
                self.set_status('camera', 'ONLINE' if ok else 'GAGAL', 'Snapshot diterima.' if ok else 'Endpoint harus mengembalikan gambar JPEG/PNG.')
                if ok: self.camera_image.emit(image)
            self.request(address, result)
        else:
            try:
                from PySide6.QtMultimedia import QMediaDevices
                devices=QMediaDevices.videoInputs()
                found=any(d.description()==cfg['device'] or bytes(d.id()).decode(errors='replace')==address for d in devices)
                self.set_status('camera', 'TERDETEKSI' if found else 'BELUM TERHUBUNG',
                                'Buka kalibrasi untuk preview.' if found else 'Pilih kamera USB atau URL snapshot HTTP/HTTPS pada kalibrasi.')
            except ImportError as exc:
                self.set_status('camera', 'MODUL TIDAK TERSEDIA', str(exc))

    def auto_tick(self):
        cfg = self.repo.load()
        if cfg['auto_upload'] and not self.paused and cfg['project_url'] and '.aggregation.local' not in cfg['project_url']:
            self.upload()

    def listen_scanner(self,level):
        cfg=self.repo.load()
        if not cfg['line_active']:raise ValueError('Line nonaktif. Aktifkan melalui Pengaturan.')
        if level not in cfg['scanners']:return 'Masukkan barcode pallet pada kolom scan.'
        profile=cfg['scanners'][level];self.scanner_armed[level]=True
        if profile['port']=='KEYBOARD':return 'Scanner keyboard siap. Fokuskan kolom scan dan pindai barcode.'
        if level in self.scanner_ports and self.scanner_ports[level].isOpen():return 'Scanner siap menerima barcode.'
        for other,serial in self.scanner_ports.items():
            if other!=level and serial.isOpen() and serial.portName()==profile['port']:raise ValueError('Port sedang digunakan scanner '+other+'.')
        serial=QSerialPort(self);serial.setPortName(profile['port']);serial.setBaudRate(profile['baud'])
        serial.setDataBits(QSerialPort.DataBits.Data8);serial.setParity(QSerialPort.Parity.NoParity)
        serial.setStopBits(QSerialPort.StopBits.OneStop);serial.setFlowControl(QSerialPort.FlowControl.NoFlowControl)
        if not serial.open(QIODevice.OpenModeFlag.ReadOnly):
            error=serial.errorString();serial.deleteLater();self.set_status('scanner_'+level,'GAGAL',error);raise ValueError(error)
        self.scanner_ports[level]=serial;self.scanner_buffers[level]=bytearray()
        def read():
            buffer=self.scanner_buffers[level];buffer.extend(bytes(serial.readAll()))
            if len(buffer)>8192:buffer.clear();self.message.emit('Data scanner terlalu panjang; periksa baud rate.');return
            while b'\r' in buffer or b'\n' in buffer:
                end=min(buffer.index(x) for x in (b'\r',b'\n') if x in buffer)
                value=bytes(buffer[:end]).decode('utf-8',errors='replace').strip();del buffer[:end+1]
                if value and (self.repo.load()['scanners'][level]['trigger']=='AUTO' or self.scanner_armed.get(level)):
                    self.scanner_armed[level]=False;self.set_status('scanner_'+level,'ONLINE','Barcode diterima.');self.scan_received.emit(level,value)
        serial.readyRead.connect(read)
        def failed(error):
            if error==QSerialPort.SerialPortError.ResourceError:
                self.set_status('scanner_'+level,'TERPUTUS',serial.errorString());serial.close()
        serial.errorOccurred.connect(failed);self.set_status('scanner_'+level,'MENUNGGU SCAN',profile['port'])
        return 'Port scanner terbuka. Pindai barcode dengan terminator Enter/CR/LF.'

    def upload(self, retry=False, level=None, event_ids=None):
        if self.stopped:return
        if self.paused:
            self.message.emit('Sinkronisasi dijeda. Klik RESUME SYNC untuk melanjutkan.');return
        if self.uploading:
            self.message.emit('Pengiriman sebelumnya masih berjalan.');return
        cfg=self.repo.load()
        if not cfg['project_url'] or '.aggregation.local' in cfg['project_url']:
            self.message.emit('Isi Project URL server Anda di Pengaturan sebelum mengirim data.');return
        allowed=set(event_ids) if event_ids is not None else None
        rows=[r for r in self.delivery.rows() if r['delivery_status']==('FAILED' if retry else 'PENDING')
              and (not level or r['stage']==level) and (allowed is None or r['id'] in allowed)]
        rows.sort(key=lambda r:r['id'])
        if not rows:
            self.message.emit('Tidak ada data gagal untuk diulang.' if retry else 'Tidak ada data pending yang cocok dengan pilihan/filter.');return
        problems=self.delivery.validate_rows(rows)
        if problems:
            self.message.emit('Validasi gagal: '+problems[0]);return
        self._upload_queue=rows;self._session_success=0;self._session_failed=0
        self.uploading=True;self._upload_config=cfg
        self._next_upload_batch()

    def set_paused(self, value):
        self.paused=bool(value)
        if self.paused:
            self.message.emit('Sinkronisasi dijeda; permintaan yang sudah dikirim menunggu konfirmasi. Data sisanya tetap dalam antrean.')
        else:self.message.emit('Sinkronisasi dilanjutkan. Klik Kirim Sekarang atau tunggu jadwal otomatis.')
        self.changed.emit()

    def _next_upload_batch(self):
        if self.stopped:return
        if self.paused or not self._upload_queue:
            self._finish_upload();return
        cfg=self._upload_config
        if self.repo.load()['project_url']!=cfg['project_url']:
            self._finish_upload('Pengiriman dihentikan karena server berubah.');return
        rows=self._upload_queue[:cfg['cache_limit']];del self._upload_queue[:len(rows)]
        events=[self.delivery.snapshot(r) for r in rows]
        # Identical bodies retain their key across restart and automatic retries.
        base={'line':cfg['line'],'mode':cfg['mode'],'events':events}
        request_id=sha256(json.dumps(base,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        payload={'request_id':request_id,**base}
        self._send_batch(payload,[r['id'] for r in rows],cfg,0)

    def _finish_upload(self, message=None):
        self.uploading=False;self._upload_queue=[]
        text=message or f'{self._session_success} data diterima server; {self._session_failed} gagal.'
        if self.paused and not message:text+=' Sinkronisasi dijeda; sisa data tetap pending.'
        with self.store.db:self.store.audit('KIRIM DATA',text)
        self.message.emit(text);self.changed.emit()

    def _send_batch(self,payload,ids,cfg,attempt):
        if self.stopped:return
        self.delivery.cache_payload(payload)
        self.repo.mark_delivery(ids,'SENDING',increment=True);self.changed.emit()
        started=perf_counter();size=len(json.dumps(payload).encode())
        def result(code,body,error):
            elapsed=max(perf_counter()-started,0.001);duration=round(elapsed*1000)
            accepted=[]
            try:
                obj=json.loads(body)
                if 200<=code<300 and not error and isinstance(obj,dict):
                    if obj.get('success') is True and 'accepted_ids' not in obj and 'accepted_record_ids' not in obj:
                        accepted=list(ids)
                    elif isinstance(obj.get('accepted_record_ids'),list):
                        identities={r['id']:r['record_id'] for r in self.delivery.rows() if r['id'] in ids}
                        accepted=[i for i in ids if identities[i] in obj['accepted_record_ids']]
                    elif isinstance(obj.get('accepted_ids'),list):
                        originals={r['id']:r['original_id'] for r in self.delivery.rows() if r['id'] in ids}
                        accepted=[i for i in ids if originals[i] in [v for v in obj['accepted_ids'] if type(v) is int] and list(originals.values()).count(originals[i])==1]
            except (ValueError,TypeError):pass
            remaining=[i for i in ids if i not in accepted]
            detail=f'HTTP {code}; '+('koneksi gagal/timeout.' if error else 'respons diterima.')
            self.last_upload=datetime.now().isoformat(timespec='seconds')
            self.upload_metrics={'time':self.last_upload,'http_code':code,'duration_ms':duration,
                                 'bytes':size,'bytes_per_second':round(size/elapsed),'detail':detail}
            with self.store.db:self.store.put('upload_metrics',self.upload_metrics)
            self.delivery.record_attempt(ids,accepted,code,duration,detail)
            self.set_status('api','ONLINE' if 200<=code<300 and not error else 'GAGAL',detail)
            if accepted:self.repo.mark_delivery(accepted,'SUCCESS',f'HTTP {code}; server mengakui data.')
            self._session_success+=len(accepted)
            if remaining and attempt<cfg['retry_count'] and (code==0 or code>=500 or code==429) and not self.paused:
                self.repo.mark_delivery(remaining,'FAILED',f'HTTP {code}; menunggu percobaan ulang.')
                QTimer.singleShot(min(2**attempt*1000,10000),lambda:self._retry_batch(payload,remaining,cfg,attempt+1))
                self.changed.emit();return
            if remaining:
                self.repo.mark_delivery(remaining,'FAILED',f'HTTP {code}; '+('koneksi gagal/timeout.' if error else 'server belum mengakui data.'))
            self._session_failed+=len(remaining)
            self.changed.emit()
            # Auth failures / unavailable servers leave later batches pending.
            if remaining and (code==0 or code in (401,403,404,429) or code>=500):
                self._finish_upload('Pengiriman berhenti: '+detail+' Periksa server lalu ulangi data gagal.');return
            QTimer.singleShot(0,self._next_upload_batch)
        self.request(cfg['project_url'].rstrip('/')+'/v1/upload',result,payload,token=cfg['api_token'],timeout=cfg['upload_timeout'])

    def _retry_batch(self,payload,ids,cfg,attempt):
        if self.stopped:return
        if self.paused:
            self._session_failed+=len(ids);self._finish_upload();return
        if self.repo.load()['project_url']!=cfg['project_url']:
            self._finish_upload('Pengiriman dihentikan karena server berubah.');return
        self._send_batch(payload,ids,cfg,attempt)

    def backup_tick(self):
        if self.repo.backup_due():
            try:
                path=self.repo.backup(); self.message.emit('Backup otomatis tersimpan: '+path.name)
            except Exception as exc:self.message.emit('Backup otomatis gagal: '+str(exc))

    def check_update(self):
        cfg=self.repo.load()
        if not cfg['project_url'] or '.aggregation.local' in cfg['project_url']:
            self.last_update='Atur Project URL server pembaruan.'; self.message.emit(self.last_update); self.changed.emit(); return
        def result(code,body,error):
            try:
                data=json.loads(body)
                version=data['version']
                import re
                if code!=200 or error or not isinstance(version,str) or not re.fullmatch(r'\d+\.\d+\.\d+',version):raise ValueError()
                newer=tuple(map(int,version.split('.')))>tuple(map(int,VERSION.split('.')))
                self.last_update=('Tersedia v' if newer else 'Versi terbaru: v')+version
            except (ValueError,TypeError,KeyError):self.last_update='Manifest versi belum tersedia dari server.'
            self.message.emit(self.last_update); self.changed.emit()
        self.request(self.api_url('/version.json'),result,token=cfg['api_token'])

    def conveyor(self):
        cfg=self.repo.load()
        if '.aggregation.local' in cfg['project_url'] or not cfg['project_url']:
            self.message.emit('Atur server controller conveyor di Project URL terlebih dahulu.'); return
        command='STOP' if self.conveyor_running else 'START'
        delay=cfg['stop_delay'] if self.conveyor_running else cfg['start_delay']
        self.message.emit(f'Perintah {command} conveyor dijadwalkan dalam {delay:g} detik.')
        def send():
            if self.stopped:return
            def result(code,body,error):
                try:ok=200<=code<300 and not error and json.loads(body).get('success') is True
                except (ValueError,AttributeError):ok=False
                if ok:self.conveyor_running=command=='START'
                self.set_status('conveyor','BERJALAN' if ok and self.conveyor_running else 'BERHENTI' if ok else 'GAGAL')
                self.message.emit(f'Conveyor {command}: '+('diakui controller.' if ok else 'controller belum mengakui perintah.'))
            self.request(self.api_url('/v1/conveyor'),result,{'command':command,'line':cfg['line']},token=cfg['api_token'])
        QTimer.singleShot(round(delay*1000),send)

    def configured_printer(self,level):
        profile=self.repo.load()['printers'][level]
        match=next((p for p in QPrinterInfo.availablePrinters() if p.printerName()==profile['device']),None)
        if match is None:raise ValueError('Printer '+profile['device']+' belum terpasang. Pilih nama driver OS atau alamat tcp://ip:9100 di Pengaturan.')
        printer=QPrinter(match,QPrinter.PrinterMode.HighResolution); printer.setResolution(profile['dpi'])
        width,height=map(float,profile['label'].removesuffix(' mm').split(' x '))
        printer.setPageSize(QPageSize(QSizeF(width,height),QPageSize.Unit.Millimeter,'Label'))
        return printer

    def print_zpl(self,document):
        """Raster ZPL honors DPI/darkness/speed; successful send is not a print confirmation."""
        from .label_render import render_image
        profile=self.repo.load()['printers'][document['level']]
        target=urlparse(profile['device'])
        doc=deepcopy(document); doc['dpi']=profile['dpi']
        image=render_image(doc,profile['dpi']).convertToFormat(QImage.Format.Format_Grayscale8)
        width,height=image.width(),image.height(); stride=image.bytesPerLine(); source=bytes(image.constBits())
        row_bytes=(width+7)//8; packed=bytearray(row_bytes*height)
        for y in range(height):
            for x in range(width):
                if source[y*stride+x]<128:packed[y*row_bytes+x//8]|=0x80>>(x%8)
        command=(f'^XA^PW{width}^LL{height}^MD{profile["darkness"]}^PR{profile["speed"]}'
                 f'^FO0,0^GFA,{len(packed)},{len(packed)},{row_bytes},'+packed.hex().upper()+'^FS^XZ').encode('ascii')
        with socket.create_connection((target.hostname,target.port),timeout=3) as conn:
            conn.sendall(command)
        self.set_status('printer_'+document['level'],'TERKIRIM','Tugas ZPL dikirim; keluaran fisik perlu diperiksa.')
        return True

    def shutdown(self):
        self.stopped=True; self.auto_timer.stop(); self.backup_timer.stop()
        for serial in self.scanner_ports.values():serial.close()
        for reply in list(self.replies):reply.abort()
        for conn in list(self.sockets):conn.abort()
        with self.store.db:
            self.store.db.execute("UPDATE delivery_ledger SET status='FAILED',detail='Aplikasi ditutup sebelum penerimaan server dikonfirmasi.' WHERE status='SENDING'")
