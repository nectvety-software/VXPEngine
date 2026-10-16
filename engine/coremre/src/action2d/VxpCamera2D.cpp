/*
 * Copyright (c) 2026 PixelRoot32
 * Licensed under the MIT License
 *
 * VxpCamera2D implementation. Integer only: the follow gain is a linear
 * approximation of exponential easing (dt*256/follow_ms, capped at 256), which
 * is stable for the 20-50 ms steps a handset actually produces and costs one
 * divide per axis per frame.
 */
#include "action2d/VxpCamera2D.h"

#include <stddef.h>
#include <string.h>

namespace {

inline int clamp_i(int v, int lo, int hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

inline int32_t clamp_q8(int32_t v, int32_t lo, int32_t hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

/* xorshift32: no libc dependency, period 2^32-1, and the state lives in the
 * camera struct so two runs of the same input produce the same frames. */
inline uint32_t xorshift32(uint32_t* state) {
    uint32_t x = *state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *state = x;
    return x;
}

/* Eases `current` toward `desired` with a time constant of tau_ms. */
inline int32_t ease_q8(int32_t current, int32_t desired, uint16_t dt_ms, uint16_t tau_ms) {
    if (tau_ms == 0 || dt_ms >= tau_ms) return desired;
    const int32_t gain = ((int32_t)dt_ms << 8) / (int32_t)tau_ms;
    const int32_t step = (int32_t)(((int64_t)(desired - current) * gain) >> 8);
    /* Once the step truncates to zero the target is less than a pixel away, so
     * close it instead of stalling: a camera that stops one Q8 unit short of
     * its world edge never reaches it, and a follow target would keep a
     * permanent offset. */
    if (step == 0) return desired;
    return current + step;
}

}  // namespace

extern "C" {

void vxpe_cam_init(
    VxpeCamera2D* cam, int view_w, int view_h, int world_w, int world_h) {
    if (cam == nullptr) return;
    memset(cam, 0, sizeof(*cam));

    if (view_w < 1) view_w = 1;
    if (view_h < 1) view_h = 1;
    if (world_w < 0) world_w = 0;
    if (world_h < 0) world_h = 0;

    cam->view_w = (uint16_t)view_w;
    cam->view_h = (uint16_t)view_h;

    /* A world narrower than the viewport centres instead of jittering between
     * an inverted clamp window. */
    const int span_x = world_w - view_w;
    const int span_y = world_h - view_h;
    cam->min_x_q8 = span_x > 0 ? 0 : ((int32_t)span_x << 7);
    cam->max_x_q8 = span_x > 0 ? ((int32_t)span_x << 8) : ((int32_t)span_x << 7);
    cam->min_y_q8 = span_y > 0 ? 0 : ((int32_t)span_y << 7);
    cam->max_y_q8 = span_y > 0 ? ((int32_t)span_y << 8) : ((int32_t)span_y << 7);

    cam->dead_l = (int16_t)(view_w * 30 / 100);
    cam->dead_r = (int16_t)(view_w * 30 / 100);
    cam->dead_t = (int16_t)(view_h * 35 / 100);
    cam->dead_b = (int16_t)(view_h * 35 / 100);
    cam->follow_ms = 90;
    cam->shake_step_ms = 32;
    cam->seed = 0x9E3779B9u;
}

void vxpe_cam_set_deadzone(VxpeCamera2D* cam, int left, int right, int top, int bottom) {
    if (cam == nullptr) return;
    cam->dead_l = (int16_t)clamp_i(left, 0, cam->view_w);
    cam->dead_r = (int16_t)clamp_i(right, 0, cam->view_w);
    cam->dead_t = (int16_t)clamp_i(top, 0, cam->view_h);
    cam->dead_b = (int16_t)clamp_i(bottom, 0, cam->view_h);
}

void vxpe_cam_set_follow_ms(VxpeCamera2D* cam, uint16_t follow_ms) {
    if (cam != nullptr) cam->follow_ms = follow_ms;
}

void vxpe_cam_set_lookahead(VxpeCamera2D* cam, int pixels) {
    if (cam == nullptr) return;
    cam->look_target_q8 = (int32_t)pixels << 8;
}

void vxpe_cam_snap(VxpeCamera2D* cam, int target_x, int target_y) {
    if (cam == nullptr) return;
    cam->x_q8 = clamp_q8(((int32_t)target_x - (int32_t)cam->view_w / 2) << 8,
                         cam->min_x_q8, cam->max_x_q8);
    cam->y_q8 = clamp_q8(((int32_t)target_y - (int32_t)cam->view_h / 2) << 8,
                         cam->min_y_q8, cam->max_y_q8);
    cam->shake_amp_q8 = 0;
    cam->shake_ms = 0;
    cam->shake_x_q8 = 0;
    cam->shake_y_q8 = 0;
}

void vxpe_cam_follow(VxpeCamera2D* cam, int target_x, int target_y, uint16_t dt_ms) {
    if (cam == nullptr) return;

    cam->look_x_q8 = ease_q8(cam->look_x_q8, cam->look_target_q8, dt_ms, 250);

    const int32_t cam_x = cam->x_q8;
    const int32_t cam_y = cam->y_q8;
    /* The lookahead biases the point being framed, so running right slides the
     * view right of the player and reveals level ahead of them. */
    const int tx = target_x + (int)(cam->look_x_q8 >> 8);
    const int sx = tx - (int)(cam_x >> 8);
    const int sy = target_y - (int)(cam_y >> 8);

    int32_t want_x = cam_x;
    int32_t want_y = cam_y;

    /* Outside the deadzone the viewport slides just enough to bring the target
     * back onto the band edge, so a walking player sits still on screen until
     * they change direction. */
    if (sx < cam->dead_l) {
        want_x = ((int32_t)tx - cam->dead_l) << 8;
    } else if (sx > cam->view_w - cam->dead_r) {
        want_x = ((int32_t)tx - (cam->view_w - cam->dead_r)) << 8;
    }
    if (sy < cam->dead_t) {
        want_y = ((int32_t)target_y - cam->dead_t) << 8;
    } else if (sy > cam->view_h - cam->dead_b) {
        want_y = ((int32_t)target_y - (cam->view_h - cam->dead_b)) << 8;
    }

    want_x = clamp_q8(want_x, cam->min_x_q8, cam->max_x_q8);
    want_y = clamp_q8(want_y, cam->min_y_q8, cam->max_y_q8);

    cam->x_q8 = ease_q8(cam_x, want_x, dt_ms, cam->follow_ms);
    cam->y_q8 = ease_q8(cam_y, want_y, dt_ms, cam->follow_ms);

    /* Easing can overshoot the clamp window by a pixel; re-clamp so the
     * viewport never shows outside the world. */
    cam->x_q8 = clamp_q8(cam->x_q8, cam->min_x_q8, cam->max_x_q8);
    cam->y_q8 = clamp_q8(cam->y_q8, cam->min_y_q8, cam->max_y_q8);
}

void vxpe_cam_shake(VxpeCamera2D* cam, int amplitude_px, uint16_t duration_ms) {
    if (cam == nullptr || amplitude_px <= 0 || duration_ms == 0) return;
    const uint16_t amp = (uint16_t)(amplitude_px << 8);
    if (amp > cam->shake_amp_q8) cam->shake_amp_q8 = amp;
    if (duration_ms > cam->shake_ms) cam->shake_ms = duration_ms;
    cam->shake_elapsed_ms = 0;
}

int vxpe_cam_shaking(const VxpeCamera2D* cam) {
    return cam && cam->shake_ms ? 1 : 0;
}

void vxpe_cam_update(VxpeCamera2D* cam, uint16_t dt_ms) {
    if (cam == nullptr) return;
    if (cam->shake_ms == 0) {
        cam->shake_x_q8 = 0;
        cam->shake_y_q8 = 0;
        return;
    }
    if (cam->seed == 0) cam->seed = 0x1u;

    const uint16_t total = cam->shake_ms;
    cam->shake_elapsed_ms += dt_ms;
    if (cam->shake_elapsed_ms >= total) {
        cam->shake_ms = 0;
        cam->shake_amp_q8 = 0;
        cam->shake_x_q8 = 0;
        cam->shake_y_q8 = 0;
        return;
    }

    /* Linear fade of the peak amplitude, then a fresh jitter whenever the
     * step period elapses. Vertical jitter is halved: a side-scroller reads
     * better when the shake mostly pushes sideways. */
    const uint16_t remain = (uint16_t)(total - cam->shake_elapsed_ms);
    const uint32_t amp = ((uint32_t)cam->shake_amp_q8 * remain) / total;

    cam->shake_step_ms = cam->shake_step_ms ? cam->shake_step_ms : 32;
    if (cam->shake_elapsed_ms % cam->shake_step_ms < dt_ms ||
        cam->shake_x_q8 == 0) {
        const uint32_t span = amp * 2u + 1u;
        const int32_t jx = (int32_t)(xorshift32(&cam->seed) % span) - (int32_t)amp;
        const int32_t jy = (int32_t)(xorshift32(&cam->seed) % (span / 2u + 1u))
                           - (int32_t)(amp / 2u);
        cam->shake_x_q8 = jx;
        cam->shake_y_q8 = jy;
    }
}

int vxpe_cam_x(const VxpeCamera2D* cam) {
    return cam ? (int)((cam->x_q8 + cam->shake_x_q8) >> 8) : 0;
}

int vxpe_cam_y(const VxpeCamera2D* cam) {
    return cam ? (int)((cam->y_q8 + cam->shake_y_q8) >> 8) : 0;
}

int vxpe_cam_to_screen_x(const VxpeCamera2D* cam, int world_x) {
    return world_x - vxpe_cam_x(cam);
}

int vxpe_cam_to_screen_y(const VxpeCamera2D* cam, int world_y) {
    return world_y - vxpe_cam_y(cam);
}

int vxpe_cam_visible(const VxpeCamera2D* cam, int x, int y, int w, int h) {
    if (cam == nullptr) return 1;
    const int vx = vxpe_cam_x(cam);
    const int vy = vxpe_cam_y(cam);
    if (x + w <= vx || y + h <= vy) return 0;
    if (x >= vx + cam->view_w || y >= vy + cam->view_h) return 0;
    return 1;
}

}  /* extern "C" */
