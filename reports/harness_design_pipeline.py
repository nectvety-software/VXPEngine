"""Harness: scene_bindings.h (bảng component) + xuất sprite .raw từ thiết kế."""
import os, sys, struct, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage

app = QApplication([])

from project_store import ProjectStore
from scene_screen_store import ScreenStore

with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)
    store = ProjectStore()
    project = store.create_project("HarnessDesign", str(tmp_path))
    root = project.folder

    # Tạo ảnh asset 8x4 đỏ RGB565 thuần (opaque) trong project.
    asset_dir = root / "assets" / "map" / "texture"
    asset_dir.mkdir(parents=True, exist_ok=True)
    img = QImage(8, 4, QImage.Format.Format_ARGB32)
    img.fill(0xFFFF0000)
    asset_path = asset_dir / "hero.png"
    assert img.save(str(asset_path))

    # Ghi scene Main với 2 component: 1 sprite + 1 hình chữ nhật, có rotation.
    scene_path = root / "assets" / "scenes" / "main.dtfe"
    scene_path.parent.mkdir(parents=True, exist_ok=True)
    import json
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    scene["children"] = [
        {
            "id": "n1", "name": "Hero", "code_name": "Hero", "type": "Sprite2D",
            "asset": "assets/map/texture/hero.png",
            "position": [10, -20], "rotation": 45.0, "scale": [1, 1],
            "display_size": [16, 8], "z_index": 2, "visible": True,
            "opacity": 1, "blend_mode": "Normal", "tint": "#FFFFFFFF",
            "events": [], "automation": {}, "clipping_mask": {},
        },
        {
            "id": "n2", "name": "Wall", "code_name": "Wall", "type": "Rectangle2D",
            "asset": "", "position": [0, 0], "rotation": 0.0, "scale": [1, 1],
            "display_size": [40, 12], "z_index": 1, "visible": True,
            "opacity": 1, "blend_mode": "Normal", "tint": "#FFFFFFFF",
            "events": [], "automation": {}, "clipping_mask": {},
        },
    ]
    scene_path.write_text(json.dumps(scene, indent=2), encoding="utf-8")

    screens = ScreenStore(root)
    out = screens.generate_c_bindings()
    header = out.read_text(encoding="utf-8")
    assert "VXP_DESIGN_ACTIVE_COUNT" in header
    assert "VXP_DESIGN_ACTIVE_HAS_DESIGN" in header
    assert "MAIN_COMPONENT_COUNT 2" in header, header[:2000]
    assert "MAIN_HAS_DESIGN 1" in header
    assert "VxpDesignComponent MAIN_DESIGN_COMPONENTS[2]" in header
    assert "z_index: 1" in header.split("z_index: 2")[0], "bảng phải sắp theo z_index"
    hero_res = [line for line in header.splitlines() if "_RES " in line and "hero" in line.lower()]
    assert hero_res, "thiếu define _RES cho component có ảnh"
    res_name = hero_res[0].split('"')[1]
    print("OK  scene_bindings.h có bảng component + RES:", res_name)

    rows = screens.last_component_rows
    assert len(rows) == 2 and any(r["res"] == res_name for r in rows)

    from design_export import export_design_sprites
    exported = export_design_sprites(root)
    assert exported == 1, exported
    raw = root / "resources" / "gen" / res_name
    assert raw.exists()
    blob = raw.read_bytes()
    w = blob[0] | (blob[1] << 8)
    h = blob[2] | (blob[3] << 8)
    opaque = blob[4]
    # Xoay 45°: canvas đường chéo ~ hypot(16,8)+2 = 20
    assert w >= 16 and h >= 8, (w, h)
    assert opaque == 0, opaque  # rotation sinh góc trong suốt → sprite có mask
    assert len(blob) == 8 + w * h * 2 + (w * h + 7) // 8, len(blob)
    mask = blob[8 + w * h * 2:]
    red_found = False
    for o in range(w * h):
        if mask[o >> 3] & (0x80 >> (o & 7)):
            px = blob[8 + o * 2] | (blob[9 + o * 2] << 8)
            if (px >> 11) >= 28:
                red_found = True
                break
    assert red_found, "không tìm thấy pixel đỏ trong vùng mask"
    print(f"OK  sprite .raw đã xuất: {w}x{h} opaque={opaque} ({len(blob)} byte)")

    # Xóa component ảnh → lần xuất sau phải dọn file cũ.
    scene["children"] = scene["children"][1:]
    scene_path.write_text(json.dumps(scene, indent=2), encoding="utf-8")
    screens.generate_c_bindings()
    exported2 = export_design_sprites(root)
    assert exported2 == 0 and not raw.exists(), "sprite cũ chưa được dọn"
    print("OK  sprite design cũ được dọn khi không còn trong thiết kế")

    try:
        store.remove(project.path)
    except Exception:
        pass

print("PASS_ALL")
