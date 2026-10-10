#include "graphics/VxpSuperScaler.h"
#include <cassert>
#include <cstdint>
#include <cstdio>

int main() {
    constexpr int W=240,H=320,GUARD=16;
    uint16_t storage[W*H+GUARD*2];
    for (auto& p:storage) p=0xDEAD;
    VxpeSuperScalerConfig c{};
    c.horizon_y=105; c.center_x=120; c.far_half_width=8; c.near_half_width=118;
    c.curve_q8=24*256; c.road_phase=0; c.curb_period=12;
    c.sky565=0x245F; c.ground565=0x6D49; c.road_a565=0xC4C3; c.road_b565=0xE5A5;
    c.curb_a565=0xF800; c.curb_b565=0xFFFF; c.lane565=0xFFFF;
    auto* fb=storage+GUARD;
    assert(vxpe_superscaler_draw(fb,W,H,W,&c)==1);
    for(int i=0;i<GUARD;++i){assert(storage[i]==0xDEAD);if(storage[GUARD+W*H+i]!=0xDEAD){std::printf("guard %d = %04x\\n",i,storage[GUARD+W*H+i]);return 2;}}
    assert(fb[20*W]==c.sky565);
    assert(fb[300*W+120]!=c.sky565);
    /* Far road stays narrow and moves less under a curve than the foreground. */
    assert(fb[110*W+120]!=c.ground565);
    assert(fb[300*W+20]==c.ground565);
    assert(fb[300*W+120]!=c.ground565);
    uint32_t before=0;for(int i=0;i<W*H;++i)before+=fb[i];
    c.road_phase=73;
    assert(vxpe_superscaler_draw(fb,W,H,W,&c)==1);
    uint32_t after=0;for(int i=0;i<W*H;++i)after+=fb[i];assert(after!=before);
    c.horizon_y=319;
    assert(vxpe_superscaler_draw(fb,W,H,W,&c)==0);
    const uint16_t road_tile[4]={0,0xF800,0,0};
    const uint16_t ground_tile[4]={0xFFFF,0,0,0};
    c.horizon_y=105;c.road_phase=0;c.road_texture=road_tile;c.road_texture_w=2;c.road_texture_h=2;
    c.ground_texture=ground_tile;c.ground_texture_w=2;c.ground_texture_h=2;
    assert(vxpe_superscaler_draw(fb,W,H,W,&c)==1);
    assert(fb[105*W]==0xFFFF);assert(fb[105*W+113]==0xF800);
    c.road_texture_w=3;assert(vxpe_superscaler_draw(fb,W,H,W,&c)==0);
    std::puts("SuperScaler fixed-point road spans, curve, scrolling stripes, and bounds passed");
}
