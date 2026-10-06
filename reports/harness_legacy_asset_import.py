from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from legacy_asset_import import import_legacy_res

def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

with TemporaryDirectory(prefix='vxpe-legacy-import-') as td:
    base=Path(td); src=base/'old'/'res'; project=base/'project'
    write(src/'bg_01.png', b'BG')
    write(src/'hero1.gif', b'GIF')
    write(src/'hero1.ani', b'\x00ANI\xff')
    write(src/'boss1.gif', b'BOSS')
    write(src/'boss1.ani', b'\x01BANI')
    write(src/'fire.gif', b'FIRE')
    write(src/'coin0.png', b'COIN')
    write(src/'menu_bg.gif', b'MENU')
    write(src/'stage.map', b'MAP')
    write(src/'theme.mid', b'MIDI')
    result=import_legacy_res(src, project)
    assert len(result['assets'])==10
    assert (project/'assets/scenes/backgrounds/bg_01.png').read_bytes()==b'BG'
    assert (project/'assets/scenes/characters/hero1.gif').read_bytes()==b'GIF'
    assert (project/'assets/scenes/characters/hero1.ani').read_bytes()==b'\x00ANI\xff'
    assert (project/'assets/scenes/bosses/boss1.ani').read_bytes()==b'\x01BANI'
    assert (project/'assets/scenes/effects/fire.gif').is_file()
    assert (project/'assets/scenes/items/coin0.png').is_file()
    assert (project/'assets/ui/menu_bg.gif').is_file()
    assert (project/'assets/map/legacy/stage.map').is_file()
    assert (project/'assets/audio/theme.mid').is_file()
    catalog=json.loads((project/'assets/legacy/legacy_assets.catalog.json').read_text(encoding='utf-8'))
    assert 'source_path_hint' not in catalog
    hero_ani=next(x for x in catalog['assets'] if x['source']=='hero1.ani')
    assert hero_ani['paired_asset']=='assets/scenes/characters/hero1.gif'
print('VXPE_LEGACY_ASSET_IMPORT_PASS')
