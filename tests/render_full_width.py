import os,sys,tempfile
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from PySide6.QtWidgets import QApplication,QPushButton
from PySide6.QtCore import Qt,QRectF,QPointF
from PySide6.QtTest import QTest
from agregasi.app import MainWindow
from agregasi.store import Store
from agregasi.display_preferences import RESOLUTIONS
app=QApplication([]);app.setStyle('Fusion');app.setStyleSheet((root/'styles/theme.qss').read_text())
out=root/'docs/lebar_penuh_v3_11_1';out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');win=MainWindow(store);win.show();app.processEvents()
 checked=0
 for resolution in RESOLUTIONS:
  width,height=map(int,resolution.split(' x '));win.resize(width,height);app.processEvents()
  for key in win.PAGES:
   win.navigate(key);app.processEvents();QTest.qWait(20);view=win.views[key]
   assert view.proxy.boundingRect()==view.sceneRect(),(resolution,key,view.proxy.boundingRect(),view.sceneRect())
   bounds=view.mapFromScene(view.proxy.sceneBoundingRect()).boundingRect();vp=view.viewport().rect()
   assert abs(bounds.left()-vp.left())<=1,(resolution,key,bounds,vp)
   assert abs(bounds.right()-vp.right())<=1,(resolution,key,bounds,vp)
   assert abs(bounds.top()-vp.top())<=1,(resolution,key,bounds,vp)
   assert abs(bounds.bottom()-vp.bottom())<=1,(resolution,key,bounds,vp)
   assert abs(view.transform().m11()-view.transform().m22())<1e-8
   assert not view.horizontalScrollBar().isVisible() and not view.verticalScrollBar().isVisible()
   target=win.pages[key].findChild(QPushButton,'nav_settings')
   point=target.mapTo(win.pages[key],target.rect().center())
   QTest.mouseClick(view.viewport(),Qt.MouseButton.LeftButton,pos=view.mapFromScene(point));app.processEvents();assert win.current_page=='settings',(resolution,key,win.current_page,target.geometry(),point,view.mapFromScene(point),target.isVisible(),win.pages[key].size(),win.pages[key].childAt(point),view.scene().mouseGrabberItem(),target.isDown(),view.isActiveWindow())
   checked+=1
  if resolution in ('1920 x 1280','1920 x 1080','1366 x 768','800 x 600'):
   win.navigate('settings');win.pages['settings'].show_display_tab(True);app.processEvents();win.grab().save(str(out/('pengaturan_'+resolution.replace(' ','')+'.png')))
   win.navigate('box');app.processEvents();win.grab().save(str(out/('box_'+resolution.replace(' ','')+'.png')))
 win.resize(1920,1080)
 for key in ('dashboard','carton','pallet','revision','send','template'):
  win.navigate(key);app.processEvents();win.grab().save(str(out/(key+'_1920x1080.png')))
 # Resizing must be reversible and must keep real print dimensions.
 page=win.pages['template'];doc=page.active_editor.document;dimensions=(doc['width_mm'],doc['height_mm'])
 win.resize(800,600);win.resize(1920,1280);app.processEvents();assert dimensions==(doc['width_mm'],doc['height_mm'])
 cfg=win.pages['settings'].repo.load();cfg['display']['fit']='UKURAN ASLI (SCROLL)';win.pages['settings'].repo.save(cfg);win.apply_display_preferences();win.resize(800,600);app.processEvents()
 assert win.pages['template'].size().width()==1448
 win.pages['settings'].dirty=False;win.close();app.processEvents();store.close()
print(f'{checked} page/resolution combinations fill all four viewport edges; navigation, uniform glyph scale, resize reversal and native scroll passed.')
