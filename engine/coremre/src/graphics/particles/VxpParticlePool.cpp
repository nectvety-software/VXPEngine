#include "graphics/particles/VxpParticlePool.h"

#include <string.h>

namespace {

inline uint16_t clamp_capacity(uint16_t capacity) {
    if (capacity == 0 || capacity > VXPE_PARTICLE_POOL_MAX) {
        return VXPE_PARTICLE_POOL_MAX;
    }
    return capacity;
}

inline uint8_t interpolate_u8(uint8_t a, uint8_t b, uint16_t t256) {
    const int value = static_cast<int>(a) +
        ((static_cast<int>(b) - static_cast<int>(a)) * static_cast<int>(t256) >> 8);
    return static_cast<uint8_t>(value < 0 ? 0 : (value > 255 ? 255 : value));
}

inline VxpeParticle* get_slot(VxpeParticlePool* pool, int slot) {
    if (pool == nullptr || slot < 0 || slot >= pool->capacity) return nullptr;
    return &pool->particles[slot];
}

inline const VxpeParticle* get_slot_const(const VxpeParticlePool* pool, int slot) {
    if (pool == nullptr || slot < 0 || slot >= pool->capacity) return nullptr;
    return &pool->particles[slot];
}

inline void refresh_lifetime_cache(VxpeParticle& p) {
    p.inv_lifetime_q24 = p.lifetime_ms
        ? static_cast<uint32_t>((0x01000000u + p.lifetime_ms / 2u) / p.lifetime_ms)
        : 0u;
}

inline void update_visual_state(VxpeParticle& p) {
    if (p.lifetime_ms == 0 || p.inv_lifetime_q24 == 0) {
        p.alpha = p.alpha_end;
        p.size = p.size_end;
        return;
    }

    uint32_t t = static_cast<uint32_t>(
        (static_cast<uint64_t>(p.age_ms) * p.inv_lifetime_q24) >> 16);
    if (t > 256u) t = 256u;
    p.alpha = interpolate_u8(p.alpha_start, p.alpha_end, static_cast<uint16_t>(t));
    p.size = interpolate_u8(p.size_start, p.size_end, static_cast<uint16_t>(t));
}

inline void add_active(VxpeParticlePool* pool, uint16_t slot) {
    const uint16_t pos = pool->active_count;
    pool->active_indices[pos] = static_cast<uint8_t>(slot);
    pool->active_positions[slot] = static_cast<uint8_t>(pos);
    pool->active_count = static_cast<uint16_t>(pos + 1u);
}

inline void remove_active(VxpeParticlePool* pool, uint16_t slot) {
    if (pool == nullptr || slot >= pool->capacity || !pool->particles[slot].active) return;

    const uint16_t pos = pool->active_positions[slot];
    const uint16_t last_pos = static_cast<uint16_t>(pool->active_count - 1u);
    const uint16_t moved_slot = pool->active_indices[last_pos];

    if (pos != last_pos) {
        pool->active_indices[pos] = static_cast<uint8_t>(moved_slot);
        pool->active_positions[moved_slot] = static_cast<uint8_t>(pos);
    }

    pool->active_positions[slot] = 0xFFu;
    pool->particles[slot].active = 0;
    pool->active_count = last_pos;
}

inline int32_t integrate_q8(int32_t value_q8, uint32_t dt_q16) {
    return static_cast<int32_t>(
        (static_cast<int64_t>(value_q8) * static_cast<int64_t>(dt_q16)) >> 16);
}

inline void integrate_particle(VxpeParticle& p, uint16_t step_ms, uint32_t dt_q16) {
    p.vx_q8 += integrate_q8(p.ax_q8, dt_q16);
    p.vy_q8 += integrate_q8(p.ay_q8, dt_q16);
    p.x_q8 += integrate_q8(p.vx_q8, dt_q16);
    p.y_q8 += integrate_q8(p.vy_q8, dt_q16);
    p.age_ms = static_cast<uint16_t>(p.age_ms + step_ms);
    update_visual_state(p);
}

inline uint8_t retained_tangent(uint8_t friction_q8) {
    return static_cast<uint8_t>(255u - friction_q8);
}

inline void resolve_velocity(VxpeParticle& p, int nx, int ny,
                             uint8_t response, uint8_t restitution_q8,
                             uint8_t friction_q8) {
    if (response == VXPE_PARTICLE_COLLISION_STOP) {
        p.vx_q8 = 0;
        p.vy_q8 = 0;
        p.ax_q8 = 0;
        p.ay_q8 = 0;
        return;
    }
    if (response != VXPE_PARTICLE_COLLISION_BOUNCE) return;

    const uint8_t tangent = retained_tangent(friction_q8);
    if (nx != 0) {
        if ((nx > 0 && p.vx_q8 < 0) || (nx < 0 && p.vx_q8 > 0)) {
            p.vx_q8 = static_cast<int32_t>(
                -(static_cast<int64_t>(p.vx_q8) * restitution_q8) / 255);
        }
        p.vy_q8 = static_cast<int32_t>(
            (static_cast<int64_t>(p.vy_q8) * tangent) / 255);
    } else if (ny != 0) {
        if ((ny > 0 && p.vy_q8 < 0) || (ny < 0 && p.vy_q8 > 0)) {
            p.vy_q8 = static_cast<int32_t>(
                -(static_cast<int64_t>(p.vy_q8) * restitution_q8) / 255);
        }
        p.vx_q8 = static_cast<int32_t>(
            (static_cast<int64_t>(p.vx_q8) * tangent) / 255);
    }
}

inline void write_event(VxpeParticleCollisionEvent* events, uint16_t max_events,
                        uint16_t& event_count, int slot, int nx, int ny,
                        uint8_t tag, uint8_t response) {
    if (events != nullptr && event_count < max_events) {
        VxpeParticleCollisionEvent& e = events[event_count++];
        e.slot = static_cast<int16_t>(slot);
        e.normal_x = static_cast<int8_t>(nx);
        e.normal_y = static_cast<int8_t>(ny);
        e.tag = tag;
        e.response = response;
    }
}

inline int half_extent(const VxpeParticle& p) {
    return p.size > 1 ? (static_cast<int>(p.size) + 1) / 2 : 1;
}
inline int collide_bounds(VxpeParticlePool* pool, uint16_t slot,
                          const VxpeParticlePhysicsWorld* world,
                          VxpeParticleCollisionEvent* events,
                          uint16_t max_events, uint16_t& event_count) {
    if (world == nullptr || !world->bounds_enabled ||
        world->bounds_response == VXPE_PARTICLE_COLLISION_NONE ||
        world->right <= world->left || world->bottom <= world->top) {
        return 0;
    }

    VxpeParticle& p = pool->particles[slot];
    const int half = half_extent(p);
    int x = static_cast<int>(p.x_q8 >> 8);
    int y = static_cast<int>(p.y_q8 >> 8);
    int nx = 0;
    int ny = 0;

    if (x - half < world->left) {
        x = world->left + half;
        nx = 1;
    } else if (x + half >= world->right) {
        x = world->right - half - 1;
        nx = -1;
    }

    if (y - half < world->top) {
        y = world->top + half;
        ny = 1;
    } else if (y + half >= world->bottom) {
        y = world->bottom - half - 1;
        ny = -1;
    }

    if (nx == 0 && ny == 0) return 0;

    p.x_q8 = static_cast<int32_t>(x) << 8;
    p.y_q8 = static_cast<int32_t>(y) << 8;
    if (p.collision_count < 255u) p.collision_count++;

    write_event(events, max_events, event_count, slot, nx, ny, 0xFFu,
                world->bounds_response);

    if (world->bounds_response == VXPE_PARTICLE_COLLISION_KILL) {
        remove_active(pool, slot);
        return 1;
    }

    if (nx != 0) {
        resolve_velocity(p, nx, 0, world->bounds_response,
                         world->bounds_restitution_q8, world->bounds_friction_q8);
    }
    if (ny != 0) {
        resolve_velocity(p, 0, ny, world->bounds_response,
                         world->bounds_restitution_q8, world->bounds_friction_q8);
    }
    return 0;
}

inline int collide_aabb(VxpeParticlePool* pool, uint16_t slot,
                        const VxpeParticleAabb& c,
                        VxpeParticleCollisionEvent* events,
                        uint16_t max_events, uint16_t& event_count) {
    if (c.w <= 0 || c.h <= 0 || c.response == VXPE_PARTICLE_COLLISION_NONE) return 0;

    VxpeParticle& p = pool->particles[slot];
    const int half = half_extent(p);
    int x = static_cast<int>(p.x_q8 >> 8);
    int y = static_cast<int>(p.y_q8 >> 8);

    const int left = x - half;
    const int right = x + half;
    const int top = y - half;
    const int bottom = y + half;
    const int cx0 = c.x;
    const int cy0 = c.y;
    const int cx1 = c.x + c.w;
    const int cy1 = c.y + c.h;

    if (right <= cx0 || left >= cx1 || bottom <= cy0 || top >= cy1) return 0;

    const int pen_left = right - cx0;
    const int pen_right = cx1 - left;
    const int pen_top = bottom - cy0;
    const int pen_bottom = cy1 - top;

    int penetration = pen_left;
    int nx = -1;
    int ny = 0;

    if (pen_right < penetration) {
        penetration = pen_right;
        nx = 1; ny = 0;
    }
    if (pen_top < penetration) {
        penetration = pen_top;
        nx = 0; ny = -1;
    }
    if (pen_bottom < penetration) {
        nx = 0; ny = 1;
    }

    if (nx < 0) x = cx0 - half - 1;
    else if (nx > 0) x = cx1 + half;
    else if (ny < 0) y = cy0 - half - 1;
    else y = cy1 + half;

    p.x_q8 = static_cast<int32_t>(x) << 8;
    p.y_q8 = static_cast<int32_t>(y) << 8;
    if (p.collision_count < 255u) p.collision_count++;

    write_event(events, max_events, event_count, slot, nx, ny, c.tag, c.response);

    if (c.response == VXPE_PARTICLE_COLLISION_KILL) {
        remove_active(pool, slot);
        return 1;
    }

    resolve_velocity(p, nx, ny, c.response, c.restitution_q8, c.friction_q8);
    return 0;
}

uint16_t update_impl(VxpeParticlePool* pool, uint16_t delta_ms,
                     const VxpeParticlePhysicsWorld* world,
                     VxpeParticleCollisionEvent* events, uint16_t max_events) {
    if (pool == nullptr || delta_ms == 0 || pool->active_count == 0) return 0;

    uint16_t event_count = 0;
    const uint32_t dt_q16 = (static_cast<uint32_t>(delta_ms) << 16) / 1000u;

    uint16_t pos = 0;
    while (pos < pool->active_count) {
        const uint16_t slot = pool->active_indices[pos];
        VxpeParticle& p = pool->particles[slot];

        const uint16_t remaining =
            p.age_ms < p.lifetime_ms ? static_cast<uint16_t>(p.lifetime_ms - p.age_ms) : 0;
        const uint16_t step_ms = delta_ms < remaining ? delta_ms : remaining;

        if (step_ms > 0) {
            const uint32_t step_q16 = step_ms == delta_ms
                ? dt_q16
                : (static_cast<uint32_t>(step_ms) << 16) / 1000u;
            integrate_particle(p, step_ms, step_q16);
        }

        if (p.age_ms >= p.lifetime_ms) {
            remove_active(pool, slot);
            continue;
        }

        if (world != nullptr && p.collide) {
            if (collide_bounds(pool, slot, world, events, max_events, event_count)) {
                continue;
            }

            if (world->colliders != nullptr) {
                for (uint16_t c = 0; c < world->collider_count; ++c) {
                    if (collide_aabb(pool, slot, world->colliders[c],
                                     events, max_events, event_count)) {
                        break;
                    }
                }
                if (!pool->particles[slot].active) continue;
            }
        }

        ++pos;
    }

    return event_count;
}

} // namespace

extern "C" {
void vxpe_particles_init(VxpeParticlePool* pool, uint16_t capacity) {
    if (pool == nullptr) return;
    memset(pool, 0, sizeof(*pool));
    memset(pool->active_positions, 0xFF, sizeof(pool->active_positions));
    pool->capacity = clamp_capacity(capacity);
}

void vxpe_particles_clear(VxpeParticlePool* pool) {
    if (pool == nullptr) return;
    const uint16_t capacity = clamp_capacity(pool->capacity);
    memset(pool->particles, 0, sizeof(pool->particles));
    memset(pool->active_indices, 0, sizeof(pool->active_indices));
    memset(pool->active_positions, 0xFF, sizeof(pool->active_positions));
    pool->capacity = capacity;
    pool->active_count = 0;
    pool->cursor = 0;
}

int vxpe_particles_spawn(VxpeParticlePool* pool, const VxpeParticleSpawn* spawn) {
    if (pool == nullptr || spawn == nullptr) return -1;
    if (pool->capacity == 0 || pool->capacity > VXPE_PARTICLE_POOL_MAX) {
        pool->capacity = clamp_capacity(pool->capacity);
    }
    if (pool->active_count >= pool->capacity || spawn->lifetime_ms == 0) return -1;

    const uint16_t capacity = pool->capacity;
    const uint16_t start = pool->cursor < capacity ? pool->cursor : 0;

    for (uint16_t n = 0; n < capacity; ++n) {
        const uint16_t slot = static_cast<uint16_t>((start + n) % capacity);
        VxpeParticle& p = pool->particles[slot];
        if (p.active) continue;

        memset(&p, 0, sizeof(p));
        p.x_q8 = static_cast<int32_t>(spawn->x) << 8;
        p.y_q8 = static_cast<int32_t>(spawn->y) << 8;
        p.vx_q8 = spawn->vx_q8;
        p.vy_q8 = spawn->vy_q8;
        p.ax_q8 = spawn->ax_q8;
        p.ay_q8 = spawn->ay_q8;
        p.lifetime_ms = spawn->lifetime_ms;
        p.color565 = spawn->color565;
        p.tint565 = spawn->tint565;
        p.draw_color565 = vxpe2d_tint565(spawn->color565, spawn->tint565);
        refresh_lifetime_cache(p);
        p.alpha_start = spawn->alpha_start;
        p.alpha_end = spawn->alpha_end;
        p.alpha = spawn->alpha_start;
        p.size_start = spawn->size_start;
        p.size_end = spawn->size_end;
        p.size = spawn->size_start;
        p.blend = spawn->blend <= VXPE_BLEND_MULTIPLY ? spawn->blend : VXPE_BLEND_ALPHA;
        p.collide = spawn->collide ? 1u : 0u;
        p.active = 1;

        add_active(pool, slot);
        pool->cursor = static_cast<uint16_t>((slot + 1u) % capacity);
        return static_cast<int>(slot);
    }

    return -1;
}

void vxpe_particles_update(VxpeParticlePool* pool, uint16_t delta_ms) {
    (void)update_impl(pool, delta_ms, nullptr, nullptr, 0);
}

uint16_t vxpe_particles_update_physics(
    VxpeParticlePool* pool,
    uint16_t delta_ms,
    const VxpeParticlePhysicsWorld* world,
    VxpeParticleCollisionEvent* events,
    uint16_t max_events) {
    return update_impl(pool, delta_ms, world, events, max_events);
}

void vxpe_particles_draw(const VxpeParticlePool* pool,
                         uint16_t* fb, int fb_w, int fb_h) {
    if (pool == nullptr || fb == nullptr || fb_w <= 0 || fb_h <= 0 ||
        pool->active_count == 0) {
        return;
    }

    for (uint16_t pos = 0; pos < pool->active_count; ++pos) {
        const uint16_t slot = pool->active_indices[pos];
        const VxpeParticle& p = pool->particles[slot];
        if (!p.active || p.alpha == 0 || p.size == 0) continue;

        const int x = static_cast<int>(p.x_q8 >> 8);
        const int y = static_cast<int>(p.y_q8 >> 8);
        const int size = p.size;
        const int x0 = x - size / 2;
        const int y0 = y - size / 2;

        if (x0 >= fb_w || y0 >= fb_h || x0 + size <= 0 || y0 + size <= 0) continue;

        if (p.blend == VXPE_BLEND_COPY && p.alpha == 255u) {
            vxpe2d_fill_rect(fb, fb_w, fb_h, x0, y0, size, size, p.draw_color565);
        } else {
            vxpe2d_overlay_rect(
                fb, fb_w, fb_h,
                x0, y0, size, size,
                p.draw_color565, p.alpha, p.blend);
        }
    }
}

uint16_t vxpe_particles_active_count(const VxpeParticlePool* pool) {
    return pool ? pool->active_count : 0;
}

uint16_t vxpe_particles_remaining_ms(const VxpeParticlePool* pool, int slot) {
    const VxpeParticle* p = get_slot_const(pool, slot);
    if (p == nullptr || !p->active || p->age_ms >= p->lifetime_ms) return 0;
    return static_cast<uint16_t>(p->lifetime_ms - p->age_ms);
}

int vxpe_particles_is_alive(const VxpeParticlePool* pool, int slot) {
    const VxpeParticle* p = get_slot_const(pool, slot);
    return p != nullptr && p->active ? 1 : 0;
}

void vxpe_particles_kill(VxpeParticlePool* pool, int slot) {
    if (pool == nullptr || slot < 0 || slot >= pool->capacity) return;
    remove_active(pool, static_cast<uint16_t>(slot));
}
void vxpe_particles_set_alpha(VxpeParticlePool* pool, int slot,
                              uint8_t alpha_start, uint8_t alpha_end) {
    VxpeParticle* p = get_slot(pool, slot);
    if (p == nullptr || !p->active) return;
    p->alpha_start = alpha_start;
    p->alpha_end = alpha_end;
    update_visual_state(*p);
}

void vxpe_particles_set_tint(VxpeParticlePool* pool, int slot, uint16_t tint565) {
    VxpeParticle* p = get_slot(pool, slot);
    if (p == nullptr || !p->active) return;
    p->tint565 = tint565;
    p->draw_color565 = vxpe2d_tint565(p->color565, tint565);
}

void vxpe_particles_set_blend(VxpeParticlePool* pool, int slot, uint8_t blend_mode) {
    VxpeParticle* p = get_slot(pool, slot);
    if (p == nullptr || !p->active) return;
    p->blend = blend_mode <= VXPE_BLEND_MULTIPLY ? blend_mode : VXPE_BLEND_ALPHA;
}

void vxpe_particles_set_lifetime(VxpeParticlePool* pool, int slot, uint16_t lifetime_ms) {
    VxpeParticle* p = get_slot(pool, slot);
    if (p == nullptr || !p->active) return;

    if (lifetime_ms == 0 || p->age_ms >= lifetime_ms) {
        vxpe_particles_kill(pool, slot);
        return;
    }

    p->lifetime_ms = lifetime_ms;
    refresh_lifetime_cache(*p);
    update_visual_state(*p);
}

void vxpe_particles_set_collision(VxpeParticlePool* pool, int slot, int enabled) {
    VxpeParticle* p = get_slot(pool, slot);
    if (p == nullptr || !p->active) return;
    p->collide = enabled ? 1u : 0u;
}

} // extern "C"
