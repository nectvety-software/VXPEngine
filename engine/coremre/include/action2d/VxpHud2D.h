/*
 * Copyright (c) 2026 PixelRoot32
 * Licensed under the MIT License
 *
 * VxpHud2D - the status layer a 2D action game draws over its world: framed
 * plates, segmented gauges with a trailing damage ghost, icon rows (hearts),
 * a boss name plate that slides in and out, and a corner room minimap.
 *
 * Everything draws straight into the caller's RGB565 buffer with integer math
 * and allocates nothing, so the whole HUD can be static data in a game's .bss
 * or file scope. Geometry is in framebuffer pixels; a widget that would fall
 * outside the screen is clipped by the primitives it calls rather than being
 * dropped, so the same HUD serves 240x320 and a landscape 320x240 build.
 *
 * Segment boundaries are computed with an accumulating remainder instead of a
 * divide per cell, because ARMv5TE has no divide instruction and a helper call
 * costs several hundred scanlines of sprite. Measured on the ARM object, a gauge
 * draw is two divides for its geometry plus one for each of the value and ghost
 * partial cells - the same price for a 1-cell and a 30-cell bar.
 */
#pragma once

#include <stdint.h>
#include "graphics/VxpRender2D.h"
#include "graphics/VxpPixelFont.h"

#ifdef __cplusplus
extern "C" {
#endif

/* --- plates --------------------------------------------------------------- */

/* A bevelled panel: outer frame, a light top/left bevel and a dark bottom/right
 * one around a flat inner field, which is what reads as "carved stone" rather
 * than "sticker" at this resolution. `inner` == 0 leaves the field untouched so
 * a plate can frame the world itself; to drop the frame or the bevel set the
 * matching thickness to 0, not the colour - a 0 RGB565 colour is black. */
typedef struct VxpeHudPlate2D {
    uint16_t frame, bevel_hi, bevel_lo, inner;
    uint8_t border_px;  /* frame thickness, 0..4 */
    uint8_t bevel_px;   /* bevel thickness inside the frame, 0..4 */
} VxpeHudPlate2D;

/* Slate plate with a gold-ish bevel: the house default for HUD furniture. */
void vxpe_hud_plate_default(VxpeHudPlate2D* plate);
void vxpe_hud_plate_draw(uint16_t* fb, int fb_w, int fb_h,
                         VxpeRectI rect, const VxpeHudPlate2D* plate);

/* Centers a sprite inside `rect` (no scaling) and clips it to the plate's
 * inner field, so oversized portrait art cannot bleed over the frame.
 * `tint` 0xFFFF is neutral and `alpha` 0 opaque - pass a red tint and a low
 * alpha ramp to make a portrait flash when its owner is hurt. */
void vxpe_hud_portrait_draw(uint16_t* fb, int fb_w, int fb_h,
                            VxpeRectI rect, const VxpeSprite565* art,
                            const VxpeHudPlate2D* plate,
                            uint16_t tint, uint8_t alpha);

/* --- gauges --------------------------------------------------------------- */

typedef struct VxpeHudGauge2D {
    int16_t x, y, w, h;
    uint16_t max_value;
    uint16_t value;
    uint16_t ghost;        /* trailing fill that falls behind `value` */
    uint16_t color_full, color_low, color_ghost, color_bg, color_frame;
    int32_t ghost_rate_q8; /* units per second the ghost falls; <=0 snaps */
    uint8_t segments;      /* 0 = one continuous bar */
    uint8_t gap_px;        /* px between segments, ignored when segments < 2 */
    uint8_t low_at;        /* percent at or below which color_low is used */
    uint8_t flash_ms;      /* >0 = the frame blinks; decayed by update */
    uint8_t mirror;        /* 1 = fills from the right, for a right-hand HUD */
    /* Sub-unit carry so a drain slower than one unit per frame still makes
     * progress: it accumulates rate_q8 * dt_ms and crosses 256 * 1000 once a
     * whole unit has passed. */
    uint32_t ghost_acc;
} VxpeHudGauge2D;

/* A red gauge, no segments, 200 units per second ghost drain and a 1 px frame.
 * Move it and resize it afterwards; set max_value and value yourself. */
void vxpe_hud_gauge_init(VxpeHudGauge2D* g, int x, int y, int w, int h,
                         uint16_t max_value);
/* Clamps to [0, max_value]. Healing past the ghost pulls the ghost up with it,
 * damage leaves it behind for the drain animation to eat. */
void vxpe_hud_gauge_set(VxpeHudGauge2D* g, uint16_t value);
/* Decays flash_ms and walks the ghost toward value. */
void vxpe_hud_gauge_update(VxpeHudGauge2D* g, uint16_t dt_ms);
void vxpe_hud_gauge_flash(VxpeHudGauge2D* g, uint8_t ms);
void vxpe_hud_gauge_draw(uint16_t* fb, int fb_w, int fb_h, const VxpeHudGauge2D* g);

/* 1 while `value` is at or below `low_at` percent - drives a critical-health
 * blink in the game instead of another field. */
int vxpe_hud_gauge_is_low(const VxpeHudGauge2D* g);

/* --- icon rows (hearts, lives, keys) -------------------------------------- */

typedef struct VxpeHudIconRow2D {
    const VxpeSprite565* full;
    const VxpeSprite565* empty; /* NULL = full art tinted to color_empty */
    int16_t x, y;
    uint16_t color_empty;       /* used only when empty is NULL */
    uint16_t value, max;
    uint8_t per_row;            /* icons per row before wrapping; 0 = one row */
    int8_t pitch_x, pitch_y;    /* px between icons; <=0 = sprite size + 2 */
    uint8_t grow;               /* 1 = the row grows leftward from x, for a right-hand HUD */
} VxpeHudIconRow2D;

void vxpe_hud_icon_row_init(VxpeHudIconRow2D* row, const VxpeSprite565* full,
                            const VxpeSprite565* empty, int x, int y,
                            uint16_t max);
/* value is clamped to [0, max] at draw time, never at set time, so an
 * over-cap pickup can still be shown by a game that reads row->value. */
void vxpe_hud_icon_row_set(VxpeHudIconRow2D* row, uint16_t value);
int vxpe_hud_icon_row_draw(uint16_t* fb, int fb_w, int fb_h,
                           const VxpeHudIconRow2D* row); /* returns icons drawn */

/* --- boss name plate ------------------------------------------------------ */

#define VXPE_BOSS_PLATE_NAME_MAX 32

typedef struct VxpeHudBossPlate2D {
    VxpeHudGauge2D gauge;   /* the health bar itself, already positioned */
    char name[VXPE_BOSS_PLATE_NAME_MAX];
    int16_t plate_y;        /* top y the plate rests at */
    int16_t slide_y;        /* current top y while it arrives or retreats */
    uint16_t hide_ms;       /* countdown to the retreat, in ms */
    uint16_t show_ms;       /* how long it holds after each damage; init gives 2500 */
    uint8_t alpha;          /* 255 solid, drops toward 0 while leaving */
    uint8_t state;          /* 0 hidden, 1 arriving, 2 shown, 3 leaving */
} VxpeHudBossPlate2D;

/* Centres a plate near the bottom of a `fb_w` x `fb_h` screen with a 10 px bar,
 * hidden. max_hp is the boss's full health in gauge units. */
void vxpe_hud_boss_init(VxpeHudBossPlate2D* p, int fb_w, int fb_h, uint16_t max_hp);
/* Reveals the plate with a name (NULL keeps the current one) and sets health.
 * Calling it while the plate is already out just refreshes the hold timer. */
void vxpe_hud_boss_show(VxpeHudBossPlate2D* p, const char* name, uint16_t hp);
/* Damage the bar and restart the hold timer. On a hidden plate only the number
 * moves, so a fight the player never sees stays invisible until boss_show. */
void vxpe_hud_boss_set_hp(VxpeHudBossPlate2D* p, uint16_t hp);
void vxpe_hud_boss_hide(VxpeHudBossPlate2D* p);
/* Runs the slide, the hold countdown and the fade. The gauge's own damage ghost
 * is updated here too, so a game that only calls this gets both animations. */
void vxpe_hud_boss_update(VxpeHudBossPlate2D* p, uint16_t dt_ms);
/* Nothing is drawn while hidden. name_style NULL uses the house default face;
 * the plate's height follows the face, so a 2x display font cannot overlap the
 * bar. While leaving, the plate dims its own colours instead of blending with
 * the world behind it. */
void vxpe_hud_boss_draw(uint16_t* fb, int fb_w, int fb_h,
                        const VxpeHudBossPlate2D* p, const VxpeFontStyle* name_style);

/* --- corner minimap ------------------------------------------------------- */

#define VXPE_MINIMAP_W_MAX 40
#define VXPE_MINIMAP_H_MAX 30
#define VXPE_MINIMAP_BYTES ((VXPE_MINIMAP_W_MAX * VXPE_MINIMAP_H_MAX + 7) / 8)

/* Per-room tags the map can draw distinctly; id 0 in `rooms` is always void.
 * A room nobody has walked into yet is not a tag - it comes from the visited
 * bitset, so the level data stays const while exploration is state. */
enum VxpeMinimapTag2D {
    VXPE_MM_NONE = 0,
    VXPE_MM_BOSS = 1,
    VXPE_MM_SAVE = 2,
    VXPE_MM_SHOP = 4
};

typedef struct VxpeHudMinimap2D {
    const uint8_t* rooms;  /* room ids, width*height, 0 = void */
    const uint8_t* tags;   /* width*height VxpeMinimapTag2D bits, or NULL */
    uint16_t color_bg, color_room, color_edge, color_here, color_boss, color_save,
             color_shop;
    int16_t x, y;
    uint8_t width, height; /* rooms */
    uint8_t cell;          /* px per room cell */
    uint8_t visited[VXPE_MINIMAP_BYTES]; /* one bit per room, revealed by mark */
} VxpeHudMinimap2D;

/* Everything starts unrevealed. `cell` is clamped to 2..8 px so a 40x30 map
 * still fits a 240 px screen, and out-of-range dimensions zero the map rather
 * than overflowing the visited bitset. */
void vxpe_hud_minimap_init(VxpeHudMinimap2D* mm, const uint8_t* rooms,
                           const uint8_t* tags, int width, int height,
                           int cell_px, int x, int y);
void vxpe_hud_minimap_mark(VxpeHudMinimap2D* mm, int rx, int ry);
int vxpe_hud_minimap_seen(const VxpeHudMinimap2D* mm, int rx, int ry);
/* Draws every revealed room, its tag marks, and the position pip. cur_rx or
 * cur_ry out of range hides the pip. */
void vxpe_hud_minimap_draw(uint16_t* fb, int fb_w, int fb_h,
                           const VxpeHudMinimap2D* mm, int cur_rx, int cur_ry);

/* --- text helpers --------------------------------------------------------- */

/* Centres on cx and right-aligns to `right`, both using the style's measured
 * logical width so a shadow does not push the text off its anchor. */
void vxpe_hud_text_center(uint16_t* fb, int fb_w, int fb_h, int cx, int y,
                          const char* text, const VxpeFontStyle* style);
void vxpe_hud_text_right(uint16_t* fb, int fb_w, int fb_h, int right, int y,
                         const char* text, const VxpeFontStyle* style);

/* Writes a signed decimal into buf, zero-padded to min_digits, and returns the
 * number of characters written (excluding the terminator). No sprintf, because
 * the MRE C library drags in a heap it does not have. A buffer too small keeps
 * the value truncated to fit and still terminates. */
int vxpe_hud_format_int(char* buf, int cap, int32_t value, int min_digits);

#ifdef __cplusplus
} /* extern "C" */
#endif
