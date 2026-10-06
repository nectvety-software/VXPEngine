#include "game.h"
#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include <string>
static void save(Game& g,const char* path){uint16_t guarded[240*320+2];guarded[0]=0x1234;guarded[240*320+1]=0x5678;uint16_t* fb=guarded+1;g.draw(fb);assert(guarded[0]==0x1234&&guarded[240*320+1]==0x5678);FILE* f=fopen(path,"wb");assert(f);fprintf(f,"P6\n240 320\n255\n");
    for(int i=0;i<320*240;++i){unsigned char rgb[3]={(unsigned char)((fb[i]>>11)*255/31),(unsigned char)(((fb[i]>>5)&63)*255/63),(unsigned char)((fb[i]&31)*255/31)};fwrite(rgb,1,3,f);}fclose(f);}
int main(int argc,char** argv){assert(argc>1);std::string dir=argv[1];Game g;
    save(g,(dir+"/splash.ppm").c_str());for(int i=0;i<60;++i)g.update();assert(g.screen==MENU);
    save(g,(dir+"/menu.ppm").c_str());g.input(OK);assert(g.screen==PLAY);
    g.input(RIGHT);assert(g.actor.action==VXPE_ACTOR_WALK);
    for(int i=0;i<4;++i)g.update();
    assert(g.actor.frame==1);
    g.input(DOWN);assert(g.actor.direction==VXPE_ACTOR_SOUTH&&g.actor.frame==1);
    g.input(LEFT);assert(g.actor.direction==VXPE_ACTOR_WEST);
    g.input(UP);assert(g.actor.direction==VXPE_ACTOR_NORTH);
    for(int i=0;i<6;++i)g.update();
    assert(g.actor.action==VXPE_ACTOR_IDLE);
    g.x=130;g.y=200;g.input(OK);assert(g.actor.action==VXPE_ACTOR_CAST);
    for(int i=0;i<65;++i)g.update();
    assert(g.cast==2);
    save(g,(dir+"/play.ppm").c_str());g.input(OK);assert(g.fish==1&&g.actor.action==VXPE_ACTOR_REEL);g.input(BACK);g.input(DOWN);g.input(OK);assert(g.screen==LANGUAGE);
    g.input(DOWN);g.input(OK);assert(g.language==1&&g.screen==MENU);save(g,(dir+"/menu_vi.ppm").c_str());
    g.selected=2;g.input(OK);save(g,(dir+"/guide.ppm").c_str());g.input(BACK);
    g.selected=3;g.input(OK);save(g,(dir+"/abouts.ppm").c_str());g.input(BACK);
    g.selected=4;g.input(OK);g.input(OK);assert(!g.effects);g.input(DOWN);g.input(OK);assert(!g.speed);save(g,(dir+"/settings.ppm").c_str());g.input(BACK);
    g.selected=5;g.input(OK);save(g,(dir+"/exit.ppm").c_str());g.input(OK);assert(!g.exiting&&g.screen==MENU);g.input(BACK);g.input(DOWN);g.input(OK);assert(g.exiting);
    puts("PASS: splash, menu routes, fishing catch, localization, settings, exit confirmation");}
