/* VxpStage2D - fixed-memory fighting/arcade stage compositor for MRE/VXP. */
#pragma once

#include <stdint.h>
#include "graphics/VxpRender2D.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct VxpeStageCamera2D {
    int32_t x_q8;
    int32_t min_x_q8;
    int32_t max_x_q8;
    int16_t viewport_w;
    int16_t deadzone_left;
    int16_t deadzone_right;
} VxpeStageCamera2D;

typedef struct VxpeStageBand2D {
    VxpeRectI src;
    int16_t dst_y;
    uint16_t dst_h;
    uint16_t parallax_q8;  /* 256 = follows camera 1:1 */
    int16_t scroll_x;
    int16_t scroll_y;
    uint16_t tint565;
    uint8_t alpha;
    uint8_t blend;
    uint8_t repeat_x;
    uint8_t raster_wave;
    int8_t wave_amplitude;
    uint8_t wave_phase;
    uint8_t wave_shift;    /* scanline period uses y >> wave_shift */
} VxpeStageBand2D;

void vxpe_stage_camera_init(
    VxpeStageCamera2D* camera, int viewport_w, int world_w);

void vxpe_stage_camera_follow(
    VxpeStageCamera2D* camera, int target_world_x, uint16_t smooth_q8);

int vxpe_stage_world_to_screen_x(
    const VxpeStageCamera2D* camera, int world_x);

void vxpe_stage_draw_band565(
    uint16_t* fb, int fb_w, int fb_h,
    const VxpeSprite565* sprite,
    const VxpeStageCamera2D* camera,
    const VxpeStageBand2D* band);

/* Low-cost 16-step colour cycle helper for water/sky grading. */
uint16_t vxpe_stage_cycle565(
    uint16_t color_a, uint16_t color_b, uint8_t phase);

#ifdef __cplusplus
}
#endif
