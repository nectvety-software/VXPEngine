#include "scene.h"
#include <stdio.h>
#include <string.h>
#include <math.h>

extern "C" void probe_reset();
extern "C" int probe_count();
extern "C" int probe_overflow();
struct Rec { int32_t ax,ay,az,bx,by,bz,cx,cy,cz; uint8_t light; };
extern "C" Rec* probe_at(int i);

static double area2(const Rec& r){
    long long ux=r.bx-r.ax, uy=r.by-r.ay, uz=r.bz-r.az;
    long long vx=r.cx-r.ax, vy=r.cy-r.ay, vz=r.cz-r.az;
    double cx=(double)uy*vz-(double)uz*vy;
    double cy=(double)uz*vx-(double)ux*vz;
    double cz=(double)ux*vy-(double)uy*vx;
    return 0.5*sqrt(cx*cx+cy*cy+cz*cz);
}

int main(){
    static PromisedFuture g;
    g.input(5);              /* enter city: mode 1 */
    probe_reset();
    uint16_t fb[240*320];
    g.draw(fb);
    int n=probe_count();
    printf("triangles submitted per frame: %d  overflow=%d\n", n, probe_overflow());

    double total=0; double minA=1e18,maxA=0;
    int lightHist[256]; memset(lightHist,0,sizeof(lightHist));
    /* screen-space area buckets: need projection, so approximate with world area first */
    double areaHist[10]; memset(areaHist,0,sizeof(areaHist));
    for(int i=0;i<n;++i){
        Rec& r=*probe_at(i);
        double a=area2(r);
        total+=a;
        if(a<minA)minA=a;
        if(a>maxA)maxA=a;
        lightHist[r.light]++;
        /* bucket world area in log decades */
        int b = a<1?0 : a<4?1 : a<16?2 : a<64?3 : a<256?4 : a<1024?5 : a<4096?6 : a<16384?7 : a<65536?8 : 9;
        areaHist[b]+=1;
    }
    printf("world-area  sum=%.0f  min=%.3f  max=%.0f  mean=%.2f\n", total, minA, maxA, total/(n?n:1));
    const char* bl[10]={"<1","1-4","4-16","16-64","64-256","256-1K","1K-4K","4K-16K","16K-64K",">=64K"};
    printf("world-area buckets:\n");
    for(int i=0;i<10;++i) if(areaHist[i]>0) printf("  %-8s %8.0f  (%.1f%%)\n", bl[i], areaHist[i], 100.0*areaHist[i]/n);

    printf("light value histogram (only used values):\n");
    int distinct=0;
    for(int i=0;i<256;++i){
        if(!lightHist[i])continue;
        distinct++;
        if(distinct<=40) printf("  light=%-4d count=%-7d\n", i, lightHist[i]);
    }
    printf("distinct light values used: %d\n", distinct);

    /* how many triangles would be sub-pixel at 120x160? focal 96, near 5. */
    /* screen area ~ world_area * (focal/dist)^2 ; assume dist ~ |centroid z - camZ| */
    int subpx=0, tiny=0;
    for(int i=0;i<n;++i){
        Rec& r=*probe_at(i);
        double cx=(r.ax+r.bx+r.cx)/3.0, cy=(r.ay+r.by+r.cy)/3.0, cz=(r.az+r.bz+r.cz)/3.0;
        double dz=cz-24.0; if(dz<5)dz=5;
        double wc=area2(r);
        double sc=96.0/dz;
        double pxarea=wc*sc*sc;
        if(pxarea<1.0)subpx++;
        if(pxarea<4.0)tiny++;
    }
    printf("estimated sub-pixel(<1px^2) tris: %d (%.1f%%)\n", subpx, 100.0*subpx/n);
    printf("estimated very-tiny(<4px^2) tris: %d (%.1f%%)\n", tiny, 100.0*tiny/n);
    return 0;
}
