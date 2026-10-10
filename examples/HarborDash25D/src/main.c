/* HarborDash25D - 240x320 VxpScene25D arcade sample.
 *
 * Sail a boat through a harbor: steer with LEFT/RIGHT (4/6), speed with
 * UP/DOWN (2/8), dodge red buoys, collect gold coins. Score + lives HUD is
 * drawn with plain framebuffer primitives (no font dependency).
 * OK (5) restarts after game over. Right softkey exits.
 */
#include "vmsys.h"
#include "vmio.h"
#include "vmgraph.h"
#include "vmtimer.h"
#include "graphics/VxpRender2D.h"
#include "graphics/VxpSpriteFx.h"
#include "graphics/VxpScene25D.h"
#include <stdint.h>
#include <string.h>

#define SW 240
#define SH 320

static VMINT g_layer = -1;
static VMINT g_timer = -1;
static uint32_t g_tick = 0;
static uint32_t g_rng = 0x25D0BEEFu;

/* game state */
static int32_t g_boat_x = 0;      /* world x, cell = 1 unit */
static int32_t g_speed = 3;       /* forward units per tick */
static int32_t g_dist = 0;        /* travelled distance */
static int g_score = 0;
static int g_lives = 3;
static int g_over = 0;
static int g_flash = 0;

/* input held */
static int g_left = 0, g_right = 0, g_up = 0, g_down = 0;

#define MAX_OBJS 10
typedef struct Obj {
    int active;
    int kind; /* 0 buoy (bad), 1 coin (good) */
    int32_t x, z; /* world pos relative to course start */
    int phase;
} Obj;
static Obj g_objs[MAX_OBJS];

/* procedural sprites */
static uint16_t g_water_px[16 * 16];
static uint16_t g_boat_px[20 * 14];
static uint8_t  g_boat_a[20 * 14];
static uint16_t g_buoy_px[12 * 16];
static uint8_t  g_buoy_a[12 * 16];
static uint16_t g_coin_px[10 * 10];
static uint8_t  g_coin_a[10 * 10];

static VxpeSpriteA8 g_water;
static VxpeSpriteA8 g_boat;
static VxpeSpriteA8 g_buoy;
static VxpeSpriteA8 g_coin;
static VxpeCamera25D g_cam;
static VxpeGrade25D g_grade;

static uint32_t rnd32(void) {
    g_rng = g_rng * 1664525u + 1013904223u;
    return g_rng;
}

static int rnd_range(int lo, int hi) {
    if (hi <= lo) return lo;
    return lo + (int)(rnd32() % (uint32_t)(hi - lo + 1));
}

static VMUINT16* framebuffer(void) {
    return (VMUINT16*)vm_graphic_get_layer_buffer(g_layer);
}

static void px(uint16_t* fb, int x, int y, uint16_t c) {
    if ((unsigned)x < (unsigned)SW && (unsigned)y < (unsigned)SH)
        fb[y * SW + x] = c;
}

static void bar(uint16_t* fb, int x, int y, int w, int h, uint16_t c) {
    int i, j;
    for (j = 0; j < h; ++j)
        for (i = 0; i < w; ++i)
            px(fb, x + i, y + j, c);
}

static void build_assets(void) {
    int x, y;
    memset(&g_water, 0, sizeof(g_water));
    memset(&g_boat, 0, sizeof(g_boat));
    memset(&g_buoy, 0, sizeof(g_buoy));
    memset(&g_coin, 0, sizeof(g_coin));
    /* water: dark blue with wave bands */
    for (y = 0; y < 16; ++y)
        for (x = 0; x < 16; ++x) {
            int wv = ((x + (y >> 1)) & 7) < 4 ? 0 : 10;
            g_water_px[y * 16 + x] =
                vxpe2d_rgb565((uint8_t)(18 + wv), (uint8_t)(52 + wv), (uint8_t)(96 + wv));
        }
    g_water.pixels = g_water_px; g_water.alpha = 0;
    g_water.width = 16; g_water.height = 16;
    g_water.stride = 16; g_water.alpha_stride = 0; g_water.opaque = 1;
    /* boat: brown hull + white sail, transparent corners */
    for (y = 0; y < 14; ++y)
        for (x = 0; x < 20; ++x) {
            uint16_t c = 0; uint8_t a = 0;
            if (y >= 9) { /* hull */
                if (x >= 1 && x < 19) {
                    c = vxpe2d_rgb565(122, 62, 28); a = 255;
                    if (y == 9) { c = vxpe2d_rgb565(150, 84, 40); }
                }
            } else { /* sail triangle */
                int half = (9 - y); /* narrows upward */
                int cx0 = 10 - half, cx1 = 10 + half;
                if (x >= cx0 && x <= cx1) {
                    c = vxpe2d_rgb565(235, 235, 240); a = 255;
                    if (x == 10) { c = vxpe2d_rgb565(190, 60, 50); }
                }
            }
            g_boat_px[y * 20 + x] = c; g_boat_a[y * 20 + x] = a;
        }
    g_boat.pixels = g_boat_px; g_boat.alpha = g_boat_a;
    g_boat.width = 20; g_boat.height = 14;
    g_boat.stride = 20; g_boat.alpha_stride = 20; g_boat.opaque = 0;
    /* buoy: red/white stripes */
    for (y = 0; y < 16; ++y)
        for (x = 0; x < 12; ++x) {
            uint16_t c = 0; uint8_t a = 0;
            int dx = x - 6;
            if (dx * dx <= 30) {
                a = 255;
                c = (y & 4) ? vxpe2d_rgb565(220, 30, 30)
                            : vxpe2d_rgb565(240, 240, 240);
                if (y < 3) { c = vxpe2d_rgb565(240, 200, 60); }
            }
            g_buoy_px[y * 12 + x] = c; g_buoy_a[y * 12 + x] = a;
        }
    g_buoy.pixels = g_buoy_px; g_buoy.alpha = g_buoy_a;
    g_buoy.width = 12; g_buoy.height = 16;
    g_buoy.stride = 12; g_buoy.alpha_stride = 12; g_buoy.opaque = 0;
    /* coin: gold disc */
    for (y = 0; y < 10; ++y)
        for (x = 0; x < 10; ++x) {
            uint16_t c = 0; uint8_t a = 0;
            int dx = x - 5, dy = y - 5;
            int d2 = dx * dx + dy * dy;
            if (d2 <= 22) {
                a = 255;
                c = (d2 <= 8) ? vxpe2d_rgb565(255, 236, 140)
                              : vxpe2d_rgb565(232, 170, 40);
            }
            g_coin_px[y * 10 + x] = c; g_coin_a[y * 10 + x] = a;
        }
    g_coin.pixels = g_coin_px; g_coin.alpha = g_coin_a;
    g_coin.width = 10; g_coin.height = 10;
    g_coin.stride = 10; g_coin.alpha_stride = 10; g_coin.opaque = 0;
}

static void reset_game(void) {
    int i;
    g_boat_x = 0; g_speed = 3; g_dist = 0;
    g_score = 0; g_lives = 3; g_over = 0; g_flash = 0;
    for (i = 0; i < MAX_OBJS; ++i) g_objs[i].active = 0;
}

static void spawn_obj(void) {
    int i;
    for (i = 0; i < MAX_OBJS; ++i) {
        if (!g_objs[i].active) {
            g_objs[i].active = 1;
            g_objs[i].kind = (rnd32() & 3) == 0 ? 1 : 0; /* 1/4 coins */
            g_objs[i].x = rnd_range(-90, 90);
            g_objs[i].z = g_dist + rnd_range(320, 520);
            g_objs[i].phase = rnd_range(0, 63);
            return;
        }
    }
}

static void update(void) {
    int i;
    if (g_over) return;
    if (g_left) g_boat_x -= 3;
    if (g_right) g_boat_x += 3;
    if (g_boat_x < -110) g_boat_x = -110;
    if (g_boat_x > 110) g_boat_x = 110;
    if (g_up && g_speed < 7) g_speed++;
    if (g_down && g_speed > 2) g_speed--;
    g_dist += g_speed;
    if ((rnd32() & 7) == 0) spawn_obj();
    for (i = 0; i < MAX_OBJS; ++i) {
        Obj* o = &g_objs[i];
        int32_t rel;
        if (!o->active) continue;
        rel = o->z - g_dist;
        if (rel < 20) { o->active = 0; continue; } /* passed */
        if (rel < 60) {
            int32_t dx = o->x - g_boat_x;
            if (dx < 0) dx = -dx;
            if (dx < 22) {
                if (o->kind == 1) {
                    g_score += 10;
                    if (g_score > 990) g_score = 990;
                } else if (g_flash == 0) {
                    g_lives--;
                    g_flash = 20;
                    if (g_lives <= 0) { g_lives = 0; g_over = 1; }
                }
                o->active = 0;
            }
        }
    }
    if (g_flash > 0) g_flash--;
}

static void draw_hud(uint16_t* fb) {
    int i;
    /* score bar (top): 1 block per 10 points, max 99 blocks shown as columns */
    int blocks = g_score / 10;
    if (blocks > 40) blocks = 40;
    bar(fb, 8, 6, 100, 3, vxpe2d_rgb565(20, 26, 40));
    bar(fb, 8, 6, blocks * 100 / 40 + (blocks ? 2 : 0), 3,
        vxpe2d_rgb565(255, 210, 80));
    /* lives hearts: red squares */
    for (i = 0; i < 3; ++i) {
        uint16_t c = (i < g_lives) ? vxpe2d_rgb565(235, 60, 60)
                                   : vxpe2d_rgb565(60, 60, 80);
        bar(fb, SW - 16 - i * 14, 4, 10, 8, c);
    }
    /* speed gauge (left edge) */
    bar(fb, 4, 40, 4, 70, vxpe2d_rgb565(20, 26, 40));
    bar(fb, 4, 40 + 70 - g_speed * 10, 4, g_speed * 10,
        vxpe2d_rgb565(90, 200, 250));
    if (g_over) {
        /* game-over frame */
        int x, y;
        for (y = 140; y < 180; ++y)
            for (x = 40; x < SW - 40; ++x)
                if (x == 40 || x == SW - 41 || y == 140 || y == 179)
                    px(fb, x, y, vxpe2d_rgb565(235, 235, 240));
        /* blinking restart block */
        if ((g_tick & 16) == 0)
            bar(fb, SW / 2 - 20, 156, 40, 8, vxpe2d_rgb565(255, 210, 80));
    }
}

static void draw(void) {
    VMUINT16* fb = framebuffer();
    int i, order[MAX_OBJS];
    int n = 0;
    VxpePlane25D sea;
    VxpeBillboard25D bb;
    if (!fb) return;
    /* sky */
    vxpe2d_gradient_vertical(fb, SW, SH, 0, 0, SW, 120,
        vxpe2d_rgb565(30, 90, 160), vxpe2d_rgb565(150, 210, 240));
    /* sea plane below horizon */
    memset(&sea, 0, sizeof(sea));
    sea.src.x = 0; sea.src.y = 0; sea.src.w = 16; sea.src.h = 16;
    sea.center_x = SW / 2; sea.top_y = 118; sea.bottom_y = SH;
    sea.top_width = 200; sea.bottom_width = SW;
    sea.tint565 = 0xFFFF; sea.alpha = 255; sea.blend = 0;
    sea.ripple_amplitude = 2;
    sea.ripple_phase = (uint8_t)(g_tick & 63);
    sea.ripple_wavelength_shift = 4;
    vxpe25d_draw_plane(fb, SW, SH, &g_water, &sea);
    /* camera follows boat */
    g_cam.world_x = g_boat_x;
    g_cam.world_y = 0;
    g_cam.world_z = g_dist;
    /* collect + sort far-to-near */
    for (i = 0; i < MAX_OBJS; ++i)
        if (g_objs[i].active) order[n++] = i;
    {
        int a, b;
        for (a = 0; a < n; ++a)
            for (b = a + 1; b < n; ++b) {
                int32_t za = g_objs[order[a]].z - g_dist;
                int32_t zb = g_objs[order[b]].z - g_dist;
                if (zb > za) { int t = order[a]; order[a] = order[b]; order[b] = t; }
            }
    }
    memset(&bb, 0, sizeof(bb));
    bb.pivot_x_q8 = 128; bb.pivot_y_q8 = 256;
    bb.tint565 = 0xFFFF; bb.alpha = 255; bb.blend = 0;
    for (i = 0; i < n; ++i) {
        Obj* o = &g_objs[order[i]];
        int32_t rel = o->z - g_dist;
        if (rel < 24 || rel > 620) continue;
        if (o->kind == 1) {
            bb.src.x = 0; bb.src.y = 0; bb.src.w = 10; bb.src.h = 10;
            bb.world_x = o->x; bb.world_y = 0; bb.world_z = rel;
            bb.world_w = 12; bb.world_h = 12;
            vxpe25d_draw_billboard(fb, SW, SH, &g_cam, &g_coin, &bb);
        } else {
            int bob = ((g_tick + o->phase) & 31) < 16 ? 0 : 2;
            bb.src.x = 0; bb.src.y = 0; bb.src.w = 12; bb.src.h = 16;
            bb.world_x = o->x; bb.world_y = bob; bb.world_z = rel;
            bb.world_w = 16; bb.world_h = 22;
            vxpe25d_draw_billboard(fb, SW, SH, &g_cam, &g_buoy, &bb);
        }
    }
    /* player boat at fixed distance ahead of camera */
    bb.src.x = 0; bb.src.y = 0; bb.src.w = 20; bb.src.h = 14;
    bb.world_x = g_boat_x; bb.world_y = 0; bb.world_z = g_dist + 46;
    bb.world_w = 34; bb.world_h = 24;
    if (g_flash & 2) bb.tint565 = vxpe2d_rgb565(255, 120, 120);
    else bb.tint565 = 0xFFFF;
    vxpe25d_draw_billboard(fb, SW, SH, &g_cam, &g_boat, &bb);
    /* atmosphere */
    vxpe25d_apply_grade(fb, SW, SH, &g_grade, 118);
    draw_hud(fb);
    vm_graphic_flush_layer(&g_layer, 1);
}

static void tick(VMINT tid) {
    (void)tid;
    g_tick++;
    update();
    draw();
}

static void start(void) {
    if (g_layer < 0)
        g_layer = vm_graphic_create_layer(0, 0, SW, SH, -1);
    build_assets();
    vxpe25d_camera_init(&g_cam, SW, SH, 118, 220);
    g_cam.fog_near_z = 260; g_cam.fog_far_z = 620;
    g_cam.fog_color565 = vxpe2d_rgb565(150, 210, 240);
    g_cam.fog_strength = 200;
    memset(&g_grade, 0, sizeof(g_grade));
    g_grade.tint565 = vxpe2d_rgb565(10, 20, 40);
    g_grade.tint_alpha = 18;
    g_grade.vignette_alpha = 60;
    reset_game();
    if (g_timer < 0) g_timer = vm_create_timer(50, tick);
    draw();
}

static void stop(void) {
    if (g_timer >= 0) { vm_delete_timer(g_timer); g_timer = -1; }
    if (g_layer >= 0) { vm_graphic_delete_layer(g_layer); g_layer = -1; }
}

void handle_sysevt(VMINT message, VMINT param) {
    (void)param;
    switch (message) {
    case VM_MSG_CREATE:
    case VM_MSG_ACTIVE: start(); break;
    case VM_MSG_PAINT: draw(); break;
    case VM_MSG_INACTIVE:
    case VM_MSG_QUIT:
        stop();
        if (message == VM_MSG_QUIT) vm_exit_app();
        break;
    }
}

static void set_held(int key, int down) {
    switch (key) {
    case VM_KEY_LEFT: case VM_KEY_NUM4: g_left = down; break;
    case VM_KEY_RIGHT: case VM_KEY_NUM6: g_right = down; break;
    case VM_KEY_UP: case VM_KEY_NUM2: g_up = down; break;
    case VM_KEY_DOWN: case VM_KEY_NUM8: g_down = down; break;
    }
}

void handle_keyevt(VMINT event, VMINT keycode) {
    if (event == VM_KEY_EVENT_DOWN) {
        set_held(keycode, 1);
        if ((keycode == VM_KEY_OK || keycode == VM_KEY_NUM5) && g_over)
            reset_game();
        if (keycode == VM_KEY_RIGHT_SOFTKEY || keycode == VM_KEY_CLEAR ||
            keycode == VM_KEY_BACK)
            vm_exit_app();
    } else if (event == VM_KEY_EVENT_UP) {
        set_held(keycode, 0);
    }
}

void handle_penevt(VMINT event, VMINT x, VMINT y) {
    (void)event; (void)x; (void)y;
}

void vm_main(void) {
    vm_reg_sysevt_callback(handle_sysevt);
    vm_reg_keyboard_callback(handle_keyevt);
    vm_reg_pen_callback(handle_penevt);
}
