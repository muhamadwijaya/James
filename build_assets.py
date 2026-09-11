"""Regenerate editable SVG assets and the Qt Designer overlay."""
from pathlib import Path
from xml.sax.saxutils import escape
from agregasi.navigation import ITEMS, button_rect
BASE=Path(__file__).resolve().parent
icons={
'box':'<path d="M7 15 24 6 41 15 41 35 24 44 7 35Z M7 15 24 24 41 15 M24 24V44 M15 11 32 20V29L27 27V22 M14 19V28"/>',
'carton':'<path d="M7 15 24 6 41 15 41 35 24 44 7 35Z M7 15 24 24 41 15 M24 24V44 M15 11 32 20V28L27 26V22"/>',
'units':'<path d="M6 15 24 5 42 15 42 36 24 45 6 36Z M6 15 24 25 42 15 M24 25V45 M12 12 30 22V42 M18 8 36 18V39 M12 18V39 M18 22V42 M6 22 24 32 42 22 M6 29 24 39 42 29"/>',
'pallet':'<rect x="5" y="5" width="16" height="10" rx="1"/><rect x="27" y="5" width="16" height="10" rx="1"/><rect x="5" y="20" width="16" height="10" rx="1"/><rect x="27" y="20" width="16" height="10" rx="1"/><path d="M9 9H16 M31 9H38 M9 24H16 M31 24H38 M3 35H45V42H3Z M8 35V42 M23 35V42 M38 35V42 M9 15V20 M17 15V20 M31 15V20 M39 15V20"/>',
'database':'<ellipse cx="24" cy="10" rx="17" ry="6"/><path d="M7 10V37C7 45 41 45 41 37V10 M7 19C7 27 41 27 41 19 M7 28C7 36 41 36 41 28"/>',
'printer':'<path d="M12 16V4H36V16 M12 34H4V17H44V34H36 M12 27H36V44H12Z M17 33H31 M17 38H31 M10 22H14 M36 22H39"/>',
'camera':'<rect x="4" y="10" width="31" height="29" rx="2"/><path d="M35 18 45 12V38L35 32Z"/><circle cx="20" cy="24" r="10"/><circle cx="20" cy="24" r="5"/>',
'scanner':'<path d="M8 5H33L39 13V20H25L31 39H21L16 20H8Z M12 10H31 M9 15H34 M24 39H33V45H18V39 M4 7H1V17H4 M24 25H28 M26 30H30"/>',
'conveyor':'<rect x="2" y="31" width="44" height="12" rx="6"/><circle cx="9" cy="37" r="3"/><circle cx="24" cy="37" r="3"/><circle cx="39" cy="37" r="3"/><path d="M16 31V5H31V31 M20 11H27 M21 15H26 M22 19H25 M17 44V47 M33 44V47"/>',
'home':'<path d="M5 22 24 6 43 22 M10 19V43H20V29H29V43H38V19"/>',
'upload':'<path d="M15 35H10A9 9 0 0 1 8 17A15 15 0 0 1 36 14A11 11 0 0 1 38 35H32 M24 44V22 M15 31 24 22 33 31"/>',
'revision':'<path d="M9 4H28L38 14V29 M9 4V44H26 M28 4V14H38 M15 20H31 M15 26H29 M15 32H24 M15 38H23"/><circle cx="35" cy="37" r="9"/><path d="M35 31V37L39 39"/>',
'template':'<path d="M8 4H36V25 M8 4V43H22 M14 11H30 M14 17H30 M14 23H25 M14 29H21 M14 35H21"/><rect x="27" y="26" width="15" height="9" rx="1"/><rect x="27" y="39" width="9" height="6" rx="1"/><path d="M31 30H38 M31 35V39"/>',
'settings':'<path d="M40.03 18.33 L44.62 20.03 L44.62 27.97 L40.03 29.67 L39.34 31.32 L41.39 35.78 L35.78 41.39 L31.32 39.34 L29.67 40.03 L27.97 44.62 L20.03 44.62 L18.33 40.03 L16.68 39.34 L12.22 41.39 L6.61 35.78 L8.66 31.32 L7.97 29.67 L3.38 27.97 L3.38 20.03 L7.97 18.33 L8.66 16.68 L6.61 12.22 L12.22 6.61 L16.68 8.66 L18.33 7.97 L20.03 3.38 L27.97 3.38 L29.67 7.97 L31.32 8.66 L35.78 6.61 L41.39 12.22 L39.34 16.68 Z"/><circle cx="24" cy="24" r="7"/>',
'shield':'<path d="M24 5 40 12V27C37 34 32 39 24 44 16 39 11 34 8 27V12Z M17 24 22 30 32 19"/>',
'reject':'<circle cx="24" cy="24" r="18"/><path d="M17 17 31 31 M31 17 17 31"/>',
'user':'<circle cx="24" cy="24" r="22"/><circle cx="24" cy="17" r="9"/><path d="M8 40C8 20 40 20 40 40"/>',
'power':'<path d="M24 3V25 M13 9A18 18 0 1 0 35 9"/>',
'barcode':'<path d="M6 8V41 M10 8V36 M15 8V39 M18 8V36 M22 8V41 M27 8V39 M31 8V36 M35 8V41 M39 8V36 M43 8V41"/>',
}
for name, body in icons.items():
    (BASE/'assets/svg'/f'{name}.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><g fill="none" stroke="#edf5ff" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">{body}</g></svg>')
buttons=[]
def button(name,x,y,w,h,tip):
    buttons.append(f'''<widget class="QPushButton" name="{name}"><property name="geometry"><rect><x>{x}</x><y>{y}</y><width>{w}</width><height>{h}</height></rect></property><property name="text"><string/></property><property name="toolTip"><string>{escape(tip)}</string></property><property name="accessibleName"><string>{escape(tip)}</string></property><property name="cursor"><cursorShape>PointingHandCursor</cursorShape></property><property name="flat"><bool>true</bool></property></widget>''')
for name,x,w in [('units',15,210),('box',234,195),('carton',438,198),('pallet',644,179),('rates',832,263)]:
    button('kpi_'+name,x,83,w,103,'Lihat rincian '+name)
# Stage navigation is intentionally limited to the stage title/icon strip.  The
# data rows remain readable and do not show a full-card hover selector.
for i,(x,w) in enumerate([(26,193),(250,189),(469,175)],1):button('stage_'+str(i),x,237,w,42,'Buka tahap '+str(i))
button('product',664,239,429,168,'Atur produk aktif dan batch')
for i,y in enumerate([414,443,471],1):button('progress_'+str(i),674,y,410,26,'Lihat progres tahap '+str(i))
button('plot',25,587,480,128,'Jelajahi data grafik produksi')
button('total_valid',25,722,156,56,'Lihat aktivitas valid')
button('total_reject',187,722,155,56,'Lihat aktivitas reject')
button('total_duplicate',348,722,156,56,'Lihat aktivitas duplikat')
button('activity',531,578,554,196,'Buka dan cari riwayat aktivitas')
for name,x in [('database',25),('printer',131),('camera',237),('scanner',343),('conveyor',449)]:button('device_'+name,x,837,97,135,'Pengaturan '+name+' • simulasi')
for i,(x,w) in enumerate([(570,118),(697,119),(824,120)],1):button('quick_'+str(i),x,843,w,114,'Buka tahap '+str(i))
button('import',953,843,125,114,'Impor kode dari CSV')
button('sidebar_stats',1115,110,309,99,'Rincian ringkasan agregasi')
button('sidebar_summary',1115,214,309,137,'Rincian total dan status')
button('sidebar_product',1115,358,309,152,'Atur produk aktif dan batch')
button('sidebar_activity',1115,516,309,142,'Buka riwayat aktivitas')
button('sidebar_system',1115,663,309,117,'Informasi sistem dan mode simulasi')
button('account',1115,789,309,95,'Lihat akun operator lokal')
for name,x in [('database',1118),('printer',1180),('camera',1242),('scanner',1304),('logout',1366)]:button('shortcut_'+name,x,925,54,51,'Keluar dari sesi lokal' if name=='logout' else 'Pengaturan '+name)
for i,(name,_,label) in enumerate(ITEMS):
    r=button_rect(i)
    button('nav_'+name,r.x(),r.y(),r.width(),r.height(),label)
button('mode_info',1390,82,32,22,'Mode simulasi lokal • klik untuk detail')
ui='''<?xml version="1.0" encoding="UTF-8"?><ui version="4.0"><class>DashboardControls</class><widget class="QWidget" name="DashboardControls"><property name="geometry"><rect><x>0</x><y>0</y><width>1448</width><height>1086</height></rect></property><property name="styleSheet"><string>QWidget#DashboardControls { background: transparent; } QPushButton { background: transparent; border: 0; border-radius: 6px; } QPushButton:hover { background: rgba(80, 176, 255, 18); border: 0; } QPushButton:focus { background: rgba(80, 176, 255, 28); border: 1px solid rgba(158, 220, 255, 130); } QPushButton:pressed { background: rgba(80, 176, 255, 44); }</string></property>'''+''.join(buttons)+'''<widget class="QComboBox" name="period"><property name="geometry"><rect><x>82</x><y>558</y><width>100</width><height>21</height></rect></property><property name="accessibleName"><string>Periode grafik produksi</string></property><item><property name="text"><string>SHIFT INI</string></property></item><item><property name="text"><string>HARI INI</string></property></item><item><property name="text"><string>SESI LOKAL</string></property></item></widget></widget><resources/><connections/></ui>'''
(BASE/'ui/dashboard.ui').write_text(ui)
print(f'Generated {len(icons)} SVG icons and {len(buttons)} interactive controls.')
