"""Generate identical core/editor bitmap fonts from authored pixel sources."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    core=ROOT if (ROOT/"fonts/vaelora.json").exists() else ROOT/"engine/coremre"
    source=core/"fonts/vaelora.json"
    faces=json.loads(source.read_text())["faces"];compiled=[]
    header=['#pragma once','// Generated from fonts/vaelora.json; no external font dependency.']
    for index,f in enumerate(faces):
        rows=[];widths=[]
        for code in range(32,127):
            pattern=f["glyphs"][chr(code)].split('/')
            if len(pattern)!=f["height"] or any(len(r)!=len(pattern[0]) or set(r)-{'0','1'} for r in pattern):raise ValueError('Invalid bitmap')
            width=f["width"] if f["fixed"] else len(pattern[0])
            if width>f["width"]:raise ValueError('Glyph too wide')
            widths.append(width)
            rows.extend(int(r.ljust(f["width"],'0'),2) for r in pattern)
        compiled.append(dict(name=f["name"],width=f["width"],height=f["height"],widths=widths,rows=rows))
        header.append('static const uint8_t font_rows_'+str(index)+'[]={'+','.join(map(str,rows))+'};')
        header.append('static const uint8_t font_widths_'+str(index)+'[]={'+','.join(map(str,widths))+'};')
    p=core/"src/graphics/PixelFontData.inc";p.write_text('\n'.join(header)+'\n')
    if (ROOT/"app").is_dir():
        (ROOT/"app/pixel_font_data.py").write_text('# Generated from engine/coremre/fonts/vaelora.json\nFONTS = '+repr(compiled)+'\n')
    print('Generated 3 bitmap faces / 285 ASCII glyphs for core and editor')
if __name__=='__main__':main()
