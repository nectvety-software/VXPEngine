/*
 * Copyright (c) 2026 PixelRoot32
 * Licensed under the MIT License
 *
 * VxpCamera2D - two-axis follow camera for side-scrolling games.
 *
 * The older VxpeStageCamera2D only tracks X, which is enough for a fighting
 * stage but not for a level with vertical shafts. This one follows both axes,
 * keeps a per-axis deadzone, biases the view in the direction the player is
 * running, clamps to the world, and carries a deterministic shake so a hit
 * lands visually without a random seed making replays diverge.
 *
 * Positions are Q8.8 pixels. The integer view origin (vxpe_cam_x/_y) is what a
 * tilemap layer or a sprite blit wants; the Q8 origin is what a sub-pixel
 * parallax band wants, and both include the shake offset.
 */
#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct VxpeCamera2D {
    int32_t x_q8, y_q8;             /* world position of the viewport top-left */
    int32_t min_x_q8, min_y_q8;     /* clamp window, already view-size aware */
    int32_t max_x_q8, max_y_q8;
    int32_t shake_x_q8, shake_y_q8; /* current jitter, folded into x_q8 reads */
    int32_t look_x_q8;              /* eased lookahead bias */
    int32_t look_target_q8;         /* lookahead the game asked for */
    uint16_t view_w, view_h;
    int16_t dead_l, dead_r;         /* px from the left / right edge */
    int16_t dead_t, dead_b;         /* px from the top / bottom edge */
    uint16_t follow_ms;             /* time constant; 0 snaps */
    uint16_t shake_amp_q8;          /* decays linearly over shake_ms */
    uint16_t shake_ms;
    uint16_t shake_step_ms;         /* jitter refresh period */
    uint16_t shake_elapsed_ms;
    uint32_t seed;                  /* xorshift32, caller-visible for replays */
} VxpeCamera2D;

/* Deadzones default to the middle 40% horizontally and 30% vertically, the
 * follow time constant to 90 ms, and shake off. world_w/world_h may be smaller
 * than the viewport, in which case the camera centres on the world. */
void vxpe_cam_init(
    VxpeCamera2D* cam, int view_w, int view_h, int world_w, int world_h);

void vxpe_cam_set_deadzone(VxpeCamera2D* cam, int left, int right, int top, int bottom);

/* 0 makes the camera lock to the target with no easing. */
void vxpe_cam_set_follow_ms(VxpeCamera2D* cam, uint16_t follow_ms);

/* Signed pixel bias added to the follow target, eased over one second. Pass a
 * positive value while the player runs right so more level appears ahead. */
void vxpe_cam_set_lookahead(VxpeCamera2D* cam, int pixels);

/* Instant move to frame a world point, bypassing deadzone and easing. */
void vxpe_cam_snap(VxpeCamera2D* cam, int target_x, int target_y);

/* Moves the viewport toward the target. Call before vxpe_cam_update. */
void vxpe_cam_follow(VxpeCamera2D* cam, int target_x, int target_y, uint16_t dt_ms);

/* Decays shake and re-picks the jitter offset. Safe to call every frame even
 * when nothing is following, so a static arena still shakes. */
void vxpe_cam_update(VxpeCamera2D* cam, uint16_t dt_ms);

/* Kick the camera. amplitude_px is the peak offset; duration_ms is how long
 * the shake lasts while it linearly fades. A repeat call takes the larger of
 * the two requests so a combo does not shorten an existing shake. */
void vxpe_cam_shake(VxpeCamera2D* cam, int amplitude_px, uint16_t duration_ms);

int vxpe_cam_shaking(const VxpeCamera2D* cam);

/* Viewport origin in whole pixels, shake included. */
int vxpe_cam_x(const VxpeCamera2D* cam);
int vxpe_cam_y(const VxpeCamera2D* cam);

/* World -> screen for sprites and props. */
int vxpe_cam_to_screen_x(const VxpeCamera2D* cam, int world_x);
int vxpe_cam_to_screen_y(const VxpeCamera2D* cam, int world_y);

/* 1 when the world rect touches the viewport. Used to cull entities. */
int vxpe_cam_visible(const VxpeCamera2D* cam, int x, int y, int w, int h);

#ifdef __cplusplus
} /* extern "C" */
#endif
