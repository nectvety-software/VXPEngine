#include "graphics/VxpStory2D.h"
#include "vxpgdx/TinyFont5x7.h"
#include <string.h>

void vxpe_story_stage_init(VxpeStoryStage2D* s, int16_t far_y, int16_t near_y) {
    if (!s) return;
    s->camera_x = s->camera_y = 0;
    s->far_y = far_y; s->near_y = near_y;
    s->far_scale_q8 = 192; s->near_scale_q8 = 256;
}

uint16_t vxpe_story_scale(const VxpeStoryStage2D* s, int16_t y) {
    if (!s || s->near_y <= s->far_y) return 256;
    int a = s->far_scale_q8, b = s->near_scale_q8;
    if (a < 1) a = 1;
    if (a > 1024) a = 1024;
    if (b < 1) b = 1;
    if (b > 1024) b = 1024;
    if (y <= s->far_y) return (uint16_t)a;
    if (y >= s->near_y) return (uint16_t)b;
    return (uint16_t)(a + (b-a)*(y-s->far_y)/(s->near_y-s->far_y));
}

int vxpe_story_push_actor(VxpeSpriteBatch* batch, const VxpeStoryStage2D* stage,
    const VxpeSpriteA8* sprite, VxpeRectI frame, int16_t ax, int16_t ay,
    int16_t x, int16_t y, int16_t lift, uint8_t flip, const VxpeSpriteFxStyle* fx) {
    if (!batch || !sprite || !sprite->pixels || frame.x < 0 || frame.y < 0 ||
        frame.w <= 0 || frame.h <= 0 || frame.x + frame.w > sprite->width ||
        frame.y + frame.h > sprite->height || ax < 0 || ay < 0 ||
        ax > frame.w || ay > frame.h) return 0;
    const int scale = vxpe_story_scale(stage, y);
    const int dx = stage ? stage->camera_x : 0, dy = stage ? stage->camera_y : 0;
    VxpeBlit565 op = {};
    op.src = frame;
    op.dst_w = (uint16_t)((frame.w * scale + 128) / 256);
    op.dst_h = (uint16_t)((frame.h * scale + 128) / 256);
    if (!op.dst_w) op.dst_w = 1;
    if (!op.dst_h) op.dst_h = 1;
    /* Mirrored source anchor uses the scaled frame extent. */
    int anchor_x = (ax * scale + 128) / 256;
    if (flip) anchor_x = op.dst_w - anchor_x;
    int px = x - dx - anchor_x;
    int py = y - dy - lift - (ay * scale + 128) / 256;
    if (px < -32768 || px > 32767 || py < -32768 || py > 32767) return 0;
    op.dst_x = (int16_t)px; op.dst_y = (int16_t)py;
    op.tint565 = 0xFFFF; op.alpha = 255; op.blend = VXPE_BLEND_ALPHA;
    op.flip_x = flip ? 1 : 0;
    return vxpe2d_batch_push(batch, sprite, &op, y, fx);
}

static void copy_text(char* dest, size_t size, const char* src) {
    if (!src) src = "";
    size_t n = 0;
    while (n + 1 < size && src[n]) { dest[n] = src[n]; ++n; }
    dest[n] = 0;
}

static void page(VxpeStoryDialogue* d) {
    memset(d->lines, 0, sizeof(d->lines));
    d->line_count = 0; d->page_glyphs = 0; d->revealed = 0; d->elapsed_ms = 0;
    int pos = d->next_offset;
    for (int row = 0; row < d->rows && d->text[pos]; ++row) {
        while (d->text[pos] == ' ' || d->text[pos] == '\r') ++pos;
        const int start = pos;
        int n = 0, last_space = -1;
        while (n < d->columns && d->text[pos+n] && d->text[pos+n] != '\n') {
            if (d->text[pos+n] == ' ') last_space = n;
            ++n;
        }
        if (n == d->columns && d->text[pos+n] && d->text[pos+n] != '\n' &&
            d->text[pos+n] != ' ' && last_space > 0) n = last_space;
        pos += n;
        if (d->text[pos] == '\n') ++pos;
        while (n > 0 && d->text[start+n-1] == ' ') --n;
        memcpy(d->lines[row], d->text + start, (size_t)n);
        d->page_glyphs += (uint16_t)n;
        ++d->line_count;
    }
    while (d->text[pos] == ' ' || d->text[pos] == '\r') ++pos;
    d->next_offset = (uint16_t)pos;
    d->has_next = d->text[pos] != 0;
    if (!d->glyph_ms) d->revealed = d->page_glyphs;
}

void vxpe_story_dialogue_open(VxpeStoryDialogue* d, const char* speaker,
    const char* text, uint8_t cols, uint8_t rows, uint16_t speed) {
    if (!d) return;
    memset(d, 0, sizeof(*d));
    copy_text(d->speaker, sizeof(d->speaker), speaker);
    copy_text(d->text, sizeof(d->text), text);
    d->columns = cols < 1 ? 1 : (cols > 48 ? 48 : cols);
    d->rows = rows < 1 ? 1 : (rows > 6 ? 6 : rows);
    d->glyph_ms = speed;
    d->active = 1;
    page(d);
}

void vxpe_story_dialogue_update(VxpeStoryDialogue* d, uint16_t dt) {
    if (!d || !d->active || d->revealed >= d->page_glyphs) return;
    if (!d->glyph_ms) { d->revealed = d->page_glyphs; return; }
    const uint32_t elapsed = (uint32_t)d->elapsed_ms + dt;
    uint32_t reveal = d->revealed + elapsed / d->glyph_ms;
    d->revealed = (uint16_t)(reveal > d->page_glyphs ? d->page_glyphs : reveal);
    d->elapsed_ms = (uint16_t)(elapsed % d->glyph_ms);
}

int vxpe_story_dialogue_advance(VxpeStoryDialogue* d) {
    if (!d || !d->active) return 0;
    if (d->revealed < d->page_glyphs) d->revealed = d->page_glyphs;
    else if (d->has_next) page(d);
    else d->active = 0;
    return d->active;
}

static void glyph(uint16_t* fb, int w, int h, int x, int y, unsigned char ch,
    uint16_t color, VxpeRectI clip) {
    if (ch < 32 || ch > 126) ch = '?';
    const uint8_t* bits = vxpe::gdx::detail::kFont5x7[ch - 32];
    for (int yy = 0; yy < 7; ++yy) for (int xx = 0; xx < 5; ++xx) {
        const int px = x+xx, py = y+yy;
        if (px >= 0 && px < w && py >= 0 && py < h && px >= clip.x &&
            py >= clip.y && px < clip.x+clip.w && py < clip.y+clip.h &&
            (bits[yy] & (1 << (4-xx)))) fb[py*w+px] = color;
    }
}

void vxpe_story_text(uint16_t* fb, int w, int h, int x, int y, const char* text,
    uint16_t color) {
    if (!fb || w <= 0 || h <= 0 || !text) return;
    VxpeRectI clip = {0,0,(int16_t)(w > 32767 ? 32767 : w),
        (int16_t)(h > 32767 ? 32767 : h)};
    const int origin = x;
    for (int i = 0; i < VXPE_STORY_TEXT_MAX && text[i]; ++i) {
        if (text[i] == '\n') { x = origin; y += 10; }
        else { glyph(fb,w,h,x,y,(unsigned char)text[i],color,clip); x += 6; }
    }
}

void vxpe_story_dialogue_draw(uint16_t* fb, int w, int h,
    const VxpeStoryDialogue* d, VxpeRectI box) {
    if (!fb || !d || !d->active || w <= 0 || h <= 0 || box.w < 32 || box.h < 42) return;
    vxpe2d_overlay_rect(fb,w,h,box.x+2,box.y+3,box.w,box.h,0,100,VXPE_BLEND_ALPHA);
    vxpe2d_overlay_rect(fb,w,h,box.x,box.y+2,box.w,box.h-4,0xEF7D,224,VXPE_BLEND_ALPHA);
    vxpe2d_overlay_rect(fb,w,h,box.x+2,box.y,box.w-4,box.h,0xEF7D,224,VXPE_BLEND_ALPHA);
    vxpe2d_fill_rect(fb,w,h,box.x+4,box.y+2,box.w-8,1,0xFFFF);
    VxpeRectI clip = {(int16_t)(box.x+10),(int16_t)(box.y+8),
        (int16_t)(box.w-20),(int16_t)(box.h-16)};
    int x = clip.x, y = clip.y;
    for (int i = 0; i < 47 && d->speaker[i]; ++i)
        glyph(fb,w,h,x+i*6,y,(unsigned char)d->speaker[i],0x2B66,clip);
    unsigned remaining = d->revealed;
    for (int row = 0; row < d->line_count && row < 6; ++row) {
        for (int col = 0; col < 48 && d->lines[row][col] && remaining; ++col, --remaining)
            glyph(fb,w,h,x+col*6,y+14+row*10,(unsigned char)d->lines[row][col],0x2945,clip);
    }
    if (d->revealed == d->page_glyphs) {
        const char* hint = d->has_next ? "5 MORE" : "5 CLOSE";
        for (int i = 0; hint[i]; ++i)
            glyph(fb,w,h,box.x+box.w-56+i*6,box.y+box.h-15,(unsigned char)hint[i],0x6B2C,clip);
    }
}

void vxpe_story_hud_default(VxpeStoryHudStyle* s) {
    if(s) { s->gold=0xEDEB; s->ivory=0xFFB8; s->muted=0xAD55;
        s->panel=0x1083; s->border=0x6288; s->keycap=0x2945; s->alpha=238; }
}
static void hud_text(uint16_t* fb,int w,int h,int x,int y,const char* text,
    uint16_t color,int max_columns) {
    char bounded[49]; int n=0;
    if(max_columns>48) max_columns=48;
    if(text) while(n<max_columns && text[n]) {
        unsigned char ch=(unsigned char)text[n];
        bounded[n++]=(ch>=32 && ch<=126)?(char)ch:'?';
    }
    bounded[n]=0;
    vxpe_story_text(fb,w,h,x,y,bounded,color);
}
static int hud_length(const char* text,int max_columns) {
    if(max_columns>48) max_columns=48;
    int n=0; if(text) while(n<max_columns && text[n]) ++n; return n;
}
void vxpe_story_hud_draw(uint16_t* fb,int w,int h,const VxpeStoryHudStyle* style,
    const char* title,const char* location,const char* chapter,const char* status,
    const char* const* keys,const char* const* labels,uint8_t count) {
    if(!fb || w<160 || h<100 || w>32767 || h>32767) return;
    VxpeStoryHudStyle fallback; vxpe_story_hud_default(&fallback);
    const VxpeStoryHudStyle& c=style?*style:fallback;
    vxpe2d_overlay_rect(fb,w,h,0,0,w,44,c.panel,c.alpha,VXPE_BLEND_ALPHA);
    int n=hud_length(title,(w-48)/6);
    int left=(w-n*6)/2;
    if(left>24) {
        vxpe2d_fill_rect(fb,w,h,12,6,left-24,1,c.gold);
        vxpe2d_fill_rect(fb,w,h,w-left+12,6,left-24,1,c.gold);
    }
    hud_text(fb,w,h,left,3,title,c.gold,n);
    n=hud_length(location,(w-24)/6);
    hud_text(fb,w,h,(w-n*6)/2,16,location,c.ivory,n);
    int columns=(w-30)/12;
    hud_text(fb,w,h,12,31,chapter,c.muted,columns);
    n=hud_length(status,columns);
    hud_text(fb,w,h,w-12-n*6,31,status,c.gold,n);
    vxpe2d_fill_rect(fb,w,h,0,43,w,1,c.border);
    vxpe2d_overlay_rect(fb,w,h,0,h-26,w,26,c.panel,c.alpha,VXPE_BLEND_ALPHA);
    vxpe2d_fill_rect(fb,w,h,0,h-26,w,1,c.border);
    if(count>6) count=6;
    for(int i=0;i<count;++i) {
        int cell=(w-6)/3,x=6+(i%3)*cell,y=h-23+(i/3)*12;
        const char* key=keys?keys[i]:0;
        int key_columns=hud_length(key,4),key_w=key_columns*6+4;
        vxpe2d_fill_rect(fb,w,h,x,y,key_w,9,c.keycap);
        hud_text(fb,w,h,x+2,y+1,key,c.gold,key_columns);
        hud_text(fb,w,h,x+key_w+4,y+1,labels?labels[i]:0,c.muted,(cell-key_w-10)/6);
    }
}
