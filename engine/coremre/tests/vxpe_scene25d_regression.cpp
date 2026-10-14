#include "graphics/VxpScene25D.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <climits>

static int nonzero(const uint16_t* fb,int n){int c=0;for(int i=0;i<n;++i)if(fb[i])++c;return c;}

int main(){
    VxpeCamera25D cam{};
    vxpe25d_camera_init(&cam,240,320,80,160);
    VxpeProjected25D p{};
    assert(vxpe25d_project(&cam,0,0,160,&p));
    assert(p.x==120);
    assert(p.y==144);
    assert(p.scale_q8==256);
    assert(cam.cos_yaw_q14==16384&&cam.cos_pitch_q14==16384);
    // A quarter turn around the camera makes world +X point directly ahead.
    cam.world_x=cam.world_y=cam.world_z=0;cam.sin_yaw_q14=16384;cam.cos_yaw_q14=0;cam.fog_strength=0;
    assert(vxpe25d_project(&cam,160,0,0,&p)&&p.x==120&&p.depth==160);
    assert(!vxpe25d_project(&cam,0,0,160,&p));
    cam.sin_yaw_q14=0;cam.cos_yaw_q14=16384;assert(vxpe25d_project(&cam,0,0,160,&p));int level_y=p.y;
    cam.sin_pitch_q14=8192;cam.cos_pitch_q14=14189;
    assert(vxpe25d_project(&cam,0,0,160,&p)&&p.y<level_y);
    cam.sin_pitch_q14=0;cam.cos_pitch_q14=16384;
    // Extreme world deltas are rejected without overflowing signed 32-bit math.
    cam.world_x=INT32_MIN;assert(!vxpe25d_project(&cam,INT32_MAX,0,160,&p));cam.world_x=0;

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

    // --- perspective ground plane, anchored to the 2.5D camera ---
    VxpeCamera25D gcam{};
    vxpe25d_camera_init(&gcam,240,320,160,160);
    gcam.world_y=64;gcam.fog_strength=0;
    VxpeSpriteA8 tex{};
    tex.pixels=px;tex.width=2;tex.height=2;tex.stride=2;tex.opaque=1;
    VxpeGround25D ground{};
    ground.src={0,0,2,2};ground.tile_w=4;ground.tile_h=4;
    ground.tint565=0;ground.alpha=0;ground.blend=VXPE_BLEND_COPY;ground.use_fog=0;
    std::memset(fb,0,sizeof(fb));
    vxpe25d_draw_ground(fb,240,320,&gcam,&tex,&ground);
    assert(nonzero(fb,240*320)>4000);
    // Sliding exactly one tile repeats the pattern pixel-for-pixel.
    static uint16_t ref[240*320];
    std::memcpy(ref,fb,sizeof(ref));
    gcam.world_z=4;
    vxpe25d_draw_ground(fb,240,320,&gcam,&tex,&ground);
    assert(std::memcmp(ref,fb,sizeof(ref))==0);
    // Half a tile shifts the two-pixel rows, so the image must change.
    gcam.world_z=2;
    vxpe25d_draw_ground(fb,240,320,&gcam,&tex,&ground);
    assert(std::memcmp(ref,fb,sizeof(ref))!=0);
    // With yaw the world X axis steps along screen rows; one tile in X
    // must again be a pixel-exact repeat.
    gcam.world_z=0;gcam.sin_yaw_q14=16384;gcam.cos_yaw_q14=0;
    vxpe25d_draw_ground(fb,240,320,&gcam,&tex,&ground);
    std::memcpy(ref,fb,sizeof(ref));
    gcam.world_x=4;
    vxpe25d_draw_ground(fb,240,320,&gcam,&tex,&ground);
    assert(std::memcmp(ref,fb,sizeof(ref))==0);
    gcam.world_x=2;
    vxpe25d_draw_ground(fb,240,320,&gcam,&tex,&ground);
    assert(std::memcmp(ref,fb,sizeof(ref))!=0);
    // Step scale with a level camera: at row 319 (dy=159) z is ~64 world
    // units, so with focal 160 px each 4-unit tile spans ~10 px and the
    // 2-texel-wide texture must alternate ~48 times across the row.  A
    // 256x step error (z_q8<<8 instead of <<16) collapses rows to one texel.
    gcam.sin_yaw_q14=0;gcam.cos_yaw_q14=16384;gcam.world_x=0;gcam.world_z=0;
    std::memset(fb,0,sizeof(fb));
    vxpe25d_draw_ground(fb,240,320,&gcam,&tex,&ground);
    {
        int changes=0,c0=0,c1=0;
        for(int x=1;x<240;++x)if(fb[319*240+x]!=fb[319*240+x-1])++changes;
        for(int x=0;x<240;++x){
            if(fb[319*240+x]==0xF800)++c0;
            else if(fb[319*240+x]==0x07E0)++c1;
        }
        assert(changes>=20);
        assert(c0>30&&c1>30&&c0+c1>=230); // row 319 samples texture row 0
        // One full tile in X repeats pixel-exactly even without yaw.
        std::memcpy(ref,fb,sizeof(ref));
        gcam.world_x=4;
        vxpe25d_draw_ground(fb,240,320,&gcam,&tex,&ground);
        assert(std::memcmp(ref,fb,sizeof(ref))==0);
        gcam.world_x=1; // a quarter tile must shift the texel boundaries
        vxpe25d_draw_ground(fb,240,320,&gcam,&tex,&ground);
        assert(std::memcmp(ref,fb,sizeof(ref))!=0);
        gcam.world_x=0;
    }
    // A band with no reachable depth (near beyond far) writes nothing.
    std::memset(fb,0,sizeof(fb));
    gcam.sin_yaw_q14=0;gcam.cos_yaw_q14=16384;gcam.world_x=0;
    gcam.near_z=2000;gcam.far_z=1024;
    vxpe25d_draw_ground(fb,240,320,&gcam,&tex,&ground);
    assert(nonzero(fb,240*320)==0);
    gcam.near_z=16;
    // Fogged rows blend toward the fog colour; untextured guard paths no-op.
    gcam.fog_near_z=10;gcam.fog_far_z=60;gcam.fog_strength=200;
    gcam.fog_color565=0x001F;ground.use_fog=1;
    std::memset(fb,0,sizeof(fb));
    vxpe25d_draw_ground(fb,240,320,&gcam,&tex,&ground);
    assert(nonzero(fb,240*320)>4000);
    ground.tile_w=0;
    uint16_t keep=fb[200*240];
    vxpe25d_draw_ground(fb,240,320,&gcam,&tex,&ground);
    assert(fb[200*240]==keep);
    ground.tile_w=4;
    // Horizon seam: focal_q8=40960, world_y=64 -> z_q8=2621440/dy, so with
    // far_z=160 rows 161..222 are past the far plane (dy<64) and rows 224+
    // still draw texture.  With use_fog the culled band must be painted the
    // fog colour instead of leaving stale framebuffer content.
    gcam.far_z=160;
    ground.alpha=255;
    std::memset(fb,0xFF,sizeof(fb));
    vxpe25d_draw_ground(fb,240,320,&gcam,&tex,&ground);
    for(int y=160;y<223;++y)assert(fb[y*240+119]==0x001F); // incl. horizon row
    std::memset(fb,0xFF,sizeof(fb));
    ground.use_fog=0;
    vxpe25d_draw_ground(fb,240,320,&gcam,&tex,&ground);
    for(int y=160;y<223;++y)assert(fb[y*240+119]==0xFFFF); // no fog: band untouched
    assert(fb[300*240+119]!=0xFFFF); // nearer rows still draw texture
    ground.use_fog=1;
    gcam.far_z=1024;

    // --- depth-sorted billboard batch ---
    const uint16_t green2[4]={0x07E0,0x07E0,0x07E0,0x07E0};
    const uint16_t red2[4]={0xF800,0xF800,0xF800,0xF800};
    VxpeSpriteA8 nearSprite{green2,nullptr,2,2,2,2,1};
    VxpeSpriteA8 farSprite{red2,nullptr,2,2,2,2,1};
    VxpeCamera25D bcam{};
    vxpe25d_camera_init(&bcam,240,320,100,160);
    bcam.world_y=64;bcam.fog_strength=0;
    VxpeBillboardBatch25D batch{};
    vxpe25d_batch_init(&batch);
    VxpeBatchEntry25D en{};
    en.sprite=&nearSprite;
    en.billboard.src={0,0,2,2};en.billboard.world_x=0;en.billboard.world_y=0;
    en.billboard.world_z=160;en.billboard.world_w=10;en.billboard.world_h=20;
    en.billboard.pivot_x_q8=128;en.billboard.pivot_y_q8=256;
    en.billboard.tint565=0xFFFF;en.billboard.alpha=255;en.billboard.blend=VXPE_BLEND_ALPHA;
    VxpeBatchEntry25D ef=en;
    ef.sprite=&farSprite;ef.billboard.world_z=200;ef.billboard.world_w=8;ef.billboard.world_h=16;
    // Near pushed first: the sort must still draw far first, so where the
    // sprites overlap the near (green) colour survives.
    assert(vxpe25d_batch_push(&batch,&en));
    assert(vxpe25d_batch_push(&batch,&ef));
    std::memset(fb,0,sizeof(fb));
    assert(vxpe25d_batch_flush(&batch,fb,240,320,&bcam)==2);
    assert(batch.count==0);
    // Near covers rows 144..163 at columns 115..124, far rows 135..150 at
    // columns 117..122; row 150 column 120 lies in both.
    assert(fb[150*240+120]==0x07E0);
    // Unprojectable entries are culled silently.
    VxpeBatchEntry25D ego=en;ego.billboard.world_z=-100;
    VxpeBatchEntry25D efar=en;efar.billboard.world_x=1000000;
    vxpe25d_batch_push(&batch,&ego);
    vxpe25d_batch_push(&batch,&efar);
    vxpe25d_batch_push(&batch,&en);
    assert(vxpe25d_batch_flush(&batch,fb,240,320,&bcam)==1);
    // Overflow accounting keeps the existing 2D batch contract.
    for(int i=0;i<VXPE_BATCH25D_MAX;++i)assert(vxpe25d_batch_push(&batch,&en));
    assert(!vxpe25d_batch_push(&batch,&en));
    assert(batch.dropped==1);
    assert(vxpe25d_batch_flush(&batch,fb,240,320,&bcam)==VXPE_BATCH25D_MAX);
    assert(!vxpe25d_batch_push(&batch,nullptr));
    // Batch shadows darken ground beside a narrow billboard.
    std::memset(fb,0xFFFF,sizeof(fb));
    VxpeBatchEntry25D es=en;es.billboard.world_w=4;es.billboard.world_h=4;
    es.shadow_radius_x=10;es.shadow_radius_y=3;es.shadow_color565=0x0000;
    es.shadow_alpha=128;es.shadow_blend=VXPE_BLEND_ALPHA;
    vxpe25d_batch_push(&batch,&es);
    vxpe25d_batch_flush(&batch,fb,240,320,&bcam);
    // Shadow centre row is the projected ground point (y=164 at z=160,
    // scale 1.0); its rim reaches ~8 px from centre while the 4-wide
    // sprite covers columns 118..121 of rows 160..163.
    assert(fb[164*240+126]!=0xFFFF);
    assert(fb[163*240+120]==0x07E0);

    std::puts("VXPE_SCENE25D_REGRESSION_PASS");
    return 0;
}
