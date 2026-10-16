/*
 * Regression coverage for VxpCombat2D: the three-window swing model, facing
 * mirrored hitboxes, i-frames, knockback, hit-stop, stun cancellation, per
 * swing hit tracking and the projectile pool.
 *
 * Every case steps a fixed dt and reads back exact Q8 values, so the file is a
 * specification of the timings a game is allowed to rely on.
 */
#include "action2d/VxpCombat2D.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

#define TILE 16
#define MAP_W 20
#define MAP_H 15
#define FLOOR_ROW 12
#define BW 12
#define BH 22

namespace {

uint16_t g_cells[MAP_W * MAP_H];
uint16_t g_flags[MAP_W * MAP_H];
uint16_t g_atlasPx[TILE * TILE];
VxpeSprite565 g_atlas;
VxpeTilemap2D g_map;

VxpeAttack2D g_slash;    /* single target, medium swing */
VxpeAttack2D g_sweep;    /* same timings, pierce */
VxpeAttack2D g_heavy;    /* long windup, huge knockback */

void build_world() {
    memset(g_cells, 0, sizeof(g_cells));
    memset(g_flags, 0, sizeof(g_flags));
    for (int y = FLOOR_ROW; y < MAP_H; ++y) {
        for (int x = 0; x < MAP_W; ++x) {
            g_cells[y * MAP_W + x] = 1;
            g_flags[y * MAP_W + x] = VXPE_TF_SOLID;
        }
    }
    for (int i = 0; i < TILE * TILE; ++i) g_atlasPx[i] = (uint16_t)(i + 1);
    g_atlas.pixels = g_atlasPx;
    g_atlas.mask = nullptr;
    g_atlas.width = TILE; g_atlas.height = TILE;
    g_atlas.stride = TILE; g_atlas.opaque = 1;
    g_map.cells = g_cells; g_map.flags = g_flags; g_map.atlas = &g_atlas;
    g_map.width = MAP_W; g_map.height = MAP_H;
    g_map.tile_w = TILE; g_map.tile_h = TILE;
    g_map.atlas_cols = 1; g_map.oob_blocks = 0;
}

void build_attacks() {
    memset(&g_slash, 0, sizeof(g_slash));
    g_slash.off_x = 10; g_slash.off_y = 2; g_slash.w = 14; g_slash.h = 12;
    g_slash.windup_ms = 60; g_slash.active_ms = 90; g_slash.recover_ms = 120;
    g_slash.damage = 3;
    g_slash.kb_x_q8 = 150 * 256; g_slash.kb_y_q8 = -90 * 256;
    g_slash.invuln_ms = 500; g_slash.hit_stop_ms = 90; g_slash.stun_ms = 200;
    g_slash.pierce = 0;

    g_sweep = g_slash;
    g_sweep.w = 26; g_sweep.h = 22; g_sweep.off_x = 4; g_sweep.off_y = 0;
    g_sweep.pierce = 1;

    g_heavy = g_slash;
    g_heavy.windup_ms = 240; g_heavy.active_ms = 60; g_heavy.recover_ms = 400;
    g_heavy.damage = 9; g_heavy.kb_x_q8 = 220 * 256; g_heavy.kb_y_q8 = -140 * 256;
}

/* A body resting on the floor with its box top-left at (x, FLOOR_ROW*TILE-BH). */
void place(VxpeBody2D* body, int x) {
    vxpe_body_init(body, x, FLOOR_ROW * TILE - BH, BW, BH);
}

int feet_on_floor(const VxpeBody2D* body) {
    return (int)((body->y_q8 >> 8) + body->h) == FLOOR_ROW * TILE;
}

/* Advance a swing until its hitbox is live, then return once. */
void wind_up(VxpeCombatant2D* c, uint16_t dt_ms) {
    VxpeRectI hb;
    int guard = 0;
    while (!vxpe_combat_hitbox(c, &hb) && ++guard < 64) vxpe_combat_update(c, dt_ms, nullptr, 0);
    assert(vxpe_combat_hitbox(c, &hb));
}

/* ---------------------------------------------------------------- windows */
void test_windows() {
    VxpeBody2D body;
    place(&body, 100);
    VxpeCombatant2D a;
    vxpe_combat_init(&a, &body, 20, 0, 0);

    VxpeRectI hb;
    assert(!vxpe_combat_hitbox(&a, &hb));
    assert(!vxpe_combat_attacking(&a));
    assert(vxpe_combat_attack(&a, &g_slash) == 1);
    assert(vxpe_combat_attacking(&a));
    /* A swing already running cannot be replaced, so mash spam cannot cancel
     * recovery into a faster attack. */
    assert(vxpe_combat_attack(&a, &g_heavy) == 0);
    assert(a.atk == &g_slash);

    VxpeCombatEvent2D ev[4];
    int total_events = 0;
    /* windup 60 / active 90 / recover 120 at 30 ms: live from the 2nd update
     * (60 ms) until the 5th (150 ms), finished at the 9th (270 ms). */
    int live_frames = 0;
    for (int f = 0; f < 9; ++f) {
        const int n = vxpe_combat_update(&a, 30, ev, 4);
        total_events += n;
        for (int i = 0; i < n; ++i) {
            if (ev[i].kind == VXPE_CE2D_WINDUP) assert(f == 1);
            if (ev[i].kind == VXPE_CE2D_SWING_END) assert(f == 8);
        }
        if (vxpe_combat_hitbox(&a, &hb)) ++live_frames;
    }
    assert(live_frames == 3);
    assert(!vxpe_combat_attacking(&a));
    assert(a.atk_ms == 0 && a.swing_mask == 0);
    assert(total_events == 2);  /* one WINDUP and one SWING_END for a swing */

    /* Recovery is vulnerable but cannot attack; the next press lands only once
     * the whole swing has elapsed. */
    assert(vxpe_combat_attack(&a, &g_slash) == 1);
    assert(vxpe_combat_attack(&a, &g_slash) == 0);
    for (int f = 0; f < 8; ++f) vxpe_combat_update(&a, 30, nullptr, 0);
    assert(vxpe_combat_attacking(&a));
    vxpe_combat_update(&a, 30, nullptr, 0);
    assert(!vxpe_combat_attacking(&a));
    assert(vxpe_combat_attack(&a, &g_slash) == 1);
    vxpe_combat_update(&a, 30, nullptr, 0);
    vxpe_combat_update(&a, 30, nullptr, 0);

    /* A 0-length active window can never connect. */
    VxpeAttack2D poke = g_slash;
    poke.active_ms = 0;
    VxpeCombatant2D p;
    vxpe_combat_init(&p, &body, 5, 0, 2);
    assert(vxpe_combat_attack(&p, &poke) == 1);
    int never = 0;
    for (int f = 0; f < 30; ++f) never += vxpe_combat_hitbox(&p, &hb);
    assert(never == 0);
    printf("  windows: 3 live frames of 9, windup and end events once\n");
}

/* ----------------------------------------------------------------- facing */
void test_facing() {
    VxpeBody2D body;
    place(&body, 100);
    body.facing = 1;
    VxpeCombatant2D a;
    vxpe_combat_init(&a, &body, 20, 0, 0);
    assert(vxpe_combat_attack(&a, &g_slash) == 1);
    wind_up(&a, 30);

    VxpeRectI right, left;
    assert(vxpe_combat_hitbox(&a, &right));
    assert(right.x == 100 + 10 && right.y == (FLOOR_ROW * TILE - BH) + 2);
    assert(right.w == 14 && right.h == 12);

    body.facing = 0;
    assert(vxpe_combat_hitbox(&a, &left));
    /* Mirrored about the body box: the blade stays the same distance from the
     * hero's back edge, so it is still in front of it. */
    assert(left.x == 100 + BW - 10 - 14);
    assert(left.x + left.w == 100 + BW - 10);
    assert(left.y == right.y);
    /* The blade crosses the body's centre line when it turns: off_x is a gap
     * measured from the trailing edge, so a swing authored to start 2 px inside
     * the hero's front still starts 2 px inside it after a turn. */
    const int mid = 100 + BW / 2;
    assert(right.x >= mid && left.x + left.w <= mid);

    /* A combatant with no body has no hitbox: a static turret is a target, not
     * a swing. */
    VxpeCombatant2D ghost;
    vxpe_combat_init(&ghost, nullptr, 1, 0, 3);
    assert(vxpe_combat_attack(&ghost, &g_slash) == 1);
    assert(!vxpe_combat_hitbox(&ghost, &right));
    printf("  facing: hitbox mirrors about the body box\n");
}

/* ------------------------------------------------------------------ melee */
void test_melee() {
    VxpeBodyTuning2D tune;
    vxpe_body_tuning_default(&tune);

    VxpeBody2D bodyA, bodyB;
    place(&bodyA, 100);
    place(&bodyB, 112);
    VxpeCombatant2D a, b;
    vxpe_combat_init(&a, &bodyA, 20, 0, 0);
    vxpe_combat_init(&b, &bodyB, 20, 1, 1);

    assert(vxpe_combat_attack(&a, &g_slash) == 1);
    wind_up(&a, 30);

    VxpeCombatEvent2D ev[4];
    const int n = vxpe_combat_resolve(&a, 1, &b, 1, ev, 4);
    assert(n == 1);
    assert(ev[0].kind == VXPE_CE2D_HIT);
    assert(ev[0].attacker == 0 && ev[0].victim == 1);
    assert(ev[0].damage == 3 && ev[0].hp_left == 17);
    /* Overlap centre of hitbox [110,124)x[172,184) and hurtbox
     * [112,124)x[170,192). */
    assert(ev[0].x == 118 && ev[0].y == 178);
    assert(b.hp == 17 && b.alive);
    assert(b.invuln_ms == 500 && b.stun_ms == 200 && b.freeze_ms == 90);
    assert(b.flash_ms == 500);          /* blinks exactly while immune */
    assert(bodyB.vx_q8 == 150 * 256);   /* flung away from the attacker */
    assert(bodyB.vy_q8 == -90 * 256);
    assert(!bodyB.on_ground && bodyB.coyote_ms == 0);
    assert(a.freeze_ms == 90);          /* hit-stop holds both still */
    assert(a.swing_mask == (1u << 1));

    /* Still inside the same active window: the mask, not a second timer, is
     * what stops the slash re-biting every frame. */
    vxpe_combat_update(&a, 30, nullptr, 0);
    VxpeRectI hb;
    assert(vxpe_combat_hitbox(&a, &hb));
    assert(vxpe_combat_resolve(&a, 1, &b, 1, ev, 4) == 0);
    assert(b.hp == 17);

    /* Hit-stop really freezes the bodies. */
    const int32_t frozen_x = bodyB.x_q8;
    for (int f = 0; f < 3; ++f) {
        vxpe_combat_body_step(&b, &g_map, &tune, 33);
        assert(bodyB.x_q8 == frozen_x);
        vxpe_combat_update(&b, 33, nullptr, 0);
    }
    assert(b.freeze_ms == 0);
    vxpe_combat_body_step(&b, &g_map, &tune, 33);
    assert(bodyB.x_q8 != frozen_x);

    /* I-frames absorb the next swing entirely, but the block is still reported
     * so a game can play a shield tick. */
    VxpeCombatant2D a2;
    vxpe_combat_init(&a2, &bodyA, 20, 0, 4);
    assert(vxpe_combat_attack(&a2, &g_slash) == 1);
    wind_up(&a2, 30);
    assert(b.invuln_ms > 0);
    assert(vxpe_combat_resolve(&a2, 1, &b, 1, ev, 4) == 1);
    assert(ev[0].kind == VXPE_CE2D_BLOCKED);
    assert(ev[0].damage == 0 && ev[0].hp_left == 17);
    assert(b.hp == 17);

    /* Once immunity lapses the same blow lands. */
    for (int f = 0; f < 20 && b.invuln_ms; ++f) vxpe_combat_update(&b, 33, nullptr, 0);
    assert(b.invuln_ms == 0 && b.flash_ms == 0);
    VxpeCombatant2D a3;
    vxpe_combat_init(&a3, &bodyA, 20, 0, 5);
    assert(vxpe_combat_attack(&a3, &g_slash) == 1);
    wind_up(&a3, 30);
    assert(vxpe_combat_resolve(&a3, 1, &b, 1, ev, 4) == 1);
    assert(ev[0].kind == VXPE_CE2D_HIT && b.hp == 14);

    /* Stun cancels an in-flight swing the moment the blow lands, and blocks a
     * new one until it wears off. */
    VxpeCombatant2D c;
    vxpe_combat_init(&c, &bodyA, 30, 0, 6);
    assert(vxpe_combat_attack(&c, &g_slash) == 1);
    wind_up(&c, 30);
    assert(vxpe_combat_attacking(&c));
    VxpeCombatEvent2D one;
    assert(vxpe_combat_hurt(&c, 1, 1, 0, 0, 0, 200, 0, -1, &one) == 1);
    assert(one.kind == VXPE_CE2D_HIT && c.stun_ms == 200);
    assert(!vxpe_combat_attacking(&c));   /* dead on arrival, not next frame */
    assert(vxpe_combat_update(&c, 33, &one, 1) == 0);
    assert(vxpe_combat_attack(&c, &g_slash) == 0);

    /* The same cancel through the public field, for a grab or a phase change:
     * the update owns it and reports it as a swing end. */
    VxpeCombatant2D grabbed;
    vxpe_combat_init(&grabbed, &bodyA, 30, 0, 7);
    assert(vxpe_combat_attack(&grabbed, &g_slash) == 1);
    wind_up(&grabbed, 30);
    grabbed.stun_ms = 200;
    assert(vxpe_combat_update(&grabbed, 33, &one, 1) == 1);
    assert(one.kind == VXPE_CE2D_SWING_END);
    assert(!vxpe_combat_attacking(&grabbed));
    printf("  melee: one hit per swing, i-frames, hit-stop, stun cancel\n");
}

/* ------------------------------------------------------------------- teams
 * Also covers the kill clamp and the per-swing pierce rule. */
void test_teams_and_death() {
    VxpeBody2D bodies[4];
    VxpeCombatant2D unit[4];
    place(&bodies[0], 100); place(&bodies[1], 112);
    place(&bodies[2], 118); place(&bodies[3], 104);
    /* Deliberately one array: resolve() walks a caller-owned range, so the
     * victims have to be contiguous. */
    vxpe_combat_init(&unit[0], &bodies[0], 20, 0, 0);   /* attacker   */
    vxpe_combat_init(&unit[1], &bodies[1], 20, 1, 1);   /* victim 1   */
    vxpe_combat_init(&unit[2], &bodies[2], 20, 1, 2);   /* victim 2   */
    vxpe_combat_init(&unit[3], &bodies[3], 20, 0, 3);   /* own team   */
    VxpeCombatant2D* atk = &unit[0];
    VxpeCombatant2D* mate = &unit[3];

    VxpeCombatEvent2D ev[4];
    assert(vxpe_combat_attack(atk, &g_slash) == 1);
    wind_up(atk, 30);
    /* Attacking yourself and your own team never registers, even when the
     * boxes overlap - which they do here on purpose. */
    assert(vxpe_combat_resolve(atk, 1, atk, 1, ev, 4) == 0);
    assert(vxpe_combat_resolve(atk, 1, mate, 1, ev, 4) == 0);
    assert(mate->hp == 20 && atk->hp == 20);

    /* A non-piercing slash takes the first victim it finds only. */
    assert(vxpe_combat_resolve(atk, 1, &unit[1], 2, ev, 4) == 1);
    assert(unit[1].hp == 17 && unit[2].hp == 20);

    /* A sweep reaches straight past an ally who is still immune from that
     * slash: the block is reported, but only a connect that draws blood spends
     * the swing, so an invulnerable body cannot be used as a shield. */
    assert(unit[1].invuln_ms > 0);
    VxpeCombatant2D sweeper;
    vxpe_combat_init(&sweeper, &bodies[0], 20, 0, 4);
    assert(vxpe_combat_attack(&sweeper, &g_sweep) == 1);
    wind_up(&sweeper, 30);
    assert(vxpe_combat_resolve(&sweeper, 1, &unit[1], 2, ev, 4) == 2);
    assert(ev[0].kind == VXPE_CE2D_BLOCKED && unit[1].hp == 17);
    assert(ev[1].kind == VXPE_CE2D_HIT && unit[2].hp == 17);
    assert(sweeper.swing_mask == (1u << 2));   /* only the one it bled */

    /* Over-damage clamps to the remaining hit points and kills once. */
    VxpeCombatant2D pair[2];
    vxpe_combat_init(&pair[0], &bodies[1], 2, 1, 5);
    vxpe_combat_init(&pair[1], &bodies[0], 20, 0, 6);
    assert(vxpe_combat_attack(&pair[1], &g_heavy) == 1);
    wind_up(&pair[1], 30);
    assert(vxpe_combat_resolve(&pair[1], 1, &pair[0], 1, ev, 4) == 1);
    assert(ev[0].kind == VXPE_CE2D_KILL);
    assert(ev[0].damage == 2 && ev[0].hp_left == 0);
    assert(pair[0].hp == 0 && !pair[0].alive && pair[0].atk == nullptr);
    VxpeRectI hb;
    assert(!vxpe_combat_hitbox(&pair[0], &hb));
    /* A corpse is not a target any more. */
    assert(vxpe_combat_resolve(&pair[1], 1, &pair[0], 1, ev, 4) == 0);
    assert(vxpe_combat_hurt(&pair[0], 5, 1, 0, 0, 0, 0, 0, 0, &ev[0]) == 0);
    printf("  teams: friendly fire off, pierce on, over-kill clamped\n");
}

/* ------------------------------------------------------- body integration */
void test_body_rules() {
    VxpeBodyTuning2D tune;
    vxpe_body_tuning_default(&tune);
    VxpeBody2D body;
    place(&body, 60);
    VxpeCombatant2D c;
    vxpe_combat_init(&c, &body, 30, 0, 0);
    VxpeBodyIntent2D in;
    memset(&in, 0, sizeof(in));
    in.x = 1;

    /* Idle on the floor, then a stunned frame: gravity and friction survive,
     * steering does not. */
    for (int f = 0; f < 4; ++f) vxpe_combat_body_control(&c, &g_map, &tune, &in, 33);
    assert(feet_on_floor(&body) && body.on_ground);
    assert(body.vx_q8 > 0);
    const int32_t running = body.vx_q8;
    vxpe_combat_hurt(&c, 1, -1, 0, 0, 0, 300, 0, 1, nullptr);
    assert(c.stun_ms > 0);
    vxpe_combat_update(&c, 1, nullptr, 0);
    body.vx_q8 = running;
    for (int f = 0; f < 3; ++f) {
        vxpe_combat_body_control(&c, &g_map, &tune, &in, 33);
        assert(body.vx_q8 < running);   /* friction, never the run accel */
    }

    /* Frozen means no movement at all, for control and for step alike. */
    c.stun_ms = 0;
    c.freeze_ms = 100;
    const int32_t x0 = body.x_q8, y0 = body.y_q8;
    for (int f = 0; f < 3; ++f) {
        vxpe_combat_body_control(&c, &g_map, &tune, &in, 33);
        vxpe_combat_body_step(&c, &g_map, &tune, 33);
        assert(body.x_q8 == x0 && body.y_q8 == y0);
    }
    assert(vxpe_combat_frozen(&c));
    vxpe_combat_update(&c, 120, nullptr, 0);
    assert(!vxpe_combat_frozen(&c));
    vxpe_combat_body_step(&c, &g_map, &tune, 33);
    assert(body.x_q8 != x0 || body.y_q8 != y0);

    /* A dead combatant stops being driven entirely. */
    c.alive = 0;
    const int32_t dead_x = body.x_q8;
    for (int f = 0; f < 5; ++f) {
        vxpe_combat_body_step(&c, &g_map, &tune, 33);
        vxpe_combat_body_control(&c, &g_map, &tune, &in, 33);
    }
    assert(body.x_q8 == dead_x);
    assert(vxpe_combat_attack(&c, &g_slash) == 0);
    printf("  bodies: stun keeps gravity, hit-stop freezes, death stops\n");
}

/* -------------------------------------------------------------- projectiles */
void test_projectiles() {
    VxpeProjectilePool2D pool;
    vxpe_proj_pool_init(&pool);
    assert(pool.count == 0);
    assert(vxpe_proj_update(&pool, &g_map, 33) == 0);

    VxpeProjectile2D shot;
    memset(&shot, 0, sizeof(shot));
    shot.w = 6; shot.h = 6;
    shot.vx_q8 = 120 * 256;
    shot.damage = 2;
    shot.life_ms = 900;
    shot.kb_x_q8 = 60 * 256;
    shot.invuln_ms = 200;
    shot.stun_ms = 0;
    shot.hit_stop_ms = 40;
    shot.team = 1;
    shot.dies_on_tile = 1;

    /* Motion is exact Q8 integration: 30720 * 33 / 1000 = 1013 units. */
    VxpeProjectile2D* p = vxpe_proj_spawn(&pool, &shot, 200, 100);
    assert(p != nullptr && pool.count == 1);
    assert(p->x_q8 == 200 * 256 && p->y_q8 == 100 * 256);
    assert(vxpe_proj_update(&pool, &g_map, 33) == 1);
    assert(p->x_q8 == 200 * 256 + 1013);
    assert(p->life_ms == 900 - 33);

    /* Gravity accumulates before the position, like the body mover. */
    VxpeProjectile2D lob = shot;
    lob.vx_q8 = 0; lob.gravity_q8 = 640 * 256; lob.x_q8 = lob.y_q8 = 0;
    VxpeProjectile2D* q = vxpe_proj_spawn(&pool, &lob, 60, 60);
    assert(q != nullptr);
    assert(vxpe_proj_update(&pool, &g_map, 33) == 2);
    assert(q->vy_q8 == (int32_t)((int64_t)640 * 256 * 33) / 1000);
    assert(q->y_q8 == 60 * 256 + (q->vy_q8 * 33) / 1000);

    /* Lifetime expiry is the only way a shot over open ground goes away. */
    VxpeProjectile2D fuse = shot;
    fuse.vx_q8 = 0; fuse.life_ms = 30;
    VxpeProjectile2D* r = vxpe_proj_spawn(&pool, &fuse, 60, 60);
    assert(vxpe_proj_update(&pool, &g_map, 33) == 2);
    assert(!r->active);

    /* dies_on_tile stops a shot dead in a wall; the same shot over a blank
     * cell keeps flying. */
    VxpeProjectile2D into_floor = shot;
    into_floor.vx_q8 = 0;
    VxpeProjectile2D* s = vxpe_proj_spawn(&pool, &into_floor, 100, FLOOR_ROW * TILE + 2);
    assert(vxpe_proj_update(&pool, &g_map, 33) == 2);
    assert(!s->active);
    VxpeProjectile2D* s2 = vxpe_proj_spawn(&pool, &into_floor, 100, 100);
    assert(vxpe_proj_update(&pool, &g_map, 33) == 3);
    assert(s2->active);

    /* Same shot, no tile test: passes straight through the floor. */
    VxpeProjectile2D ghost = shot;
    ghost.vx_q8 = 0; ghost.dies_on_tile = 0;
    VxpeProjectile2D* s3 = vxpe_proj_spawn(&pool, &ghost, 100, FLOOR_ROW * TILE + 2);
    assert(vxpe_proj_update(&pool, &g_map, 33) == 4);
    assert(s3->active);

    vxpe_proj_pool_init(&pool);
    assert(vxpe_proj_update(&pool, &g_map, 33) == 0);

    /* Pool capacity is the documented 24 slots. */
    int spawned = 0;
    for (int i = 0; i < VXPE_PROJ_POOL2D_MAX + 6; ++i) {
        if (vxpe_proj_spawn(&pool, &shot, 40 + i * 4, 60) != nullptr) ++spawned;
    }
    assert(spawned == VXPE_PROJ_POOL2D_MAX);
    assert(pool.count == VXPE_PROJ_POOL2D_MAX);
    vxpe_proj_pool_init(&pool);

    /* --- resolve --- */
    VxpeBody2D tb;
    place(&tb, 100);
    VxpeCombatant2D target;
    vxpe_combat_init(&target, &tb, 20, 0, 1);

    /* A shot on the same team is ignored and stays in flight. */
    VxpeProjectile2D friendly = shot;
    friendly.vx_q8 = 0;
    friendly.team = 0;
    assert(vxpe_proj_spawn(&pool, &friendly, 100, 170) != nullptr);
    assert(vxpe_proj_resolve(&pool, &target, 1, nullptr, 0) == 0);
    assert(target.hp == 20 && pool.items[0].active);

    /* Enemy shot overlapping the hurtbox: damage, knockback along the travel
     * direction, and the shot is spent. */
    vxpe_proj_pool_init(&pool);
    VxpeProjectile2D enemy = shot;
    enemy.vx_q8 = -120 * 256;
    assert(vxpe_proj_spawn(&pool, &enemy, 102, 172) != nullptr);
    VxpeCombatEvent2D ev[4];
    assert(vxpe_proj_resolve(&pool, &target, 1, ev, 4) == 1);
    assert(ev[0].kind == VXPE_CE2D_HIT && ev[0].damage == 2 && ev[0].hp_left == 18);
    assert(ev[0].attacker == 0xFF);   /* a shot has no slot */
    assert(ev[0].victim == 1);
    assert(target.hp == 18 && target.invuln_ms == 200 && target.freeze_ms == 40);
    assert(tb.vx_q8 == -60 * 256);    /* flung the way the arrow was travelling */
    assert(!pool.items[0].active);

    /* A piercing shot stays alive and cannot re-hit the same target on the
     * next frame, but will hit a second one. Drop the immunity the arrow above
     * left behind: this case is about the hit mask, not about blocking. */
    target.invuln_ms = 0;
    target.freeze_ms = 0;
    vxpe_proj_pool_init(&pool);
    VxpeProjectile2D lance = shot;
    lance.vx_q8 = 0; lance.pierce = 1; lance.invuln_ms = 0; lance.hit_stop_ms = 0;
    assert(vxpe_proj_spawn(&pool, &lance, 102, 172) != nullptr);
    assert(vxpe_proj_resolve(&pool, &target, 1, ev, 4) == 1);
    assert(pool.items[0].active && pool.items[0].hit_mask == (1u << 1));
    assert(vxpe_proj_resolve(&pool, &target, 1, ev, 4) == 0);  /* already bled */
    VxpeBody2D tb2;
    place(&tb2, 104);
    VxpeCombatant2D second;
    vxpe_combat_init(&second, &tb2, 9, 0, 2);
    assert(vxpe_proj_resolve(&pool, &second, 1, ev, 4) == 1);
    assert(second.hp == 7 && target.hp == 16);

    /* I-frames block a shot without spending it, but the slot it bled is still
     * marked so a pierce does not shred one immune target every frame. */
    vxpe_proj_pool_init(&pool);
    assert(vxpe_proj_spawn(&pool, &lance, 102, 172) != nullptr);
    target.invuln_ms = 300;
    assert(vxpe_proj_resolve(&pool, &target, 1, ev, 4) == 1);
    assert(ev[0].kind == VXPE_CE2D_BLOCKED && target.hp == 16);
    assert(pool.items[0].active);        /* a pierce keeps flying */
    assert(pool.items[0].hit_mask == (1u << 1));
    target.invuln_ms = 0;

    /* Event capacity never throttles damage: three shots, two event slots, all
     * three targets still bleed. Bodies sit 24 px apart so each shot can only
     * reach its own target. */
    vxpe_proj_pool_init(&pool);
    VxpeBody2D bodies[3];
    VxpeCombatant2D squad[3];
    for (int i = 0; i < 3; ++i) {
        place(&bodies[i], 40 + i * 24);
        vxpe_combat_init(&squad[i], &bodies[i], 20, 0, i);
        VxpeProjectile2D one = shot;
        one.vx_q8 = 0; one.hit_stop_ms = 0;
        assert(vxpe_proj_spawn(&pool, &one, 40 + i * 24, 172) != nullptr);
    }
    VxpeCombatEvent2D two[2];
    assert(vxpe_proj_resolve(&pool, squad, 3, two, 2) == 2);
    assert(squad[0].hp == 18 && squad[1].hp == 18 && squad[2].hp == 18);

    /* Overlap query, for a shield or a "clear the doorway" check. */
    vxpe_proj_pool_init(&pool);
    VxpeProjectile2D still = shot;
    still.vx_q8 = 0;
    assert(vxpe_proj_spawn(&pool, &still, 100, 170) != nullptr);
    assert(vxpe_proj_overlaps(&pool, 100, 170, 6, 6));
    assert(vxpe_proj_overlaps(&pool, 105, 175, 1, 1));
    assert(!vxpe_proj_overlaps(&pool, 106, 170, 10, 10));
    assert(!vxpe_proj_overlaps(&pool, 0, 170, 100, 10));
    assert(!vxpe_proj_overlaps(&pool, 100, 170, 0, 0));
    printf("  projectiles: exact Q8 motion, tiles, lifetime, pierce, pool cap\n");
}

/* ------------------------------------------------------------- timer edges */
void test_timers() {
    VxpeBody2D body;
    place(&body, 100);
    VxpeCombatant2D c;
    vxpe_combat_init(&c, &body, 30, 0, 0);

    /* A dropped-frame dt must saturate, not wrap: a 100 ms i-frame window handed
     * a 60 s step has to end at zero, not at 60 s of immunity. */
    assert(vxpe_combat_hurt(&c, 1, 1, 0, 0, 100, 100, 100, 1, nullptr) == 1);
    assert(c.invuln_ms == 100 && c.stun_ms == 100 && c.freeze_ms == 100);
    vxpe_combat_update(&c, 60000, nullptr, 0);
    assert(c.invuln_ms == 0 && c.stun_ms == 0 && c.freeze_ms == 0 && c.flash_ms == 0);

    /* dt = 0 is legal and changes nothing. */
    assert(vxpe_combat_attack(&c, &g_slash) == 1);
    vxpe_combat_update(&c, 0, nullptr, 0);
    assert(c.atk_ms == 0 && c.atk == &g_slash);
    vxpe_combat_update(&c, 30, nullptr, 0);
    assert(c.atk_ms == 30);

    /* A swing handed a huge step ends in one update instead of wrapping past
     * its total duration and never ending. */
    vxpe_combat_update(&c, 60000, nullptr, 0);
    assert(c.atk == nullptr && c.atk_ms == 0);

    /* Repeated damage inside i-frames cannot drain the bar twice. */
    VxpeBody2D v_body;
    place(&v_body, 200);
    VxpeCombatant2D v;
    vxpe_combat_init(&v, &v_body, 10, 1, 1);
    int landed = 0;
    for (int i = 0; i < 40; ++i) {
        landed += vxpe_combat_hurt(&v, 1, 1, 0, 0, 500, 0, 0, 0, nullptr);
        vxpe_combat_update(&v, 10, nullptr, 0);   /* 10 ms < 500 ms immunity */
    }
    assert(landed == 1 && v.hp == 9);
    printf("  timers: saturating decay, dt=0 and 60 s steps both safe\n");
}

/* --------------------------------------------------------------- no-ops */
void test_null_safety() {
    VxpeBody2D body;
    place(&body, 100);
    VxpeProjectilePool2D pool;
    VxpeProjectile2D shot;
    memset(&shot, 0, sizeof(shot));
    VxpeRectI hb;
    VxpeCombatEvent2D ev;
    /* A dead combatant is the well-initialised way to reach the "nothing to do"
     * return on every entry point. */
    VxpeCombatant2D c;
    vxpe_combat_init(&c, &body, 5, 0, 0);
    c.alive = 0;

    vxpe_combat_init(nullptr, &body, 1, 0, 0);
    assert(vxpe_combat_attack(nullptr, &g_slash) == 0);
    assert(vxpe_combat_attack(&c, nullptr) == 0);
    assert(vxpe_combat_attacking(nullptr) == 0);
    assert(vxpe_combat_frozen(nullptr) == 0);
    vxpe_combat_update(nullptr, 33, &ev, 1);
    assert(vxpe_combat_hitbox(nullptr, &hb) == 0);
    assert(vxpe_combat_hitbox(&c, nullptr) == 0);
    vxpe_combat_hurtbox(nullptr, &hb);
    assert(hb.w == 0 && hb.h == 0);
    vxpe_combat_hurtbox(&c, nullptr);
    assert(vxpe_combat_hurt(nullptr, 1, 0, 0, 0, 0, 0, 0, 0, &ev) == 0);
    assert(vxpe_combat_hurt(&c, 1, 0, 0, 0, 0, 0, 0, 0, nullptr) == 0);
    assert(vxpe_combat_resolve(nullptr, 1, &c, 1, &ev, 1) == 0);
    assert(vxpe_combat_resolve(&c, 1, nullptr, 1, &ev, 1) == 0);
    assert(vxpe_combat_resolve(&c, 0, &c, 1, &ev, 1) == 0);
    assert(vxpe_combat_resolve(&c, 1, &c, 0, &ev, 1) == 0);
    vxpe_combat_body_control(nullptr, &g_map, nullptr, nullptr, 33);
    vxpe_combat_body_step(nullptr, &g_map, nullptr, 33);

    vxpe_proj_pool_init(nullptr);
    assert(vxpe_proj_spawn(nullptr, &shot, 0, 0) == nullptr);
    vxpe_proj_pool_init(&pool);
    assert(vxpe_proj_spawn(&pool, nullptr, 0, 0) == nullptr);
    assert(vxpe_proj_update(nullptr, &g_map, 33) == 0);
    assert(vxpe_proj_update(&pool, nullptr, 33) == 0);
    assert(vxpe_proj_resolve(nullptr, &c, 1, &ev, 1) == 0);
    assert(vxpe_proj_resolve(&pool, nullptr, 1, &ev, 1) == 0);
    assert(vxpe_proj_resolve(&pool, &c, 0, &ev, 1) == 0);
    assert(vxpe_proj_overlaps(nullptr, 0, 0, 4, 4) == 0);

    /* A combatant with no body is still damageable: hp, i-frames and events all
     * work, only knockback has nowhere to go. */
    VxpeCombatant2D ghost;
    vxpe_combat_init(&ghost, nullptr, 5, 0, 7);
    assert(vxpe_combat_hurt(&ghost, 2, 1, 100, -100, 0, 0, 0, 0, &ev) == 1);
    assert(ghost.hp == 3 && ev.kind == VXPE_CE2D_HIT && ev.damage == 2);
    vxpe_combat_body_step(&ghost, &g_map, nullptr, 33);
    printf("  null safety: every entry point is a no-op or a documented zero\n");
}

/* ---------------------------------------------------------- determinism */
void test_deterministic() {
    struct Snapshot {
        uint16_t hp[3];
        int32_t x[3], y[3], vx[3], vy[3];
        uint16_t invuln[3], stun[3], freeze[3];
        int events;
    } s[2];

    for (int run = 0; run < 2; ++run) {
        VxpeBodyTuning2D tune;
        vxpe_body_tuning_default(&tune);
        VxpeBody2D bodies[3];
        VxpeCombatant2D cs[3];
        place(&bodies[0], 100); place(&bodies[1], 112); place(&bodies[2], 124);
        vxpe_combat_init(&cs[0], &bodies[0], 30, 0, 0);
        vxpe_combat_init(&cs[1], &bodies[1], 30, 1, 1);
        vxpe_combat_init(&cs[2], &bodies[2], 30, 1, 2);
        VxpeProjectilePool2D pool;
        vxpe_proj_pool_init(&pool);
        VxpeCombatEvent2D ev[16];
        int events = 0;
        VxpeBodyIntent2D in;
        memset(&in, 0, sizeof(in));
        in.x = 1;

        VxpeProjectile2D shot;
        memset(&shot, 0, sizeof(shot));
        shot.w = 6; shot.h = 6; shot.vx_q8 = 90 * 256; shot.damage = 1;
        shot.life_ms = 1200; shot.kb_x_q8 = 40 * 256; shot.invuln_ms = 120;
        shot.team = 0; shot.dies_on_tile = 1;

        for (int f = 0; f < 120; ++f) {
            for (int i = 0; i < 3; ++i) events += vxpe_combat_update(&cs[i], 33, nullptr, 0);
            if ((f % 11) == 0) (void)vxpe_combat_attack(&cs[0], &g_slash);
            if ((f % 7) == 0) (void)vxpe_proj_spawn(&pool, &shot, 60, 172);
            vxpe_proj_update(&pool, &g_map, 33);
            vxpe_combat_body_control(&cs[0], &g_map, &tune, &in, 33);
            for (int i = 1; i < 3; ++i) vxpe_combat_body_step(&cs[i], &g_map, &tune, 33);
            events += vxpe_combat_resolve(cs, 3, cs, 3, ev, 16);
            events += vxpe_proj_resolve(&pool, cs, 3, ev, 16);
        }
        for (int i = 0; i < 3; ++i) {
            s[run].hp[i] = cs[i].hp;
            s[run].x[i] = bodies[i].x_q8; s[run].y[i] = bodies[i].y_q8;
            s[run].vx[i] = bodies[i].vx_q8; s[run].vy[i] = bodies[i].vy_q8;
            s[run].invuln[i] = cs[i].invuln_ms; s[run].stun[i] = cs[i].stun_ms;
            s[run].freeze[i] = cs[i].freeze_ms;
        }
        s[run].events = events;
    }
    assert(memcmp(&s[0], &s[1], sizeof(s[0])) == 0);
    assert(s[0].events > 0);
    printf("  determinism: two 120-frame melees byte-identical (%d events)\n", s[0].events);
}

}  /* namespace */

int main() {
    build_world();
    build_attacks();
    test_windows();
    test_facing();
    test_melee();
    test_teams_and_death();
    test_body_rules();
    test_projectiles();
    test_timers();
    test_null_safety();
    test_deterministic();
    printf("combat2d regression passed\n");
    return 0;
}
