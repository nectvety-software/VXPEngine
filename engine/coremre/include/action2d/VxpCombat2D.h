/*
 * Copyright (c) 2026 PixelRoot32
 * Licensed under the MIT License
 *
 * VxpCombat2D - melee hitboxes, damage with i-frames, knockback, hit-stop and
 * a projectile pool for C action games.
 *
 * This is the layer that turns VxpBody2D motion into a fight. Everything a
 * designer tunes (an attack) is a const descriptor that belongs in .rodata, and
 * everything per-entity (a combatant) is a fixed 32-byte struct the game owns
 * in static storage: nothing here allocates, so a boss with twelve adds costs
 * exactly what the level author budgeted.
 *
 * Timing is the three-window swing model: windup telegraphs the attack and has
 * no hitbox, active is the only window that can connect, and recovery leaves
 * the attacker vulnerable with no way to re-attack. That asymmetry is what
 * makes a heavy weapon feel heavy, and it costs two integer comparisons.
 *
 * Damage is applied through i-frames, so a 3-frame slash and a 30-frame
 * overlap can never deal 10x the damage, and a swing tracks which targets it
 * already bit through a per-swing mask instead of a second timer per pair.
 */
#pragma once

#include <stdint.h>
#include "action2d/VxpBody2D.h"

#ifdef __cplusplus
extern "C" {
#endif

/* One attack, shared by every entity that uses it. off_x/off_y are read from
 * the owner's collision box top-left, with off_x mirrored when the owner faces
 * left, so a swing drawn 2 px in front of a 12 px hero stays in front of it
 * after a turn. */
typedef struct VxpeAttack2D {
    int16_t off_x, off_y;
    uint16_t w, h;             /* hitbox size in px */
    uint16_t windup_ms;        /* telegraph, no hitbox */
    uint16_t active_ms;        /* hitbox live */
    uint16_t recover_ms;       /* follow-through, cannot re-attack */
    uint16_t damage;
    /* Q8.8 px/s, so int32_t: a 160 px/s launch is 40 960 and an int16_t field
     * would silently wrap it into a pull toward the attacker. */
    int32_t kb_x_q8;           /* flung away from the attacker */
    int32_t kb_y_q8;           /* negative = upward pop */
    uint16_t invuln_ms;        /* i-frames granted to the victim */
    uint16_t hit_stop_ms;      /* both bodies freeze for this long on connect */
    uint16_t stun_ms;          /* victim cannot act for this long */
    uint8_t pierce;            /* 1 = one swing may hit several targets */
    uint8_t pad_;
} VxpeAttack2D;

typedef enum VxpeCombatEventKind2D {
    VXPE_CE2D_NONE = 0,
    VXPE_CE2D_HIT = 1,     /* a blow landed and cost hit points */
    VXPE_CE2D_BLOCKED = 2, /* absorbed by i-frames: no damage, still a signal */
    VXPE_CE2D_KILL = 3,    /* the victim reached 0 hp */
    VXPE_CE2D_WINDUP = 4,  /* an attack entered its active window */
    VXPE_CE2D_SWING_END = 5
} VxpeCombatEventKind2D;

/* Written to a caller-owned array so a game can queue sound and VFX without
 * the core knowing either exists. x/y is the impact point in world px. */
typedef struct VxpeCombatEvent2D {
    uint8_t kind;
    uint8_t attacker;   /* slot of the source, 0xFF for environmental damage */
    uint8_t victim;
    uint8_t pad_;
    uint16_t damage;
    uint16_t hp_left;
    int16_t x, y;
} VxpeCombatEvent2D;

typedef struct VxpeCombatant2D {
    VxpeBody2D* body;             /* may be NULL for a static target */
    const VxpeAttack2D* atk;      /* current swing, NULL when idle */
    uint16_t hp, max_hp;
    uint16_t invuln_ms;           /* counts down; 0 means take damage normally */
    uint16_t stun_ms;             /* cannot start or continue an attack */
    uint16_t freeze_ms;           /* hit-stop: physics is skipped while nonzero */
    uint16_t atk_ms;              /* elapsed inside the current swing */
    uint16_t flash_ms;            /* renderer hint: draw the sprite white */
    uint32_t swing_mask;          /* victim slots already hit by this swing */
    int8_t team;                  /* attacks only register across teams */
    uint8_t slot;                 /* own bit in every swing mask, 0..31 */
    uint8_t alive;
    uint8_t pad_;
} VxpeCombatant2D;

/* `slot` picks the bit used for per-swing hit tracking, so it must be unique
 * within any group passed to vxpe_combat_resolve together. */
void vxpe_combat_init(VxpeCombatant2D* c, VxpeBody2D* body,
                      uint16_t max_hp, int team, int slot);

/* Start a swing. Refused while stunned, dead, already attacking or frozen, so
 * a game can call this on every button press without a state machine. Returns
 * 1 when the attack actually started. */
int vxpe_combat_attack(VxpeCombatant2D* c, const VxpeAttack2D* atk);

/* 1 while any part of a swing is still running. */
int vxpe_combat_attacking(const VxpeCombatant2D* c);

/* 1 while physics should be skipped. vxpe_combat_body_step already honours
 * this; read it to skip animation and input too. */
int vxpe_combat_frozen(const VxpeCombatant2D* c);

/* Advance swing, i-frame, stun, hit-stop and flash timers. Writes `events`
 * (may be NULL) when the swing starts or ends its active window, and returns
 * how many it wrote. A swing cancelled by damage is already gone by the time
 * this runs; a game that sets stun_ms or alive by hand gets the cancel here
 * instead. */
int vxpe_combat_update(VxpeCombatant2D* c, uint16_t dt_ms,
                       VxpeCombatEvent2D* events, int max_events);

/* Fills `out` with the live hitbox in world px. Returns 0 when the combatant
 * is idle, dead, or outside the active window, without touching `out`. */
int vxpe_combat_hitbox(const VxpeCombatant2D* c, VxpeRectI* out);

/* The combatant's own hurtbox: its collision box, or an empty rect when it has
 * no body. */
void vxpe_combat_hurtbox(const VxpeCombatant2D* c, VxpeRectI* out);

/* Body movement that respects hit-stop and death. Identical to the VxpeBody2D
 * entry points apart from the freeze check, so a game can swap them 1:1. */
void vxpe_combat_body_control(VxpeCombatant2D* c, const VxpeTilemap2D* map,
                              const VxpeBodyTuning2D* tuning,
                              const VxpeBodyIntent2D* intent, uint16_t dt_ms);
void vxpe_combat_body_step(VxpeCombatant2D* c, const VxpeTilemap2D* map,
                           const VxpeBodyTuning2D* tuning, uint16_t dt_ms);

/* Apply damage from anything that is not a swing: spikes, lava, a fall, the
 * world edge. `dir_x` is the sign the knockback flies in (-1, 0, +1). Returns
 * 1 when hit points were lost, 0 when i-frames absorbed it, and writes
 * `event` when given. */
int vxpe_combat_hurt(VxpeCombatant2D* c, uint16_t damage, int dir_x,
                     int32_t kb_x_q8, int32_t kb_y_q8, uint16_t invuln_ms,
                     uint16_t stun_ms, uint16_t hit_stop_ms,
                     int attacker_slot, VxpeCombatEvent2D* event);

/* Every attacker's live hitbox against every victim's hurtbox. Same-team pairs
 * and a combatant hitting itself are skipped. Appends events and returns how
 * many were written (capped at max_events). Only a connect that draws blood
 * spends that victim for the rest of the swing, so an immune ally cannot be
 * used as a shield; a non-piercing swing stops at the first body it bleeds. */
int vxpe_combat_resolve(VxpeCombatant2D* attackers, int attacker_count,
                        VxpeCombatant2D* victims, int victim_count,
                        VxpeCombatEvent2D* events, int max_events);

/* --- projectiles ----------------------------------------------------------
 * A fixed pool in caller-owned storage. Projectiles carry their own damage
 * descriptor so a fireball and an arrow are data, not code paths. */
#define VXPE_PROJ_POOL2D_MAX 24

typedef struct VxpeProjectile2D {
    int32_t x_q8, y_q8;    /* top-left of the hurtbox, world px */
    int32_t vx_q8, vy_q8;  /* Q8.8 px/s */
    int32_t gravity_q8;    /* Q8.8 px/s^2, 0 for a straight shot */
    uint16_t w, h;
    uint16_t damage;
    uint16_t life_ms;
    int32_t kb_x_q8, kb_y_q8;
    uint16_t invuln_ms, stun_ms, hit_stop_ms;
    int8_t team;
    uint8_t pierce;        /* 1 = keeps flying through bodies */
    uint8_t dies_on_tile;  /* 1 = destroyed by VXPE_TF_SOLID */
    uint8_t active;
    uint32_t hit_mask;     /* target slots already bled by this shot */
} VxpeProjectile2D;

typedef struct VxpeProjectilePool2D {
    VxpeProjectile2D items[VXPE_PROJ_POOL2D_MAX];
    uint8_t count;   /* highest slot ever used; keeps the loops short */
    uint8_t pad_;
} VxpeProjectilePool2D;

void vxpe_proj_pool_init(VxpeProjectilePool2D* pool);

/* Copies `init` into a free slot at world pixel (x,y) and clears its hit mask.
 * Returns NULL when the pool is full, which is the only failure mode - a game
 * that wants a guaranteed shot should reclaim one of its own first. */
VxpeProjectile2D* vxpe_proj_spawn(VxpeProjectilePool2D* pool,
                                  const VxpeProjectile2D* init, int x, int y);

/* Integrates motion, ages the shot and, when map is not NULL, stops a shot
 * flagged dies_on_tile on a solid tile. Returns how many are still alive. */
int vxpe_proj_update(VxpeProjectilePool2D* pool, const VxpeTilemap2D* map,
                     uint16_t dt_ms);

/* Live shots against combatants on the other team. Each connect spends the
 * shot unless it pierces, and a blocked connect spends it too: an arrow
 * stopped by a shield is still an arrow no longer in flight. Returns the number
 * of events written. */
int vxpe_proj_resolve(VxpeProjectilePool2D* pool, VxpeCombatant2D* targets,
                      int target_count, VxpeCombatEvent2D* events,
                      int max_events);

/* 1 when any live shot overlaps the rect. Used for a shielded door switch or
 * an "off-screen" test in a HUD. */
int vxpe_proj_overlaps(const VxpeProjectilePool2D* pool, int x, int y, int w, int h);

#ifdef __cplusplus
} /* extern "C" */
#endif
