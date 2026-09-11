"""Interactive label canvas, rulers, selection, resizing and document undo."""
from copy import deepcopy
from uuid import uuid4

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QUndoCommand, QUndoStack, QKeySequence
from PySide6.QtWidgets import QGraphicsObject, QGraphicsScene, QGraphicsView, QGraphicsItem, QWidget

from .label_render import UNITS, paint_element
from .template_model import new_element
from .typography import ui_font


class DocumentChange(QUndoCommand):
    def __init__(self,canvas,before,after,title):
        super().__init__(title);self.canvas=canvas;self.before=deepcopy(before);self.after=deepcopy(after)
    def undo(self):self.canvas._load(self.before)
    def redo(self):self.canvas._load(self.after)


class LabelObject(QGraphicsObject):
    def __init__(self,canvas,element,index):
        super().__init__();self.canvas=canvas;self.element=element;self.resizing=False;self.before=None
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,not element.get('locked',False))
        self.setAcceptHoverEvents(True);self.setPos(element['x']*UNITS,element['y']*UNITS);self.setZValue(index)
        self.setToolTip(element['type'].upper()+': '+element.get('text',''))
    def boundingRect(self):return QRectF(0,0,self.element['w']*UNITS,self.element['h']*UNITS)
    def paint(self,painter,option,widget=None):
        paint_element(painter,self.element,self.canvas.document,local=True,show_errors=True)
        if self.isSelected():
            painter.save();pen=QPen(QColor('#0786ef'),1.4,Qt.PenStyle.DashLine);pen.setCosmetic(True)
            painter.setPen(pen);painter.setBrush(Qt.BrushStyle.NoBrush);painter.drawRect(self.boundingRect())
            if not self.element.get('locked'):
                size=self.handle_size();painter.setBrush(QColor('#ffffff'));painter.setPen(QPen(QColor('#087ace'),1))
                painter.drawRect(QRectF(self.boundingRect().right()-size,self.boundingRect().bottom()-size,size,size))
            painter.restore()
    def handle_size(self):return max(12,7/max(0.05,self.canvas.view.transform().m11()))
    def mousePressEvent(self,event):
        self.before=deepcopy(self.canvas.document)
        corner=self.boundingRect().bottomRight();size=self.handle_size()*1.5
        self.resizing=self.isSelected() and not self.element.get('locked') and event.pos().x()>corner.x()-size and event.pos().y()>corner.y()-size
        if self.resizing:event.accept()
        else:super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self.resizing:
            p=event.pos()/UNITS;w=max(0.5,p.x());h=max(0.5,p.y())
            if self.canvas.snap:w=round(w*2)/2;h=round(h*2)/2
            self.prepareGeometryChange();self.element['w']=min(w,self.canvas.document['width_mm']-self.element['x']);self.element['h']=min(h,self.canvas.document['height_mm']-self.element['y']);self.update();event.accept()
        else:super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event)
        before=self.before;self.before=None;self.resizing=False
        if before is not None and before!=self.canvas.document:
            after=deepcopy(self.canvas.document)
            QTimer.singleShot(0,lambda:self.canvas.commit(before,after,'Pindah / ubah ukuran objek'))
    def mouseDoubleClickEvent(self,event):
        self.setSelected(True);self.canvas.edit_requested.emit(self.element['id']);event.accept()
    def hoverMoveEvent(self,event):
        size=self.handle_size()*1.5;r=self.boundingRect()
        self.setCursor(Qt.CursorShape.SizeFDiagCursor if self.isSelected() and event.pos().x()>r.right()-size and event.pos().y()>r.bottom()-size and not self.element.get('locked') else Qt.CursorShape.OpenHandCursor)
        super().hoverMoveEvent(event)
    def itemChange(self,change,value):
        if change==QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene() is not None and not self.canvas.loading:
            x=value.x()/UNITS;y=value.y()/UNITS
            if self.canvas.snap:x=round(x*2)/2;y=round(y*2)/2
            x=max(0,min(x,self.canvas.document['width_mm']-self.element['w']));y=max(0,min(y,self.canvas.document['height_mm']-self.element['h']))
            self.element['x']=x;self.element['y']=y
            return QPointF(x*UNITS,y*UNITS)
        return super().itemChange(change,value)


class Ruler(QWidget):
    def __init__(self,view,horizontal):
        super().__init__(view);self.view=view;self.horizontal=horizontal
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),QColor('#092a40'));p.setPen(QColor('#9bb1c6'));p.setFont(ui_font(8))
        doc=self.view.canvas.document
        maximum=doc['width_mm'] if self.horizontal else doc['height_mm']
        for mm in range(0,int(maximum)+1):
            q=self.view.mapFromScene(QPointF(mm*UNITS,0) if self.horizontal else QPointF(0,mm*UNITS))
            coord=q.x() if self.horizontal else q.y();long=mm%10==0
            if self.horizontal:
                p.drawLine(coord,self.height(),coord,self.height()-(8 if long else 3))
                if long:p.drawText(coord+2,10,str(mm))
            else:
                p.drawLine(self.width(),coord,self.width()-(8 if long else 3),coord)
                if long:p.drawText(1,coord-2,str(mm))
        p.end()


class CanvasView(QGraphicsView):
    def __init__(self,canvas,parent=None):
        super().__init__(canvas.scene,parent);self.canvas=canvas;self.zoom_mode='Fit'
        self.setObjectName('labelCanvasView');self.setStyleSheet('QGraphicsView {border:1px solid #345d74;background:#092b42;}')
        self.setRenderHints(QPainter.RenderHint.Antialiasing|QPainter.RenderHint.TextAntialiasing|QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag);self.setRubberBandSelectionMode(Qt.ItemSelectionMode.ContainsItemShape)
        self.setViewportMargins(24,22,0,0);self.top_ruler=Ruler(self,True);self.left_ruler=Ruler(self,False)
        self.horizontalScrollBar().valueChanged.connect(self.update_rulers);self.verticalScrollBar().valueChanged.connect(self.update_rulers)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    def update_rulers(self):self.top_ruler.update();self.left_ruler.update()
    def resizeEvent(self,event):
        super().resizeEvent(event);self.top_ruler.setGeometry(24,0,self.viewport().width(),22);self.left_ruler.setGeometry(0,22,24,self.viewport().height())
        self.set_zoom(self.zoom_mode)
    def showEvent(self,event):super().showEvent(event);self.set_zoom(self.zoom_mode)
    def set_zoom(self,mode):
        self.zoom_mode=str(mode);self.resetTransform()
        self.fitInView(self.sceneRect(),Qt.AspectRatioMode.KeepAspectRatio)
        if mode!='Fit':
            factor=float(str(mode).replace('%',''))/100;self.scale(factor,factor)
        self.update_rulers()
    def drawBackground(self,painter,rect):
        painter.fillRect(rect,QColor('#0c2d43'))
        if self.canvas.grid:
            pen=QPen(QColor('#224359'),1);pen.setCosmetic(True);painter.setPen(pen)
            step=5*UNITS
            x=int(rect.left()/step)*step
            while x<rect.right():painter.drawLine(QPointF(x,rect.top()),QPointF(x,rect.bottom()));x+=step
            y=int(rect.top()/step)*step
            while y<rect.bottom():painter.drawLine(QPointF(rect.left(),y),QPointF(rect.right(),y));y+=step
    def keyPressEvent(self,event):
        matches=[(QKeySequence.StandardKey.Undo,self.canvas.undo.undo),(QKeySequence.StandardKey.Redo,self.canvas.undo.redo),(QKeySequence.StandardKey.Copy,self.canvas.copy),(QKeySequence.StandardKey.Cut,self.canvas.cut),(QKeySequence.StandardKey.Paste,self.canvas.paste),(QKeySequence.StandardKey.SelectAll,self.canvas.select_all)]
        for shortcut,callback in matches:
            if event.matches(shortcut):callback();event.accept();return
        if event.key() in (Qt.Key.Key_Delete,Qt.Key.Key_Backspace):self.canvas.delete();event.accept();return
        offsets={Qt.Key.Key_Left:(-1,0),Qt.Key.Key_Right:(1,0),Qt.Key.Key_Up:(0,-1),Qt.Key.Key_Down:(0,1)}
        if event.key() in offsets:
            dx,dy=offsets[event.key()];step=5 if event.modifiers()&Qt.KeyboardModifier.ShiftModifier else .5
            self.canvas.nudge(dx*step,dy*step);event.accept();return
        if event.key()==Qt.Key.Key_D and event.modifiers()&Qt.KeyboardModifier.ControlModifier:self.canvas.duplicate();event.accept();return
        super().keyPressEvent(event)
    def wheelEvent(self,event):
        if event.modifiers()&Qt.KeyboardModifier.ControlModifier:
            self.scale(1.1 if event.angleDelta().y()>0 else 1/1.1,1.1 if event.angleDelta().y()>0 else 1/1.1);self.update_rulers();event.accept()
        else:super().wheelEvent(event)


class LabelCanvas(QWidget):
    changed=Signal();selection_changed=Signal();edit_requested=Signal(str)
    clipboard=[]
    def __init__(self,document,parent=None):
        super().__init__(parent);self.loading=False;self.snap=True;self.grid=True;self.document=deepcopy(document)
        self.scene=QGraphicsScene(self);self.undo=QUndoStack(self);self.view=CanvasView(self,self)
        self.scene.selectionChanged.connect(self.selection_changed)
        self._load(document)
    def resizeEvent(self,event):super().resizeEvent(event);self.view.setGeometry(self.rect())
    def _load(self,document):
        selection=set(self.selected_ids());self.loading=True;self.scene.blockSignals(True)
        try:
            self.document=deepcopy(document);self.scene.clear()
            w=self.document['width_mm']*UNITS;h=self.document['height_mm']*UNITS
            paper=self.scene.addRect(QRectF(0,0,w,h),QPen(QColor('#c2c9ce'),1),QColor('#ffffff'));paper.setZValue(-1000)
            for i,e in enumerate(self.document['elements']):
                item=LabelObject(self,e,i);self.scene.addItem(item);item.setSelected(e['id'] in selection)
            old=self.scene.sceneRect();self.scene.setSceneRect(-25,-25,w+50,h+50)
            if old!=self.scene.sceneRect():self.view.set_zoom(self.view.zoom_mode)
        finally:self.loading=False;self.scene.blockSignals(False)
        self.changed.emit();self.selection_changed.emit()
    def set_document(self,document):self.scene.clearSelection();self._load(document);self.undo.clear();self.undo.setClean()
    def commit(self,before,after,title):
        if before!=after:self.undo.push(DocumentChange(self,before,after,title))
    def change(self,after,title='Ubah template'):self.commit(self.document,after,title)
    def selected_ids(self):return [i.element['id'] for i in self.scene.selectedItems() if isinstance(i,LabelObject)]
    def selected_elements(self):
        identifiers=set(self.selected_ids());return [e for e in self.document['elements'] if e['id'] in identifiers]
    def select_ids(self,ids):
        self.scene.blockSignals(True)
        for item in self.scene.items():
            if isinstance(item,LabelObject):item.setSelected(item.element['id'] in ids)
        self.scene.blockSignals(False);self.selection_changed.emit()
    def select_all(self):self.select_ids([e['id'] for e in self.document['elements']])
    def add(self,kind,**values):
        if len(self.document['elements'])>=250:raise ValueError('Maksimal 250 objek per label.')
        dims={'text':(35,8),'barcode':(50,15),'qr':(20,20),'datamatrix':(20,20),'rectangle':(30,20),'line':(35,.2),'image':(25,25),'symbol':(12,12)}
        w,h=dims[kind];element=new_element(kind,5,5,min(w,self.document['width_mm']-10),min(h,self.document['height_mm']-10),**values)
        after=deepcopy(self.document);after['elements'].append(element);self.change(after,'Tambah '+kind);self.select_ids([element['id']])
    def update_selected(self,values):
        selected=set(self.selected_ids());after=deepcopy(self.document)
        for e in after['elements']:
            if e['id'] in selected:
                e.update(values);e['w']=min(e['w'],after['width_mm']);e['h']=min(e['h'],after['height_mm'])
                e['x']=max(0,min(e['x'],after['width_mm']-e['w']));e['y']=max(0,min(e['y'],after['height_mm']-e['h']))
        self.change(after,'Ubah properti objek')
    def delete(self):
        selected=set(self.selected_ids());after=deepcopy(self.document);after['elements']=[e for e in after['elements'] if e['id'] not in selected or e.get('locked')];self.change(after,'Hapus objek')
    def copy(self):LabelCanvas.clipboard=deepcopy(self.selected_elements())
    def cut(self):self.copy();self.delete()
    def paste(self):
        if not LabelCanvas.clipboard:return
        if len(self.document['elements'])+len(LabelCanvas.clipboard)>250:raise ValueError('Maksimal 250 objek per label.')
        after=deepcopy(self.document);ids=[]
        for e in deepcopy(LabelCanvas.clipboard):
            e['id']=uuid4().hex;e['w']=min(e['w'],after['width_mm']);e['h']=min(e['h'],after['height_mm'])
            e['x']=max(0,min(e['x']+2,after['width_mm']-e['w']));e['y']=max(0,min(e['y']+2,after['height_mm']-e['h']))
            ids.append(e['id']);after['elements'].append(e)
        self.change(after,'Tempel objek');self.select_ids(ids)
    def duplicate(self):self.copy();self.paste()
    def nudge(self,dx,dy):
        ids=set(self.selected_ids());after=deepcopy(self.document)
        for e in after['elements']:
            if e['id'] in ids and not e.get('locked'):
                e['x']=max(0,min(e['x']+dx,after['width_mm']-e['w']));e['y']=max(0,min(e['y']+dy,after['height_mm']-e['h']))
        self.change(after,'Geser objek')
    def align(self,mode):
        ids=set(self.selected_ids());after=deepcopy(self.document);elements=[e for e in after['elements'] if e['id'] in ids and not e.get('locked')]
        if not elements:return
        left=min(e['x'] for e in elements);right=max(e['x']+e['w'] for e in elements);top=min(e['y'] for e in elements);bottom=max(e['y']+e['h'] for e in elements)
        if len(elements)==1:left=top=0;right=after['width_mm'];bottom=after['height_mm']
        for e in elements:
            if mode=='left':e['x']=left
            elif mode=='center':e['x']=(left+right-e['w'])/2
            elif mode=='right':e['x']=right-e['w']
            elif mode=='top':e['y']=top
            elif mode=='middle':e['y']=(top+bottom-e['h'])/2
            elif mode=='bottom':e['y']=bottom-e['h']
        self.change(after,'Ratakan '+mode)
    def distribute(self,horizontal=True):
        ids=set(self.selected_ids());after=deepcopy(self.document);elems=[e for e in after['elements'] if e['id'] in ids and not e.get('locked')]
        if len(elems)<3:return
        axis,size=('x','w') if horizontal else ('y','h');elems.sort(key=lambda e:e[axis]);start=elems[0][axis];end=elems[-1][axis]+elems[-1][size]
        gap=(end-start-sum(e[size] for e in elems))/(len(elems)-1);pos=start
        for e in elems:e[axis]=pos;pos+=e[size]+gap
        self.change(after,'Samakan jarak objek')
    def reorder(self,front=True):
        ids=set(self.selected_ids());after=deepcopy(self.document);chosen=[e for e in after['elements'] if e['id'] in ids];rest=[e for e in after['elements'] if e['id'] not in ids]
        after['elements']=rest+chosen if front else chosen+rest;self.change(after,'Urutan lapisan')
