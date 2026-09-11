"""Application shell and internal page navigation."""
from PySide6.QtCore import Qt, QSize, QTimer, QRectF
from PySide6.QtGui import QKeySequence, QShortcut, QPainter
from PySide6.QtWidgets import QMainWindow, QGraphicsView, QGraphicsScene, QFrame, QStackedWidget

from .dashboard import Dashboard
from .pages import OperationPage, RevisionPage, SendPage
from .box_page import BoxPage
from .carton_page import CartonPage
from .pallet_page import PalletPage
from .settings_page import SettingsPage
from .template_page import TemplatePage
from .store import STAGES
from .typography import ui_font
from .responsive_surface import ResponsiveSurface, WIDTH, HEIGHT


class ScaledView(QGraphicsView):
    """Fill the viewport with expanding layout cells and uniform text rendering."""
    def __init__(self, widget, parent=None):
        super().__init__(parent)
        scene = QGraphicsScene(self); self.setScene(scene)
        self.proxy=scene.addWidget(widget); scene.setSceneRect(0, 0, 1448, 1086)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fit_mode = 'PAS LAYAR'
        self.canvas_widget=widget
        self.surface=None
        self._fitting=False
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_canvas()
    def showEvent(self, event):
        super().showEvent(event); self.fit_canvas()

    def fit_canvas(self):
        if not hasattr(self,'canvas_widget') or self._fitting:return
        self._fitting=True
        try:
            self.resetTransform()
            scroll = self.fit_mode == 'UKURAN ASLI (SCROLL)'
            policy = Qt.ScrollBarPolicy.ScrollBarAsNeeded if scroll else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            self.setHorizontalScrollBarPolicy(policy);self.setVerticalScrollBarPolicy(policy)
            width=max(1,self.viewport().width());height=max(1,self.viewport().height())
            if self.surface is None:
                # The shell initializes baselines after all pages/devices are wired.
                self.scene().setSceneRect(0,0,WIDTH,HEIGHT)
                if not scroll:self.scale(min(width/WIDTH,height/HEIGHT),min(width/WIDTH,height/HEIGHT))
                return
            factor=1. if scroll else min(width/WIDTH,height/HEIGHT)
            canvas_width=WIDTH if scroll else round(width/factor)
            canvas_height=HEIGHT if scroll else round(height/factor)
            self.surface.resize(canvas_width,canvas_height)
            # Qt caches the proxy's original fixed-size constraints separately.
            # Update both the widget and proxy so painting and hit testing agree.
            self.proxy.setMinimumSize(canvas_width,canvas_height)
            self.proxy.setMaximumSize(canvas_width,canvas_height)
            self.proxy.setGeometry(QRectF(0,0,canvas_width,canvas_height))
            self.scene().setSceneRect(0,0,canvas_width,canvas_height)
            if not scroll:self.scale(factor,factor)
        finally:self._fitting=False


class MainWindow(QMainWindow):
    PAGES = ('dashboard', 'box', 'carton', 'pallet', 'revision', 'send', 'settings', 'template')
    def __init__(self, store):
        super().__init__()
        self.setFont(ui_font())
        self.store = store
        self.setWindowTitle('AGREGASI • Monitoring & Ringkasan Proses Agregasi')
        self.setMinimumSize(640, 480)
        self.resize(1280, 800)
        self._display_config = None
        self.host = QStackedWidget(self)
        self.setCentralWidget(self.host)
        self.pages = {}; self.views = {}; self.current_page = 'dashboard'
        for key in self.PAGES: self._make_page(key)
        self.settings_runtime = self.pages['settings'].runtime
        from .shared_sidebar import install_sidebar_controls
        for page in self.pages.values():
            page.settings_runtime = self.settings_runtime
            install_sidebar_controls(page)
        self.settings_runtime.scan_received.connect(self.receive_device_scan)
        self.settings_runtime.changed.connect(self.pages['dashboard'].update)
        self.pages['send'].attach_runtime(self.settings_runtime)
        for stage in STAGES:
            self.pages[stage.lower()].settings_runtime = self.settings_runtime
        self._wire_pages()
        self.pages['settings'].changed.connect(self.apply_display_preferences)
        from .aggregation_runtime import AggregationRuntime
        self.aggregation_runtime=AggregationRuntime(store,self.pages['template'].repo)
        self.pages['revision'].attach(self.settings_runtime,self.aggregation_runtime,self.pages['template'])
        for stage in STAGES:self.pages[stage.lower()].configure_templates(self.aggregation_runtime,self.print_aggregation_label)
        for sequence, key in [('Ctrl+1','box'), ('Ctrl+2','carton'), ('Ctrl+3','pallet')]:
            shortcut=QShortcut(QKeySequence(sequence), self); shortcut.activated.connect(lambda k=key:self.navigate(k))
        full=QShortcut(QKeySequence('F11'),self); full.activated.connect(self.toggle_fullscreen)
        refresh=QShortcut(QKeySequence('F5'),self); refresh.activated.connect(self.refresh_all)
        esc=QShortcut(QKeySequence('Escape'),self); esc.activated.connect(lambda:self.showNormal() if self.isFullScreen() else None)
        for view in self.views.values():view.surface=ResponsiveSurface(view.canvas_widget)
        self.apply_display_preferences()
    def apply_display_preferences(self):
        from .display_preferences import configure_display
        from .display_runtime import apply_native_preferences
        cfg=self.pages['settings'].repo.load()['display']
        if cfg == self._display_config:
            apply_native_preferences(self)
            return
        previous=self._display_config;self._display_config=dict(cfg)
        configure_display(cfg);apply_native_preferences(self)
        for view in self.views.values():view.fit_mode=cfg['fit'];view.fit_canvas()
        geometry_changed=previous is None or any(previous[k]!=cfg[k] for k in ('resolution','window_mode'))
        if geometry_changed:
            if self.isVisible():self.show_configured()
            elif cfg['window_mode']=='JENDELA':self.resize_to_preset()
        self.refresh_all()
    def resize_to_preset(self):
        cfg=self._display_config
        available=self.screen().availableGeometry()
        preset=cfg['resolution']
        width,height=(min(1448,available.width()),min(1086,available.height())) if preset=='OTOMATIS' else map(int,preset.split(' x '))
        frame_w=max(0,self.frameGeometry().width()-self.width());frame_h=max(0,self.frameGeometry().height()-self.height())
        self.resize(min(width,max(640,available.width()-frame_w)),min(height,max(480,available.height()-frame_h)))
        frame=self.frameGeometry();frame.moveCenter(available.center());self.move(frame.topLeft())
    def show_configured(self,windowed=False):
        mode='JENDELA' if windowed else self._display_config['window_mode']
        if mode=='LAYAR PENUH':self.showFullScreen()
        elif mode=='MAKSIMAL':self.showMaximized()
        else:
            self.showNormal();self.resize_to_preset()
        QTimer.singleShot(0,lambda:[v.fit_canvas() for v in self.views.values()])

    def receive_device_scan(self,level,value):
        page=self.pages[level.lower()]
        if self.current_page!=level.lower():
            self.settings_runtime.message.emit('Barcode '+level+' diabaikan karena halaman tahap tersebut tidak aktif.')
            return
        page.scan_input.setText(value);page.scan()

    def print_aggregation_label(self,document,identifier,automatic=False):
        from copy import deepcopy
        cfg=self.settings_runtime.repo.load()['printers'][document['level']]
        doc=deepcopy(document);doc['dpi']=cfg['dpi']
        width,height=map(float,cfg['label'].removesuffix(' mm').split(' x '))
        if doc['width_mm']>width or doc['height_mm']>height:
            raise ValueError('Ukuran template melebihi label printer yang dipilih. Sesuaikan ukuran label pada Pengaturan.')
        if cfg['device'].startswith('tcp://'):
            return self.settings_runtime.print_zpl(doc)
        try:
            printer=self.settings_runtime.configured_printer(document['level'])
        except ValueError:
            if automatic:raise
            return self.pages['template'].print_document(doc,identifier)
        return self.pages['template'].print_document(doc,identifier,printer=printer,confirm=not automatic)

    def _make_page(self, key):
        if key in self.pages:return
        if key=='dashboard': page=Dashboard(self.store)
        elif key=='box': page=BoxPage(self.store)
        elif key=='carton': page=CartonPage(self.store)
        elif key=='pallet': page=PalletPage(self.store)
        elif key=='revision': page=RevisionPage(self.store)
        elif key=='send': page=SendPage(self.store)
        elif key=='settings': page=SettingsPage(self.store)
        elif key=='template': page=TemplatePage(self.store)
        else: raise ValueError('Halaman tidak dikenal: '+key)
        self.pages[key]=page; self.views[key]=ScaledView(page,self.host); self.host.addWidget(self.views[key])
    def _wire_pages(self):
        for page in self.pages.values():
            page.action.connect(self.handle_action)
            if hasattr(page, 'changed'): page.changed.connect(self.refresh_all)
    def navigate(self, key):
        aliases={'nav_dashboard':'dashboard','nav_box':'box','nav_carton':'carton','nav_pallet':'pallet','nav_revision':'revision','nav_send':'send','nav_settings':'settings','nav_template':'template'}
        key=aliases.get(key.lower(),key.lower())
        if key not in self.pages:return
        self.current_page = key
        navigation = getattr(self.pages[key], 'navigation', None)
        if navigation is not None:
            navigation.reset()
        self.host.setCurrentWidget(self.views[key])
        self.refresh_all()
    def register_page(self, key, factory):
        """Replace a page factory when the next reference page is supplied."""
        if key in self.pages:
            old=self.pages.pop(key); view=self.views.pop(key); self.host.removeWidget(view); old.deleteLater(); view.deleteLater()
        page=factory(self.store) if callable(factory) else factory; self.pages[key]=page; self.views[key]=ScaledView(page,self.host); self.views[key].surface=ResponsiveSurface(page); self.host.addWidget(self.views[key]); page.action.connect(self.handle_action); page.changed.connect(self.refresh_all) if hasattr(page, 'changed') else None; self.navigate(key)
    def handle_action(self, name):
        if name == 'template_logout':
            self.close(); return
        if name.startswith('nav_'):
            self.navigate(name); return
        if name.startswith('shortcut_'):
            if name=='shortcut_logout':self.close();return
            level=self.current_page.upper() if self.current_page in ('box','carton','pallet') else 'BOX'
            self.navigate('settings')
            self.pages['settings'].show_display_tab(False)
            target={'shortcut_database':'server_host','shortcut_printer':'printers.BOX.device','shortcut_camera':'camera.address','shortcut_scanner':'scanners.BOX.port'}.get(name)
            if name=='shortcut_printer':target='printers.'+level+'.device'
            if target:self.pages['settings'].controls[target].setFocus()
            return
        if name in ('stage_1','stage_2','stage_3','quick_1','quick_2','quick_3'):
            self.navigate(STAGES[int(name[-1])-1]); return
        if name in ('product','sidebar_product','account','mode_info','sidebar_system','device_database','device_printer','device_camera','device_scanner','device_conveyor'):
            self.navigate('settings'); return
        if name in ('kpi_units','kpi_rates'):
            self.navigate('revision'); return
        if name in ('kpi_box','kpi_carton','kpi_pallet'):
            self.navigate(name[4:]); return
        if name in ('activity','sidebar_activity','total_valid','total_reject','total_duplicate','plot','sidebar_stats','sidebar_summary'):
            self.navigate('revision'); return
        if name in ('import','nav_send'):
            self.navigate('send'); return
        if name.startswith('progress_'):
            self.navigate(STAGES[int(name[-1])-1]); return
    def refresh_all(self):
        for page in self.pages.values():
            if hasattr(page,'refresh'):
                try: page.refresh()
                except TypeError: pass
            page.update()
    def toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def closeEvent(self, event):
        settings = self.pages.get('settings')
        if settings is not None and not settings.may_close():
            event.ignore()
            return
        template = self.pages.get('template')
        if template is not None and not template.may_close():
            event.ignore()
            return
        if template is not None:
            template.shutdown()
        if settings is not None:
            settings.shutdown()
        super().closeEvent(event)
