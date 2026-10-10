#include "ps1.h"
#include <stdio.h>
#include <assert.h>
int main(int argc,char**argv){assert(argc==2);FILE* f=fopen(argv[1],"wb");assert(f);static uint16_t pixels[120*160],depth[120*160];VxpeToonTarget3D t={pixels,depth,120,160};
 for(int frame=0;frame<8;++frame){urban_ps1_render(&t,frame*31,0,false);int count=0;
 for(int i=0;i<120*160;++i){uint16_t c=pixels[i];unsigned char rgba[4]={(unsigned char)(((c>>11)&31)*255/31),(unsigned char)(((c>>5)&63)*255/63),(unsigned char)((c&31)*255/31),(unsigned char)(depth[i]==65535?0:255)};fwrite(rgba,1,4,f);if(rgba[3])++count;}assert(count>600&&count<120*160/2);}
 fclose(f);puts("PASS: PS1 mesh bake, eight views and transparent pixel coverage");}
