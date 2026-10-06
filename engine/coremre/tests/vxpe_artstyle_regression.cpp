#include "graphics/VxpArtStyle.h"
#include "graphics/VxpRender2D.h"
#include <cassert>
#include <cstdio>
#include <cstring>
int main(){VxpeArtStyleProfile p{};vxpe_artstyle_init(&p,VXPE_ARTSTYLE_SATURATED_ADVENTURE);assert(p.postprocess&&p.trail_alpha&&p.fog_strength);assert(std::strcmp(vxpe_artstyle_name(VXPE_ARTSTYLE_SATURATED_ADVENTURE),"Saturated Adventure")==0);VxpeCamera25D c{};VxpeGrade25D g{};vxpe25d_camera_init(&c,240,320,96,150);vxpe_artstyle_apply_scene25d(&p,&c,&g);assert(c.fog_strength==p.fog_strength&&g.tint565==p.tint565);VxpeSpriteFxStyle fx{};vxpe_artstyle_apply_sprite_fx(&p,&fx);assert(fx.outline_px==p.sprite_fx.outline_px);uint16_t fb[4]={vxpe2d_rgb565(50,80,100),vxpe2d_rgb565(120,140,150),vxpe2d_rgb565(180,160,80),vxpe2d_rgb565(30,180,75)},before[4];std::memcpy(before,fb,sizeof(fb));vxpe_artstyle_postprocess565(fb,2,2,&p);bool changed=false;for(int i=0;i<4;++i)if(fb[i]!=before[i])changed=true;assert(changed);for(int i=0;i<VXPE_ARTSTYLE_COUNT;++i){vxpe_artstyle_init(&p,(VxpeArtStyleId)i);assert(vxpe_artstyle_name((VxpeArtStyleId)i));}std::puts("VXPE_ARTSTYLE_PASS");return 0;}
