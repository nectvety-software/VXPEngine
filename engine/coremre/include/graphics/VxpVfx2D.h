/*
 * VxpVfx2D - fixed-memory 2D VFX primitives for MediaTek MRE/VXP.
 * C-compatible. Integer/fixed-point hot paths, no heap allocation per frame.
 */
#pragma once

#include <stdint.h>
#include "graphics/VxpSpriteFx.h"

#ifdef __cplusplus
extern "C" {
#endif

#ifndef VXPE_TRAIL_MAX_POINTS
#define VXPE_TRAIL_MAX_POINTS 24
#endif

typedef struct VxpeTrailPoint {
    int16_t x;
    int16_t y;
    uint16_t age_ms;
} VxpeTrailPoint;

typedef struct VxpeTrail2D {
    VxpeTrailPoint points[VXPE_TRAIL_MAX_POINTS];
    uint16_t count;
    uint16_t lifetime_ms;
    uint16_t head_color;
    uint16_t tail_color;
    uint8_t head_width;
    uint8_t tail_width;
    uint8_t alpha;
    uint8_t blend;
} VxpeTrail2D;

typedef struct VxpeBeamStyle {
    uint16_t outer_color;
    uint16_t core_color;
    uint16_t hot_color;
    uint8_t outer_width;
    uint8_t core_width;
    uint8_t hot_width;
    uint8_t alpha;
    uint8_t blend;
} VxpeBeamStyle;

void vxpe2d_trail_init(
    VxpeTrail2D* trail,
    uint16_t lifetime_ms,
    uint16_t head_color,
    uint16_t tail_color,
    uint8_t head_width,
    uint8_t tail_width,
    uint8_t alpha,
    uint8_t blend_mode);

void vxpe2d_trail_reset(VxpeTrail2D* trail);
void vxpe2d_trail_push(VxpeTrail2D* trail, int x, int y);
void vxpe2d_trail_update(VxpeTrail2D* trail, uint16_t delta_ms);
void vxpe2d_trail_draw(
    const VxpeTrail2D* trail,
    uint16_t* fb, int fb_w, int fb_h);

/* Multi-layer beam. Intended for plasma/laser/magic attacks. */
void vxpe2d_draw_beam(
    uint16_t* fb, int fb_w, int fb_h,
    int x0, int y0, int x1, int y1,
    const VxpeBeamStyle* style);

/*
 * Ring/shield primitive. thickness >= 1. start/end alpha are combined with
 * edge coverage; blend is usually ALPHA or ADD.
 */
void vxpe2d_draw_ring(
    uint16_t* fb, int fb_w, int fb_h,
    int cx, int cy, int radius, int thickness,
    uint16_t color, uint8_t alpha, uint8_t blend_mode);

/* Deterministic radial hit burst with 4/8/12/16 rays. phase is 0..15. */
void vxpe2d_draw_burst(
    uint16_t* fb, int fb_w, int fb_h,
    int cx, int cy,
    int inner_radius, int outer_radius,
    uint8_t rays, uint8_t phase,
    uint16_t color, uint8_t alpha, uint8_t blend_mode);

/*
 * Rotate an A8 sprite around the centre of op->dst rectangle.
 * sin_q14/cos_q14 use Q2.14 (-16384..16384). Scaling/crop/flip/tint from op
 * are preserved. Best for small projectiles, weapon sprites and spell glyphs.
 */
void vxpe2d_blit_a8_rot_q14(
    uint16_t* fb, int fb_w, int fb_h,
    const VxpeSpriteA8* sprite,
    const VxpeBlit565* op,
    int16_t sin_q14, int16_t cos_q14);

/*
 * Per-scanline horizontal sine distortion for water/lava/energy backgrounds.
 * phase is 0..255, amplitude in pixels. Full sprite op semantics are used,
 * except rotation is not applied.
 */
void vxpe2d_blit_a8_wave_x(
    uint16_t* fb, int fb_w, int fb_h,
    const VxpeSpriteA8* sprite,
    const VxpeBlit565* op,
    uint8_t phase, uint8_t amplitude_px, uint8_t wavelength_shift);

/*
 * Native-size A8 tiled parallax layer. Camera and factors use Q8.8.
 * factor 256 = full camera speed, 128 = half speed. repeat_x/repeat_y can
 * independently disable wrapping. max_tiles is a safety cap; <=0 uses 64.
 */
void vxpe2d_blit_a8_parallax(
    uint16_t* fb, int fb_w, int fb_h,
    const VxpeSpriteA8* sprite,
    int32_t camera_x_q8, int32_t camera_y_q8,
    uint16_t factor_x_q8, uint16_t factor_y_q8,
    int offset_x, int offset_y,
    uint8_t alpha, uint8_t blend_mode,
    uint8_t repeat_x, uint8_t repeat_y,
    int max_tiles);

#ifdef __cplusplus
} /* extern "C" */
#endif
