#include "game.h"
#include <assert.h>
#include <stdio.h>
#include <vector>
#include <math.h>

static void frame(Game& game,const char* name){
    std::vector<uint16_t> guarded(240*320+2,0x1234);
    game.draw(&guarded[1]);assert(guarded.front()==0x1234&&guarded.back()==0x1234);
    FILE* output=fopen(name,"wb");assert(output);fprintf(output,"P6\n240 320\n255\n");
    for(int i=1;i<=240*320;++i){unsigned short c=guarded[i];unsigned char rgb[3]={(unsigned char)(((c>>11)&31)*255/31),(unsigned char)(((c>>5)&63)*255/63),(unsigned char)((c&31)*255/31)};fwrite(rgb,1,3,output);}fclose(output);
}
static void clear(Game& g){for(int i=0;i<18;++i)g.zombies[i].alive=false;g.remaining=0;g.breakTimer=0;}
int main(){
    Game g;assert(g.phase==TITLE);frame(g,"menu.ppm");g.action(FIRE);assert(g.phase==RUNNING);
    g.x=1.21f;g.y=5.5f;g.angle=3.14159265f;g.hold(FORWARD,true);
    for(int i=0;i<12;++i)g.update();g.hold(FORWARD,false);assert(g.x>=1.18f);
    assert(!g.visible(3.5f,5.5f,8.5f,5.5f));g.gateOpen=true;assert(g.visible(3.5f,5.5f,8.5f,5.5f));
    g.start();clear(g);g.x=3.5f;g.y=5.5f;g.angle=0;
    g.zombies[0]={5.2f,5.5f,68,0,0,true};g.shoot();assert(g.ammo==11&&g.points==10&&g.zombies[0].hp==28);
    g.shoot();assert(g.ammo==11);for(int i=0;i<7;++i)g.update();g.shoot();assert(g.kills==1&&g.points==110);
    int ammo=g.ammo,reserve=g.reserve;g.action(RELOAD);g.shoot();assert(g.ammo==ammo);
    for(int i=0;i<40;++i)g.update();assert(g.ammo==12&&g.reserve==reserve-(12-ammo));
    g.x=6.3f;g.y=5.5f;g.points=499;g.interact();assert(!g.gateOpen&&g.points==499);
    g.points=500;g.interact();assert(g.gateOpen&&g.points==0);
    g.x=2.5f;g.y=5.5f;g.points=200;g.reserve=1;g.interact();assert(g.reserve==120&&g.points==0);
    g.x=3.5f;g.y=6.5f;g.barrier=2;g.interact();assert(g.barrier==3&&g.points==10);
    g.x=10.5f;g.y=10.5f;g.health=20;g.points=300;g.interact();assert(g.health==100&&g.points==0);
    g.action(PAUSE);int h=g.health,r=g.reloadTimer;float x=g.x;g.hold(FORWARD,true);for(int i=0;i<40;++i)g.update();assert(g.x==x&&g.health==h&&g.reloadTimer==r);g.action(PAUSE);
    g.start();clear(g);g.zombies[0]={g.x+.3f,g.y,68,0,0,true};g.update();assert(g.health==90);
    for(int i=0;i<230;++i)g.update();assert(g.phase==DEAD);g.action(FIRE);assert(g.phase==RUNNING&&g.health==100&&g.wave==1);
    clear(g);g.update();assert(g.breakTimer==120);for(int i=0;i<120;++i)g.update();assert(g.wave==2&&g.remaining==8);
    g.start();clear(g);g.angle=-.08f;g.zombies[0]={5.5f,5.4f,68,0,0,true};g.zombies[1]={6.0f,4.5f,68,0,1,true};g.messageTimer=0;frame(g,"cabin.ppm");g.shoot();frame(g,"shot.ppm");
    g.x=9.f;g.y=11.f;g.angle=-.9f;g.gateOpen=true;g.fireTimer=0;g.zombies[0]={11.2f,8.2f,84,0,0,true};g.zombies[1]={13.f,7.5f,84,0,1,true};g.wave=3;frame(g,"courtyard.ppm");
    g.phase=PAUSED;frame(g,"paused.ppm");g.phase=DEAD;frame(g,"dead.ppm");
    // Many simulated ticks and orientations exercise sprite clipping and wall bounds.
    g.start();for(int i=0;i<300;++i){g.angle=i*.1f;g.update();if(i%30==0)frame(g,"stress.ppm");}
    puts("PASS: collision, occlusion, hits, ammo/reload, purchases, repair, pause, death/retry, waves and render bounds");
}
