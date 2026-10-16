/*
 * Copyright (c) 2026 PixelRoot32
 * Licensed under the MIT License
 *
 * VxpTilemap2D - scrolling tile layers plus tile collision for C games.
 *
 * Level data stays const so it lands in .rodata next to the sprite atlas: a
 * cell id array and an optional flag array, both width*height, indexing a
 * rectangular tile atlas. Nothing allocates, so a 200x100 room costs the same
 * on a handset as on the host harness.
 *
 * All coordinates are whole pixels with floor semantics, so a body at negative
 * world x still addresses the tile left of the origin. The renderer takes the
 * screen position of tile (0,0) rather than a camera struct, which keeps this
 * module independent of VxpCamera2D and lets the same map serve a parallax
 * layer, a foreground prop sheet or a HUD inset.
 */
#pragma once

#include <stdint.h>
#include "graphics/VxpRender2D.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Tile flag bits. Bits 0..5 are gameplay, 8..9 are render modifiers, and
 * 12..15 are free for games (doors, breakable, secret) without a second table. */
enum VxpeTileFlag2D {
    VXPE_TF_SOLID        = 0x0001, /* blocks every direction */
    VXPE_TF_ONEWAY       = 0x0002, /* blocks only downward motion */
    VXPE_TF_HAZARD       = 0x0004, /* spikes/lava: gameplay reads this, it never blocks */
    VXPE_TF_LADDER       = 0x0008,
    VXPE_TF_WATER        = 0x0010,
    VXPE_TF_TRIGGER      = 0x0020, /* door/switch volume, never solid */
    VXPE_TF_SLOPE_UP_R   = 0x0040, /* floor rises as world x grows */
    VXPE_TF_SLOPE_UP_L   = 0x0080, /* floor rises as world x shrinks */
    VXPE_TF_FLIP_X       = 0x0100,
    VXPE_TF_FLIP_Y       = 0x0200,
    VXPE_TF_GAME0        = 0x1000,
    VXPE_TF_GAME1        = 0x2000,
    VXPE_TF_GAME2        = 0x4000,
    VXPE_TF_GAME3        = 0x8000
};

/* A slope tile is only solid through its upper triangle, so it never carries
 * VXPE_TF_SOLID; VxpeBody2D resolves it with vxpe_tilemap_floor_y instead. */
#define VXPE_TF_SLOPE (VXPE_TF_SLOPE_UP_R | VXPE_TF_SLOPE_UP_L)

typedef struct VxpeTilemap2D {
    const uint16_t* cells;   /* width*height tile ids; id 0 is the blank tile */
    const uint16_t* flags;   /* width*height flag words, or NULL for pure decor */
    const VxpeSprite565* atlas;
    uint16_t width, height;  /* in tiles */
    uint16_t tile_w, tile_h; /* pixels, and the atlas cell size */
    uint16_t atlas_cols;     /* atlas cells per row */
    uint8_t oob_blocks;      /* 1 = outside the map stops a body, 0 = open world */
    uint8_t pad_;
} VxpeTilemap2D;

typedef struct VxpeTileDraw2D {
    int16_t origin_x, origin_y; /* screen position of tile (0,0) */
    int16_t clip_x, clip_y;     /* clip_w/clip_h == 0 means the whole frame */
    uint16_t clip_w, clip_h;
    uint16_t tint565;           /* 0 = neutral */
    uint8_t alpha;              /* 0 = opaque */
    uint8_t blend;              /* VxpeBlendMode */
    uint8_t skip_blank;         /* 1 = cell id 0 is not drawn */
} VxpeTileDraw2D;

/* Fill a draw descriptor with the usual "opaque, whole screen, blanks skipped"
 * layer. Returns the same pointer so it can nest inside a call. */
VxpeTileDraw2D* vxpe_tile_view(VxpeTileDraw2D* view, int origin_x, int origin_y);

/* Draws the visible tile window. Returns the number of tiles actually blitted,
 * which lets a test prove culling and a game budget its frame. */
int vxpe_tilemap_draw(
    uint16_t* fb, int fb_w, int fb_h,
    const VxpeTilemap2D* map, const VxpeTileDraw2D* view);

/* --- queries ------------------------------------------------------------- */

/* Cell id at tile coordinates; 0 when outside the map. */
uint16_t vxpe_tilemap_cell(const VxpeTilemap2D* map, int tx, int ty);

/* Flag word at tile coordinates. Outside the map the answer is
 * VXPE_TF_SOLID when oob_blocks is set, otherwise 0. */
uint16_t vxpe_tilemap_flags(const VxpeTilemap2D* map, int tx, int ty);

/* World-pixel forms: wx/tile_w and wy/tile_h with floor semantics. */
uint16_t vxpe_tilemap_flags_at_px(const VxpeTilemap2D* map, int wx, int wy);
int vxpe_tilemap_blocks_at_px(const VxpeTilemap2D* map, int wx, int wy, uint16_t mask);

/* OR of every flag word overlapping the pixel rect [x0,y0)..(x1,y1). A body
 * uses this for hazard and water tests: one call covers the whole box. */
uint16_t vxpe_tilemap_rect_flags(const VxpeTilemap2D* map,
                                 int x0, int y0, int x1, int y1);

/* Surface height of a slope tile at local_x in [0, tile_w): the world y of the
 * floor there. Non-slope tiles return their bottom edge, so callers can use
 * this unconditionally once they know the tile is not VXPE_TF_SOLID. */
int vxpe_tilemap_floor_y(const VxpeTilemap2D* map, int tx, int ty, int local_x);

#ifdef __cplusplus
} /* extern "C" */
#endif
