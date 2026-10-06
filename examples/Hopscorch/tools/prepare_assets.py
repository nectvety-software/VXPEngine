"""Compile local art and Unicode labels to self-contained RGB565/bitmaps."""
from pathlib import Path
import json
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QFont, QFontMetrics, QFontDatabase
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
app = QApplication.instance() or QApplication([])
font_file = Path('C:/Windows/Fonts/segoeui.ttf')
font_id = QFontDatabase.addApplicationFont(str(font_file))
if font_id < 0: raise RuntimeError('Install Segoe UI to regenerate labels (compiled labels are included).')
font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
english = ['Play','Language','Guide','Abouts','Settings','Exit',
    'A little seaside adventure','Fish','5: Cast / reel   Back: Menu',
    'BITE! Press 5 to reel!', 'Arrows or 2/4/6/8: move', '5 / OK: cast your fishing line',
    'Wait for the golden bobber', 'Press 5 during BITE to catch', 'Back: return to the menu',
    'Original fishing demo', 'Water effects', 'Walk speed', 'On','Off','Fast','Slow',
    'Leave Hopscorch?', 'Yes, exit','No, stay','Back: Menu   OK: Select']
vietnamese = ['Chơi','Ngôn ngữ','Hướng dẫn','Giới thiệu','Cài đặt','Thoát',
    'Một chuyến phiêu lưu bên biển','Cá','5: Thả / kéo   Back: Menu',
    'CÁ CẮN! Bấm 5 để kéo!', 'Phím hướng hoặc 2/4/6/8: đi', '5 / OK: thả dây câu xuống nước',
    'Chờ phao chuyển sang màu vàng', 'Bấm 5 khi CÁ CẮN để bắt cá', 'Back: trở về màn hình chính',
    'Dự án mẫu câu cá', 'Hiệu ứng nước', 'Tốc độ đi', 'Bật','Tắt','Nhanh','Chậm',
    'Thoát Hopscorch?', 'Có, thoát','Không, ở lại','Back: Menu   OK: Chọn']
keys=['PLAY_ITEM','LANG','GUIDE','ABOUTS','SET','QUIT','SUBTITLE','FISH','PLAY_HINT','BITE',
      'HELP1','HELP2','HELP3','HELP4','HELP5','ABOUT_NOTE','EFFECTS','SPEED','ON','OFF','FAST','SLOW','EXIT_QUESTION','YES','NO','BACK_HINT']
special=[('TITLE','HOPSCORCH',26),('TITLE_SMALL','HOPSCORCH',15),('BRAND','VXPstore',12),
         ('COPYRIGHT','© VXPstore. All rights reserved.',11),
         ('COPYRIGHT_SMALL','© VXPstore. All rights reserved.',9),
         ('WEBSITE','Website: qeafivels.com',12),('EN_NAME','English',14),('VI_NAME','Tiếng Việt',14)]
lines=['#pragma once','#include <stdint.h>','enum TextKey {'+','.join(f'{k}={i}' for i,k in enumerate(keys))+'};',
       'enum { EN_BASE=0, VI_BASE=26, '+','.join(f'{name}={52+i}' for i,(name,_,_) in enumerate(special))+' };',
       'struct Label { int w,h; const uint8_t* bits; };']
all_text=[(t,10 if i in (8,25) else 12) for i,t in enumerate(english)]+[(t,10 if i in (8,25) else 12) for i,t in enumerate(vietnamese)]+[(t,s) for _,t,s in special]
dims=[]
for i,(text,size) in enumerate(all_text):
    font=QFont(font_family);font.setPixelSize(size);font.setBold(i in (52,53))
    limit=208
    if i<52 and i%26<6:limit=108
    fm=QFontMetrics(font)
    while fm.horizontalAdvance(text)+2>limit and font.pixelSize()>5:
        font.setPixelSize(font.pixelSize()-1);fm=QFontMetrics(font)
    w=fm.horizontalAdvance(text)+2;h=fm.height()+2
    assert w<=212,(text,w)
    image=QImage(w,h,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.transparent)
    p=QPainter(image);p.setFont(font);p.setPen(QColor('white'));p.setRenderHint(QPainter.RenderHint.TextAntialiasing,False);p.drawText(1,1+fm.ascent(),text);p.end()
    bits=bytearray((w*h+7)//8)
    for y in range(h):
        for x in range(w):
            if image.pixelColor(x,y).alpha()>=100:bits[(y*w+x)//8]|=128>>((y*w+x)%8)
    lines.append(f'static const uint8_t text_{i}[]={{'+','.join(map(str,bits))+'};');dims.append((w,h))
lines.append('static const Label labels[]={'+','.join(f'{{{w},{h},text_{i}}}' for i,(w,h) in enumerate(dims))+'};')
(ROOT/'src/labels.h').write_text('\n'.join(lines),encoding='utf-8')
(ROOT/'assets/localization.json').write_text(json.dumps({'en':dict(zip(keys,english)),'vi':dict(zip(keys,vietnamese)),
    'copyright':'© VXPstore. All rights reserved.','website':'https://qeafivels.com/?utm_source=chatgpt.com'},ensure_ascii=False,indent=2),encoding='utf-8')
source=QImage(str(ROOT/'assets/sprites/seaside.png'))
if source.isNull():raise RuntimeError('Missing seaside.png')
source=source.scaledToHeight(320,Qt.TransformationMode.FastTransformation)
source=source.copy(85,0,240,320)
source.save(str(ROOT/'assets/sprites/seaside_qvga.png'))
pixels=[]
for y in range(320):
    for x in range(240):
        c=source.pixelColor(x,y);pixels.append(((c.red()>>3)<<11)|((c.green()>>2)<<5)|(c.blue()>>3))
(ROOT/'src/art.h').write_text('#pragma once\n#include <stdint.h>\nstatic const uint16_t background[76800]={\n'+
    ',\n'.join(','.join(map(str,pixels[i:i+240])) for i in range(0,len(pixels),240))+'\n};\n',encoding='ascii')
print('Compiled QVGA scene and 60 Unicode labels')
