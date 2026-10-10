#include "graphics/VxpStage2D.h"
#include <cassert>
#include <cstdio>

static int changed(const uint16_t* fb,int n){int c=0;for(int i=0;i<n;++i)if(fb[i])++c;return c;}

int main(){
    VxpeStageCamera2D cam{};
    vxpe_stage_camera_init(&cam,240,480);
    assert(cam.max_x_q8==(240<<8));
    vxpe_stage_camera_follow(&cam,220,256);
    assert(cam.x_q8>0);
    assert(vxpe_stage_world_to_screen_x(&cam,220)<=cam.deadzone_right);

    uint16_t tex[32*8];
    for(int y=0;y<8;++y)for(int x=0;x<32;++x)
        tex[y*32+x]=vxpe2d_rgb565((uint8_t)(20+x*4),(uint8_t)(60+y*12),(uint8_t)(120+x*2));
    VxpeSprite565 sprite{tex,nullptr,32,8,32,1};
    static uint16_t fb[240*80];
    VxpeStageBand2D band{};
    band.src={0,0,32,8}; band.dst_y=10; band.dst_h=50;
    band.parallax_q8=128; band.tint565=0xFFFF; band.alpha=255;
    band.blend=VXPE_BLEND_COPY; band.repeat_x=1; band.raster_wave=1;
    band.wave_amplitude=4; band.wave_phase=3; band.wave_shift=2;
    vxpe_stage_draw_band565(fb,240,80,&sprite,&cam,&band);
    assert(changed(fb,240*80)>5000);

    assert(vxpe_stage_cycle565(0x001F,0x07E0,0)!=vxpe_stage_cycle565(0x001F,0x07E0,8));
    std::puts("VXPE_STAGE2D_REGRESSION_PASS");
    return 0;
}
