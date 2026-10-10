#include "graphics/VxpToon3D.h"
#include <assert.h>
int main(void){
    uint16_t pixels[32*32],depth[32*32];
    VxpeToonTarget3D target={pixels,depth,32,32};
    VxpeToonCamera3D camera;VxpeToonMaterial3D material;
    VxpeVec3D quad[4]={{-8,8,24},{8,8,24},{8,-8,24},{-8,-8,24}};
    for(int i=0;i<32*32;++i){pixels[i]=0x1234;depth[i]=0x5678;}
    vxpe_toon3d_clear_depth(&target);
    for(int i=0;i<32*32;++i)assert(pixels[i]==0x1234&&depth[i]==65535);
    vxpe_toon3d_camera_init(&camera,32,32);vxpe_toon3d_material_init(&material,0xFFE0);
    vxpe_toon3d_clear(&target,0);assert(vxpe_toon3d_quad(&target,&camera,quad,&material,255)>0);
    assert(pixels[16*32+16]==0xFFE0);
    VxpeVec3D triangle[3]={{-12,-8,24},{12,-8,24},{0,12,24}};uint8_t vertex_light[3]={40,255,100};
    vxpe_toon3d_clear(&target,0);assert(vxpe_toon3d_triangle_gouraud(&target,&camera,triangle[0],triangle[1],triangle[2],&material,vertex_light,0)>0);
    /* Textured Gouraud and its quad wrapper must be reachable from plain C. */
    uint16_t texPixels[4]={0xFFFF,0xFFFF,0xFFFF,0xFFFF};uint8_t texAlpha[4]={255,255,255,255};
    VxpeSpriteA8 texture={texPixels,texAlpha,2,2,2,2,0};
    VxpeToonVertex3D textured[3]={{{-12,-8,24},0,0},{{12,-8,24},3*256,0},{{0,12,24},0,0}};
    vxpe_toon3d_clear(&target,0);
    assert(vxpe_toon3d_triangle_gouraud_textured(&target,&camera,textured,&texture,&material,vertex_light,0)>0);
    VxpeToonVertex3D texturedQuad[4]={{{-12,-8,24},0,0},{{12,-8,24},3*256,0},{{12,12,24},3*256,3*256},{{-12,12,24},0,3*256}};
    uint8_t quad_light[4]={40,255,100,200};
    vxpe_toon3d_clear(&target,0);
    assert(vxpe_toon3d_quad_gouraud_textured(&target,&camera,texturedQuad,&texture,&material,quad_light)>0);
    return 0;
}
