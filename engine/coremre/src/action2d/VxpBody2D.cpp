/*
 * Copyright (c) 2026 PixelRoot32
 * Licensed under the MIT License
 *
 * VxpBody2D implementation.
 *
 * Two invariants keep this cheap on ARMv5TE and correct at speed:
 *  - horizontal motion advances at most one pixel per iteration, so a body can
 *    never pass a tile it should have collided with;
 *  - vertical motion does not step at all. It sweeps the whole travel span and
 *    asks for the first surface inside it, which is both faster and unable to
 *    tunnel through a one-tile floor at terminal velocity.
 */
#include "action2d/VxpBody2D.h"

#include <stddef.h>
#include <string.h>

namespace {

const int NO_FLOOR = 0x7FFFFFFF;

inline int floor_div(int v, int d) {
    if (d <= 0) return 0;
    const int q = v / d;
    return (v < 0 && v % d) ? q - 1 : q;
}

/* 1 when any tile overlapping the half-open box carries one of `mask`. */
int box_flags(const VxpeTilemap2D* m, int x, int y, int w, int h, uint16_t mask) {
    const int tx0 = floor_div(x, m->tile_w);
    const int tx1 = floor_div(x + w - 1, m->tile_w);
    const int ty0 = floor_div(y, m->tile_h);
    const int ty1 = floor_div(y + h - 1, m->tile_h);
    for (int ty = ty0; ty <= ty1; ++ty) {
        for (int tx = tx0; tx <= tx1; ++tx) {
            if (vxpe_tilemap_flags(m, tx, ty) & mask) return 1;
        }
    }
    return 0;
}

/*
 * First supporting surface inside [from_y, to_y). Slopes are evaluated at the
 * body's centre column: a ramp supports the body where its middle sits, which
 * is what makes a 16 px ramp walkable without a polygon collider. Reports slope
 * contact through *slope_hit.
 *
 * The range is strict. A tile whose top edge sits above from_y is geometry the
 * body is already inside or below, not a floor it can land on, and snapping to
 * it would push the body upward - the classic way a one-way platform swallows a
 * drop-through request that is still in flight.
 */
int surface_below(const VxpeTilemap2D* m, int x, int w, int center_x,
                  int from_y, int to_y, uint16_t mask, int* slope_hit) {
    if (to_y <= from_y || w <= 0) return NO_FLOOR;
    const int tw = m->tile_w;
    const int th = m->tile_h;
    const int tx0 = floor_div(x, tw);
    const int tx1 = floor_div(x + w - 1, tw);
    const int ty0 = floor_div(from_y, th);
    const int ty1 = floor_div(to_y - 1, th);
    const int cx_tile = floor_div(center_x, tw);

    int best = NO_FLOOR;
    for (int ty = ty0; ty <= ty1; ++ty) {
        const int tile_top = ty * th;
        for (int tx = tx0; tx <= tx1; ++tx) {
            const uint16_t f = vxpe_tilemap_flags(m, tx, ty);
            int cand = NO_FLOOR;
            if ((f & VXPE_TF_SOLID) && (mask & VXPE_TF_SOLID)) {
                cand = tile_top;
            } else if ((f & VXPE_TF_ONEWAY) && (mask & VXPE_TF_ONEWAY)) {
                cand = tile_top;
            } else if ((f & VXPE_TF_SLOPE) && (mask & VXPE_TF_SLOPE) && tx == cx_tile) {
                cand = vxpe_tilemap_floor_y(m, tx, ty, center_x - tx * tw);
            }
            if (cand < from_y || cand >= to_y) continue;
            if (cand < best) {
                best = cand;
                if (slope_hit) *slope_hit = (f & VXPE_TF_SLOPE) ? 1 : 0;
            }
        }
    }
    return best;
}

/* While the drop-through window is open a one-way tile stops supporting the
 * body, so it falls through and the window closes on its own. */
uint16_t support_mask(const VxpeBody2D* b) {
    return b->drop_ms > 0
        ? (uint16_t)(VXPE_TF_SOLID | VXPE_TF_SLOPE)
        : (uint16_t)(VXPE_TF_SOLID | VXPE_TF_ONEWAY | VXPE_TF_SLOPE);
}

void move_x(VxpeBody2D* b, const VxpeTilemap2D* m, const VxpeBodyTuning2D* t, int32_t dx_q8) {
    if (dx_q8 == 0) return;
    const int dir = dx_q8 > 0 ? 1 : -1;
    int32_t remain = dx_q8 > 0 ? dx_q8 : -dx_q8;
    /* A body that starts inside geometry (a spawn mistake, or a tile that
     * appeared around it) must still be able to leave. */
    const int stuck = box_flags(m, (int)(b->x_q8 >> 8), (int)(b->y_q8 >> 8),
                                b->w, b->h, VXPE_TF_SOLID);

    while (remain > 0) {
        const int32_t step = remain > 256 ? 256 : remain;
        const int32_t nx = b->x_q8 + dir * step;
        const int x = (int)(nx >> 8);
        const int y = (int)(b->y_q8 >> 8);
        remain -= step;

        if (stuck || !box_flags(m, x, y, b->w, b->h, VXPE_TF_SOLID)) {
            b->x_q8 = nx;
            continue;
        }

        int climbed = 0;
        if (b->on_ground && t->step_up_px > 0) {
            for (int up = 1; up <= t->step_up_px; ++up) {
                if (!box_flags(m, x, y - up, b->w, b->h, VXPE_TF_SOLID)) {
                    b->x_q8 = nx;
                    b->y_q8 -= (int32_t)up << 8;
                    climbed = 1;
                    break;
                }
            }
        }
        if (climbed) continue;

        if (dir > 0) {
            const int edge = floor_div(x + b->w - 1, m->tile_w) * m->tile_w;
            b->x_q8 = (int32_t)(edge - b->w) << 8;
            b->on_wall_r = 1;
        } else {
            const int edge = (floor_div(x, m->tile_w) + 1) * m->tile_w;
            b->x_q8 = (int32_t)edge << 8;
            b->on_wall_l = 1;
        }
        b->vx_q8 = 0;
        return;
    }
}

void move_y(VxpeBody2D* b, const VxpeTilemap2D* m, const VxpeBodyTuning2D* t, int32_t dy_q8) {
    const int x = (int)(b->x_q8 >> 8);
    const int cx = x + b->w / 2;
    const int was_ground = b->on_ground;
    int slope_hit = 0;

    if (dy_q8 > 0) {
        const int from = (int)(b->y_q8 >> 8) + b->h;
        const int to = (int)((b->y_q8 + dy_q8) >> 8) + b->h + 1;
        const int s = surface_below(m, x, b->w, cx, from, to, support_mask(b), &slope_hit);
        if (s != NO_FLOOR) {
            b->y_q8 = (int32_t)(s - b->h) << 8;
            b->vy_q8 = 0;
            b->on_ground = 1;
            b->on_slope = (uint8_t)slope_hit;
        } else {
            b->y_q8 += dy_q8;
            b->on_ground = 0;
        }
    } else if (dy_q8 < 0) {
        const int ny = (int)((b->y_q8 + dy_q8) >> 8);
        if (box_flags(m, x, ny, b->w, b->h, VXPE_TF_SOLID)) {
            const int row = (floor_div(ny, m->tile_h) + 1) * m->tile_h;
            b->y_q8 = (int32_t)row << 8;
            b->vy_q8 = 0;
            b->on_ceiling = 1;
            b->on_ground = 0;
        } else {
            b->y_q8 += dy_q8;
            b->on_ground = 0;
        }
    } else {
        /* Standing still: keep the ground flag honest so walking off a ledge is
         * noticed on the same frame rather than after a frame of hover. */
        const int y = (int)(b->y_q8 >> 8);
        const int s = surface_below(m, x, b->w, cx, y + b->h, y + b->h + 1,
                                    support_mask(b), &slope_hit);
        b->on_ground = (s == y + b->h);
        b->on_slope = b->on_ground ? (uint8_t)slope_hit : 0;
    }

    if (!was_ground && b->on_ground) b->landed = 1;

    /* Ramps and small descents. move_x already handles stepping up over solid
     * blocks, so this pass only lifts onto slope surfaces and keeps the body
     * glued to the ground while running downhill. */
    if (b->on_ground) {
        const int bottom = (int)(b->y_q8 >> 8) + b->h;
        const int up = surface_below(m, x, b->w, cx, bottom - (t->step_up_px + 1), bottom,
                                     VXPE_TF_SLOPE, &slope_hit);
        if (up != NO_FLOOR && up < bottom) {
            b->y_q8 = (int32_t)(up - b->h) << 8;
            b->on_slope = 1;
        } else {
            const int down = surface_below(m, x, b->w, cx, bottom,
                                           bottom + t->step_down_px + 1,
                                           support_mask(b), &slope_hit);
            if (down != NO_FLOOR) {
                b->y_q8 = (int32_t)(down - b->h) << 8;
                b->on_slope = (uint8_t)slope_hit;
            } else {
                b->on_ground = 0;
            }
        }
    }
}

/* Accelerates `v` toward `target` by at most `rate` per second. */
inline int32_t approach(int32_t v, int32_t target, int32_t rate_q8, uint16_t dt_ms) {
    const int32_t d = (int32_t)(((int64_t)rate_q8 * dt_ms) / 1000);
    if (d <= 0) return v;
    if (v < target) return v + d > target ? target : v + d;
    if (v > target) return v - d < target ? target : v - d;
    return v;
}

}  // namespace

extern "C" {

void vxpe_body_init(VxpeBody2D* body, int x, int y, int w, int h) {
    if (body == nullptr) return;
    memset(body, 0, sizeof(*body));
    body->x_q8 = (int32_t)x << 8;
    body->y_q8 = (int32_t)y << 8;
    body->w = (uint16_t)(w > 0 ? w : 1);
    body->h = (uint16_t)(h > 0 ? h : 1);
    body->facing = 1;
}

void vxpe_body_tuning_default(VxpeBodyTuning2D* t) {
    if (t == nullptr) return;
    memset(t, 0, sizeof(*t));
    /* Tuned for 16 px tiles: a 92 px/s run crosses the 240 px screen in 2.6 s,
     * and 230 px/s against 640 px/s^2 peaks at 41 px - about two and a half
     * tiles, which is what a gothic staircase expects. */
    t->run_max_q8 = 92 * 256;
    t->run_accel_q8 = 900 * 256;
    t->run_friction_q8 = 780 * 256;
    t->air_accel_q8 = 520 * 256;
    t->gravity_q8 = 640 * 256;
    t->jump_vel_q8 = 230 * 256;
    t->jump_cut_q8 = 70 * 256;
    t->fall_max_q8 = 260 * 256;
    t->wall_slide_q8 = 40 * 256;
    t->swim_max_q8 = 60 * 256;
    t->climb_q8 = 46 * 256;
    t->coyote_ms = 90;
    t->jump_buffer_ms = 110;
    t->step_up_px = 16;
    t->step_down_px = 12;
}

void vxpe_body_snap(VxpeBody2D* body, int x, int y) {
    if (body == nullptr) return;
    body->x_q8 = (int32_t)x << 8;
    body->y_q8 = (int32_t)y << 8;
    body->vx_q8 = 0;
    body->vy_q8 = 0;
    body->on_ground = 0;
    body->air_ms = 0;
}

int vxpe_body_settle(VxpeBody2D* body, const VxpeTilemap2D* map) {
    if (body == nullptr || map == nullptr) return 0;
    const int x = (int)(body->x_q8 >> 8);
    const int bottom = (int)(body->y_q8 >> 8) + body->h;
    int slope = 0;
    const int s = surface_below(map, x, body->w, x + body->w / 2, bottom,
                                bottom + 16 * map->tile_h,
                                VXPE_TF_SOLID | VXPE_TF_ONEWAY | VXPE_TF_SLOPE, &slope);
    if (s == NO_FLOOR) return 0;
    body->y_q8 = (int32_t)(s - body->h) << 8;
    body->vy_q8 = 0;
    body->on_ground = 1;
    body->on_slope = (uint8_t)slope;
    return 1;
}

void vxpe_body_step(
    VxpeBody2D* body, const VxpeTilemap2D* map, const VxpeBodyTuning2D* t, uint16_t dt_ms) {
    if (body == nullptr || map == nullptr || t == nullptr || dt_ms == 0 ||
        map->tile_w == 0 || map->tile_h == 0) {
        return;
    }
    const int32_t dt = dt_ms;

    body->landed = 0;
    body->on_ceiling = 0;
    body->on_wall_l = 0;
    body->on_wall_r = 0;

    if (!body->on_ladder) {
        int32_t g = t->gravity_q8;
        if (body->in_water) g /= 3;
        body->vy_q8 += (int32_t)(((int64_t)g * dt) / 1000);
        const int32_t cap = body->in_water ? t->swim_max_q8 : t->fall_max_q8;
        if (cap > 0 && body->vy_q8 > cap) body->vy_q8 = cap;
    }

    move_x(body, map, t, (int32_t)(((int64_t)body->vx_q8 * dt) / 1000));
    move_y(body, map, t, (int32_t)(((int64_t)body->vy_q8 * dt) / 1000));

    if (body->on_ground) {
        body->air_ms = 0;
        body->coyote_ms = t->coyote_ms;
    } else {
        if (body->air_ms < 60000) body->air_ms += dt_ms;
        if (body->coyote_ms > dt_ms) body->coyote_ms -= dt_ms;
        else body->coyote_ms = 0;
    }
    if (body->drop_ms > dt_ms) body->drop_ms -= dt_ms;
    else body->drop_ms = 0;
    if (body->buffer_ms > dt_ms) body->buffer_ms -= dt_ms;
    else body->buffer_ms = 0;
}

void vxpe_body_control(
    VxpeBody2D* body, const VxpeTilemap2D* map, const VxpeBodyTuning2D* t,
    const VxpeBodyIntent2D* in, uint16_t dt_ms) {
    if (body == nullptr || map == nullptr || t == nullptr || in == nullptr || dt_ms == 0) return;

    const int x = (int)(body->x_q8 >> 8);
    const int y = (int)(body->y_q8 >> 8);
    const uint16_t under = vxpe_tilemap_rect_flags(map, x, y, x + body->w, y + body->h);
    body->in_water = (under & VXPE_TF_WATER) ? 1 : 0;
    const int on_ladder_tile = (under & VXPE_TF_LADDER) ? 1 : 0;

    /* --- ladder: vertical control replaces gravity ----------------------
     * Grabbing needs an up/down intent (or an existing grip); jump releases it
     * so a player on a ladder can hop off instead of being glued to it. */
    if (on_ladder_tile) {
        if (body->on_ladder && in->jump) {
            body->on_ladder = 0;
            body->vy_q8 = -(t->jump_vel_q8 / 2);
            body->jump_ms = 1;
            /* Zero the grace windows: the press is spent on the dismount, and a
             * full-strength jump would fire the moment the buffer is read. */
            body->coyote_ms = 0;
            body->buffer_ms = 0;
        } else if (in->y != 0 || body->on_ladder) {
            body->on_ladder = 1;
        }
    } else if (body->on_ladder) {
        body->on_ladder = 0;
        body->vy_q8 = 0;
    }
    if (body->on_ladder) {
        body->vx_q8 = 0;
        body->vy_q8 = (int32_t)in->y * t->climb_q8;
        body->on_ground = 0;
        if (in->x != 0) body->facing = (uint8_t)(in->x > 0 ? 1 : 0);
        vxpe_body_step(body, map, t, dt_ms);
        return;
    }

    /* --- horizontal ------------------------------------------------------ */
    if (in->x != 0) {
        const int32_t cap = body->in_water ? (t->run_max_q8 * 3) / 4 : t->run_max_q8;
        const int32_t rate = body->on_ground ? t->run_accel_q8 : t->air_accel_q8;
        body->vx_q8 = approach(body->vx_q8, in->x > 0 ? cap : -cap, rate, dt_ms);
        body->facing = (uint8_t)(in->x > 0 ? 1 : 0);
    } else if (body->on_ground || body->in_water) {
        const int32_t rate = body->in_water ? t->run_friction_q8 * 2 : t->run_friction_q8;
        body->vx_q8 = approach(body->vx_q8, 0, rate, dt_ms);
    }

    /* --- drop through a one-way platform ---------------------------------
     * Runs before the jump block and spends the press: down+jump standing on a
     * platform is a drop, not a hop. The window is deliberately not gated on
     * on_ground, because from the next frame onward the body is airborne with
     * the button usually still held. */
    int press_spent = 0;
    if (in->jump && in->y > 0) {
        body->drop_ms = 140;
        body->buffer_ms = 0;
        if (body->on_ground && body->vy_q8 >= 0) body->vy_q8 = 24 * 256;
        press_spent = 1;
    }

    /* --- jump, with buffering and coyote time ----------------------------
     * control() only ever loads the buffer; vxpe_body_step owns the decay of
     * buffer_ms, drop_ms and coyote_ms, so a press cannot be spent twice. */
    if (in->jump && !press_spent) body->buffer_ms = t->jump_buffer_ms;

    if (!press_spent && body->buffer_ms) {
        /* on_wall_* still holds last frame's contacts here: move_x clears and
         * re-sets them, and a wall jump wants the wall the player is pressing
         * into right now, which is what the previous frame measured. */
        const int wall_grab = !body->on_ground && body->coyote_ms == 0 && t->jump_vel_q8 > 0 &&
                              ((body->on_wall_l && in->x < 0) || (body->on_wall_r && in->x > 0));
        const int can_jump = body->on_ground || body->coyote_ms > 0 || body->in_water;
        if (can_jump || wall_grab) {
            const int32_t boost = body->in_water ? (t->jump_vel_q8 * 3) / 5 : t->jump_vel_q8;
            body->vy_q8 = -boost;
            body->on_ground = 0;
            body->coyote_ms = 0;
            body->buffer_ms = 0;
            body->air_ms = 1;
            body->jump_ms = 1;
            if (wall_grab) {
                body->vx_q8 = body->on_wall_l ? -t->run_max_q8 : t->run_max_q8;
                body->facing = body->on_wall_l ? 0 : 1;
            }
        }
    }

    /* Variable height: releasing early keeps only a fraction of the rise, so a
     * tapped button hops and a held one clears two and a half tiles. */
    if (body->jump_ms && !in->jump_held && body->vy_q8 < -t->jump_cut_q8) {
        body->vy_q8 = -t->jump_cut_q8;
        body->jump_ms = 0;
    }
    if (body->vy_q8 >= 0) body->jump_ms = 0;

    /* --- wall slide ------------------------------------------------------ */
    if (!body->on_ground && body->vy_q8 > 0 && t->wall_slide_q8 > 0 &&
        ((body->on_wall_l && in->x < 0) || (body->on_wall_r && in->x > 0))) {
        if (body->vy_q8 > t->wall_slide_q8) body->vy_q8 = t->wall_slide_q8;
    }

    vxpe_body_step(body, map, t, dt_ms);
}

int vxpe_body_touching(const VxpeBody2D* body, const VxpeTilemap2D* map, uint16_t mask) {
    if (body == nullptr || map == nullptr) return 0;
    return box_flags(map, (int)(body->x_q8 >> 8), (int)(body->y_q8 >> 8),
                     body->w, body->h, mask);
}

int vxpe_body_ground_tile(const VxpeBody2D* body, const VxpeTilemap2D* map, int* tx, int* ty) {
    if (body == nullptr || map == nullptr || !body->on_ground) return 0;
    const int x = (int)(body->x_q8 >> 8);
    const int y = (int)(body->y_q8 >> 8);
    const int gx = floor_div(x + body->w / 2, map->tile_w);
    const int gy = floor_div(y + body->h, map->tile_h);
    if (tx) *tx = gx;
    if (ty) *ty = gy;
    return 1;
}

}  /* extern "C" */
