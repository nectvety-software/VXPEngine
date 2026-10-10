# Vaelora lane prototype

Native viewport 240x320; world 240x960. 2468 move, 5/7/9/0 cast, 1 recover, * pause. Menu 7 toggles player palette skin, 9 bot palette skin; 4/6 hero and 2/8 bot. Each hero has two cosmetic palettes, identical stats. These are palette variants, not additional illustrated costumes.

Each side owns outer tower (900 HP), inner tower (900 HP), core (1800 HP). Protected structures ignore damage until the preceding tower falls. Automatic basic attacks prioritize a nearby hero then reachable structures. Towers fire every 1.2 seconds within range. Defeated heroes respawn at home after five seconds; home regenerates HP/mana. Destroy the enemy core to win. Five-minute timeout compares core HP. Bot fights nearby heroes, recovers when injured, and pushes the next unlocked structure when no live hero is nearby.

Velin: prism projectile, nearby burst, binding projectile, area nova; every third cast grants shield. Torvan: hammer arc, iron shield, forward charge with stun, earthquake stun; passive armor. Nimara: slowing arrow, retreat dash/shield, binding arrow, area arrow storm; movement restores extra mana. Each of the twelve skills now has a distinct cast/movement animation; projectile skills also have separate flight and hit effects. Dash trails use actual collision-limited endpoints; guard follows the caster and bindings only appear on a successful hit. Skins tint cast, projectile and impact visuals. See SKILL_EFFECTS.md and the animated comparison in tests/runtime_screenshots/skill_fx.

Artwork remains original Vaelora art. Terrain uses an original stone-and-grass ground tile across the scrolling world. Twenty-three placed environment objects (walls, huts, trees, grass and ruins) scroll with the camera. World placements and foot colliders are editable in assets/gameplay/world.json; tools/generate_world.py emits runtime geometry. Walls, trees, huts and live structures block walking and dashes; tall grass is passable. Movement resolves axes separately to slide along walls; dashes sweep each pixel. Bot steering detours around lane structures. Depth sorting places characters behind/in front of environment according to feet position. Structures now use original generated pixel sprites with blue/red teams and separate tower/core rubble; HUD uses 12 dedicated skill icons. See COMBAT_ARTWORK_PROMPTS.md. Minion waves, siege carts, gold farming and equipment are now implemented; see LANE_WARFARE.md. Lane JSON is descriptive editor metadata; runtime constants reside in scene.cpp.

## Reference sources

YouTube solo video located through search (title/description inspected; footage not watched): [Anhhao – Solo 1v1](https://www.youtube.com/watch?v=VZFK4cTEinc).
Official [1v1 mode](https://lienquan.garena.vn/hoc-vien/che-do-choi/d/1v1-pvp-thanh-pho-den/) and [game modes](https://lienquan.garena.vn/hoc-vien/che-do-choi/d/) provide broad mode/objective references. Original mechanics above are prototype design choices, not a claim of reproducing exact Arena of Valor rules.

World placement JSON drives runtime constants through build generation; lane.json remains descriptive metadata. Environment source art and generation prompts are recorded in ENVIRONMENT_ARTWORK_PROMPTS.md.

Validation: host combat/collision regression passes, including wall sliding, walkable grass, swept charge/retreat dash, bot detour and pushing, destroyed tower passage, and framebuffer guards. Actual ARM VXP passes VXPEmu at 240x320 with eight captures including a held movement/scroll capture and ground pixel parity.
