#include "graphics/VxpScene25D.h"
#include <cassert>
#include <cstdio>
#include <cstring>

static int nonzero(const uint16_t* fb,int n){int c=0;for(int i=0;i<n;++i)if(fb[i])++c;return c;}

int main(){
    VxpeCamera25D cam{};
    vxpe25d_camera_init(&cam,240,320,80,160);
    VxpeProjected25D p{};
    assert(vxpe25d_project(&cam,0,0,160,&p));
    assert(p.x==120);
    assert(p.y==144);
    assert(p.scale_q8==256);

    const uint16_t px[4]={0xF800,0x07E0,0x001F,0xFFFF};
    VxpeSpriteA8 sprite{};
    sprite.pixels=px;sprite.width=2;sprite.height=2;sprite.stride=2;sprite.opaque=1;
    static uint16_t fb[240*320];

    VxpeBillboard25D bill{};
    bill.src={0,0,2,2};bill.world_x=0;bill.world_y=0;bill.world_z=160;
    bill.world_w=20;bill.world_h=20;bill.pivot_x_q8=128;bill.pivot_y_q8=256;
    bill.tint565=0xFFFF;bill.alpha=255;bill.blend=VXPE_BLEND_ALPHA;
    assert(vxpe25d_draw_billboard(fb,240,320,&cam,&sprite,&bill));
    assert(nonzero(fb,240*320)>0);

    std::memset(fb,0,sizeof(fb));
    VxpePlane25D plane{};
    plane.src={0,0,2,2};plane.center_x=120;plane.top_y=90;plane.bottom_y=150;
    plane.top_width=40;plane.bottom_width=180;plane.tint565=0xFFFF;
    plane.alpha=255;plane.blend=VXPE_BLEND_COPY;plane.ripple_amplitude=1;
    vxpe25d_draw_plane(fb,240,320,&sprite,&plane);
    assert(nonzero(fb,240*320)>100);

    vxpe25d_draw_ground_shadow(fb,240,320,&cam,0,160,16,5,0x0000,100,VXPE_BLEND_ALPHA);
    VxpeRopeStyle25D rope{0x4208,0xFFFF,3,1,220,VXPE_BLEND_ALPHA};
    assert(vxpe25d_draw_rope_world(fb,240,320,&cam,-20,70,120,20,0,240,&rope));

    uint16_t before=fb[160*240+120];
    VxpeGrade25D grade{vxpe2d_rgb565(80,130,90),48,40,8,24};
    vxpe25d_apply_grade(fb,240,320,&grade,80);
    assert(fb[160*240+120]!=before || before==0);

    cam.fog_near_z=100;cam.fog_far_z=300;cam.fog_strength=200;
    assert(vxpe25d_project(&cam,0,0,260,&p));
    assert(p.fog_alpha>0);
    std::puts("VXPE_SCENE25D_REGRESSION_PASS");
    return 0;
}
