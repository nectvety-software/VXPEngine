/*
 * Copyright (c) 2026 PixelRoot32
 * Licensed under the MIT License
 *
 * VxpRender2D: full-colour RGB565 rendering helpers for MediaTek MRE/VXP.
 *
 * The API is intentionally C-compatible so games generated from the default
 * C template can use the same core as C++ scenes. All hot paths are
 * allocation-free and use integer math.
 */
#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct VxpeRectI {
    int16_t x;
    int16_t y;
    int16_t w;
    int16_t h;
} VxpeRectI;

/*
 * Full-colour RGB565 sprite. mask is optional, 1 bit per source pixel,
 * MSB first. stride is measured in pixels; 0 means width.
 */
typedef struct VxpeSprite565 {
    const uint16_t* pixels;
    const uint8_t* mask;
    uint16_t width;
    uint16_t height;
    uint16_t stride;
    uint8_t opaque;
} VxpeSprite565;

typedef enum VxpeBlendMode {
    VXPE_BLEND_COPY = 0,
    VXPE_BLEND_ALPHA = 1,
    VXPE_BLEND_ADD = 2,
    VXPE_BLEND_MULTIPLY = 3
} VxpeBlendMode;

typedef struct VxpeBlit565 {
    VxpeRectI src;
    int16_t dst_x;
    int16_t dst_y;
    uint16_t dst_w;
    uint16_t dst_h;
    uint16_t tint565;   /* 0xFFFF = neutral */
    uint8_t alpha;      /* 0..255 */
    uint8_t blend;      /* VxpeBlendMode */
    uint8_t flip_x;
    uint8_t flip_y;
    uint8_t flip_d;     /* Tiled diagonal x/y-axis swap before H/V flips. */
    int16_t clip_x;     /* clip_w/clip_h == 0 means full framebuffer */
    int16_t clip_y;
    uint16_t clip_w;
    uint16_t clip_h;
} VxpeBlit565;

/*
 * Atlas animation. frames points at frame_count source rectangles.
 * durations_ms may be NULL; then frame_ms is used for every frame.
 * loop=0 stops on the final frame. ping_pong=1 reverses at the ends.
 */
typedef struct VxpeAnimClip {
    const VxpeRectI* frames;
    const uint16_t* durations_ms;
    uint16_t frame_count;
    uint16_t frame_ms;
    uint8_t loop;
    uint8_t ping_pong;
} VxpeAnimClip;

typedef struct VxpeAnimState {
    uint16_t frame;
    uint16_t elapsed_ms;
    int8_t direction;
    uint8_t finished;
} VxpeAnimState;

/* RGB888 -> RGB565 convenience helper. */
uint16_t vxpe2d_rgb565(uint8_t r, uint8_t g, uint8_t b);

/* Multiply an RGB565 colour by an RGB565 tint (0xFFFF = neutral). */
uint16_t vxpe2d_tint565(uint16_t color, uint16_t tint);

/*
 * Parse VXPEngine .raw design sprite:
 *   byte 0..1 width LE, 2..3 height LE, 4 opaque flag,
 *   byte 8.. RGB565 pixels, then optional 1-bit visibility mask.
 * Returns 1 on success and 0 on invalid/truncated data.
 */
int vxpe2d_sprite_from_raw(const void* data, uint32_t size, VxpeSprite565* out);

/* Fast solid rectangle with framebuffer clipping. */
void vxpe2d_fill_rect(
    uint16_t* fb, int fb_w, int fb_h,
    int x, int y, int w, int h, uint16_t color);

/* Vertical RGB565 gradient, clipped to the framebuffer. */
void vxpe2d_gradient_vertical(
    uint16_t* fb, int fb_w, int fb_h,
    int x, int y, int w, int h,
    uint16_t top_color, uint16_t bottom_color);

/* Blend a solid colour over a rectangle. */
void vxpe2d_overlay_rect(
    uint16_t* fb, int fb_w, int fb_h,
    int x, int y, int w, int h,
    uint16_t color, uint8_t alpha, uint8_t blend_mode);

/*
 * Full sprite blitter: crop/source rectangle, nearest-neighbour scale,
 * horizontal/vertical flip, tint and blend. Empty/invalid src means the full
 * sprite. dst_w/dst_h=0 means source size.
 */
void vxpe2d_blit(
    uint16_t* fb, int fb_w, int fb_h,
    const VxpeSprite565* sprite, const VxpeBlit565* op);

/* Convenience unscaled copy using the full sprite. */
void vxpe2d_blit_simple(
    uint16_t* fb, int fb_w, int fb_h,
    const VxpeSprite565* sprite, int x, int y);

/*
 * Repeat a sprite horizontally as a parallax layer. camera_x_q8 and
 * parallax_q8 use Q8.8 pixels/factor (256 = 1.0). world_y is screen-space Y.
 * repeat_width <= 0 uses sprite width. max_tiles is a safety cap; <=0 uses 32.
 */
void vxpe2d_blit_parallax_x(
    uint16_t* fb, int fb_w, int fb_h,
    const VxpeSprite565* sprite,
    int32_t camera_x_q8, uint16_t parallax_q8,
    int world_y, int repeat_width, int max_tiles);

/*
 * Additive radial light. Pixels inside radius are blended toward light_color;
 * intensity is strongest at the centre and falls off quadratically.
 */
void vxpe2d_radial_light(
    uint16_t* fb, int fb_w, int fb_h,
    int center_x, int center_y, int radius,
    uint16_t light_color, uint8_t intensity);

/*
 * Faster low-power glow using a Manhattan/diamond distance approximation.
 * Avoids per-pixel squared-distance math and is intended for MRE/VXP effects.
 */
void vxpe2d_radial_light_fast(
    uint16_t* fb, int fb_w, int fb_h,
    int center_x, int center_y, int radius,
    uint16_t light_color, uint8_t intensity);

/*
 * Perspective floor / road renderer for OutRun-style pseudo-3D.
 * The texture repeats in X/Y. far_width is the strip width at horizon_y,
 * near_width at bottom_y. scroll_x/scroll_y are texture pixel offsets.
 * bend_q8 shifts the road centre progressively; 256 means ~1 pixel of shift
 * per scanline at maximum depth.
 */
void vxpe2d_perspective_floor(
    uint16_t* fb, int fb_w, int fb_h,
    const VxpeSprite565* texture,
    int center_x, int horizon_y, int bottom_y,
    int far_width, int near_width,
    int scroll_x, int scroll_y, int16_t bend_q8);

/* Animation helpers; zero allocation, caller owns clip/state. */
void vxpe2d_anim_reset(VxpeAnimState* state);
void vxpe2d_anim_update(
    VxpeAnimState* state, const VxpeAnimClip* clip, uint16_t delta_ms);
VxpeRectI vxpe2d_anim_frame_rect(
    const VxpeAnimState* state, const VxpeAnimClip* clip);

/* Build a blit operation for the current animation frame. */
VxpeBlit565 vxpe2d_anim_blit(
    const VxpeAnimState* state, const VxpeAnimClip* clip,
    int x, int y, uint16_t dst_w, uint16_t dst_h);

/* Exact nearest-neighbour 2x upscale into caller-owned destination.
 * src/dst must be disjoint; dst dimensions must equal 2*src dimensions.
 * Returns 0 without writing for invalid dimensions/pointers. */
int vxpe2d_upscale2x565(uint16_t* dst,int dst_w,int dst_h,const uint16_t* src,int src_w,int src_h);

/* Palette-preserving Scale2x: refines diagonals from four neighbours,
 * using the same disjoint buffers/dimension limits as upscale2x565. */
int vxpe2d_scale2x565(uint16_t* dst,int dst_w,int dst_h,const uint16_t* src,int src_w,int src_h);

#ifdef __cplusplus
} /* extern "C" */
#endif
