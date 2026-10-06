#include "scene.h"
#include <stdio.h>
#include <assert.h>
static void save(UrbanScene& scene,const char* path){static uint16_t pixels[240*320+2];pixels[0]=pixels[240*320+1]=0x1234;scene.draw(pixels+1);assert(pixels[0]==0x1234&&pixels[240*320+1]==0x1234);
    FILE* file=fopen(path,"wb");assert(file);fprintf(file,"P6\n240 320\n255\n");for(int i=1;i<=240*320;++i){unsigned short c=pixels[i];unsigned char p[3]={(unsigned char)(((c>>11)&31)*255/31),(unsigned char)(((c>>5)&63)*255/63),(unsigned char)((c&31)*255/31)};fwrite(p,1,3,file);}fclose(file);}
int main(){static UrbanScene scene;assert(sizeof(scene)<=78000);save(scene,"urban_toon.ppm");scene.input(7);scene.input(5);for(int i=0;i<14;++i)scene.update();save(scene,"urban_grind.ppm");assert(scene.points>=150&&scene.jump&&scene.grind);
    scene.input(0);save(scene,"urban_camera.ppm");scene.input(0);save(scene,"urban_camera2.ppm");scene.input(9);int z=scene.pz;scene.update();assert(scene.pz==z);scene.paused=false;static uint16_t stress[240*320+2];
    for(int mode=0;mode<3;++mode)for(int side=-1;side<=1;++side)for(int jump=1;jump<=35;jump+=17){scene.cameraMode=mode;scene.px=side*130;scene.jump=jump;scene.pz=319;stress[0]=stress[240*320+1]=0x1234;scene.draw(stress+1);assert(stress[0]==0x1234&&stress[240*320+1]==0x1234);}
    puts("PASS: urban renderer, steering, jump/grind, camera and pause");}
