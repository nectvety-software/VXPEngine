/* Throwaway probe: measure the real triangle geometry/lighting the demo submits.
 * Built by renaming the demo's quad/tri helpers to recording shims. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

struct Rec { int32_t ax,ay,az,bx,by,bz,cx,cy,cz; uint8_t light; };
static Rec g_rec[200000];
static int g_n=0;
static int g_overflow=0;

extern "C" void probe_reset(){ g_n=0; g_overflow=0; }
extern "C" int probe_count(){ return g_n; }
extern "C" int probe_overflow(){ return g_overflow; }
extern "C" Rec* probe_at(int i){ return &g_rec[i]; }
extern "C" void probe_push(int32_t ax,int32_t ay,int32_t az,
                          int32_t bx,int32_t by,int32_t bz,
                          int32_t cx,int32_t cy,int32_t cz,uint8_t light){
    if(g_n>=200000){ g_overflow=1; return; }
    Rec& r=g_rec[g_n++];
    r.ax=ax;r.ay=ay;r.az=az; r.bx=bx;r.by=by;r.bz=bz; r.cx=cx;r.cy=cy;r.cz=cz; r.light=light;
}
