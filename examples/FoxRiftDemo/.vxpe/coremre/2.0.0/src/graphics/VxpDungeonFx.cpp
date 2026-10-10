#include "graphics/VxpDungeonFx.h"
#include <stdint.h>
static uint16_t color(int r,int g,int b){return (uint16_t)(((r>>3)<<11)|((g>>2)<<5)|(b>>3));}
extern "C" uint16_t vxpe_dungeon_light565(VxpeVec3D p,uint16_t albedo,uint8_t ambient,const VxpeDungeonLight3D* lights,unsigned count){
    unsigned r=ambient,g=ambient,b=ambient;if(!lights)count=0;if(count>16)count=16;
    for(unsigned i=0;i<count;++i){const VxpeDungeonLight3D& l=lights[i];if(!l.radius)continue;
        int64_t dx=(int64_t)p.x-l.position.x,dy=(int64_t)p.y-l.position.y,dz=(int64_t)p.z-l.position.z;
        if(dx>l.radius||dx<-(int)l.radius||dy>l.radius||dy<-(int)l.radius||dz>l.radius||dz<-(int)l.radius)continue;
        uint64_t d=(uint64_t)(dx*dx+dy*dy+dz*dz),rad=(uint64_t)l.radius*l.radius;if(d>=rad)continue;
        unsigned energy=(unsigned)((rad-d)*l.intensity/rad);
        r+=((l.color565>>11)&31)*energy/31;g+=((l.color565>>5)&63)*energy/63;b+=(l.color565&31)*energy/31;
    }
    if(r>255)r=255;
    if(g>255)g=255;
    if(b>255)b=255;
    return color(((albedo>>11)&31)*255/31*r/255,((albedo>>5)&63)*255/63*g/255,(albedo&31)*255/31*b/255);
}
extern "C" void vxpe_dungeon_mana_sky(uint16_t* fb,int w,int h,unsigned frame){
    if(!fb||w<1||h<1||w>2048||h>2048)return;
    int cx=w*3/5,cy=h/3;
    for(int y=0;y<h;++y)for(int x=0;x<w;++x){int dx=(x-cx)*256/w,dy=(y-cy)*256/h;
        unsigned radius=(unsigned)(dx*dx+dy*dy);unsigned swirl=(radius/23+(unsigned)(dx*3+dy*5)+frame*2)&127;
        int beam=swirl<13?13-(int)swirl:0;
        unsigned hash=((unsigned)x*73856093u)^((unsigned)y*19349663u);
        int star=(hash%1801==0)?110:0;
        int r=14+beam*5+star,g=7+beam*9+star,b=43+beam*14+star;
        if(r>255)r=255;
    if(g>255)g=255;
    if(b>255)b=255;
        fb[y*w+x]=color(r,g,b);
    }
}
