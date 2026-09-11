"""Validated, portable application display preferences (never OS display changes)."""
RESOLUTIONS = ('1920 x 1280', '1920 x 1200', '1920 x 1080', '1680 x 1050',
    '1600 x 1200', '1600 x 900', '1440 x 900', '1400 x 1050', '1366 x 768',
    '1360 x 768', '1280 x 1024', '1280 x 960', '1280 x 800', '1280 x 768',
    '1280 x 720', '1280 x 600', '1152 x 864', '1024 x 768', '800 x 600')
MODES = ('MAKSIMAL', 'JENDELA', 'LAYAR PENUH')
FITS = ('PAS LAYAR', 'UKURAN ASLI (SCROLL)')
DENSITIES = ('RAPAT', 'NORMAL', 'LEGA')

def display_defaults():
    return dict(resolution='OTOMATIS', window_mode='MAKSIMAL', fit='PAS LAYAR',
                font_family='OTOMATIS', font_scale=100, icon_scale=100,
                density='NORMAL', radius=5, hover=True)

def validate_display(raw):
    if not isinstance(raw, dict):
        raise ValueError('Pengaturan tampilan harus berupa objek.')
    cfg = {**display_defaults(), **raw}
    for key, options in [('resolution', ('OTOMATIS', *RESOLUTIONS)), ('window_mode', MODES),
                         ('fit', FITS), ('density', DENSITIES)]:
        if cfg[key] not in options: raise ValueError('Pilihan tampilan tidak valid: '+key)
    for key, low, high in [('font_scale',90,115), ('icon_scale',80,120), ('radius',0,10)]:
        if type(cfg[key]) is not int or not low <= cfg[key] <= high:
            raise ValueError(f'{key} harus {low}–{high}.')
    if not isinstance(cfg['font_family'],str) or not 1 <= len(cfg['font_family']) <= 100:
        raise ValueError('Nama font tidak valid.')
    if not isinstance(cfg['hover'],bool): raise ValueError('Hover harus aktif/nonaktif.')
    return {key:cfg[key] for key in display_defaults()}

CURRENT = display_defaults()
def configure_display(cfg):
    CURRENT.clear(); CURRENT.update(validate_display(cfg))

def icon_rect(x, y, width, height=None):
    from PySide6.QtCore import QRectF
    height = width if height is None else height
    # Preserve the icon's centre and leave its click target in place.
    factor = CURRENT['icon_scale']/100
    return QRectF(x+(width-width*factor)/2, y+(height-height*factor)/2,
                  width*factor, height*factor)
