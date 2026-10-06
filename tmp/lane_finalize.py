from pathlib import Path
import json
p=Path('examples/FoxRiftDemo/src/scene.cpp');s=p.read_text().replace('dist(f,fighters[0])','dist(fighters[i],fighters[0])');s=s.replace('r=12+(650-e.life)/14','r=8+e.skill*5+(650-e.life)/(18-e.skill*2)');p.write_text(s)
p=Path('examples/FoxRiftDemo/tests/vxpemu_smoke.cpp');s=p.read_text().replace('source=expected.pixel(x,y)','source=expected.pixel(x,(y+560)%320)');p.write_text(s)
r=Path('examples/FoxRiftDemo');(r/'assets/gameplay/lane.json').write_text(json.dumps({'viewport':[240,320],'world':[240,960],'respawn_ms':5000,'time_limit_ms':300000,'structure_hp':{'tower':900,'core':1800},'unlock_order':['outer_tower','inner_tower','core'],'skins':{'Velin':['Prism','Frost Prism'],'Torvan':['Copper','Obsidian'],'Nimara':['Wind','Sunset']},'skin_type':'cosmetic RGB565 palette tint, no stat changes'},indent=2))
(r/'docs/LANE_AND_SKINS.md').write_text('''# Vaelora lane prototype

Native viewport 240x320; world 240x960. 2468 move, 5/7/9/0 cast, 1 recover, * pause. Menu 7 toggles player palette skin, 9 bot palette skin; 4/6 hero and 2/8 bot. Each hero has two cosmetic palettes, identical stats. These are palette variants, not additional illustrated costumes.

Each side owns outer tower (900 HP), inner tower (900 HP), core (1800 HP). Protected structures ignore damage until the preceding tower falls. Automatic basic attacks prioritize a nearby hero then reachable structures. Towers fire every 1.2 seconds within range. Defeated heroes respawn at home after five seconds; home regenerates HP/mana. Destroy the enemy core to win. Five-minute timeout compares core HP. Bot fights nearby heroes, recovers when injured, and pushes the next unlocked structure when no live hero is nearby.

Velin: prism projectile, nearby burst, binding projectile, area nova; every third cast grants shield. Torvan: hammer arc, iron shield, forward charge with stun, earthquake stun; passive armor. Nimara: slowing arrow, retreat dash/shield, binding arrow, area arrow storm; movement restores extra mana. Effects use hero-specific prism shards, ground shock lines and falling arrow streaks. Skill index controls visual radius and expansion speed; skins tint both hero and effects.

Artwork remains original Vaelora art. Terrain currently repeats the existing original tile across the scrolling world. Structures use original code-drawn pixel shapes. This prototype has no minion waves, shop or equipment yet. Lane JSON is descriptive editor metadata; runtime constants reside in scene.cpp.

## Reference sources

YouTube solo video located through search (title/description inspected; footage not watched): [Anhhao – Solo 1v1](https://www.youtube.com/watch?v=VZFK4cTEinc).
Official [1v1 mode](https://lienquan.garena.vn/hoc-vien/che-do-choi/d/1v1-pvp-thanh-pho-den/) and [game modes](https://lienquan.garena.vn/hoc-vien/che-do-choi/d/) provide broad mode/objective references. Original mechanics above are prototype design choices, not a claim of reproducing exact Arena of Valor rules.
''',encoding='utf-8')
