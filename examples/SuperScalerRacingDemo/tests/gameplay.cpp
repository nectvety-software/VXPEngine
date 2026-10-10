#include "scene.h"
#include <cassert>
#include <cstdio>
#include <cstdint>

int main(){
    SuperScalerGame g;assert(g.mode==0);g.input(5);assert(g.mode==1);
    const auto initial=g.speed;g.input(2);assert(g.speed>initial);g.input(8);assert(g.speed<100);
    g.input(4);assert(g.player_x<0);for(int i=0;i<8;++i)g.input(4);assert(g.player_x==-100);
    g.input(6);assert(g.player_x<0);g.input(5);assert(g.speed==100);
    for(int i=0;i<400;++i)g.update();assert(g.distance>0&&g.score>0&&g.bestScore>=g.score);
    g.input(9);assert(g.mode==2);const auto frozen=g.tick;g.update();assert(g.tick==frozen);g.input(9);assert(g.mode==1);
    uint16_t fb[240*320]{};g.player_x=0;g.draw(fb);
    FILE*f=std::fopen("super_scaler_preview.ppm","wb");assert(f);std::fprintf(f,"P6\n240 320\n255\n");
    for(auto p:fb){const unsigned r=((p>>11)&31)*255/31,gc=((p>>5)&63)*255/63,b=(p&31)*255/31;const unsigned char rgb[3]={(unsigned char)r,(unsigned char)gc,(unsigned char)b};std::fwrite(rgb,1,3,f);}std::fclose(f);
    std::puts("SuperScaler racing input, speed, steering, pause, traffic and frame render passed");
}
