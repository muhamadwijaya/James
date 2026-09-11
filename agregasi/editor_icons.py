"""Small vector controls matching the line icon style of the reference."""
from functools import lru_cache
from pathlib import Path
from PySide6.QtCore import QByteArray,Qt,QRectF
from PySide6.QtGui import QIcon,QPixmap,QPainter
from PySide6.QtSvg import QSvgRenderer

PATHS={
 'pallet_level':'<rect x="3" y="2" width="18" height="4" rx="1"/><rect x="3" y="9" width="18" height="4" rx="1"/><rect x="3" y="16" width="18" height="4" rx="1"/><path d="M2 24v-2h20v2M7 20v2M17 20v2"/>',
 'box_level':'<path d="M2 7 12 1l10 6v13l-10 5-10-5ZM2 7l10 6 10-6M12 13v12"/>',
 'paper':'<path d="M5 2h10l5 5v17H5ZM15 2v6h5M8 12h9M8 16h9M8 20h6"/>',
 'zoom_in':'<circle cx="10" cy="10" r="7"/><path d="m15 15 8 8M6 10h8M10 6v8"/>',
 'zoom_out':'<circle cx="10" cy="10" r="7"/><path d="m15 15 8 8M6 10h8"/>',
 'chevron_left':'<path d="m16 3-9 10 9 10"/>',
 'chevron_right':'<path d="m8 3 9 10-9 10"/>',
 'carton_level':'<path d="M2 12l5-3 5 3v7l-5 3-5-3ZM2 12l5 3 5-3M7 15v7M12 12l5-3 5 3v7l-5 3-5-3ZM12 12l5 3 5-3M17 15v7M7 4l5-3 5 3v6l-5 3-5-3ZM7 4l5 3 5-3M12 7v6"/>',
 'undo':'<path d="M8 6 3 11l5 5M3 11h11a6 6 0 0 1 0 12"/>',
 'redo':'<path d="m16 6 5 5-5 5M21 11H10a6 6 0 0 0 0 12"/>',
 'cut':'<circle cx="5" cy="6" r="3"/><circle cx="5" cy="18" r="3"/><path d="m8 8 13 13M8 16 21 3"/>',
 'copy':'<rect x="8" y="8" width="13" height="14" rx="1"/><path d="M16 7V2H2v15h5"/>',
 'paste':'<path d="M8 4H4v18h16V4h-4"/><rect x="8" y="2" width="8" height="5" rx="1"/>',
 'delete':'<path d="M3 6h18M8 3h8M5 6l1 16h12l1-16M9 10v8M15 10v8"/>',
 'duplicate':'<rect x="2" y="2" width="13" height="13" rx="1"/><rect x="8" y="8" width="14" height="14" rx="1"/><path d="M12 15h6M15 12v6"/>',
 'align':'<path d="M3 2v20M7 5h14v4H7ZM7 14h9v4H7Z"/>',
 'distribute':'<path d="M2 2v20M22 2v20M7 7h3v10H7ZM14 7h3v10h-3Z"/>',
 'layer':'<path d="m2 8 10-6 10 6-10 6ZM2 13l10 6 10-6M2 18l10 6 10-6"/>',
 'grid':'<path d="M2 2h20v20H2ZM2 8h20M2 15h20M8 2v20M15 2v20"/>',
 'snap':'<path d="M4 3v12a8 8 0 0 0 16 0V3h-5v12a3 3 0 0 1-6 0V3ZM4 8h5M15 8h5"/>',
 'text':'<path d="M3 3h18M12 3v19M7 22h10"/>',
 'barcode':'<path d="M2 3v18M5 3v18M9 3v18M11 3v18M15 3v18M18 3v18M22 3v18"/>',
 'datamatrix':'<path d="M2 2v20h20M6 2h3M13 2h3M20 2h2v3M22 9v3M22 17v2M6 6h4v4H6ZM13 7h3v3h-3ZM6 14h3v3H6ZM13 13h5v5h-5Z"/>',
 'qr':'<path d="M2 2h7v7H2ZM15 2h7v7h-7ZM2 15h7v7H2ZM13 13h4v4h-4ZM19 13h3v4M13 20v2h4M20 20h2v2"/>',
 'rectangle':'<rect x="2" y="4" width="20" height="16" rx="1"/>',
 'line':'<path d="M3 21 21 3"/><circle cx="3" cy="21" r="1"/><circle cx="21" cy="3" r="1"/>',
 'image':'<rect x="2" y="2" width="20" height="20" rx="1"/><circle cx="16" cy="7" r="2"/><path d="m2 18 6-8 6 8 3-4 5 7"/>',
 'date':'<rect x="2" y="4" width="20" height="18" rx="1"/><path d="M6 1v6M18 1v6M2 10h20M6 15h3M14 15h3M6 19h3"/>',
 'serial':'<path d="M7 3 5 21M17 3l-2 18M2 9h20M1 15h20"/>',
 'batch':'<path d="M2 2h10l10 10-10 10L2 12Z"/><circle cx="7" cy="7" r="2"/>',
 'dynamic':'<path d="M8 3H5v6l-3 3 3 3v6h3M16 3h3v6l3 3-3 3v6h-3M10 12h4"/>',
 'preview':'<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12Z"/><circle cx="12" cy="12" r="4"/>',
 'import':'<path d="M3 15v7h18v-7M12 1v15M7 11l5 5 5-5"/>',
 'export':'<path d="M3 15v7h18v-7M12 16V1M7 6l5-5 5 5"/>',
 'publish':'<path d="M6 17H4a4 4 0 0 1-1-8 7 7 0 0 1 13-4 6 6 0 0 1 4 12h-2M12 23V9M7 14l5-5 5 5"/>',
 'save':'<path d="M2 2h17l3 3v17H2ZM6 2v7h12V2M6 14h12v8H6Z"/>',
 'new':'<path d="M4 2h12l4 4v16H4ZM12 9v9M8 13h8"/>',
 'field_error':'<circle cx="13" cy="13" r="10"/><path d="M13 6v9M13 19h.01"/>',
 'default':'<path d="m12 1 3 7 8 1-6 5 2 8-7-4-7 4 2-8-6-5 8-1Z"/>',
}

# Equal optical bounds and stroke weight for the reference sidebar badges.
for _name,_source in [('sidebar_box','box_level'),('sidebar_carton','carton_level'),('sidebar_pallet','pallet_level'),('sidebar_printer','paper')]:
    _inner=PATHS[_source]
    if _name=='sidebar_printer':_inner='<path d="M6 8V2h12v6M6 18H2V8h20v10h-4M6 14h12v10H6Z"/><path d="M17 11h2"/>'
    PATHS[_name]='<circle cx="13" cy="13" r="10.5"/><g transform="translate(5.8 5.2) scale(.60)" stroke-width="2">'+_inner+'</g>'
PATHS['sidebar_inactive']='<circle cx="13" cy="13" r="10.5"/><path d="m11 8 6 5-6 5Z"/>'
PATHS['sidebar_default']='<circle cx="13" cy="13" r="10.5"/><path d="m11 8 5 5-5 5"/>'
PATHS['sidebar_total']='<circle cx="13" cy="13" r="10.5"/><circle cx="13" cy="13" r="4.5"/>'
PATHS['sidebar_clock']='<circle cx="13" cy="13" r="10.5"/><path d="M13 6v7h5"/>'

@lru_cache(maxsize=128)
def icon(name,size=24):
    if name in PATHS:
        raw=('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 26 26"><g fill="none" stroke="#c2d2e4" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'+PATHS[name]+'</g></svg>').encode()
    else:
        path=Path(__file__).resolve().parent.parent/'assets/svg'/f'{name}.svg'
        raw=path.read_bytes()
    renderer=QSvgRenderer(QByteArray(raw));pix=QPixmap(size*2,size*2);pix.fill(Qt.GlobalColor.transparent)
    p=QPainter(pix);renderer.render(p,QRectF(0,0,size*2,size*2));p.end();pix.setDevicePixelRatio(2)
    return QIcon(pix)
