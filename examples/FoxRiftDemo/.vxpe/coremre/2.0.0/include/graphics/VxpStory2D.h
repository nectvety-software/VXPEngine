/* Fantasy sprite stages and paginated dialogue. C API, fixed memory, no heap. */
#pragma once
#include "graphics/VxpSpriteFx.h"
#ifdef __cplusplus
extern "C" {
#endif

/* Shallow perspective: y is a ground-plane foot position, lift does not
 * affect sort order. Camera translation is applied before depth scaling. */
typedef struct VxpeStoryStage2D {
    int16_t camera_x, camera_y;
    int16_t far_y, near_y;
    uint16_t far_scale_q8, near_scale_q8;
} VxpeStoryStage2D;

void vxpe_story_stage_init(VxpeStoryStage2D* stage, int16_t far_y, int16_t near_y);
uint16_t vxpe_story_scale(const VxpeStoryStage2D* stage, int16_t foot_y);
/* Returns 0 for invalid input or full batch. Crop anchor uses source pixels.
 * NULL style disables sprite FX. Sprite/texture lifetime must span flush. */
int vxpe_story_push_actor(VxpeSpriteBatch* batch, const VxpeStoryStage2D* stage,
    const VxpeSpriteA8* sprite, VxpeRectI frame, int16_t anchor_x, int16_t anchor_y,
    int16_t foot_x, int16_t foot_y, int16_t lift, uint8_t flip_x,
    const VxpeSpriteFxStyle* style);

#define VXPE_STORY_TEXT_MAX 512
#define VXPE_STORY_COLUMNS_MAX 48
#define VXPE_STORY_LINES_MAX 6
typedef struct VxpeStoryDialogue {
    char speaker[48], text[VXPE_STORY_TEXT_MAX];
    char lines[VXPE_STORY_LINES_MAX][VXPE_STORY_COLUMNS_MAX + 1];
    uint16_t next_offset, revealed, page_glyphs, elapsed_ms, glyph_ms;
    uint8_t columns, rows, line_count, active, has_next;
} VxpeStoryDialogue;

/* ASCII text, copied into owned buffers; truncation is NUL-terminated.
 * Columns clamp to 1..48, rows to 1..6. Speed 0 reveals immediately. */
void vxpe_story_dialogue_open(VxpeStoryDialogue* dialogue, const char* speaker,
    const char* text, uint8_t columns, uint8_t rows, uint16_t glyph_ms);
void vxpe_story_dialogue_update(VxpeStoryDialogue* dialogue, uint16_t dt_ms);
/* First press reveals page; later presses page forward, then close.
 * Returns 1 while open, 0 after close (or NULL). */
int vxpe_story_dialogue_advance(VxpeStoryDialogue* dialogue);
void vxpe_story_dialogue_draw(uint16_t* fb, int w, int h,
    const VxpeStoryDialogue* dialogue, VxpeRectI box);
/* Bounded 5x7 ASCII text, newline supported. */
void vxpe_story_text(uint16_t* fb, int w, int h, int x, int y,
    const char* text, uint16_t color);
/* Borrowed ASCII strings; draw does not retain pointers or allocate. */
typedef struct VxpeStoryHudStyle {
    uint16_t gold, ivory, muted, panel, border, keycap;
    uint8_t alpha;
} VxpeStoryHudStyle;
void vxpe_story_hud_default(VxpeStoryHudStyle* style);
/* Responsive title/location/chapter/status and up to six three-column keycaps.
 * NULL style uses defaults; NULL strings are empty. Requires w>=160,h>=100. */
void vxpe_story_hud_draw(uint16_t* fb, int w, int h,
    const VxpeStoryHudStyle* style, const char* title, const char* location,
    const char* chapter, const char* status, const char* const* keys,
    const char* const* labels, uint8_t count);
#ifdef __cplusplus
}
#endif
