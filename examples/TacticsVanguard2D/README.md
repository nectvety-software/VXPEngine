# Tactics Vanguard 2D — VXPEngine sample game

A Fire-Emblem-style 16-px tactical map for MRE VXP handsets (240x320,
Nokia 225/220 portrait), rebuilt from the reference clip frame by frame:
yellow-green grass, tan roads, clumpy pines, faceted mountains with snow
peaks, a dithered sand shore under a river with three bridges, golden keeps
and 16x26 cel-outlined knights that overflow their tile upward. Selecting a
unit paints its move range as a hatched field with a chunky ivory path arrow,
confirming the move opens a parchment action card, and attacking slides in a
skewed cut-in band before damage numbers and HP bars resolve.

240/16 is exact, so the field needs no scaling and every tile edge lands on a
pixel boundary — the whole map is 15x17 tiles at native size.

The clip has no title or menu, so the splash, menu and briefing screens reuse
the map's own language: the battlefield stays live behind a scrim, the army
crest is the emblem, and parchment plus gold mark anything the player can act
on. All art is procedural — no external assets, no licensed names or sprites.

## Asset model: one generator, baked RGB565 + 1-bit masks

`tools/generate_tacticsvanguard_assets.py` rasterises everything into
`src/assets_gen.h` (209,095 bytes):

- **22 terrain tiles** (`TV_NTILE`), 16x16 RGB565, baked opaque. `tile_id()`
  picks a variant per cell from a cheap `(x*7 + y*13) & 7` hash over
  `GRASS0..3` / `ROAD0..1` / `FOREST0..2` / `MOUNT0..1`, so the field never
  looks tiled, and the water tile cycles three frames for the river animation.
- **40 masked sprites** (`TV_NSPRITE`): 38 unit poses — 6 classes x 2 armies x
  3 poses (idle / step / attack) plus the fox's 2 — and 2 army crests. Foot
  units are 16x26, the knight 24 wide; each carries an MSB-first 1-bit
  visibility mask with the row padded to a byte, so `w` is always a multiple
  of 8.
- Colours come from the reference frame's histogram rather than from memory.
  Each class is a feature dict (`crest: comb|horns|plume|none|hood`, `weapon:
  sword|axe|lance|bow|staff`, plus `shield`/`cape`/`robe`/`hair` flags) painted
  in a fixed layer order — rear arm, body, pauldrons, crest, weapon, weapon arm
  — so the six classes read apart at 16 px without outlines thicker than the
  art, and a new class costs one dict entry.

The cut-in portrait is not a second asset: the same unit sprite is blitted at
3x through `VxpeBlit565.dst_w/dst_h`, which keeps the parchment-scale face in
exact register with the map art.

## Field and rules

- **Map** — a 17-line x 15-char literal in `parse_map()`, so the terrain is
  editable as text. 13 terrain kinds (`PLAIN, ROAD, SAND, SEA, SHORE, WOOD,
  CLIFF, PEAK, HOUSE, KEEP, CAMP, RUIN, BRIDGE`) with three parallel lookup
  tables: `TR_DEF` (0-40 cover), `TR_AVOID` (0-25 dodge) and `TR_HOOF` (which
  tiles a knight may not cross — sea, cliffs, peaks and houses, so cavalry
  routes around the mountain spine instead of through it).
- **Roster** — 13 units (`MAXU 14`, zero heap): 7 for AZURE including the fox
  VIXEN, 6 for CRIMSON. Each side's commander is the sword; losing the
  commander ends the battle even with units left, which is what the briefing
  page tells the player.
- **Classes** (`hp, mt, mov, rmin, rmax, spd, dfn, str, hoof`): sword
  28/6/5/1-1, axe 32/9/5/1-1, lance 30/7/6/1-1, bow 24/5/4/2-3, mage
  22/7/4/2-3, knight 34/8/8/1-1, fox 18/3/7/1-1. Bow and mage cannot counter
  at range, which is why the river crossings decide the fight.
- **Move range** — Dijkstra over the 255-cell grid, settled until the move
  budget runs out (a 5-move unit settles ~40 cells), with `g_prev` kept so the
  ivory path arrow is the real route rather than a straight line.
- **Combat** — `dmg = (str+mt) - (dfn + TR_DEF) + rnd(3)`, floored at 1;
  `hit = 78 + 4*Δspd - TR_AVOID` clamped to 25..99; crit chance
  `6 + spd/2` % and a crit triples the blow. The numbers are tuned so a road
  fight trades two hits for one, which is what makes the terrain table worth
  reading at all.
- **Presentation of a blow** — a 34-step (~1.1 s) skewed cut-in band, damage
  landing at step 10, then a 22-step hit beat that shows the counter blow
  before `end_unit()`. Damage pops and sparks come out of a 6-slot static pool.
- **AI** — per unit: range + path, then score every standable cell
  (`60 + 4*speed - 3*worst + TR_DEF/5` when a target is in reach, otherwise a
  proximity-lowering approach score), walk, attack. It needs no player input,
  so an unattended battle plays to a result.

## Engine paths exercised

- `vxpe2d_blit` with `VxpeSprite565.mask` — every unit, crest and portrait,
  through one 20-line `blit_sprite()` helper that also drives `tint565`
  (white flash on hit), `alpha`, `flip_x` (facing) and scaled `dst_w/dst_h`
  (the 3x cut-in portrait).
- `vxpe2d_fill_rect` (27 calls) for the HUD rules, bars, selection frame and
  the 168-line splash gradient; `vxpe2d_overlay_rect` (7) with
  `VXPE_BLEND_ALPHA` for the scrims and the row highlight;
  `vxpe2d_gradient_vertical` (5) for the card plates; `vxpe2d_radial_light_fast`
  once, behind the crest.
- `VxpPixelFont`: `VXPE_FONT_DISPLAY` carries every heading — scale 3 with
  `OUTLINE|BEVEL` for the splash title, scale 2 for the cut-in name and the
  `VANGUARD` menu header, scale 1 for `TACTICS PRIMER`, and scale 3 again for
  `VICTORY`/`DEFEAT` — while `VXPE_FONT_UI` does all body text and `SHADOW`
  marks the prompts. The footer's terrain readout is assembled with a
  hand-rolled `num_str/app/appnum` pair — no `sprintf` anywhere in the file.
- No 2.5D calls at all: this sample is deliberately a pure `VxpRender2D` +
  `VxpPixelFont` project, which makes it the reference for masked-sprite
  2D layering.
- Frame probe: `g_frame_ms` is `vm_get_tick_count()` around `draw()` and is
  printed in the HUD as `MS n`, so on-device cost is readable from a
  screenshot instead of a log.

## Screens

All four share one backdrop: `backdrop()` repaints the full 240x320 with
`UI_INK`, `draw_map()` + `draw_units()` render the live field into y 24..295,
then a scrim dims it. Every overlay screen clears the whole frame itself —
`draw_map` only owns its band, so a screen that skipped the clear leaves the
previous screen's text burned in above and below the map.

- **Splash** (`draw_splash`) — 78 steps x 33 ms = 2.57 s, skippable by any
  key. Live field behind a 128 scrim, a 168-line blue gradient plate framed in
  gold, the army crest, `TACTICS` / `VANGUARD` at display scale 3 (gold with
  outline+bevel, ivory with outline), the teal tagline, a `PRESS ANY KEY`
  blink gated on `g_splash_t > 20 && (t & 16)`, and a gold loading bar that
  ramps 5 px per step from `t=31` and clamps to the 100 px track by `t=50`. The
  crest follows the army chosen in the menu, so a rematch re-skins the splash
  for free.
- **Menu** (`draw_menu`) — a gold-framed card over the same live field: crest,
  `VANGUARD / COMMAND SELECT`, a stat block (`ARMY: AZURE|CRIMSON`,
  `4/6 SWITCH`, `UNITS n`, `15X17 FIELD`) and four rows — `BEGIN BATTLE`,
  `CHANGE ARMY`, `BRIEFING`, `EXIT`. The selected row gets a 74/255 teal wash
  plus a 3-px gold bar at its left edge. `CHANGE ARMY` shows the current side
  right-aligned in that side's colour.
- **Briefing** (`draw_help`) — the card language again, titled `TACTICS
  PRIMER`: three gold-ruled blocks (key table, how a turn works, terrain and
  the lose condition) at 11-px pitch, `ANY KEY: BACK` in teal. Built by
  `help_block()` from `const char* const[]` tables so copy edits never touch
  layout code.
- **Battle** (`draw_battle`) — field, animated water, hatched move range,
  attack ring, path arrow, walking units with in-tile Q8.8 offsets, damage
  pops and sparks, the parchment action card, the cut-in band, and the top HUD
  (`ROUND n` / `YOUR PHASE|ENEMY PHASE|BATTLE OVER` / `YOU n` / `MS n`) with a
  footer that reports the terrain under the cursor and the selected unit.

## Play

- **Keys** are per screen. Splash and briefing: any key advances or returns.
  Menu: `2/8` or arrows move the cursor (wrapping), `5`/OK picks, and `4/6`
  flip the army *only* on the `CHANGE ARMY` row — off that row they fall
  through to cursor navigation, which is also why `EXIT` sits under `4/6` if
  you are not looking. In battle: `2/4/6/8` move the cursor, `5`/OK confirms
  (pick unit -> pick destination -> card row -> target), `7` backs out one
  level, `9` or `*` ends the player phase, `CLEAR` returns to the menu, right
  softkey exits the app.
- **Pen**: a tap aims the cursor at that tile and a second tap on the same
  tile confirms it, so the whole battle is playable by tapping; on the action
  card a tap picks the row under it, and in `BP_SELECT` a tap directly on a
  selectable unit confirms in one go.
- Win by routing the enemy or killing their commander; lose the same way.
  `5` on the result screen fights again, `CLEAR` goes back to the menu.

## Build & run

```bat
build_arm.bat     :: -> build-arm\main\tactics_vanguard_2d.vxp (APPID 6053201, dev)
run_vxpemu.bat    :: build + launch VXPEmu
```

Retail: rebuild with the engine-signed flow (`certid 100`, per-app key —
see `docs/BUILD_VA_KY_VXP.md`); keys never live in the project.

## Verification

`tmp/tactics_shots.c` links the *real* `src/main.c` against an offscreen MRE
shim (12 entry points over a static `unsigned short g_fb[240*320]`), drives
key and pen events, dumps raw 565 frames and lets `tmp/tactics_sheet.py` tile
them into labelled 2x contact sheets (`tmp/tactics_sheet_*.png`). Every screen
and animation stage was judged by eye there before any device run.

`tmp/tactics_dbg.c` + `tmp/make_tactics_dbg.sh` add a second translation unit
that `#include`s `main.c` (and must not also link `main.o`) to print the
`static` game state — phase, round, active side, result, cursor and every
unit's HP and range — which is how the stall below was actually diagnosed.

## Notes from the VXPEmu runs (2026-10-14)

Built with `build_arm.bat` (log `tmp/tactics_arm_build.log`); the shipped
`tactics_vanguard_2d.vxp` is **132,647 bytes**, `APP ID 6053201`,
`VENDOR VXPstore`. `src/main.c` is 55,559 bytes.

`tmp/tactics_emu_tour.py` (pass 3), `tmp/tactics_emu_ai.py` (pass 4) and
`tmp/tactics_emu_final.py` (pass 5, against the rebuilt binary) boot that
`.vxp` screen-only, drive it with posted key messages and grab the device
screen with DPI-aware `PrintWindow`; the frames are in
`tmp/tactics_emu_pass3/`, `tmp/tactics_emu/` and `tmp/tactics_emu_final/`,
tiled by `tmp/tactics_emu_sheet.py` into `tmp/tactics_emu_sheet_*.png` and the
HUD close-ups into `tmp/tactics_emu_hud_strip.png`. Everything below is from
looking at those PNGs.

- Splash, menu, briefing page, `CHANGE ARMY` to CRIMSON (`UNITS 6`) and back
  to AZURE (`UNITS 7`), field, hatched range with the `CAEDRIC SWORD HP 28/28
  MV 5 RNG 1` footer, ivory path arrow, completed walk, parchment card, enemy
  phase, five different cut-in bands, damage pops, HP bars draining, the round
  counter, `BATTLE OVER` and the `DEFEAT` overlay were all confirmed rendering
  live on the ARM build.
- **Frame cost** read off the in-app `MS n` probe: **32-61 ms** across the
  player phase, range display and action card, **33-55 ms** while the AI walks
  and attacks, and **67-98 ms** on the full-screen result overlay (it repaints
  map + units + scrim + display-scale text every frame). Pass 5 on the rebuilt
  binary read `MS 48` and `MS 58` for the field and range, so the clamp cost
  nothing. That is 16-30 fps in play; the emulator is not a speed reference,
  but the result screen is the one place a handset would visibly drop frames.
- An unattended battle (only `9` pressed, never `5`) resolved in **round 6**
  with `SURVIVORS 0` — the same length as the host harness's unplayed replay,
  so the AI tuning transfers between the two builds.
- Phase-to-phase motion measured 188-19,189 changed 2-px samples per step in
  pass 3 and 328-8,832 per second during the AI run, so nothing freezes
  between inputs.
- **A byte-identical capture is a dead app, not a hung one.** Pass 2 froze on
  `s09_range` for 22 consecutive grabs. The frames were identical because the
  app had exited: the menu treats `4/6` as row navigation on every row except
  `CHANGE ARMY`, so the driver's army flips slid the cursor onto `EXIT` and the
  next `5` called `vm_exit_app()`. `Get-Process` CPU time was flat (a real
  infinite loop would peg a core), and the emulator keeps painting the last
  frame. Pass 3+ therefore reads the menu's 3-px gold highlight strip out of
  the screenshot to place the cursor instead of pressing a fixed key count.
- The same pass found the splash's gold card rule at y=212 sitting exactly
  under the menu row-2 highlight sample, so a one-pixel "is this the menu"
  probe matched the splash and the whole run drifted one screen. The detector
  now requires gold 13 px apart in the same column — only the 20-px-tall
  highlight fits that.
- **The loading bar overshot its track and only a 0.25 s sampler saw it.** The
  splash fill is `(t-30)*5` px, which reaches 120 at `t=54` against a 100 px
  track, so the last frames painted 20 px of gold past the end. Passes 2-4
  polled at 0.3 s and never landed inside that 4-frame window. Pass 5 samples
  the bar width on every grab (measured ramp 0, 0, 20, 60, 100, 100, 100, 100
  px) and the clamp is in `draw_splash()`, with a `splash_t54` frame added to
  the host harness to cover it.
- **Gameplay bug the harness caught and the pixels hid**: `hp` is a `uint8_t`,
  and `g_u[d].hp -= dmg` wrapped a killing blow back to a large positive
  number, so nobody ever died and the battle stalled (host replay ran rounds
  4->56 with zero casualties while every screen still looked correct). Fixed
  in `deliver()` by subtracting in `int` and clamping. Only the state dump
  from `tmp/tactics_dbg.c` showed it.
- Harness hazards: VXPEmu is single-instance, so both scripts `taskkill` it
  first — a live process keeps serving its already-loaded module and the run
  would silently test a stale build. The window exists ~2.9-3.1 s after
  launch, which is why the first pass missed the splash entirely; polling from
  the first paint captures 8 splash frames at 0.3 s spacing.
