#include "graphics/VxpSpriteFx.h"

#include <stddef.h>
#include <string.h>

namespace {

inline int clamp_i(int v, int lo, int hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

inline uint16_t tint565_local(uint16_t src, uint16_t tint) {
    if (tint == 0xFFFFu) return src;
    const uint32_t sr=(src>>11)&31u, sg=(src>>5)&63u, sb=src&31u;
    const uint32_t tr=(tint>>11)&31u, tg=(tint>>5)&63u, tb=tint&31u;
    return static_cast<uint16_t>(
        (((sr*tr+15u)/31u)<<11) |
        (((sg*tg+31u)/63u)<<5) |
        ((sb*tb+15u)/31u));
}

inline uint16_t alpha565_local(uint16_t dst, uint16_t src, uint8_t a) {
    if (a==0) return dst;
    if (a==255) return src;
    const uint32_t inv=255u-a;
    const uint32_t dr=(dst>>11)&31u,dg=(dst>>5)&63u,db=dst&31u;
    const uint32_t sr=(src>>11)&31u,sg=(src>>5)&63u,sb=src&31u;
    return static_cast<uint16_t>(
        (((sr*a+dr*inv+127u)/255u)<<11) |
        (((sg*a+dg*inv+127u)/255u)<<5) |
        ((sb*a+db*inv+127u)/255u));
}

inline uint16_t add565_local(uint16_t dst, uint16_t src, uint8_t a) {
    uint32_t dr=(dst>>11)&31u,dg=(dst>>5)&63u,db=dst&31u;
    dr += (((src>>11)&31u)*a)/255u;
    dg += (((src>>5)&63u)*a)/255u;
    db += ((src&31u)*a)/255u;
    if(dr>31u)dr=31u;
    if(dg>63u)dg=63u;
    if(db>31u)db=31u;
    return static_cast<uint16_t>((dr<<11)|(dg<<5)|db);
}

inline uint16_t multiply565_local(uint16_t dst,uint16_t src,uint8_t a) {
    if(a==0)return dst;
    const uint32_t dr=(dst>>11)&31u,dg=(dst>>5)&63u,db=dst&31u;
    const uint32_t sr=(src>>11)&31u,sg=(src>>5)&63u,sb=src&31u;
    const uint16_t m=static_cast<uint16_t>(
        (((dr*sr+15u)/31u)<<11) |
        (((dg*sg+31u)/63u)<<5) |
        ((db*sb+15u)/31u));
    return alpha565_local(dst,m,a);
}

inline uint16_t blend565_local(uint16_t dst,uint16_t src,uint8_t a,uint8_t mode){
    if(mode==VXPE_BLEND_ADD)return add565_local(dst,src,a);
    if(mode==VXPE_BLEND_MULTIPLY)return multiply565_local(dst,src,a);
    return alpha565_local(dst,src,a);
}

struct MapInfo {
    int sx0,sy0,sw,sh,dw,dh,stride,astride;
};

inline int build_map(const VxpeSpriteA8* s,const VxpeBlit565* op,MapInfo& m){
    if(!s||!op||!s->pixels||s->width==0||s->height==0||op->alpha==0)return 0;
    m.sx0=op->src.x;m.sy0=op->src.y;m.sw=op->src.w;m.sh=op->src.h;
    if(m.sw<=0||m.sh<=0){m.sx0=0;m.sy0=0;m.sw=s->width;m.sh=s->height;}
    if(m.sx0<0){m.sw+=m.sx0;m.sx0=0;} if(m.sy0<0){m.sh+=m.sy0;m.sy0=0;}
    if(m.sx0>=s->width||m.sy0>=s->height)return 0;
    if(m.sx0+m.sw>s->width)m.sw=s->width-m.sx0;
    if(m.sy0+m.sh>s->height)m.sh=s->height-m.sy0;
    if(m.sw<=0||m.sh<=0)return 0;
    m.dw=op->dst_w?op->dst_w:m.sw;m.dh=op->dst_h?op->dst_h:m.sh;
    if(m.dw<=0||m.dh<=0)return 0;
    m.stride=s->stride?s->stride:s->width;
    m.astride=s->alpha_stride?s->alpha_stride:s->width;
    return 1;
}

inline uint8_t alpha_at_source(const VxpeSpriteA8* s,const MapInfo&m,int sx,int sy){
    if(sx<0||sy<0||sx>=s->width||sy>=s->height)return 0;
    return (s->opaque||s->alpha==nullptr)?255u:s->alpha[sy*m.astride+sx];
}

inline void map_rel(const VxpeBlit565* op,const MapInfo& m,int lx,int ly,int& sxr,int& syr){
    int ux=lx,uy=ly;
    if(op->flip_y)uy=m.dh-1-uy;
    if(op->flip_x)ux=m.dw-1-ux;
    if(op->flip_d){
        sxr=(uy*m.sw)/m.dh;
        syr=(ux*m.sh)/m.dw;
    }else{
        sxr=(ux*m.sw)/m.dw;
        syr=(uy*m.sh)/m.dh;
    }
    if(sxr>=m.sw)sxr=m.sw-1;
    if(syr>=m.sh)syr=m.sh-1;
}

inline uint8_t coverage_at_dest(const VxpeSpriteA8* s,const VxpeBlit565* op,
                                const MapInfo&m,int dx,int dy){
    int lx=dx-op->dst_x,ly=dy-op->dst_y;
    if(lx<0||ly<0||lx>=m.dw||ly>=m.dh)return 0;
    int sxr,syr;map_rel(op,m,lx,ly,sxr,syr);
    return alpha_at_source(s,m,m.sx0+sxr,m.sy0+syr);
}

inline uint8_t spread_coverage(const VxpeSpriteA8*s,const VxpeBlit565*op,
                               const MapInfo&m,int x,int y,int r){
    uint8_t a=coverage_at_dest(s,op,m,x,y);
    if(r<=0)return a;
    const int ox[8]={-1,1,0,0,-1,1,-1,1};
    const int oy[8]={0,0,-1,1,-1,-1,1,1};
    for(int i=0;i<8;++i){
        uint8_t q=coverage_at_dest(s,op,m,x+ox[i]*r,y+oy[i]*r);
        if(q>a)a=q;
    }
    if(r>1){
        int h=(r+1)>>1;
        for(int i=0;i<4;++i){
            uint8_t q=coverage_at_dest(s,op,m,x+ox[i]*h,y+oy[i]*h);
            if(q>a)a=q;
        }
    }
    return a;
}

inline uint8_t mul255_u16(uint16_t v){
    uint16_t t=(uint16_t)(v+128u);
    return (uint8_t)((t+(t>>8))>>8);
}

inline uint8_t mul_alpha3(uint8_t a,uint8_t b,uint8_t c){
    uint8_t ab=mul255_u16((uint16_t)a*(uint16_t)b);
    return mul255_u16((uint16_t)ab*(uint16_t)c);
}

inline uint8_t direct_alpha_local(const VxpeSpriteA8* s,const MapInfo&m,
                                  const VxpeBlit565* op,int lx,int ly){
    if(lx<0||ly<0||lx>=m.sw||ly>=m.sh)return 0;
    int sxr,syr;map_rel(op,m,lx,ly,sxr,syr);
    return alpha_at_source(s,m,m.sx0+sxr,m.sy0+syr);
}

inline uint8_t direct_spread(const VxpeSpriteA8*s,const MapInfo&m,
                             const VxpeBlit565*op,int lx,int ly,int r){
    uint8_t a=direct_alpha_local(s,m,op,lx,ly);
    if(r<=0)return a;
    const int ox[8]={-1,1,0,0,-1,1,-1,1};
    const int oy[8]={0,0,-1,1,-1,-1,1,1};
    for(int i=0;i<8;++i){
        uint8_t q=direct_alpha_local(s,m,op,lx+ox[i]*r,ly+oy[i]*r);
        if(q>a)a=q;
    }
    if(r>1){
        for(int i=0;i<4;++i){
            uint8_t q=direct_alpha_local(s,m,op,lx+ox[i],ly+oy[i]);
            if(q>a)a=q;
        }
    }
    return a;
}

inline void blend_point(uint16_t*fb,int fw,int fh,int x,int y,
                        uint16_t c,uint8_t a,uint8_t mode){
    if(a==0||x<0||y<0||x>=fw||y>=fh)return;
    uint16_t& d=fb[y*fw+x];d=blend565_local(d,c,a,mode);
}

void draw_fx_direct(uint16_t*fb,int fw,int fh,const VxpeSpriteA8*s,
                    const VxpeBlit565*op,const MapInfo&m,
                    const VxpeSpriteFxStyle*st){
    if(!st)return;
    if(st->shadow_alpha){
        const int soft=st->shadow_softness?1:0;
        for(int ly=0;ly<m.sh;++ly)for(int lx=0;lx<m.sw;++lx){
            uint8_t cov=direct_alpha_local(s,m,op,lx,ly);if(!cov)continue;
            uint8_t a=mul_alpha3(cov,st->shadow_alpha,op->alpha);
            int x=op->dst_x+lx+st->shadow_dx,y=op->dst_y+ly+st->shadow_dy;
            if(soft){
                uint8_t sa=(uint8_t)(a>>2);
                blend_point(fb,fw,fh,x-1,y,st->shadow_color,sa,VXPE_BLEND_ALPHA);
                blend_point(fb,fw,fh,x+1,y,st->shadow_color,sa,VXPE_BLEND_ALPHA);
                blend_point(fb,fw,fh,x,y-1,st->shadow_color,sa,VXPE_BLEND_ALPHA);
                blend_point(fb,fw,fh,x,y+1,st->shadow_color,sa,VXPE_BLEND_ALPHA);
                a=(uint8_t)(a-(a>>2));
            }
            blend_point(fb,fw,fh,x,y,st->shadow_color,a,VXPE_BLEND_ALPHA);
        }
    }
    int ro=st->outline_px>2?2:st->outline_px;
    int rg=st->glow_px>2?2:st->glow_px;
    int r=ro>rg?ro:rg;
    if(r>0&&(st->outline_alpha||st->glow_alpha)){
        for(int ly=-r;ly<m.sh+r;++ly)for(int lx=-r;lx<m.sw+r;++lx){
            uint8_t own=direct_alpha_local(s,m,op,lx,ly);
            if(own>112u)continue;
            int x=op->dst_x+lx,y=op->dst_y+ly;
            if(st->glow_alpha&&rg){
                uint8_t spread=direct_spread(s,m,op,lx,ly,rg);
                if(spread>own){
                    uint8_t edge=(uint8_t)(spread-own);
                    uint8_t a=mul_alpha3(edge,st->glow_alpha,op->alpha);
                    blend_point(fb,fw,fh,x,y,st->glow_color,a,VXPE_BLEND_ADD);
                }
            }
            if(st->outline_alpha&&ro){
                uint8_t spread=direct_spread(s,m,op,lx,ly,ro);
                if(spread>own){
                    uint8_t edge=(uint8_t)(spread-own);
                    uint8_t a=mul_alpha3(edge,st->outline_alpha,op->alpha);
                    blend_point(fb,fw,fh,x,y,st->outline_color,a,VXPE_BLEND_ALPHA);
                }
            }
        }
    }
}

} // namespace

extern "C" {
int vxpe2d_sprite_a8_from_vxa8(const void* data,uint32_t size,VxpeSpriteA8* out){
    if(!data||!out||size<12u)return 0;
    const uint8_t* b=static_cast<const uint8_t*>(data);
    if(b[0]!='V'||b[1]!='X'||b[2]!='A'||b[3]!='8'||b[9]!=1u)return 0;
    const uint16_t w=static_cast<uint16_t>(b[4]|(static_cast<uint16_t>(b[5])<<8));
    const uint16_t h=static_cast<uint16_t>(b[6]|(static_cast<uint16_t>(b[7])<<8));
    const uint16_t hs=static_cast<uint16_t>(b[10]|(static_cast<uint16_t>(b[11])<<8));
    if(w==0||h==0||hs<12u||hs>size)return 0;
    const uint64_t count=static_cast<uint64_t>(w)*h;
    const uint64_t pbytes=count*2u;
    const uint8_t opaque=(b[8]&1u)?1u:0u;
    const uint64_t need=static_cast<uint64_t>(hs)+pbytes+(opaque?0u:count);
    if(need>size)return 0;
    out->pixels=reinterpret_cast<const uint16_t*>(b+hs);
    out->alpha=opaque?nullptr:(b+hs+static_cast<uint32_t>(pbytes));
    out->width=w;out->height=h;out->stride=w;out->alpha_stride=w;out->opaque=opaque;
    return 1;
}

void vxpe2d_blit_a8(uint16_t* fb,int fb_w,int fb_h,
                    const VxpeSpriteA8* sprite,const VxpeBlit565* op){
    if(!fb||fb_w<=0||fb_h<=0)return;
    MapInfo m;if(!build_map(sprite,op,m))return;
    int cx0=0,cy0=0,cx1=fb_w,cy1=fb_h;
    if(op->clip_w&&op->clip_h){
        cx0=clamp_i(op->clip_x,0,fb_w);cy0=clamp_i(op->clip_y,0,fb_h);
        cx1=clamp_i(op->clip_x+op->clip_w,0,fb_w);cy1=clamp_i(op->clip_y+op->clip_h,0,fb_h);
    }
    const int x0=clamp_i(op->dst_x,cx0,cx1),y0=clamp_i(op->dst_y,cy0,cy1);
    const int x1=clamp_i(op->dst_x+m.dw,cx0,cx1),y1=clamp_i(op->dst_y+m.dh,cy0,cy1);
    if(x1<=x0||y1<=y0)return;
    for(int dy=y0;dy<y1;++dy){
        int ly=dy-op->dst_y;uint16_t* row=fb+dy*fb_w;
        for(int dx=x0;dx<x1;++dx){
            int lx=dx-op->dst_x,sxr,syr;map_rel(op,m,lx,ly,sxr,syr);
            int sx=m.sx0+sxr,sy=m.sy0+syr;
            uint8_t pa=alpha_at_source(sprite,m,sx,sy);
            if(pa==0)continue;
            uint8_t a=mul255_u16((uint16_t)pa*(uint16_t)op->alpha);
            if(a==0)continue;
            uint16_t c=tint565_local(sprite->pixels[sy*m.stride+sx],op->tint565);
            row[dx]=blend565_local(row[dx],c,a,op->blend);
        }
    }
}

void vxpe2d_anim_draw_a8(uint16_t* fb,int fb_w,int fb_h,
                           const VxpeSpriteA8* sprite,
                           const VxpeAnimState* state,const VxpeAnimClip* clip,
                           int x,int y,uint16_t dst_w,uint16_t dst_h,
                           uint16_t tint,uint8_t alpha,uint8_t blend_mode,
                           uint8_t flip_x,uint8_t flip_y){
    if(!fb||!sprite||!state||!clip||!alpha)return;
    VxpeBlit565 op=vxpe2d_anim_blit(state,clip,x,y,dst_w,dst_h);
    op.tint565=tint;op.alpha=alpha;op.blend=blend_mode;op.flip_x=flip_x;op.flip_y=flip_y;
    vxpe2d_blit_a8(fb,fb_w,fb_h,sprite,&op);
}

void vxpe2d_blit_a8_silhouette(uint16_t* fb,int fb_w,int fb_h,
                                 const VxpeSpriteA8* sprite,const VxpeBlit565* op,
                                 int offset_x,int offset_y,
                                 uint16_t color,uint8_t alpha,uint8_t blend_mode){
    if(!fb||fb_w<=0||fb_h<=0||alpha==0)return;
    MapInfo m;if(!build_map(sprite,op,m))return;
    const int ox=op->dst_x+offset_x,oy=op->dst_y+offset_y;
    const int x0=clamp_i(ox,0,fb_w),y0=clamp_i(oy,0,fb_h);
    const int x1=clamp_i(ox+m.dw,0,fb_w),y1=clamp_i(oy+m.dh,0,fb_h);
    if(x1<=x0||y1<=y0)return;
    for(int dy=y0;dy<y1;++dy){
        int ly=dy-oy;uint16_t* row=fb+dy*fb_w;
        for(int dx=x0;dx<x1;++dx){
            int lx=dx-ox,sxr,syr;map_rel(op,m,lx,ly,sxr,syr);
            int sx=m.sx0+sxr,sy=m.sy0+syr;
            uint8_t cov=alpha_at_source(sprite,m,sx,sy);if(!cov)continue;
            uint8_t a=mul_alpha3(cov,alpha,op->alpha);
            row[dx]=blend565_local(row[dx],color,a,blend_mode);
        }
    }
}

void vxpe2d_draw_isometric_a8(uint16_t* fb,int fb_w,int fb_h,
                               const VxpeSpriteA8* atlas,
                               const uint16_t* tile_ids,
                               uint16_t map_w,uint16_t map_h,
                               uint16_t tile_w,uint16_t tile_h,
                               uint16_t atlas_columns,
                               int origin_x,int origin_y,
                               uint16_t empty_id){
    if(!fb||!atlas||!tile_ids||map_w==0||map_h==0||
       tile_w==0||tile_h==0||atlas_columns==0)return;
    const int half_w=tile_w/2,half_h=tile_h/2;
    const int diagonals=static_cast<int>(map_w)+static_cast<int>(map_h)-1;
    for(int d=0;d<diagonals;++d){
        int y0=d-(static_cast<int>(map_w)-1);if(y0<0)y0=0;
        int y1=d;if(y1>=map_h)y1=map_h-1;
        for(int my=y0;my<=y1;++my){
            int mx=d-my;if(mx<0||mx>=map_w)continue;
            uint16_t id=tile_ids[my*map_w+mx];
            if(id==empty_id)continue;
            int sx=(id%atlas_columns)*tile_w;
            int sy=(id/atlas_columns)*tile_h;
            if(sx+tile_w>atlas->width||sy+tile_h>atlas->height)continue;
            VxpeBlit565 op={};
            op.src.x=static_cast<int16_t>(sx);op.src.y=static_cast<int16_t>(sy);
            op.src.w=static_cast<int16_t>(tile_w);op.src.h=static_cast<int16_t>(tile_h);
            op.dst_x=static_cast<int16_t>(origin_x+(mx-my)*half_w-half_w);
            op.dst_y=static_cast<int16_t>(origin_y+(mx+my)*half_h);
            op.dst_w=tile_w;op.dst_h=tile_h;op.tint565=0xFFFFu;op.alpha=255u;op.blend=VXPE_BLEND_ALPHA;
            vxpe2d_blit_a8(fb,fb_w,fb_h,atlas,&op);
        }
    }
}

void vxpe2d_draw_sprite_fx(uint16_t* fb,int fb_w,int fb_h,
                           const VxpeSpriteA8* sprite,
                           const VxpeBlit565* op,
                           const VxpeSpriteFxStyle* style){
    if(!fb||!sprite||!op){return;}
    MapInfo m;if(!build_map(sprite,op,m))return;
    if(m.dw==m.sw&&m.dh==m.sh){
        draw_fx_direct(fb,fb_w,fb_h,sprite,op,m,style);
        vxpe2d_blit_a8(fb,fb_w,fb_h,sprite,op);
        return;
    }
    if(style){
        if(style->shadow_alpha){
            const int r=style->shadow_softness>3?3:style->shadow_softness;
            const int bx=op->dst_x+style->shadow_dx-r,by=op->dst_y+style->shadow_dy-r;
            const int ex=op->dst_x+style->shadow_dx+m.dw+r;
            const int ey=op->dst_y+style->shadow_dy+m.dh+r;
            const int x0=clamp_i(bx,0,fb_w),y0=clamp_i(by,0,fb_h);
            const int x1=clamp_i(ex,0,fb_w),y1=clamp_i(ey,0,fb_h);
            for(int y=y0;y<y1;++y){uint16_t* row=fb+y*fb_w;
                for(int x=x0;x<x1;++x){
                    int sx=x-style->shadow_dx,sy=y-style->shadow_dy;
                    uint8_t cov=spread_coverage(sprite,op,m,sx,sy,r);
                    if(!cov)continue;
                    uint8_t a=mul_alpha3(cov,style->shadow_alpha,op->alpha);
                    row[x]=alpha565_local(row[x],style->shadow_color,a);
                }
            }
        }
        if(style->glow_alpha&&style->glow_px){
            int r=style->glow_px>4?4:style->glow_px;
            int x0=clamp_i(op->dst_x-r,0,fb_w),y0=clamp_i(op->dst_y-r,0,fb_h);
            int x1=clamp_i(op->dst_x+m.dw+r,0,fb_w),y1=clamp_i(op->dst_y+m.dh+r,0,fb_h);
            for(int y=y0;y<y1;++y){uint16_t* row=fb+y*fb_w;
                for(int x=x0;x<x1;++x){
                    uint8_t own=coverage_at_dest(sprite,op,m,x,y);
                    uint8_t spread=spread_coverage(sprite,op,m,x,y,r);
                    if(spread<=own)continue;
                    uint8_t edge=static_cast<uint8_t>(spread-own);
                    uint8_t a=mul_alpha3(edge,style->glow_alpha,op->alpha);
                    row[x]=add565_local(row[x],style->glow_color,a);
                }
            }
        }
        if(style->outline_alpha&&style->outline_px){
            int r=style->outline_px>3?3:style->outline_px;
            int x0=clamp_i(op->dst_x-r,0,fb_w),y0=clamp_i(op->dst_y-r,0,fb_h);
            int x1=clamp_i(op->dst_x+m.dw+r,0,fb_w),y1=clamp_i(op->dst_y+m.dh+r,0,fb_h);
            for(int y=y0;y<y1;++y){uint16_t* row=fb+y*fb_w;
                for(int x=x0;x<x1;++x){
                    uint8_t own=coverage_at_dest(sprite,op,m,x,y);
                    if(own>96u)continue;
                    uint8_t spread=spread_coverage(sprite,op,m,x,y,r);
                    if(spread<=own)continue;
                    uint8_t edge=static_cast<uint8_t>(spread-own);
                    uint8_t a=mul_alpha3(edge,style->outline_alpha,op->alpha);
                    row[x]=alpha565_local(row[x],style->outline_color,a);
                }
            }
        }
    }
    vxpe2d_blit_a8(fb,fb_w,fb_h,sprite,op);
}
void vxpe2d_batch_init(VxpeSpriteBatch* batch){
    if(!batch)return;
    memset(batch,0,sizeof(*batch));
}

int vxpe2d_batch_push(VxpeSpriteBatch* batch,
                      const VxpeSpriteA8* sprite,
                      const VxpeBlit565* op,
                      int16_t z,
                      const VxpeSpriteFxStyle* style){
    if(!batch||!sprite||!op)return 0;
    if(batch->count>=VXPE_SPRITE_BATCH_MAX){batch->dropped++;return 0;}
    VxpeSpriteDrawCmd& c=batch->commands[batch->count++];
    memset(&c,0,sizeof(c));
    c.sprite=sprite;c.op=*op;c.z=z;
    if(style){c.style=*style;c.use_fx=1u;}
    return 1;
}

void vxpe2d_batch_flush(VxpeSpriteBatch* batch,
                        uint16_t* fb,int fb_w,int fb_h){
    if(!batch||!fb)return;
    for(uint16_t i=1;i<batch->count;++i){
        VxpeSpriteDrawCmd key=batch->commands[i];
        int j=static_cast<int>(i)-1;
        while(j>=0&&batch->commands[j].z>key.z){
            batch->commands[j+1]=batch->commands[j];
            --j;
        }
        batch->commands[j+1]=key;
    }
    for(uint16_t i=0;i<batch->count;++i){
        VxpeSpriteDrawCmd& c=batch->commands[i];
        if(c.use_fx)vxpe2d_draw_sprite_fx(fb,fb_w,fb_h,c.sprite,&c.op,&c.style);
        else vxpe2d_blit_a8(fb,fb_w,fb_h,c.sprite,&c.op);
    }
    batch->count=0;
}

} // extern "C"
