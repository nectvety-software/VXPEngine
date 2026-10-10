#include "scene.h"
#include <assert.h>
#include <stdio.h>

static void save(const char* path,const uint16_t* p){FILE* f=fopen(path,"wb");assert(f);fprintf(f,"P6\n240 320\n255\n");for(int i=0;i<240*320;++i){uint16_t c=p[i];unsigned char rgb[3]={(unsigned char)(((c>>11)&31)*255/31),(unsigned char)(((c>>5)&63)*255/63),(unsigned char)((c&31)*255/31)};fwrite(rgb,1,3,f);}fclose(f);}
int main(){static LostLatencyMall g;assert(sizeof(g)<40000);assert(g.progress()==0&&g.mode==0);static uint16_t frame[240*320+2];frame[0]=frame[240*320+1]=0x1234;g.draw(frame+1);assert(frame[0]==0x1234&&frame[240*320+1]==0x1234);save("lost_latency_title.ppm",frame+1);
 g.input(5);assert(g.mode==1);g.update();int z=g.worldZ;g.input(2);assert(g.worldZ>z);g.input(4);g.input(6);assert(g.yaw==0);
 g.worldX=-108;g.worldZ=150;g.nearest=0;g.input(5);assert(g.progress()==1);g.input(0);assert(g.mode==3);g.input(5);assert(g.mode==1);
 g.restore(0x0d);assert(g.progress()==0x0d);g.input(9);assert(g.mode==2);g.update();g.input(9);assert(g.mode==1);
 g.worldX=0;g.worldZ=24;g.nearest=-1;g.draw(frame+1);assert(frame[0]==0x1234&&frame[240*320+1]==0x1234);save("lost_latency_mall.ppm",frame+1);
 LostLatencyMall quit;quit.input(-1);assert(quit.exiting);puts("PASS Lost in Latency: 240x320 bounds, compact 120x160 3D buffers, start/walk/turn, QR scan/journal/cache, pause/exit");}
