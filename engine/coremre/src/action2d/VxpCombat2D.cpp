/*
 * Copyright (c) 2026 PixelRoot32
 * Licensed under the MIT License
 *
 * VxpCombat2D implementation. The whole module is integer comparisons and one
 * overlap test per candidate pair, so a 4x4 attacker/victim grid costs 16 rect
 * tests - cheaper than the sprite blit for a single character.
 */
#include "action2d/VxpCombat2D.h"

#include <stddef.h>

namespace {

/* Saturating countdown: a timer may be handed a dt larger than itself when the
 * emulator drops frames, and wrapping to a huge value would make a fighter
 * invulnerable for the rest of the level. */
inline void dec_ms(uint16_t* v, uint16_t dt_ms) {
    if (*v > dt_ms) *v = (uint16_t)(*v - dt_ms);
    else *v = 0;
}

inline void raise_ms(uint16_t* v, uint16_t want) {
    if (want > *v) *v = want;
}

inline int32_t q8_of(int v) { return (int32_t)v << 8; }

inline int center_x(const VxpeRectI* r) { return r->x + r->w / 2; }
inline int center_y(const VxpeRectI* r) { return r->y + r->h / 2; }

inline int rects_overlap(const VxpeRectI* a, const VxpeRectI* b) {
    return a->x < b->x + b->w && b->x < a->x + a->w &&
           a->y < b->y + b->h && b->y < a->y + a->h;
}

/* Overlap centre: where a spark or blood puff belongs. */
inline void impact(const VxpeRectI* a, const VxpeRectI* b, VxpeCombatEvent2D* e) {
    const int x0 = a->x > b->x ? a->x : b->x;
    const int x1 = (a->x + a->w) < (b->x + b->w) ? (a->x + a->w) : (b->x + b->w);
    const int y0 = a->y > b->y ? a->y : b->y;
    const int y1 = (a->y + a->h) < (b->y + b->h) ? (a->y + a->h) : (b->y + b->h);
    e->x = (int16_t)((x0 + x1) / 2);
    e->y = (int16_t)((y0 + y1) / 2);
}

inline void push_event(VxpeCombatEvent2D* events, int* written, int max_events,
                       const VxpeCombatEvent2D* e) {
    if (events != nullptr && *written < max_events) events[(*written)++] = *e;
}

/* A swing is over for any reason: the timer ran out, the owner got stunned, or
 * the owner died. All three must clear the per-swing hit mask, because the next
 * attack starts from a clean slate. */
void end_swing(VxpeCombatant2D* c, VxpeCombatEvent2D* events, int* written,
               int max_events) {
    c->atk = nullptr;
    c->atk_ms = 0;
    c->swing_mask = 0;
    VxpeCombatEvent2D e{};
    e.kind = VXPE_CE2D_SWING_END;
    e.attacker = c->slot;
    e.victim = 0xFF;
    push_event(events, written, max_events, &e);
}

}  /* namespace */

extern "C" {

void vxpe_combat_init(VxpeCombatant2D* c, VxpeBody2D* body,
                      uint16_t max_hp, int team, int slot) {
    if (c == nullptr) return;
    c->body = body;
    c->atk = nullptr;
    c->hp = max_hp;
    c->max_hp = max_hp;
    c->invuln_ms = 0;
    c->stun_ms = 0;
    c->freeze_ms = 0;
    c->atk_ms = 0;
    c->flash_ms = 0;
    c->swing_mask = 0;
    c->team = (int8_t)team;
    c->slot = (uint8_t)(slot & 31);
    c->alive = 1;
    c->pad_ = 0;
}

int vxpe_combat_attack(VxpeCombatant2D* c, const VxpeAttack2D* atk) {
    if (c == nullptr || atk == nullptr) return 0;
    if (!c->alive || c->atk != nullptr || c->stun_ms || c->freeze_ms) return 0;
    c->atk = atk;
    c->atk_ms = 0;
    c->swing_mask = 0;
    return 1;
}

int vxpe_combat_attacking(const VxpeCombatant2D* c) {
    return (c != nullptr && c->atk != nullptr) ? 1 : 0;
}

int vxpe_combat_frozen(const VxpeCombatant2D* c) {
    return (c != nullptr && c->freeze_ms) ? 1 : 0;
}

int vxpe_combat_update(VxpeCombatant2D* c, uint16_t dt_ms,
                       VxpeCombatEvent2D* events, int max_events) {
    if (c == nullptr) return 0;
    dec_ms(&c->invuln_ms, dt_ms);
    dec_ms(&c->stun_ms, dt_ms);
    dec_ms(&c->freeze_ms, dt_ms);
    dec_ms(&c->flash_ms, dt_ms);
    if (c->atk == nullptr) return 0;

    int written = 0;
    const VxpeAttack2D* a = c->atk;
    const uint16_t total = (uint16_t)(a->windup_ms + a->active_ms + a->recover_ms);
    const uint16_t before = c->atk_ms;
    const uint32_t advanced = (uint32_t)before + dt_ms;
    c->atk_ms = (uint16_t)(advanced > 60000u ? 60000u : advanced);

    /* Getting hit already cancelled the swing inside vxpe_combat_hurt, so this
     * branch is the escape hatch for a game that drives stun_ms or alive by
     * hand - a cutscene grab, a boss phase change. Either way a stun that lands
     * mid-swing kills it: two enemies trading blows must not both connect every
     * frame, or no fight can ever be won. */
    if (c->stun_ms || !c->alive) {
        end_swing(c, events, &written, max_events);
        return written;
    }

    if (a->active_ms && before < a->windup_ms && c->atk_ms >= a->windup_ms) {
        VxpeCombatEvent2D e{};
        e.kind = VXPE_CE2D_WINDUP;
        e.attacker = c->slot;
        e.victim = 0xFF;
        e.damage = a->damage;
        e.hp_left = c->hp;
        if (c->body != nullptr) {
            e.x = (int16_t)(c->body->x_q8 >> 8);
            e.y = (int16_t)(c->body->y_q8 >> 8);
        }
        push_event(events, &written, max_events, &e);
    }
    if (c->atk_ms >= total) end_swing(c, events, &written, max_events);
    return written;
}

int vxpe_combat_hitbox(const VxpeCombatant2D* c, VxpeRectI* out) {
    if (c == nullptr || out == nullptr || !c->alive || c->atk == nullptr ||
        c->body == nullptr) {
        return 0;
    }
    const VxpeAttack2D* a = c->atk;
    if (c->atk_ms < a->windup_ms || c->atk_ms >= (uint16_t)(a->windup_ms + a->active_ms)) {
        return 0;
    }
    const int bx = (int)(c->body->x_q8 >> 8);
    const int by = (int)(c->body->y_q8 >> 8);
    out->w = (int16_t)a->w;
    out->h = (int16_t)a->h;
    out->y = (int16_t)(by + a->off_y);
    /* Mirror about the body box, not the sprite: the offset was authored for
     * one facing and a turn has to keep the blade in front of the owner. */
    out->x = (int16_t)(c->body->facing ? bx + a->off_x
                                       : bx + (int)c->body->w - a->off_x - (int)a->w);
    return 1;
}

void vxpe_combat_hurtbox(const VxpeCombatant2D* c, VxpeRectI* out) {
    if (out == nullptr) return;
    out->x = 0; out->y = 0; out->w = 0; out->h = 0;
    if (c == nullptr || !c->alive || c->body == nullptr) return;
    out->x = (int16_t)(c->body->x_q8 >> 8);
    out->y = (int16_t)(c->body->y_q8 >> 8);
    out->w = (int16_t)c->body->w;
    out->h = (int16_t)c->body->h;
}

void vxpe_combat_body_control(VxpeCombatant2D* c, const VxpeTilemap2D* map,
                              const VxpeBodyTuning2D* tuning,
                              const VxpeBodyIntent2D* intent, uint16_t dt_ms) {
    if (c == nullptr || c->body == nullptr || !c->alive || c->freeze_ms) return;
    /* Stunned keeps gravity and friction, drops only the player's steering: a
     * knocked-back hero should still fall, just not answer to the pad. */
    static const VxpeBodyIntent2D idle = {0, 0, 0, 0};
    vxpe_body_control(c->body, map, tuning, c->stun_ms ? &idle : intent, dt_ms);
}

void vxpe_combat_body_step(VxpeCombatant2D* c, const VxpeTilemap2D* map,
                           const VxpeBodyTuning2D* tuning, uint16_t dt_ms) {
    if (c == nullptr || c->body == nullptr || !c->alive || c->freeze_ms) return;
    vxpe_body_step(c->body, map, tuning, dt_ms);
}

int vxpe_combat_hurt(VxpeCombatant2D* c, uint16_t damage, int dir_x,
                     int32_t kb_x_q8, int32_t kb_y_q8, uint16_t invuln_ms,
                     uint16_t stun_ms, uint16_t hit_stop_ms, int attacker_slot,
                     VxpeCombatEvent2D* event) {
    if (c == nullptr || !c->alive || c->hp == 0) return 0;

    VxpeRectI box;
    vxpe_combat_hurtbox(c, &box);

    if (c->invuln_ms) {
        /* I-frames absorb the hit but still report it, so a game can play a
         * shield tick instead of silence. */
        if (event != nullptr) {
            event->kind = VXPE_CE2D_BLOCKED;
            event->attacker = (uint8_t)(attacker_slot < 0 ? 0xFF : (attacker_slot & 31));
            event->victim = c->slot;
            event->damage = 0;
            event->hp_left = c->hp;
            event->x = (int16_t)center_x(&box);
            event->y = (int16_t)center_y(&box);
        }
        return 0;
    }

    const uint16_t dealt = damage > c->hp ? c->hp : damage;
    c->hp = (uint16_t)(c->hp - dealt);
    raise_ms(&c->invuln_ms, invuln_ms);
    raise_ms(&c->stun_ms, stun_ms);
    raise_ms(&c->freeze_ms, hit_stop_ms);
    /* Blink exactly as long as the immunity lasts: one timer explains both the
     * renderer's flash and why the next blow did nothing. */
    raise_ms(&c->flash_ms, c->invuln_ms);

    if (c->stun_ms) { c->atk = nullptr; c->atk_ms = 0; c->swing_mask = 0; }

    if (c->body != nullptr && (kb_x_q8 || kb_y_q8)) {
        if (kb_x_q8) c->body->vx_q8 = (int32_t)(dir_x < 0 ? -kb_x_q8 : kb_x_q8);
        if (kb_y_q8) {
            c->body->vy_q8 = kb_y_q8;
            if (kb_y_q8 < 0) { c->body->on_ground = 0; c->body->coyote_ms = 0; }
        }
    }

    if (event != nullptr) {
        event->kind = c->hp ? VXPE_CE2D_HIT : VXPE_CE2D_KILL;
        event->attacker = (uint8_t)(attacker_slot < 0 ? 0xFF : (attacker_slot & 31));
        event->victim = c->slot;
        event->damage = dealt;
        event->hp_left = c->hp;
        event->x = (int16_t)center_x(&box);
        event->y = (int16_t)center_y(&box);
    }
    if (!c->hp) {
        c->alive = 0;
        c->atk = nullptr;
        c->atk_ms = 0;
    }
    return 1;
}

int vxpe_combat_resolve(VxpeCombatant2D* attackers, int attacker_count,
                        VxpeCombatant2D* victims, int victim_count,
                        VxpeCombatEvent2D* events, int max_events) {
    if (attackers == nullptr || victims == nullptr ||
        attacker_count <= 0 || victim_count <= 0) {
        return 0;
    }
    int written = 0;
    for (int i = 0; i < attacker_count; ++i) {
        VxpeCombatant2D* a = &attackers[i];
        VxpeRectI hb;
        if (!vxpe_combat_hitbox(a, &hb)) continue;
        const VxpeAttack2D* atk = a->atk;
        for (int j = 0; j < victim_count; ++j) {
            VxpeCombatant2D* v = &victims[j];
            if (v == a || !v->alive || v->team == a->team) continue;
            const uint32_t bit = 1u << (v->slot & 31);
            if (a->swing_mask & bit) continue;
            VxpeRectI vb;
            vxpe_combat_hurtbox(v, &vb);
            if (!rects_overlap(&hb, &vb)) continue;

            VxpeCombatEvent2D e{};
            const int dir = center_x(&vb) >= center_x(&hb) ? 1 : -1;
            const int landed = vxpe_combat_hurt(v, atk->damage, dir, atk->kb_x_q8,
                                                atk->kb_y_q8, atk->invuln_ms,
                                                atk->stun_ms, atk->hit_stop_ms,
                                                a->slot, &e);
            if (!landed) {
                /* I-frames report a block but do not spend the swing. An
                 * immune ally standing in the way would otherwise become a
                 * shield the player cannot see through, which reads as the
                 * weapon missing for no reason. */
                if (e.kind != VXPE_CE2D_BLOCKED) continue;
                impact(&hb, &vb, &e);
                push_event(events, &written, max_events, &e);
                continue;
            }
            a->swing_mask |= bit;
            impact(&hb, &vb, &e);
            push_event(events, &written, max_events, &e);
            /* A hit freezes the swing too, which is what holds the two sprites
             * still for a beat before the knockback carries them apart. */
            raise_ms(&a->freeze_ms, atk->hit_stop_ms);
            if (!atk->pierce) break;  /* one body per swing */
        }
    }
    return written;
}

/* --- projectiles ---------------------------------------------------------- */

void vxpe_proj_pool_init(VxpeProjectilePool2D* pool) {
    if (pool == nullptr) return;
    for (int i = 0; i < VXPE_PROJ_POOL2D_MAX; ++i) {
        pool->items[i].active = 0;
        pool->items[i].hit_mask = 0;
    }
    pool->count = 0;
    pool->pad_ = 0;
}

VxpeProjectile2D* vxpe_proj_spawn(VxpeProjectilePool2D* pool,
                                  const VxpeProjectile2D* init, int x, int y) {
    if (pool == nullptr || init == nullptr) return nullptr;
    for (int i = 0; i < VXPE_PROJ_POOL2D_MAX; ++i) {
        if (pool->items[i].active) continue;
        VxpeProjectile2D* p = &pool->items[i];
        *p = *init;
        p->x_q8 = q8_of(x);
        p->y_q8 = q8_of(y);
        p->hit_mask = 0;
        p->active = 1;
        if (i + 1 > pool->count) pool->count = (uint8_t)(i + 1);
        return p;
    }
    return nullptr;
}

int vxpe_proj_update(VxpeProjectilePool2D* pool, const VxpeTilemap2D* map,
                     uint16_t dt_ms) {
    if (pool == nullptr) return 0;
    int alive = 0;
    for (int i = 0; i < pool->count; ++i) {
        VxpeProjectile2D* p = &pool->items[i];
        if (!p->active) continue;
        if (p->life_ms <= dt_ms) { p->active = 0; continue; }
        p->life_ms = (uint16_t)(p->life_ms - dt_ms);
        if (p->gravity_q8) {
            p->vy_q8 += (int32_t)(((int64_t)p->gravity_q8 * dt_ms) / 1000);
        }
        p->x_q8 += (int32_t)(((int64_t)p->vx_q8 * dt_ms) / 1000);
        p->y_q8 += (int32_t)(((int64_t)p->vy_q8 * dt_ms) / 1000);
        if (map != nullptr && p->dies_on_tile) {
            const int x = (int)(p->x_q8 >> 8), y = (int)(p->y_q8 >> 8);
            if (vxpe_tilemap_rect_flags(map, x, y, x + p->w, y + p->h) & VXPE_TF_SOLID) {
                p->active = 0;
                continue;
            }
        }
        ++alive;
    }
    return alive;
}

int vxpe_proj_resolve(VxpeProjectilePool2D* pool, VxpeCombatant2D* targets,
                      int target_count, VxpeCombatEvent2D* events, int max_events) {
    if (pool == nullptr || targets == nullptr || target_count <= 0) return 0;
    int written = 0;
    for (int i = 0; i < pool->count; ++i) {
        VxpeProjectile2D* p = &pool->items[i];
        if (!p->active) continue;
        VxpeRectI pb;
        pb.x = (int16_t)(p->x_q8 >> 8);
        pb.y = (int16_t)(p->y_q8 >> 8);
        pb.w = (int16_t)p->w;
        pb.h = (int16_t)p->h;
        for (int j = 0; j < target_count; ++j) {
            VxpeCombatant2D* t = &targets[j];
            if (!t->alive || t->team == p->team) continue;
            const uint32_t bit = 1u << (t->slot & 31);
            if (p->hit_mask & bit) continue;
            VxpeRectI tb;
            vxpe_combat_hurtbox(t, &tb);
            if (!rects_overlap(&pb, &tb)) continue;
            p->hit_mask |= bit;
            VxpeCombatEvent2D e{};
            const int dir = p->vx_q8 >= 0 ? 1 : -1;
            const int landed = vxpe_combat_hurt(t, p->damage, dir, p->kb_x_q8,
                                                p->kb_y_q8, p->invuln_ms, p->stun_ms,
                                                p->hit_stop_ms, -1, &e);
            if (landed) impact(&pb, &tb, &e);
            else if (e.kind != VXPE_CE2D_BLOCKED) continue;
            push_event(events, &written, max_events, &e);
            if (!p->pierce) { p->active = 0; break; }
        }
    }
    return written;
}

int vxpe_proj_overlaps(const VxpeProjectilePool2D* pool, int x, int y, int w, int h) {
    if (pool == nullptr || w <= 0 || h <= 0) return 0;
    VxpeRectI r;
    r.x = (int16_t)x; r.y = (int16_t)y; r.w = (int16_t)w; r.h = (int16_t)h;
    for (int i = 0; i < pool->count; ++i) {
        const VxpeProjectile2D* p = &pool->items[i];
        if (!p->active) continue;
        VxpeRectI pb;
        pb.x = (int16_t)(p->x_q8 >> 8);
        pb.y = (int16_t)(p->y_q8 >> 8);
        pb.w = (int16_t)p->w;
        pb.h = (int16_t)p->h;
        if (rects_overlap(&r, &pb)) return 1;
    }
    return 0;
}

}  /* extern "C" */
