/* MeadowRush25D - 240x320 VxpScene25D driving sample.
 *
 * First-person meadow run: the camera IS the player, so the scene exercises
 * the two game-facing 2.5D core paths:
 *   - vxpe25d_draw_ground: camera-anchored perspective grass under yaw+drive
 *   - vxpe25d_batch_flush: unsorted trees/rocks/coins auto-sorted far-to-near
 *     with projected ground shadows
 * An on-screen frame-time probe bar (bottom-left) lets emulator runs read the
 * real per-frame cost without trusting pixel-font text.
 *
 * LEFT/RIGHT (4/6) steer, UP/DOWN (2/8) throttle, OK (5) restarts,
 * right softkey / CLEAR exits. Pen: left/right halves steer, middle brakes.
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
#define HORIZON 104
#define CAM_Y 44
#define EYE_Z 30        /* objects closer than this (camera space) are behind */
#define FAR_Z 900
#define OBJ_COUNT 40

static VMINT g_layer = -1;
static VMINT g_timer = -1;
static uint32_t g_tick = 0;
static uint32_t g_rng = 0x25D0FADEu;

/* world + player */
static int g_yaw = 0;               /* 0..31, 11.25 deg per step */
static int32_t g_cam_x = 0, g_cam_z = 0;
static int g_speed = 3;             /* 1..8 units per tick */
static int g_score = 0, g_lives = 3, g_over = 0, g_flash = 0;
static uint32_t g_frame_ms = 0;

/* input held */
static int g_left = 0, g_right = 0, g_up = 0, g_down = 0;

typedef struct Obj {
    int active, kind;               /* 0 tree, 1 rock, 2 coin */
    int32_t x, z;
    int phase;
} Obj;
static Obj g_objs[OBJ_COUNT];

/* procedural art */
static uint16_t g_grass_px[16 * 16];
static uint16_t g_tree_px[16 * 24];   static uint8_t g_tree_a[16 * 24];
static uint16_t g_rock_px[12 * 8];    static uint8_t g_rock_a[12 * 8];
static uint16_t g_coin_px[8 * 8];     static uint8_t g_coin_a[8 * 8];
static VxpeSpriteA8 g_grass, g_tree, g_rock, g_coin;
static VxpeCamera25D g_cam;
static VxpeBillboardBatch25D g_batch;
static VxpeGrade25D g_grade;

static const int16_t SIN_Q14[32] = {
    0,3196,6270,9102,11585,13623,15137,16069,16384,16069,15137,13623,11585,
    9102,6270,3196,0,-3196,-6270,-9102,-11585,-13623,-15137,-16069,-16384,
    -16069,-15137,-13623,-11585,-9102,-6270,-3196};
static const int16_t COS_Q14[32] = {
    16384,16069,15137,13623,11585,9102,6270,3196,0,-3196,-6270,-9102,-11585,
    -13623,-15137,-16069,-16384,-16069,-15137,-13623,-11585,-9102,-6270,-3196,
    0,3196,6270,9102,11585,13623,15137,16069};

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
    memset(&g_grass, 0, sizeof(g_grass));
    memset(&g_tree, 0, sizeof(g_tree));
    memset(&g_rock, 0, sizeof(g_rock));
    memset(&g_coin, 0, sizeof(g_coin));
    /* grass: two-tone checker with blade speckles */
    for (y = 0; y < 16; ++y)
        for (x = 0; x < 16; ++x) {
            int blk = ((x >> 2) + (y >> 2)) & 1;
            int sp = ((x * 7 + y * 13) & 7) == 0 ? 18 : 0;
            g_grass_px[y * 16 + x] = vxpe2d_rgb565(
                (uint8_t)(blk ? 60 : 48),
                (uint8_t)(blk ? 148 + sp : 122 + sp),
                (uint8_t)(blk ? 62 : 50));
        }
    g_grass.pixels = g_grass_px;
    g_grass.width = g_grass.height = g_grass.stride = 16;
    g_grass.opaque = 1;
    /* tree: trunk + two-tone canopy blob */
    for (y = 0; y < 24; ++y)
        for (x = 0; x < 16; ++x) {
            uint16_t c = 0; uint8_t a = 0;
            if (y >= 15 && x >= 6 && x <= 9) {          /* trunk */
                c = vxpe2d_rgb565(110, 66, 34); a = 255;
            } else if (y < 17) {                        /* canopy */
                int dx = x - 7, dy = y - 8;
                if (dx * dx * 2 + dy * dy * 3 < 100) {
                    c = ((x + y) & 3) ? vxpe2d_rgb565(46, 150, 60)
                                      : vxpe2d_rgb565(30, 112, 44);
                    a = 255;
                }
            }
            g_tree_px[y * 16 + x] = c; g_tree_a[y * 16 + x] = a;
        }
    g_tree.pixels = g_tree_px; g_tree.alpha = g_tree_a;
    g_tree.width = 16; g_tree.height = 24;
    g_tree.stride = g_tree.alpha_stride = 16;
    /* rock: squat grey dome */
    for (y = 0; y < 8; ++y)
        for (x = 0; x < 12; ++x) {
            uint16_t c = 0; uint8_t a = 0;
            int dx = x - 5, dy = y - 8;
            if (dy * dy * 2 + dx * dx * 3 < 120) {
                c = y < 3 ? vxpe2d_rgb565(168, 168, 176)
                          : vxpe2d_rgb565(112, 110, 120);
                a = 255;
            }
            g_rock_px[y * 12 + x] = c; g_rock_a[y * 12 + x] = a;
        }
    g_rock.pixels = g_rock_px; g_rock.alpha = g_rock_a;
    g_rock.width = 12; g_rock.height = 8;
    g_rock.stride = g_rock.alpha_stride = 12;
    /* coin: gold disc with highlight */
    for (y = 0; y < 8; ++y)
        for (x = 0; x < 8; ++x) {
            uint16_t c = 0; uint8_t a = 0;
            int dx = x - 3, dy = y - 3;
            if (dx * dx + dy * dy <= 10) {
                c = (x + y < 5) ? vxpe2d_rgb565(255, 232, 120)
                                : vxpe2d_rgb565(230, 170, 40);
                a = 255;
            }
            g_coin_px[y * 8 + x] = c; g_coin_a[y * 8 + x] = a;
        }
    g_coin.pixels = g_coin_px; g_coin.alpha = g_coin_a;
    g_coin.width = g_coin.height = g_coin.stride = g_coin.alpha_stride = 8;
}

static void place_obj(Obj* o, int32_t ahead_min, int32_t ahead_max) {
    /* spawn in a wide band ahead in WORLD axes; camera turns through them */
    int32_t lead = (int32_t)ahead_min + (int32_t)rnd32() % (uint32_t)(ahead_max - ahead_min);
    int side = (int)(rnd32() & 1) ? 1 : -1;
    o->active = 1;
    o->kind = rnd32() % 100 < 45 ? 0 : (rnd32() % 100 < 55 ? 1 : 2);
    o->phase = (int)(rnd32() & 31);
    o->z = g_cam_z + lead;
    o->x = g_cam_x + side * (24 + (int32_t)(rnd32() % 260));
}

static void reset_game(void) {
    int i;
    g_rng = 0x25D0FADEu;
    g_yaw = 0; g_cam_x = 0; g_cam_z = 0; g_speed = 3;
    g_score = 0; g_lives = 3; g_over = 0; g_flash = 0;
    for (i = 0; i < OBJ_COUNT; ++i) {
        memset(&g_objs[i], 0, sizeof(Obj));
        place_obj(&g_objs[i], 60 + i * 24, 90 + i * 24);
    }
}

static void update(void) {
    int i;
    if (g_over) return;
    if (g_left)  g_yaw = (g_yaw + 31) & 31;
    if (g_right) g_yaw = (g_yaw + 1) & 31;
    if (g_up)   { if (g_speed < 8) ++g_speed; }
    if (g_down) { if (g_speed > 1) --g_speed; }
    /* forward along yaw: dx = -sin, dz = cos (yaw index steps right) */
    g_cam_x -= (SIN_Q14[g_yaw] * g_speed) >> 13;
    g_cam_z += (COS_Q14[g_yaw] * g_speed) >> 13;
    for (i = 0; i < OBJ_COUNT; ++i) {
        Obj* o = &g_objs[i];
        int32_t dx = o->x - g_cam_x, dz = o->z - g_cam_z;
        int32_t cdx = (dx * COS_Q14[g_yaw] + dz * SIN_Q14[g_yaw]) >> 14;
        int32_t cdz = (dz * COS_Q14[g_yaw] - dx * SIN_Q14[g_yaw]) >> 14;
        /* collisions first: objects inside EYE_Z respawn and vanish */
        if (o->kind == 2 && cdx * cdx + cdz * cdz < 26 * 26) {
            g_score += 10; place_obj(o, 500, 950); continue;
        }
        if (o->kind == 1 && !g_flash && cdx * cdx < 12 * 12 && cdz < 20) {
            --g_lives; g_flash = 24;
            place_obj(o, 500, 950);
            if (g_lives <= 0) g_over = 1;
            continue;
        }
        if (cdz < EYE_Z) place_obj(o, 500, 950);
    }
    if (g_flash) --g_flash;
}

static void draw_hud(uint16_t* fb) {
    int i;
    /* lives pips */
    for (i = 0; i < 3; ++i)
        bar(fb, 4 + i * 8, 4, 6, 6,
            i < g_lives ? vxpe2d_rgb565(240, 70, 90) : vxpe2d_rgb565(40, 44, 52));
    /* score as 10-point blocks, right aligned */
    for (i = 0; i < 8; ++i) {
        int v = (g_score / (10 * (i + 1))) % 10;
        uint16_t c = v > 7 ? vxpe2d_rgb565(255, 220, 90)
                 : v > 4 ? vxpe2d_rgb565(120, 220, 140)
                 : v > 0 ? vxpe2d_rgb565(90, 160, 250)
                         : vxpe2d_rgb565(30, 34, 42);
        bar(fb, SW - 16 - i * 14, 4, 10, 8, c);
    }
    /* speed gauge (left edge) */
    bar(fb, 4, 40, 4, 80, vxpe2d_rgb565(20, 26, 40));
    bar(fb, 4, 40 + 80 - g_speed * 10, 4, g_speed * 10,
        vxpe2d_rgb565(90, 200, 250));
    /* frame-time probe: 1 px per ms, green <=20, amber <=40, red above.
     * Label block marks the bar so grabs can locate it deterministically. */
    bar(fb, 4, SH - 12, 64, 8, vxpe2d_rgb565(16, 18, 24));
    bar(fb, 4, SH - 12, 2, 8, vxpe2d_rgb565(255, 255, 255));
    {
        int ms = (int)(g_frame_ms > 999 ? 999 : g_frame_ms);
        int w = ms > 63 ? 63 : ms;
        uint16_t c = ms <= 20 ? vxpe2d_rgb565(80, 220, 110)
                   : ms <= 40 ? vxpe2d_rgb565(240, 200, 70)
                              : vxpe2d_rgb565(240, 80, 80);
        bar(fb, 6, SH - 10, w, 4, c);
    }
    if (g_over) {
        int x, y;
        for (y = 140; y < 180; ++y)
            for (x = 40; x < SW - 40; ++x)
                if (x == 40 || x == SW - 41 || y == 140 || y == 179)
                    px(fb, x, y, vxpe2d_rgb565(235, 235, 240));
        if ((g_tick & 16) == 0)
            bar(fb, SW / 2 - 20, 156, 40, 8, vxpe2d_rgb565(255, 210, 80));
    }
}

static void draw(void) {
    VMUINT16* fb = framebuffer();
    VxpeGround25D ground;
    int i;
    uint32_t t0;
    if (!fb) return;
    t0 = vm_get_tick_count();
    /* sky down to the ground horizon */
    vxpe2d_gradient_vertical(fb, SW, SH, 0, 0, SW, HORIZON,
        vxpe2d_rgb565(34, 96, 168), vxpe2d_rgb565(158, 214, 240));
    /* camera-anchored grass: drives and yaws with the player */
    g_cam.world_x = g_cam_x;
    g_cam.world_y = CAM_Y;
    g_cam.world_z = g_cam_z;
    g_cam.sin_yaw_q14 = SIN_Q14[(g_yaw + 16) & 31]; /* = -sin(yaw): camera faces travel */
    g_cam.cos_yaw_q14 = COS_Q14[g_yaw];
    memset(&ground, 0, sizeof(ground));
    ground.src.x = 0; ground.src.y = 0; ground.src.w = 16; ground.src.h = 16;
    ground.tile_w = 40; ground.tile_h = 40;
    ground.blend = VXPE_BLEND_COPY; ground.use_fog = 1;
    vxpe25d_draw_ground(fb, SW, SH, &g_cam, &g_grass, &ground);
    /* everything else: pushed in slot order, batch sorts far-to-near */
    vxpe25d_batch_init(&g_batch);
    for (i = 0; i < OBJ_COUNT; ++i) {
        Obj* o = &g_objs[i];
        VxpeBatchEntry25D e;
        const VxpeSpriteA8* spr;
        int16_t bob = 0;
        if (!o->active) continue;
        memset(&e, 0, sizeof(e));
        if (o->kind == 0) {
            spr = &g_tree;
            e.billboard.src.w = 16; e.billboard.src.h = 24;
            e.billboard.world_w = 30; e.billboard.world_h = 46;
            e.shadow_radius_x = 10; e.shadow_radius_y = 3;
        } else if (o->kind == 1) {
            spr = &g_rock;
            e.billboard.src.w = 12; e.billboard.src.h = 8;
            e.billboard.world_w = 20; e.billboard.world_h = 13;
            e.shadow_radius_x = 7; e.shadow_radius_y = 2;
        } else {
            spr = &g_coin;
            bob = (int16_t)(((g_tick + o->phase) & 15) < 8 ? 0 : 2);
            e.billboard.src.w = 8; e.billboard.src.h = 8;
            e.billboard.world_w = 9; e.billboard.world_h = 9;
            e.billboard.world_y = 6 + bob;
        }
        e.sprite = spr;
        e.billboard.world_x = o->x;
        e.billboard.world_z = o->z;
        e.billboard.pivot_x_q8 = 128; e.billboard.pivot_y_q8 = 256;
        e.billboard.tint565 = (g_flash & 8) && o->kind == 1
            ? vxpe2d_rgb565(255, 140, 140) : 0xFFFF;
        e.billboard.alpha = 255; e.billboard.blend = VXPE_BLEND_ALPHA;
        e.shadow_color565 = 0x18C3; e.shadow_alpha = 96;
        e.shadow_blend = VXPE_BLEND_ALPHA;
        vxpe25d_batch_push(&g_batch, &e);
    }
    vxpe25d_batch_flush(&g_batch, fb, SW, SH, &g_cam);
    /* atmosphere + HUD last at native resolution */
    vxpe25d_apply_grade(fb, SW, SH, &g_grade, HORIZON);
    draw_hud(fb);
    g_frame_ms = vm_get_tick_count() - t0;
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
    vxpe25d_camera_init(&g_cam, SW, SH, HORIZON, 170);
    g_cam.near_z = 24; g_cam.far_z = FAR_Z;
    g_cam.fog_near_z = 320; g_cam.fog_far_z = 860;
    g_cam.fog_color565 = vxpe2d_rgb565(150, 200, 228);
    g_cam.fog_strength = 190;
    memset(&g_grade, 0, sizeof(g_grade));
    g_grade.tint565 = vxpe2d_rgb565(12, 22, 40);
    g_grade.tint_alpha = 14;
    g_grade.vignette_alpha = 56;
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
    int down = (event == VM_PEN_EVENT_TAP || event == VM_PEN_EVENT_MOVE ||
                event == VM_PEN_EVENT_LONG_TAP);
    if (y < HORIZON) { if (!down) g_left = g_right = g_down = 0; return; }
    if (down) {
        if (x < SW / 3) g_left = 1;
        else if (x > 2 * SW / 3) g_right = 1;
        else g_down = 1;
        if (g_over) reset_game();
    } else {
        g_left = g_right = g_down = 0;
    }
}

void vm_main(void) {
    vm_reg_sysevt_callback(handle_sysevt);
    vm_reg_keyboard_callback(handle_keyevt);
    vm_reg_pen_callback(handle_penevt);
}
