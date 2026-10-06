/*
 * VxpScene25D - fixed-memory 2.5D scene primitives for MediaTek MRE/VXP.
 *
 * Designed for low-resolution perspective scenes such as The Water Museum:
 * projected billboards, textured trapezoid planes, ground shadows, rope/line
 * primitives and low-cost atmosphere/colour grading.  Integer/fixed-point
 * hot paths, no per-frame heap allocation.
 */
#pragma once

#include <stdint.h>
#include "graphics/VxpSpriteFx.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct VxpeCamera25D {
    int32_t world_x;
    int32_t world_y;
    int32_t world_z;
    int16_t center_x;
    int16_t horizon_y;
    uint16_t focal_q8;       /* focal length in pixels, Q8.8 */
    uint16_t near_z;
    uint16_t far_z;
    uint16_t min_scale_q8;
    uint16_t max_scale_q8;
    uint16_t fog_near_z;
    uint16_t fog_far_z;
    uint16_t fog_color565;
    uint8_t fog_strength;
} VxpeCamera25D;

typedef struct VxpeProjected25D {
    int16_t x;
    int16_t y;
    uint16_t scale_q8;
    uint16_t depth;
    uint8_t fog_alpha;
    uint8_t visible;
} VxpeProjected25D;

typedef struct VxpeBillboard25D {
    VxpeRectI src;
    int32_t world_x;
    int32_t world_y;
    int32_t world_z;
    uint16_t world_w;
    uint16_t world_h;
    uint16_t pivot_x_q8;     /* 0=left, 128=center, 256=right */
    uint16_t pivot_y_q8;     /* 0=top, 256=bottom */
    uint16_t tint565;
    uint8_t alpha;
    uint8_t blend;
    uint8_t flip_x;
    uint8_t flip_y;
} VxpeBillboard25D;

typedef struct VxpePlane25D {
    VxpeRectI src;
    int16_t center_x;
    int16_t top_y;
    int16_t bottom_y;
    uint16_t top_width;
    uint16_t bottom_width;
    uint16_t tint565;
    uint8_t alpha;
    uint8_t blend;
    int8_t ripple_amplitude;
    uint8_t ripple_phase;
    uint8_t ripple_wavelength_shift;
} VxpePlane25D;

typedef struct VxpeRopeStyle25D {
    uint16_t outer_color565;
    uint16_t core_color565;
    uint8_t outer_width;
    uint8_t core_width;
    uint8_t alpha;
    uint8_t blend;
} VxpeRopeStyle25D;

typedef struct VxpeGrade25D {
    uint16_t tint565;
    uint8_t tint_alpha;
    uint8_t vignette_alpha;
    uint8_t dither_strength;
    uint8_t fog_horizon_alpha;
} VxpeGrade25D;

void vxpe25d_camera_init(
    VxpeCamera25D* camera,
    int screen_w, int screen_h,
    int horizon_y, int focal_px);

int vxpe25d_project(
    const VxpeCamera25D* camera,
    int32_t world_x, int32_t world_y, int32_t world_z,
    VxpeProjected25D* out);

uint16_t vxpe25d_fog_tint(
    const VxpeCamera25D* camera,
    uint16_t base_tint565,
    uint8_t fog_alpha);

int vxpe25d_draw_billboard(
    uint16_t* fb, int fb_w, int fb_h,
    const VxpeCamera25D* camera,
    const VxpeSpriteA8* sprite,
    const VxpeBillboard25D* billboard);

void vxpe25d_draw_plane(
    uint16_t* fb, int fb_w, int fb_h,
    const VxpeSpriteA8* sprite,
    const VxpePlane25D* plane);

void vxpe25d_draw_ground_shadow(
    uint16_t* fb, int fb_w, int fb_h,
    const VxpeCamera25D* camera,
    int32_t world_x, int32_t world_z,
    uint16_t radius_x, uint16_t radius_y,
    uint16_t color565, uint8_t alpha, uint8_t blend_mode);

int vxpe25d_draw_rope_world(
    uint16_t* fb, int fb_w, int fb_h,
    const VxpeCamera25D* camera,
    int32_t x0, int32_t y0, int32_t z0,
    int32_t x1, int32_t y1, int32_t z1,
    const VxpeRopeStyle25D* style);

void vxpe25d_apply_grade(
    uint16_t* fb, int fb_w, int fb_h,
    const VxpeGrade25D* grade,
    int horizon_y);

#ifdef __cplusplus
} /* extern "C" */
#endif
