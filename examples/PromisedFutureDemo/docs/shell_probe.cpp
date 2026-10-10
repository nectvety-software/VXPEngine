/* Render the tower SHELL ONLY (no bands, no caps) and see if holes remain.
   If holes remain, the shell quad depth ordering is at fault. */
#include "graphics/VxpToon3D.h"
#include "graphics/VxpRender2D.h"
#include <stdio.h>
#include <math.h>
#include <string.h>
static const int16_t SIN_Q14[32]={0,3196,6270,9102,11585,13623,15137,16069,16384,16069,15137,13623,11585,9102,6270,3196,0,-3196,-6270,-9102,-11585,-13623,-15137,-16069,-16384,-16069,-15137,-13623,-11585,-9102,-6270,-3196};
static const int16_t COS_Q14[32]={16384,16069,15137,13623,11585,9102,6270,3196,0,-3196,-6270,-9102,-11585,-13623,-15137,-16069,-16384,-16069,-15137,-13623,-11585,-9102,-6270,-3196,0,3196,6270,9102,11585,13623,15137,16069};
static uint16_t rgb(int r,int g,int b){return vxpe2d_rgb565((uint8_t)r,(uint8_t)g,(uint8_t)b);}
static VxpeVec3D point(int x,int y,int z){VxpeVec3D v={x,y,z};return v;}
static VxpeVec3D ring16(int cx,int cy,int cz,int radius,int i){int k=(i&15)*2;return point(cx+(int32_t)COS_Q14[k]*radius/16384,cy,cz+(int32_t)SIN_Q14[k]*radius/16384);}
static uint16_t PIX[120*160]; static uint16_t DEP[120*160];
int main(int argc,char**argv){
    VxpeToonTarget3D t={PIX,DEP,120,160};
    vxpe2d_gradient_vertical(PIX,120,160,0,0,120,160,rgb(5,53,180),rgb(137,218,222));
    vxpe_toon3d_clear_depth(&t);
    VxpeToonCamera3D cam; vxpe_toon3d_camera_init(&cam,120,160);
    cam.position=point(0,102,24); cam.sin_yaw_q14=0; cam.cos_yaw_q14=16384;
    cam.center_x=60; cam.horizon_y=82; cam.focal_px=96; cam.near_z=5; cam.far_z=1500;
    cam.sin_pitch_q14=1050; cam.cos_pitch_q14=16350;
    VxpeToonMaterial3D white,glass,shade;
    vxpe_toon3d_material_init(&white,rgb(232,240,222));
    vxpe_toon3d_material_init(&glass,rgb(56,190,218));
    vxpe_toon3d_material_init(&shade,rgb(151,207,209));
    white.fog565=rgb(222,239,221); white.fog_near_z=360; white.fog_far_z=1450; white.fog_alpha=100;
    glass.fog565=rgb(152,225,227); glass.fog_near_z=360; glass.fog_far_z=1450; glass.fog_alpha=100;
    shade.fog565=rgb(193,227,222); shade.fog_near_z=360; shade.fog_far_z=1450; shade.fog_alpha=100;

    /* identical tower geometry to the demo, ONE tower, shell + caps ONLY */
    int x=-175,z=385,h=235,r=61;
    int ys[5]={0,h/5,h*2/5,h*4/5,h},rs[5]={r,r*6/5,r*11/10,r*4/5,r/4};
    for(int level=0;level<4;++level)for(int s=0;s<16;++s){
        int bend=level*level*2;
        VxpeVec3D a=ring16(x,ys[level],z,rs[level],s),b=ring16(x,ys[level],z,rs[level],s+1);
        VxpeVec3D d=ring16(x+bend,ys[level+1],z,rs[level+1],s+1),e=ring16(x+bend,ys[level+1],z,rs[level+1],s);
        const VxpeToonMaterial3D& m=((s+level)&5)==0?shade:(((s+level)&1)?glass:white);
        VxpeVec3D v[4]={a,b,d,e};
        vxpe_toon3d_quad(&t,&cam,v,&m,(uint8_t)(188+((s*13+level*17)%62)));
    }
    FILE* f=fopen(argv[1],"wb"); fprintf(f,"P6\n120 160\n255\n");
    for(int i=0;i<120*160;++i){uint16_t c=PIX[i];
        /* upscale 2x horizontally by writing twice */
        unsigned char px[3]={(unsigned char)(((c>>11)&31)*255/31),(unsigned char)(((c>>5)&63)*255/63),(unsigned char)((c&31)*255/31)};
        fwrite(px,1,3,f); fwrite(px,1,3,f);}
    fclose(f);
    printf("shell-only render done\n");
    return 0;
}
