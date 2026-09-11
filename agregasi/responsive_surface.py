"""Expand layout cells to the viewport while keeping type and icons proportional.

The page's drawing coordinates remain in design units. Native widget cells grow
with the page; Qt continues to lay out and render their text normally. This is
layout expansion, not a nonuniform transform of the finished screen.
"""
from PySide6.QtCore import QRect, QRectF, Qt
from shiboken6 import isValid
from PySide6.QtGui import QPainter, QTransform
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget, QLabel, QAbstractButton, QDialog
from .shell_layout import BODY, content_transform, is_content_cell

WIDTH, HEIGHT = 1448, 1086


def mapped_cell(painter, rect):
    """Map a design cell into page coordinates, before uniform viewport zoom."""
    return painter.worldTransform().mapRect(QRectF(rect))


def proportional_cell(painter, rect):
    original=QRectF(rect);mapped=mapped_cell(painter,original)
    if original.isEmpty():return mapped
    factor=min(mapped.width()/original.width(),mapped.height()/original.height())
    w,h=original.width()*factor,original.height()*factor
    return QRectF(mapped.center().x()-w/2,mapped.center().y()-h/2,w,h)


class SurfacePainter(QPainter):
    """Panels expand, while circular status marks remain circular."""
    def __init__(self, device):
        super().__init__(device)
        sx,sy=getattr(device,'canvas_factors',(1.,1.))
        self.scale(sx,sy)
    def drawEllipse(self,*args):
        if len(args)==1 and isinstance(args[0],(QRect,QRectF)):
            rect=proportional_cell(self,args[0]);self.save();self.resetTransform()
            super().drawEllipse(rect);self.restore()
        else:super().drawEllipse(*args)
    def drawArc(self,rect,start,span):
        mapped=proportional_cell(self,rect);self.save();self.resetTransform()
        super().drawArc(mapped,start,span);self.restore()


class SurfaceSvgRenderer(QSvgRenderer):
    def render(self,painter,*args):
        if len(args)==1 and isinstance(args[0],(QRect,QRectF)) and isinstance(painter,SurfacePainter):
            rect=proportional_cell(painter,args[0]);painter.save();painter.resetTransform()
            super().render(painter,rect);painter.restore()
        else:super().render(painter,*args)


class ResponsiveSurface:
    """One immutable geometry baseline, shared by all resize operations."""
    def __init__(self,page):
        self.page=page;self.cells=[]
        layers=[(page,False)]
        controls=getattr(page,'controls',None)
        if isinstance(controls,QWidget):layers.append((controls,False))
        layers.extend((editor,True) for editor in getattr(page,'editors',{}).values())
        for layer,local in layers:
            for child in layer.findChildren(QWidget,options=Qt.FindChildOption.FindDirectChildrenOnly):
                if child.isWindow() or isinstance(child,QDialog):continue
                original=QRectF(child.geometry())
                content=local or is_content_cell(page.active,original)
                if child is getattr(page,'appearance_panel',None):
                    rect=QRectF(BODY)
                elif content:
                    rect=content_transform(page.active,local).mapRect(original)
                else:
                    rect=original
                child.setProperty('design_geometry',rect.toRect())
                self.cells.append((child,rect))
                if isinstance(child,QAbstractButton):
                    for label in child.findChildren(QLabel,options=Qt.FindChildOption.FindDirectChildrenOnly):
                        label_rect=QRectF(label.geometry())
                        if content:label_rect=content_transform(page.active,True).mapRect(label_rect)
                        self.cells.append((label,label_rect))
        self.factors=(1.,1.)
    def resize(self,width,height):
        sx,sy=width/WIDTH,height/HEIGHT
        self.factors=(sx,sy);self.page.canvas_factors=(sx,sy)
        self.page.setFixedSize(width,height)
        self.cells=[(child,rect) for child,rect in self.cells if isValid(child)]
        for child,rect in self.cells:
            x,y=round(rect.x()*sx),round(rect.y()*sy)
            right,bottom=round((rect.x()+rect.width())*sx),round((rect.y()+rect.height())*sy)
            child.setGeometry(x,y,right-x,bottom-y)
        for editor in getattr(self.page,'editors',{}).values():
            # LabelCanvas already owns a uniform fit policy for real print data.
            editor.canvas.view.set_zoom(editor.zoom.currentText())
        self.page.update()
    def design_rect(self,rect):
        sx,sy=self.factors
        return QRectF(rect.x()*sx,rect.y()*sy,rect.width()*sx,rect.height()*sy)

    def content_rect(self,rect):
        """A legacy content cell in current page pixels, matching its control."""
        return self.design_rect(content_transform(self.page.active).mapRect(QRectF(rect)))
