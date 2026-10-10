"""Create the slightly wider condensed font used by the reference presentation.
The source URW font license and font exception are bundled in ui_assets.
"""
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
assets=Path(__file__).resolve().parents[1]/'pm3tool/ui_assets'
for style in ('Regular','Bold'):
    f=TTFont(assets/f'NimbusSansNarrow-{style}.otf');glyphset=f.getGlyphSet();top=f['CFF '].cff.topDictIndex[0];factor=1.12
    for name in f.getGlyphOrder():
        width,lsb=f['hmtx'].metrics[name];pen=T2CharStringPen(round(width*factor),glyphset)
        glyphset[name].draw(TransformPen(pen,(factor,0,0,1,0,0)))
        top.CharStrings[name]=pen.getCharString(private=top.Private,globalSubrs=f['CFF '].cff.GlobalSubrs)
        f['hmtx'].metrics[name]=(round(width*factor),round(lsb*factor))
    for name in ('advanceWidthMax','minLeftSideBearing','minRightSideBearing','xMaxExtent'):
        setattr(f['hhea'],name,round(getattr(f['hhea'],name)*factor))
    family='PM3 Reference Sans';postscript='PM3ReferenceSans-'+style
    for name_id,value in [(1,family),(2,style),(3,postscript),(4,family+' '+style),(6,postscript),(16,family),(17,style)]:
        for platform,encoding,lang in [(3,1,0x409),(1,0,0)]:f['name'].setName(value,name_id,platform,encoding,lang)
    top.FamilyName=family;top.FullName=family+' '+style;f['CFF '].cff.fontNames=[postscript]
    f.save(assets/(postscript+'.otf'))
