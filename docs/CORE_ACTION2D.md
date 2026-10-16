# VXPEngine action2d core

Six modules under `engine/coremre/{include,src}/action2d` turn the engine from a
sprite blitter into a side-scrolling action-game runtime: a scrolling tilemap with
tile collision, a follow camera, a platformer body, frame-accurate melee and
projectile combat, the handset HUD widgets, and an action-based input map.

They exist because the class of game the engine had to reach — a 240x320
Castlevania-shaped action platformer with parallax, a whip, ladders, a boss bar
and a corner map — needs contracts, not more blitters. Every module is `extern
"C"`, allocates nothing, stores no globals, and uses Q8.8 fixed point with shifts
and multiplies only: no float, no divide, because ARMv5TE handsets have neither an
FPU nor a divide instruction.

```c
#include "action2d/VxpTilemap2D.h"
#include "action2d/VxpCamera2D.h"
#include "action2d/VxpBody2D.h"
#include "action2d/VxpCombat2D.h"
#include "action2d/VxpHud2D.h"
#include "action2d/VxpInputMap2D.h"
```

## VxpTilemap2D — map data, renderer and collision queries in one

`VxpeTilemap2D` is a `cells` array (tile ids), an optional `flags` array and a
pointer to a rectangular `VxpeSprite565` atlas, all `const` so they land in
`.rodata` next to the art. `vxpe_tilemap_draw` blits only the visible window and
returns the number of tiles it actually drew, so culling is provable from a test
and a game can budget a frame without a profiler.

The renderer takes the screen position of tile (0,0) instead of a camera struct,
which keeps it independent of `VxpCamera2D`: the same map array can serve a
parallax band, a prop sheet or a HUD inset. Coordinates have floor semantics, so a
body at negative world x still addresses the tile left of the origin.

Flag bits 0..5 are gameplay (`SOLID`, `ONEWAY`, `HAZARD`, `LADDER`, `WATER`,
`TRIGGER`), 6 and 8..9 are render modifiers (slopes, flips) and 12..15 are free for
games. A slope tile never carries `SOLID`: it is solid only through its upper
triangle, and `VxpeBody2D` resolves it through `vxpe_tilemap_floor_y`.

Two layers over one shared `flags` array is the intended way to build a stage: an
opaque ground atlas for the mass of the terrain and a masked ledge atlas for
overhangs. Collision reads the flags once, so the two views can never disagree.

## VxpCamera2D — follow, deadzone, lookahead, shake

`vxpe_cam_init(&cam, view_w, view_h, world_w, world_h)` clamps to the world;
`vxpe_cam_set_deadzone` sizes the box the target may move inside before the camera
moves at all, and `vxpe_cam_set_lookahead` biases that box by facing.
`vxpe_cam_update` eases toward the target over `follow_ms`; `vxpe_cam_snap` is the
instant version for a respawn.

Shake is additive and never touches the follow state: `vxpe_cam_shake(&cam, amp,
ms)` writes `shake_x_q8/shake_y_q8` on top of `cam.x_q8`, and the shake decays to
zero on its own. Read the follow position with `vxpe_cam_x/y` (integer px) for
collision-relevant work, and add `shake_*_q8` only when computing a draw origin —
otherwise a shake drags the whole level sideways.

## VxpBody2D — the platformer move set

`vxpe_body_step(body, &tuning, map, &intent, dt_ms)` is the whole module: swept
axis-separated collision against tile flags, with `run_max_q8`, `run_accel_q8`,
`run_friction_q8`, `air_accel_q8`, `gravity_q8`, `jump_vel_q8`, `jump_cut_q8`,
`fall_max_q8`, `wall_slide_q8`, `swim_max_q8`, `climb_q8`, `coyote_ms`,
`jump_buffer_ms`, `step_up_px` and `step_down_px`. Every speed field is px/s in
Q8.8, so a tuning table reads like a design document: `104 * 256` is 104 px/s, and
the hero crossing a 240 px screen in 2.3 s is one multiplication to check.

The pieces that make a handset platformer feel deliberate rather than sticky:

- **Coyote time** keeps `coyote_ms` counting down after the body leaves a ledge,
  so a jump pressed just after the edge still fires.
- **Jump buffer** does the same for the opposite case: a press in the air is
  honoured on landing inside `jump_buffer_ms`.
- **Variable height** comes from `jump_cut_q8`: releasing the button mid-rise
  clamps the upward speed, so one key covers hop and full jump.
- **Step up/down** auto-climbs ledges up to `step_up_px` (also the slope
  tolerance) and keeps the body grounded while it falls up to `step_down_px`,
  which is what stops staircases from reading as walls.
- **Ladders** need intent, not a key: grabbing requires `intent.y != 0` on a
  `LADDER` tile. While attached, `vx_q8` is forced to 0 and motion is vertical at
  `climb_q8`; the body releases when the tile above has no ladder flag. Holding up
  at the top of a ladder therefore steps you off automatically.
- **One-way tiles** use `drop_ms`: a down-press opens a pass-through window
  instead of the body falling through every platform it touches.

`vxpe_body_touching` and `vxpe_body_ground_tile` answer the questions a game
actually asks (what am I standing on, am I inside a trigger) without a second
collision library.

## VxpCombat2D — windows, i-frames, projectiles

A `VxpeCombatant2D` owns a body, an HP total, and four independent timers:
`invuln_ms` (damage immunity), `stun_ms` (control taken away), `freeze_ms` (hit
stop — the sim pauses for this combatant only) and `flash_ms` (renderer hint).
`vxpe_combat_hurt` raises them with `max()` semantics, so a second hit inside a
window extends rather than shortens it, and `flash_ms` is pinned to `invuln_ms` so
one timer explains both the flash and why the next blow did nothing.

An attack is a `VxpeAttack2D` table: hitbox offset and size, then the three
windows `windup_ms`, `active_ms`, `recover_ms`, then `damage`, knockback in Q8.8,
`invuln_ms`, `hit_stop_ms`, `stun_ms` and `pierce`. `vxpe_combat_hitbox` returns
true only while `windup_ms <= atk_ms < windup_ms + active_ms` and hands back a
world-space rect already mirrored for facing:

```c
out->x = facing ? bx + off_x : bx + body->w - off_x - w;
```

That single rule is the reason a whip's art and its hitbox can never drift apart,
and the reason a game must draw its crescent from the same pivot the box uses.
`vxpe_combat_resolve` matches attack rects against `vxpe_combat_hurtbox` rects and
writes `VxpeCombatEvent2D` records — `HIT`, `KILL`, `BLOCKED` — into a
caller-owned array. Events are the only way a game learns what happened, and a
blocked hit is reported too, so a shield can tick instead of the game going
silent.

`vxpe_proj_pool_init` + `vxpe_proj_spawn` + `vxpe_proj_update` + `vxpe_proj_resolve`
give fixed-capacity projectiles with tile and combatant collision, and
`pierce` decides whether a hit ends the flight.

## VxpHud2D — widgets that read RGB565 palettes, not themes

`plate` (bevel + frame), `portrait`, `icon_row` (hearts, ammo — a filled sprite and
an empty sprite, so a spent heart is drawn not dimmed), `gauge` (segmented MP bar
with `vxpe_hud_gauge_is_low` and `vxpe_hud_gauge_flash`), `boss` (a name plate with
an HP bar that shows and hides on command), and `minimap` (a room grid plus a
`seen` bitmap the game reveals as the player explores). `vxpe_hud_format_int`,
`vxpe_hud_text_center` and `vxpe_hud_text_right` cover the rest, so no game needs
`sprintf` — which is what keeps `printf`-shaped code out of an ARM build.

The boss plate is drawn last and lives on the bottom edge; a game that ends the
fight must call `vxpe_hud_boss_hide`, because a live boss bar over a verdict panel
reads as a bug to the player.

## VxpInputMap2D — actions, not key codes

The game binds actions to keys once (`vxpe_input_bind(map, ACT_JUMP, VM_KEY_OK,
VM_KEY_NUM7, PEN_JUMP)`) and then only ever asks for actions: `pressed`,
`released`, `held`, `held_ms`, `repeated`, `axis`. Three physical codes map to one
action, which is how a handset's arrows, its 2/4/6/8 row and a synthetic on-screen
pad code all feed the same door.

Two rules that are easy to get wrong and are covered by tests:

- `vxpe_input_update` refreshes `pressed` from the pending edges once per frame,
  so a press can never be read twice — and a tap squeezed between two updates
  still produces both edges, which is what a menu needs.
- Repeat is one edge per frame whatever `dt_ms` says, so a 30 fps loop cannot
  fire a menu cursor twice for one physical tick.

A virtual pad is not a special case: the pen callbacks push synthetic key codes
(`#define PEN_JUMP 202` and friends) into `vxpe_input_press`, so the game never
sees a screen coordinate and there is exactly one control path to test.

## Verification

`engine/coremre/tests` builds the whole core with the modules linked in. The eight
action2d cases are `vxpe_action2d_runtime`, `vxpe_action2d_c_api`,
`vxpe_combat2d_runtime`, `vxpe_combat2d_c_api`, `vxpe_input2d_runtime`,
`vxpe_input2d_c_api`, `vxpe_hud2d_runtime`, `vxpe_hud2d_c_api`; the `_c_api` twins
compile the headers as C so a C game cannot be broken by a C++-only declaration.
The full suite is 31 tests and passes 31/31 in 3.63 s (`ctest -C Debug`, output
archived at `tmp/sforge_full_ctest.log`); the two newest cases belong to the art
import route described in [SPRITE_FORGE_INTEGRATION.md](SPRITE_FORGE_INTEGRATION.md).

The reference project for the whole set is `examples/VampireVeilDemo`: a
128x24-tile stage (2048x384 px), two map layers over one flag array, three
parallax bands, 14 combatant slots, 35 sprites, and a device build whose paint
cost is printed by its own HUD. Its art is still a hand-written generator. The
next step for that class of project is to author the hero's walk cycle with the
vendored sprite forge and import it through
`tools/vxp_import_sprite_forge.py --mode atlas`, because that is the case where
clip timing with per-frame durations earns its keep.
