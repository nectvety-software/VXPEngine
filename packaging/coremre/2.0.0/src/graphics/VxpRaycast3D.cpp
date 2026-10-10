#include "graphics/VxpRaycast3D.h"
#include <string.h>

namespace {
static int clampi(int v,int lo,int hi){return v<lo?lo:(v>hi?hi:v);}
static bool texture_ok(const VxpeRaycastTexture* t){return t&&t->pixels&&t->width&&t->height&&(!t->stride||t->stride>=t->width);}
static bool sprite_ok(const VxpeSpriteA8* s){return s&&s->pixels&&s->width&&s->height&&(!s->stride||s->stride>=s->width)&&(!s->alpha_stride||s->alpha_stride>=s->width);}
static bool scene_ok(const VxpeRaycastTarget* t,const VxpeRaycastCamera* c,const VxpeRaycastScene* s){
    return t&&t->pixels&&t->width&&t->height&&(!t->stride||t->stride>=t->width)&&
        c&&c->focal_px&&c->eye_height_q8&&c->eye_height_q8<256&&c->max_distance_q8&&
        s&&s->map.walls&&s->map.width&&s->map.height&&s->map.width<=64&&s->map.height<=64&&
        (!s->map.stride||s->map.stride>=s->map.width)&&s->wall_textures&&s->wall_count;
}
static uint16_t mix565(uint16_t a,uint16_t b,int alpha){int inv=255-alpha;return (uint16_t)(((((a>>11)*inv+(b>>11)*alpha)/255)<<11)|(((((a>>5)&63)*inv+((b>>5)&63)*alpha)/255)<<5)|(((a&31)*inv+(b&31)*alpha)/255));}
static uint16_t shade565(uint16_t c,int light){return (uint16_t)((((c>>11)*light/255)<<11)|(((((c>>5)&63)*light/255)<<5))|((c&31)*light/255));}
static uint16_t sample(const VxpeRaycastTexture* t,int x,int y){int stride=t->stride?t->stride:t->width;return t->pixels[y*stride+x];}
static uint16_t fog_pixel(const VxpeRaycastScene* s,uint16_t c,uint32_t distance,int x,int y){
    if(!s->fog_strength||distance<=s->fog_near_q8||s->fog_far_q8<=s->fog_near_q8)return c;
    int alpha=(int)((distance-s->fog_near_q8)*s->fog_strength/(s->fog_far_q8-s->fog_near_q8));
    if(alpha>s->fog_strength)alpha=s->fog_strength;
    if(s->dither_strength){static const uint8_t bayer[16]={0,8,2,10,12,4,14,6,3,11,1,9,15,7,13,5};alpha+=((int)bayer[((y&3)<<2)|(x&3)]-8)*s->dither_strength/8;alpha=clampi(alpha,0,255);}
    return mix565(c,s->fog565,alpha);
}
static int tex_coord(int world_q8,int extent){int fraction=world_q8&255;return (fraction*extent)>>8;}
static void draw_plane_rows(VxpeRaycastTarget* t,const VxpeRaycastCamera* c,const VxpeRaycastScene* s,int first,int last,const VxpeRaycastTexture* texture,int planeHeightQ8){
    if(!texture_ok(texture))return;
    int w=t->width,h=t->height,stride=t->stride?t->stride:w,center=c->horizon_y;
    const int32_t leftX=(int32_t)c->dir_x_q14-c->plane_x_q14,leftZ=(int32_t)c->dir_z_q14-c->plane_z_q14;
    const int32_t rayStepX=(int32_t)c->plane_x_q14*2,rayStepZ=(int32_t)c->plane_z_q14*2;
    for(int y=first;y<last;++y){
        int p=y-center;if(p==0)continue;if(p<0)p=-p;
        uint32_t distance=(uint32_t)planeHeightQ8*c->focal_px/(uint32_t)p;
        if(distance>c->max_distance_q8)distance=c->max_distance_q8;
        int32_t wx=c->x_q8+(int32_t)((int64_t)leftX*distance/16384);
        int32_t wz=c->z_q8+(int32_t)((int64_t)leftZ*distance/16384);
        int32_t stepX=(int32_t)((int64_t)rayStepX*distance/(16384*w));
        int32_t stepZ=(int32_t)((int64_t)rayStepZ*distance/(16384*w));
        uint16_t* row=t->pixels+y*stride;
        for(int x=0;x<w;++x,wx+=stepX,wz+=stepZ){
            uint16_t color=sample(texture,tex_coord(wx,texture->width),tex_coord(wz,texture->height));
            row[x]=fog_pixel(s,color,distance,x,y);
        }
    }
}
}

extern "C" {
void vxpe_raycast3d_camera_init(VxpeRaycastCamera* c,int width,int height,int horizon,int focal){
    if(!c)return;memset(c,0,sizeof(*c));c->dir_z_q14=16384;c->plane_x_q14=10923;
    c->horizon_y=(int16_t)clampi(horizon>=0?horizon:height/2,0,height-1);
    c->focal_px=(uint16_t)clampi(focal>0?focal:width*2/3,1,4096);c->eye_height_q8=128;c->max_distance_q8=8192;
}

int vxpe_raycast3d_render(VxpeRaycastTarget* t,const VxpeRaycastCamera* c,const VxpeRaycastScene* s){
    if(!scene_ok(t,c,s))return 0;
    int w=t->width,h=t->height,stride=t->stride?t->stride:w,center=clampi(c->horizon_y,0,h-1);
    for(int y=0;y<h;++y){uint16_t color=y<center?s->sky565:s->fog565;uint16_t* row=t->pixels+y*stride;for(int x=0;x<w;++x)row[x]=color;}
    draw_plane_rows(t,c,s,0,center,&s->ceiling_texture,(256-c->eye_height_q8));
    draw_plane_rows(t,c,s,center+1,h,&s->floor_texture,c->eye_height_q8);
    int mapStride=s->map.stride?s->map.stride:s->map.width;
    int startMapX=c->x_q8>>8,startMapZ=c->z_q8>>8;
    if(startMapX<0||startMapZ<0||startMapX>=s->map.width||startMapZ>=s->map.height)return 1;
    for(int x=0;x<w;++x){
        int mapX=startMapX,mapZ=startMapZ;
        int cameraX=((2*x+1)*256/w)-256;
        int32_t rayX=(int32_t)c->dir_x_q14+(int32_t)c->plane_x_q14*cameraX/256;
        int32_t rayZ=(int32_t)c->dir_z_q14+(int32_t)c->plane_z_q14*cameraX/256;
        int stepX=rayX<0?-1:1,stepZ=rayZ<0?-1:1;
        int absRayX=rayX<0?-rayX:rayX,absRayZ=rayZ<0?-rayZ:rayZ;
        int deltaX=absRayX?(256*16384)/absRayX:32767,deltaZ=absRayZ?(256*16384)/absRayZ:32767;
        int sideX=stepX<0?(int)(((int64_t)(c->x_q8-mapX*256)*16384)/(absRayX?absRayX:1)):(int)(((int64_t)((mapX+1)*256-c->x_q8)*16384)/(absRayX?absRayX:1));
        int sideZ=stepZ<0?(int)(((int64_t)(c->z_q8-mapZ*256)*16384)/(absRayZ?absRayZ:1)):(int)(((int64_t)((mapZ+1)*256-c->z_q8)*16384)/(absRayZ?absRayZ:1));
        int cell=0,side=0,steps=0;
        while(steps++<96){
            if(sideX<sideZ){sideX+=deltaX;mapX+=stepX;side=0;}else{sideZ+=deltaZ;mapZ+=stepZ;side=1;}
            if(mapX<0||mapZ<0||mapX>=s->map.width||mapZ>=s->map.height){cell=1;break;}
            cell=s->map.walls[mapZ*mapStride+mapX];if(cell)break;
            if((sideX<sideZ?sideX:sideZ)>c->max_distance_q8)break;
        }
        if(!cell||cell>s->wall_count){if(t->wall_depth_q8)t->wall_depth_q8[x]=c->max_distance_q8;continue;}
        int distance=side?(sideZ-deltaZ):(sideX-deltaX);if(distance<1)distance=1;if(distance>c->max_distance_q8)distance=c->max_distance_q8;
        if(t->wall_depth_q8)t->wall_depth_q8[x]=(uint16_t)distance;
        const VxpeRaycastTexture* texture=&s->wall_textures[cell-1];if(!texture_ok(texture))continue;
        int top=center-(int)((uint32_t)c->eye_height_q8*c->focal_px/(uint32_t)distance);
        int bottom=center+(int)((uint32_t)(256-c->eye_height_q8)*c->focal_px/(uint32_t)distance);
        int lineHeight=bottom-top;if(lineHeight<=0)continue;
        int32_t wallQ8=side?c->x_q8+(int32_t)((int64_t)distance*rayX/16384):c->z_q8+(int32_t)((int64_t)distance*rayZ/16384);
        int tx=tex_coord(wallQ8,texture->width);if((side==0&&rayX>0)||(side==1&&rayZ<0))tx=texture->width-1-tx;
        int drawTop=clampi(top,0,h),drawBottom=clampi(bottom+1,0,h);
        int texPos=top<0?(int)((int64_t)(-top)*texture->height*256/lineHeight):0;
        int texStep=(texture->height*256)/lineHeight;if(texStep<1)texStep=1;
        for(int y=drawTop;y<drawBottom;++y,texPos+=texStep){
            int ty=clampi(texPos>>8,0,texture->height-1);
            uint16_t color=sample(texture,tx,ty);if(side)color=shade565(color,210);
            color=fog_pixel(s,color,(uint32_t)distance,x,y);
            t->pixels[y*stride+x]=color;
        }
    }
    return 1;
}

int vxpe_raycast3d_billboard(VxpeRaycastTarget* t,const VxpeRaycastCamera* c,const VxpeSpriteA8* sprite,const VxpeRaycastBillboard* b){
    if(!t||!t->pixels||!c||!sprite_ok(sprite)||!b||!b->width_q8||!b->height_q8||!c->focal_px)return 0;
    int stride=t->stride?t->stride:t->width;
    int32_t dx=b->x_q8-c->x_q8,dz=b->z_q8-c->z_q8;
    int32_t depth=(int32_t)(((int64_t)dx*c->dir_x_q14+(int64_t)dz*c->dir_z_q14)/16384);
    if(depth<16||depth>c->max_distance_q8)return 0;
    int32_t lateral=(int32_t)(((int64_t)dx*c->dir_z_q14-(int64_t)dz*c->dir_x_q14)/16384);
    int centerX=t->width/2+(int)((int64_t)lateral*c->focal_px/depth);
    int width=(int)((uint32_t)b->width_q8*c->focal_px/(uint32_t)depth);
    int height=(int)((uint32_t)b->height_q8*c->focal_px/(uint32_t)depth);
    if(width<1)width=1;if(height<1)height=1;
    int bottom=c->horizon_y-(int)((int64_t)(b->bottom_y_q8-c->eye_height_q8)*c->focal_px/depth);
    int left=centerX-width/2,top=bottom-height;
    if(left>=t->width||left+width<=0||top>=t->height||bottom<=0)return 0;
    int drawn=0;
    for(int y=clampi(top,0,t->height);y<clampi(bottom,0,t->height);++y){
        int sy=(int)((int64_t)(y-top)*sprite->height/height);if(sy>=sprite->height)sy=sprite->height-1;
        for(int x=clampi(left,0,t->width);x<clampi(left+width,0,t->width);++x){
            if(t->wall_depth_q8&&depth>t->wall_depth_q8[x])continue;
            int sx=(int)((int64_t)(x-left)*sprite->width/width);if(sx>=sprite->width)sx=sprite->width-1;
            int a=sprite->opaque||!sprite->alpha?255:sprite->alpha[sy*(sprite->alpha_stride?sprite->alpha_stride:sprite->width)+sx];
            a=a*b->alpha/255;if(a<128)continue;
            uint16_t color=sprite->pixels[sy*(sprite->stride?sprite->stride:sprite->width)+sx];if(b->tint565)color=vxpe2d_tint565(color,b->tint565);
            int index=y*stride+x;t->pixels[index]=a==255?color:mix565(t->pixels[index],color,a);++drawn;
        }
    }
    return drawn;
}
}
