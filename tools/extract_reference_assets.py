"""Extract user-supplied reference artwork; runtime controls remain native Qt widgets."""
from pathlib import Path
from PIL import Image
import numpy as np
import shutil,json
root=Path(__file__).resolve().parents[1]
src=root.parent/'upload';out=root/'pm3tool/ui_assets';out.mkdir(exist_ok=True)
files=['Emerald RFID reader dashboard(1).png','Dark Dump Viewer Interface(1).png','Dark neon RFID clone interface(1).png','Neon write data recycle dashboard(1).png','Proxmark3 Firmware Control Dashboard(1).png','Proxmark3 Recovery Keys Dashboard(1).png','Neon RFID Chip Writing Dashboard(1).png']
images=[Image.open(src/p).convert('RGB') for p in files]
records={}
def crop(name,index,box,transparent=True):
    im=images[index].crop(box)
    if transparent:
        ar=np.array(im).astype(float);a=np.clip((ar.max(2)-100)/85,0,1)
        im=Image.fromarray(np.dstack((ar,np.round(a*255))).astype('uint8'),'RGBA')
    im.save(out/(name+'.png'));records[name]={'source':files[index],'crop':list(box)}
crop('brand',0,(24,3,355,77),False)
for name,i,box in [
 ('nav_reader',2,(44,158,78,192)),('nav_dump',2,(203,158,238,192)),('nav_clone',1,(400,158,438,193)),('nav_edit',1,(574,158,610,193)),('nav_firmware',0,(839,157,878,194)),('nav_key',1,(1020,158,1059,194)),('nav_ink',0,(1236,159,1275,193)),
 ('calendar',6,(724,446,747,468)),('magic',2,(990,230,1033,273)),('target',2,(871,307,918,352)),('clone_copy',2,(310,545,357,593)),('reader_key',0,(286,568,327,609)),('radio',0,(45,224,98,271)),('key',0,(43,445,96,492)),('monitor',0,(44,650,95,694)),('terminal',2,(41,726,95,773)),('file',1,(43,221,91,269)),('layers',2,(42,222,98,276)),('edit',2,(43,495,88,537)),('gear',3,(1029,219,1071,259)),('chip',4,(43,218,96,269)),('ink',6,(42,216,100,275)),
 ('card',2,(918,390,1041,486)),('device',4,(1043,510,1131,598)),('database',5,(443,302,489,352)),('check',5,(64,301,116,354)),('missing',0,(609,923,657,972)),('empty',3,(739,647,800,711)),
 ('monitor_button',0,(199,289,246,333)),('search',0,(677,290,718,334)),('wave',0,(1191,291,1234,334)),('key_button',0,(654,358,697,402)),('file_button',0,(1197,358,1239,404)),('copy',2,(1117,733,1156,766)),('trash',2,(1243,733,1280,766)),('save',2,(1379,733,1417,766)),('folder',2,(1340,944,1386,986)),('play',6,(140,533,164,554)),('stop',6,(916,525,952,560)),('refresh',0,(1358,99,1388,130)),('trace',0,(1044,566,1084,609)),('download',4,(1283,702,1310,733)),('shield',3,(1041,399,1079,437)),('warning',4,(60,283,94,314)),('eye',1,(1344,285,1372,310))]:crop(name,i,box)
# Native Qt nine-slice skins: all nine regions are cropped from unlabeled areas.
def skin(name,index,box,n=10):
    im=images[index];x,y,r,b=box;size=64;dst=Image.new('RGB',(size,size));mid=(x+r)//2
    blank_x=600 if name=='primary' else x+n+2
    blank=im.crop((blank_x,y+n,blank_x+2,b-n)).resize((size-2*n,size-2*n));dst.paste(blank,(n,n))
    patches=[((x,y,x+n,y+n),(0,0,n,n)),((mid,y,mid+8,y+n),(n,0,size-n,n)),((r-n,y,r,y+n),(size-n,0,size,n)),((x,b-n,x+n,b),(0,size-n,n,size)),((mid,b-n,mid+8,b),(n,size-n,size-n,size)),((r-n,b-n,r,b),(size-n,size-n,size,size)),((x,y+12,x+n,y+20),(0,n,n,size-n)),((r-n,y+12,r,y+20),(size-n,n,size,size-n))]
    for source,target in patches:dst.paste(im.crop(source).resize((target[2]-target[0],target[3]-target[1])),target[:2])
    dst.save(out/(name+'.png'));records[name]={'source':files[index],'frame':list(box),'slice':n}
skin('panel',0,(25,210,1513,424))
skin('button',0,(45,283,527,341))
skin('primary',0,(45,561,761,616))
skin('disabled',3,(1321,549,1499,594))
skin('danger',2,(1227,224,1495,279))
skin('field',0,(215,510,1493,550),7)
skin('tab',0,(191,151,383,199),7)
skin('tab_selected',1,(191,151,383,199),7)
# Font files are distributed with their license, for consistent Windows/Linux layout.
for p in ['NimbusSans-Regular.otf','NimbusSans-Bold.otf','NimbusSansNarrow-Regular.otf','NimbusSansNarrow-Bold.otf','NimbusMonoPS-Regular.otf']:
    shutil.copyfile(Path('/usr/share/fonts/opentype/urw-base35')/p,out/p)
license_path=Path('/usr/share/doc/fonts-urw-base35/copyright')
if license_path.exists():shutil.copyfile(license_path,out/'FONT_LICENSE.txt')
(out/'reference_assets.json').write_text(json.dumps(records,indent=2))
# Developer contact sheet, not a runtime screenshot or backing image.
canvas=Image.new('RGB',(750,((len(records)+7)//8)*85),(0,18,27))
from PIL import ImageDraw
p=ImageDraw.Draw(canvas)
for n,k in enumerate(records):
    im=Image.open(out/(k+'.png')).convert('RGBA');im.thumbnail((70,56));x=(n%8)*93;y=(n//8)*85
    canvas.paste(im,(x+5,y+4),im);p.text((x+3,y+64),k,fill='white')
canvas.save(root.parent/'reference-assets.png')
