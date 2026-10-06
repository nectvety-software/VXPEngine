"""Editor persistence and per-pixel parity against the C renderer."""
import os,sys,tempfile,struct
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"app"))
from PySide6.QtWidgets import QApplication
from PIL import Image
from pixel_fonts import load,save,draw,rgb565,style,preset
from widgets.font_styles_panel import FontStylesPanel
app=QApplication.instance() or QApplication([])
with tempfile.TemporaryDirectory() as folder:
    root=Path(folder);panel=FontStylesPanel(root)
    panel.theme.setCurrentText("Rune Violet");panel.apply_theme()
    panel.role.setCurrentText("numbers");panel.fields["spacing"].setValue(2);panel.save_project()
    data=load(root);assert data["title"]["color565"]==preset("Rune Violet")["title"]["color565"]
    assert data["numbers"]["spacing"]==2
    assert load(root)==FontStylesPanel(root).styles
    assert 'vaelora_font_numbers' in (root/"src/font_styles_generated.h").read_text()
    old=(root/"assets/ui/font_styles.json").read_bytes()
    data["body"]["scale"]=0
    try:save(root,data)
    except ValueError:pass
    else:raise AssertionError('Invalid scale accepted')
    assert old==(root/"assets/ui/font_styles.json").read_bytes()
if len(sys.argv)>1:
    p=Path(sys.argv[1]);actual=list(struct.unpack('<'+'H'*(240*320),p.read_bytes()))
    im=Image.new('RGB',(240,320),rgb565(0x0862))
    s=style(0,0xC59F,7);draw(im,9,11,'Vale UI: Aa Bb 0123456789',s)
    s.update(font_id=1,scale=2,color565=0xEDEB);draw(im,10,44,'VAELORA',s)
    s.update(font_id=2,scale=1,spacing=0,effects=1,color565=0x57F7);draw(im,12,91,'1100/1100  01:29',s)
    s.update(font_id=0,scale=3,spacing=2,effects=3);draw(im,-7,130,'Clipped\n?7',s,(13,141,104,50))
    expected=list(im.get_flattened_data());assert all(rgb565(c)==pixel for c,pixel in zip(actual,expected))
    print('PASS: 76,800 pixel parity between Editor font preview and C renderer')
print('PASS: Font Styles role/theme editing, save/reload, header export and validation')
