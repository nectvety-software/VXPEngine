#include "scene.h"
#include <assert.h>
#include <stdio.h>
static void step(FoxScene& s,int n){for(int i=0;i<n;++i)s.update();}
static void save(FoxScene& s,const char* name){
    unsigned short pixels[240*320+2]={};pixels[0]=pixels[240*320+1]=0xCAFE;
    s.draw(pixels+1);assert(pixels[0]==0xCAFE&&pixels[240*320+1]==0xCAFE);
    FILE* f=fopen(name,"wb");assert(f);fprintf(f,"P6\n240 320\n255\n");
    for(int i=1;i<=240*320;++i){unsigned short c=pixels[i];unsigned char rgb[3]={(unsigned char)((c>>11)*255/31),(unsigned char)(((c>>5)&63)*255/63),(unsigned char)((c&31)*255/31)};fwrite(rgb,1,3,f);}fclose(f);
}
static void setup(FoxScene& s,int hero,int enemy=1){s.selected=hero;s.bot_selected=enemy;s.start_match();s.fighters[1].x=s.fighters[0].x+50;s.fighters[1].y=s.fighters[0].y;}
int main(){
    static FoxScene s;s.init();assert(s.screen==DUEL_SPLASH);save(s,"01_splash.ppm");
    step(s,55);assert(s.screen==DUEL_SELECT);save(s,"02_select.ppm");
    s.hold(6,true);assert(s.selected==1);s.hold(6,false);save(s,"03_torvan_select.ppm");
    s.input(1);assert(s.help);save(s,"04_help.ppm");s.input(1);
    s.hold(8,true);assert(s.bot_selected==2);s.hold(8,false);s.input(5);assert(s.screen==DUEL_MATCH&&s.fighters[0].hero==1&&s.fighters[1].hero==2);
    int x=s.fighters[0].x;s.hold(6,true);step(s,5);s.hold(6,false);assert(s.fighters[0].x>x);
    s.input(10);int time=s.time_ms,bot_casts=s.fighters[1].casts;step(s,20);assert(s.time_ms==time&&s.fighters[1].casts==bot_casts);save(s,"05_pause.ppm");s.input(10);
    setup(s,0);int mana=s.fighters[0].mana;s.cast(0);assert(s.fighters[0].mana==mana-40);s.cast(0);assert(s.fighters[0].mana==mana-40);step(s,12);assert(s.fighters[0].damage_dealt>100);
    setup(s,0,0);s.cast(0);s.cast(1);s.cast(2);assert(s.fighters[0].shield==50);save(s,"06_velin.ppm");
    setup(s,1);s.cast(1);assert(s.fighters[0].shield==240);int hp=s.fighters[0].hp;s.hit(1,100);assert(s.fighters[0].hp==hp&&s.fighters[0].shield==155);
    int before=s.fighters[0].x;s.cast(2);assert(s.fighters[0].x>before&&s.fighters[1].stun_ms>0);save(s,"07_torvan.ppm");
    setup(s,2);before=s.fighters[0].x;s.cast(1);assert(s.fighters[0].x<before);s.cast(2);step(s,10);assert(s.fighters[1].stun_ms>0);save(s,"08_nimara.ppm");
    setup(s,0);s.fighters[0].mana=0;s.cast(0);assert(s.fighters[0].casts==0);s.fighters[0].stun_ms=500;s.fighters[0].mana=600;s.cast(0);assert(s.fighters[0].casts==0);
    // A projectile aims at the original position and can miss a moving target.
    setup(s,0);s.cast(0);s.fighters[1].y=112;s.fighters[1].stun_ms=1900;
    step(s,20);assert(s.fighters[0].damage_dealt==0);
    // Ranger passive requires actual movement, for player and bot alike.
    setup(s,2);s.fighters[1].stun_ms=1900;s.fighters[0].mana=100;s.regen_ms=267;
    s.hold(6,true);s.update();s.hold(6,false);assert(s.fighters[0].mana==106);
    s.regen_ms=267;s.update();assert(s.fighters[0].mana==110);
    // Recovery belongs to the shared combat rules; the bot uses it at low HP.
    setup(s,0,2);s.fighters[1].hp=100;s.update();assert(s.fighters[1].healing==300&&s.fighters[1].heal_ms==15000);
    setup(s,1);s.fighters[0].hp=500;s.input(1);assert(s.fighters[0].hp==800);s.input(1);assert(s.fighters[0].hp==800);
    for(int hero=0;hero<3;++hero){setup(s,(hero+1)%3,hero);step(s,60);assert(s.bot_decisions>0&&s.fighters[1].casts>0);s.fighters[1].hp=100;s.fighters[1].heal_ms=15000;step(s,12);assert(s.bot_retreats>0);}
    setup(s,0);s.hit(0,10000);assert(s.screen==DUEL_MATCH&&s.fighters[1].hp==0);
    step(s,154);assert(s.fighters[1].hp>0&&s.fighters[1].y<250);
    s.damage_structure(0,3,9999);assert(s.structures[3].hp==1800);
    s.damage_structure(0,4,9999);assert(s.structures[4].hp==900);
    s.damage_structure(0,5,9999);s.damage_structure(0,4,9999);s.damage_structure(0,3,9999);
    assert(s.screen==DUEL_RESULT&&s.result==1);save(s,"09_victory.ppm");s.input(5);
    s.damage_structure(1,2,9999);s.damage_structure(1,1,9999);s.damage_structure(1,0,9999);
    assert(s.screen==DUEL_RESULT&&s.result==-1);save(s,"10_defeat.ppm");s.input(-1);
    s.input(7);s.input(9);assert(s.selected_skin==1&&s.bot_skin==1);s.start_match();
    assert(s.fighters[0].skin==1&&s.fighters[1].skin==1);
    int initial=s.camera_y;s.hold(2,true);step(s,80);s.hold(2,false);assert(s.camera_y<initial);save(s,"12_lane_skin.ppm");
    s.time_ms=299999;s.update();assert(s.result==2);save(s,"11_draw.ppm");
    // Export ready skill icons for all heroes and both teams' structures for visual review.
    for(int hero=0;hero<3;++hero){
        s.selected=hero;s.selected_skin=0;s.start_match();s.fighters[0].x=55;s.fighters[0].y=740;
        s.camera_y=560;char name[40];snprintf(name,sizeof(name),"13_icons_%d.ppm",hero);save(s,name);
    }
    s.fighters[0].y=835;s.camera_y=640;save(s,"14_blue_core.ppm");
    s.fighters[0].y=370;s.camera_y=180;save(s,"15_red_tower.ppm");
    s.structures[5].hp=0;save(s,"16_tower_ruins.ppm");
    s.fighters[0].y=150;s.camera_y=0;save(s,"17_red_core.ppm");
    s.structures[3].hp=0;save(s,"18_core_ruins.ppm");
    s.input(-1);s.input(-1);assert(s.exiting);
    puts("PASS: splash/menu, hero/bot selection, mana/cooldown/stun, three hero mechanics, AI casts/retreat, heal, pause, respawn, guarded towers/core victory, camera, skins/time limit, rematch/back, framebuffer guards");
}
