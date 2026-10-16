/*
 * Proves the sprite-forge bridge at the byte level.
 *
 * tools/vxp_import_sprite_forge.py emits the two headers included here. This
 * file compiles them as C99 (the project template's language) and then reads
 * every pixel back through the real core paths - vxpe2d_blit, vxpe2d_anim_* -
 * so an importer change that breaks mask indexing, stride, the opaque flag or
 * clip timing fails here instead of showing up as a shifted sprite on a phone.
 */
#include "data/sprite_forge/fixture_atlas.h"
#include "data/sprite_forge/fixture_loose.h"
#include "graphics/VxpRender2D.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

#define FB_W 32
#define FB_H 32

/* Not equal to any fixture colour, so a leftover background pixel proves
 * that the core skipped it rather than drew black over it. */
#define BG 0xF81Fu

#define C_K vxpe2d_rgb565(0x1A, 0x1C, 0x2C)
#define C_D vxpe2d_rgb565(0x25, 0x71, 0x79)
#define C_G vxpe2d_rgb565(0x38, 0xB7, 0x64)
#define C_L vxpe2d_rgb565(0xA7, 0xF0, 0x70)
#define C_H vxpe2d_rgb565(0xF4, 0xF4, 0xF4)

static uint16_t fb[FB_W * FB_H];

static int mask_bit(const VxpeSprite565* s, int x, int y)
{
    unsigned bit = (unsigned)y * s->width + (unsigned)x;
    return (s->mask[bit >> 3] & (0x80u >> (bit & 7u))) != 0;
}

static void reset_fb(void)
{
    int i;
    for (i = 0; i < FB_W * FB_H; ++i) fb[i] = BG;
}

/* The fixture hero: 12x10, body, face plate, outline nubs, empty corners. */
static uint16_t hero_expected(int x, int y)
{
    if (x >= 3 && x <= 8 && y >= 2 && y <= 4) return C_H;
    if ((x == 2 || x == 9) && (y == 1 || y == 8)) return C_K;
    if ((x == 1 || x == 10) && (y == 4 || y == 5)) return C_K;
    if (x >= 2 && x <= 9 && y >= 1 && y <= 8) return C_G;
    return BG; /* everything else is transparent */
}

/* The bundle frames share one 8x8 shape; only the fill and the step nubs move. */
static uint16_t frame_expected(int frame, int x, int y, uint16_t bg)
{
    int main_col = (frame == 3) ? C_D : C_G;
    int left_nub = (frame == 1 || frame == 3);
    int right_nub = (frame == 2 || frame == 3);
    if (x == 3 && y == 2) return C_K;
    if (x == 4 && y == 2) return C_K;
    if (x == 1 && y == 6 && left_nub) return C_L;
    if (x == 5 && y == 6 && right_nub) return C_L;
    if (x >= 1 && x <= 6 && y >= 1 && y <= 6) return (uint16_t)main_col;
    return bg;
}

static void blit_cell(const VxpeSprite565* atlas, VxpeRectI src, int dx, int dy)
{
    VxpeBlit565 op;
    memset(&op, 0, sizeof(op));
    op.src = src;
    op.dst_x = (int16_t)dx;
    op.dst_y = (int16_t)dy;
    op.dst_w = (uint16_t)src.w;
    op.dst_h = (uint16_t)src.h;
    op.tint565 = 0xFFFFu;
    op.alpha = 255u;
    op.blend = VXPE_BLEND_COPY;
    vxpe2d_blit(fb, FB_W, FB_H, atlas, &op);
}

static void check_loose(void)
{
    const VxpeSprite565* hero = &ff_loose_sprites[FF_LOOSE_SPR_HERO_MASKED];
    const VxpeSprite565* tile = &ff_loose_sprites[FF_LOOSE_SPR_TILE_OPAQUE];
    int x, y;

    assert(FF_LOOSE_NSPRITE == 2);
    assert(hero->width == 12 && hero->height == 10);
    assert(hero->stride == 12);
    assert(hero->mask != NULL && hero->opaque == 0);
    assert(tile->width == 8 && tile->height == 8 && tile->stride == 8);
    /* A frame with no transparent pixel must be flagged opaque and carry no
     * mask, or vxpe2d_blit pays the per-pixel loop for nothing. */
    assert(tile->mask == NULL && tile->opaque == 1);

    for (y = 0; y < hero->height; ++y) {
        for (x = 0; x < hero->width; ++x) {
            uint16_t want = hero_expected(x, y);
            assert(mask_bit(hero, x, y) == (want != BG));
            if (want == BG) {
                assert(hero->pixels[y * hero->stride + x] == 0);
            } else {
                assert(hero->pixels[y * hero->stride + x] == want);
            }
        }
    }

    reset_fb();
    vxpe2d_blit_simple(fb, FB_W, FB_H, hero, 5, 7);
    for (y = 0; y < hero->height; ++y) {
        for (x = 0; x < hero->width; ++x) {
            uint16_t want = hero_expected(x, y);
            uint16_t got = fb[(7 + y) * FB_W + (5 + x)];
            assert(got == (want == BG ? BG : want));
        }
    }

    reset_fb();
    vxpe2d_blit_simple(fb, FB_W, FB_H, tile, 0, 20);
    assert(fb[20 * FB_W + 0] == C_G);
    assert(fb[20 * FB_W + 7] == C_D);
    assert(fb[27 * FB_W + 0] == C_L);
    assert(fb[27 * FB_W + 7] == C_K);
}

static void check_atlas(void)
{
    VxpeRectI cell;
    int frame, x, y;

    assert(FF_BUNDLE_NFRAME == 4);
    assert(FF_BUNDLE_TILE_W == 8 && FF_BUNDLE_TILE_H == 8);
    assert(ff_bundle_atlas.width == FF_BUNDLE_ATLAS_W);
    /* Atlas cells only stay addressable because stride == width: mask_visible()
     * indexes with width, so the importer must not pad rows. */
    assert(ff_bundle_atlas.stride == ff_bundle_atlas.width);
    assert(ff_bundle_atlas.mask != NULL && ff_bundle_atlas.opaque == 0);

    for (frame = 0; frame < FF_BUNDLE_NFRAME; ++frame) {
        int col = frame % FF_BUNDLE_ATLAS_COLS;
        int row = frame / FF_BUNDLE_ATLAS_COLS;
        cell.x = (int16_t)(col * FF_BUNDLE_TILE_W);
        cell.y = (int16_t)(row * FF_BUNDLE_TILE_H);
        cell.w = FF_BUNDLE_TILE_W;
        cell.h = FF_BUNDLE_TILE_H;
        reset_fb();
        blit_cell(&ff_bundle_atlas, cell, 4, 12);
        for (y = 0; y < FF_BUNDLE_TILE_H; ++y) {
            for (x = 0; x < FF_BUNDLE_TILE_W; ++x) {
                uint16_t want = frame_expected(frame, x, y, BG);
                uint16_t got = fb[(12 + y) * FB_W + (4 + x)];
                assert(got == want);
            }
        }
    }

    /* Atlas pixels outside a cell must not leak into a neighbouring blit:
     * cell 0 is stand, whose last row and column are empty canvas. */
    reset_fb();
    cell.x = 0;
    cell.y = 0;
    cell.w = FF_BUNDLE_TILE_W;
    cell.h = FF_BUNDLE_TILE_H;
    blit_cell(&ff_bundle_atlas, cell, 0, 0);
    assert(fb[0] == BG);
    assert(fb[7 * FB_W + 7] == BG);
    assert(fb[6 * FB_W + 6] == C_G);
    assert(fb[FB_W] == BG);
}

static void check_clips(void)
{
    VxpeAnimState st;
    VxpeRectI rect;
    VxpeRectI cell;
    int i, x, y;

    /* idle is 160/120/160/120 ms over 4 clip positions; the core must honour
     * the per-frame durations the forge emitted, not a single frame_ms. */
    vxpe2d_anim_reset(&st);
    assert(st.frame == 0);
    vxpe2d_anim_update(&st, &ff_bundle_idle, 159);
    assert(st.frame == 0);
    vxpe2d_anim_update(&st, &ff_bundle_idle, 1);
    assert(st.frame == 1);
    vxpe2d_anim_update(&st, &ff_bundle_idle, 120);
    assert(st.frame == 2);
    vxpe2d_anim_update(&st, &ff_bundle_idle, 160);
    assert(st.frame == 3);
    vxpe2d_anim_update(&st, &ff_bundle_idle, 120);
    assert(st.frame == 0 && ff_bundle_idle.loop == 1);

    rect = vxpe2d_anim_frame_rect(&st, &ff_bundle_idle);
    assert(rect.x == 0 && rect.y == 0 && rect.w == 8 && rect.h == 8);
    vxpe2d_anim_update(&st, &ff_bundle_idle, 160);
    rect = vxpe2d_anim_frame_rect(&st, &ff_bundle_idle);
    assert(rect.x == 0 && rect.y == 0);
    vxpe2d_anim_update(&st, &ff_bundle_idle, 120);
    rect = vxpe2d_anim_frame_rect(&st, &ff_bundle_idle);
    /* Clip position 2 of idle is step_a, the second cell in atlas row 0. */
    assert(rect.x == 8 && rect.y == 0);

    /* One full cycle lands exactly back on frame 0 with no drift. */
    vxpe2d_anim_reset(&st);
    for (i = 0; i < 24; ++i) vxpe2d_anim_update(&st, &ff_bundle_walk, 20);
    assert(st.frame == 0);

    /* hurt is a 2-frame non-looping clip: it has to stop on the last frame. */
    vxpe2d_anim_reset(&st);
    rect = vxpe2d_anim_frame_rect(&st, &ff_bundle_hurt);
    /* hurt clip position 0 is frame 3, cell (1,1) of a 2-column atlas. */
    assert(rect.x == 8 && rect.y == 8);
    vxpe2d_anim_update(&st, &ff_bundle_hurt, 200);
    assert(st.frame == 1 && st.finished == 0);
    rect = vxpe2d_anim_frame_rect(&st, &ff_bundle_hurt);
    assert(rect.x == 0 && rect.y == 0);
    vxpe2d_anim_update(&st, &ff_bundle_hurt, 400);
    assert(st.frame == 1 && st.finished == 1);
    vxpe2d_anim_update(&st, &ff_bundle_hurt, 400);
    assert(st.frame == 1 && st.finished == 1);

    reset_fb();
    cell.x = 8;
    cell.y = 8;
    cell.w = FF_BUNDLE_TILE_W;
    cell.h = FF_BUNDLE_TILE_H;
    blit_cell(&ff_bundle_atlas, cell, 4, 12);
    for (y = 0; y < FF_BUNDLE_TILE_H; ++y) {
        for (x = 0; x < FF_BUNDLE_TILE_W; ++x) {
            assert(fb[(12 + y) * FB_W + (4 + x)] == frame_expected(3, x, y, BG));
        }
    }
}

int main(void)
{
    check_loose();
    check_atlas();
    check_clips();
    printf("sprite-forge import C API ok\n");
    return 0;
}
