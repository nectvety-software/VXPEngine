#include "graphics/VxpScene25D.h"
#include <assert.h>
#include <string.h>

int main(void){
    static uint16_t fb[120*160];
    const uint16_t texPixels[4]={0xF800,0x07E0,0x001F,0xFFFF};
    VxpeSpriteA8 texture={texPixels,0,2,2,2,2,1};
    VxpeCamera25D camera;
    vxpe25d_camera_init(&camera,120,160,80,100);
    camera.world_y=48;
    /* Ground entry point reachable from C99 with plain initializers. */
    VxpeGround25D ground;
    memset(&ground,0,sizeof(ground));
    ground.src.x=0;ground.src.y=0;ground.src.w=2;ground.src.h=2;
    ground.tile_w=4;ground.tile_h=4;ground.blend=VXPE_BLEND_COPY;
    vxpe25d_draw_ground(fb,120,160,&camera,&texture,&ground);
    {
        int painted=0,i;
        for(i=0;i<120*160;++i)if(fb[i])++painted;
        assert(painted>1000);
    }
    /* Batch API reachable from C99. */
    VxpeBillboardBatch25D batch;
    vxpe25d_batch_init(&batch);
    VxpeBatchEntry25D entry;
    memset(&entry,0,sizeof(entry));
    entry.sprite=&texture;
    entry.billboard.src.x=0;entry.billboard.src.y=0;
    entry.billboard.src.w=2;entry.billboard.src.h=2;
    entry.billboard.world_z=160;entry.billboard.world_w=8;entry.billboard.world_h=8;
    entry.billboard.pivot_x_q8=128;entry.billboard.pivot_y_q8=256;
    entry.billboard.alpha=255;entry.billboard.blend=VXPE_BLEND_ALPHA;
    assert(vxpe25d_batch_push(&batch,&entry));
    assert(vxpe25d_batch_flush(&batch,fb,120,160,&camera)==1);
    return 0;
}
