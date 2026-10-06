/*
 * VxpLight2D - low-resolution coloured lightmap for MRE/VXP.
 * Fixed memory, C-compatible, intended for QVGA dynamic lighting/bloom proxy.
 */
#pragma once
#include <stdint.h>
#include "graphics/VxpRender2D.h"

#ifdef __cplusplus
extern "C" {
#endif

#ifndef VXPE_LIGHTMAP_MAX_PIXELS
#define VXPE_LIGHTMAP_MAX_PIXELS 4800
#endif

typedef struct VxpeLightmap2D {
    uint16_t cells[VXPE_LIGHTMAP_MAX_PIXELS];
    uint16_t width;
    uint16_t height;
    uint16_t screen_w;
    uint16_t screen_h;
    uint8_t valid;
} VxpeLightmap2D;

/* Returns 1 when dimensions fit the fixed buffer. QVGA default: 60x80. */
int vxpe2d_lightmap_init(
    VxpeLightmap2D* lm,
    uint16_t map_w, uint16_t map_h,
    uint16_t screen_w, uint16_t screen_h);

void vxpe2d_lightmap_clear(VxpeLightmap2D* lm);

/* Coordinates/radius are in screen pixels. Multiple lights accumulate. */
void vxpe2d_lightmap_add_radial(
    VxpeLightmap2D* lm,
    int screen_x, int screen_y, int screen_radius,
    uint16_t color565, uint8_t intensity);

/* Low-resolution glow along a screen-space line/beam. */
void vxpe2d_lightmap_add_beam(
    VxpeLightmap2D* lm,
    int x0, int y0, int x1, int y1,
    int radius_px,
    uint16_t color565, uint8_t intensity);

/*
 * Composite only non-black lightmap cells as scaled additive blocks.
 * clip_h can exclude a HUD (e.g. 240 for a 240x320 screen); <=0 uses screen_h.
 */
void vxpe2d_lightmap_composite_add(
    const VxpeLightmap2D* lm,
    uint16_t* fb, int fb_w, int fb_h,
    uint8_t global_alpha, int clip_h);

#ifdef __cplusplus
}
#endif
