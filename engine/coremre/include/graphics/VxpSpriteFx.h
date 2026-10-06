/*
 * Copyright (c) 2026 PixelRoot32
 * Licensed under the MIT License
 *
 * VxpSpriteFx: high-quality software sprite compositing for MRE/VXP.
 * RGB565 colour + optional A8 per-pixel alpha, outline, soft shadow, glow,
 * depth-sorted fixed command batch. C-compatible and zero-heap at runtime.
 */
#pragma once

#include <stdint.h>
#include "graphics/VxpRender2D.h"

#ifdef __cplusplus
extern "C" {
#endif

#ifndef VXPE_SPRITE_BATCH_MAX
#define VXPE_SPRITE_BATCH_MAX 48
#endif

typedef struct VxpeSpriteA8 {
    const uint16_t* pixels;
    const uint8_t* alpha;
    uint16_t width;
    uint16_t height;
    uint16_t stride;
    uint16_t alpha_stride;
    uint8_t opaque;
} VxpeSpriteA8;

/*
 * VXA8 file/resource layout (little endian):
 *   0..3   "VXA8"
 *   4..5   width
 *   6..7   height
 *   8      flags (bit0 = fully opaque)
 *   9      version (=1)
 *   10..11 header size (=12)
 *   12..   RGB565 pixels, width*height*2
 *   then   A8 alpha, width*height bytes, omitted when opaque
 */
int vxpe2d_sprite_a8_from_vxa8(
    const void* data, uint32_t size, VxpeSpriteA8* out);

/* Draw RGB565+A8 with crop/scale/flip/tint/global alpha/blend. */
void vxpe2d_blit_a8(
    uint16_t* fb, int fb_w, int fb_h,
    const VxpeSpriteA8* sprite, const VxpeBlit565* op);

/* Draw the current VxpeAnimClip frame directly from a VXA8 sprite/atlas. */
void vxpe2d_anim_draw_a8(
    uint16_t* fb, int fb_w, int fb_h,
    const VxpeSpriteA8* sprite,
    const VxpeAnimState* state, const VxpeAnimClip* clip,
    int x, int y, uint16_t dst_w, uint16_t dst_h,
    uint16_t tint565, uint8_t alpha, uint8_t blend_mode,
    uint8_t flip_x, uint8_t flip_y);

/*
 * Draw the sprite's A8 coverage as a solid colour. Useful for cheap drop
 * shadows, hit flashes, team highlights and selection silhouettes.
 * offset is applied after op.dst_x/op.dst_y. This is a single-pass effect.
 */
void vxpe2d_blit_a8_silhouette(
    uint16_t* fb, int fb_w, int fb_h,
    const VxpeSpriteA8* sprite, const VxpeBlit565* op,
    int offset_x, int offset_y,
    uint16_t color, uint8_t alpha, uint8_t blend_mode);

/*
 * Draw a full-colour isometric tile layer from a VXA8 atlas.
 * tile_ids is row-major; each ID selects a tile frame from atlas_columns.
 * Tiles are drawn in painter order. empty_id entries are skipped.
 */
void vxpe2d_draw_isometric_a8(
    uint16_t* fb, int fb_w, int fb_h,
    const VxpeSpriteA8* atlas,
    const uint16_t* tile_ids,
    uint16_t map_w, uint16_t map_h,
    uint16_t tile_w, uint16_t tile_h,
    uint16_t atlas_columns,
    int origin_x, int origin_y,
    uint16_t empty_id);

/* Effect style. Set fields to 0 to disable an effect. */
typedef struct VxpeSpriteFxStyle {
    int8_t shadow_dx;
    int8_t shadow_dy;
    uint8_t shadow_alpha;
    uint8_t shadow_softness; /* 0..3 px */
    uint16_t shadow_color;

    uint8_t outline_px;      /* 0..3 px */
    uint8_t outline_alpha;
    uint16_t outline_color;

    uint8_t glow_px;         /* 0..4 px */
    uint8_t glow_alpha;
    uint16_t glow_color;
} VxpeSpriteFxStyle;

/*
 * Composite in order: soft shadow -> additive glow -> outline -> sprite.
 * Intended for hero/NPC/object rendering at QVGA.
 */
void vxpe2d_draw_sprite_fx(
    uint16_t* fb, int fb_w, int fb_h,
    const VxpeSpriteA8* sprite,
    const VxpeBlit565* op,
    const VxpeSpriteFxStyle* style);

typedef struct VxpeSpriteDrawCmd {
    const VxpeSpriteA8* sprite;
    VxpeBlit565 op;
    VxpeSpriteFxStyle style;
    int16_t z;
    uint8_t use_fx;
} VxpeSpriteDrawCmd;

typedef struct VxpeSpriteBatch {
    VxpeSpriteDrawCmd commands[VXPE_SPRITE_BATCH_MAX];
    uint16_t count;
    uint16_t dropped;
} VxpeSpriteBatch;

void vxpe2d_batch_init(VxpeSpriteBatch* batch);
int vxpe2d_batch_push(
    VxpeSpriteBatch* batch,
    const VxpeSpriteA8* sprite,
    const VxpeBlit565* op,
    int16_t z,
    const VxpeSpriteFxStyle* style);

/* Stable insertion-sort by z, then draw. Clears count but preserves dropped. */
void vxpe2d_batch_flush(
    VxpeSpriteBatch* batch,
    uint16_t* fb, int fb_w, int fb_h);

#ifdef __cplusplus
} /* extern "C" */
#endif
