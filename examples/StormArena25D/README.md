# Storm Arena 2.5D — VXPEngine sample game

Anime-style 1v1 fighting-game stage for MRE VXP (240x320, Nokia 225/220),
recreating the *graphics language* of the reference video (perspective grid
arena with a tan boundary ellipse, cel-outlined ninjas, radial hit bursts,
puffy white dust clouds, fullscreen speed lines, thin gold HP bars + blue
gauge pips + infinity timer + yellow combo counter + damage popups) on the
`VxpScene25D` core. Characters REN (silver hair / green vest) and KURO (black
suit / red accent) are original: the video's roster is fan art of a licensed
franchise and is not reproduced. All art is procedural — no external assets.
The clip is 9 s of gameplay captured in an editor and has no title or menu, so
the splash, menu and help screens below were designed in the HUD's own visual
language rather than copied.

## Art model: authored parts, composited at runtime

The video's sprites are fine 1-px pixel art roughly half the screen tall, so
they must be *authored* at display size; nearest-neighbour upscaling a small
atlas produces the blocky look the earlier revisions had.

`tools/generate_stormarena_sprites.py` authors each fighter as **10 body
parts** on a shared 96x176 figure canvas (head, torso, four arm poses, four leg
poses), rasterised as a material index map and baked once into
`src/sprites_gen.h` as RGB565 + a 1-bit visibility mask:

- **Materials, not colours.** Every stroke is laid down as a material id
  (`SKIN`, `HAIR`, `CLOTH`, `METAL`, `VEST`, `VEST_D`, `LEG_UP`, `LEG_LO`,
  `WRAP`, `SANDAL`, `BELT`, `GLOVE`, `ACCENT`, `EYE`) and the colour is resolved
  at bake time from a per-fighter palette, so REN and KURO share one art source.
- **One raster, two silhouettes.** `LEG_UP`/`LEG_LO` are the same leg drawn
  once: REN resolves them as navy trousers top to ankle, KURO as black shorts
  over a bare calf. The wrap band works the same way - its stripe period lives
  on the palette (0 = REN's solid cream band, 3 = KURO's bandedage ladder) and
  is carved at bake time, so the reference's most distinctive difference costs
  no extra sprite data.
- **Figure-space cel lighting.** A diagonal terminator keyed to each part's own
  bounding box (key light from the upper right) plus a rim highlight on exposed
  right edges, so a copied limb never picks up the key light just because it
  sits high on the canvas.
- **Material-tinted outlines.** The 1-px silhouette line is a darkened copy of
  the material it touches, never a fixed near-black. Parts are composited at
  runtime, and a single global outline colour stacks two rings into a 3-px black
  stripe in every seam - which is what made the earlier builds read as black
  boxes bolted onto a ninja.
- **Runtime compositing.** `refresh_sprites()` clears the scratch canvas and
  blits the six slots of the current pose; `blit_part()` skips masked pixels, so
  no dilation or outline pass runs on the handset.

Proportions and colours are measured, not eyeballed, and the source frame
matters: `tmp/refvid/f02.png` is washed out by a hit flash, which is what sent
an earlier revision chasing a tan vest. `tmp/refvid/f05.png` is the clean frame
- REN is 127 px tall with a 14% head, a shoulder line 25% of his height, the
knee at 70%; his vest is olive (`#42493f`), his trousers navy (`#222433`), his
hair the brightest thing in frame; KURO's suit is `#0f0e10`. `tmp/art_sheet.py`
renders six poses per fighter next to a crop of that frame so every art change
is judged by eye against the reference.

Budget: 10 parts x 2 fighters = **91,522 bytes** of baked sprite data, plus two
96x176 scratch canvases with alpha planes (101,376 bytes of `.bss`). Eight full
96x176 poses per fighter would have cost ~792 KB, which no handset in this
family can hold.

Two rules the pose table has to respect, both learned from a broken frame:

- A grounded pose must contain a part whose pixels reach the sole line (canvas
  y=166). The old `leg_trail` part had its heel up, and using it as the kick's
  only support leg floated the whole figure 17 px above its own shadow.
- The head may sit at most ~2 px further along than the torso, or the neck
  tears open.

Because the flip happens at blit time, the baked key light mirrors with the
sprite: two fighters facing each other are lit from opposite screen sides.
Fixing that means a second, mirror-lit bake of every part (~2x sprite data),
which is not worth the bytes on this hardware.

- At the fight depth (`FIGHT_Z == focal`) the billboard maps 1:1, so the figure
  renders 167 px tall — 52% of the 320-px screen, matching the video's framing.
- The canvas is wider than the body (96 px for an ~58 px figure) so the punch
  arm and kick leg can fully extend without clipping. The body sits at canvas
  x=40, so `pivot_x_q8` is 106 — and 150 when `flip_x` is set, because the
  engine mirrors *inside* the destination rect. `pivot_y_q8` anchors at the
  sandal line (canvas y=166), not the canvas bottom, so the ground shadow hugs
  the feet.

Regenerate after editing the art source:

```bat
.venv\Scripts\python tools\generate_stormarena_sprites.py           :: header + preview
.venv\Scripts\python tools\generate_stormarena_sprites.py --preview :: preview only, tmp\sprites_preview.png
```

## Engine paths exercised

- `vxpe25d_draw_ground`: endless grid floor (16x16 tile, subtle grid lines and
  speckle), row fog toward the horizon, camera locked to the fight midpoint.
- `vxpe25d_draw_rope_world`: the arena boundary — a 16-segment world-space
  ellipse (radius 150, Q14 cosine table) plus 8 radial ticks, painted in a
  warm tan line after the ground so it reads like the video's stage ring. The
  ring centre sits deeper than the fight line so the near arc lands on-screen.
- `vxpe25d_batch_*`: both fighters as depth-sorted billboards with projected
  ground shadows, drawn 1:1 (world size == source size at the fight depth),
  `flip_x` for facing, per-tint white flash on hit.
- `vxpe2d_draw_burst` (ADD): 16-ray hit spark with a filled flash core, and
  expanding fullscreen speed lines on the super. `vxpe2d_draw_ring` supplies
  both the shockwave ring and — with `thickness == radius` — the six filled
  lobes of the dust cloud, each drawn once as a grey rim and once as white so
  only the silhouette keeps its rim.
- `VxpPixelFont` HUD: name plates, a thin gold HP bar stacked over a wider
  segmented teal gauge per side (both sampled from the reference frame),
  centre infinity, yellow "N HITS / DMG" combo, rising "+N" popups projected
  through the 2.5D camera, numbered skill-icon column, K.O. overlay.
- Frame probe bar bottom-left (1 px/ms, green/amber/red).

## Screens

The fight sits behind a three-screen front end, all drawn with the same
zero-heap APIs and the HUD's own vocabulary (gold display type with
outline/bevel, teal accents, studio-navy grid, `UI_INK` plates):

- **Splash** (`draw_splash`) — a 2.6 s card: dithered navy gradient, a hand
  rasterised vanishing grid (13 converging verticals + 5 horizontals; the
  perspective-floor path needs a 16x16 tile and the arena tile is far too
  bright for a navy card, so this is a Bresenham `line()` loop), a gold-framed
  ink plate, `STORM\nARENA` at display scale 3 with outline+bevel over a warm
  radial light, then a teal loading bar whose fill is `g_splash_t` and a
  blinking `PRESS ANY KEY`. It auto-advances and any key cuts it short.
- **Menu** (`draw_menu`) — the arena itself is the backdrop: `draw_scene()`
  renders both fighters idling at `x = ±58` and a 118/256 ink scrim goes over
  it, so the two figures read through the panel the way they do through the
  stage haze in the clip. Header band, a
  name plate per fighter projected through the 2.5D camera (so the plates track
  the figures), a gold VS ring, and five rows — `FIGHT A CPU`, `WATCH DEMO`,
  `P1 SIDE: REN/KURO`, `HOW TO PLAY`, `EXIT` — each with a right-aligned hint
  column. The selected row gets a slate highlight plus a 3-px gold bar.
- **Help** (`draw_help`) — key table (4/6, 2, 5, 7, 8), the two pen gestures,
  and the rematch/Clear notes. Any key goes back.
- **Fight** (`draw_fight`) — the scene plus the HUD described above.

`P1 SIDE` swaps which fighter the player owns: it flips `g_p1_side`, and the
name plates, the HUD names and the KO winner text all read through
`side_name()`, so one switch moves the whole front end. `CLEAR` leaves a match
early and returns to the menu without ending the app.

## Play

- **Keys are per screen.** Splash and help: any key goes back/forward. Menu:
  `2/8` or up/down move (wrapping), `4/6` change the P1 side *only* on its own
  row, `5`/OK picks, `CLEAR`/softkey exits. Fight: the list below.
- Pen: on the menu, a tap picks the row under it (`menu_row_at`) and taps
  outside the card do nothing; in the fight, hold the left/right third to walk
  and tap the centre to punch.
- `4/6`: walk left/right. `2`: jump. `5`: punch. `7`: kick. `8`: super
  (needs a full gauge; launches the opponent, freezes frames for impact).
- **Attract mode.** `WATCH DEMO` runs both fighters on the CPU; `FIGHT A CPU`
  hands P1 to the player. Inside a match the demo still takes P1 back 3 s after
  the last input. The gate is wall-clock (`vm_get_tick_count()`), not the frame
  counter - see the notes below.
- KURO stays CPU-controlled (holds ~92 px of spacing, attacks in range,
  retreats, spends its gauge on a super). First to 0 HP loses; `5` rematches
  into the same mode. Right softkey/CLEAR exits.
- Combos: consecutive hits within ~3 s stack the hit counter and total damage.

## Build & run

```bat
build_arm.bat     :: -> build-arm\main\storm_arena_25d.vxp (APPID 6053101, dev)
run_vxpemu.bat    :: build + launch VXPEmu
```

Retail: rebuild with the engine-signed flow (`certid 100`, per-app key —
see `docs/BUILD_VA_KY_VXP.md`); keys never live in the project.

## Notes from the VXPEmu runs (2026-10-11)

`tmp/storm_emu_test.py` boots the built `.vxp`, drives idle/throttle/attack/
steer phases with posted key messages and grabs the device screen with
PrintWindow; every claim below is from looking at the saved PNGs in
`tmp/storm_emu/`, not from pixel-diff counts alone.

- Boot 0.5 s. The shipped build measures **15-34 ms per frame** on the probe bar
  across all phases (`storm_emu_run4.log` next to the captures; a much lighter
  scene than MeadowRush25D, which saturates at 64 ms). The six phase-to-phase
  motions (changed 2-px samples) ran 1,539-6,352, so nothing is frozen between
  inputs. The emulator is not a speed reference.
- `cmake --build tmp/host25d-mingw -j8` + `ctest --test-dir tmp/host25d-mingw`:
  **21/21 passed** with the final art in the tree.
- Driving this sample exposed a core bug in `vxpe25d_draw_ground`: the per-pixel
  world step was 256x too small with a level camera, so the arena showed only
  horizontal bands and no vertical grid lines. Fixed (Q16 step + un-truncated
  row phase) with a new regression test in
  `engine/coremre/tests/vxpe_scene25d_regression.cpp`; MeadowRush25D was
  re-checked afterwards and its ground now shows true perspective tiling.
- **The app timer does not run at its requested rate.** VXPEmu fires the 50 ms
  `vm_create_timer` callback at whatever rate it can paint - measured 11.5 Hz on
  this scene (81 callbacks in 7.05 s) and ~76 Hz on an earlier, lighter one. So
  `g_tick` counts *simulation steps* driven by a 33 ms accumulator over
  `vm_get_tick_count()`, and the attract-mode idle gate compares wall-clock
  milliseconds. Both were frame counters before, which is why the demo looked
  one-sided: at 11.5 Hz the 150-callback latch kept P1 passive for ~13 s.
- That diagnosis came from `tmp/combat_sim.c`, a headless copy of the combat
  loop (rendering and VFX stripped) run over 8 variants x 400 matches. A fully
  passive P1 reproduces the device signature exactly - starts 14.3, hits 14.11,
  100.0 damage taken, 13.3 s match - which matched the observed
  "14 HITS / 194 DMG, KURO WINS" and ruled out the AI being at fault.
  `tmp/combat_sim_report.txt` holds the run.
- Sample-side bugs found by looking at captures, in order: wrong atlas stride
  (garbled stripe fighters), ground shadows floating under the feet (pivot
  anchored at the empty canvas rows), punch/kick limbs clipped away by an 80-px
  canvas that left no room to extend an arm, a kick pose with no planted foot
  (figure floated 17 px above its shadow), and a hair fan wider than the
  shoulder line (read as a spiky wig, now capped at 26 px). Stage colours, ring
  colour and HUD bar colours were re-sampled from `tmp/refvid/f05.png` rather
  than eyeballed - the earlier sample frame was a hit-flash frame.
- Harness hazards worth remembering: VXPEmu is single-instance, so the script
  `taskkill`s it before every run - a live process would keep serving its
  already-loaded module and the whole run would silently test a stale build.
  From Git Bash the flag has to be quoted as `"/IM"`; `//IM` reaches the process
  as a path. And an HP sampler that reads `0` is usually a white hit-flash frame
  (the flash repaints the bar region), not a dead fighter - confirm on the next
  frame before believing a knockout.
- The super and dust-cloud frames were verified with temporary builds
  (`gauge` forced full; dust spawned on any hit) and the probes were reverted
  before the shipped build. The `>= 20` damage gate still means only the super
  raises a cloud.

### Front-end verification

`tmp/storm_screens_test.py` boots the same `.vxp` and walks splash -> menu ->
side toggle -> help -> back -> match -> Clear -> menu -> any-key splash skip,
capturing every screen; its stdout is archived as
`tmp/storm_screens/run1.log` next to the PNGs, and
`tmp/emu_screens_sheet.py` tiles them into `tmp/emu_screens_sheet.png`.

- Splash: window exists at **3.04 s**, the card is first seen in that same
  poll, the loading bar reads **26 px of 158** there and **97 px** one second
  later, and the menu takes over **2.07 s** after that. The design is 78
  simulation steps x 33 ms = 2.57 s, and roughly 0.5 s of it runs before the
  emulator window exists, so the numbers agree.
- The `PRESS ANY KEY` blink measured **8 visible of 14 samples** at 0.12 s
  spacing, 170 bright pixels when on - the ~1 Hz duty the `g_tick & 16` gate
  asks for.
- Motion between phases (changed 2-px samples): menu idle breathing **1,063**,
  side toggle **2,729**, menu -> help **18,691**, menu -> fight **19,192**,
  fight -> menu **19,159**. Nothing is a frozen frame.
- Probe bar: the **first** fight frame after the menu is the worst frame of the
  run at **64 ms** - and 64 is the bar's ceiling (1 px/ms over 64 px), so that
  one transition is at or above it; the next two frames read **21 ms** and
  **19 ms**. The older fight/perf walk
  (`tmp/storm_emu_test.py`, now two OK taps past the splash) still passes and
  measures **16-43 ms** across its idle/throttle/attack/super/steer phases.
- `ctest --test-dir tmp/host25d-mingw`: **21/21 passed** with the front end in
  the tree.
- Harness hazards this added: VXPEmu's client area here is 300x400, so the grab
  is downsampled 1.25:1 and a **1-px gold rule can vanish** - screen detectors
  count gold pixels over the logo block instead of reading single pixels. The
  window hunt has to spin at ~20 ms, because the card only lives 2.6 s and the
  0.5 s polling loop of the first version missed it entirely. And VXPEmu's
  screen-only window has **no mouse/touch -> pen path at all** (no `WM_*` or pen
  handling anywhere in its `src/`), so the menu's pen rows are verified on the
  host harness instead.
- That harness (`tmp/make_shots.sh`) compiles the *shipped* `main.c` with mingw
  against a 9-function MRE shim, drives `handle_sysevt/keyevt/penevt` directly,
  dumps raw RGB565 and tiles a 2x sheet (`tmp/shots_sheet.png`). It is what made
  whole-screen UI reviewable in under a second, and it caught four layout bugs
  before any ARM build: the help page truncating every line at 3 characters,
  corner ticks drawn with negative widths (so nothing appeared), a VS ring whose
  radius equalled the half-width of the letters inside it, and menu arrows
  overflowing the card frame.
