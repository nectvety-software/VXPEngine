#include "graphics/VxpCinematic2D.h"
#include <string.h>

namespace {
inline uint32_t xs32(uint32_t& s){
    if(!s)s=0xA341316Cu;
    s^=s<<13;s^=s>>17;s^=s<<5;return s;
}
inline uint16_t sub_sat(uint16_t v,uint16_t d){return d>=v?0:(uint16_t)(v-d);}
inline int16_t clamp16(int32_t v){
    if(v>32767)return 32767;if(v<-32768)return -32768;return (int16_t)v;
}
}

extern "C" {

void vxpe2d_cinematic_init(VxpeCinematic2D*fx,uint32_t seed){
    if(!fx)return;memset(fx,0,sizeof(*fx));fx->rng=seed?seed:0xC001D00Du;
}
void vxpe2d_cinematic_clear(VxpeCinematic2D*fx){
    if(!fx)return;uint32_t seed=fx->rng;memset(fx,0,sizeof(*fx));fx->rng=seed?seed:0xC001D00Du;
}
void vxpe2d_cinematic_shake(VxpeCinematic2D*fx,uint8_t amp,uint16_t dur){
    if(!fx||!amp||!dur)return;
    if(dur>fx->shake_left_ms||amp>=fx->shake_amplitude){
        fx->shake_amplitude=amp;fx->shake_left_ms=dur;fx->shake_total_ms=dur;
    }
}
void vxpe2d_cinematic_punch(VxpeCinematic2D*fx,int16_t xq8,int16_t yq8,uint16_t dur){
    if(!fx||!dur)return;fx->punch_x_q8=xq8;fx->punch_y_q8=yq8;
    fx->punch_left_ms=dur;fx->punch_total_ms=dur;
}
void vxpe2d_cinematic_hitstop(VxpeCinematic2D*fx,uint16_t dur){
    if(!fx||!dur)return;if(dur>fx->hitstop_left_ms)fx->hitstop_left_ms=dur;
}
uint16_t vxpe2d_cinematic_update(VxpeCinematic2D*fx,uint16_t dt){
    if(!fx)return dt;
    int32_t ox=0,oy=0;
    if(fx->shake_left_ms){
        uint32_t r=xs32(fx->rng),r2=xs32(fx->rng);
        uint32_t amp=fx->shake_amplitude;
        if(fx->shake_total_ms)amp=(amp*(uint32_t)fx->shake_left_ms)/fx->shake_total_ms;
        int32_t span=(int32_t)(amp*2u+1u);
        ox+=(int32_t)(r%(uint32_t)span)-(int32_t)amp;
        oy+=(int32_t)(r2%(uint32_t)span)-(int32_t)amp;
        fx->shake_left_ms=sub_sat(fx->shake_left_ms,dt);
        if(!fx->shake_left_ms)fx->shake_amplitude=0;
    }
    if(fx->punch_left_ms){
        uint32_t q16=fx->punch_total_ms?
            ((uint32_t)fx->punch_left_ms<<16)/fx->punch_total_ms:0;
        ox+=(int32_t)(((int64_t)fx->punch_x_q8*q16)>>24);
        oy+=(int32_t)(((int64_t)fx->punch_y_q8*q16)>>24);
        fx->punch_left_ms=sub_sat(fx->punch_left_ms,dt);
    }
    fx->offset_x=clamp16(ox);fx->offset_y=clamp16(oy);
    if(fx->hitstop_left_ms){
        fx->hitstop_left_ms=sub_sat(fx->hitstop_left_ms,dt);
        return 0;
    }
    return dt;
}
void vxpe2d_cinematic_offset(const VxpeCinematic2D*fx,int16_t*out_x,int16_t*out_y){
    if(out_x)*out_x=fx?fx->offset_x:0;if(out_y)*out_y=fx?fx->offset_y:0;
}
uint8_t vxpe2d_cinematic_is_hitstopped(const VxpeCinematic2D*fx){
    return (fx&&fx->hitstop_left_ms)?1u:0u;
}

void vxpe2d_cinematic_shift_rgb565(uint16_t*fb,int fw,int fh,int clip_h,
                                      int ox,int oy,uint16_t clear565){
    if(!fb||fw<=0||fh<=0||(!ox&&!oy))return;
    int h=clip_h>0?clip_h:fh;if(h>fh)h=fh;
    if(ox>=fw||ox<=-fw||oy>=h||oy<=-h){
        for(int y=0;y<h;++y)for(int x=0;x<fw;++x)fb[y*fw+x]=clear565;
        return;
    }
    int ys,ye,ystep;
    if(oy>0){ys=h-1;ye=-1;ystep=-1;}else{ys=0;ye=h;ystep=1;}
    for(int y=ys;y!=ye;y+=ystep){
        int sy=y-oy;uint16_t*dst=fb+y*fw;
        if(sy<0||sy>=h){
            for(int x=0;x<fw;++x)dst[x]=clear565;
            continue;
        }
        uint16_t*src=fb+sy*fw;
        if(ox>0){
            memmove(dst+ox,src,(size_t)(fw-ox)*sizeof(uint16_t));
            for(int x=0;x<ox;++x)dst[x]=clear565;
        }else if(ox<0){
            int n=fw+ox;
            memmove(dst,src-ox,(size_t)n*sizeof(uint16_t));
            for(int x=n;x<fw;++x)dst[x]=clear565;
        }else if(dst!=src){
            memmove(dst,src,(size_t)fw*sizeof(uint16_t));
        }
    }
}

} // extern "C"
