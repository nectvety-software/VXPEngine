#include "graphics/VxpRaycast3D.h"
#include <cassert>
#include <cstdio>

int main(){
    static const uint8_t map[8*8]={
        1,1,1,1,1,1,1,1,
        1,0,0,0,0,0,0,1,
        1,0,0,0,0,0,0,1,
        1,0,0,0,0,0,0,1,
        1,0,0,0,0,0,0,1,
        1,0,0,0,0,0,0,1,
        1,1,1,2,1,1,1,1,
        1,1,1,1,1,1,1,1};
    static const uint16_t wallPixels[16]={0x7800,0x7800,0x7800,0x7800,0x7800,0xA800,0xA800,0x7800,0x7800,0x7800,0x7800,0x7800,0xA800,0x7800,0x7800,0x7800};
    static const uint16_t floorPixels[16]={0x0320,0x0320,0x0320,0x0320,0x0320,0x0460,0x0460,0x0320,0x0320,0x0460,0x0460,0x0320,0x0320,0x0320,0x0320,0x0320};
    static const uint16_t wall2Pixels[16]={0x001F,0x001F,0x001F,0x001F,0x001F,0x03FF,0x03FF,0x001F,0x001F,0x001F,0x001F,0x001F,0x03FF,0x001F,0x001F,0x001F};
    const VxpeRaycastTexture walls[2]={{wallPixels,4,4,4},{wall2Pixels,4,4,4}};
    const VxpeRaycastTexture floor={floorPixels,4,4,4};
    VxpeRaycastScene scene{};scene.map={map,8,8,8};scene.wall_textures=walls;scene.wall_count=2;scene.floor_texture=floor;scene.sky565=0x867D;scene.fog565=0x4208;scene.fog_near_q8=900;scene.fog_far_q8=1800;scene.fog_strength=100;scene.dither_strength=5;
    uint16_t pixels[40*30+2],depth[40+2];pixels[0]=pixels[40*30+1]=0x1234;depth[0]=depth[41]=0x5678;
    VxpeRaycastTarget target={pixels+1,40,30,40,depth+1};VxpeRaycastCamera camera;vxpe_raycast3d_camera_init(&camera,40,30,14,32);camera.x_q8=3*256+128;camera.z_q8=3*256+128;camera.max_distance_q8=1800;
    assert(vxpe_raycast3d_render(&target,&camera,&scene));
    assert(depth[20+1]>0&&depth[20+1]<camera.max_distance_q8);
    assert(pixels[0]==0x1234&&pixels[40*30+1]==0x1234&&depth[0]==0x5678&&depth[41]==0x5678);
    int colors=0;for(int i=0;i<40*30;++i)colors+=pixels[i+1]!=0;assert(colors>400);
    static const uint16_t spritePixels[4]={0xFFFF,0xFFFF,0xFFFF,0xFFFF};static const uint8_t alpha[4]={255,255,255,255};
    VxpeSpriteA8 sprite={spritePixels,alpha,2,2,2,2,0};VxpeRaycastBillboard object={3*256+128,5*256,0,128,256,0xFFFF,255};
    assert(vxpe_raycast3d_billboard(&target,&camera,&sprite,&object)>0);
    object.z_q8=7*256;assert(vxpe_raycast3d_billboard(&target,&camera,&sprite,&object)==0);
    VxpeRaycastScene invalid=scene;invalid.wall_count=0;assert(!vxpe_raycast3d_render(&target,&camera,&invalid));
    puts("PASS: raycast DDA, RGB565 wall/floor texture, distance fog+dither, billboard depth occlusion and buffer guards");
}
