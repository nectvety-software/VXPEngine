from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from legacy_asset_import import import_legacy_res, load_legacy_catalog
from widgets.asset_editor import AssetEditorDialog


def find_item(dialog: AssetEditorDialog, suffix: str):
    for index in range(dialog.legacy_asset_list.count()):
        item = dialog.legacy_asset_list.item(index)
        target = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if target.endswith(suffix):
            return item
    return None


app = QApplication.instance() or QApplication([])

with tempfile.TemporaryDirectory(prefix="legacy-browser-", dir=ROOT) as td:
    base = Path(td)
    source = base / "old" / "res"
    project = base / "project"
    source.mkdir(parents=True)

    hero = QImage(16, 24, QImage.Format.Format_ARGB32)
    hero.fill(QColor("#d85a7f"))
    assert hero.save(str(source / "hero1.png"))

    bg = QImage(40, 20, QImage.Format.Format_ARGB32)
    bg.fill(QColor("#5e8fb3"))
    assert bg.save(str(source / "bg_01.png"))

    (source / "hero1.ani").write_bytes(b"\x00ANI\xff\x01")
    (source / "theme.mid").write_bytes(b"MThd")

    result = import_legacy_res(source, project)
    assert len(result["assets"]) == 4

    dialog = AssetEditorDialog(project)
    assert dialog.legacy_asset_list.count() == 4

    # Category filter.
    character_index = dialog.legacy_category_filter.findData("character")
    assert character_index >= 0
    dialog.legacy_category_filter.setCurrentIndex(character_index)
    assert dialog.legacy_asset_list.count() == 1
    assert find_item(dialog, "hero1.png") is not None

    # Search spans source, target and metadata.
    dialog.legacy_category_filter.setCurrentIndex(0)
    dialog.legacy_search.setText("hero1")
    assert dialog.legacy_asset_list.count() == 2

    descriptor = find_item(dialog, "hero1.ani")
    assert descriptor is not None
    dialog.legacy_asset_list.setCurrentItem(descriptor)
    app.processEvents()

    assert dialog.legacy_open_button.isEnabled()
    assert not dialog.legacy_preview.pixmap().isNull()
    assert dialog.legacy_pair_label.text().endswith("hero1.png")

    # Edit and persist metadata on the descriptor without touching its bytes.
    original_descriptor = (project / "assets/scenes/characters/hero1.ani").read_bytes()
    dialog.legacy_display_name.setText("Hero Idle Animation")
    dialog.legacy_role.setText("player_idle")
    dialog.legacy_tags.setText("hero, idle, combat, hero")
    dialog.legacy_notes.setPlainText("Imported from legacy MRE resource pack.")
    dialog._legacy_save_metadata()
    app.processEvents()

    catalog = load_legacy_catalog(project)
    row = next(x for x in catalog["assets"] if x["target"].endswith("hero1.ani"))
    assert row["metadata"]["display_name"] == "Hero Idle Animation"
    assert row["metadata"]["role"] == "player_idle"
    assert row["metadata"]["tags"] == ["hero", "idle", "combat"]
    assert row["metadata"]["notes"].startswith("Imported from")
    assert (project / row["target"]).read_bytes() == original_descriptor

    # Search uses edited metadata.
    dialog.legacy_search.setText("player_idle")
    assert dialog.legacy_asset_list.count() == 1

    descriptor = dialog.legacy_asset_list.item(0)
    dialog.legacy_asset_list.setCurrentItem(descriptor)
    dialog._legacy_open_item(descriptor)
    app.processEvents()
    assert dialog.current_source is not None
    assert dialog.current_source.name == "hero1.png"

    # Category metadata edits are reflected in filters and catalog counts.
    dialog.legacy_category_edit.setCurrentIndex(dialog.legacy_category_edit.findData("effect"))
    dialog._legacy_save_metadata()
    app.processEvents()
    catalog = load_legacy_catalog(project)
    row = next(x for x in catalog["assets"] if x["target"].endswith("hero1.ani"))
    assert row["category"] == "effect"
    assert catalog["counts"]["effect"] == 1

    dialog.close()

print("VXPE_LEGACY_BROWSER_EDITOR_PASS")
