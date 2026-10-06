/*
 * Copyright (c) 2026 PixelRoot32
 * Licensed under the MIT License
 *
 * Fixed-capacity, zero-heap particle pool for VXP/MRE.
 * C-compatible API for gameplay code generated from VXPEngine templates.
 */
#pragma once

#include <stdint.h>
#include "graphics/VxpRender2D.h"

#ifdef __cplusplus
extern "C" {
#endif

#ifndef VXPE_PARTICLE_POOL_MAX
#define VXPE_PARTICLE_POOL_MAX 64
#endif

typedef enum VxpeParticleCollisionResponse {
    VXPE_PARTICLE_COLLISION_NONE = 0,
    VXPE_PARTICLE_COLLISION_BOUNCE = 1,
    VXPE_PARTICLE_COLLISION_STOP = 2,
    VXPE_PARTICLE_COLLISION_KILL = 3
} VxpeParticleCollisionResponse;

typedef struct VxpeParticle {
    int32_t x_q8;
    int32_t y_q8;
    int32_t vx_q8;
    int32_t vy_q8;
    int32_t ax_q8;
    int32_t ay_q8;

    uint16_t age_ms;
    uint16_t lifetime_ms;

    uint16_t color565;
    uint16_t tint565;
    uint16_t draw_color565;

    uint32_t inv_lifetime_q24; /* cached 2^24 / lifetime_ms */

    uint8_t alpha_start;
    uint8_t alpha_end;
    uint8_t alpha;

    uint8_t size_start;
    uint8_t size_end;
    uint8_t size;

    uint8_t blend;
    uint8_t collide;
    uint8_t collision_count;
    uint8_t active;
} VxpeParticle;

typedef struct VxpeParticleSpawn {
    int16_t x;
    int16_t y;

    /* Velocity/acceleration are Q8.8 pixels per second. 256 = 1 px/s. */
    int32_t vx_q8;
    int32_t vy_q8;
    int32_t ax_q8;
    int32_t ay_q8;

    uint16_t lifetime_ms;
    uint16_t color565;
    uint16_t tint565;

    uint8_t alpha_start;
    uint8_t alpha_end;
    uint8_t size_start;
    uint8_t size_end;
    uint8_t blend;   /* VxpeBlendMode */
    uint8_t collide; /* 0 = visual only; non-zero = physics collision */
} VxpeParticleSpawn;

/* Static axis-aligned collider owned by the game. */
typedef struct VxpeParticleAabb {
    int16_t x;
    int16_t y;
    int16_t w;
    int16_t h;

    uint8_t response;        /* VxpeParticleCollisionResponse */
    uint8_t restitution_q8;  /* 0..255: retained normal velocity */
    uint8_t friction_q8;     /* 0..255: tangential velocity removed */
    uint8_t tag;             /* user-defined collider id */
} VxpeParticleAabb;

/*
 * Optional collision world. Bounds use [left,right) x [top,bottom).
 * colliders points to caller-owned storage; no allocation/copy is performed.
 */
typedef struct VxpeParticlePhysicsWorld {
    int16_t left;
    int16_t top;
    int16_t right;
    int16_t bottom;

    const VxpeParticleAabb* colliders;
    uint8_t collider_count;

    uint8_t bounds_enabled;
    uint8_t bounds_response;
    uint8_t bounds_restitution_q8;
    uint8_t bounds_friction_q8;
} VxpeParticlePhysicsWorld;

typedef struct VxpeParticleCollisionEvent {
    int16_t slot;
    int8_t normal_x;
    int8_t normal_y;
    uint8_t tag;       /* 0xFF = world bounds */
    uint8_t response;  /* VxpeParticleCollisionResponse */
} VxpeParticleCollisionEvent;

typedef struct VxpeParticlePool {
    VxpeParticle particles[VXPE_PARTICLE_POOL_MAX];

    /* Dense active list: update/draw cost scales with live particles. */
    uint8_t active_indices[VXPE_PARTICLE_POOL_MAX];
    uint8_t active_positions[VXPE_PARTICLE_POOL_MAX];

    uint16_t capacity;
    uint16_t active_count;
    uint16_t cursor;
} VxpeParticlePool;

/* Initialise/reset a pool. capacity=0 uses VXPE_PARTICLE_POOL_MAX. */
void vxpe_particles_init(VxpeParticlePool* pool, uint16_t capacity);

/* Remove every live particle without reallocating anything. */
void vxpe_particles_clear(VxpeParticlePool* pool);

/*
 * Spawn into the first available slot, searching from a rolling cursor.
 * Returns slot index >= 0 on success or -1 when the pool is full/invalid.
 */
int vxpe_particles_spawn(VxpeParticlePool* pool, const VxpeParticleSpawn* spawn);

/* Integrate position/velocity and age/lifetime using integer math. */
void vxpe_particles_update(VxpeParticlePool* pool, uint16_t delta_ms);

/*
 * Integrate + resolve world bounds/AABB collisions.
 * Returns the number of events written. events may be NULL/max_events=0.
 */
uint16_t vxpe_particles_update_physics(
    VxpeParticlePool* pool,
    uint16_t delta_ms,
    const VxpeParticlePhysicsWorld* world,
    VxpeParticleCollisionEvent* events,
    uint16_t max_events);

/* Draw all active particles to an RGB565 framebuffer. */
void vxpe_particles_draw(
    const VxpeParticlePool* pool,
    uint16_t* fb, int fb_w, int fb_h);

/* Pool/particle state helpers. */
uint16_t vxpe_particles_active_count(const VxpeParticlePool* pool);
uint16_t vxpe_particles_remaining_ms(const VxpeParticlePool* pool, int slot);
int vxpe_particles_is_alive(const VxpeParticlePool* pool, int slot);
void vxpe_particles_kill(VxpeParticlePool* pool, int slot);

/* Runtime controls for a live particle. */
void vxpe_particles_set_alpha(
    VxpeParticlePool* pool, int slot, uint8_t alpha_start, uint8_t alpha_end);
void vxpe_particles_set_tint(
    VxpeParticlePool* pool, int slot, uint16_t tint565);
void vxpe_particles_set_blend(
    VxpeParticlePool* pool, int slot, uint8_t blend_mode);
void vxpe_particles_set_lifetime(
    VxpeParticlePool* pool, int slot, uint16_t lifetime_ms);
void vxpe_particles_set_collision(
    VxpeParticlePool* pool, int slot, int enabled);

#ifdef __cplusplus
} /* extern "C" */
#endif
