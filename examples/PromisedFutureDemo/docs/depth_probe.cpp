/* Print, for one tower at level 0, the camera-space z of each of the 16 shell
   quads' 4 corners. If a "front" quad has larger z than a "back" quad at the
   same screen x, the depth test will wrongly reject the front. */
#include "graphics/VxpToon3D.h"
#include <stdio.h>
static const int16_t SIN_Q14[32]={0,3196,6270,9102,11585,13623,15137,16069,16384,16069,15137,13623,11585,9102,6270,3196,0,-3196,-6270,-9102,-11585,-13623,-15137,-16069,-16384,-16069,-15137,-13623,-11585,-9102,-6270,-3196};
static const int16_t COS_Q14[32]={16384,16069,15137,13623,11585,9102,6270,3196,0,-3196,-6270,-9102,-11585,-13623,-15137,-16069,-16384,-16069,-15137,-13623,-11585,-9102,-6270,-3196,0,3196,6270,9102,11585,13623,15137,16069};
static VxpeVec3D point(int x,int y,int z){VxpeVec3D v={x,y,z};return v;}
static VxpeVec3D ring16(int cx,int cy,int cz,int radius,int i){int k=(i&15)*2;return point(cx+(int32_t)COS_Q14[k]*radius/16384,cy,cz+(int32_t)SIN_Q14[k]*radius/16384);}
int main(){
    int x=-175,z=385,h=235,r=61;
    int ys[5]={0,h/5,h*2/5,h*4/5,h},rs[5]={r,r*6/5,r*11/10,r*4/5,r/4};
    /* camera from the demo */
    int cx=0,cy=102,cz=24;
    printf("camera at (%d,%d,%d), focal=96, level 0 shell quads (R=%d..%d):\n",cx,cy,cz,rs[0],rs[1]);
    printf(" s | corner A(rel z)  B(rel z)  D(rel z)  E(rel z) | minZ maxZ | screenX range\n");
    for(int s=0;s<16;++s){
        int bend=0;
        VxpeVec3D a=ring16(x,ys[0],z,rs[0],s),b=ring16(x,ys[0],z,rs[0],s+1);
        VxpeVec3D d=ring16(x+bend,ys[1],z,rs[1],s+1),e=ring16(x+bend,ys[1],z,rs[1],s);
        /* relative camera z (cos_yaw=1 so rel z = world z - cam z) */
        int az=a.z-cz,bz=b.z-cz,dz=d.z-cz,ez=e.z-cz;
        int minz=az<bz?az:bz; if(dz<minz)minz=dz; if(ez<minz)minz=ez;
        int maxz=az>bz?az:bz; if(dz>maxz)maxz=dz; if(ez>maxz)maxz=ez;
        /* screen x of each corner */
        int axp=60+(a.x-cx)*96/az, bxp=60+(b.x-cx)*96/bz, dxp=60+(d.x-cx)*96/dz, exp_=60+(e.x-cx)*96/ez;
        printf("%2d | %6d %6d %6d %6d | %6d %6d | %4d..%4d\n",s,az,bz,dz,ez,minz,maxz,
            (axp<bxp?axp:bxp)<(dxp<exp_?dxp:exp_)?(axp<bxp?axp:bxp):(dxp<exp_?dxp:exp_),
            (axp>bxp?axp:bxp)>(dxp>exp_?dxp:exp_)?(axp>bxp?axp:bxp):(dxp>exp_?dxp:exp_));
    }
    return 0;
}
