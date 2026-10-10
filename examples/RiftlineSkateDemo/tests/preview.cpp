#include "scene.h"
#include <assert.h>
#include <stdio.h>

static void save(RiftlineScene& s,const char* path){static uint16_t pixels[240*320+2];pixels[0]=pixels[240*320+1]=0x1234;s.draw(pixels+1);assert(pixels[0]==0x1234&&pixels[240*320+1]==0x1234);
 FILE* f=fopen(path,"wb");assert(f);fprintf(f,"P6\n240 320\n255\n");for(int i=1;i<=240*320;++i){uint16_t c=pixels[i];uint8_t rgb[3]={(uint8_t)(((c>>11)&31)*255/31),(uint8_t)(((c>>5)&63)*255/63),(uint8_t)((c&31)*255/31)};fwrite(rgb,1,3,f);}fclose(f);}
int main(){static RiftlineScene s;assert(sizeof(s)<=78000);save(s,"riftline_title.ppm");s.input(5);assert(s.started);s.input(5);assert(s.jump>0);s.input(1);assert(s.points==125&&s.combo==2);for(int i=0;i<10;++i)s.update();save(s,"riftline_trick.ppm");s.input(3);assert(s.points==305&&s.combo==3);s.input(7);assert(s.grind&&s.points==525);for(int i=0;i<12;++i)s.update();save(s,"riftline_grind.ppm");s.input(9);int z=s.pz;s.update();assert(s.pz==z);s.input(9);int x=s.px;s.input(6);assert(s.px==x+9);s.grind=0;s.jump=0;s.trick=0;s.px=15;s.pz=640;save(s,"riftline_ramp.ppm");RiftlineScene exit;exit.input(-1);assert(exit.exiting);puts("PASS Riftline: title, ollie, tricks, grind, pause, ramp, exit, 240x320 guards");}
