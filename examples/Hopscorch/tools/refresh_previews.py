from pathlib import Path
import sys
from PySide6.QtGui import QImage,QPainter,QColor
root=Path(__file__).resolve().parents[1]
source=Path(sys.argv[1]) if len(sys.argv)>1 else root.parents[1]/'reports/hopscorch_reference'
canvas=QImage(960,640,QImage.Format.Format_RGB32);canvas.fill(QColor('#151b22'));paint=QPainter(canvas)
for i,name in enumerate(['splash','menu','play','menu_vi','guide','abouts','settings','exit']):
    image=QImage(str(source/(name+'.ppm')));assert (image.width(),image.height())==(240,320)
    image.save(str(root/'docs'/(name+'.png')));paint.drawImage((i%4)*240,(i//4)*320,image)
paint.end();canvas.save(str(root/'docs/preview.png'))
