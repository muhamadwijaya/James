"""One vector renderer for canvas, thumbnails, PNG, PDF and printer output."""
import base64
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QMarginsF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QImage, QPageSize, QPainter, QPen, QPdfWriter
from PySide6.QtSvg import QSvgRenderer

from .template_model import resolve_text, validate_document
from .typography import ui_font

UNITS = 10.0
SYMBOLS = {
 'dry':'<path d="M3 12a9 9 0 0 1 18 0c-3-3-3-3-6 0-3-3-3-3-6 0-3-3-3-3-6 0Z" fill="#111820"/><path d="M12 12v7c0 4 5 4 5 0M12 1v2"/>',
 'stack':'<path d="M5 10h14v5H5zM5 17h14v5H5zM6 3l12 6M18 3 6 9"/>',
 'up':'<path d="M6 19V4M18 19V4M2 8l4-5 4 5M14 8l4-5 4 5M2 22h20"/>',
 'package':'<path d="M2 7 12 2l10 5v12l-10 5-10-5ZM2 7l10 5 10-5M12 12v12M7 4l10 5v5"/>',
 'weight':'<path d="M8 8h8l4 14H4Z" fill="#111820"/><circle cx="12" cy="5" r="3"/>',
 'care':'<path d="M7 4 12 1l5 3v8l-5 3-5-3ZM7 4l5 3 5-3M12 7v8M2 8v9l7 6M22 8v9l-7 6M3 12l5 5M21 12l-5 5"/>',
}


@lru_cache(maxsize=16)
def symbol_renderer(name):
    body=SYMBOLS.get(name,SYMBOLS['package'])
    return QSvgRenderer(QByteArray(('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 26"><g stroke="#111820" fill="none" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'+body+'</g></svg>').encode()))


@lru_cache(maxsize=512)
def encoded_symbol(kind, value):
    if not value or '{{' in value:raise ValueError('Isi kode kosong atau data dinamis belum diisi.')
    if len(value)>500:raise ValueError('Isi kode maksimal 500 karakter.')
    if kind=='barcode':
        from barcode import Code128
        if any(ord(c)>127 for c in value):raise ValueError('Code128 hanya menerima karakter ASCII.')
        return Code128(value).build()[0]
    if kind=='qr':
        import qrcode
        qr=qrcode.QRCode(border=4,error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=1)
        qr.add_data(value);qr.make(fit=True)
        return tuple(tuple(row) for row in qr.get_matrix())
    if kind=='datamatrix':
        from pystrich.datamatrix import DataMatrixEncoder,DataMatrixData
        encoder=DataMatrixEncoder(DataMatrixData(value,auto_encoding=True),quiet_zone=2)
        image=encoder.get_pilimage(cellsize=1).convert('L')
        return tuple(tuple(image.getpixel((x,y))<128 for x in range(image.width)) for y in range(image.height))
    raise ValueError('Jenis kode tidak didukung.')


def check_renderable(document):
    doc=validate_document(document)
    for e in doc['elements']:
        if '{{' in resolve_text(e.get('text',''),doc):raise ValueError('Field dinamis belum memiliki nilai: '+e.get('text',''))
        if e['type'] in ('barcode','qr','datamatrix'):
            try:encoded_symbol(e['type'],resolve_text(e.get('text',''),doc))
            except Exception as exc:raise ValueError('Kode tidak dapat dibuat: '+str(exc)) from exc
        if e['type']=='image':
            image=QImage.fromData(base64.b64decode(e['image']))
            if image.isNull() or image.width()*image.height()>16_000_000:raise ValueError('Gambar tidak valid atau melebihi 16 megapiksel.')
    return doc


def _matrix(painter, matrix, rect):
    n=len(matrix);m=len(matrix[0]);cell=min(rect.width()/m,rect.height()/n)
    x0=rect.center().x()-m*cell/2;y0=rect.center().y()-n*cell/2
    painter.setRenderHint(QPainter.RenderHint.Antialiasing,False)
    painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor('#000000'))
    for y,row in enumerate(matrix):
        start=None
        for x in range(m+1):
            on=x<m and row[x]
            if on and start is None:start=x
            if not on and start is not None:
                painter.drawRect(QRectF(x0+start*cell,y0+y*cell,(x-start)*cell,cell));start=None


def paint_element(painter, element, document, local=False, show_errors=False):
    e=element;x=0 if local else e['x']*UNITS;y=0 if local else e['y']*UNITS
    r=QRectF(x,y,e['w']*UNITS,e['h']*UNITS)
    painter.save();painter.setClipRect(r.adjusted(-1,-1,1,1),Qt.ClipOperation.IntersectClip)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing,True)
    pen=QPen(QColor(e.get('color','#111820')),e.get('stroke',0.25)*UNITS)
    if e.get('dashed'):pen.setStyle(Qt.PenStyle.DashLine)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush if e.get('fill','none')=='none' else QColor(e['fill']))
    kind=e['type'];text=resolve_text(e.get('text',''),document)
    if kind=='text':
        font=ui_font(max(1,round(e.get('font',7)*25.4/72*UNITS)),e.get('bold',False))
        painter.setFont(font);painter.setPen(QColor(e.get('color','#111820')))
        align={'left':Qt.AlignmentFlag.AlignLeft,'center':Qt.AlignmentFlag.AlignHCenter,'right':Qt.AlignmentFlag.AlignRight}.get(e.get('align'),Qt.AlignmentFlag.AlignLeft)
        painter.drawText(r,int(align|Qt.AlignmentFlag.AlignVCenter|Qt.TextFlag.TextWordWrap),text)
    elif kind in ('barcode','qr','datamatrix'):
        painter.fillRect(r,Qt.GlobalColor.white)
        try:
            code=encoded_symbol(kind,text)
            if kind=='barcode':
                # Code128 includes a checksum; retain a ten-module quiet zone.
                cell=r.width()/(len(code)+20);bar_h=r.height()-(3.6*UNITS if e.get('human',True) else 0)
                if bar_h<=0:raise ValueError('Tinggi Code128 terlalu kecil.')
                painter.setRenderHint(QPainter.RenderHint.Antialiasing,False)
                painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor('#000000'))
                start=None
                for i in range(len(code)+1):
                    on=i<len(code) and code[i]=='1'
                    if on and start is None:start=i
                    if not on and start is not None:
                        painter.drawRect(QRectF(r.x()+(start+10)*cell,r.y(),(i-start)*cell,bar_h));start=None
                if e.get('human',True):
                    painter.setFont(ui_font(round(6*25.4/72*UNITS)));painter.setPen(QColor('#000000'))
                    painter.drawText(QRectF(r.x(),r.y()+bar_h,r.width(),r.height()-bar_h),int(Qt.AlignmentFlag.AlignCenter),text)
            else:_matrix(painter,code,r)
        except Exception as exc:
            if not show_errors:
                painter.restore();raise
            painter.fillRect(r,QColor('#fff0f0'));painter.setPen(QColor('#ae2632'));painter.setFont(ui_font(22))
            painter.drawText(r,int(Qt.AlignmentFlag.AlignCenter|Qt.TextFlag.TextWordWrap),'KODE TIDAK VALID\n'+str(exc))
    elif kind=='rectangle':
        inset=e.get('stroke',0.25)*UNITS/2;painter.drawRect(r.adjusted(inset,inset,-inset,-inset))
    elif kind=='line':
        painter.drawLine(r.topLeft(),r.bottomRight())
    elif kind=='symbol':symbol_renderer(e.get('symbol','package')).render(painter,r)
    elif kind=='image':
        try:im=QImage.fromData(base64.b64decode(e.get('image','')))
        except Exception:im=QImage()
        if not im.isNull():
            size=im.size().scaled(r.size().toSize(),Qt.AspectRatioMode.KeepAspectRatio)
            target=QRectF(r.center().x()-size.width()/2,r.center().y()-size.height()/2,size.width(),size.height())
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,True);painter.drawImage(target,im)
    painter.restore()


def paint_document(painter,document,target=None):
    source=QRectF(0,0,document['width_mm']*UNITS,document['height_mm']*UNITS)
    painter.save()
    if target is not None:
        scale=min(target.width()/source.width(),target.height()/source.height())
        painter.translate(target.center().x()-source.width()*scale/2,target.center().y()-source.height()*scale/2)
        painter.scale(scale,scale)
    painter.fillRect(source,Qt.GlobalColor.white);painter.setClipRect(source)
    for element in document['elements']:paint_element(painter,element,document)
    painter.restore()


def render_image(document,dpi=None):
    dpi=dpi or document['dpi'];w=round(document['width_mm']/25.4*dpi);h=round(document['height_mm']/25.4*dpi)
    image=QImage(w,h,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.white)
    image.setDotsPerMeterX(round(dpi/0.0254));image.setDotsPerMeterY(round(dpi/0.0254))
    painter=QPainter(image)
    try:paint_document(painter,document,QRectF(0,0,w,h))
    finally:painter.end()
    return image


def export_pdf(document,path):
    check_renderable(document)
    writer=QPdfWriter(str(path));writer.setResolution(int(document['dpi']))
    writer.setPageSize(QPageSize(QSizeF(document['width_mm'],document['height_mm']),QPageSize.Unit.Millimeter,'Label',QPageSize.SizeMatchPolicy.ExactMatch))
    writer.setPageMargins(QMarginsF(0,0,0,0));writer.setTitle(document['name'])
    painter=QPainter(writer)
    if not painter.isActive():raise ValueError('PDF tidak dapat dibuat di lokasi tersebut.')
    try:paint_document(painter,document,QRectF(0,0,writer.width(),writer.height()))
    finally:painter.end()
    if not Path(path).is_file() or Path(path).stat().st_size<100:raise ValueError('PDF gagal disimpan.')
