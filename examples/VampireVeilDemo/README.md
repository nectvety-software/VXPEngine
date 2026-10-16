# Vampire Veil: Night Hunt — VXPEngine action-2D sample game

A Symphony-of-the-Night style side-scroller for MRE VXP handsets (240x320,
Nokia 225/220 portrait), rebuilt from the reference trailer frame by frame:
three wrapped pine bands sliding at different rates under a moon, a 16-px
tilemap whose walkable lip is a continuous golden cobble seam broken by magenta
moss, a cloak-wearing hunter who opens a red whip crescent in front of his own
hitbox, bats/imps/owls that die into soul motes, a hooded villager who mends and
saves, and a stone Warden in the far court with a name plate of its own. The HUD
is the reference's layout: round portrait plate, heart row, MP gauge, corner
room minimap, soul counter under it.

This project exists to be the read-order proof for the `action2d` core. Its
guide is `docs/CORE_ACTION2D.md`.

## The one rule the sample is built around

Everything above the framebuffer is one of six core modules — nothing else:

| module | what the game uses it for |
| --- | --- |
| `VxpTilemap2D` | both tile layers and every collision query |
| `VxpCamera2D` | two-axis follow, lookahead bias, deterministic shake |
| `VxpBody2D` | run/jump/coyote/one-way/ladder/hazard movement |
| `VxpCombat2D` | whip swings, i-frames, hit-stop, enemy projectiles |
| `VxpHud2D` | plate, portrait, hearts, gauge, boss plate, minimap |
| `VxpInputMap2D` | handset codes and pen taps become named action edges |

There is no per-module glue. `src/main.c` (70,558 bytes, 1,782 lines) owns only
data — the level tables, the entity pools, the drawing order — which is the
point: if the core were missing a primitive the game needs, that need would
show up as hand-written physics in this file instead.

Zero heap for the whole game: the tilemap is three `uint16_t[128*24]` arrays
(ground cells, ledge cells, one shared flag array) plus `uint8_t` room and
surface arrays, all static.

## Asset model: one generator, baked RGB565 + 1-bit masks

`tools/generate_vampireveil_assets.py` (50,403 bytes) rasterises everything into
`src/assets_gen.h` (294,028 bytes):

- **`VV_TILE 16`**, one ground atlas `VV_ATLAS` of **8x1 cells**, opaque, drawn
  through the `copy_tile` fast path, and one ledge atlas `VV_ATLAS2` of **4x2
  cells** carrying a 256-byte MSB-first mask so a slab is solid to the mover and
  transparent to the blitter.
- **`VV_NSPRITE = 35`** masked sprites: the hunter's run/jump/whip/climb poses,
  bat/imp/owl/Warden frames, three parallax bands, the moon, lamp/fence/grave/
  statue props, coin/orb/soul loot, heart + empty heart, whip crescent and the
  hit sparks.
- Colours are sampled from the reference frames, not from memory — `C_GOLD`
  `vxpe2d_rgb565(232,196,92)` is the cobble seam, `C_BLOOD` (176,40,48) the whip
  and the hearts, `C_MP` (96,170,226) the gauge.
- Cell 0 of each atlas is never drawn, so tile id 0 means "air" without a
  special case in the blitter.

## Stage authoring: a column list, not a tile editor

The map is **128x24 tiles = 2048x384 px**, and the whole layout is literal
column tables so a level edit is a data edit:

- `GROUND_RUNS[]` — **14** runs of `{c0, c1, top}`. A column is solid from `top`
  down to the floor, so the walkable plane is always the top tile's upper edge —
  the same row `VxpBody2D` resolves against. Columns whose top sits below
  `PLANE_ROW 15` (y 240) read as holes in the forest floor and get a void rect
  and a cold lip instead of flat sky.
- `HAZARD_RUNS[]` — **2** runs (the spike trench at cols 52-55, the chasm floor
  at 90-92). The hazard word lives on the floor tile, so standing anywhere in it
  bleeds; `VxpBody2D` never treats `HAZARD` as blocking, only `SOLID` does.
- `LEDGES[]` — **9** one-way slabs, each authored as left cap / middle / right
  cap on the masked atlas.
- `LADDERS[]` — **3** climbs, including the one out of the spike trench.
- `PROPS[]` **21**, `SPAWNS[]` **12** (5 bats, 4 imps, 3 owls), `LOOT[]` **8**,
  all anchored to their own column's plane so decor follows the terrace it
  stands on.

Combatants live in `MAX_ACT 14` static slots — 0 the hero, 1..12 the stage, 13
the Warden (`enemy_spawn(WARDEN_SLOT, EN_WARDEN, 122, PLANE_ROW - 3)` in the
court at cols 120-127) — with `MAX_ITEM 20` pickups, `MAX_FX 48` effects and the
core's 24-slot projectile pool (`VXPE_PROJ_POOL2D_MAX`, `VxpCombat2D.h:153`).
The minimap is the same map at 4x4-tile rooms: `ROOMS_W 32` x `ROOMS_H 6`.

## Movement and combat

Physics is Q8.8 with no divide and no FPU. `vxpe_body_tuning_default()` is
overridden per archetype:

- **hero** — run 104 px/s, accel 1080, friction 920, air accel 640, gravity 660,
  jump 240 with an 80 px/s cut, fall max 288, wall slide 46, climb 62, coyote
  95 ms, jump buffer 120 ms, step down 14 px.
- **imp** — run 52, accel 420, friction 520, air accel 260, jump and climb
  zeroed, coyote and buffer 0, step up 16 / step down 10.
- **owl/bat** — a zeroed table (gravity 0), so a flier is a body with nothing
  tuned, not a second movement code path.

Five `VxpeAttack2D` literals cover everything. The whip
`ATK_WHIP = {8,6,26,14, 70,130,190, 2, 150<<8, -(34<<8), 640, 70, 150, 1, 0}`
is 70 ms windup, 130 ms active, 190 ms recovery — 390 ms per swing, 2 damage
against bat 4 / owl 6 / imp 8 / Warden 40 HP, hero 8 hearts, knockback +150
px/s plus -34 px/s lift. `off_x` reads from the owner's box and mirrors with
facing (`out->x = facing ? bx + off_x : bx + body->w - off_x - w`), which is why
every swing stays in front of the body it belongs to after a turn. The Warden's
`ATK_SLAM` is a 34x36 box at `-6, 2` with 2 damage and 170 px/s knockback after a
300 ms windup — the only attack in the game that hits on both sides of its owner.

Soul burst costs `MP_BURST 50` of `MP_MAX 100`; a kill pays back `+24` MP
("SOUL MP +24"). The villager at `VILLAGE_COL 11` refills HP and writes the
save; the court gate is `BOSS_GATE_COL 112`.

## HUD, placed by the widgets rather than by hand

- plate + round portrait at `2,2 34x34`; the portrait tints to
  `rgb565(255,110,110)` on alternating frames while `g_flash > 0`.
- hearts: `vxpe_hud_icon_row_init(..., 40, 6, HERO_HP)` with `pitch_x/y 10`.
- MP gauge: `vxpe_hud_gauge_init(&g_mpbar, 40, 22, 58, 6, MP_MAX)`, 5 segments,
  `low_at 20`. The "MP" word sits at `102,22` — past the gauge, not under it,
  because the strip below is sky and a two-glyph word there reads as level art.
- minimap: 32x6 rooms at `cell 3`, `x = SW - 96 - 4`, `y 4`, inside a plate 2 px
  larger on every side — an unrevealed map is a black rectangle and without the
  bevel it reads as a hole punched in the HUD. Its `color_bg` is lifted to
  `rgb565(24,26,52)` for the same reason.
- boss plate through `vxpe_hud_boss_init/show/set_hp/hide` (`WARDEN_HP 40`), and
  the transient message band at `y 246` on a plate sized by
  `vxpe_font_measure()`.
- `MS n` paint probe at `2,306`, in the one corner the world never draws status
  into.

Camera is `vxpe_cam_init(&g_cam, SW, SH, WORLD_W, WORLD_H)` with deadzone
`(74,74,120,96)` and **7** `vxpe_cam_shake` call sites (5,260 / 2,120 / 4,220 /
2|3,130 / 8,900 on the boss kill / 3,180 / 6,700).

## Input

`vxpe_input_bind` maps **11** named actions (`ACT_LEFT..ACT_MENU`) and every one
accepts handset keys *and* the numpad: arrows or 2/4/6/8 run and climb, 5 or the
left softkey whips, 7 or OK jumps, 3 or the right softkey spends 50 MP on the
burst, 9 pauses, 1/CLEAR backs out, 0/# opens the menu. The step is `DT_MS 33`
and one `vxpe_input_update` runs per step, so a `pressed` edge can never be read
twice — which is also why the menu cursor does not run away on a long key hold.

Pen has no key codes, so the three tap bands push **synthetic** codes
(`PEN_LEFT 200`..`PEN_BURST 206`) through `vxpe_input_press`: tap the sky to
leap, the middle band to run or whip in its centre, the bottom band to climb or
burst. The game never sees a coordinate; there is one control path to test.

## Screens

`SCR_SPLASH, SCR_MENU, SCR_HELP, SCR_GAME, SCR_PAUSE, SCR_OVER, SCR_WIN`.
Splash self-advances at 2.4 s (`g_title_ms > 2400`) over an attract world that
runs the same simulation with an autopilot hunter. The menu is three rows —
`NIGHT HUNT`, `HOW TO PLAY`, `LEAVE THE VEIL` — at `MENU_Y0 176`, `MENU_STEP 26`,
with `BEST SOULS` and `SOULS TAKEN` in 5-digit `vxpe_hud_format_int`. Pause and
the verdicts dim the live frame behind a plate rather than drawing a separate
scene. Result windows ignore input for their first 400 ms, and a death verdict
for 1.2 s: a hero who dies mid-jump would otherwise read the very next hop as
"dismiss" and never see the panel he is supposed to learn from.

## Engine paths exercised (distinct core calls in `src/main.c`)

`vxpe_hud_*` 22, `vxpe_input_*` 10, `vxpe_combat_*` 10, `vxpe_cam_*` 13,
`vxpe_proj_*` 4, `vxpe_tilemap_draw`/`vxpe_tile_view` + `vxpe_tilemap_blocks_at_px`
and only 4 direct `vxpe_body_*` (`init`, `tuning_default`, `settle`, `touching`)
— every actual move goes through `vxpe_combat_body_step`/`_control`, so a body
that can be hit and a body that cannot are the same integrator. `VxpRender2D`
stays thin on purpose:
`vxpe2d_blit_parallax_x` 3 (the bands), `vxpe2d_blit` 2 (masked sprites and the
additive `VXPE_BLEND_ADD` spark pool at `alpha 40+life*8`, `dst_w = w*scale/2`),
`vxpe2d_fill_rect` 5, `vxpe2d_gradient_vertical_dithered` 2 (the two sky halves),
`vxpe2d_overlay_rect` 1 (the scrims), `vxpe2d_rgb565` 27 for the palette.
`VxpPixelFont`'s 3 entry points carry every word: 11 `vxpe_font_draw` sites over
4 styles, only `st_title` switching to `VXPE_FONT_DISPLAY` at scale 2 with
`OUTLINE|SHADOW`. No 2.5D or raycast call anywhere — this is the reference for
pure `action2d` + `VxpRender2D` layering.

## Build & run

```bat
scripts\build_arm.bat     :: -> build-arm\main\vampire_veil.vxp (APP ID 9591686, dev)
scripts\run_vxpemu.bat    :: build + launch VXPEmu
```

RAM tag 800 KB, `developer VXPstore`, `api File Audio ProMng`
(`project.vxp.json`). Progress is the template's `src/vxp_public_cache.h`:
`<removable-drive>:\@vxp_9591686\save.bin`, versioned header, temp-file commit,
best-souls and kill counters only — never art. Retail: rebuild through the
engine-signed flow (`certid 100`, per-app key); keys never live in the project.

## Verification

- **Core regressions**: `engine/coremre/tests` — the eight action2d cases
  (`vxpe_action2d_runtime/_c_api`, `vxpe_combat2d_*`, `vxpe_input2d_*`,
  `vxpe_hud2d_*`) plus the graphics suites. The run that shipped this sample
  measured 29 tests, **29/29 passed**, total test time 0.71 s —
  `tmp/veil_a2d_ctest.log` (configure/build logs
  `tmp/veil_a2d_configure.log`, `tmp/veil_a2d_build.log`). The same build tree
  now carries two more cases from the sprite-forge art route and measures
  **31/31 passed** in 3.63 s — `tmp/sforge_full_ctest.log`.
- **Host offscreen harness**: `tmp/veil_shots.c` links the *real* `src/main.c`
  against `tmp/veil_shim.c` (an MRE shim over a static `uint16_t g_fb[240*320]`),
  drives key and pen events and dumps **77 frames** as raw 565 into `tmp/vshots/`;
  `tmp/make_veil_shots.sh` builds and runs it, `tmp/veil_sheet.py` tiles them
  into labelled 2x contact sheets (`tmp/veil_sheet_{title,menu,run,boss,end,pen,
  hero,small}.png`, `tmp/veil_{tiles,tiles2,props,actors,bands,hero,hud}_sheet.png`).
  Every screen and animation stage was judged by eye there before any device run.

## Notes from the VXPEmu runs (2026-10-16)

Built with `scripts\build_arm.bat`; the shipped `vampire_veil.vxp` is
**485,579 bytes**, APP ID **9591686**, unsigned dev module. Eight device runs,
driven by six scripts (`tmp/veil_emu_tour.py` pass 1, `veil_emu_boss.py` pass 2,
`veil_emu_court.py` pass 3, `veil_emu_court2.py` passes 4-6, `veil_emu_ms.py`
pass 7, plus the p00-p05 persistence probe), grabbed **109** real device screens
with DPI-aware `PrintWindow` into `tmp/veil_emu/` and tiled them into
`tmp/veil_sheet_emu{,2..6}.png`. Everything below is from looking at those PNGs.

- Confirmed live on the ARM build: splash with rising title over the attract
  world; the menu panel with its `BEST SOULS` / `SOULS TAKEN` rows; the `HOW TO
  PLAY` page fully legible; hunt start; HUD (portrait, 8 hearts, 5-segment MP
  gauge, `MP` label, 4-digit score, dotted 32x6 corner minimap); the east run;
  the **red whip crescent** in three separate frames; jumps; ladder traversal out
  of the crypt void; brick walls, gravestones, statues, fences, lamps; imps, owls
  and bats; `SOUL MP +24`; `MENDED AND SAVED - the court lies east`;
  `THE VEIL BITES BACK`; hit particles; the red portrait damage flash; a
  projectile sprite; `THE STONE WARDEN WAKES`; the **STONE WARDEN plate with a
  full red HP bar**; and the PAUSED panel with scrim.
- **Save persistence, proven across process restarts.** `vm_get_removable_driver`
  is `'e'` in VXPEmu (`MreIO.cpp:562`) and `path_from_emu` maps it to
  `%LOCALAPPDATA%\MREmu\fs\e\`, so the game's cache lands at
  `...\fs\e\@vxp_00925b86\save.bin` — 24 bytes: header `VXPC`/v1/12, then
  `magic 0x56534C31, best 160, kills 0`. A fresh boot read it back as
  `BEST SOULS 00160` (`tmp/veil_menu_probe.png` stacks the 4x digit crops of
  `tmp/veil_emu/p00_boot_menu.png`, `p03_menu.png` and `p05_relaunch_menu.png`).
  Caveat found while checking this: an in-session menu number is *not* evidence —
  the early passes showed 00035 and 00160 in-session while their own fresh boots
  still read 00000, because `save_write` only runs on death, at the villager, and
  on destroy from a non-menu screen (`main.c:1735`). A short run that ends by
  backing out to the menu writes nothing: `save.bin`'s mtime did not move across
  the whole p01-p04 run.
- **Paint cost read off the in-app probe: `MS 07` to `MS 09`**, sampled every 4 s
  across a 28 s live run (`tmp/veil_ms_probe.png` — 8 grabs of that corner
  cropped 4x out of `tmp/veil_emu/` frames: 08 08 08 07 07 07 09 07). At
  `DT_MS 33` that is roughly a quarter of the frame budget, so the whip, both
  tile layers, three bands, the whole 14-slot combatant pool and the full HUD
  leave room for a second effect layer on a handset. Note the host harness always
  reports `MS 00` — `tmp/veil_shim.c:40` returns a tick counter that does not
  advance inside `draw()`, so that number is device-only.
- **A byte-identical capture is a dead app, not a hung one.** Pass 2 froze at 0 px
  motion for the rest of its grabs: `tap("NP8")` is UP, row 0 wraps upward to
  `LEAVE THE VEIL`, and the next RETURN ran `vm_exit_app()` while PrintWindow kept
  replaying the last frame. `Get-Process .CPU` was flat (a real loop would peg a
  core), `EnumWindows` showed no dialog, and the PNGs were byte-identical in
  length. Pass 3+ navigate the menu with `NP2` (DOWN) only, and `shot()` in
  `tmp/veil_emu_tour.py` warns after three unchanged grabs.
- **The device hop is shorter than the host's.** Pass 4 arrived at the court on 0
  HP because a 0.17 s OK-press jump — the host pen-tap equivalent — drops into the
  spike trench. `hop = 0.34` s in pass 5 cleared every gap and reached the Warden
  alive; the traversal bot is `cycle()` in `tmp/veil_emu_court2.py`.
- A real playability defect only device testing found: the verdict panel could be
  dismissed by the same key that killed the hero, so a mid-jump death skipped the
  panel entirely. Fixed with the `g_title_ms` locks in `sim_update()` and the two
  screen handlers, then re-verified end-to-end on the host harness (77 frames,
  behaviour unchanged elsewhere).
- Harness hazards: VXPEmu is single-instance, so every driver `taskkill`s it and
  waits for the window to disappear before `Popen` — a live process keeps serving
  its already-loaded module and the run silently tests a stale build. The window
  exists ~3 s after launch; `wait_boot()` polls on mean luminance instead of
  sleeping.
