#include "graphics/VxpScene25D.h"

#include <string.h>

namespace {

static int clamp_i(int v,int lo,int hi){return v<lo?lo:(v>hi?hi:v);}
static uint8_t clamp_u8(int v){return (uint8_t)(v<0?0:(v>255?255:v));}

static uint16_t rgb_mix(uint16_t a,uint16_t b,uint8_t t){
    int ar=(a>>11)&31,ag=(a>>5)&63,ab=a&31;
    int br=(b>>11)&31,bg=(b>>5)&63,bb=b&31;
    int r=ar+((br-ar)*t+127)/255;
    int g=ag+((bg-ag)*t+127)/255;
    int bl=ab+((bb-ab)*t+127)/255;
    return (uint16_t)((r<<11)|(g<<5)|bl);
}

static uint16_t blend565(uint16_t dst,uint16_t src,uint8_t alpha){
    if(alpha==0)return dst;
    if(alpha==255)return src;
    int dr=(dst>>11)&31,dg=(dst>>5)&63,db=dst&31;
    int sr=(src>>11)&31,sg=(src>>5)&63,sb=src&31;
    int ia=255-alpha;
    int r=(sr*alpha+dr*ia+127)/255;
    int g=(sg*alpha+dg*ia+127)/255;
    int b=(sb*alpha+db*ia+127)/255;
    return (uint16_t)((r<<11)|(g<<5)|b);
}

static uint16_t add565(uint16_t dst,uint16_t src,uint8_t alpha){
    int dr=(dst>>11)&31,dg=(dst>>5)&63,db=dst&31;
    int sr=((src>>11)&31)*alpha/255;
    int sg=((src>>5)&63)*alpha/255;
    int sb=(src&31)*alpha/255;
    dr+=sr;dg+=sg;db+=sb;
    if (dr > 31) dr = 31;
    if (dg > 63) dg = 63;
    if (db > 31) db = 31;
    return (uint16_t)((dr<<11)|(dg<<5)|db);
}

static void put_pixel(uint16_t* fb,int w,int h,int x,int y,uint16_t c,uint8_t a,uint8_t blend){
    if(!fb||x<0||y<0||x>=w||y>=h||!a)return;
    uint16_t* p=fb+y*w+x;
    if(blend==VXPE_BLEND_ADD)*p=add565(*p,c,a);
    else *p=blend565(*p,c,a);
}

static void draw_line_width(
    uint16_t* fb,int w,int h,int x0,int y0,int x1,int y1,
    uint16_t color,uint8_t alpha,uint8_t blend,int width)
{
    int dx=x1>x0?x1-x0:x0-x1,sx=x0<x1?1:-1;
    int dy=y1>y0?y0-y1:y1-y0,sy=y0<y1?1:-1;
    int err=dx+dy;
    int half=width>1?width/2:0;
    for(;;){
        for(int yy=-half;yy<=half;++yy)
            for(int xx=-half;xx<=half;++xx)
                put_pixel(fb,w,h,x0+xx,y0+yy,color,alpha,blend);
        if(x0==x1&&y0==y1)break;
        int e2=err<<1;
        if(e2>=dy){err+=dy;x0+=sx;}
        if(e2<=dx){err+=dx;y0+=sy;}
    }
}

static uint32_t isqrt32(uint32_t n){
    uint32_t res=0,bit=1u<<30;
    while(bit>n)bit>>=2;
    while(bit){
        if(n>=res+bit){n-=res+bit;res=(res>>1)+bit;}
        else res>>=1;
        bit>>=2;
    }
    return res;
}

static int wave_offset(int y,uint8_t phase,uint8_t shift,int amplitude){
    if(amplitude==0)return 0;
    static const int8_t lut[16]={0,3,6,7,8,7,6,3,0,-3,-6,-7,-8,-7,-6,-3};
    int idx=(phase+(y>>shift))&15;
    return (lut[idx]*amplitude)/8;
}

} // namespace

extern "C" {

void vxpe25d_camera_init(
    VxpeCamera25D* camera,int screen_w,int screen_h,int horizon_y,int focal_px)
{
    if(!camera)return;
    memset(camera,0,sizeof(*camera));
    camera->world_y=64;
    camera->center_x=(int16_t)(screen_w/2);
    camera->horizon_y=(int16_t)(horizon_y>=0?horizon_y:screen_h/3);
    camera->focal_q8=(uint16_t)clamp_i(focal_px>0?focal_px*256:160*256,1,65535);
    camera->near_z=16;camera->far_z=1024;
    camera->min_scale_q8=48;camera->max_scale_q8=768;
    camera->fog_near_z=256;camera->fog_far_z=900;
    camera->fog_color565=vxpe2d_rgb565(112,145,116);
    camera->fog_strength=180;
}

int vxpe25d_project(
    const VxpeCamera25D* camera,
    int32_t world_x,int32_t world_y,int32_t world_z,
    VxpeProjected25D* out)
{
    if(!camera||!out)return 0;
    memset(out,0,sizeof(*out));
    int32_t dz=world_z-camera->world_z;
    if(dz<(int32_t)camera->near_z||dz>(int32_t)camera->far_z)return 0;
    uint32_t scale=(uint32_t)camera->focal_q8/(uint32_t)dz;
    if(scale<camera->min_scale_q8)scale=camera->min_scale_q8;
    if(scale>camera->max_scale_q8)scale=camera->max_scale_q8;
    int32_t dx=world_x-camera->world_x;
    int32_t dy=world_y-camera->world_y;
    int32_t sx=(int32_t)camera->center_x+((dx*(int32_t)scale)>>8);
    int32_t sy=(int32_t)camera->horizon_y-((dy*(int32_t)scale)>>8);
    if(sx<-32768||sx>32767||sy<-32768||sy>32767)return 0;
    int fog=0;
    if(camera->fog_strength&&dz>(int32_t)camera->fog_near_z){
        int range=(int)camera->fog_far_z-(int)camera->fog_near_z;
        if(range<=0)fog=camera->fog_strength;
        else fog=(int)(((dz-camera->fog_near_z)*camera->fog_strength)/range);
        if(fog>camera->fog_strength)fog=camera->fog_strength;
    }
    out->x=(int16_t)sx;out->y=(int16_t)sy;
    out->scale_q8=(uint16_t)scale;out->depth=(uint16_t)dz;
    out->fog_alpha=clamp_u8(fog);out->visible=1;
    return 1;
}

uint16_t vxpe25d_fog_tint(
    const VxpeCamera25D* camera,uint16_t base_tint565,uint8_t fog_alpha)
{
    if(!camera||!fog_alpha)return base_tint565;
    uint16_t fog_mul=rgb_mix(0xFFFFu,camera->fog_color565,fog_alpha);
    int ar=(base_tint565>>11)&31,ag=(base_tint565>>5)&63,ab=base_tint565&31;
    int br=(fog_mul>>11)&31,bg=(fog_mul>>5)&63,bb=fog_mul&31;
    return (uint16_t)(((ar*br/31)<<11)|((ag*bg/63)<<5)|(ab*bb/31));
}

int vxpe25d_draw_billboard(
    uint16_t* fb,int fb_w,int fb_h,
    const VxpeCamera25D* camera,
    const VxpeSpriteA8* sprite,
    const VxpeBillboard25D* billboard)
{
    if(!fb||!camera||!sprite||!billboard)return 0;
    VxpeProjected25D p;
    if(!vxpe25d_project(camera,billboard->world_x,billboard->world_y,billboard->world_z,&p))return 0;
    int dw=(int)(((uint32_t)billboard->world_w*p.scale_q8+127)>>8);
    int dh=(int)(((uint32_t)billboard->world_h*p.scale_q8+127)>>8);
    if (dw < 1) dw = 1;
    if (dh < 1) dh = 1;
    int dx=p.x-(int)(((uint32_t)dw*billboard->pivot_x_q8+127)>>8);
    int dy=p.y-(int)(((uint32_t)dh*billboard->pivot_y_q8+127)>>8);
    if(dx>=fb_w||dy>=fb_h||dx+dw<=0||dy+dh<=0)return 0;
    VxpeBlit565 op{};
    op.src=billboard->src;op.dst_x=(int16_t)dx;op.dst_y=(int16_t)dy;
    op.dst_w=(uint16_t)dw;op.dst_h=(uint16_t)dh;
    op.tint565=vxpe25d_fog_tint(camera,billboard->tint565?billboard->tint565:0xFFFFu,p.fog_alpha);
    op.alpha=billboard->alpha;op.blend=billboard->blend;
    op.flip_x=billboard->flip_x;op.flip_y=billboard->flip_y;
    vxpe2d_blit_a8(fb,fb_w,fb_h,sprite,&op);
    return 1;
}

void vxpe25d_draw_plane(
    uint16_t* fb,int fb_w,int fb_h,
    const VxpeSpriteA8* sprite,const VxpePlane25D* plane)
{
    if(!fb||!sprite||!plane)return;
    int top=plane->top_y,bottom=plane->bottom_y;
    if(bottom<=top)return;
    int span=bottom-top;
    for(int y=top;y<bottom;++y){
        if(y<0||y>=fb_h)continue;
        int t=((y-top)*256)/span;
        int width=(int)plane->top_width+(((int)plane->bottom_width-(int)plane->top_width)*t>>8);
        if(width<1)continue;
        int sy=plane->src.y+((int)plane->src.h*t>>8);
        if(sy>=plane->src.y+plane->src.h)sy=plane->src.y+plane->src.h-1;
        int cx=plane->center_x+wave_offset(y,plane->ripple_phase,plane->ripple_wavelength_shift,plane->ripple_amplitude);
        VxpeBlit565 op{};
        op.src={plane->src.x,(int16_t)sy,plane->src.w,1};
        op.dst_x=(int16_t)(cx-width/2);op.dst_y=(int16_t)y;
        op.dst_w=(uint16_t)width;op.dst_h=1;
        op.tint565=plane->tint565?plane->tint565:0xFFFFu;
        op.alpha=plane->alpha;op.blend=plane->blend;
        vxpe2d_blit_a8(fb,fb_w,fb_h,sprite,&op);
    }
}

void vxpe25d_draw_ground_shadow(
    uint16_t* fb,int fb_w,int fb_h,
    const VxpeCamera25D* camera,
    int32_t world_x,int32_t world_z,
    uint16_t radius_x,uint16_t radius_y,
    uint16_t color565,uint8_t alpha,uint8_t blend_mode)
{
    if(!fb||!camera||!radius_x||!radius_y||!alpha)return;
    VxpeProjected25D p;
    if(!vxpe25d_project(camera,world_x,0,world_z,&p))return;
    int rx=(int)(((uint32_t)radius_x*p.scale_q8+127)>>8);
    int ry=(int)(((uint32_t)radius_y*p.scale_q8+127)>>8);
    if (rx < 1) rx = 1;
    if (ry < 1) ry = 1;
    uint32_t ry2=(uint32_t)ry*(uint32_t)ry;
    for(int dy=-ry;dy<=ry;++dy){
        uint32_t y2=(uint32_t)(dy*dy);
        uint32_t rem=ry2>y2?ry2-y2:0;
        int ex=(int)((uint32_t)rx*isqrt32(rem)/((uint32_t)ry?ry:1));
        if(ex<1)ex=1;
        vxpe2d_overlay_rect(fb,fb_w,fb_h,p.x-ex,p.y+dy,ex*2+1,1,color565,alpha,blend_mode);
    }
}

int vxpe25d_draw_rope_world(
    uint16_t* fb,int fb_w,int fb_h,
    const VxpeCamera25D* camera,
    int32_t x0,int32_t y0,int32_t z0,
    int32_t x1,int32_t y1,int32_t z1,
    const VxpeRopeStyle25D* style)
{
    if(!fb||!camera||!style)return 0;
    VxpeProjected25D a,b;
    if(!vxpe25d_project(camera,x0,y0,z0,&a))return 0;
    if(!vxpe25d_project(camera,x1,y1,z1,&b))return 0;
    int ow=style->outer_width?style->outer_width:1;
    int cw=style->core_width?style->core_width:1;
    if(style->outer_color565&&ow)
        draw_line_width(fb,fb_w,fb_h,a.x,a.y,b.x,b.y,style->outer_color565,style->alpha,style->blend,ow);
    if(style->core_color565&&cw)
        draw_line_width(fb,fb_w,fb_h,a.x,a.y,b.x,b.y,style->core_color565,style->alpha,style->blend,cw);
    return 1;
}

void vxpe25d_apply_grade(
    uint16_t* fb,int fb_w,int fb_h,
    const VxpeGrade25D* grade,int horizon_y)
{
    if(!fb||!grade||fb_w<=0||fb_h<=0)return;
    static const uint8_t bayer[16]={0,8,2,10,12,4,14,6,3,11,1,9,15,7,13,5};
    int cx=fb_w/2,cy=fb_h/2;
    int maxd=cx+cy;if(maxd<1)maxd=1;
    for(int y=0;y<fb_h;++y){
        int horizon_alpha=0;
        if(grade->fog_horizon_alpha){
            int dy=y-horizon_y;if(dy<0)dy=-dy;
            int band=fb_h/3;if(band<1)band=1;
            horizon_alpha=grade->fog_horizon_alpha-(grade->fog_horizon_alpha*dy/band);
            if(horizon_alpha<0)horizon_alpha=0;
        }
        for(int x=0;x<fb_w;++x){
            uint16_t c=fb[y*fb_w+x];
            if(grade->tint_alpha)c=blend565(c,grade->tint565,grade->tint_alpha);
            if(horizon_alpha)c=blend565(c,grade->tint565,(uint8_t)horizon_alpha);
            if(grade->vignette_alpha){
                int dx=x-cx;if(dx<0)dx=-dx;int dy=y-cy;if(dy<0)dy=-dy;
                int edge=(dx+dy)*grade->vignette_alpha/maxd;
                if(edge>0)c=blend565(c,0,(uint8_t)clamp_i(edge,0,255));
            }
            if(grade->dither_strength){
                int threshold=bayer[((y&3)<<2)|(x&3)];
                if(threshold<8){
                    int dark=(int)grade->dither_strength*(8-threshold)/8;
                    c=blend565(c,0,(uint8_t)dark);
                }
            }
            fb[y*fb_w+x]=c;
        }
    }
}

} /* extern "C" */
