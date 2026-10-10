#include "graphics/VxpToon3D.h"
#include <assert.h>
int main(void){
    uint16_t pixels[32*32],depth[32*32];
    VxpeToonTarget3D target={pixels,depth,32,32};
    VxpeToonCamera3D camera;VxpeToonMaterial3D material;
    VxpeVec3D quad[4]={{-8,8,24},{8,8,24},{8,-8,24},{-8,-8,24}};
    vxpe_toon3d_camera_init(&camera,32,32);vxpe_toon3d_material_init(&material,0xFFE0);
    vxpe_toon3d_clear(&target,0);assert(vxpe_toon3d_quad(&target,&camera,quad,&material,255)>0);
    assert(pixels[16*32+16]==0xFFE0);return 0;
}
