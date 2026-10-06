/* WaterMuseum25DDemo - 240x320 VxpScene25D integration sample. */
#include "vmsys.h"
#include "vmio.h"
#include "vmgraph.h"
#include "vmtimer.h"
#include "graphics/VxpRender2D.h"
#include "graphics/VxpSpriteFx.h"
#include "graphics/VxpScene25D.h"
#include "graphics/VxpLight2D.h"
#include "graphics/VxpVfx2D.h"
#include "graphics/particles/VxpParticlePool.h"
#include <stdint.h>
#include <string.h>

#define SW 240
#define SH 320

static VMINT g_layer = -1;
static VMINT g_timer = -1;
static uint32_t g_tick = 0;
static uint32_t g_rng = 0x25D0BEEFu;
static int32_t g_hook_x = 0;
static int32_t g_hook_z = 245;
static uint8_t g_started = 0;

static uint16_t g_water_px[16 * 16];
static uint16_t g_ball_px[16 * 16];
static uint8_t  g_ball_a[16 * 16];
static uint16_t g_fish_px[24 * 12];
static uint8_t  g_fish_a[24 * 12];

static VxpeSpriteA8 g_water;
static VxpeSpriteA8 g_ball;
static VxpeSpriteA8 g_fish;
static VxpeCamera25D g_camera;
static VxpeLightmap2D g_lightmap;
static VxpeParticlePool g_particles;

typedef struct DemoBall {
    int16_t x;
    int16_t z;
    uint16_t tint;
    uint8_t size;
} DemoBall;

static const DemoBall g_balls[] = {
    {-74, 180, 0xFFFF, 20},
    {-40, 215, 0xFBE0, 18},
    { 24, 194, 0xF81F, 19},
    { 70, 230, 0x07FF, 17},
    {-56, 275, 0xFFE0, 16},
    { 12, 290, 0xF800, 16},
    { 62, 318, 0x07E0, 15},
    {-18, 350, 0x001F, 14},
    { 42, 380, 0xFD20, 14}
};

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

static void build_procedural_assets(void) {
    int x, y;
    memset(&g_water, 0, sizeof(g_water));
    memset(&g_ball, 0, sizeof(g_ball));
    memset(&g_fish, 0, sizeof(g_fish));

    for (y = 0; y < 16; ++y) {
        for (x = 0; x < 16; ++x) {
            int wave = ((x + (y >> 1)) & 3);
            int glint = ((x * 3 + y * 5) & 15) == 0;
            int r = 36 + wave * 4 + (glint ? 24 : 0);
            int g = 82 + wave * 7 + (glint ? 28 : 0);
            int b = 72 + wave * 5 + (glint ? 18 : 0);
            g_water_px[y * 16 + x] = vxpe2d_rgb565((uint8_t)r, (uint8_t)g, (uint8_t)b);
        }
    }
    g_water.pixels = g_water_px;
    g_water.alpha = 0;
    g_water.width = 16;
    g_water.height = 16;
    g_water.stride = 16;
    g_water.alpha_stride = 0;
    g_water.opaque = 1;

    for (y = 0; y < 16; ++y) {
        for (x = 0; x < 16; ++x) {
            int dx = x - 7;
            int dy = y - 8;
            int d2 = dx * dx + dy * dy;
            int idx = y * 16 + x;
            if (d2 <= 43) {
                int highlight = (x <= 6 && y <= 6) ? 255 : (220 - d2 * 2);
                if (highlight < 96) highlight = 96;
                g_ball_px[idx] = vxpe2d_rgb565((uint8_t)highlight, (uint8_t)highlight, (uint8_t)highlight);
                g_ball_a[idx] = (d2 > 37) ? 180 : 255;
            } else {
                g_ball_px[idx] = 0;
                g_ball_a[idx] = 0;
            }
        }
    }
    g_ball.pixels = g_ball_px;
    g_ball.alpha = g_ball_a;
    g_ball.width = 16;
    g_ball.height = 16;
    g_ball.stride = 16;
    g_ball.alpha_stride = 16;
    g_ball.opaque = 0;

    for (y = 0; y < 12; ++y) {
        for (x = 0; x < 24; ++x) {
            int idx = y * 24 + x;
            int body = ((x - 11) * (x - 11) * 2 + (y - 6) * (y - 6) * 7) < 130;
            int tail = (x < 6 && (y >= x || y >= 11 - x));
            if (body || tail) {
                int shade = 160 + ((x + y) & 3) * 20;
                if (shade > 235) shade = 235;
                g_fish_px[idx] = vxpe2d_rgb565((uint8_t)(shade * 3 / 5), (uint8_t)shade, (uint8_t)(shade * 4 / 5));
                g_fish_a[idx] = (uint8_t)((y == 0 || y == 11) ? 150 : 210);
            }
        }
    }
    g_fish.pixels = g_fish_px;
    g_fish.alpha = g_fish_a;
    g_fish.width = 24;
    g_fish.height = 12;
    g_fish.stride = 24;
    g_fish.alpha_stride = 24;
    g_fish.opaque = 0;
}

static void setup_scene(void) {
    vxpe25d_camera_init(&g_camera, SW, SH, 72, 150);
    g_camera.world_y = 60;
    g_camera.near_z = 80;
    g_camera.far_z = 720;
    g_camera.min_scale_q8 = 48;
    g_camera.max_scale_q8 = 620;
    g_camera.fog_near_z = 230;
    g_camera.fog_far_z = 620;
    g_camera.fog_color565 = vxpe2d_rgb565(90, 128, 100);
    g_camera.fog_strength = 150;

    vxpe2d_lightmap_init(&g_lightmap, 60, 80, SW, SH);
    vxpe_particles_init(&g_particles, VXPE_PARTICLE_POOL_MAX);
}

static int hook_screen(VxpeProjected25D* out) {
    return vxpe25d_project(&g_camera, g_hook_x, 6, g_hook_z, out);
}

static void spawn_splash(void) {
    VxpeProjected25D hp;
    int i;
    if (!hook_screen(&hp)) return;
    for (i = 0; i < 10; ++i) {
        VxpeParticleSpawn p;
        memset(&p, 0, sizeof(p));
        p.x = (int16_t)(hp.x + rnd_range(-3, 3));
        p.y = (int16_t)(hp.y + rnd_range(-2, 2));
        p.vx_q8 = rnd_range(-34, 34) * 256;
        p.vy_q8 = -rnd_range(28, 72) * 256;
        p.ay_q8 = rnd_range(80, 130) * 256;
        p.lifetime_ms = (uint16_t)rnd_range(320, 620);
        p.color565 = 0xFFFF;
        p.tint565 = (rnd32() & 1u)
            ? vxpe2d_rgb565(150, 225, 194)
            : vxpe2d_rgb565(204, 242, 218);
        p.alpha_start = (uint8_t)rnd_range(170, 235);
        p.alpha_end = 0;
        p.size_start = (uint8_t)rnd_range(1, 3);
        p.size_end = 1;
        p.blend = VXPE_BLEND_ADD;
        p.collide = 0;
        vxpe_particles_spawn(&g_particles, &p);
    }
}

static void draw_room(uint16_t* fb) {
    int y;
    vxpe2d_gradient_vertical(
        fb, SW, SH, 0, 0, SW, SH,
        vxpe2d_rgb565(17, 27, 24),
        vxpe2d_rgb565(33, 48, 39));

    /* Far wall panels / museum display silhouettes. */
    vxpe2d_fill_rect(fb, SW, SH, 0, 0, SW, 72, vxpe2d_rgb565(20, 30, 27));
    vxpe2d_fill_rect(fb, SW, SH, 8, 13, 45, 49, vxpe2d_rgb565(29, 43, 36));
    vxpe2d_fill_rect(fb, SW, SH, 187, 13, 45, 49, vxpe2d_rgb565(29, 43, 36));
    vxpe2d_fill_rect(fb, SW, SH, 13, 18, 35, 39, vxpe2d_rgb565(55, 73, 55));
    vxpe2d_fill_rect(fb, SW, SH, 192, 18, 35, 39, vxpe2d_rgb565(55, 73, 55));

    /* Vertical architecture and floor lines. */
    vxpe2d_fill_rect(fb, SW, SH, 0, 70, 12, 185, vxpe2d_rgb565(24, 35, 30));
    vxpe2d_fill_rect(fb, SW, SH, 228, 70, 12, 185, vxpe2d_rgb565(24, 35, 30));
    for (y = 74; y < 248; y += 22) {
        int inset = (y - 74) / 3;
        vxpe2d_fill_rect(fb, SW, SH, inset, y, SW - inset * 2, 1, vxpe2d_rgb565(47, 62, 49));
    }
}

static void draw_pool(uint16_t* fb) {
    VxpePlane25D rim;
    VxpePlane25D water;
    memset(&rim, 0, sizeof(rim));
    memset(&water, 0, sizeof(water));

    rim.src.x = 0; rim.src.y = 0; rim.src.w = 16; rim.src.h = 16;
    rim.center_x = 120;
    rim.top_y = 78;
    rim.bottom_y = 284;
    rim.top_width = 146;
    rim.bottom_width = 420;
    rim.tint565 = vxpe2d_rgb565(100, 102, 70);
    rim.alpha = 255;
    rim.blend = VXPE_BLEND_MULTIPLY;
    vxpe25d_draw_plane(fb, SW, SH, &g_water, &rim);

    water.src.x = 0; water.src.y = 0; water.src.w = 16; water.src.h = 16;
    water.center_x = 120;
    water.top_y = 86;
    water.bottom_y = 270;
    water.top_width = 122;
    water.bottom_width = 346;
    water.tint565 = vxpe2d_rgb565(118, 170, 134);
    water.alpha = 245;
    water.blend = VXPE_BLEND_ALPHA;
    water.ripple_amplitude = 2;
    water.ripple_phase = (uint8_t)((g_tick >> 1) & 15);
    water.ripple_wavelength_shift = 3;
    vxpe25d_draw_plane(fb, SW, SH, &g_water, &water);

    /* Near wood/metal lip hides clipped lower plane edges. */
    vxpe2d_fill_rect(fb, SW, SH, 0, 270, SW, 8, vxpe2d_rgb565(58, 52, 35));
    vxpe2d_fill_rect(fb, SW, SH, 0, 270, SW, 2, vxpe2d_rgb565(151, 134, 78));
}

static void draw_fish(uint16_t* fb) {
    VxpeBillboard25D fish;
    int32_t swim = (int32_t)((g_tick % 100) - 50);
    memset(&fish, 0, sizeof(fish));
    fish.src.x = 0; fish.src.y = 0; fish.src.w = 24; fish.src.h = 12;
    fish.world_x = swim;
    fish.world_y = -3;
    fish.world_z = 320 + (int32_t)((g_tick >> 2) & 31);
    fish.world_w = 42;
    fish.world_h = 20;
    fish.pivot_x_q8 = 128;
    fish.pivot_y_q8 = 128;
    fish.tint565 = vxpe2d_rgb565(118, 192, 151);
    fish.alpha = 150;
    fish.blend = VXPE_BLEND_ALPHA;
    fish.flip_x = (g_tick / 100) & 1u;
    vxpe25d_draw_billboard(fb, SW, SH, &g_camera, &g_fish, &fish);
}

static void draw_balls(uint16_t* fb) {
    unsigned i;
    for (i = 0; i < sizeof(g_balls) / sizeof(g_balls[0]); ++i) {
        const DemoBall* b = &g_balls[i];
        VxpeBillboard25D bb;
        vxpe25d_draw_ground_shadow(
            fb, SW, SH, &g_camera,
            b->x, b->z,
            (uint16_t)(b->size * 7 / 10), (uint16_t)(b->size * 2 / 10 + 1),
            vxpe2d_rgb565(10, 17, 12), 115, VXPE_BLEND_ALPHA);

        memset(&bb, 0, sizeof(bb));
        bb.src.x = 0; bb.src.y = 0; bb.src.w = 16; bb.src.h = 16;
        bb.world_x = b->x;
        bb.world_y = (int32_t)(b->size / 2);
        bb.world_z = b->z;
        bb.world_w = b->size;
        bb.world_h = b->size;
        bb.pivot_x_q8 = 128;
        bb.pivot_y_q8 = 256;
        bb.tint565 = b->tint;
        bb.alpha = 245;
        bb.blend = VXPE_BLEND_ALPHA;
        vxpe25d_draw_billboard(fb, SW, SH, &g_camera, &g_ball, &bb);
    }
}

static void draw_fishing(uint16_t* fb) {
    VxpeRopeStyle25D rope;
    VxpeProjected25D hp;
    memset(&rope, 0, sizeof(rope));
    rope.outer_color565 = vxpe2d_rgb565(19, 25, 19);
    rope.core_color565 = vxpe2d_rgb565(202, 229, 187);
    rope.outer_width = 3;
    rope.core_width = 1;
    rope.alpha = 225;
    rope.blend = VXPE_BLEND_ALPHA;

    /* Rod starts close to camera at the lower edge, line ends at hook. */
    vxpe25d_draw_rope_world(
        fb, SW, SH, &g_camera,
        -12, -42, 96,
        g_hook_x, 8, g_hook_z,
        &rope);

    if (hook_screen(&hp)) {
        vxpe2d_radial_light_fast(
            fb, SW, SH, hp.x, hp.y, 11,
            vxpe2d_rgb565(132, 219, 176), 58);
        vxpe2d_fill_rect(fb, SW, SH, hp.x - 1, hp.y - 1, 3, 3,
                         vxpe2d_rgb565(226, 246, 218));
        vxpe2d_draw_ring(
            fb, SW, SH, hp.x, hp.y + 1,
            7 + (int)((g_tick >> 2) & 3), 1,
            vxpe2d_rgb565(159, 220, 190),
            (uint8_t)(90 - ((g_tick >> 2) & 3) * 15),
            VXPE_BLEND_ADD);
    }

    /* Simple rod/hand silhouette in screen space. */
    vxpe2d_fill_rect(fb, SW, SH, 105, 286, 30, 7, vxpe2d_rgb565(39, 31, 24));
    vxpe2d_fill_rect(fb, SW, SH, 114, 278, 12, 16, vxpe2d_rgb565(126, 96, 67));
}

static void draw_lights(uint16_t* fb) {
    vxpe2d_lightmap_clear(&g_lightmap);
    vxpe2d_lightmap_add_radial(
        &g_lightmap, 38, 42, 44,
        vxpe2d_rgb565(151, 189, 137), 150);
    vxpe2d_lightmap_add_radial(
        &g_lightmap, 202, 42, 44,
        vxpe2d_rgb565(151, 189, 137), 150);
    vxpe2d_lightmap_add_radial(
        &g_lightmap, 120, 142, 58,
        vxpe2d_rgb565(80, 145, 105), 62);
    vxpe2d_lightmap_composite_add(&g_lightmap, fb, SW, SH, 92, 285);
}

static void draw_ui(uint16_t* fb) {
    int x = clampi((int)((g_hook_x + 90) * 70 / 180), 0, 70);
    int z = clampi((int)((g_hook_z - 130) * 70 / 260), 0, 70);
    vxpe2d_fill_rect(fb, SW, SH, 7, 7, 74, 14, vxpe2d_rgb565(12, 18, 15));
    vxpe2d_fill_rect(fb, SW, SH, 9, 10, x, 3, vxpe2d_rgb565(111, 192, 141));
    vxpe2d_fill_rect(fb, SW, SH, 9, 16, z, 3, vxpe2d_rgb565(154, 190, 114));
    vxpe2d_fill_rect(fb, SW, SH, 159, 7, 74, 14, vxpe2d_rgb565(12, 18, 15));
    vxpe2d_fill_rect(fb, SW, SH, 163, 10, 8, 8, vxpe2d_rgb565(132, 209, 165));
    vxpe2d_fill_rect(fb, SW, SH, 175, 10, 52, 2, vxpe2d_rgb565(70, 92, 75));
    vxpe2d_fill_rect(fb, SW, SH, 175, 16, 34, 2, vxpe2d_rgb565(70, 92, 75));
}

static void draw(void) {
    uint16_t* fb = (uint16_t*)framebuffer();
    VxpeGrade25D grade;
    if (!fb || g_layer < 0) return;

    draw_room(fb);
    draw_pool(fb);
    draw_fish(fb);
    draw_balls(fb);
    draw_fishing(fb);
    vxpe_particles_draw(&g_particles, fb, SW, SH);
    draw_lights(fb);

    memset(&grade, 0, sizeof(grade));
    grade.tint565 = vxpe2d_rgb565(79, 118, 91);
    grade.tint_alpha = 22;
    grade.vignette_alpha = 34;
    grade.dither_strength = 3;
    grade.fog_horizon_alpha = 18;
    vxpe25d_apply_grade(fb, SW, SH, &grade, 76);

    draw_ui(fb);
    vm_graphic_flush_layer(&g_layer, 1);
}

static void tick(VMINT tid) {
    (void)tid;
    ++g_tick;
    if ((g_tick % 42u) == 0u) spawn_splash();
    vxpe_particles_update(&g_particles, 33);
    draw();
}

void handle_keyevt(VMINT event, VMINT keycode) {
    if (event != VM_KEY_EVENT_DOWN && event != VM_KEY_EVENT_REPEAT) return;
    if (keycode == VM_KEY_LEFT || keycode == VM_KEY_NUM4) {
        g_hook_x = clampi((int)g_hook_x - 8, -88, 88);
    } else if (keycode == VM_KEY_RIGHT || keycode == VM_KEY_NUM6) {
        g_hook_x = clampi((int)g_hook_x + 8, -88, 88);
    } else if (keycode == VM_KEY_UP || keycode == VM_KEY_NUM2) {
        g_hook_z = clampi((int)g_hook_z + 12, 130, 390);
    } else if (keycode == VM_KEY_DOWN || keycode == VM_KEY_NUM8) {
        g_hook_z = clampi((int)g_hook_z - 12, 130, 390);
    } else if (keycode == VM_KEY_OK || keycode == VM_KEY_NUM5) {
        spawn_splash();
    } else if (keycode == VM_KEY_RIGHT_SOFTKEY ||
               keycode == VM_KEY_CLEAR || keycode == VM_KEY_BACK) {
        vm_exit_app();
        return;
    }
    draw();
}

void handle_penevt(VMINT event, VMINT x, VMINT y) {
    if (event == VM_PEN_EVENT_TAP || event == VM_PEN_EVENT_MOVE) {
        g_hook_x = clampi((x - 120) * 3 / 4, -88, 88);
        g_hook_z = clampi(390 - (y - 80) * 260 / 190, 130, 390);
        if (event == VM_PEN_EVENT_TAP) spawn_splash();
        draw();
    }
}

static void start(void) {
    if (g_layer < 0) g_layer = vm_graphic_create_layer(0, 0, SW, SH, -1);
    if (!g_started) {
        build_procedural_assets();
        setup_scene();
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
