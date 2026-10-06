#include "graphics/VxpActorSprite2D.h"
#include <assert.h>
#include <string.h>
int main(){
    uint16_t pixels[16]={1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16};
    uint8_t alpha[16];memset(alpha,255,sizeof(alpha));
    VxpeActorAtlas2D a={{pixels,alpha,4,4,4,4,0},1,1,0,0,
        {{0,1,100,1},{0,4,100,1},{1,2,100,0},{3,1,100,0}}};
    VxpeActorState2D s;vxpe_actor_init(&s);assert(s.direction==1&&s.action==0);
    vxpe_actor_set(&s,2,1);vxpe_actor_update(&s,&a,350);assert(s.frame==3&&s.elapsed_ms==50);
    vxpe_actor_set(&s,3,1);assert(s.frame==3&&s.elapsed_ms==50);
    vxpe_actor_update(&s,&a,65535);assert(s.frame==2&&s.elapsed_ms==85);
    vxpe_actor_set(&s,1,2);assert(s.frame==0&&s.elapsed_ms==0);
    vxpe_actor_update(&s,&a,500);assert(s.finished&&s.frame==1);
    vxpe_actor_update(&s,&a,500);assert(s.finished&&s.frame==1);
    uint16_t guarded[11];for(int i=0;i<11;++i)guarded[i]=0xabcd;
    assert(vxpe_actor_draw(guarded+1,3,3,&a,&s,0,0));assert(guarded[1]==7);
    assert(guarded[0]==0xabcd&&guarded[10]==0xabcd);
    alpha[6]=0;guarded[1]=0xabcd;vxpe_actor_draw(guarded+1,3,3,&a,&s,0,0);assert(guarded[1]==0xabcd);
    a.anchor_x=1;assert(vxpe_actor_draw(guarded+1,3,3,&a,&s,0,0));assert(guarded[0]==0xabcd);
    a.clips[2].count=9;assert(!vxpe_actor_update(&s,&a,33));assert(!vxpe_actor_draw(guarded+1,3,3,&a,&s,0,0));
    a.clips[2].count=2;a.clips[2].frame_ms=0;assert(!vxpe_actor_update(&s,&a,33));
    assert(!vxpe_actor_set(&s,4,0));assert(!vxpe_actor_set(0,0,0));
    assert(!vxpe_actor_draw(0,3,3,&a,&s,0,0));
    return 0;
}
