"""Headless editor integration, persistence and invalid-input checks."""
import os, sys, tempfile
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"app"))
from PySide6.QtWidgets import QApplication
from story_hud import load, save, DEFAULT, preview
from widgets.story_hud_panel import StoryHudPanel
app=QApplication.instance() or QApplication([])
with tempfile.TemporaryDirectory() as folder:
    root=Path(folder);panel=StoryHudPanel(root)
    panel.fields["title"].setText('MY "GAME"')
    panel.fields["alpha"].setValue(200)
    panel.label_fields[0].setText("WALK")
    panel.save_project()
    result=load(root)
    assert result["title"]=='MY "GAME"' and result["alpha"]==200
    assert result["labels"][0]=="WALK"
    header=(root/"src/story_hud_generated.h").read_text()
    assert 'story_hud_style' in header and 'story_hud_labels' in header
    assert load(root)==StoryHudPanel(root).data()
    for size in ((240,320),(320,240)):
        im=preview(result,size);assert im.size==size
        assert im.getpixel((0,43))!=im.getpixel((0,100))
    before=(root/"assets/ui/story_hud.json").read_bytes()
    try:save(root,{**result,"title":chr(0x1f600)})
    except ValueError:pass
    else:raise AssertionError("Non-ASCII input must be rejected")
    assert before==(root/"assets/ui/story_hud.json").read_bytes()
print("PASS: Story HUD editor preview, save/reload, header export, both viewports, input validation")
