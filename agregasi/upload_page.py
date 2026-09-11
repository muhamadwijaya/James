"""Complete Upload / Kirim Data screen with real queue controls."""
from .sidebar_layout import fixed_sidebar, SIDEBAR
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt,QDate,QRectF,QSize
from PySide6.QtGui import QColor,QPen,QIcon
from PySide6.QtWidgets import (QPushButton,QTableWidgetItem,QDateEdit,QLabel,QAbstractItemView,
    QVBoxLayout,QHBoxLayout,QLineEdit,QTableWidget,QHeaderView)
from .pages import PageBase
from .dashboard import BASE,WHITE,MUTED,GREEN,RED,YELLOW,BLUE,num
from .settings_model import VERSION
from .ui_dialogs import FileDialog,MessageBox,AppDialog

COLORS={'BOX':'#128448','CARTON':'#048dc8','PALLET':'#68409b','PENDING':YELLOW,'SENDING':BLUE,'SUCCESS':GREEN,'FAILED':RED}

def stamp(value):
    try:return datetime.fromisoformat(value).strftime('%d-%m-%Y %H:%M:%S')
    except (ValueError,TypeError):return value or '—'
def duration(ms):
    if ms is None:return '—'
    return f'{ms/1000:.2f} dtk' if ms<1000 else f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02}'
def size_label(n):
    return f'{n/1024**2:.2f} MB' if n>=1024**2 else f'{n/1024:.1f} KB'


class SendPage(PageBase):
    PAGE_SIZE=10
    def __init__(self,store):
        super().__init__(store,'send','Kirim Data','SINKRONISASI & PENGIRIMAN DATA','send')
        self.settings_runtime=None;self.page_index=0;self.selected_ids=set();self.all_delivery_rows=[];self.rows=[];self.history_rows=[]
        self.auto=False;self.paused=False;self.message='Siap. Pilih data atau gunakan filter sebelum mengirim.'
        self.level=self.combo(124,620,269,29,['SEMUA (BOX/CARTON/PALLET)','BOX','CARTON','PALLET'])
        self.batch=self.combo(124,656,269,29,['SEMUA BATCH'])
        self.date=QDateEdit(QDate.currentDate(),self);self.date.setGeometry(124,692,180,29)
        self.date.setDisplayFormat('dd/MM/yyyy');self.date.setCalendarPopup(True)
        self.date.setStyleSheet('QDateEdit {color:#edf5ff;background:#04283f;border:1px solid #3f6780;border-radius:4px;padding:4px;font-size:12px;} QCalendarWidget QAbstractItemView {color:#eaf4ff;background:#07334d;selection-background-color:#147cc0;}')
        self.date_enabled=self.checkbox(312,692,86,29,'Filter');self.date.setEnabled(False)
        self.filter_status=self.combo(124,728,269,29,['SEMUA STATUS','PENDING','SENDING','SUCCESS','FAILED'])
        self.queue=self.table(25,216,693,330,['WAKTU','LEVEL','KODE','BATCH','JUMLAH','STATUS','RETRY'],[154,68,140,126,64,88,49])
        self.queue.verticalHeader().setDefaultSectionSize(29);self.queue.horizontalHeader().setFixedHeight(30)
        self.queue.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.queue.itemChanged.connect(self.selection_changed)
        self.empty_queue=QLabel('Belum ada data yang cocok dengan filter.',self);self.empty_queue.setGeometry(80,344,580,40)
        self.empty_queue.setAlignment(Qt.AlignmentFlag.AlignCenter);self.empty_queue.setStyleSheet('color:#90b9d3;font-size:13px;background:transparent;')
        self.history=self.table(429,620,652,250,['WAKTU','LEVEL','KODE','JUMLAH','STATUS','DURASI'],[145,66,160,64,89,100])
        self.history.verticalHeader().setDefaultSectionSize(27);self.history.horizontalHeader().setFixedHeight(30)
        self.history.cellDoubleClicked.connect(self.history_detail)
        self.empty_history=QLabel('Riwayat muncul setelah percobaan pengiriman.',self);self.empty_history.setGeometry(459,713,586,32)
        self.empty_history.setAlignment(Qt.AlignmentFlag.AlignCenter);self.empty_history.setStyleSheet('color:#90b9d3;font-size:12px;background:transparent;')
        self.buttons={}
        self.button('select_all',25,766,116,32,'PILIH SEMUA','check_circle')
        self.button('refresh',149,766,116,32,'REFRESH','sync')
        self.button('validate',273,766,120,32,'VALIDASI','shield','green')
        for name,x,y,label,ico,color in [
            ('backup_local',25,851,'BACKUP LOKAL','database','blue'),('export_csv',150,851,'EXPORT CSV','file_csv','blue'),('export_excel',275,851,'EXPORT EXCEL','file_csv','blue'),
            ('export_pdf',25,915,'EXPORT PDF','file_pdf','blue'),('import_again',150,915,'IMPORT ULANG','upload','blue'),('clear_cache',275,915,'CLEAR CACHE','trash','red')]:
            self.button(name,x,y,118,55,label,ico,color,stacked=True)
        for name,x,label,ico,color,sub in [
            ('send_now',429,'KIRIM SEKARANG','send','green','Kirim sesuai pilihan / filter'),
            ('retry_failed',596,'RETRY GAGAL','sync','gold','Ulangi data gagal / filter'),
            ('toggle_auto',763,'AUTO SYNC ON','sync','blue','Sesuai interval pengaturan'),
            ('toggle_pause',930,'PAUSE SYNC','pause','red','Jeda sinkronisasi')]:
            self.button(name,x,911,157,61,label,ico,color,subtitle=sub)
        self.button('history_all',945,873,136,24,'LIHAT SEMUA  ›',None,flat=True)
        self.button('page_prev',452,548,28,25,'‹',None,flat=True)
        self.button('page_next',687,548,28,25,'›',None,flat=True)
        self.page_buttons=[]
        for i in range(5):
            b=self.button('page_'+str(i),487+i*38,548,33,25,str(i+1),None,flat=True)
            self.page_buttons.append(b)
        for box in (self.level,self.batch,self.filter_status):box.currentTextChanged.connect(self.filters_changed)
        self.date.dateChanged.connect(self.filters_changed)
        self.date_enabled.toggled.connect(self.toggle_date)
        self.action.connect(self.local_action)
        self.refresh()

    def button(self,name,x,y,w,h,label,icon,color='blue',subtitle='',stacked=False,flat=False):
        button=QPushButton(self);button.setObjectName(name);button.setGeometry(x,y,w,h)
        button.setAccessibleName(label);button.setToolTip(subtitle or label);button.setCursor(Qt.CursorShape.PointingHandCursor)
        palette={'blue':('#076fac','#03426b','#249bd2'),'green':('#09824a','#045631','#2faa63'),'gold':('#a77a0a','#6c4e06','#d5ad35'),'red':('#bf302e','#781f23','#ea5456')}
        top,bottom,border=palette[color]
        text=label+('\n'+subtitle if subtitle else '')
        button.setText(text)
        if icon:
            button.setIcon(QIcon(str(BASE/'assets/svg'/f'{icon}.svg')));button.setIconSize(QSize(25 if h>40 else 17,25 if h>40 else 17))
        if subtitle:
            button.setText('');button.setIcon(QIcon())
            pic=QLabel(button);pic.setGeometry(9,13,25,25);pic.setPixmap(QIcon(str(BASE/'assets/svg'/f'{icon}.svg')).pixmap(25,25));pic.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            title=QLabel(label,button);title.setObjectName('button_title');title.setGeometry(39,9,w-41,22);title.setStyleSheet('color:white;font-size:10px;font-weight:600;background:transparent;');title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            caption=QLabel(subtitle,button);caption.setObjectName('button_subtitle');caption.setGeometry(6,36,w-12,18);caption.setAlignment(Qt.AlignmentFlag.AlignCenter);caption.setStyleSheet('color:#d6edf5;font-size:8px;background:transparent;');caption.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        if stacked:
            # Compact vertical label below a crisp SVG symbol.
            button.setText('');button.setIcon(QIcon())
            pic=QLabel(button);pic.setGeometry(47,5,24,24);pic.setPixmap(QIcon(str(BASE/'assets/svg'/f'{icon}.svg')).pixmap(24,24));pic.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            caption=QLabel(label,button);caption.setGeometry(2,31,w-4,19);caption.setAlignment(Qt.AlignmentFlag.AlignCenter);caption.setStyleSheet('color:#edf7ff;font-size:10px;background:transparent;');caption.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        button.setStyleSheet(('QPushButton {background:transparent;border:0;color:#d2e8fb;padding:0;font-size:11px;} QPushButton:hover {background:#106aa0;} QPushButton:checked {background:#087bc3;}' if flat else
            f'QPushButton {{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {top},stop:1 {bottom});border:1px solid {border};border-radius:4px;color:#f0f8ff;padding:2px;font-size:{10 if subtitle else 11}px;}} QPushButton:hover {{border:1px solid #afdfef;background:{top};}} QPushButton:pressed {{background:{bottom};}} QPushButton:disabled {{color:#7392a4;background:#173d51;border-color:#355267;}}'))
        button.clicked.connect(lambda checked=False,n=name:self.action.emit(n));self.buttons[name]=button
        return button

    def attach_runtime(self,runtime):
        self.settings_runtime=runtime;runtime.changed.connect(self.refresh);runtime.message.connect(self.delivery_message);self.refresh()
    def delivery_message(self,text):self.message=text;self.refresh()
    def toggle_date(self,checked):self.date.setEnabled(checked);self.filters_changed()
    def filters_changed(self,*args):self.page_index=0;self.selected_ids.clear();self.refresh()
    def filters(self):
        return dict(level='' if self.level.currentIndex()==0 else self.level.currentText(),
            batch='' if self.batch.currentIndex()==0 else self.batch.currentText(),
            date=self.date.date().toString('yyyy-MM-dd') if self.date_enabled.isChecked() else '',
            status='' if self.filter_status.currentIndex()==0 else self.filter_status.currentText())
    def selection_changed(self,item):
        if item.column()!=0:return
        identifier=item.data(Qt.ItemDataRole.UserRole)
        if item.checkState()==Qt.CheckState.Checked:self.selected_ids.add(identifier)
        else:self.selected_ids.discard(identifier)
        self.update()
    def action_rows(self):return [r for r in self.rows if not self.selected_ids or r['id'] in self.selected_ids]
    def refresh(self):
        runtime=self.settings_runtime
        self.all_delivery_rows=runtime.delivery.rows() if runtime else []
        self.auto=runtime.repo.load()['auto_upload'] if runtime else False;self.paused=runtime.paused if runtime else False
        batch=self.batch.currentText();options=['SEMUA BATCH']+sorted({r['batch'] for r in self.all_delivery_rows})
        if [self.batch.itemText(i) for i in range(self.batch.count())]!=options:
            self.batch.blockSignals(True);self.batch.clear();self.batch.addItems(options);self.batch.setCurrentText(batch if batch in options else options[0]);self.batch.blockSignals(False)
        f=self.filters()
        self.rows=runtime.delivery.filter_rows(self.all_delivery_rows,**f) if runtime else []
        if not f['status']:self.rows=[r for r in self.rows if r['delivery_status']!='SUCCESS']
        self.selected_ids.intersection_update({r['id'] for r in self.rows})
        self.page_count=max(1,(len(self.rows)+self.PAGE_SIZE-1)//self.PAGE_SIZE)
        self.page_index=min(self.page_index,self.page_count-1)
        visible=self.rows[self.page_index*self.PAGE_SIZE:(self.page_index+1)*self.PAGE_SIZE]
        self.queue.blockSignals(True);self.queue.setRowCount(len(visible))
        for i,r in enumerate(visible):
            vals=[stamp(r['ts']),r['stage'],r['code'],r['batch'],r['quantity'],r['delivery_status'],max(0,r['attempts']-1)]
            self.populate(self.queue,i,vals,r)
            cell=self.queue.item(i,0);cell.setFlags(cell.flags()|Qt.ItemFlag.ItemIsUserCheckable);cell.setData(Qt.ItemDataRole.UserRole,r['id'])
            cell.setCheckState(Qt.CheckState.Checked if r['id'] in self.selected_ids else Qt.CheckState.Unchecked)
        self.queue.blockSignals(False);self.empty_queue.setVisible(not visible)
        start=max(0,min(self.page_index-2,self.page_count-5))
        for offset,b in enumerate(self.page_buttons):
            index=start+offset;b.setVisible(index<self.page_count);b.setText(str(index+1));b.setProperty('page_index',index);b.setCheckable(True);b.setChecked(index==self.page_index)
        self.buttons['page_prev'].setEnabled(self.page_index>0);self.buttons['page_next'].setEnabled(self.page_index<self.page_count-1)
        self.all_history=runtime.delivery.history() if runtime else []
        self.history_rows=runtime.delivery.filter_rows(self.all_history,**f) if runtime else []
        self.history.setRowCount(min(8,len(self.history_rows)))
        for i,r in enumerate(self.history_rows[:8]):
            self.populate(self.history,i,[stamp(r['sent_at']),r['stage'],r['code'],r['quantity'],r['delivery_status'],duration(r['duration_ms'])],r)
        self.empty_history.setVisible(not self.history_rows)
        self.buttons['toggle_auto'].findChild(QLabel,'button_title').setText('AUTO SYNC '+('ON' if self.auto else 'OFF'))
        self.buttons['toggle_pause'].findChild(QLabel,'button_title').setText('RESUME SYNC' if self.paused else 'PAUSE SYNC')
        self.buttons['toggle_pause'].findChild(QLabel,'button_subtitle').setText('Lanjutkan sinkronisasi' if self.paused else 'Jeda sinkronisasi')
        busy=bool(runtime and runtime.uploading)
        for name in ('send_now','retry_failed','import_again','clear_cache'):self.buttons[name].setEnabled(not busy and (not self.paused or name not in ('send_now','retry_failed')))
        self.buttons['select_all'].setText('BATAL PILIH' if self.rows and len(self.selected_ids)==len(self.rows) else 'PILIH SEMUA')
        self.update()
    def populate(self,table,i,values,row):
        for j,value in enumerate(values):
            cell=QTableWidgetItem(str(value));cell.setToolTip(str(value)+'\n'+row.get('delivery_detail',''))
            if str(value) in COLORS:
                if str(value) in ('BOX','CARTON','PALLET'):cell.setBackground(QColor(COLORS[str(value)]));cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                else:cell.setForeground(QColor(COLORS[str(value)]))
            table.setItem(i,j,cell)
    def local_action(self,name):
        runtime=self.settings_runtime
        if not runtime:return
        try:
            if name=='select_all':self.selected_ids=set() if len(self.selected_ids)==len(self.rows) else {r['id'] for r in self.rows}
            elif name=='refresh':self.message='Antrean diperbarui dari database lokal.';runtime.test_connection()
            elif name=='validate':
                rows=self.action_rows();problems=runtime.delivery.validate_rows(rows)
                self.message=f'{len(rows)} data diperiksa; {len(problems)} bermasalah.'
                if problems:MessageBox.warning(self,'Hasil validasi','\n'.join(problems[:30]))
                elif not rows:self.message='Tidak ada data untuk divalidasi.'
                else:self.message+= ' Struktur siap dikirim.'
            elif name in ('send_now','retry_failed'):runtime.upload(retry=name=='retry_failed',event_ids=[r['id'] for r in self.action_rows()])
            elif name=='toggle_auto':
                cfg=runtime.repo.load();cfg['auto_upload']=not cfg['auto_upload'];runtime.repo.save(cfg)
                self.message='Auto sync '+('ON' if cfg['auto_upload'] else 'OFF')+'. Berlaku untuk seluruh antrean pending.';self.changed.emit()
            elif name=='toggle_pause':runtime.set_paused(not runtime.paused)
            elif name=='clear_cache':
                count=runtime.delivery.clear_cache();self.message=f'{count} salinan payload dibersihkan; antrean dan riwayat tetap tersimpan.'
            elif name=='backup_local' or name.startswith('export_'):
                kind={'backup_local':'json','export_csv':'csv','export_excel':'xlsx','export_pdf':'pdf'}[name]
                path,_=FileDialog.getSaveFileName(self,'Backup antrean lengkap' if kind=='json' else 'Ekspor data terpilih / filter',f'agregasi-upload-{datetime.now():%Y%m%d-%H%M%S}.{kind}',f'{kind.upper()} (*.{kind})')
                if path:
                    if not Path(path).suffix:path+='.'+kind
                    rows=self.all_delivery_rows if kind=='json' else self.action_rows()
                    runtime.delivery.export(path,rows,kind);self.message=f'{len(rows)} data tersimpan ke {Path(path).name}.'
            elif name=='import_again':
                path,_=FileDialog.getOpenFileName(self,'Impor ulang antrean','', 'Antrean AGREGASI (*.json *.csv *.xlsx)')
                if path:
                    records=runtime.delivery.read_import(path)
                    if MessageBox.question(self,'Impor ulang antrean',f'{len(records)} record lolos validasi. Tambahkan record yang belum ada sebagai PENDING? ID yang sudah ada dilewati. Pengiriman menunggu konfirmasi server.')==MessageBox.StandardButton.Yes:
                        added,skipped=runtime.delivery.import_records(records);self.message=f'{added} data ditambahkan; {skipped} ID sudah ada.';self.changed.emit()
            elif name=='page_prev':self.page_index=max(0,self.page_index-1)
            elif name=='page_next':self.page_index=min(self.page_count-1,self.page_index+1)
            elif name.startswith('page_'):self.page_index=self.buttons[name].property('page_index')
            elif name=='history_all':self.show_history()
        except Exception as exc:
            self.message='Operasi gagal: '+str(exc);MessageBox.warning(self,'Kirim Data',self.message)
        self.refresh()
    def history_detail(self,row,column):
        if row<len(self.history_rows):
            r=self.history_rows[row];MessageBox.information(self,'Detail pengiriman',f"Kode: {r['code']}\nRecord ID: {r['record_id']}\nWaktu: {stamp(r['sent_at'])}\nStatus: {r['delivery_status']}\nDurasi: {duration(r['duration_ms'])}\n{r['delivery_detail']}")
    def show_history(self):
        dialog=AppDialog(self);dialog.setWindowTitle('Seluruh riwayat pengiriman');dialog.resize(1060,620)
        layout=QVBoxLayout(dialog);search=QLineEdit();search.setPlaceholderText('Cari kode, batch, level, status, atau waktu…');layout.addWidget(search)
        grid=QTableWidget();grid.setColumnCount(8);grid.setHorizontalHeaderLabels(['WAKTU','LEVEL','KODE','BATCH','JUMLAH','STATUS','DURASI','HTTP'])
        grid.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);grid.verticalHeader().hide();grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents);grid.horizontalHeader().setStretchLastSection(True);layout.addWidget(grid)
        bar=QHBoxLayout();info=QLabel();prev=QPushButton('‹ Sebelumnya');next_=QPushButton('Berikutnya ›');close=QPushButton('Tutup')
        for w in (info,prev,next_,close):bar.addWidget(w)
        layout.addLayout(bar);position=[0]
        def render(reset=False):
            if reset:position[0]=0
            query=search.text().casefold();rows=[r for r in self.settings_runtime.delivery.history() if query in ' '.join(str(v) for v in r.values()).casefold()]
            maximum=max(0,(len(rows)-1)//50);position[0]=min(position[0],maximum);chunk=rows[position[0]*50:(position[0]+1)*50]
            grid.setRowCount(len(chunk))
            for i,r in enumerate(chunk):self.populate(grid,i,[stamp(r['sent_at']),r['stage'],r['code'],r['batch'],r['quantity'],r['delivery_status'],duration(r['duration_ms']),r['http_code'] or '—'],r)
            info.setText(f'{len(rows)} percobaan • Halaman {position[0]+1}/{maximum+1}');prev.setEnabled(position[0]>0);next_.setEnabled(position[0]<maximum)
        def move(delta):position[0]+=delta;render()
        search.textChanged.connect(lambda:render(True));prev.clicked.connect(lambda:move(-1));next_.clicked.connect(lambda:move(1));close.clicked.connect(dialog.accept)
        render();dialog.exec();dialog.deleteLater()

    def ring(self,x,y,size,rate,label='Selesai'):
        r=QRectF(x+6,y+6,size-12,size-12);self.p.setBrush(Qt.BrushStyle.NoBrush)
        self.p.setPen(QPen(QColor('#205976'),10));self.p.drawEllipse(r)
        self.p.setPen(QPen(QColor(GREEN),10));self.p.drawArc(r,90*16,-round(min(1,rate)*360*16))
        self.text(x,y+size*.29,size,size*.28,f'{rate*100:.0f}%',23 if size>100 else 14,WHITE,True,Qt.AlignmentFlag.AlignCenter)
        self.text(x,y+size*.57,size,18,label,10,MUTED,align=Qt.AlignmentFlag.AlignCenter)
    def paint_content(self):
        runtime=self.settings_runtime;rows=self.all_delivery_rows
        self.counts={s:sum(r['delivery_status']==s for r in rows) for s in ('PENDING','SENDING','SUCCESS','FAILED')}
        c=self.counts;queue=c['PENDING']+c['SENDING']+c['FAILED'];cache=runtime.delivery.cache_bytes() if runtime else 0
        metrics=runtime.upload_metrics if runtime else {};last=stamp(metrics.get('time',''))
        self.panel(15,75,1080,99)
        for i,(label,value,ico,sub) in enumerate([
            ('TOTAL QUEUE',num(queue),'database','data belum selesai'),('PENDING UPLOAD',num(c['PENDING']+c['SENDING']),'upload','data'),
            ('BERHASIL DIKIRIM',num(c['SUCCESS']),'check_circle','data terkonfirmasi'),('GAGAL',num(c['FAILED']),'reject','data'),
            ('CACHE LOKAL',size_label(cache),'database','salinan payload'),('LAST SYNC',last[-8:] if last!='—' else '—','clock',last[:10] if last!='—' else 'belum ada pengiriman')]):
            x=28+i*178;self.icon(ico,x,99,38);self.text(x+48,87,127,23,label,10,MUTED,True);self.text(x+48,112,126,31,value,24,WHITE,True);self.text(x+48,145,126,18,sub,9,MUTED)
            if i<5:self.line_vertical(x+169,88,72)
        self.panel(15,184,715,392,'ANTREAN DATA SIAP KIRIM')
        self.text(580,188,137,24,f'{len(self.rows)} data • {len(self.selected_ids)} dipilih',10,MUTED,align=Qt.AlignmentFlag.AlignRight)
        lo=self.page_index*10+1 if self.rows else 0;hi=min((self.page_index+1)*10,len(self.rows))
        self.text(27,548,416,24,f'Menampilkan {lo} – {hi} dari {len(self.rows)} data',10,MUTED)
        self.panel(740,184,355,392,'STATUS SINKRONISASI')
        api=runtime.status.get('api',{}) if runtime else {}
        self.icon('database',754,229,20);self.text(782,226,119,24,'DATABASE',10,MUTED);self.text(916,226,160,24,'ONLINE' if runtime else '—',11,GREEN,align=Qt.AlignmentFlag.AlignRight)
        self.line(753,254,328);self.icon('upload',754,262,20);self.text(782,259,115,22,'API ENDPOINT',10,MUTED)
        endpoint=runtime.api_url('/v1/upload') if runtime else 'Belum dikonfigurasi';self.text(755,282,322,24,endpoint,10,MUTED)
        self.line(753,309,328);self.text(756,312,142,24,'UPLOAD SPEED',10,MUTED);self.text(898,312,178,24,size_label(metrics.get('bytes_per_second',0))+'/s' if metrics else '—',11,align=Qt.AlignmentFlag.AlignRight)
        self.text(756,340,122,22,'LAST RESPONSE',10,MUTED);self.text(879,340,134,22,last[-8:] if metrics else '—',11)
        code=metrics.get('http_code');self.rect(1014,341,65,21,'#126d4b' if code and 200<=code<300 else '#663028',stroke='#386279',radius=3);self.text(1014,341,65,21,str(code) if code else '—',10,WHITE,True,Qt.AlignmentFlag.AlignCenter)
        self.line(753,370,328);self.text(754,378,324,23,'PROGRES SINKRONISASI',13,WHITE,True)
        total=len(rows);rate=c['SUCCESS']/total if total else 0;self.ring(754,412,115,rate)
        for i,(label,count,color) in enumerate([('Total data',total,WHITE),('Berhasil',c['SUCCESS'],GREEN),('Gagal',c['FAILED'],RED),('Sisa',c['PENDING']+c['SENDING'],BLUE)]):
            y=407+i*30;self.text(891,y,95,25,label,11,MUTED);self.text(984,y,92,25,num(count)+' data',11,color,True,Qt.AlignmentFlag.AlignRight)
        self.rect(756,550,322,10,'#185a7d','#185a7d','#397999',3)
        if total:
            if rate:self.rect(757,551,320*rate,8,GREEN,GREEN,GREEN,2)
            fail=c['FAILED']/total
            if fail:self.rect(757+320*rate,551,320*fail,8,RED,RED,RED,2)
        self.panel(15,585,391,222,'PILIH DATA & FILTER')
        for y,label in [(620,'LEVEL'),(656,'BATCH'),(692,'TANGGAL'),(728,'STATUS')]:self.text(28,y,88,29,label,11,MUTED)
        self.panel(15,817,391,164,'BACKUP & EXPORT')
        self.panel(417,585,678,316,'RIWAYAT PENGIRIMAN')
        self.text(430,872,500,25,f'Menampilkan {min(1,len(self.history_rows))} – {min(8,len(self.history_rows))} dari {len(self.history_rows)} percobaan',10,MUTED)
        self.panel(417,904,678,77)
        self.text(20,982,1070,13,self.message,9,'#163d55')
    def line_vertical(self,x,y,h):self.p.setPen(QPen(QColor('#315773'),1));self.p.drawLine(x,y,x,y+h)
    def sidebar(self):
        from .shared_sidebar import paint_sidebar
        paint_sidebar(self)
    def side_row(self,y,label,value,color=WHITE,size=10):
        self.text(1126,y,170,20,label,size,MUTED);self.text(1294,y,118,20,value,size,color,align=Qt.AlignmentFlag.AlignRight)
