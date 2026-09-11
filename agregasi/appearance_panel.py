"""An embedded settings page for screen, type, icons and UI density."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontDatabase, QIcon
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QGroupBox,
    QLabel,QPushButton,QSpinBox,QCheckBox,QFrame)
from .ui_controls import ThemedComboBox
from .display_preferences import display_defaults,validate_display,RESOLUTIONS,MODES,FITS,DENSITIES
from .typography import ui_font
from pathlib import Path
ASSETS=Path(__file__).resolve().parent.parent/'assets/svg'

class AppearancePanel(QWidget):
    applied=Signal(dict)
    def __init__(self,repo,parent=None):
        super().__init__(parent);self.repo=repo;self.controls={}
        self.setObjectName('appearance_panel')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True)
        self.setStyleSheet('''QWidget#appearance_panel {background:#03243a;border:1px solid #476981;border-radius:6px;}
        QGroupBox {background:#03283e;border:1px solid #285d77;margin-top:16px;padding:18px 16px 14px;border-radius:5px;}
        QGroupBox::title {color:#edf5ff;left:14px;padding:0 6px;}
        QLabel {color:#bed2e1;font-size:13px;}
        QSpinBox,QComboBox {background:#062e46;color:#eef6ff;border:1px solid #356881;border-radius:4px;padding:3px 8px;font-size:13px;}
        QSpinBox::up-button,QSpinBox::down-button {width:18px;border:0;background:#0b3850;}
        QSpinBox::up-arrow {image:url("@UP@");width:8px;height:5px;}
        QSpinBox::down-arrow {image:url("@DOWN@");width:8px;height:5px;}
        QCheckBox {color:#dcebf6;font-size:13px;spacing:8px;}
        QPushButton {font-size:13px;padding:8px 14px;}'''.replace('@UP@',(ASSETS/'chevron_up.svg').as_posix()).replace('@DOWN@',(ASSETS/'chevron_down.svg').as_posix()))
        outer=QVBoxLayout(self);outer.setContentsMargins(24,22,24,22);outer.setSpacing(18)
        title=QLabel('TAMPILAN APLIKASI');title.setStyleSheet('font-size:22px;font-weight:700;color:#edf5ff;');outer.addWidget(title)
        info=QLabel('Atur layar, tipografi, ikon, dan elemen antarmuka dari satu tempat.');outer.addWidget(info)
        columns=QHBoxLayout();columns.setSpacing(24);outer.addLayout(columns,1)
        left=QVBoxLayout();right=QVBoxLayout();columns.addLayout(left,1);columns.addLayout(right,1)
        def group(title,target):
            box=QGroupBox(title);form=QFormLayout(box);form.setHorizontalSpacing(18);form.setVerticalSpacing(18);form.setLabelAlignment(Qt.AlignmentFlag.AlignVCenter);target.addWidget(box);return form
        def combo(key,label,items,form):
            w=ThemedComboBox();w.addItems(items);w.setMinimumHeight(36);w.setSizeAdjustPolicy(ThemedComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);w.setMinimumContentsLength(12);form.addRow(label,w);self.controls[key]=w
        def spin(key,label,low,high,form,suffix=' %'):
            w=QSpinBox();w.setRange(low,high);w.setSuffix(suffix);w.setMinimumHeight(36);form.addRow(label,w);self.controls[key]=w
        form=group('LAYAR DAN RESOLUSI',left)
        combo('resolution','Resolusi aplikasi',['OTOMATIS',*RESOLUTIONS],form)
        combo('window_mode','Mode jendela',MODES,form);combo('fit','Penyesuaian konten',FITS,form)
        self.screen_info=QLabel();self.screen_info.setWordWrap(True);form.addRow(self.screen_info)
        note=QLabel('Preset berlaku pada mode JENDELA. Mode MAKSIMAL dan LAYAR PENUH mengikuti layar aktif. Ukuran memakai piksel logis sesuai skala Windows.');note.setWordWrap(True);note.setStyleSheet('color:#8fabbe;font-size:11px;');form.addRow(note)
        form=group('FONT',left)
        fonts=sorted(QFontDatabase.families());preferred=[f for f in ('Segoe UI','Inter','Noto Sans','DejaVu Sans','Arial') if f in fonts]
        combo('font_family','Jenis font',['OTOMATIS',*preferred,*[f for f in fonts if f not in preferred]],form)
        spin('font_scale','Ukuran font',90,115,form)
        note=QLabel('Otomatis menggunakan Segoe UI jika tersedia. Teks panjang disingkat di dalam kolom agar tidak bertumpuk.');note.setWordWrap(True);note.setStyleSheet('color:#8fabbe;font-size:11px;');form.addRow(note)
        left.addStretch()
        form=group('IKON DAN ELEMEN',right)
        spin('icon_scale','Ukuran ikon',80,120,form);combo('density','Kepadatan elemen',DENSITIES,form);spin('radius','Sudut elemen',0,10,form,' px')
        self.controls['hover']=QCheckBox('Aktifkan sorotan pada elemen interaktif');form.addRow(self.controls['hover'])
        form=group('PRATINJAU',right)
        self.preview=QLabel('Agregasi siap digunakan\nBOX-250501-0001  •  50 unit');self.preview.setMinimumHeight(90);self.preview.setWordWrap(True);form.addRow(self.preview)
        self.preview_button=QPushButton('Pengaturan');self.preview_button.setIcon(QIcon(str(ASSETS/'settings.svg')));self.preview_button.setMinimumHeight(50);form.addRow(self.preview_button)
        self.preview_button.clicked.connect(lambda:self.status.setText('Tombol dan ikon mengikuti pengaturan yang dipilih.'))
        right.addStretch()
        self.status=QLabel('');self.status.setWordWrap(True);outer.addWidget(self.status)
        actions=QHBoxLayout();self.reset_button=QPushButton('KEMBALIKAN DEFAULT');self.reload_button=QPushButton('BATALKAN PERUBAHAN');self.apply_button=QPushButton('TERAPKAN DAN SIMPAN');self.apply_button.setObjectName('apply_display');self.apply_button.setStyleSheet('background:#087942;border:1px solid #399963;')
        actions.addWidget(self.reset_button);actions.addWidget(self.reload_button);actions.addStretch();actions.addWidget(self.apply_button);outer.addLayout(actions)
        self.reset_button.clicked.connect(lambda:self.populate(display_defaults()));self.reload_button.clicked.connect(self.reload);self.apply_button.clicked.connect(self.save)
        self.controls['resolution'].currentTextChanged.connect(self.resolution_selected)
        for w in self.controls.values():
            if isinstance(w,QSpinBox):w.valueChanged.connect(self.update_preview)
            elif isinstance(w,QCheckBox):w.toggled.connect(self.update_preview)
            else:w.currentTextChanged.connect(self.update_preview)
        self.reload()
    def values(self):
        return {key:(w.isChecked() if isinstance(w,QCheckBox) else w.value() if isinstance(w,QSpinBox) else w.currentText()) for key,w in self.controls.items()}
    def populate(self,cfg):
        for key,w in self.controls.items():
            w.blockSignals(True);value=cfg[key]
            if isinstance(w,QCheckBox):w.setChecked(value)
            elif isinstance(w,QSpinBox):w.setValue(value)
            else:
                if key=='font_family' and w.findText(value)<0:w.addItem(value)
                w.setCurrentText(value)
            w.blockSignals(False)
        self.update_preview()
    def reload(self):
        self.populate(self.repo.load()['display']);self.status.setText('Pengaturan berlaku setelah menekan TERAPKAN DAN SIMPAN.')
    def resolution_selected(self,value):
        if value!='OTOMATIS':self.controls['window_mode'].setCurrentText('JENDELA')
    def update_preview(self,*args):
        from PySide6.QtCore import QSize
        cfg=self.values();font=ui_font(15)
        if cfg['font_family']!='OTOMATIS':font.setFamily(cfg['font_family'])
        font.setPixelSize(round(15*cfg['font_scale']/100));self.preview.setStyleSheet('color:#e8f3fc;');self.preview.setFont(font)
        size=round(25*cfg['icon_scale']/100);self.preview_button.setIconSize(QSize(size,size));self.preview_button.setFont(font)
        self.preview_button.setStyleSheet(f"QPushButton {{background:#084c77;border:1px solid #397da3;border-radius:{cfg['radius']}px;padding:8px;}}"+('QPushButton:hover {background:#116392;}' if cfg['hover'] else ''))
    def showEvent(self,event):
        super().showEvent(event);screen=self.screen();available=screen.availableGeometry();self.screen_info.setText(f'Layar aktif: {screen.size().width()} × {screen.size().height()}  |  Area kerja: {available.width()} × {available.height()}  |  Skala: {screen.devicePixelRatio()*100:.0f}%')
    def save(self):
        try:
            cfg=self.repo.load();cfg['display']=validate_display(self.values());self.repo.save(cfg);self.applied.emit(cfg['display'])
            self.status.setText('Tampilan tersimpan dan diterapkan ke semua halaman.')
        except (ValueError,TypeError) as exc:self.status.setText(str(exc))
