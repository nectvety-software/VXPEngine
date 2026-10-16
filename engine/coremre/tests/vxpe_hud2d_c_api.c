/*
 * The HUD has to be reachable from the C project template: this file is
 * compiled as C99 and drives every widget with designated initialisers and
 * plain calls, so a game written in C never links a C++ symbol for its status
 * layer. Kept deliberately short - the pixel-exact behaviour is covered by
 * vxpe_hud2d_regression.cpp, this is the language-binding gate.
 */
#include "action2d/VxpHud2D.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

#define W 240
#define H 320

static uint16_t fb[W * H];
static uint16_t heart_px[8 * 8];
static uint16_t face_px[16 * 16];

/* Field names are part of the contract a main.c reads, so the gauge and the
 * icon row are built here the way a C game would build them at file scope. */
static VxpeHudGauge2D hp = {
    .x = 34, .y = 6, .w = 100, .h = 8,
    .max_value = 100, .value = 60, .ghost = 100,
    .color_full = 0xB26Au, .color_low = 0xD924u, .color_ghost = 0x6030u,
    .color_bg = 0x1032u, .color_frame = 0x6DB8u,
    .ghost_rate_q8 = 51200, .segments = 0, .gap_px = 2,
    .low_at = 25, .flash_ms = 0, .mirror = 0, .ghost_acc = 0
};

static const VxpeHudPlate2D slate = {
    .frame = 0x1022u, .bevel_hi = 0x8C71u, .bevel_lo = 0x2105u, .inner = 0x0842u,
    .border_px = 1, .bevel_px = 1
};

int main(void) {
    VxpeSprite565 heart, face;
    VxpeHudIconRow2D hearts = { 0 };
    VxpeHudBossPlate2D boss;
    VxpeHudMinimap2D map;
    VxpeHudPlate2D plate;
    VxpeFontStyle style;
    VxpeRectI rect;
    static const uint8_t rooms[6] = { 1, 1, 1, 1, 0, 1 };
    static const uint8_t tags[6] = { 0, 0, 0, VXPE_MM_SAVE, 0, VXPE_MM_BOSS };
    char buf[16];
    int i;

    /* --- plate + portrait ------------------------------------------------ */
    vxpe_hud_plate_default(&plate);
    rect.x = 4; rect.y = 4; rect.w = 20; rect.h = 20;
    vxpe_hud_plate_draw(fb, W, H, rect, &plate);
    vxpe_hud_plate_draw(fb, W, H, rect, &slate);
    assert(fb[4 * W + 4] == slate.frame);

    memset(face_px, 0, sizeof(face_px));
    for (i = 0; i < 16 * 16; ++i) face_px[i] = 0x7BEFu;
    memset(&face, 0, sizeof(face));
    face.pixels = face_px; face.width = 16; face.height = 16;
    face.stride = 16; face.opaque = 1;
    vxpe_hud_portrait_draw(fb, W, H, rect, &face, &plate, 0xFFFFu, 0);
    assert(fb[10 * W + 10] == 0x7BEFu);

    /* --- gauge ----------------------------------------------------------- */
    vxpe_hud_gauge_init(&hp, 34, 6, 100, 8, 100);
    hp.ghost_rate_q8 = 2560; /* 10 units/s, so the ghost outlives the loop below */
    vxpe_hud_gauge_set(&hp, 60);
    assert(hp.ghost == 100 && hp.value == 60);
    vxpe_hud_gauge_flash(&hp, 80);
    for (i = 0; i < 10; ++i) vxpe_hud_gauge_update(&hp, 33);
    assert(hp.flash_ms == 0 && hp.ghost < 100 && hp.ghost > hp.value);
    vxpe_hud_gauge_set(&hp, 10);
    assert(vxpe_hud_gauge_is_low(&hp));
    vxpe_hud_gauge_draw(fb, W, H, &hp);

    /* --- icon row -------------------------------------------------------- */
    for (i = 0; i < 8 * 8; ++i) heart_px[i] = 0xF800u;
    memset(&heart, 0, sizeof(heart));
    heart.pixels = heart_px; heart.width = 8; heart.height = 8;
    heart.stride = 8; heart.opaque = 1;
    vxpe_hud_icon_row_init(&hearts, &heart, 0, 34, 18, 10);
    hearts.color_empty = 0x4208u; /* no empty art: the tinted path */
    hearts.per_row = 5;
    vxpe_hud_icon_row_set(&hearts, 7);
    assert(vxpe_hud_icon_row_draw(fb, W, H, &hearts) == 10);

    /* --- boss plate ------------------------------------------------------ */
    vxpe_hud_boss_init(&boss, W, H, 500);
    vxpe_hud_boss_show(&boss, "COUNTRESS VAMIRA", 500);
    for (i = 0; i < 20; ++i) vxpe_hud_boss_update(&boss, 33);
    assert(boss.state == 2);
    vxpe_hud_boss_set_hp(&boss, 320);
    vxpe_font_style_default(&style);
    vxpe_hud_boss_draw(fb, W, H, &boss, &style);
    vxpe_hud_boss_hide(&boss);
    for (i = 0; i < 400; ++i) vxpe_hud_boss_update(&boss, 33);
    assert(boss.state == 0);

    /* --- minimap --------------------------------------------------------- */
    vxpe_hud_minimap_init(&map, rooms, tags, 3, 2, 6, 200, 240);
    assert(map.visited[0] == 0);
    vxpe_hud_minimap_mark(&map, 0, 0);
    vxpe_hud_minimap_mark(&map, 2, 1);
    assert(vxpe_hud_minimap_seen(&map, 2, 1) && !vxpe_hud_minimap_seen(&map, 1, 0));
    vxpe_hud_minimap_draw(fb, W, H, &map, 2, 1);

    /* --- text ------------------------------------------------------------ */
    vxpe_font_style_default(&style);
    rect.x = 0; rect.y = 0; rect.w = W; rect.h = H;
    vxpe_hud_text_center(fb, W, H, 120, 300, "GAME OVER", &style);
    vxpe_hud_text_right(fb, W, H, 236, 312, "9", &style);
    assert(vxpe_hud_format_int(buf, sizeof(buf), -1234, 6) == 7);
    assert(strcmp(buf, "-001234") == 0);
    assert(vxpe_hud_format_int(buf, 3, 9999, 1) == 2);

    printf("hud2d C API ok\n");
    return 0;
}
