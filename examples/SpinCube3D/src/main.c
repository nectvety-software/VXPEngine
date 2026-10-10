/* SpinCube3D - 240x320 VxpSoft3D sample: clean-room soft 3D on MRE.
 *
 * A textured cube spins with perspective-correct UV, 16-bit depth, baked
 * per-face light and distance fog — all integer, no FPU. LEFT/RIGHT orbit
 * yaw, UP/DOWN pitch, OK toggles auto-spin. Right softkey exits.
 * HUD shows real FPS (vm_get_tick_count) as a bar + cube icon.
 */
#include "vmsys.h"
#include "vmio.h"
#include "vmgraph.h"
#include "vmtimer.h"
#include "graphics/VxpRender2D.h"
#include "graphics/VxpSpriteFx.h"
#include "graphics/VxpSoft3D.h"
#include <stdint.h>
#include <string.h>

#define SW 240
#define SH 320
#define HALF 22
#define CENTER_Z 130

static VMINT g_layer = -1;
static VMINT g_timer = -1;
static uint32_t g_tick = 0;

/* framebuffer mirrors (caller-owned, static: 150KB + 150KB depth) */
static uint16_t g_depth[SW * SH];

/* game state */
static uint8_t g_yaw = 0;       /* 0..255 = 0..2pi */
static uint8_t g_pitch = 0;
static int g_auto = 1;
static int g_left = 0, g_right = 0, g_up = 0, g_down = 0;
static uint32_t g_fps_mark = 0;
static int g_fps = 0;
static int g_frames = 0;

/* 8x8 checker texture */
static uint16_t g_tex_px[8 * 8];
static VxpeSpriteA8 g_tex;
static VxpeSoft3DTarget g_target;
static VxpeSoft3DCamera g_cam;
static VxpeSoft3DMaterial g_mat;
static VxpeSoft3DLight g_light;

/* baked per-face illumination (object space, light fixed at +Z) */
static uint8_t g_face_illum[6];

/* 256-entry sine LUT, Q14 */
static int16_t g_sin_q14[256];
static int g_lut_ready = 0;

static int16_t isin(uint8_t a) { return g_sin_q14[a]; }
static int16_t icos(uint8_t a) { return g_sin_q14[(uint8_t)(a + 64)]; }

static void build_sin(void) {
    int i;
    if (g_lut_ready) return;
    /* sin via Taylor on the first octant (0..pi/2), Q16; then exact
     * quadrant symmetry. Integer only, runs once at startup. */
    {
        int32_t oct[65];
        int k;
        for (k = 0; k <= 64; ++k) {
            /* x = k * (pi/2) / 64 in Q16: (pi/2)*65536/64 = 102944/64 */
            int32_t x_q16 = (k * 102944) >> 6;
            int32_t x2 = (int32_t)(((int64_t)x_q16 * x_q16) >> 16);
            int32_t x3 = (int32_t)(((int64_t)x2 * x_q16) >> 16);
            int32_t x5 = (int32_t)(((int64_t)x2 * x3) >> 16);
            int32_t s = x_q16 - x3 / 6 + x5 / 120; /* Q16 */
            if (s < 0) s = 0;
            if (s > 65536) s = 65536;
            oct[k] = s;
        }
        for (k = 0; k < 64; ++k) {
            int32_t s0 = (oct[k] * 16384 + 32768) >> 16; /* Q14 */
            g_sin_q14[k] = (int16_t)s0;                 /* quad 0 */
            g_sin_q14[64 + k] = (int16_t)s0;            /* quad 1 mirrored below */
            g_sin_q14[128 + k] = (int16_t)-s0;
            g_sin_q14[192 + k] = (int16_t)-s0;
        }
        /* mirror quad 1 (sin rises to 1 at 64 then falls): reuse reversed */
        for (k = 0; k < 64; ++k) {
            int32_t s1 = (oct[64 - k] * 16384 + 32768) >> 16;
            g_sin_q14[64 + k] = (int16_t)s1;
            g_sin_q14[192 + k] = (int16_t)-s1;
        }
        g_sin_q14[64] = 16384; g_sin_q14[192] = -16384;
        g_sin_q14[0] = 0; g_sin_q14[128] = 0;
    }
    g_lut_ready = 1;
}

/* cube corners, object space */
static const int32_t g_corners[8][3] = {
    {-HALF, -HALF, -HALF}, {HALF, -HALF, -HALF},
    {HALF, HALF, -HALF}, {-HALF, HALF, -HALF},
    {-HALF, -HALF, HALF}, {HALF, -HALF, HALF},
    {HALF, HALF, HALF}, {-HALF, HALF, HALF}
};

/* 6 faces as corner quads (outward), + object-space normals */
static const uint8_t g_quads[6][4] = {
    {4, 5, 6, 7}, /* front +z */
    {1, 0, 3, 2}, /* back -z */
    {1, 2, 6, 5}, /* right +x */
    {0, 4, 7, 3}, /* left -x */
    {3, 7, 6, 2}, /* top +y */
    {0, 1, 5, 4}  /* bottom -y */
};
static const int32_t g_normals[6][3] = {
    {0, 0, 16384}, {0, 0, -16384},
    {16384, 0, 0}, {-16384, 0, 0},
    {0, 16384, 0}, {0, -16384, 0}
};

static void rotate_point(int32_t x, int32_t y, int32_t z,
                         int16_t cy, int16_t sy, int16_t cp, int16_t sp,
                         int32_t* ox, int32_t* oy, int32_t* oz) {
    /* yaw around Y, then pitch around X */
    int32_t x1 = (int32_t)(((int64_t)x * cy - (int64_t)z * sy) >> 14);
    int32_t z1 = (int32_t)(((int64_t)x * sy + (int64_t)z * cy) >> 14);
    int32_t y2 = (int32_t)(((int64_t)y * cp - (int64_t)z1 * sp) >> 14);
    int32_t z2 = (int32_t)(((int64_t)y * sp + (int64_t)z1 * cp) >> 14);
    *ox = x1; *oy = y2; *oz = z2 + CENTER_Z;
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
    for (y = 0; y < 8; ++y)
        for (x = 0; x < 8; ++x) {
            int chk = ((x >> 1) + (y >> 1)) & 1;
            int edge = (x == 0 || y == 0 || x == 7 || y == 7);
            if (edge) g_tex_px[y * 8 + x] = vxpe2d_rgb565(20, 24, 40);
            else if (chk) g_tex_px[y * 8 + x] = vxpe2d_rgb565(70, 140, 230);
            else g_tex_px[y * 8 + x] = vxpe2d_rgb565(235, 240, 250);
        }
    memset(&g_tex, 0, sizeof(g_tex));
    g_tex.pixels = g_tex_px; g_tex.alpha = 0;
    g_tex.width = 8; g_tex.height = 8;
    g_tex.stride = 8; g_tex.alpha_stride = 0; g_tex.opaque = 1;
}

static void bake_light(void) {
    /* Object-space bake with light fixed at +Z (viewer side), via the real
     * bake API: positions unused by the math, normals carry the faces. */
    VxpeSoft3DVec pos[6], nrm[6];
    int i;
    VxpeSoft3DLight bl;
    vxpe_soft3d_light_init(&bl);
    bl.ambient = 110;
    for (i = 0; i < 6; ++i) {
        pos[i].x = 0; pos[i].y = 0; pos[i].z = 0;
        nrm[i].x = g_normals[i][0];
        nrm[i].y = g_normals[i][1];
        nrm[i].z = g_normals[i][2];
    }
    vxpe_soft3d_bake_vertex_light(pos, nrm, NULL, g_face_illum, 6, &bl);
}

static void draw_cube(uint16_t* fb) {
    int16_t cy = icos(g_yaw), sy = isin(g_yaw);
    int16_t cp = icos(g_pitch), sp = isin(g_pitch);
    int f;
    /* static: MRE dislikes big stack frames */
    static VxpeSoft3DVertex v[4];
    static uint16_t idx16[6] = {0, 1, 2, 0, 2, 3};
    static uint8_t il[2];
    VxpeSoft3DMesh16 mesh;
    mesh.vertices = v; mesh.indices = idx16;
    mesh.vertex_count = 4; mesh.face_count = 2;
    for (f = 0; f < 6; ++f) {
        int k;
        for (k = 0; k < 4; ++k) {
            int32_t rx, ry, rz;
            const int32_t* c = g_corners[g_quads[f][k]];
            rotate_point(c[0], c[1], c[2], cy, sy, cp, sp, &rx, &ry, &rz);
            v[k].position.x = rx; v[k].position.y = ry; v[k].position.z = rz;
            /* full-texture UV per face corner */
            v[k].u_q8 = (k == 0 || k == 3) ? 0 : 7 * 256;
            v[k].v_q8 = (k < 2) ? 0 : 7 * 256;
        }
        /* baked object-space light for this face */
        il[0] = g_face_illum[f]; il[1] = g_face_illum[f];
        mesh.illumination = il;
        vxpe_soft3d_mesh16(&g_target, &g_cam, &mesh, &g_tex, &g_mat, NULL);
    }
    (void)fb;
}

static void draw_hud(uint16_t* fb) {
    int i;
    /* title blocks */
    bar(fb, 8, 6, 30, 4, vxpe2d_rgb565(90, 200, 250));
    bar(fb, 42, 6, 30, 4, vxpe2d_rgb565(255, 210, 80));
    bar(fb, 76, 6, 14, 4, vxpe2d_rgb565(235, 90, 90));
    /* fps bar: fps/30 of 100px */
    int w = g_fps * 100 / 30;
    if (w > 100) w = 100;
    bar(fb, 8, 14, 100, 3, vxpe2d_rgb565(20, 26, 40));
    bar(fb, 8, 14, w, 3, vxpe2d_rgb565(110, 230, 140));
    /* spin indicator */
    for (i = 0; i < 8; ++i) {
        int on = g_auto ? ((g_tick / 4 + i) & 7) == 0 : (i == 0);
        bar(fb, 120 + i * 12, 6, 8, 8,
            on ? vxpe2d_rgb565(255, 210, 80) : vxpe2d_rgb565(50, 56, 74));
    }
}

static void draw(void) {
    VMUINT16* fb = framebuffer();
    if (!fb) return;
    g_target.pixels = fb;
    g_target.depth = g_depth;
    g_target.width = SW; g_target.height = SH;
    vxpe_soft3d_clear(&g_target, vxpe2d_rgb565(8, 12, 22));
    draw_cube(fb);
    draw_hud(fb);
    vm_graphic_flush_layer(&g_layer, 1);
}

static void tick(VMINT tid) {
    uint32_t now;
    (void)tid;
    g_tick++;
    g_frames++;
    if (g_auto) {
        g_yaw++;
        /* gentle pitch wobble: triangle wave +/-24 */
        {
            uint8_t ph = (uint8_t)((g_tick >> 1) & 127);
            int wob = (ph < 64) ? (int)ph - 32 : 96 - (int)ph;
            g_pitch = (uint8_t)(wob * 24 / 32);
        }
    }
    if (g_left) g_yaw -= 3;
    if (g_right) g_yaw += 3;
    if (g_up) g_pitch += 2;
    if (g_down) g_pitch -= 2;
    now = (uint32_t)vm_get_tick_count();
    if (now - g_fps_mark >= 1000) {
        g_fps = g_frames * 1000 / (int)(now - g_fps_mark ? now - g_fps_mark : 1);
        if (g_fps > 99) g_fps = 99;
        g_frames = 0;
        g_fps_mark = now;
    }
    draw();
}

static void start(void) {
    if (g_layer < 0)
        g_layer = vm_graphic_create_layer(0, 0, SW, SH, -1);
    build_sin();
    build_assets();
    vxpe_soft3d_camera_init(&g_cam, SW, SH);
    vxpe_soft3d_material_init(&g_mat, vxpe2d_rgb565(220, 228, 240));
    g_mat.fog_near_z = 170; g_mat.fog_far_z = 420;
    g_mat.fog565 = vxpe2d_rgb565(8, 12, 22);
    vxpe_soft3d_light_init(&g_light);
    g_light.ambient = 110; /* readable side faces on dim MRE screens */
    bake_light();
    g_fps_mark = (uint32_t)vm_get_tick_count();
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
        if (keycode == VM_KEY_OK || keycode == VM_KEY_NUM5) g_auto = !g_auto;
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
