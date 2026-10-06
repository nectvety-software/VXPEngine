#include "scene.h"
#include <assert.h>
#include <stdio.h>
static void save(DungeonScene& s,const char* name){static uint16_t pixels[240*320+2];pixels[0]=pixels[240*320+1]=0x1234;s.draw(pixels+1);assert(pixels[0]==0x1234&&pixels[240*320+1]==0x1234);FILE* f=fopen(name,"wb");assert(f);fprintf(f,"P6\n240 320\n255\n");for(int i=1;i<=240*320;++i){uint16_t c=pixels[i];unsigned char p[3]={(unsigned char)(((c>>11)&31)*255/31),(unsigned char)(((c>>5)&63)*255/63),(unsigned char)((c&31)*255/31)};fwrite(p,1,3,f);}fclose(f);}
int main(){static DungeonScene s;save(s,"title.ppm");s.input(5);assert(s.phase==1);save(s,"dungeon.ppm");float z=s.z;s.input(2);assert(s.z>z);s.input(9);int tick=s.tick;s.update();assert(s.tick==tick);s.input(9);
 s.x=288;s.z=300;s.yaw=0;save(s,"hall.ppm");s.x=288;s.z=405;save(s,"courtyard.ppm");s.x=440;s.z=455;s.input(7);assert(s.keys);s.x=450;s.z=110;s.input(7);assert(s.phase==4);s.input(5);assert(!s.keys&&s.health==100);
 s.enemies[0]={s.x,s.z+40,1,0};s.attack();assert(s.enemies[0].hp==0);assert(s.blocked(-1,100)&&s.blocked(0,0));puts("PASS: framebuffer guards, movement, pause, combat, key and exit progression");}
