#include "graphics/VxpStory2D.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>

int main() {
    VxpeStoryStage2D stage;
    vxpe_story_stage_init(&stage, 100, 200);
    assert(vxpe_story_scale(&stage, 0) == 192);
    assert(vxpe_story_scale(&stage, 150) == 224);
    assert(vxpe_story_scale(&stage, 300) == 256);
    assert(vxpe_story_scale(0, 1) == 256);
    uint16_t red[4] = {0xF800,0xF800,0xF800,0xF800};
    uint16_t green[4] = {0x07E0,0x07E0,0x07E0,0x07E0};
    VxpeSpriteA8 a = {red,0,2,2,2,0,1}, b = {green,0,2,2,2,0,1};
    VxpeSpriteBatch batch;
    vxpe2d_batch_init(&batch);
    VxpeRectI frame = {0,0,2,2};
    stage.far_scale_q8 = stage.near_scale_q8 = 256;
    assert(vxpe_story_push_actor(&batch,&stage,&b,frame,0,2,4,8,2,0,0));
    assert(vxpe_story_push_actor(&batch,&stage,&a,frame,0,2,4,6,0,0,0));
    uint16_t guarded[102];
    memset(guarded,0,sizeof(guarded));
    guarded[0] = guarded[101] = 0x1234;
    vxpe2d_batch_flush(&batch,guarded+1,10,10);
    assert(guarded[1+4*10+4] == 0x07E0); // Ground feet sort, independent of lift.
    assert(guarded[0] == 0x1234 && guarded[101] == 0x1234);
    frame.w = 3;
    assert(!vxpe_story_push_actor(&batch,&stage,&a,frame,0,0,0,0,0,0,0));
    frame.w = 2;
    assert(vxpe_story_push_actor(&batch,&stage,&a,frame,1,2,0,0,0,1,0));
    for (int i=1;i<VXPE_SPRITE_BATCH_MAX;++i)
        assert(vxpe_story_push_actor(&batch,0,&a,frame,1,2,0,0,0,0,0));
    assert(!vxpe_story_push_actor(&batch,0,&a,frame,1,2,0,0,0,0,0));
    assert(batch.dropped == 1);

    VxpeStoryDialogue d;
    vxpe_story_dialogue_open(&d,"Keeper","One two three four five six.",9,1,20);
    assert(!strcmp(d.lines[0],"One two"));
    vxpe_story_dialogue_update(&d,60);
    assert(d.revealed == 3);
    assert(vxpe_story_dialogue_advance(&d) && d.revealed == d.page_glyphs);
    assert(vxpe_story_dialogue_advance(&d) && !strcmp(d.lines[0],"three"));
    int pages=1;
    while(d.active && pages<20) { vxpe_story_dialogue_update(&d,65535); vxpe_story_dialogue_advance(&d); ++pages; }
    assert(!d.active && pages<20);
    vxpe_story_dialogue_open(&d,"","abcdefghijklmnop\nZ",4,2,0);
    assert(!strcmp(d.lines[0],"abcd") && !strcmp(d.lines[1],"efgh"));
    assert(d.revealed == 8);
    vxpe_story_dialogue_advance(&d);
    assert(!strcmp(d.lines[0],"ijkl") && !strcmp(d.lines[1],"mnop"));
    vxpe_story_dialogue_advance(&d);
    assert(!strcmp(d.lines[0],"Z"));
    assert(!vxpe_story_dialogue_advance(&d));
    vxpe_story_dialogue_open(&d,0,0,0,0,0);
    assert(!vxpe_story_dialogue_advance(&d));
    char longtext[800]; memset(longtext,'A',799); longtext[799]=0;
    vxpe_story_dialogue_open(&d,longtext,longtext,255,255,1);
    assert(strlen(d.text)==511 && strlen(d.speaker)==47 && d.columns==48 && d.rows==6);
    vxpe_story_dialogue_update(&d,65535);
    uint16_t screen[320*240+2] = {};
    screen[0] = screen[320*240+1] = 0xBEEF;
    VxpeRectI box = {-15,-20,320,110};
    vxpe_story_dialogue_draw(screen+1,320,240,&d,box);
    vxpe_story_text(screen+1,320,240,-8,237,"Clipped text",0xFFFF);
    assert(screen[0]==0xBEEF && screen[320*240+1]==0xBEEF);
    VxpeStoryHudStyle hud; vxpe_story_hud_default(&hud);
    assert(hud.alpha==238 && hud.gold==0xEDEB);
    const char* keys[]={"2468","5","7","0","9","1"};
    const char* labels[]={"MOVE","TALK","CAST","SCENE","PAUSE","RESET"};
    for(int orientation=0;orientation<2;++orientation) {
        int w=orientation?320:240,h=orientation?240:320;
        memset(screen+1,0,320*240*sizeof(uint16_t));
        vxpe_story_hud_draw(screen+1,w,h,0,"EMBER CHRONICLE","LOCATION",
            "A very long chapter string","SEALS 0/3",keys,labels,255);
        assert(screen[0]==0xBEEF && screen[320*240+1]==0xBEEF);
        assert(screen[1+43*w]==hud.border && screen[1+(h-26)*w]==hud.border);
        assert(screen[1+100*w+100]==0); // HUD leaves the scene untouched.
        vxpe_story_hud_draw(screen+1,w,h,&hud,0,0,0,0,0,0,6);
    }
    vxpe_story_hud_draw(0,240,320,0,0,0,0,0,0,0,0);
    puts("PASS: perspective, foot depth/lift, capacity, crop validation, dialogue paging/typewriter/truncation/clipping");
}
