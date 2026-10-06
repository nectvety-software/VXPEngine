#include "game.h"
#include "art.h"
#include "labels.h"
#include "actor_assets.h"
#include "prop_assets.h"
#include "graphics/VxpRender2D.h"
#include "vxpgdx/TinyFont5x7.h"
#include <string.h>

static uint16_t* buffer;
static uint16_t rgb(int r,int g,int b) { return (uint16_t)(((r>>3)<<11)|((g>>2)<<5)|(b>>3)); }
static void rect(int x,int y,int w,int h,uint16_t c) { vxpe2d_fill_rect(buffer,240,320,x,y,w,h,c); }
static void label(int id,int x,int y,uint16_t color,bool centered=false) {
    const Label& l=labels[id]; if(centered) x-=l.w/2;
    for(int yy=0;yy<l.h;++yy) for(int xx=0;xx<l.w;++xx)
        if(l.bits[(yy*l.w+xx)>>3] & (128>>((yy*l.w+xx)&7))) rect(x+xx,y+yy,1,1,color);
}
static void ascii(const char* s,int x,int y,uint16_t c) {
    for(;*s;++s,x+=6) {
        unsigned ch=(unsigned char)*s;if(ch<32||ch>126)continue;
        for(int yy=0;yy<7;++yy)for(int xx=0;xx<5;++xx)
            if(vxpe::gdx::detail::kFont5x7[ch-32][yy]&(1<<(4-xx)))rect(x+xx,y+yy,1,1,c);
    }
}
static void panel(int x,int y,int w,int h) {
    rect(x-2,y-2,w+4,h+4,rgb(223,181,104));
    rect(x,y,w,h,rgb(25,43,45));
    rect(x+3,y+3,w-6,1,rgb(75,94,83));
}
static void line(int x,int y,int tx,int ty,uint16_t c) {
    int dx=tx-x,dy=ty-y,steps=(dx<0?-dx:dx);if((dy<0?-dy:dy)>steps)steps=dy<0?-dy:dy;
    for(int i=0;i<=steps;++i)rect(x+(steps?dx*i/steps:0),y+(steps?dy*i/steps:0),1,1,c);
}
static void prop(int frame,int x,int y){
    VxpeBlit565 op={};op.src.x=(int16_t)(frame*16);op.src.w=16;op.src.h=16;
    op.dst_x=(int16_t)x;op.dst_y=(int16_t)y;op.dst_w=16;op.dst_h=16;
    op.tint565=65535;op.alpha=255;op.blend=VXPE_BLEND_ALPHA;
    vxpe2d_blit_a8(buffer,240,320,&fishing_props,&op);
}
void Game::input(Input key) {
    if(screen==SPLASH){screen=MENU;selected=0;return;}
    if(key==BACK){ if(screen==MENU){screen=EXIT_CONFIRM;selected=0;}else {screen=MENU;selected=0;cast=0;reel_ticks=0;last_move_tick=tick-99;vxpe_actor_set(&actor,(uint8_t)facing,VXPE_ACTOR_IDLE);}return; }
    if(screen==PLAY){
        if(!cast){int step=speed?3:2;if(key==LEFT){x-=step;facing=3;++walk;last_move_tick=tick;}if(key==RIGHT){x+=step;facing=1;++walk;last_move_tick=tick;}if(key==UP){y-=step;facing=0;++walk;last_move_tick=tick;}if(key==DOWN){y+=step;facing=2;++walk;last_move_tick=tick;}
            if(x<104)x=104;
            if(x>150)x=150;
            if(y<100)y=100;
            if(y>275)y=275;}
        if(key==OK){if(!cast){cast=1;cast_tick=0;facing=1;}else {if(cast==2){++fish;reel_ticks=8;}cast=0;}}
        vxpe_actor_set(&actor,(uint8_t)facing,reel_ticks?VXPE_ACTOR_REEL:cast?VXPE_ACTOR_CAST:tick-last_move_tick<5?VXPE_ACTOR_WALK:VXPE_ACTOR_IDLE);
        return;
    }
    int count=screen==MENU?6:screen==LANGUAGE?2:screen==SETTINGS?2:screen==EXIT_CONFIRM?2:1;
    if(key==UP)selected=(selected+count-1)%count;
    if(key==DOWN)selected=(selected+1)%count;
    if(screen==SETTINGS&&(key==LEFT||key==RIGHT||key==OK)){if(selected==0)effects=!effects;else speed=!speed;return;}
    if(key!=OK)return;
    if(screen==MENU){const Screen dest[]={PLAY,LANGUAGE,HELP,ABOUT,SETTINGS,EXIT_CONFIRM};screen=dest[selected];selected=0;return;}
    if(screen==LANGUAGE){language=selected;screen=MENU;selected=0;return;}
    if(screen==EXIT_CONFIRM){if(selected==1)exiting=true;else{screen=MENU;selected=0;}return;}
    screen=MENU;selected=0;
}
void Game::update(){
    ++tick;if(screen==SPLASH&&tick>=60)screen=MENU;
    if(screen==PLAY){
        if(reel_ticks)--reel_ticks;
        if(cast){++cast_tick;if(cast_tick==65)cast=2;if(cast_tick>100)cast=0;}
        vxpe_actor_set(&actor,(uint8_t)facing,reel_ticks?VXPE_ACTOR_REEL:cast?VXPE_ACTOR_CAST:tick-last_move_tick<5?VXPE_ACTOR_WALK:VXPE_ACTOR_IDLE);
        vxpe_actor_update(&actor,&hero_atlas,33);
    }
}
void Game::draw(uint16_t* fb) {
    buffer=fb;memcpy(fb,background,sizeof(background));
    const uint16_t cream=rgb(255,237,185),gold=rgb(240,190,91),teal=rgb(110,220,200);
    const int base=language?VI_BASE:EN_BASE;
    if(effects)for(int i=0;i<22;++i){int wx=180+(i*37)%56,wy=38+(i*29)%245;rect(wx,wy+((tick/5+i)%3),4,1,rgb(110,169,142));}
    if(screen==PLAY){
        rect(x-7,y+12,16,3,rgb(77,66,46));
        vxpe_actor_draw(fb,240,320,&hero_atlas,&actor,(int16_t)x,(int16_t)(y+12));
        if(reel_ticks)prop(0,x+10,y-20);
        if(cast){line(x+5,y+2,x+15,y-13,rgb(76,51,42));line(x+15,y-13,218,y-2,rgb(222,242,208));
            int radius=4+(tick/3)%6;
            if(effects){rect(218-radius,y+3,radius*2,1,teal);rect(218-radius+2,y+5,radius*2-4,1,teal);}
            prop(1,210,y-10+(cast==2?(tick/3)%2:0));
            if(cast==2){rect(217,y-15,2,5,gold);rect(217,y-8,2,1,gold);}
            if(cast==2){panel(22,248,196,25);label(base+BITE,120,254,gold,true);}}
        panel(8,8,130,27);label(base+FISH,16,14,cream);char n[5];int v=fish%1000;n[0]='0'+v/100;n[1]='0'+v/10%10;n[2]='0'+v%10;n[3]=0;ascii(n,107,18,gold);
        panel(8,296,224,16);label(base+PLAY_HINT,120,296,cream,true);return;
    }
    if(screen==SPLASH){panel(14,100,212,110);label(TITLE,120,116,gold,true);label(base+SUBTITLE,120,154,cream,true);
        label(BRAND,120,183,teal,true);rect(30,224,tick*180/60,3,gold);return;}
    if(screen==MENU){panel(36,54,168,230);label(TITLE_SMALL,120,68,gold,true);
        for(int i=0;i<6;++i){int y=105+i*28;if(i==selected){rect(46,y-2,148,24,rgb(74,94,75));rect(46,y-2,3,24,gold);}label(base+i,61,y, i==selected?gold:cream);}
        rect(0,303,240,17,rgb(25,43,45));label(COPYRIGHT_SMALL,120,305,cream,true);return;}
    panel(12,44,216,238);
    int heading=screen==LANGUAGE?LANG:screen==HELP?GUIDE:screen==ABOUT?ABOUTS:screen==SETTINGS?SET:QUIT;
    label(base+heading,120,58,gold,true);
    if(screen==LANGUAGE){for(int i=0;i<2;++i){if(selected==i)rect(30,112+i*42,180,28,rgb(74,94,75));label(i?VI_NAME:EN_NAME,120,115+i*42,cream,true);}}
    if(screen==HELP){for(int i=0;i<5;++i)label(base+HELP1+i,120,102+i*26,cream,true);}
    if(screen==ABOUT){label(TITLE_SMALL,120,99,cream,true);label(COPYRIGHT,120,134,cream,true);label(WEBSITE,120,164,teal,true);label(base+ABOUT_NOTE,120,198,cream,true);}
    if(screen==SETTINGS){for(int i=0;i<2;++i){if(selected==i)rect(24,110+i*50,192,35,rgb(74,94,75));label(base+(i?SPEED:EFFECTS),32,115+i*50,cream);label(base+(i?(speed?FAST:SLOW):(effects?ON:OFF)),190,115+i*50,gold,true);}}
    if(screen==EXIT_CONFIRM){label(base+EXIT_QUESTION,120,107,cream,true);for(int i=0;i<2;++i){if(selected==i)rect(38,151+i*34,164,26,rgb(74,94,75));label(base+(i?YES:NO),120,154+i*34,cream,true);}}
    label(base+BACK_HINT,120,255,teal,true);
}
