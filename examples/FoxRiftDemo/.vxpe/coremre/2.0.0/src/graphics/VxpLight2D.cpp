#include "graphics/VxpLight2D.h"
#include <string.h>

namespace {
inline int clamp_i(int v,int lo,int hi){return v<lo?lo:(v>hi?hi:v);}
inline int abs_i(int v){return v<0?-v:v;}

inline uint16_t add565(uint16_t d,uint16_t s,uint8_t a){
    uint32_t dr=(d>>11)&31u,dg=(d>>5)&63u,db=d&31u;
    dr+=(((s>>11)&31u)*a)/255u;
    dg+=(((s>>5)&63u)*a)/255u;
    db+=(s&31u)*a/255u;
    if(dr>31u)dr=31u;if(dg>63u)dg=63u;if(db>31u)db=31u;
    return (uint16_t)((dr<<11)|(dg<<5)|db);
}
inline uint16_t scale565(uint16_t c,uint8_t a){
    uint32_t r=((c>>11)&31u)*a/255u;
    uint32_t g=((c>>5)&63u)*a/255u;
    uint32_t b=(c&31u)*a/255u;
    return (uint16_t)((r<<11)|(g<<5)|b);
}
inline void add_cell(VxpeLightmap2D*lm,int x,int y,uint16_t c,uint8_t a){
    if(!lm||x<0||y<0||x>=lm->width||y>=lm->height||!a)return;
    uint16_t& d=lm->cells[y*lm->width+x];
    d=add565(d,c,a);
}
void cell_disc(VxpeLightmap2D*lm,int cx,int cy,int r,uint16_t c,uint8_t a){
    if(r<=0){add_cell(lm,cx,cy,c,a);return;}
    int r2=r*r;
    for(int y=-r;y<=r;++y)for(int x=-r;x<=r;++x){
        int d2=x*x+y*y;if(d2>r2)continue;
        uint8_t aa=(uint8_t)((uint32_t)a*(uint32_t)(r2-d2)/(uint32_t)r2);
        if(aa)add_cell(lm,cx+x,cy+y,c,aa);
    }
}
}

extern "C" {

int vxpe2d_lightmap_init(VxpeLightmap2D*lm,uint16_t mw,uint16_t mh,uint16_t sw,uint16_t sh){
    if(!lm||mw==0||mh==0||sw==0||sh==0||(uint32_t)mw*mh>VXPE_LIGHTMAP_MAX_PIXELS)return 0;
    memset(lm,0,sizeof(*lm));lm->width=mw;lm->height=mh;lm->screen_w=sw;lm->screen_h=sh;lm->valid=1;
    return 1;
}
void vxpe2d_lightmap_clear(VxpeLightmap2D*lm){
    if(!lm||!lm->valid)return;
    memset(lm->cells,0,(size_t)lm->width*lm->height*sizeof(uint16_t));
}
void vxpe2d_lightmap_add_radial(VxpeLightmap2D*lm,int sx,int sy,int sr,
                                uint16_t color,uint8_t intensity){
    if(!lm||!lm->valid||sr<=0||!intensity)return;
    int cx=sx*lm->width/lm->screen_w,cy=sy*lm->height/lm->screen_h;
    int rx=sr*lm->width/lm->screen_w,ry=sr*lm->height/lm->screen_h;
    if(rx<1)rx=1;if(ry<1)ry=1;
    int x0=clamp_i(cx-rx,0,lm->width-1),x1=clamp_i(cx+rx,0,lm->width-1);
    int y0=clamp_i(cy-ry,0,lm->height-1),y1=clamp_i(cy+ry,0,lm->height-1);
    int64_t rr=(int64_t)rx*rx*ry*ry;
    for(int y=y0;y<=y1;++y){int dy=y-cy;for(int x=x0;x<=x1;++x){
        int dx=x-cx;
        int64_t d=(int64_t)dx*dx*ry*ry+(int64_t)dy*dy*rx*rx;
        if(d>=rr)continue;
        uint8_t a=(uint8_t)(((uint64_t)(rr-d)*intensity)/(uint64_t)rr);
        add_cell(lm,x,y,color,a);
    }}
}
void vxpe2d_lightmap_add_beam(VxpeLightmap2D*lm,int x0,int y0,int x1,int y1,
                              int radius_px,uint16_t color,uint8_t intensity){
    if(!lm||!lm->valid||!intensity)return;
    int ax=x0*lm->width/lm->screen_w,ay=y0*lm->height/lm->screen_h;
    int bx=x1*lm->width/lm->screen_w,by=y1*lm->height/lm->screen_h;
    int r=radius_px*lm->width/lm->screen_w;if(r<1)r=1;
    int dx=abs_i(bx-ax),sx=ax<bx?1:-1,dy=-abs_i(by-ay),sy=ay<by?1:-1,err=dx+dy;
    for(;;){
        cell_disc(lm,ax,ay,r,color,intensity);
        if(ax==bx&&ay==by)break;
        int e2=err<<1;if(e2>=dy){err+=dy;ax+=sx;}if(e2<=dx){err+=dx;ay+=sy;}
    }
}
void vxpe2d_lightmap_composite_add(const VxpeLightmap2D*lm,uint16_t*fb,int fw,int fh,
                                   uint8_t global_alpha,int clip_h){
    if(!lm||!lm->valid||!fb||fw<=0||fh<=0||!global_alpha)return;
    int limit=clip_h>0?clip_h:fh;if(limit>fh)limit=fh;
    int exact_x=(lm->screen_w%lm->width)==0,exact_y=(lm->screen_h%lm->height)==0;
    int bw=exact_x?lm->screen_w/lm->width:0,bh=exact_y?lm->screen_h/lm->height:0;
    for(int my=0;my<lm->height;++my)for(int mx=0;mx<lm->width;++mx){
        uint16_t c=lm->cells[my*lm->width+mx];if(!c)continue;
        int x0=exact_x?mx*bw:mx*lm->screen_w/lm->width;
        int x1=exact_x?x0+bw:(mx+1)*lm->screen_w/lm->width;
        int y0=exact_y?my*bh:my*lm->screen_h/lm->height;
        int y1=exact_y?y0+bh:(my+1)*lm->screen_h/lm->height;
        x0=clamp_i(x0,0,fw);x1=clamp_i(x1,0,fw);y0=clamp_i(y0,0,limit);y1=clamp_i(y1,0,limit);
        for(int y=y0;y<y1;++y){uint16_t*row=fb+y*fw;for(int x=x0;x<x1;++x)row[x]=add565(row[x],c,global_alpha);}
    }
}

} // extern "C"
