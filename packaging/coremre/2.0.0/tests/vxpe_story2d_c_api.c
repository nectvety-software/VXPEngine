#include "graphics/VxpStory2D.h"
#include <assert.h>
#include "graphics/VxpPixelFont.h"
int main(void) {
    VxpeStoryStage2D stage;
    VxpeStoryDialogue d;
    vxpe_story_stage_init(&stage,100,200);
    assert(vxpe_story_scale(&stage,150)==224);
    vxpe_story_dialogue_open(&d,"Speaker","C-compatible dialogue",48,3,0);
    assert(d.active && d.revealed==d.page_glyphs);
    assert(!vxpe_story_dialogue_advance(&d));
    VxpeFontStyle font;
    vxpe_font_style_default(&font);
    assert(vxpe_font_measure("II",&font)==7);
    return 0;
}
