/*
 * Regression coverage for the action2d core: the identity-scale blit fast path,
 * tilemap rendering and queries, the follow camera, and the platformer body.
 * Deterministic throughout - the camera shake seeds its own xorshift and every
 * body test steps a fixed dt, so a run never depends on host timing.
 */
#include "action2d/VxpTilemap2D.h"
#include "action2d/VxpCamera2D.h"
#include "action2d/VxpBody2D.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

#define FB_W 240
#define FB_H 320
#define TILE 16
#define MAP_W 20
#define MAP_H 15
#define ATLAS_COLS 4
#define ATLAS_ROWS 2

static uint16_t g_fb[FB_W * FB_H];
static uint16_t g_ref[FB_W * FB_H];

/* Atlas cell k (row-major) is filled with 10+k, except cell 2, which is split
 * left/right so a flip is observable. */
static uint16_t make_atlas(uint16_t* px) {
    for (int row = 0; row < ATLAS_ROWS; ++row) {
        for (int col = 0; col < ATLAS_COLS; ++col) {
            const int cell = row * ATLAS_COLS + col;
            for (int y = 0; y < TILE; ++y) {
                for (int x = 0; x < TILE; ++x) {
                    uint16_t v = (uint16_t)(10 + cell);
                    if (cell == 2) v = (uint16_t)(x < TILE / 2 ? 200 : 201);
                    px[(row * TILE + y) * (ATLAS_COLS * TILE) + col * TILE + x] = v;
                }
            }
        }
    }
    return (uint16_t)(ATLAS_COLS * TILE);
}

static uint16_t g_atlas_px[ATLAS_COLS * TILE * ATLAS_ROWS * TILE];
static uint16_t g_cells[MAP_W * MAP_H];
static uint16_t g_flags[MAP_W * MAP_H];
static VxpeSprite565 g_atlas;

static void set_tile(int tx, int ty, uint16_t cell, uint16_t flags) {
    g_cells[ty * MAP_W + tx] = cell;
    g_flags[ty * MAP_W + tx] = flags;
}

/* Static storage: the map struct only ever holds a pointer to the atlas
 * sprite, so a local one would dangle the moment make_map returned. */
static VxpeTilemap2D make_map(void) {
    VxpeTilemap2D map;
    memset(&map, 0, sizeof(map));
    memset(&g_atlas, 0, sizeof(g_atlas));
    g_atlas.pixels = g_atlas_px;
    g_atlas.mask = NULL;
    g_atlas.width = ATLAS_COLS * TILE;
    g_atlas.height = ATLAS_ROWS * TILE;
    g_atlas.stride = make_atlas(g_atlas_px);
    g_atlas.opaque = 1;
    map.cells = g_cells;
    map.flags = g_flags;
    map.atlas = &g_atlas;
    map.width = MAP_W;
    map.height = MAP_H;
    map.tile_w = TILE;
    map.tile_h = TILE;
    map.atlas_cols = ATLAS_COLS;
    map.oob_blocks = 1;
    return map;
}

/* World is 320x240 px of tiles; a solid floor sits on `floor_ty` with two rows
 * of fill below it and nothing above. */
static void build_ground(int floor_ty) {
    memset(g_cells, 0, sizeof(g_cells));
    memset(g_flags, 0, sizeof(g_flags));
    for (int tx = 0; tx < MAP_W; ++tx) set_tile(tx, floor_ty, 1, VXPE_TF_SOLID);
    for (int ty = floor_ty + 1; ty < MAP_H; ++ty)
        for (int tx = 0; tx < MAP_W; ++tx) set_tile(tx, ty, 3, VXPE_TF_SOLID);
}

static int px_at(int x, int y) { return g_fb[y * FB_W + x]; }

/* --- blit fast path must equal the generic resampling path ---------------- */

#define BS_W 8
#define BS_H 6
static uint16_t g_bs_px[BS_W * BS_H];
static uint8_t g_bs_mask[(BS_W * BS_H + 7) / 8];

static void make_blit_source(void) {
    for (int i = 0; i < BS_W * BS_H; ++i) g_bs_px[i] = (uint16_t)(i * 7u + 1u);
    memset(g_bs_mask, 0, sizeof(g_bs_mask));
    for (int y = 0; y < BS_H; ++y) {
        for (int x = 0; x < BS_W; ++x) {
            const int b = y * BS_W + x;
            const int hidden = (x == 2 && y == 1) || (x == 5 && y == 3) || (x == 0 && y == 5);
            if (!hidden) g_bs_mask[b >> 3] = (uint8_t)(g_bs_mask[b >> 3] | (0x80u >> (b & 7)));
        }
    }
}

/* The documented generic mapping: normalise the destination pixel inside the
 * blit rect, flip in destination space, divide back into the source rect. At
 * 1:1 the divides collapse to the identity, which is exactly what the fast path
 * hard-codes, so the two must agree pixel for pixel. COPY + alpha 255 makes the
 * store equal to the tinted source, so no blend arithmetic is duplicated here.
 */
static void ref_blit_1to1(uint16_t* fb, const VxpeSprite565* sp, const VxpeBlit565* op) {
    for (int dy = 0; dy < FB_H; ++dy) {
        for (int dx = 0; dx < FB_W; ++dx) {
            const int lx = dx - op->dst_x;
            const int ly = dy - op->dst_y;
            if (lx < 0 || ly < 0 || lx >= op->dst_w || ly >= op->dst_h) continue;
            if (op->clip_w && op->clip_h) {
                if (dx < op->clip_x || dy < op->clip_y) continue;
                if (dx >= op->clip_x + op->clip_w || dy >= op->clip_y + op->clip_h) continue;
            }
            int ux = lx, uy = ly;
            if (op->flip_y) uy = op->dst_h - 1 - uy;
            if (op->flip_x) ux = op->dst_w - 1 - ux;
            const int sx = op->src.x + (ux * op->src.w) / op->dst_w;
            const int sy = op->src.y + (uy * op->src.h) / op->dst_h;
            const int bit = sy * sp->width + sx;
            if (!sp->opaque && !(g_bs_mask[bit >> 3] & (0x80u >> (bit & 7)))) continue;
            fb[dy * FB_W + dx] = vxpe2d_tint565(sp->pixels[sy * sp->stride + sx], op->tint565);
        }
    }
}

static void blit_case(const VxpeSprite565* sp, int sx, int sy, int sw, int sh,
                      int dx, int dy, uint16_t tint,
                      int flip_x, int flip_y, int clip) {
    VxpeBlit565 op;
    memset(&op, 0, sizeof(op));
    op.src.x = (int16_t)sx; op.src.y = (int16_t)sy;
    op.src.w = (int16_t)sw; op.src.h = (int16_t)sh;
    op.dst_x = (int16_t)dx; op.dst_y = (int16_t)dy;
    op.dst_w = (uint16_t)sw; op.dst_h = (uint16_t)sh;
    op.tint565 = tint; op.alpha = 255; op.blend = VXPE_BLEND_COPY;
    op.flip_x = (uint8_t)flip_x; op.flip_y = (uint8_t)flip_y;
    if (clip) { op.clip_x = 2; op.clip_y = 2; op.clip_w = 4; op.clip_h = 4; }

    memset(g_fb, 0, sizeof(g_fb));
    memset(g_ref, 0, sizeof(g_ref));
    vxpe2d_blit(g_fb, FB_W, FB_H, sp, &op);
    ref_blit_1to1(g_ref, sp, &op);
    assert(memcmp(g_fb, g_ref, sizeof(g_fb)) == 0);
}

static void test_blit_identity(void) {
    make_blit_source();
    VxpeSprite565 sp;
    memset(&sp, 0, sizeof(sp));
    sp.pixels = g_bs_px;
    sp.mask = g_bs_mask;
    sp.width = BS_W;
    sp.height = BS_H;
    sp.stride = BS_W;
    sp.opaque = 0;

    blit_case(&sp, 0, 0, BS_W, BS_H, 10, 20, 0xFFFF, 0, 0, 0);
    blit_case(&sp, 0, 0, BS_W, BS_H, 10, 20, 0x7BEF, 1, 0, 0);
    blit_case(&sp, 0, 0, BS_W, BS_H, 10, 20, 0xFFFF, 0, 1, 0);
    blit_case(&sp, 0, 0, BS_W, BS_H, 10, 20, 0xF81F, 1, 1, 0);
    blit_case(&sp, 2, 1, 4, 3, 30, 40, 0xFFFF, 0, 0, 0);
    blit_case(&sp, 2, 1, 4, 3, 2, 2, 0xFFE0, 1, 1, 0);
    /* Clipped, and pushed off every edge of the framebuffer. */
    blit_case(&sp, 0, 0, BS_W, BS_H, 3, 3, 0xFFFF, 0, 0, 1);
    blit_case(&sp, 0, 0, BS_W, BS_H, -3, -2, 0xFFFF, 0, 0, 0);
    blit_case(&sp, 0, 0, BS_W, BS_H, FB_W - 3, FB_H - 2, 0xFFFF, 1, 1, 0);
    blit_case(&sp, 0, 0, BS_W, BS_H, 100, 100, 0xFFFF, 0, 0, 1);

    /* A non-identity scale still renders through the generic path. */
    memset(g_fb, 0, sizeof(g_fb));
    VxpeBlit565 up;
    memset(&up, 0, sizeof(up));
    up.src.x = 0; up.src.y = 0; up.src.w = BS_W; up.src.h = BS_H;
    up.dst_x = 4; up.dst_y = 4; up.dst_w = BS_W * 2; up.dst_h = BS_H * 2;
    up.tint565 = 0xFFFF; up.alpha = 255; up.blend = VXPE_BLEND_COPY;
    vxpe2d_blit(g_fb, FB_W, FB_H, &sp, &up);
    assert(px_at(4, 4) == g_bs_px[0]);       /* (0,0) hidden by the mask? no: visible */
    assert(px_at(5, 4) == g_bs_px[0]);       /* 2x block duplicate */
    assert(px_at(4, 20) == 0);               /* past dst_h */

    /* The plain memcpy branch must not run past the clip rect. */
    VxpeSprite565 solid;
    memset(&solid, 0, sizeof(solid));
    solid.pixels = g_bs_px;
    solid.width = BS_W; solid.height = BS_H; solid.stride = BS_W; solid.opaque = 1;
    memset(g_fb, 0, sizeof(g_fb));
    VxpeBlit565 cl;
    memset(&cl, 0, sizeof(cl));
    cl.src.x = 0; cl.src.y = 0; cl.src.w = BS_W; cl.src.h = BS_H;
    cl.dst_x = 0; cl.dst_y = 0; cl.dst_w = BS_W; cl.dst_h = BS_H;
    cl.tint565 = 0xFFFF; cl.alpha = 255; cl.blend = VXPE_BLEND_COPY;
    cl.clip_x = 0; cl.clip_y = 0; cl.clip_w = 4; cl.clip_h = 2;
    vxpe2d_blit(g_fb, FB_W, FB_H, &solid, &cl);
    for (int y = 0; y < 2; ++y)
        for (int x = 0; x < 4; ++x) assert(px_at(x, y) == g_bs_px[y * BS_W + x]);
    assert(px_at(4, 0) == 0 && px_at(0, 2) == 0);
    printf("blit identity ok\n");
}

/* --- tilemap ------------------------------------------------------------- */

static void test_tilemap(void) {
    const VxpeTilemap2D map = make_map();
    build_ground(12);
    memset(g_fb, 0, sizeof(g_fb));

    VxpeTileDraw2D view;
    vxpe_tile_view(&view, 0, 0);
    /* The window is 240x320 px: 15 tile columns of the 20-column map, and rows
     * 12..14 (the floor plus two fill rows) are the only non-blank ones. */
    const int visible_cols = FB_W / TILE;
    assert(vxpe_tilemap_draw(g_fb, FB_W, FB_H, &map, &view) == visible_cols * 3);
    assert(px_at(8, 12 * TILE + 8) == 11);   /* cell 1 -> 10+1 */
    assert(px_at(8, 13 * TILE + 8) == 13);   /* cell 3 -> 10+3 */
    assert(px_at(8, 4 * TILE + 8) == 0);     /* blank cells untouched */

    /* Scrolling by three columns shifts the layer and keeps exactly one window
     * worth of columns visible. */
    memset(g_fb, 0, sizeof(g_fb));
    vxpe_tile_view(&view, -TILE * 3, 0);
    assert(vxpe_tilemap_draw(g_fb, FB_W, FB_H, &map, &view) == visible_cols * 3);
    assert(px_at(0, 12 * TILE + 8) == 11);
    assert(px_at(FB_W - 1, 12 * TILE + 8) == 11);

    /* A map row scrolled wholly off the top draws nothing and counts nothing. */
    memset(g_fb, 0, sizeof(g_fb));
    vxpe_tile_view(&view, 0, -(MAP_H + 2) * TILE);
    assert(vxpe_tilemap_draw(g_fb, FB_W, FB_H, &map, &view) == 0);

    /* Per-tile flip reaches the blitter: cell 2 is split 200/201 left/right. */
    memset(g_cells, 0, sizeof(g_cells));
    memset(g_flags, 0, sizeof(g_flags));
    set_tile(0, 0, 2, VXPE_TF_FLIP_X);
    set_tile(1, 0, 2, 0);
    memset(g_fb, 0, sizeof(g_fb));
    vxpe_tile_view(&view, 0, 0);
    assert(vxpe_tilemap_draw(g_fb, FB_W, FB_H, &map, &view) == 2);
    assert(px_at(0, 8) == 201 && px_at(TILE - 1, 8) == 200);
    assert(px_at(TILE, 8) == 200 && px_at(2 * TILE - 1, 8) == 201);

    /* Clip window: only the clipped tile changes, and only inside the rect. */
    memset(g_cells, 0, sizeof(g_cells));
    memset(g_flags, 0, sizeof(g_flags));
    for (int ty = 0; ty < MAP_H; ++ty)
        for (int tx = 0; tx < MAP_W; ++tx) set_tile(tx, ty, 5, 0);
    memset(g_fb, 0, sizeof(g_fb));
    vxpe_tile_view(&view, 0, 0);
    view.clip_x = 32; view.clip_y = 64; view.clip_w = 16; view.clip_h = 16;
    assert(vxpe_tilemap_draw(g_fb, FB_W, FB_H, &map, &view) == 1);
    assert(px_at(32, 64) == 15 && px_at(47, 79) == 15);
    assert(px_at(31, 64) == 0 && px_at(48, 64) == 0 && px_at(32, 80) == 0);
    assert(px_at(16, 16) == 0);
    view.clip_w = 0; view.clip_h = 0;

    /* A tinted, half-transparent layer goes through the blitter for every tile
     * instead of the plain copy branch. */
    for (int i = 0; i < FB_W * FB_H; ++i) g_fb[i] = 0x0800u;
    build_ground(12);
    view.tint565 = 0xF81F; view.alpha = 128; view.blend = VXPE_BLEND_ALPHA;
    assert(vxpe_tilemap_draw(g_fb, FB_W, FB_H, &map, &view) == visible_cols * 3);
    assert(px_at(8, 12 * TILE + 8) != 0x0800u);  /* the tile blended over it */
    assert(px_at(8, 4 * TILE + 8) == 0x0800u);   /* blank cells leave the layer */
    view.tint565 = 0; view.alpha = 0; view.blend = VXPE_BLEND_COPY;

    /* Queries. */
    assert(vxpe_tilemap_cell(&map, 4, 12) == 1);
    assert(vxpe_tilemap_cell(&map, -1, 12) == 0);
    assert(vxpe_tilemap_cell(&map, 4, MAP_H) == 0);
    assert(vxpe_tilemap_flags(&map, 4, 12) == VXPE_TF_SOLID);
    assert(vxpe_tilemap_flags(&map, -1, -1) == VXPE_TF_SOLID);  /* oob_blocks */
    VxpeTilemap2D open = map;
    open.oob_blocks = 0;
    assert(vxpe_tilemap_flags(&open, -1, -1) == 0);
    assert(vxpe_tilemap_flags_at_px(&map, 4 * TILE, 12 * TILE) == VXPE_TF_SOLID);
    assert(vxpe_tilemap_flags_at_px(&map, -1, 12 * TILE) == VXPE_TF_SOLID);
    assert(vxpe_tilemap_blocks_at_px(&map, 4 * TILE, 11 * TILE, VXPE_TF_SOLID) == 0);
    assert(vxpe_tilemap_blocks_at_px(&map, 4 * TILE, 12 * TILE, 0) == 1);

    set_tile(6, 11, 2, VXPE_TF_HAZARD);
    assert(vxpe_tilemap_rect_flags(&map, 6 * TILE, 11 * TILE, 7 * TILE, 12 * TILE)
           == VXPE_TF_HAZARD);
    assert(vxpe_tilemap_rect_flags(&map, 6 * TILE, 11 * TILE, 7 * TILE, 12 * TILE + 8)
           == (VXPE_TF_HAZARD | VXPE_TF_SOLID));

    /* Slope surfaces: UP_R starts at the tile bottom and rises to its top. */
    memset(g_cells, 0, sizeof(g_cells));
    memset(g_flags, 0, sizeof(g_flags));
    set_tile(3, 5, 2, VXPE_TF_SLOPE_UP_R);
    set_tile(4, 5, 2, VXPE_TF_SLOPE_UP_L);
    assert(vxpe_tilemap_floor_y(&map, 3, 5, 0) == 6 * TILE);
    assert(vxpe_tilemap_floor_y(&map, 3, 5, TILE - 1) == 5 * TILE + 1);
    assert(vxpe_tilemap_floor_y(&map, 4, 5, 0) == 5 * TILE + 1);
    assert(vxpe_tilemap_floor_y(&map, 4, 5, TILE - 1) == 6 * TILE);
    assert(vxpe_tilemap_floor_y(&map, 0, 0, 4) == TILE);  /* plain tile: bottom */

    /* Garbage input must not draw or crash. */
    memset(g_fb, 0, sizeof(g_fb));
    VxpeTilemap2D broken = map;
    broken.cells = NULL;
    vxpe_tile_view(&view, 0, 0);
    assert(vxpe_tilemap_draw(g_fb, FB_W, FB_H, &broken, &view) == 0);
    broken = map;
    broken.tile_w = 0;
    assert(vxpe_tilemap_draw(g_fb, FB_W, FB_H, &broken, &view) == 0);
    printf("tilemap ok\n");
}

/* --- camera -------------------------------------------------------------- */

#define CAM_WORLD_W 640
#define CAM_WORLD_H 480

static void test_camera(void) {
    VxpeCamera2D cam;
    vxpe_cam_init(&cam, FB_W, FB_H, CAM_WORLD_W, CAM_WORLD_H);
    assert(cam.view_w == FB_W && cam.view_h == FB_H);
    assert(cam.min_x_q8 == 0 && cam.min_y_q8 == 0);
    assert(cam.max_x_q8 == (CAM_WORLD_W - FB_W) * 256);
    assert(cam.max_y_q8 == (CAM_WORLD_H - FB_H) * 256);

    /* Snap frames the target in the middle of the viewport. */
    vxpe_cam_snap(&cam, FB_W / 2, FB_H / 2);
    assert(vxpe_cam_x(&cam) == 0 && vxpe_cam_y(&cam) == 0);
    vxpe_cam_snap(&cam, 9999, 9999);
    assert(vxpe_cam_x(&cam) == CAM_WORLD_W - FB_W);
    assert(vxpe_cam_y(&cam) == CAM_WORLD_H - FB_H);
    vxpe_cam_snap(&cam, -9999, -9999);
    assert(vxpe_cam_x(&cam) == 0 && vxpe_cam_y(&cam) == 0);

    /* A world smaller than the viewport centres instead of jittering between an
     * inverted clamp window. */
    vxpe_cam_init(&cam, FB_W, FB_H, 200, 250);
    vxpe_cam_snap(&cam, 0, 0);
    assert(vxpe_cam_x(&cam) == (200 - FB_W) / 2);
    assert(vxpe_cam_y(&cam) == (250 - FB_H) / 2);

    /* Inside the deadzone the viewport must not move at all. */
    vxpe_cam_init(&cam, FB_W, FB_H, CAM_WORLD_W, CAM_WORLD_H);
    vxpe_cam_snap(&cam, CAM_WORLD_W / 2, CAM_WORLD_H / 2);
    const int x0 = vxpe_cam_x(&cam), y0 = vxpe_cam_y(&cam);
    assert(x0 == CAM_WORLD_W / 2 - FB_W / 2);
    for (int i = 0; i < 20; ++i) {
        vxpe_cam_follow(&cam, CAM_WORLD_W / 2 + i, CAM_WORLD_H / 2, 33);
        vxpe_cam_update(&cam, 33);
    }
    assert(vxpe_cam_x(&cam) == x0 && vxpe_cam_y(&cam) == y0);

    /* Tracking a long run: monotonic, never outside the world, and it settles
     * on the edge. */
    int prev = vxpe_cam_x(&cam);
    for (int i = 0; i < 600; ++i) {
        vxpe_cam_follow(&cam, CAM_WORLD_W / 2 + i * 4, CAM_WORLD_H / 2, 33);
        vxpe_cam_update(&cam, 33);
        const int cx = vxpe_cam_x(&cam);
        assert(cx >= prev);
        prev = cx;
        assert(cx >= 0 && cx <= CAM_WORLD_W - FB_W);
    }
    assert(vxpe_cam_x(&cam) == CAM_WORLD_W - FB_W);

    /* follow_ms == 0 snaps the viewport to the deadzone edge. */
    vxpe_cam_init(&cam, FB_W, FB_H, CAM_WORLD_W, CAM_WORLD_H);
    vxpe_cam_set_follow_ms(&cam, 0);
    vxpe_cam_follow(&cam, CAM_WORLD_W - 10, 10, 33);
    assert(vxpe_cam_x(&cam) == CAM_WORLD_W - FB_W);
    assert(vxpe_cam_y(&cam) == 0);

    /* Lookahead slides the view in the running direction. */
    vxpe_cam_init(&cam, FB_W, FB_H, 4000, 4000);
    vxpe_cam_set_lookahead(&cam, 0);
    for (int i = 0; i < 300; ++i) {
        vxpe_cam_follow(&cam, 2000, 2000, 33);
        vxpe_cam_update(&cam, 33);
    }
    const int base = vxpe_cam_x(&cam);
    vxpe_cam_set_lookahead(&cam, 40);
    for (int i = 0; i < 600; ++i) {
        vxpe_cam_follow(&cam, 2000, 2000, 33);
        vxpe_cam_update(&cam, 33);
    }
    assert(vxpe_cam_x(&cam) == base + 40);

    /* Shake stays inside its amplitude, dies on schedule and is reproducible. */
    vxpe_cam_init(&cam, FB_W, FB_H, 4000, 4000);
    vxpe_cam_snap(&cam, 2000, 2000);
    const int rest_x = vxpe_cam_x(&cam);
    const int rest_y = vxpe_cam_y(&cam);
    vxpe_cam_shake(&cam, 5, 200);
    assert(vxpe_cam_shaking(&cam));
    int max_off = 0;
    for (int i = 0; i < 5; ++i) {
        vxpe_cam_update(&cam, 33);
        int off = vxpe_cam_x(&cam) - rest_x;
        if (off < 0) off = -off;
        assert(off <= 5);
        assert(vxpe_cam_y(&cam) >= rest_y - 3 && vxpe_cam_y(&cam) <= rest_y + 3);
        if (off > max_off) max_off = off;
    }
    assert(max_off > 0);
    for (int i = 0; i < 6; ++i) vxpe_cam_update(&cam, 33);
    assert(!vxpe_cam_shaking(&cam));
    assert(vxpe_cam_x(&cam) == rest_x && vxpe_cam_y(&cam) == rest_y);
    /* An expired shake is a no-op, not a drift source. */
    vxpe_cam_update(&cam, 33);
    assert(vxpe_cam_x(&cam) == rest_x && cam.shake_x_q8 == 0);

    VxpeCamera2D a, b;
    vxpe_cam_init(&a, FB_W, FB_H, 4000, 4000);
    vxpe_cam_init(&b, FB_W, FB_H, 4000, 4000);
    vxpe_cam_snap(&a, 2000, 2000);
    vxpe_cam_snap(&b, 2000, 2000);
    vxpe_cam_shake(&a, 6, 300);
    vxpe_cam_shake(&b, 6, 300);
    for (int i = 0; i < 5; ++i) {
        vxpe_cam_update(&a, 30);
        vxpe_cam_update(&b, 30);
        assert(a.shake_x_q8 == b.shake_x_q8 && a.shake_y_q8 == b.shake_y_q8);
        assert(a.seed == b.seed);
    }

    /* A repeat request keeps the stronger amplitude and the longer duration. */
    vxpe_cam_shake(&a, 2, 50);
    assert(a.shake_amp_q8 == 6 * 256 && a.shake_ms == 300);
    vxpe_cam_shake(&a, 9, 100);
    assert(a.shake_amp_q8 == 9 * 256 && a.shake_ms == 300);
    vxpe_cam_shake(&a, 0, 500);
    assert(a.shake_amp_q8 == 9 * 256);

    assert(vxpe_cam_to_screen_x(&b, vxpe_cam_x(&b) + 7) == 7);
    assert(vxpe_cam_to_screen_y(&b, vxpe_cam_y(&b)) == 0);
    /* `cam` is the settled one: same rest position, shake already expired. */
    assert(vxpe_cam_visible(&cam, rest_x - 1, rest_y, 2, 2) == 1);
    assert(vxpe_cam_visible(&cam, rest_x + FB_W + 4, rest_y, 8, 8) == 0);
    assert(vxpe_cam_visible(&cam, rest_x - 2, rest_y - 2, 4, 4) == 1);
    assert(vxpe_cam_visible(&cam, rest_x, rest_y + FB_H, 4, 4) == 0);
    printf("camera ok\n");
}

/* --- body ---------------------------------------------------------------- */

static VxpeTilemap2D g_body_map;

static void body_world(void) {
    g_body_map = make_map();
    build_ground(12);
}

/* Drive `frames` steps of the controller. `jump_frames` presses the button for
 * that many frames (0 = never), `held_frames` keeps it down that long. */
static void drive(VxpeBody2D* b, const VxpeBodyTuning2D* t, int dx, int dy,
                  int jump_frames, int held_frames, int frames, uint16_t dt) {
    VxpeBodyIntent2D in;
    for (int i = 0; i < frames; ++i) {
        in.x = (int8_t)dx;
        in.y = (int8_t)dy;
        in.jump = (uint8_t)(i < jump_frames ? 1 : 0);
        in.jump_held = (uint8_t)(i < held_frames ? 1 : 0);
        vxpe_body_control(b, &g_body_map, t, &in, dt);
    }
}

static void idle_frames(VxpeBody2D* b, const VxpeBodyTuning2D* t, int frames, uint16_t dt) {
    drive(b, t, 0, 0, 0, 0, frames, dt);
}

static int body_y(const VxpeBody2D* b) { return (int)(b->y_q8 >> 8); }
static int body_x(const VxpeBody2D* b) { return (int)(b->x_q8 >> 8); }
static int feet_y(const VxpeBody2D* b) { return body_y(b) + b->h; }

static void test_body(void) {
    VxpeBodyTuning2D t;
    vxpe_body_tuning_default(&t);
    body_world();

    /* Settle onto the floor and stay put with no intent. */
    VxpeBody2D b;
    vxpe_body_init(&b, 100, 100, 10, 22);
    assert(vxpe_body_settle(&b, &g_body_map));
    assert(feet_y(&b) == 12 * TILE);
    assert(b.on_ground);
    const int rest_y = body_y(&b);
    idle_frames(&b, &t, 120, 33);
    assert(body_y(&b) == rest_y && b.on_ground && b.vy_q8 == 0);
    assert(b.air_ms == 0 && b.coyote_ms == t.coyote_ms);

    /* A settle with no floor under the body reports failure. */
    VxpeTilemap2D empty = g_body_map;
    static uint16_t zero_cells[MAP_W * MAP_H];
    empty.cells = zero_cells;
    empty.flags = zero_cells;
    empty.oob_blocks = 0;
    vxpe_body_init(&b, 100, 100, 10, 22);
    assert(!vxpe_body_settle(&b, &empty));

    /* Run right hits the tuned cap and covers about 92 px in one second. */
    vxpe_body_init(&b, 40, 12 * TILE - 22, 10, 22);
    vxpe_body_settle(&b, &g_body_map);
    const int x_start = body_x(&b);
    drive(&b, &t, 1, 0, 0, 0, 30, 33);
    assert(b.facing == 1);
    const int travelled = body_x(&b) - x_start;
    assert(travelled > 70 && travelled < 120);
    assert(b.on_ground);
    /* Friction stops it again within about a tenth of a second. */
    idle_frames(&b, &t, 10, 33);
    assert(b.vx_q8 == 0);

    /* A wall stops the body flush against the tile edge. */
    for (int ty = 8; ty < 12; ++ty) set_tile(9, ty, 4, VXPE_TF_SOLID);
    vxpe_body_init(&b, 100, 12 * TILE - 22, 10, 22);
    vxpe_body_settle(&b, &g_body_map);
    b.x_q8 = 5 * TILE * 256;
    drive(&b, &t, 1, 0, 0, 0, 90, 33);
    assert(body_x(&b) + b.w == 9 * TILE);
    assert(b.vx_q8 == 0);
    assert(b.on_wall_r);
    /* Facing away from the wall it walks off again. */
    drive(&b, &t, -1, 0, 0, 0, 10, 33);
    assert(body_x(&b) + b.w < 9 * TILE);

    /* Step-up: a one-tile ledge is walked over without jumping. */
    body_world();
    for (int tx = 12; tx < MAP_W; ++tx) set_tile(tx, 11, 4, VXPE_TF_SOLID);
    vxpe_body_init(&b, 10 * TILE, 12 * TILE - 22, 10, 22);
    vxpe_body_settle(&b, &g_body_map);
    drive(&b, &t, 1, 0, 0, 0, 120, 33);
    assert(feet_y(&b) == 11 * TILE);
    assert(b.on_ground);
    assert(body_x(&b) > 13 * TILE);

    /* Jump: a held button clears about two and a half tiles. */
    body_world();
    vxpe_body_init(&b, 100, 12 * TILE - 22, 10, 22);
    vxpe_body_settle(&b, &g_body_map);
    VxpeBodyIntent2D in;
    int apex = feet_y(&b);
    in.x = 0; in.y = 0; in.jump = 1; in.jump_held = 1;
    for (int i = 0; i < 40; ++i) {
        vxpe_body_control(&b, &g_body_map, &t, &in, 33);
        in.jump = 0;
        if (feet_y(&b) < apex) apex = feet_y(&b);
    }
    const int rise = 12 * TILE - apex;
    assert(rise > 30 && rise < 55);
    assert(b.on_ground);          /* it came back down */
    assert(body_x(&b) == 100);    /* no intent, so no drift */

    /* A second press while airborne does not extend the jump. */
    vxpe_body_init(&b, 100, 12 * TILE - 22, 10, 22);
    vxpe_body_settle(&b, &g_body_map);
    drive(&b, &t, 0, 0, 1, 40, 3, 33);
    const int32_t held_vy = b.vy_q8;
    assert(held_vy < 0);
    vxpe_body_init(&b, 100, 12 * TILE - 22, 10, 22);
    vxpe_body_settle(&b, &g_body_map);
    drive(&b, &t, 0, 0, 3, 40, 3, 33);
    assert(b.vy_q8 == held_vy);

    /* A tapped jump is cut short. */
    vxpe_body_init(&b, 100, 12 * TILE - 22, 10, 22);
    vxpe_body_settle(&b, &g_body_map);
    int tap_apex = feet_y(&b);
    in.jump = 1; in.jump_held = 1;
    for (int i = 0; i < 30; ++i) {
        vxpe_body_control(&b, &g_body_map, &t, &in, 33);
        in.jump = 0;
        if (i >= 2) in.jump_held = 0;
        if (feet_y(&b) < tap_apex) tap_apex = feet_y(&b);
    }
    assert(12 * TILE - tap_apex < rise - 10);

    /* Coyote time: walking off a ledge still allows a jump just after. */
    body_world();
    for (int tx = 10; tx < MAP_W; ++tx) {
        set_tile(tx, 12, 0, 0);
        for (int ty = 13; ty < MAP_H; ++ty) set_tile(tx, ty, 0, 0);
    }
    vxpe_body_init(&b, 8 * TILE, 12 * TILE - 22, 10, 22);
    vxpe_body_settle(&b, &g_body_map);
    drive(&b, &t, 1, 0, 0, 0, 12, 33);
    assert(!b.on_ground);
    assert(b.coyote_ms > 0);
    in.x = 1; in.y = 0; in.jump = 1; in.jump_held = 1;
    vxpe_body_control(&b, &g_body_map, &t, &in, 33);
    assert(b.vy_q8 < 0);          /* the grace window paid for the jump */
    in.jump = 0;
    int coyote_apex = feet_y(&b);
    for (int i = 0; i < 30; ++i) {
        vxpe_body_control(&b, &g_body_map, &t, &in, 33);
        if (feet_y(&b) < coyote_apex) coyote_apex = feet_y(&b);
    }
    assert(coyote_apex < 12 * TILE);
    /* Once the window closes the same press is a no-op. */
    vxpe_body_init(&b, 12 * TILE, 12 * TILE - 22, 10, 22);
    b.on_ground = 0;
    b.coyote_ms = 0;
    b.vy_q8 = 20 * 256;
    drive(&b, &t, 0, 0, 1, 20, 1, 33);
    assert(b.vy_q8 > 0);

    /* Jump buffering: a press in the air fires on landing. */
    VxpeBodyTuning2D t2;
    vxpe_body_tuning_default(&t2);
    t2.coyote_ms = 0;             /* isolate the buffer from coyote time */
    body_world();
    vxpe_body_init(&b, 100, 12 * TILE - 22 - 6, 10, 22);
    b.vy_q8 = 90 * 256;           /* two frames from the floor */
    b.on_ground = 0;
    in.x = 0; in.y = 0; in.jump = 1; in.jump_held = 1;
    vxpe_body_control(&b, &g_body_map, &t2, &in, 33);
    assert(b.buffer_ms > 0);
    assert(b.vy_q8 > 0);          /* still falling: nothing fired yet */
    assert(!b.on_ground);
    in.jump = 0;
    int jumped = 0;
    for (int i = 0; i < 6; ++i) {
        vxpe_body_control(&b, &g_body_map, &t2, &in, 33);
        if (b.vy_q8 < 0) jumped = 1;
    }
    assert(jumped);
    /* A press that stays in the buffer past its window is dropped. */
    t2.jump_buffer_ms = 20;
    vxpe_body_init(&b, 100, 12 * TILE - 22 - 30, 10, 22);
    b.vy_q8 = 20 * 256;
    b.on_ground = 0;
    in.jump = 1;
    vxpe_body_control(&b, &g_body_map, &t2, &in, 33);
    in.jump = 0;
    int late_jumped = 0;
    for (int i = 0; i < 20; ++i) {
        vxpe_body_control(&b, &g_body_map, &t2, &in, 33);
        if (b.vy_q8 < 0) late_jumped = 1;
    }
    assert(!late_jumped);

    /* One-way platform: pass upward, land from above, drop through on request. */
    body_world();
    for (int tx = 4; tx < 10; ++tx) set_tile(tx, 9, 2, VXPE_TF_ONEWAY);
    vxpe_body_init(&b, 6 * TILE, 12 * TILE - 22, 10, 22);
    vxpe_body_settle(&b, &g_body_map);
    b.vy_q8 = -300 * 256;
    b.on_ground = 0;
    int up_apex = feet_y(&b);
    for (int i = 0; i < 12; ++i) {
        in.x = 0; in.y = 0; in.jump = 0; in.jump_held = 0;
        vxpe_body_control(&b, &g_body_map, &t, &in, 33);
        if (feet_y(&b) < up_apex) up_apex = feet_y(&b);
    }
    assert(up_apex < 9 * TILE);   /* it rose through the platform */
    assert(!b.on_ceiling);

    /* Falling onto it from above supports the body. */
    vxpe_body_init(&b, 6 * TILE, 6 * TILE, 10, 22);
    b.vy_q8 = 0;
    b.on_ground = 0;
    for (int i = 0; i < 90; ++i) {
        in.x = 0; in.y = 0; in.jump = 0; in.jump_held = 0;
        vxpe_body_control(&b, &g_body_map, &t, &in, 33);
    }
    assert(feet_y(&b) == 9 * TILE && b.on_ground);

    /* Drop-through needs down + jump together. */
    in.x = 0; in.y = -1; in.jump = 1; in.jump_held = 0;
    vxpe_body_control(&b, &g_body_map, &t, &in, 33);
    assert(b.drop_ms == 0);       /* up + jump does not drop */
    assert(b.vy_q8 < 0);          /* it jumped instead */
    b.vy_q8 = 0;
    b.y_q8 = (int32_t)(9 * TILE - 22) << 8;
    b.on_ground = 0;
    idle_frames(&b, &t, 2, 33);
    assert(feet_y(&b) == 9 * TILE && b.on_ground);
    in.x = 0; in.y = 1; in.jump = 1; in.jump_held = 0;
    vxpe_body_control(&b, &g_body_map, &t, &in, 33);
    assert(b.drop_ms > 0 && !b.on_ground);
    for (int i = 0; i < 40; ++i) {
        in.x = 0; in.y = 0; in.jump = 0; in.jump_held = 0;
        vxpe_body_control(&b, &g_body_map, &t, &in, 33);
    }
    assert(feet_y(&b) == 12 * TILE);

    /* No tunnelling: a 200 ms frame at terminal speed still lands on a
     * one-tile floor. */
    body_world();
    for (int tx = 0; tx < MAP_W; ++tx) {
        set_tile(tx, 12, 0, 0);
        for (int ty = 13; ty < MAP_H; ++ty) set_tile(tx, ty, 0, 0);
    }
    for (int tx = 4; tx < 8; ++tx) set_tile(tx, 10, 1, VXPE_TF_SOLID);
    vxpe_body_init(&b, 5 * TILE, 2 * TILE, 10, 22);
    for (int i = 0; i < 6; ++i) vxpe_body_step(&b, &g_body_map, &t, 200);
    assert(feet_y(&b) == 10 * TILE);
    assert(b.on_ground);
    assert(vxpe_body_ground_tile(&b, &g_body_map, NULL, NULL));

    /* A single 45-degree slope tile is walkable and lifts the body. */
    body_world();
    set_tile(6, 11, 2, VXPE_TF_SLOPE_UP_R);
    vxpe_body_init(&b, 4 * TILE, 12 * TILE - 22, 10, 22);
    vxpe_body_settle(&b, &g_body_map);
    int crossed_slope = 0, lifted = 0;
    for (int i = 0; i < 40; ++i) {
        in.x = 1; in.y = 0; in.jump = 0; in.jump_held = 0;
        vxpe_body_control(&b, &g_body_map, &t, &in, 33);
        if (b.on_slope) crossed_slope = 1;
        if (feet_y(&b) < 12 * TILE) lifted = 1;
    }
    assert(body_x(&b) > 7 * TILE); /* the ramp was never a wall */
    assert(crossed_slope && lifted);

    /* Water and hazard flags are reported without changing solidity. */
    body_world();
    for (int tx = 2; tx < 6; ++tx) set_tile(tx, 11, 2, VXPE_TF_WATER);
    set_tile(3, 11, 2, (uint16_t)(VXPE_TF_WATER | VXPE_TF_HAZARD));
    vxpe_body_init(&b, 3 * TILE, 12 * TILE - 22, 10, 22);
    assert(vxpe_body_settle(&b, &g_body_map));
    assert(feet_y(&b) == 12 * TILE);
    assert(vxpe_body_touching(&b, &g_body_map, VXPE_TF_HAZARD));
    assert(vxpe_body_touching(&b, &g_body_map, VXPE_TF_WATER));
    assert(!vxpe_body_touching(&b, &g_body_map, VXPE_TF_TRIGGER));
    idle_frames(&b, &t, 1, 33);
    assert(b.in_water);
    /* Buoyancy: gravity is scaled down in water. */
    const int32_t vy_before = b.vy_q8;
    vxpe_body_step(&b, &g_body_map, &t, 100);
    assert(b.in_water);
    assert(b.vy_q8 - vy_before < 640 * 256 * 100 / 1000);
    /* Swimming caps a hard fall to swim speed. */
    b.vy_q8 = 200 * 256;
    vxpe_body_step(&b, &g_body_map, &t, 100);
    assert(b.vy_q8 <= t.swim_max_q8);

    /* Ladder climb. */
    body_world();
    for (int ty = 0; ty < 12; ++ty) set_tile(8, ty, 2, VXPE_TF_LADDER);
    vxpe_body_init(&b, 8 * TILE + 3, 12 * TILE - 22, 10, 22);
    vxpe_body_settle(&b, &g_body_map);
    drive(&b, &t, 0, -1, 0, 0, 30, 33);
    assert(b.on_ladder);
    assert(body_y(&b) <= 12 * TILE - 22 - 30);
    assert(b.vy_q8 < 0);
    /* Stepping off with jump leaves the ladder and gravity returns. */
    drive(&b, &t, 0, 0, 1, 0, 1, 33);
    assert(!b.on_ladder);
    assert(b.vy_q8 < 0);          /* half-strength ladder dismount */
    drive(&b, &t, 0, 0, 0, 0, 20, 33);
    assert(b.vy_q8 >= 0);

    /* Ground tile reporting. */
    body_world();
    vxpe_body_init(&b, 4 * TILE + 8, 12 * TILE - 22, 10, 22);
    vxpe_body_settle(&b, &g_body_map);
    int tx = -1, ty = -1;
    assert(vxpe_body_ground_tile(&b, &g_body_map, &tx, &ty));
    assert(tx == 4 && ty == 12);
    b.on_ground = 0;
    assert(!vxpe_body_ground_tile(&b, &g_body_map, &tx, &ty));

    /* dt=0, a NULL tuning table and a NULL intent are all no-ops. */
    vxpe_body_init(&b, 100, 100, 10, 22);
    const int32_t y_before = b.y_q8;
    drive(&b, &t, 1, 0, 1, 1, 5, 0);
    assert(b.y_q8 == y_before && b.x_q8 == (int32_t)100 << 8);
    VxpeBodyIntent2D still;
    memset(&still, 0, sizeof(still));
    vxpe_body_control(&b, &g_body_map, NULL, &still, 33);
    vxpe_body_control(&b, &g_body_map, &t, NULL, 33);
    vxpe_body_control(&b, NULL, &t, &still, 33);
    vxpe_body_step(&b, &g_body_map, &t, 0);
    assert(b.y_q8 == y_before);
    printf("body ok\n");
}

int main(void) {
    test_blit_identity();
    test_tilemap();
    test_camera();
    test_body();
    printf("action2d regression passed\n");
    return 0;
}
