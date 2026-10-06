#include "graphics/VxpVfx2D.h"

#include <stddef.h>
#include <string.h>

namespace {

inline int clamp_i(int v,int lo,int hi){return v<lo?lo:(v>hi?hi:v);}
inline int abs_i(int v){return v<0?-v:v;}

inline uint16_t alpha565(uint16_t d,uint16_t s,uint8_t a){
    if(a==0)return d;if(a==255)return s;
    const uint32_t inv=255u-a;
    const uint32_t dr=(d>>11)&31u,dg=(d>>5)&63u,db=d&31u;
    const uint32_t sr=(s>>11)&31u,sg=(s>>5)&63u,sb=s&31u;
    return (uint16_t)((((sr*a+dr*inv+127u)/255u)<<11)|
                      (((sg*a+dg*inv+127u)/255u)<<5)|
                      ((sb*a+db*inv+127u)/255u));
}
inline uint16_t add565(uint16_t d,uint16_t s,uint8_t a){
    uint32_t dr=(d>>11)&31u,dg=(d>>5)&63u,db=d&31u;
    dr+=(((s>>11)&31u)*a)/255u;dg+=(((s>>5)&63u)*a)/255u;db+=(s&31u)*a/255u;
    if(dr>31u)dr=31u;if(dg>63u)dg=63u;if(db>31u)db=31u;
    return (uint16_t)((dr<<11)|(dg<<5)|db);
}
inline uint16_t mul565(uint16_t d,uint16_t s,uint8_t a){
    if(a==0)return d;
    const uint32_t dr=(d>>11)&31u,dg=(d>>5)&63u,db=d&31u;
    const uint32_t sr=(s>>11)&31u,sg=(s>>5)&63u,sb=s&31u;
    uint16_t m=(uint16_t)((((dr*sr+15u)/31u)<<11)|(((dg*sg+31u)/63u)<<5)|((db*sb+15u)/31u));
    return alpha565(d,m,a);
}
inline uint16_t blend565(uint16_t d,uint16_t s,uint8_t a,uint8_t mode){
    if(mode==VXPE_BLEND_ADD)return add565(d,s,a);
    if(mode==VXPE_BLEND_MULTIPLY)return mul565(d,s,a);
    return alpha565(d,s,a);
}
inline uint16_t tint565(uint16_t s,uint16_t t){
    if(t==0xFFFFu)return s;
    uint32_t sr=(s>>11)&31u,sg=(s>>5)&63u,sb=s&31u;
    uint32_t tr=(t>>11)&31u,tg=(t>>5)&63u,tb=t&31u;
    return (uint16_t)((((sr*tr+15u)/31u)<<11)|(((sg*tg+31u)/63u)<<5)|((sb*tb+15u)/31u));
}
inline uint16_t lerp565(uint16_t a,uint16_t b,uint8_t t){
    uint32_t inv=255u-t;
    uint32_t ar=(a>>11)&31u,ag=(a>>5)&63u,ab=a&31u;
    uint32_t br=(b>>11)&31u,bg=(b>>5)&63u,bb=b&31u;
    return (uint16_t)((((ar*inv+br*t+127u)/255u)<<11)|
                      (((ag*inv+bg*t+127u)/255u)<<5)|
                      ((ab*inv+bb*t+127u)/255u));
}
inline uint8_t src_alpha(const VxpeSpriteA8*s,int sx,int sy){
    if(!s||sx<0||sy<0||sx>=s->width||sy>=s->height)return 0;
    if(s->opaque||!s->alpha)return 255u;
    int as=s->alpha_stride?s->alpha_stride:s->width;
    return s->alpha[sy*as+sx];
}
inline void put(uint16_t*fb,int fw,int fh,int x,int y,uint16_t c,uint8_t a,uint8_t mode){
    if(!fb||x<0||y<0||x>=fw||y>=fh||!a)return;
    uint16_t& d=fb[y*fw+x];d=blend565(d,c,a,mode);
}
void disc(uint16_t*fb,int fw,int fh,int cx,int cy,int r,uint16_t c,uint8_t a,uint8_t mode){
    if(r<=0){put(fb,fw,fh,cx,cy,c,a,mode);return;}
    int r2=r*r;
    for(int y=-r;y<=r;++y)for(int x=-r;x<=r;++x)if(x*x+y*y<=r2)put(fb,fw,fh,cx+x,cy+y,c,a,mode);
}
void thick_line(uint16_t*fb,int fw,int fh,int x0,int y0,int x1,int y1,
                int width,uint16_t c,uint8_t a,uint8_t mode){
    int dx=abs_i(x1-x0),sx=x0<x1?1:-1,dy=-abs_i(y1-y0),sy=y0<y1?1:-1,err=dx+dy;
    int r=width>1?width/2:0;
    for(;;){
        disc(fb,fw,fh,x0,y0,r,c,a,mode);
        if(x0==x1&&y0==y1)break;
        int e2=err<<1;if(e2>=dy){err+=dy;x0+=sx;}if(e2<=dx){err+=dx;y0+=sy;}
    }
}

static const int8_t kSin64[64]={
0,12,25,37,49,60,71,81,90,98,106,112,117,122,125,126,
127,126,125,122,117,112,106,98,90,81,71,60,49,37,25,12,
0,-12,-25,-37,-49,-60,-71,-81,-90,-98,-106,-112,-117,-122,-125,-126,
-127,-126,-125,-122,-117,-112,-106,-98,-90,-81,-71,-60,-49,-37,-25,-12};

static const int16_t kDir16[16][2]={
{1024,0},{946,392},{724,724},{392,946},{0,1024},{-392,946},{-724,724},{-946,392},
{-1024,0},{-946,-392},{-724,-724},{-392,-946},{0,-1024},{392,-946},{724,-724},{946,-392}};

} // namespace

extern "C" {
void vxpe2d_trail_init(VxpeTrail2D* t,uint16_t lifetime_ms,uint16_t head_color,
                       uint16_t tail_color,uint8_t head_width,uint8_t tail_width,
                       uint8_t alpha,uint8_t blend_mode){
    if(!t)return;memset(t,0,sizeof(*t));
    t->lifetime_ms=lifetime_ms?lifetime_ms:1;t->head_color=head_color;t->tail_color=tail_color;
    t->head_width=head_width?head_width:1;t->tail_width=tail_width?tail_width:1;
    t->alpha=alpha;t->blend=blend_mode;
}
void vxpe2d_trail_reset(VxpeTrail2D* t){if(t)t->count=0;}
void vxpe2d_trail_push(VxpeTrail2D* t,int x,int y){
    if(!t)return;
    if(t->count&&t->points[t->count-1].x==x&&t->points[t->count-1].y==y)return;
    if(t->count>=VXPE_TRAIL_MAX_POINTS){
        memmove(&t->points[0],&t->points[1],sizeof(VxpeTrailPoint)*(VXPE_TRAIL_MAX_POINTS-1));
        t->count=VXPE_TRAIL_MAX_POINTS-1;
    }
    VxpeTrailPoint& p=t->points[t->count++];p.x=(int16_t)x;p.y=(int16_t)y;p.age_ms=0;
}
void vxpe2d_trail_update(VxpeTrail2D* t,uint16_t dt){
    if(!t||!t->count)return;
    uint16_t out=0;
    for(uint16_t i=0;i<t->count;++i){
        uint32_t age=(uint32_t)t->points[i].age_ms+dt;
        if(age<t->lifetime_ms){t->points[i].age_ms=(uint16_t)age;t->points[out++]=t->points[i];}
    }
    t->count=out;
}
void vxpe2d_trail_draw(const VxpeTrail2D* t,uint16_t*fb,int fw,int fh){
    if(!t||!fb||t->count<2||!t->alpha)return;
    for(uint16_t i=1;i<t->count;++i){
        const VxpeTrailPoint& a=t->points[i-1];const VxpeTrailPoint& b=t->points[i];
        uint16_t age=(uint16_t)(((uint32_t)a.age_ms+b.age_ms)>>1);
        uint32_t life=t->lifetime_ms?t->lifetime_ms:1;
        uint8_t fade=(uint8_t)(age>=life?0u:255u-((uint32_t)age*255u/life));
        uint8_t pos=(uint8_t)((uint32_t)i*255u/(t->count-1));
        uint8_t alpha=(uint8_t)((uint16_t)t->alpha*fade/255u);
        int width=t->tail_width+((int)(t->head_width-t->tail_width)*pos)/255;
        if(width<1)width=1;
        uint16_t color=lerp565(t->tail_color,t->head_color,pos);
        thick_line(fb,fw,fh,a.x,a.y,b.x,b.y,width,color,alpha,t->blend);
    }
}
void vxpe2d_draw_beam(uint16_t*fb,int fw,int fh,int x0,int y0,int x1,int y1,
                      const VxpeBeamStyle* s){
    if(!fb||!s||!s->alpha)return;
    if(s->outer_width)thick_line(fb,fw,fh,x0,y0,x1,y1,s->outer_width,s->outer_color,
                                 (uint8_t)(s->alpha>>1),s->blend);
    if(s->core_width)thick_line(fb,fw,fh,x0,y0,x1,y1,s->core_width,s->core_color,
                                s->alpha,s->blend);
    if(s->hot_width)thick_line(fb,fw,fh,x0,y0,x1,y1,s->hot_width,s->hot_color,
                               s->alpha,s->blend);
}
void vxpe2d_draw_ring(uint16_t*fb,int fw,int fh,int cx,int cy,int radius,int thickness,
                      uint16_t color,uint8_t alpha,uint8_t mode){
    if(!fb||radius<=0||thickness<=0||!alpha)return;
    int ro=radius,ri=radius-thickness;if(ri<0)ri=0;
    int ro2=ro*ro,ri2=ri*ri;
    int x0=clamp_i(cx-ro,0,fw-1),x1=clamp_i(cx+ro,0,fw-1);
    int y0=clamp_i(cy-ro,0,fh-1),y1=clamp_i(cy+ro,0,fh-1);
    for(int y=y0;y<=y1;++y){int dy=y-cy;for(int x=x0;x<=x1;++x){
        int dx=x-cx,d2=dx*dx+dy*dy;if(d2<=ro2&&d2>=ri2)put(fb,fw,fh,x,y,color,alpha,mode);
    }}
}
void vxpe2d_draw_burst(uint16_t*fb,int fw,int fh,int cx,int cy,int inner_r,int outer_r,
                       uint8_t rays,uint8_t phase,uint16_t color,uint8_t alpha,uint8_t mode){
    if(!fb||outer_r<=inner_r||!alpha)return;
    if(rays<4)rays=4;if(rays>16)rays=16;
    for(uint8_t i=0;i<rays;++i){
        uint8_t idx=(uint8_t)((phase+((uint16_t)i*16u/rays))&15u);
        int dx=kDir16[idx][0],dy=kDir16[idx][1];
        int x0=cx+((dx*inner_r)>>10),y0=cy+((dy*inner_r)>>10);
        int x1=cx+((dx*outer_r)>>10),y1=cy+((dy*outer_r)>>10);
        thick_line(fb,fw,fh,x0,y0,x1,y1,1,color,alpha,mode);
    }
}
void vxpe2d_blit_a8_rot_q14(uint16_t*fb,int fw,int fh,const VxpeSpriteA8*s,
                             const VxpeBlit565*op,int16_t sin_q14,int16_t cos_q14){
    if(!fb||!s||!op||!s->pixels||!op->alpha)return;
    int sx0=op->src.x,sy0=op->src.y,sw=op->src.w,sh=op->src.h;
    if(sw<=0||sh<=0){sx0=0;sy0=0;sw=s->width;sh=s->height;}
    if(sx0<0){sw+=sx0;sx0=0;}if(sy0<0){sh+=sy0;sy0=0;}
    if(sx0>=s->width||sy0>=s->height)return;
    if(sx0+sw>s->width)sw=s->width-sx0;if(sy0+sh>s->height)sh=s->height-sy0;
    if(sw<=0||sh<=0)return;
    int dw=op->dst_w?op->dst_w:sw,dh=op->dst_h?op->dst_h:sh;if(dw<=0||dh<=0)return;
    int cx=op->dst_x+dw/2,cy=op->dst_y+dh/2;
    int rad=(dw+dh+1)/2;
    int x0=clamp_i(cx-rad,0,fw-1),x1=clamp_i(cx+rad,0,fw-1);
    int y0=clamp_i(cy-rad,0,fh-1),y1=clamp_i(cy+rad,0,fh-1);
    int stride=s->stride?s->stride:s->width;
    for(int y=y0;y<=y1;++y)for(int x=x0;x<=x1;++x){
        int dx=x-cx,dy=y-cy;
        int rx=(dx*cos_q14+dy*sin_q14)>>14;
        int ry=(-dx*sin_q14+dy*cos_q14)>>14;
        int lx=rx+dw/2,ly=ry+dh/2;if(lx<0||ly<0||lx>=dw||ly>=dh)continue;
        int sxr=(lx*sw)/dw,syr=(ly*sh)/dh;
        if(op->flip_x)sxr=sw-1-sxr;if(op->flip_y)syr=sh-1-syr;
        int sx=sx0+sxr,sy=sy0+syr;uint8_t a=src_alpha(s,sx,sy);if(!a)continue;
        a=(uint8_t)((uint16_t)a*op->alpha/255u);if(!a)continue;
        uint16_t c=tint565(s->pixels[sy*stride+sx],op->tint565);
        put(fb,fw,fh,x,y,c,a,op->blend);
    }
}
void vxpe2d_blit_a8_wave_x(uint16_t*fb,int fw,int fh,const VxpeSpriteA8*s,
                           const VxpeBlit565*op,uint8_t phase,uint8_t amp,uint8_t wave_shift){
    if(!fb||!s||!op||!s->pixels||!op->alpha)return;
    int sx0=op->src.x,sy0=op->src.y,sw=op->src.w,sh=op->src.h;
    if(sw<=0||sh<=0){sx0=0;sy0=0;sw=s->width;sh=s->height;}
    if(sx0<0){sw+=sx0;sx0=0;}if(sy0<0){sh+=sy0;sy0=0;}
    if(sx0>=s->width||sy0>=s->height)return;
    if(sx0+sw>s->width)sw=s->width-sx0;if(sy0+sh>s->height)sh=s->height-sy0;
    if(sw<=0||sh<=0)return;
    int dw=op->dst_w?op->dst_w:sw,dh=op->dst_h?op->dst_h:sh;if(dw<=0||dh<=0)return;
    if(wave_shift>6)wave_shift=6;
    int stride=s->stride?s->stride:s->width;
    int y0=clamp_i(op->dst_y,0,fh),y1=clamp_i(op->dst_y+dh,0,fh);
    for(int y=y0;y<y1;++y){
        int ly=y-op->dst_y,syr=(ly*sh)/dh;if(syr>=sh)syr=sh-1;if(op->flip_y)syr=sh-1-syr;
        int sy=sy0+syr;
        uint8_t wave_idx=(uint8_t)(((phase>>2)+(ly>>wave_shift))&63u);
        int shift=(kSin64[wave_idx]*(int)amp)>>7;
        for(int lx=0;lx<dw;++lx){
            int x=op->dst_x+lx+shift;if(x<0||x>=fw)continue;
            int sxr=(lx*sw)/dw;if(sxr>=sw)sxr=sw-1;if(op->flip_x)sxr=sw-1-sxr;
            int sx=sx0+sxr;uint8_t a=src_alpha(s,sx,sy);if(!a)continue;
            a=(uint8_t)((uint16_t)a*op->alpha/255u);if(!a)continue;
            uint16_t c=tint565(s->pixels[sy*stride+sx],op->tint565);
            put(fb,fw,fh,x,y,c,a,op->blend);
        }
    }
}

void vxpe2d_blit_a8_parallax(uint16_t*fb,int fw,int fh,const VxpeSpriteA8*s,
                                int32_t camx_q8,int32_t camy_q8,
                                uint16_t fx_q8,uint16_t fy_q8,
                                int offx,int offy,uint8_t alpha,uint8_t blend,
                                uint8_t repeat_x,uint8_t repeat_y,int max_tiles){
    if(!fb||!s||!s->pixels||s->width==0||s->height==0||!alpha)return;
    if(max_tiles<=0)max_tiles=64;
    int shiftx=(int)(((int64_t)camx_q8*fx_q8)>>16);
    int shifty=(int)(((int64_t)camy_q8*fy_q8)>>16);
    int tw=s->width,th=s->height;
    int startx=offx-shiftx,starty=offy-shifty;
    if(repeat_x){int m=startx%tw;if(m>0)m-=tw;startx=m;}
    if(repeat_y){int m=starty%th;if(m>0)m-=th;starty=m;}
    int y_first=repeat_y?starty:offy-shifty;
    int drawn=0;
    for(int y=y_first;y<fh&&drawn<max_tiles;y+=repeat_y?th:fh+th){
        int x_first=repeat_x?startx:offx-shiftx;
        for(int x=x_first;x<fw&&drawn<max_tiles;x+=repeat_x?tw:fw+tw){
            VxpeBlit565 op={};op.src.x=0;op.src.y=0;op.src.w=(int16_t)tw;op.src.h=(int16_t)th;
            op.dst_x=(int16_t)x;op.dst_y=(int16_t)y;op.dst_w=(uint16_t)tw;op.dst_h=(uint16_t)th;
            op.tint565=0xFFFFu;op.alpha=alpha;op.blend=blend;
            vxpe2d_blit_a8(fb,fw,fh,s,&op);++drawn;
            if(!repeat_x)break;
        }
        if(!repeat_y)break;
    }
}

} // extern "C"
