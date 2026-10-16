/*
 * Copyright (c) 2026 PixelRoot32
 * Licensed under the MIT License
 *
 * VxpBody2D - tilemap platformer body for C games.
 *
 * Everything is Q8.8 fixed point because ARMv5TE has no FPU: a float gravity
 * term would pull in __aeabi_fmul on every integration step. Velocities are
 * Q8 pixels per second and accelerations Q8 pixels per second squared, so a
 * tuning table reads like a design document (run_max_q8 = 92*256 is 92 px/s).
 *
 * The mover is axis separated and never substeps more than the swept floor
 * scan can cover, so a body falling at terminal speed cannot tunnel through a
 * one-tile platform. Solid tiles block, one-way tiles block only downward
 * motion that started above their surface, and slope tiles are resolved
 * through vxpe_tilemap_floor_y so a ramp is walkable without a polygon
 * collider.
 */
#pragma once

#include <stdint.h>
#include "action2d/VxpTilemap2D.h"

#ifdef __cplusplus
extern "C" {
#endif

/* All speeds are Q8.8 px/s, all accelerations Q8.8 px/s^2. The fields are
 * int32_t because a Q8 gravity of 640 px/s^2 is 163 840 - an int16_t would
 * silently wrap and the body would fall upwards. */
typedef struct VxpeBodyTuning2D {
    int32_t run_max_q8;
    int32_t run_accel_q8;
    int32_t run_friction_q8;
    int32_t air_accel_q8;
    int32_t gravity_q8;
    int32_t jump_vel_q8;      /* upward launch speed, positive */
    int32_t jump_cut_q8;      /* speed kept when jump is released early */
    int32_t fall_max_q8;      /* terminal downward speed */
    int32_t wall_slide_q8;    /* capped fall speed while sliding a wall */
    int32_t swim_max_q8;      /* vertical speed cap while in water */
    int32_t climb_q8;         /* ladder speed */
    uint16_t coyote_ms;       /* grace to jump after leaving a ledge */
    uint16_t jump_buffer_ms;  /* grace for a press that lands mid-air */
    uint8_t step_up_px;       /* auto-climb height, also the slope tolerance */
    uint8_t step_down_px;     /* how far the body may fall and stay grounded */
} VxpeBodyTuning2D;

typedef struct VxpeBody2D {
    int32_t x_q8, y_q8;   /* top-left of the collision box, world px */
    int32_t vx_q8, vy_q8;

    uint16_t w, h;        /* collision box in px */

    /* Contact state, valid after the step. */
    uint8_t on_ground;
    uint8_t on_ceiling;
    uint8_t on_wall_l;
    uint8_t on_wall_r;
    uint8_t in_water;
    uint8_t on_ladder;
    uint8_t on_slope;     /* resting on a slope surface rather than a flat tile */

    uint8_t facing;       /* 0 = left, 1 = right, updated from run intent */

    uint16_t air_ms;      /* time since leaving the ground */
    uint16_t coyote_ms;   /* remaining grace, counts down */
    uint16_t buffer_ms;   /* remaining jump-buffer window, counts down */
    uint16_t drop_ms;     /* one-way pass-through window still open */
    uint16_t jump_ms;     /* nonzero while a jump rise is still "owned" by the button */
    uint8_t landed;       /* 1 only on the frame the body touched down */
} VxpeBody2D;

typedef struct VxpeBodyIntent2D {
    int8_t x;             /* -1 / 0 / +1 run intent */
    int8_t y;             /* -1 up, +1 down: ladder climb and one-way drop */
    uint8_t jump;         /* 1 on the frame the jump button was pressed */
    uint8_t jump_held;    /* 1 while it stays down */
} VxpeBodyIntent2D;

/* Box starts with its top-left at world (x,y). Call once per body. */
void vxpe_body_init(VxpeBody2D* body, int x, int y, int w, int h);

/* Full character controller: run intent, friction, coyote time, jump buffering,
 * variable jump height, air control, wall slide, ladder, water, one-way drop
 * through, slope and step handling, then the tile move. This is what a player
 * body wants. */
void vxpe_body_control(
    VxpeBody2D* body, const VxpeTilemap2D* map, const VxpeBodyTuning2D* tuning,
    const VxpeBodyIntent2D* intent, uint16_t dt_ms);

/* Physics only: integrates gravity into the current velocity and moves the
 * body. Use this for enemies that steer by setting vx_q8 directly. */
void vxpe_body_step(
    VxpeBody2D* body, const VxpeTilemap2D* map, const VxpeBodyTuning2D* tuning,
    uint16_t dt_ms);

/* Teleport helpers. Snap puts the body exactly at a world point without
 * moving it; settle drops it onto the floor below its feet within 16 tiles. */
void vxpe_body_snap(VxpeBody2D* body, int x, int y);
int vxpe_body_settle(VxpeBody2D* body, const VxpeTilemap2D* map);

/* 1 when any tile overlapping the box carries one of `mask`. A game uses this
 * for spikes, water volumes and door triggers. */
int vxpe_body_touching(const VxpeBody2D* body, const VxpeTilemap2D* map, uint16_t mask);

/* The tile the body currently stands on (only meaningful when on_ground).
 * `tx`/`ty` may be NULL. Returns 1 when a tile was written. */
int vxpe_body_ground_tile(const VxpeBody2D* body, const VxpeTilemap2D* map, int* tx, int* ty);

/* A ready-made tuning set: about 92 px/s run, a 3-tile jump, tuned for 16 px
 * tiles at 30 fps. Copy it and edit the fields per game. */
void vxpe_body_tuning_default(VxpeBodyTuning2D* tuning);

#ifdef __cplusplus
} /* extern "C" */
#endif
