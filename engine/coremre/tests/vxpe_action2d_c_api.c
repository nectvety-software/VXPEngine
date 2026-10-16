/* The action2d core is the C template's gameplay layer: every entry point has
 * to compile and work from plain C99, with struct initializers a main.c written
 * for MediaTek MRE can actually use. */
#include "action2d/VxpTilemap2D.h"
#include "action2d/VxpCamera2D.h"
#include "action2d/VxpBody2D.h"

#include <assert.h>
#include <string.h>

#define W 240
#define H 320
#define T 16
#define MW 20
#define MH 15

static uint16_t fb[W * H];
static uint16_t atlas[T * 2 * T * 2];
static uint16_t cells[MW * MH];
static uint16_t flags[MW * MH];

int main(void) {
    int i, tx, ty;
    for (i = 0; i < T * 2 * T * 2; ++i) atlas[i] = 0xF81Fu;

    VxpeSprite565 sheet;
    memset(&sheet, 0, sizeof(sheet));
    sheet.pixels = atlas;
    sheet.width = (uint16_t)(2 * T);
    sheet.height = (uint16_t)(2 * T);
    sheet.stride = (uint16_t)(2 * T);
    sheet.opaque = 1;

    memset(cells, 0, sizeof(cells));
    memset(flags, 0, sizeof(flags));
    for (tx = 0; tx < MW; ++tx) {
        cells[12 * MW + tx] = 1;
        flags[12 * MW + tx] = VXPE_TF_SOLID;
    }
    for (tx = 0; tx < MW; ++tx) cells[3 * MW + tx] = 2;

    VxpeTilemap2D map;
    memset(&map, 0, sizeof(map));
    map.cells = cells;
    map.flags = flags;
    map.atlas = &sheet;
    map.width = MW;
    map.height = MH;
    map.tile_w = T;
    map.tile_h = T;
    map.atlas_cols = 2;
    map.oob_blocks = 1;

    VxpeTileDraw2D view;
    vxpe_tile_view(&view, 0, 0);
    assert(vxpe_tilemap_draw(fb, W, H, &map, &view) == (W / T) * 2);
    assert(fb[(12 * T + 8) * W + 8] == 0xF81Fu);

    VxpeCamera2D cam;
    vxpe_cam_init(&cam, W, H, MW * T, MH * T);
    vxpe_cam_snap(&cam, 100, 100);
    vxpe_cam_set_lookahead(&cam, 24);
    vxpe_cam_follow(&cam, 140, 120, 33);
    vxpe_cam_shake(&cam, 4, 180);
    assert(vxpe_cam_shaking(&cam));
    vxpe_cam_update(&cam, 33);
    VxpeTileDraw2D scrolled;
    vxpe_tile_view(&scrolled, -vxpe_cam_x(&cam), -vxpe_cam_y(&cam));
    assert(vxpe_tilemap_draw(fb, W, H, &map, &scrolled) > 0);

    VxpeBodyTuning2D tuning;
    vxpe_body_tuning_default(&tuning);
    VxpeBody2D body;
    vxpe_body_init(&body, 100, 100, 10, 22);
    assert(vxpe_body_settle(&body, &map));
    assert(body.y_q8 == (int32_t)(12 * T - 22) << 8);

    VxpeBodyIntent2D intent;
    memset(&intent, 0, sizeof(intent));
    intent.x = 1;
    intent.jump = 1;
    intent.jump_held = 1;
    for (i = 0; i < 30; ++i) {
        vxpe_body_control(&body, &map, &tuning, &intent, 33);
        intent.jump = 0;
    }
    assert(body.on_ground);
    assert(body.x_q8 > ((int32_t)100 << 8));
    /* The collision box rests on top of the floor row, it never overlaps it. */
    assert(!vxpe_body_touching(&body, &map, VXPE_TF_SOLID));
    assert(vxpe_body_ground_tile(&body, &map, &tx, &ty));
    assert(ty == 12 && tx >= 0 && tx < MW);

    flags[11 * MW + 6] = VXPE_TF_HAZARD;
    VxpeBody2D spike;
    vxpe_body_init(&spike, 6 * T, 11 * T - 20, 10, 22);
    assert(vxpe_body_touching(&spike, &map, VXPE_TF_HAZARD));
    assert(vxpe_tilemap_rect_flags(&map, 0, 12 * T, T, 13 * T) == VXPE_TF_SOLID);
    return 0;
}
