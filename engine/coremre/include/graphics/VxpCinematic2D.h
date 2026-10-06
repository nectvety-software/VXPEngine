/*
 * VxpCinematic2D - C-compatible camera impact + hit-stop for MRE/VXP.
 * Fixed memory, integer math, no heap.
 */
#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct VxpeCinematic2D {
    uint32_t rng;
    uint16_t shake_left_ms;
    uint16_t shake_total_ms;
    uint16_t punch_left_ms;
    uint16_t punch_total_ms;
    uint16_t hitstop_left_ms;
    uint8_t shake_amplitude;
    int16_t punch_x_q8;
    int16_t punch_y_q8;
    int16_t offset_x;
    int16_t offset_y;
} VxpeCinematic2D;

void vxpe2d_cinematic_init(VxpeCinematic2D* fx, uint32_t seed);
void vxpe2d_cinematic_clear(VxpeCinematic2D* fx);

void vxpe2d_cinematic_shake(
    VxpeCinematic2D* fx, uint8_t amplitude_px, uint16_t duration_ms);

void vxpe2d_cinematic_punch(
    VxpeCinematic2D* fx,
    int16_t x_q8, int16_t y_q8,
    uint16_t duration_ms);

void vxpe2d_cinematic_hitstop(
    VxpeCinematic2D* fx, uint16_t duration_ms);

/*
 * Advance real-time effects. Return the dt that should be applied to gameplay:
 * 0 while hit-stop is active, real_dt_ms otherwise.
 * Camera offset is updated even during hit-stop.
 */
uint16_t vxpe2d_cinematic_update(
    VxpeCinematic2D* fx, uint16_t real_dt_ms);

void vxpe2d_cinematic_offset(
    const VxpeCinematic2D* fx, int16_t* out_x, int16_t* out_y);

uint8_t vxpe2d_cinematic_is_hitstopped(const VxpeCinematic2D* fx);

/*
 * Shift a framebuffer gameplay region in-place by camera offset.
 * clip_h lets HUD rows remain fixed. Exposed pixels are filled with clear565.
 */
void vxpe2d_cinematic_shift_rgb565(
    uint16_t* fb, int fb_w, int fb_h, int clip_h,
    int offset_x, int offset_y, uint16_t clear565);

#ifdef __cplusplus
}
#endif
