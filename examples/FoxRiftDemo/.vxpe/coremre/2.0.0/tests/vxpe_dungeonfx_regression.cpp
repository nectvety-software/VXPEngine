#include "graphics/VxpDungeonFx.h"
#include "graphics/VxpArtStyle.h"
#include <assert.h>
#include <limits.h>
#include <stdio.h>
int main(){VxpeDungeonLight3D red={{0,0,0},0xf800,100,255};
 assert(vxpe_dungeon_light565({0,0,0},0xffff,0,&red,1)==0xf800);
 uint16_t half=vxpe_dungeon_light565({50,0,0},0xffff,0,&red,1);assert(half>0&&half<0xf800&&(half&0x7ff)==0);
 assert(!vxpe_dungeon_light565({100,0,0},0xffff,0,&red,1));assert(!vxpe_dungeon_light565({INT_MIN,INT_MAX,0},0xffff,0,&red,1));
 assert(vxpe_dungeon_light565({0,0,0},0xffff,255,0,100)==0xffff);red.radius=0;assert(!vxpe_dungeon_light565({0,0,0},0xffff,0,&red,1));
 uint16_t fb[64*48+2];fb[0]=fb[64*48+1]=0x1234;vxpe_dungeon_mana_sky(fb+1,64,48,0);uint16_t before=fb[1];
 bool changed=false;uint16_t copy[64*48];for(int i=0;i<64*48;++i)copy[i]=fb[i+1];vxpe_dungeon_mana_sky(fb+1,64,48,9);for(int i=0;i<64*48;++i)changed|=copy[i]!=fb[i+1];assert(changed);
 vxpe_dungeon_mana_sky(fb+1,2049,48,0);assert(fb[0]==0x1234&&fb[64*48+1]==0x1234);(void)before;
 VxpeArtStyleProfile p;vxpe_artstyle_init(&p,VXPE_ARTSTYLE_DUNGEON_SYNTH);assert(p.fog_strength==65&&p.light_alpha==190);
 puts("PASS: coloured light falloff, range/extreme guards, animated sky, buffer guards and dungeon preset");}
