/*
 * The combat core has to be reachable from the C project template: this file
 * is compiled as C99 and drives every entry point with plain initialisers, so a
 * game written in C never has to link a single C++ symbol.
 */
#include "action2d/VxpCombat2D.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

#define TILE 16
#define MAP_W 20
#define MAP_H 12
#define FLOOR_ROW 9

static uint16_t cells[MAP_W * MAP_H];
static uint16_t flags[MAP_W * MAP_H];
static uint16_t atlas_px[TILE * TILE];
static VxpeSprite565 atlas;
static VxpeTilemap2D level;

/* A C99 designated initialiser: the field names are the contract a game reads,
 * so this also proves the struct layout stays source-compatible for C. */
static const VxpeAttack2D whip = {
    .off_x = 12, .off_y = 4, .w = 18, .h = 10,
    .windup_ms = 90, .active_ms = 60, .recover_ms = 150,
    .damage = 4,
    .kb_x_q8 = 120 * 256, .kb_y_q8 = -60 * 256,
    .invuln_ms = 400, .hit_stop_ms = 60, .stun_ms = 150,
    .pierce = 0, .pad_ = 0
};

static void build_level(void) {
    int x, y;
    memset(cells, 0, sizeof(cells));
    memset(flags, 0, sizeof(flags));
    for (y = FLOOR_ROW; y < MAP_H; ++y) {
        for (x = 0; x < MAP_W; ++x) {
            cells[y * MAP_W + x] = 1;
            flags[y * MAP_W + x] = VXPE_TF_SOLID;
        }
    }
    for (x = 0; x < TILE * TILE; ++x) atlas_px[x] = (uint16_t)(x + 1);
    atlas.pixels = atlas_px;
    atlas.mask = 0;
    atlas.width = TILE; atlas.height = TILE;
    atlas.stride = TILE; atlas.opaque = 1;
    level.cells = cells; level.flags = flags; level.atlas = &atlas;
    level.width = MAP_W; level.height = MAP_H;
    level.tile_w = TILE; level.tile_h = TILE;
    level.atlas_cols = 1; level.oob_blocks = 0;
}

int main(void) {
    VxpeBodyTuning2D tune;
    VxpeBodyIntent2D drive;
    VxpeBody2D hero_body, foe_body;
    VxpeCombatant2D hero, foe;
    VxpeProjectilePool2D pool;
    VxpeProjectile2D arrow;
    VxpeProjectile2D* shot;
    VxpeCombatEvent2D events[4];
    VxpeRectI box;
    int f, n;

    build_level();
    vxpe_body_tuning_default(&tune);

    vxpe_body_init(&hero_body, 64, FLOOR_ROW * TILE - 22, 12, 22);
    vxpe_body_init(&foe_body, 74, FLOOR_ROW * TILE - 22, 12, 22);
    vxpe_combat_init(&hero, &hero_body, 30, 0, 0);
    vxpe_combat_init(&foe, &foe_body, 30, 1, 1);
    assert(foe.alive && hero.hp == 30);

    memset(&drive, 0, sizeof(drive));
    drive.x = 1;

    /* Wind the swing up while both bodies fall onto the floor: step until the
     * active window opens, which is what a game loop really does. */
    assert(vxpe_combat_attack(&hero, &whip) == 1);
    for (f = 0; f < 10 && !vxpe_combat_hitbox(&hero, &box); ++f) {
        vxpe_combat_update(&hero, 33, 0, 0);
        vxpe_combat_update(&foe, 33, 0, 0);
        vxpe_combat_body_control(&hero, &level, &tune, &drive, 33);
        vxpe_combat_body_step(&foe, &level, &tune, 33);
    }
    assert(vxpe_combat_hitbox(&hero, &box));
    assert(box.w == 18 && box.h == 10);

    n = vxpe_combat_resolve(&hero, 1, &foe, 1, events, 4);
    assert(n == 1);
    assert(events[0].kind == VXPE_CE2D_HIT);
    assert(events[0].damage == 4 && events[0].hp_left == 26);
    assert(foe.invuln_ms == 400 && foe.freeze_ms == 60);
    assert(hero.freeze_ms == 60);

    /* A second press inside the immunity window is reported as a block. */
    for (f = 0; f < 12; ++f) vxpe_combat_update(&hero, 33, 0, 0);
    assert(!vxpe_combat_attacking(&hero));
    assert(vxpe_combat_attack(&hero, &whip) == 1);
    for (f = 0; f < 10 && !vxpe_combat_hitbox(&hero, &box); ++f) vxpe_combat_update(&hero, 33, 0, 0);
    assert(vxpe_combat_hitbox(&hero, &box));
    assert(vxpe_combat_resolve(&hero, 1, &foe, 1, events, 4) == 1);
    assert(events[0].kind == VXPE_CE2D_BLOCKED);
    assert(foe.hp == 26);

    /* Projectiles from C: spawn, fly, hit, and the pool reports its survivors. */
    vxpe_proj_pool_init(&pool);
    memset(&arrow, 0, sizeof(arrow));
    arrow.w = 5; arrow.h = 5;
    arrow.vx_q8 = 140 * 256;
    arrow.damage = 3;
    arrow.life_ms = 800;
    arrow.kb_x_q8 = 80 * 256;
    arrow.invuln_ms = 100;
    arrow.team = 0;
    arrow.dies_on_tile = 1;
    foe.invuln_ms = 0;
    foe.freeze_ms = 0;
    shot = vxpe_proj_spawn(&pool, &arrow, 20, FLOOR_ROW * TILE - 12);
    assert(shot != 0);
    assert(shot->x_q8 == 20 * 256);
    assert(vxpe_proj_update(&pool, &level, 33) == 1);
    assert(shot->x_q8 > 20 * 256);
    assert(vxpe_proj_overlaps(&pool, 20, FLOOR_ROW * TILE - 12, 40, 12));

    /* Drive the shot into the foe by simply letting it fly. */
    n = 0;
    for (f = 0; f < 30; ++f) {
        vxpe_proj_update(&pool, &level, 33);
        n += vxpe_proj_resolve(&pool, &foe, 1, events, 4);
        if (n) break;
    }
    assert(n == 1);
    assert(events[0].kind == VXPE_CE2D_HIT && events[0].damage == 3);
    assert(foe.hp == 23);
    assert(vxpe_proj_update(&pool, &level, 33) == 0);   /* spent, pool empty */

    /* Environmental damage needs no attacker at all. */
    assert(vxpe_combat_hurt(&hero, 5, -1, 0, 0, 50, 0, 0, -1, events) == 1);
    assert(events[0].attacker == 0xFF && hero.hp == 25);
    assert(hero.invuln_ms == 50);
    printf("combat2d C API ok\n");
    return 0;
}
