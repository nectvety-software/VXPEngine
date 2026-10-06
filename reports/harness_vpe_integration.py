"""Verify embedded editing and native animation transfer without touching user assets."""
from pathlib import Path
import tempfile
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
from PySide6.QtGui import QColor,QImage
from PySide6.QtWidgets import QApplication
from vendor.vpe_pixel.vpx_editor.vpea import encode_vpea
from vendor.vpe_pixel.vpx_editor.vpe import encode_vpe
from widgets.asset_editor import AssetEditorDialog

app=QApplication.instance() or QApplication([])
with tempfile.TemporaryDirectory(prefix='vpe-bridge-') as td:
    root=Path(td).resolve();(root/'assets/scenes').mkdir(parents=True)
    editor=AssetEditorDialog(root)
    original_size=editor.canvas.image.size()
    app_qss=app.styleSheet();app_palette=app.palette()
    native=root/'sample.vpe';native.write_bytes(encode_vpe(2,2,[65535,0xf800,0x07e0,0x001f]))
    animation=root/'sample.vpea';animation.write_bytes(encode_vpea(2,2,[[65535,0xf800,0x07e0,0x001f],[0,1,2,3]],140,False))
    original=animation.read_bytes()
    editor.load_image(animation)
    assert editor.workspace_tabs.currentIndex()==1
    backend=editor.vpe_pixel.editor
    assert not backend.isWindow() and app.styleSheet()==app_qss and app.palette()==app_palette
    backend._toggle_theme()
    assert app.styleSheet()==app_qss and app.palette()==app_palette
    backend._toggle_theme()
    assert backend._doc.frame_count()==2
    assert all(not a.isEnabled() for a in editor._asset_shortcut_actions)
    editor.vpe_pixel.white_alpha.setChecked(True)
    editor.vpe_pixel.receive_document()
    assert editor.workspace_tabs.currentIndex()==0 and len(editor.scene_frames)==2
    assert editor.scene_frames[0].duration_ms==140
    assert editor.scene_frames[0].image.pixelColor(0,0).alpha()==0
    assert editor.scene_frames[0].image.pixelColor(1,0).red()==255
    assert not editor.animation_loop.isChecked()
    assert all(a.isEnabled() for a in editor._asset_shortcut_actions)
    assert animation.read_bytes()==original
    editor._send_to_vpe_pixel()
    assert backend._doc.frames[0][0]==65535 and backend._doc.frame_count()==2
    assert backend._doc.delay_ms==140 and not backend._doc.loop
    backend._doc.dirty=False
    editor.undo()
    assert editor.canvas.image.size()==original_size and not editor.scene_frames
    editor.redo()
    assert len(editor.scene_frames)==2 and not editor.animation_loop.isChecked()
    editor.undo()
    editor.load_image(native)
    editor.vpe_pixel.white_alpha.setChecked(False);editor.vpe_pixel.receive_document()
    assert editor.canvas.image.pixelColor(0,0).alpha()==255 and not editor.scene_frames
    editor.asset_name.setText('received.png');editor.initial_destination='assets/scenes'
    editor._apply_initial_destination('assets/scenes');editor.write_animation.setChecked(False)
    editor.save_and_apply()
    assert editor.saved_path and editor.saved_path.is_relative_to(root/'assets')
    assert QImage(str(editor.saved_path)).size()==editor.canvas.image.size()
    assert native.read_bytes()==encode_vpe(2,2,[65535,0xf800,0x07e0,0x001f])
    editor.reject()
    multi=AssetEditorDialog(root)
    multi.load_image(animation)
    multi.save_and_apply()  # Host footer saves the active VPE document directly.
    assert multi.saved_path and multi.saved_path.is_relative_to(root/'assets')
    descriptor=root/'assets/scenes/sample.ani..dtfe'
    payload=__import__('json').loads(descriptor.read_text(encoding='utf-8'))
    assert len(payload['frames'])==2 and not payload['animation']['loop']
    assert all(frame['duration_ms']==140 for frame in payload['frames'])
    assert (root/payload['texture']).is_file() and animation.read_bytes()==original
    multi.reject()
print('PASS: embedded UI/theme, native VPE/VPEA, alpha choice, animation transfer, undo, project save, originals unchanged')
