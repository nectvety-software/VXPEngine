#include "graphics/VxpActorSprite2D.h"
#include <string.h>
static int valid(const VxpeActorAtlas2D* a, const VxpeActorState2D* s) {
    if(!a||!s||!a->sprite.pixels||!a->frame_w||!a->frame_h||s->direction>3||s->action>3) return 0;
    if(a->frame_w>32767||a->frame_h>32767||a->sprite.width>32767||a->sprite.height>32767) return 0;
    if(a->sprite.width%a->frame_w||a->sprite.height/a->frame_h<4) return 0;
    if(a->sprite.stride&&a->sprite.stride<a->sprite.width) return 0;
    if(a->sprite.alpha&&a->sprite.alpha_stride&&a->sprite.alpha_stride<a->sprite.width) return 0;
    const VxpeActorClip2D& c=a->clips[s->action];
    return c.count&&c.frame_ms&&(uint32_t)c.first+c.count<=a->sprite.width/a->frame_w&&s->frame<c.count;
}
void vxpe_actor_init(VxpeActorState2D* s){if(s){memset(s,0,sizeof(*s));s->direction=VXPE_ACTOR_EAST;}}
int vxpe_actor_set(VxpeActorState2D* s,uint8_t direction,uint8_t action){
    if(!s||direction>3||action>3)return 0;
    if(s->action!=action){s->frame=0;s->elapsed_ms=0;s->finished=0;}
    s->direction=direction;s->action=action;return 1;
}
int vxpe_actor_update(VxpeActorState2D* s,const VxpeActorAtlas2D* a,uint16_t dt){
    if(!valid(a,s))return 0;
    if(s->finished)return 1;
    const VxpeActorClip2D& c=a->clips[s->action];
    uint32_t time=(uint32_t)s->elapsed_ms+dt,frame=s->frame+time/c.frame_ms;
    s->elapsed_ms=(uint16_t)(time%c.frame_ms);
    if(c.loop)s->frame=(uint16_t)(frame%c.count);
    else if(frame>=c.count){s->frame=c.count-1;s->elapsed_ms=0;s->finished=1;}
    else s->frame=(uint16_t)frame;
    return 1;
}
int vxpe_actor_draw(uint16_t* fb,int w,int h,const VxpeActorAtlas2D* a,const VxpeActorState2D* s,int16_t x,int16_t y){
    if(!fb||w<=0||h<=0||!valid(a,s))return 0;
    int dx=(int)x-a->anchor_x,dy=(int)y-a->anchor_y;
    if(dx<-32768||dx>32767||dy<-32768||dy>32767)return 0;
    VxpeBlit565 op={};const VxpeActorClip2D& c=a->clips[s->action];
    op.src.x=(int16_t)((c.first+s->frame)*a->frame_w);op.src.y=(int16_t)(s->direction*a->frame_h);
    op.src.w=a->frame_w;op.src.h=a->frame_h;op.dst_x=(int16_t)dx;op.dst_y=(int16_t)dy;
    op.dst_w=a->frame_w;op.dst_h=a->frame_h;op.tint565=65535;op.alpha=255;op.blend=VXPE_BLEND_ALPHA;
    vxpe2d_blit_a8(fb,w,h,&a->sprite,&op);return 1;
}
