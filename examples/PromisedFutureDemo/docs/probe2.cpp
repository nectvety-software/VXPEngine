#include "scene.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
extern "C" void probe_reset();
extern "C" int probe_count();
struct Rec { int32_t ax,ay,az,bx,by,bz,cx,cy,cz; uint8_t light; };
extern "C" Rec* probe_at(int i);
static double area2(const Rec& r){long long ux=r.bx-r.ax,uy=r.by-r.ay,uz=r.bz-r.az;long long vx=r.cx-r.ax,vy=r.cy-r.ay,vz=r.cz-r.az;double cx=(double)uy*vz-(double)uz*vy,cy=(double)uz*vx-(double)ux*vz,cz=(double)ux*vy-(double)uy*vx;return 0.5*sqrt(cx*cx+cy*cy+cz*cz);}
int main(){
    static PromisedFuture g; g.input(5);
    probe_reset(); uint16_t fb[240*320]; g.draw(fb);
    int n=probe_count();
    /* per-tower breakdown: towers are the tallest structures, y up to 305.
       count triangles whose max Y > 200 => tower geometry */
    int tower=0,cloud=0,water=0,island=0,other=0,palm=0;
    double pix_tower=0,pix_total=0;
    for(int i=0;i<n;++i){Rec& r=*probe_at(i);
        double ax=(r.ax+r.bx+r.cx)/3.0, ay=(r.ay+r.by+r.cy)/3.0, az=(r.az+r.bz+r.cz)/3.0;
        double dz=az-24.0; if(dz<5)dz=5; double sc=96.0/dz; double px=area2(r)*sc*sc; pix_total+=px;
        if(ay>60&&ay<180&&(r.ax<-120||r.bx<-120||r.cx<-120||r.ax>120||r.bx>120||r.cx>120)) {cloud++; continue;}
        if(ay>150) {tower++; pix_tower+=px; continue;}
        if(ay<6) {water++; continue;}
        if(ay<60&&(area2(r)>2000)) {island++; continue;}
        if(ay>20&&ay<120&&area2(r)<400) {palm++; continue;}
        other++;
    }
    printf("triangles=%d\n", n);
    printf("est. tower tris=%d  (%.0f%% of tri count, %.0f%% of est. pixels)\n", tower, 100.0*tower/n, 100.0*pix_tower/pix_total);
    printf("cloud=%d water=%d island=%d palm=%d other=%d\n", cloud,water,island,palm,other);
    printf("total est. pixel coverage (sum of tri areas in px) = %.0f vs 19200 screen px => overdraw x%.1f\n", pix_total, pix_total/19200.0);
    return 0;
}
