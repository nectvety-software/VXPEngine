/* ParticleFireDemo - fixed pool + physics collision demo for VXPEngine/MRE. */
#include "vmsys.h"
#include "vmio.h"
#include "vmgraph.h"
#include "vmtimer.h"
#include "graphics/VxpRender2D.h"
#include "graphics/particles/VxpParticlePool.h"
#include <string.h>

static VMINT g_layer = -1;
static VMINT g_timer = -1;
static VMINT g_tick = 0;
static VMINT g_started = 0;
static VMINT g_emit = 1;
static int g_emitter_x = 120;
static uint32_t g_rng = 0x51F15EEDu;
static uint32_t g_collision_total = 0;
static uint8_t g_hit_mask = 0;
static uint8_t g_hit_flash = 0;

static VxpeParticlePool g_particles;
static VxpeParticleAabb g_colliders[2];
static VxpeParticlePhysicsWorld g_world;
static VxpeParticleCollisionEvent g_events[8];

static uint32_t rnd32(void) {
    g_rng = g_rng * 1664525u + 1013904223u;
    return g_rng;
}

static int rnd_range(int lo, int hi) {
    if (hi <= lo) return lo;
    return lo + (int)(rnd32() % (uint32_t)(hi - lo + 1));
}

static int clampi(int v, int lo, int hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

static VMUINT16* framebuffer(void) {
    return (VMUINT16*)vm_graphic_get_layer_buffer(g_layer);
}

static void setup_world(int sw, int sh) {
    memset(&g_world, 0, sizeof(g_world));
    memset(g_colliders, 0, sizeof(g_colliders));

    g_world.left = 4;
    g_world.top = 18;
    g_world.right = (int16_t)(sw - 4);
    g_world.bottom = (int16_t)(sh - 36);
    g_world.colliders = g_colliders;
    g_world.collider_count = 2;
    g_world.bounds_enabled = 1;
    g_world.bounds_response = VXPE_PARTICLE_COLLISION_BOUNCE;
    g_world.bounds_restitution_q8 = 158;
    g_world.bounds_friction_q8 = 54;

    g_colliders[0].x = 22;
    g_colliders[0].y = (int16_t)(sh - 95);
    g_colliders[0].w = 54;
    g_colliders[0].h = 9;
    g_colliders[0].response = VXPE_PARTICLE_COLLISION_BOUNCE;
    g_colliders[0].restitution_q8 = 172;
    g_colliders[0].friction_q8 = 76;
    g_colliders[0].tag = 1;

    g_colliders[1].x = (int16_t)(sw - 76);
    g_colliders[1].y = (int16_t)(sh - 124);
    g_colliders[1].w = 54;
    g_colliders[1].h = 9;
    g_colliders[1].response = VXPE_PARTICLE_COLLISION_BOUNCE;
    g_colliders[1].restitution_q8 = 184;
    g_colliders[1].friction_q8 = 62;
    g_colliders[1].tag = 2;
}

static void spawn_flame(int sh) {
    VxpeParticleSpawn p;
    memset(&p, 0, sizeof(p));

    p.x = (int16_t)(g_emitter_x + rnd_range(-12, 12));
    p.y = (int16_t)(sh - 52 + rnd_range(-2, 5));
    p.vx_q8 = rnd_range(-14, 14) * 256;
    p.vy_q8 = -rnd_range(38, 72) * 256;
    p.ax_q8 = rnd_range(-2, 2) * 256;
    p.ay_q8 = -rnd_range(3, 10) * 256;
    p.lifetime_ms = (uint16_t)rnd_range(430, 820);
    p.color565 = 0xFFFF;

    if ((rnd32() & 3u) == 0u)
        p.tint565 = vxpe2d_rgb565(255, 90, 24);
    else if ((rnd32() & 1u) == 0u)
        p.tint565 = vxpe2d_rgb565(255, 170, 35);
    else
        p.tint565 = vxpe2d_rgb565(255, 225, 92);

    p.alpha_start = (uint8_t)rnd_range(190, 245);
    p.alpha_end = 0;
    p.size_start = (uint8_t)rnd_range(3, 6);
    p.size_end = 1;
    p.blend = VXPE_BLEND_ADD;
    p.collide = 0;
    vxpe_particles_spawn(&g_particles, &p);
}

static void spawn_smoke(int sh) {
    VxpeParticleSpawn p;
    memset(&p, 0, sizeof(p));

    p.x = (int16_t)(g_emitter_x + rnd_range(-9, 9));
    p.y = (int16_t)(sh - 60 - rnd_range(0, 10));
    p.vx_q8 = rnd_range(-8, 8) * 256;
    p.vy_q8 = -rnd_range(16, 29) * 256;
    p.ay_q8 = -2 * 256;
    p.lifetime_ms = (uint16_t)rnd_range(1100, 1700);
    p.color565 = 0xFFFF;
    p.tint565 = vxpe2d_rgb565(95, 88, 92);
    p.alpha_start = (uint8_t)rnd_range(48, 86);
    p.alpha_end = 0;
    p.size_start = 3;
    p.size_end = (uint8_t)rnd_range(7, 10);
    p.blend = VXPE_BLEND_ALPHA;
    p.collide = 0;
    vxpe_particles_spawn(&g_particles, &p);
}

static void spawn_spark(int sh, int burst) {
    VxpeParticleSpawn p;
    memset(&p, 0, sizeof(p));

    p.x = (int16_t)(g_emitter_x + rnd_range(-8, 8));
    p.y = (int16_t)(sh - 58 + rnd_range(-2, 2));
    p.vx_q8 = rnd_range(burst ? -105 : -68, burst ? 105 : 68) * 256;
    p.vy_q8 = -rnd_range(burst ? 70 : 48, burst ? 145 : 105) * 256;
    p.ay_q8 = rnd_range(155, 205) * 256;
    p.lifetime_ms = (uint16_t)rnd_range(1050, 1750);
    p.color565 = 0xFFFF;
    p.tint565 = (rnd32() & 1u)
        ? vxpe2d_rgb565(255, 206, 70)
        : vxpe2d_rgb565(255, 112, 24);
    p.alpha_start = 255;
    p.alpha_end = 24;
    p.size_start = (uint8_t)(burst ? 3 : 2);
    p.size_end = 1;
    p.blend = VXPE_BLEND_ADD;
    p.collide = 1;
    vxpe_particles_spawn(&g_particles, &p);
}

static void spawn_burst(int sh) {
    int i;
    for (i = 0; i < 12; ++i) spawn_spark(sh, 1);
}

static void update(void) {
    int sw = vm_graphic_get_screen_width();
    int sh = vm_graphic_get_screen_height();
    uint16_t event_count;
    uint16_t i;

    g_tick++;

    if (g_emit) {
        spawn_flame(sh);
        spawn_flame(sh);
        if ((g_tick & 3) == 0) spawn_smoke(sh);
        if ((g_tick & 1) == 0) spawn_spark(sh, 0);
    }

    event_count = vxpe_particles_update_physics(
        &g_particles, 33, &g_world, g_events,
        (uint16_t)(sizeof(g_events) / sizeof(g_events[0])));

    if (event_count > 0) {
        g_hit_flash = 4;
        g_collision_total += event_count;
        for (i = 0; i < event_count; ++i) {
            if (g_events[i].tag == 1) g_hit_mask |= 1u;
            else if (g_events[i].tag == 2) g_hit_mask |= 2u;
        }
    } else if (g_hit_flash > 0) {
        g_hit_flash--;
        if (g_hit_flash == 0) g_hit_mask = 0;
    }

    (void)sw;
}

static void draw_logs(VMUINT16* fb, int sw, int sh) {
    int y = sh - 42;
    vxpe2d_fill_rect((uint16_t*)fb, sw, sh, g_emitter_x - 24, y, 48, 7,
                     vxpe2d_rgb565(62, 31, 19));
    vxpe2d_fill_rect((uint16_t*)fb, sw, sh, g_emitter_x - 18, y - 4, 36, 5,
                     vxpe2d_rgb565(104, 51, 24));
    vxpe2d_fill_rect((uint16_t*)fb, sw, sh, g_emitter_x - 3, y - 1, 6, 6,
                     vxpe2d_rgb565(238, 124, 30));
}

static void draw_platforms(VMUINT16* fb, int sw, int sh) {
    int i;
    for (i = 0; i < 2; ++i) {
        VxpeParticleAabb* c = &g_colliders[i];
        int hot = g_hit_flash && ((i == 0 && (g_hit_mask & 1u)) ||
                                 (i == 1 && (g_hit_mask & 2u)));
        uint16_t body = hot
            ? vxpe2d_rgb565(255, 177, 60)
            : vxpe2d_rgb565(68, 74, 90);
        uint16_t top = hot
            ? vxpe2d_rgb565(255, 232, 146)
            : vxpe2d_rgb565(118, 126, 148);
        vxpe2d_fill_rect((uint16_t*)fb, sw, sh,
                         c->x, c->y, c->w, c->h, body);
        vxpe2d_fill_rect((uint16_t*)fb, sw, sh,
                         c->x, c->y, c->w, 2, top);
    }
}

static void draw(void) {
    VMUINT16* fb = framebuffer();
    int sw, sh, active, bar_w, hit_w;
    if (!fb || g_layer < 0) return;

    sw = vm_graphic_get_screen_width();
    sh = vm_graphic_get_screen_height();

    vxpe2d_gradient_vertical((uint16_t*)fb, sw, sh, 0, 0, sw, sh,
                             vxpe2d_rgb565(4, 8, 20),
                             vxpe2d_rgb565(28, 18, 20));

    vxpe2d_fill_rect((uint16_t*)fb, sw, sh, 0, sh - 36, sw, 36,
                     vxpe2d_rgb565(15, 13, 18));

    vxpe2d_radial_light_fast((uint16_t*)fb, sw, sh,
                             g_emitter_x, sh - 61, 48,
                             vxpe2d_rgb565(255, 92, 20), 82);

    draw_platforms(fb, sw, sh);
    draw_logs(fb, sw, sh);
    vxpe_particles_draw(&g_particles, (uint16_t*)fb, sw, sh);

    active = (int)vxpe_particles_active_count(&g_particles);
    vxpe2d_fill_rect((uint16_t*)fb, sw, sh, 8, 7, sw - 16, 5,
                     vxpe2d_rgb565(27, 31, 44));
    bar_w = (sw - 16) * active / VXPE_PARTICLE_POOL_MAX;
    vxpe2d_fill_rect((uint16_t*)fb, sw, sh, 8, 7, bar_w, 5,
                     g_emit ? vxpe2d_rgb565(255, 145, 35)
                            : vxpe2d_rgb565(92, 98, 110));

    hit_w = (int)(g_collision_total % (uint32_t)(sw - 16));
    vxpe2d_fill_rect((uint16_t*)fb, sw, sh, 8, 14, hit_w, 2,
                     vxpe2d_rgb565(110, 208, 255));

    vm_graphic_flush_layer(&g_layer, 1);
}

static void tick(VMINT tid) {
    (void)tid;
    update();
    draw();
}

void handle_keyevt(VMINT event, VMINT keycode) {
    int sh;
    if (event != VM_KEY_EVENT_DOWN && event != VM_KEY_EVENT_REPEAT) return;

    sh = vm_graphic_get_screen_height();

    if (keycode == VM_KEY_LEFT) {
        g_emitter_x = clampi(g_emitter_x - 8, 28, vm_graphic_get_screen_width() - 28);
    } else if (keycode == VM_KEY_RIGHT) {
        g_emitter_x = clampi(g_emitter_x + 8, 28, vm_graphic_get_screen_width() - 28);
    } else if (keycode == VM_KEY_UP) {
        spawn_burst(sh);
    } else if (keycode == VM_KEY_OK || keycode == VM_KEY_NUM5) {
        g_emit = !g_emit;
        if (!g_emit) vxpe_particles_clear(&g_particles);
    } else if (keycode == VM_KEY_RIGHT_SOFTKEY ||
               keycode == VM_KEY_CLEAR || keycode == VM_KEY_BACK) {
        vm_exit_app();
        return;
    }
    draw();
}

void handle_penevt(VMINT event, VMINT x, VMINT y) {
    if (event == VM_PEN_EVENT_TAP || event == VM_PEN_EVENT_MOVE) {
        g_emitter_x = clampi(x, 28, vm_graphic_get_screen_width() - 28);
    }
    if (event == VM_PEN_EVENT_TAP && y < vm_graphic_get_screen_height() / 2) {
        spawn_burst(vm_graphic_get_screen_height());
    }
}

static void start(void) {
    int sw = vm_graphic_get_screen_width();
    int sh = vm_graphic_get_screen_height();

    if (g_layer < 0) {
        g_layer = vm_graphic_create_layer(0, 0, sw, sh, -1);
    }

    if (!g_started) {
        vxpe_particles_init(&g_particles, VXPE_PARTICLE_POOL_MAX);
        g_emitter_x = sw / 2;
        setup_world(sw, sh);
        g_started = 1;
    }

    if (g_timer < 0) g_timer = vm_create_timer(33, tick);
    draw();
}

static void stop(void) {
    if (g_timer >= 0) {
        vm_delete_timer(g_timer);
        g_timer = -1;
    }
    if (g_layer >= 0) {
        vm_graphic_delete_layer(g_layer);
        g_layer = -1;
    }
}

void handle_sysevt(VMINT message, VMINT param) {
    (void)param;
    if (message == VM_MSG_CREATE || message == VM_MSG_ACTIVE) {
        start();
    } else if (message == VM_MSG_PAINT) {
        draw();
    } else if (message == VM_MSG_INACTIVE || message == VM_MSG_QUIT) {
        stop();
        if (message == VM_MSG_QUIT) vm_exit_app();
    }
}

void vm_main(void) {
    vm_reg_sysevt_callback(handle_sysevt);
    vm_reg_keyboard_callback(handle_keyevt);
    vm_reg_pen_callback(handle_penevt);
}
