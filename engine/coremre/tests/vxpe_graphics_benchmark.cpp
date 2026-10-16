#include "graphics/VxpScene25D.h"
#include "graphics/VxpToon3D.h"
#include "graphics/VxpRender2D.h"
#include "action2d/VxpTilemap2D.h"
#include "action2d/VxpCamera2D.h"
#include "action2d/VxpBody2D.h"

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <filesystem>

namespace {
using Clock = std::chrono::steady_clock;
static uint16_t pixels25[240 * 320];
static uint16_t pixels3d[240 * 320];
static uint16_t depth3d[240 * 320];
static uint16_t spritePixels[16 * 24];
static uint8_t spriteAlpha[16 * 24];
static uint16_t exactImage[240 * 320];
static uint16_t floorTex[8*8],glassTex[8*8],waterTex[8*8],roofTex[8*8];
static VxpeSpriteA8 floorSprite{},glassSprite{},waterSprite{},roofSprite{};
static int width=240,height=320;
static const int16_t SIN_Q14[32]={0,3196,6270,9102,11585,13623,15137,16069,16384,16069,15137,13623,11585,9102,6270,3196,0,-3196,-6270,-9102,-11585,-13623,-15137,-16069,-16384,-16069,-15137,-13623,-11585,-9102,-6270,-3196};
static const int16_t COS_Q14[32]={16384,16069,15137,13623,11585,9102,6270,3196,0,-3196,-6270,-9102,-11585,-13623,-15137,-16069,-16384,-16069,-15137,-13623,-11585,-9102,-6270,-3196,0,3196,6270,9102,11585,13623,15137,16069};
static int animationPhase=0;

static void write_ppm(const char* path,const uint16_t* pixels,int w,int h){
    FILE* f=std::fopen(path,"wb");if(!f)return;
    std::fprintf(f,"P6\n%d %d\n255\n",w,h);
    for(int i=0;i<w*h;++i){uint16_t p=pixels[i];uint8_t rgb[3]={
        (uint8_t)(((p>>11)&31)*255/31),(uint8_t)(((p>>5)&63)*255/63),(uint8_t)((p&31)*255/31)};
        std::fwrite(rgb,1,3,f);}
    std::fclose(f);
}
static uint64_t checksum(const uint16_t* p,int n){uint64_t h=1469598103934665603ull;for(int i=0;i<n;++i)h=(h^p[i])*1099511628211ull;return h;}
static void init_sprite(){
    std::memset(spritePixels,0,sizeof(spritePixels));std::memset(spriteAlpha,0,sizeof(spriteAlpha));
    for(int y=0;y<24;++y)for(int x=0;x<16;++x){
        bool leaf=(y<15&&x>=2&&x<=13&&((x+y)%5!=0));
        bool trunk=(y>=11&&y<23&&x>=7&&x<=9);
        int i=y*16+x;if(leaf||trunk){spritePixels[i]=trunk?0x9B2A:((x+y)%3?0x46C8:0x6F4A);spriteAlpha[i]=255;}
    }
}
static uint16_t rgb565(int r,int g,int b){return vxpe2d_rgb565((uint8_t)r,(uint8_t)g,(uint8_t)b);}
static void init_textures(){
    for(int y=0;y<8;++y)for(int x=0;x<8;++x){int i=y*8+x;
        floorTex[i]=((x/2+y/2)&1)?rgb565(173,145,111):rgb565(126,111,104);
        glassTex[i]=((x+y)&3)?rgb565(54,157,185):rgb565(147,220,225);
        roofTex[i]=(y==0||y==7||x==0||x==7)?rgb565(230,194,117):((x+y)&1)?rgb565(105,188,213):rgb565(76,150,183);
        int wave=(y+(x/2))&7;waterTex[i]=(wave==0||wave==1)?rgb565(191,247,225):((x+y)&1)?rgb565(36,174,190):rgb565(22,128,166);
    }
    floorSprite={floorTex,0,8,8,8,8,1};glassSprite={glassTex,0,8,8,8,8,1};
    waterSprite={waterTex,0,8,8,8,8,1};roofSprite={roofTex,0,8,8,8,8,1};
}
static void render25d(){
    for(int y=0;y<height;++y){uint16_t c=y<height*3/10?rgb565(111,193,217):(y<height*38/100?rgb565(175,222,210):rgb565(85,74,78));for(int x=0;x<width;++x)pixels25[y*width+x]=c;}
    VxpePlane25D floor{};floor.src={0,0,8,8};floor.center_x=(int16_t)(width/2);floor.top_y=(int16_t)(height*34/100);floor.bottom_y=(int16_t)height;
    floor.top_width=(uint16_t)(width*2/3);floor.bottom_width=(uint16_t)(width*3/2);floor.tint565=0xFFFF;floor.alpha=255;floor.blend=VXPE_BLEND_COPY;
    vxpe25d_draw_plane(pixels25,width,height,&floorSprite,&floor);
    VxpeCamera25D cam;vxpe25d_camera_init(&cam,width,height,height*3/10,width*164/240);cam.world_y=44;cam.fog_strength=80;
    cam.world_x=SIN_Q14[(animationPhase/2)&31]*8/16384;cam.world_z=animationPhase*3;
    cam.sin_yaw_q14=(int16_t)(SIN_Q14[(animationPhase/2)&31]/10);cam.cos_yaw_q14=16384;
    VxpeSpriteA8 sprite={spritePixels,spriteAlpha,16,24,16,16,0};
    for(int i=47;i>=0;--i){int row=i/8,col=i%8;int z=76+row*58,x=(col-4)*68+(row%2)*28;
        vxpe25d_draw_ground_shadow(pixels25,width,height,&cam,x,z,13,4,0x2104,128,VXPE_BLEND_ALPHA);
        VxpeBillboard25D b{};b.src={0,0,16,24};b.world_x=x;b.world_y=0;b.world_z=z;
        b.world_w=22;b.world_h=34;b.pivot_x_q8=128;b.pivot_y_q8=256;b.tint565=0xFFFF;b.alpha=255;b.blend=VXPE_BLEND_ALPHA;
        vxpe25d_draw_billboard(pixels25,width,height,&cam,&sprite,&b);
    }
}
static VxpeSpriteA8 treeSprite{spritePixels,spriteAlpha,16,24,16,16,0};
static VxpeBillboardBatch25D gameBatch;
// A drivable 2.5D scene: camera-anchored tiled ground plus 48 depth-sorted
// billboard trees with projected shadows, pushed in random order every frame.
static void render25d_game(){
    VxpeCamera25D cam;vxpe25d_camera_init(&cam,width,height,height*3/10,width*164/240);
    cam.world_y=44;cam.fog_strength=80;
    cam.world_x=SIN_Q14[(animationPhase/2)&31]*8/16384;cam.world_z=animationPhase*6;
    cam.sin_yaw_q14=(int16_t)(SIN_Q14[(animationPhase/2)&31]/10);cam.cos_yaw_q14=16384;
    for(int y=0;y<height;++y){uint16_t c=y<height*3/10?rgb565(111,193,217):rgb565(175,222,210);for(int x=0;x<width;++x)pixels25[y*width+x]=c;}
    VxpeGround25D ground{};ground.src={0,0,8,8};ground.tile_w=32;ground.tile_h=32;
    ground.tint565=0;ground.alpha=0;ground.blend=VXPE_BLEND_COPY;ground.use_fog=1;
    vxpe25d_draw_ground(pixels25,width,height,&cam,&floorSprite,&ground);
    vxpe25d_batch_init(&gameBatch);
    for(int i=0;i<48;++i){int row=i/8,col=i%8;int z=76+row*58,x=(col-4)*68+(row%2)*28;
        VxpeBatchEntry25D e{};e.sprite=&treeSprite;
        e.billboard.src={0,0,16,24};e.billboard.world_x=x;e.billboard.world_y=0;e.billboard.world_z=z;
        e.billboard.world_w=22;e.billboard.world_h=34;e.billboard.pivot_x_q8=128;e.billboard.pivot_y_q8=256;
        e.billboard.tint565=0xFFFF;e.billboard.alpha=255;e.billboard.blend=VXPE_BLEND_ALPHA;
        e.shadow_radius_x=13;e.shadow_radius_y=4;e.shadow_color565=0x2104;e.shadow_alpha=128;e.shadow_blend=VXPE_BLEND_ALPHA;
        vxpe25d_batch_push(&gameBatch,&e);}
    vxpe25d_batch_flush(&gameBatch,pixels25,width,height,&cam);
}
static void render25d_game_dispatch(){render25d_game();animationPhase=(animationPhase+1)&63;}
static void draw_box(VxpeToonTarget3D* t,const VxpeToonCamera3D* c,int x,int z,int w,int h,int d,const VxpeToonMaterial3D* m){    int x1=x+w,z1=z+d,y1=h;
    VxpeVec3D q[4];
    q[0]={x,0,z};q[1]={x1,0,z};q[2]={x1,y1,z};q[3]={x,y1,z};vxpe_toon3d_quad(t,c,q,m,220);
    q[0]={x,0,z1};q[1]={x,0,z};q[2]={x,y1,z};q[3]={x,y1,z1};vxpe_toon3d_quad(t,c,q,m,175);
    q[0]={x1,0,z};q[1]={x1,0,z1};q[2]={x1,y1,z1};q[3]={x1,y1,z};vxpe_toon3d_quad(t,c,q,m,145);
    q[0]={x,y1,z};q[1]={x1,y1,z};q[2]={x1,y1,z1};q[3]={x,y1,z1};vxpe_toon3d_quad(t,c,q,m,255);
}
static void render3d(int w,int h,bool affine){
    VxpeToonTarget3D target={pixels3d,depth3d,(uint16_t)w,(uint16_t)h};
    VxpeToonCamera3D cam;vxpe_toon3d_camera_init(&cam,w,h);cam.position={0,34,0};cam.horizon_y=(int16_t)(h*2/5);cam.focal_px=(uint16_t)(w*2/3);cam.far_z=1200;
    cam.sin_yaw_q14=3196;cam.cos_yaw_q14=16069;cam.sin_pitch_q14=2600;cam.cos_pitch_q14=16176;
    vxpe_toon3d_clear(&target,0x7DDF);
    VxpeToonMaterial3D mats[4];uint16_t colors[4]={0x9B2A,0x46C8,0xFC69,0x7A6A};
    for(int i=0;i<4;++i){vxpe_toon3d_material_init(&mats[i],colors[i]);mats[i].outline_px=0;mats[i].fog_alpha=0;mats[i].affine_depth=affine?1:0;}
    // A tilted tiled plaza and repeated storefront blocks stress clipping,
    // coverage, perspective depth and overdraw using only the public core API.
    for(int z=16;z<900;z+=48){
        for(int x=-300;x<300;x+=100){VxpeVec3D q[4]={{x,0,z},{x+100,0,z},{x+100,0,z+100},{x,0,z+100}};
            vxpe_toon3d_quad(&target,&cam,q,&mats[((x/100+z/100)&1)?1:2],185);}
    }
    for(int z=80;z<900;z+=100){
        draw_box(&target,&cam,-205,z+14,44,88,42,&mats[0]);
        draw_box(&target,&cam,-68,z+14,44,112,42,&mats[2]);
        draw_box(&target,&cam,75,z+14,44,72,42,&mats[3]);
        draw_box(&target,&cam,178,z+14,34,98,42,&mats[1]);
    }
}
static void textured_quad(VxpeToonTarget3D* target,const VxpeToonCamera3D* camera,
    const VxpeVec3D p[4],const VxpeSpriteA8* texture,int light,int uOffset=0){
    VxpeToonVertex3D v[4];
    for(int i=0;i<4;++i)v[i]={p[i],((i==1||i==2)?7*256:0)+uOffset,((i>=2)?7*256:0)};
    VxpeToonMaterial3D m;vxpe_toon3d_material_init(&m,0xFFFF);m.outline_px=0;m.fog_alpha=0;m.texture_wrap=1;
    vxpe_toon3d_quad_textured(target,camera,v,texture,&m,(uint8_t)light);
}
static void box_face(VxpeToonTarget3D* target,const VxpeToonCamera3D* camera,
    VxpeVec3D a,VxpeVec3D b,VxpeVec3D c,VxpeVec3D d,uint16_t color,int light){
    VxpeToonMaterial3D m;vxpe_toon3d_material_init(&m,color);m.outline_px=0;m.fog_alpha=0;
    VxpeVec3D q[4]={a,b,c,d};vxpe_toon3d_quad(target,camera,q,&m,(uint8_t)light);
}
static void draw_retro_mall(int w,int h,int phase){
    VxpeToonTarget3D target={pixels3d,depth3d,(uint16_t)w,(uint16_t)h};
    VxpeToonCamera3D cam;vxpe_toon3d_camera_init(&cam,w,h);
    cam.position={SIN_Q14[(phase/2)&31]*8/16384,48+SIN_Q14[(phase/4)&31]*2/16384,24+phase*3};
    cam.sin_yaw_q14=(int16_t)(SIN_Q14[(phase/2)&31]/8);cam.cos_yaw_q14=16384;
    cam.sin_pitch_q14=2300;cam.cos_pitch_q14=16221;cam.horizon_y=(int16_t)(h*34/100);cam.focal_px=(uint16_t)(w*7/10);cam.far_z=1150;
    vxpe_toon3d_clear(&target,rgb565(98,181,210));
    VxpeToonMaterial3D floorMaterial;vxpe_toon3d_material_init(&floorMaterial,0xFFFF);floorMaterial.outline_px=0;floorMaterial.fog_alpha=0;floorMaterial.texture_wrap=1;
    // Low-resolution tiled terrazzo; flat per-face values act as baked light.
    for(int z=12;z<1000;z+=90)for(int x=-360;x<360;x+=90){
        VxpeVec3D q[4]={{x,0,z},{x+90,0,z},{x+90,0,z+90},{x,0,z+90}};
        textured_quad(&target,&cam,q,&floorSprite,((x/90+z/90)&1)?205:165);
    }
    // Sky-lit glass ceiling and brass ribs form strong retro perspective lines.
    for(int z=50;z<1000;z+=150){
        VxpeVec3D roof[4]={{-155,132,z},{155,132,z},{155,132,z+144},{-155,132,z+144}};
        textured_quad(&target,&cam,roof,&roofSprite,220);
        box_face(&target,&cam,{-157,127,z},{-151,127,z},{-151,135,z+144},{-157,135,z+144},rgb565(221,177,95),255);
        box_face(&target,&cam,{151,127,z},{157,127,z},{157,135,z+144},{151,135,z+144},rgb565(221,177,95),255);
    }
    // Repeating shop fronts: teal low-res glass, warm baked wall panels.
    for(int z=30;z<1020;z+=150){
        VxpeVec3D leftWall[4]={{-166,0,z},{-166,120,z},{-166,120,z+140},{-166,0,z+140}};
        VxpeVec3D rightWall[4]={{166,0,z},{166,0,z+140},{166,120,z+140},{166,120,z}};
        box_face(&target,&cam,{-170,0,z},{-164,0,z},{-164,120,z+140},{-170,120,z+140},rgb565(143,94,77),210);
        box_face(&target,&cam,{164,0,z},{170,0,z},{170,120,z+140},{164,120,z+140},rgb565(137,93,84),180);
        textured_quad(&target,&cam,leftWall,&glassSprite,220);
        textured_quad(&target,&cam,rightWall,&glassSprite,195);
        // Original abstract signage blocks; static face illumination simulates baked lighting.
        box_face(&target,&cam,{-165,96,z+22},{-164,96,z+22},{-164,108,z+83},{-165,108,z+83},rgb565(243,91,153),255);
        box_face(&target,&cam,{164,96,z+22},{165,96,z+22},{165,108,z+83},{164,108,z+83},rgb565(248,197,103),255);
    }
    // Eight-sided fountain basin with animated 8x8 water and low-poly spout.
    const int fz=185, radius=54;static const int8_t cx[8]={100,70,0,-70,-100,-70,0,70},cz[8]={0,70,100,70,0,-70,-100,-70};
    for(int i=0;i<8;++i){int j=(i+1)&7;VxpeVec3D tri[4]={{0,4,fz},{cx[i]*radius/100,4,fz+cz[i]*radius/100},{cx[j]*radius/100,4,fz+cz[j]*radius/100},{0,12,fz}};
        box_face(&target,&cam,tri[0],tri[1],tri[2],tri[2],rgb565(129,112,91),195);}
    VxpeVec3D water[4]={{-37,11,fz-37},{37,11,fz-37},{37,11,fz+37},{-37,11,fz+37}};
    textured_quad(&target,&cam,water,&waterSprite,225,(phase/3%8)*256);
    box_face(&target,&cam,{-7,12,fz-7},{7,12,fz-7},{7,36,fz+7},{-7,36,fz+7},rgb565(222,190,126),235);
    // Arcade cabinet screens and a pizza counter use original color blocks.
    box_face(&target,&cam,{-93,0,300},{-52,0,300},{-52,70,300},{-93,70,300},rgb565(69,55,83),185);
    VxpeVec3D tv[4]={{-87,29,302},{-58,29,302},{-58,59,302},{-87,59,302}};textured_quad(&target,&cam,tv,&roofSprite,245,(phase/2%8)*256);
    box_face(&target,&cam,{56,0,430},{119,0,430},{119,47,430},{56,47,430},rgb565(202,107,83),220);
    box_face(&target,&cam,{48,47,406},{127,47,406},{127,53,454},{48,53,454},rgb565(238,188,112),240);
    // Aquarium glass and tiny fish oscillate while the camera glides past.
    for(int z=600;z<1000;z+=78){
        VxpeVec3D glass[4]={{-139,8,z},{-139,100,z},{-139,100,z+72},{-139,8,z+72}};textured_quad(&target,&cam,glass,&glassSprite,205);
        int fx=-136+SIN_Q14[(phase+z/20)&31]*9/16384,fy=48+SIN_Q14[(phase+z/35)&31]*4/16384;
        VxpeToonMaterial3D fish;vxpe_toon3d_material_init(&fish,(z&1)?rgb565(255,205,85):rgb565(247,124,173));fish.outline_px=0;fish.fog_alpha=0;
        vxpe_toon3d_triangle(&target,&cam,{fx-9,fy,z+22},{fx+8,fy+4,z+22},{fx+7,fy-4,z+22},&fish,225,0);
        vxpe_toon3d_triangle(&target,&cam,{fx+6,fy,z+22},{fx+13,fy+5,z+22},{fx+13,fy-5,z+22},&fish,175,0);
    }
}
/* --- action2d -------------------------------------------------------------
 * A side-scrolling action frame: two scrolling tile layers, masked character
 * sprites and the per-frame physics of one controlled body plus an enemy
 * patrol pool. Measured here because a handset has to fit all of that inside a
 * 33 ms frame with no FPU, no divide instruction and no heap. */
static const int A2_W = 240, A2_H = 320;
static const int A2_TW = 16, A2_TH = 16;
static const int A2_COLS = 4, A2_ROWS = 2;    /* atlas holds 8 tile cells */
static const int A2_MAPW = 40, A2_MAPH = 25;  /* world 640x400 px */
static const int A2_SPRITES = 7, A2_BW = 12, A2_BH = 22;
/* Deliberately not tile-aligned: mid-scroll is the normal case, and both tile
 * measurements below use this same offset so their geometry is provably equal
 * and the sampler is the only variable. 16 cols x 21 rows = 336 tiles, with
 * partial tiles on the right and bottom edges. */
static const int A2_SCROLL_X = 101, A2_SCROLL_Y = 53;
static uint16_t a2AtlasPx[A2_COLS * A2_TW * A2_ROWS * A2_TH];
static uint16_t a2BackCell[A2_MAPW * A2_MAPH], a2BackFlag[A2_MAPW * A2_MAPH];
static uint16_t a2SolCell[A2_MAPW * A2_MAPH], a2SolFlag[A2_MAPW * A2_MAPH];
static uint16_t a2CharPx[2 * 16 * 24];  /* two 16x24 frames side by side */
static uint8_t a2CharMask[(2 * 16 * 24 + 7) / 8];
static uint16_t a2Fb[A2_W * A2_H];
static VxpeSprite565 a2Atlas{}, a2Char{};
static VxpeTilemap2D a2Back{}, a2Solid{}, a2BackFlat{};
static VxpeCamera2D a2Cam{};
static VxpeBodyTuning2D a2Tune{};
static VxpeBody2D a2Bodies[A2_SPRITES];
static int a2Phase = 0;

static void init_action2d() {
    static const uint8_t cell_rgb[8][3] = {
        {24, 18, 34}, {40, 30, 52}, {58, 44, 28}, {92, 72, 48},
        {120, 104, 72}, {30, 54, 40}, {150, 54, 48}, {196, 164, 96}};
    for (int cell = 0; cell < A2_COLS * A2_ROWS; ++cell) {
        const int cx = (cell % A2_COLS) * A2_TW, cy = (cell / A2_COLS) * A2_TH;
        const uint16_t base = vxpe2d_rgb565(cell_rgb[cell][0], cell_rgb[cell][1], cell_rgb[cell][2]);
        for (int y = 0; y < A2_TH; ++y) {
            for (int x = 0; x < A2_TW; ++x) {
                const bool edge = x == 0 || y == 0 || x == A2_TW - 1 || y == A2_TH - 1;
                const bool seam = x == 1 || y == 1;
                a2AtlasPx[(size_t)(cy + y) * (A2_COLS * A2_TW) + cx + x] =
                    edge ? (uint16_t)(base & 0x7BE7u) : (seam ? (uint16_t)(base | 0x0821u) : base);
            }
        }
    }
    a2Atlas.pixels = a2AtlasPx;
    a2Atlas.mask = nullptr;
    a2Atlas.width = (uint16_t)(A2_COLS * A2_TW);
    a2Atlas.height = (uint16_t)(A2_ROWS * A2_TH);
    a2Atlas.stride = (uint16_t)(A2_COLS * A2_TW);
    a2Atlas.opaque = 1;

    /* Background: a full-screen brick field. Half the tiles carry FLIP_X so the
     * layer is not one uniform cell, which is also what pushes those tiles into
     * the blitter instead of the whole-tile copy. */
    for (int y = 0; y < A2_MAPH; ++y) {
        for (int x = 0; x < A2_MAPW; ++x) {
            const size_t i = (size_t)y * A2_MAPW + (size_t)x;
            a2BackCell[i] = (uint16_t)((x * 3 + y * 5) & 7);
            a2BackFlag[i] = (uint16_t)(((x + y) & 1) ? VXPE_TF_FLIP_X : 0);
        }
    }
    a2Back.cells = a2BackCell; a2Back.flags = a2BackFlag; a2Back.atlas = &a2Atlas;
    a2Back.width = A2_MAPW; a2Back.height = A2_MAPH;
    a2Back.tile_w = A2_TW; a2Back.tile_h = A2_TH;
    a2Back.atlas_cols = A2_COLS; a2Back.oob_blocks = 1;
    /* Same cells, no flag table: the unmasked/untinted copy path. */
    a2BackFlat = a2Back;
    a2BackFlat.flags = nullptr;

    /* Solid layer: a floor band, a one-way ledge and two pillars. Blank cells
     * stay id 0 so the layer only costs the tiles a level really has. */
    for (int y = 0; y < A2_MAPH; ++y) {
        for (int x = 0; x < A2_MAPW; ++x) {
            const size_t i = (size_t)y * A2_MAPW + (size_t)x;
            uint16_t id = 0, flags = 0;
            if (y >= 22) { id = 7; flags = VXPE_TF_SOLID; }
            else if (y >= 17 && x >= 8 && x <= 22) { id = 6; flags = VXPE_TF_ONEWAY; }
            else if ((x == 30 || x == 31) && y >= 12) { id = 5; flags = VXPE_TF_SOLID; }
            if (id && ((x + y) & 1)) flags |= VXPE_TF_FLIP_X;
            a2SolCell[i] = id; a2SolFlag[i] = flags;
        }
    }
    a2Solid.cells = a2SolCell; a2Solid.flags = a2SolFlag; a2Solid.atlas = &a2Atlas;
    a2Solid.width = A2_MAPW; a2Solid.height = A2_MAPH;
    a2Solid.tile_w = A2_TW; a2Solid.tile_h = A2_TH;
    a2Solid.atlas_cols = A2_COLS; a2Solid.oob_blocks = 1;

    /* A 16x24 character in two walk frames, masked: head, cloak and legs with a
     * transparent eye socket, so the blitter cannot take the memcpy branch. */
    std::memset(a2CharMask, 0, sizeof(a2CharMask));
    for (int frame = 0; frame < 2; ++frame) {
        for (int y = 0; y < 24; ++y) {
            for (int x = 0; x < 16; ++x) {
                int visible;
                uint16_t color;
                if (y < 7) { visible = (x >= 5 && x <= 10); color = vxpe2d_rgb565(224, 202, 176); }
                else if (y < 17) { visible = (x >= 3 && x <= 12); color = vxpe2d_rgb565(122, 34, 46); }
                else {
                    const int lead = frame ? (x > 7 ? 1 : 0) : (x < 8 ? 1 : 0);
                    visible = (x >= 4 + lead && x <= 11 - lead);
                    color = vxpe2d_rgb565(48, 44, 66);
                }
                if (visible && y == 2 && x == 6) visible = 0;
                const size_t p = (size_t)y * 32 + (size_t)frame * 16 + (size_t)x;
                a2CharPx[p] = color;
                if (visible) a2CharMask[p >> 3] |= (uint8_t)(0x80u >> (p & 7u));
            }
        }
    }
    a2Char.pixels = a2CharPx; a2Char.mask = a2CharMask;
    a2Char.width = 32; a2Char.height = 24; a2Char.stride = 32; a2Char.opaque = 0;

    vxpe_cam_init(&a2Cam, A2_W, A2_H, A2_MAPW * A2_TW, A2_MAPH * A2_TH);
    vxpe_cam_set_follow_ms(&a2Cam, 90);
    vxpe_cam_set_lookahead(&a2Cam, 24);
    vxpe_body_tuning_default(&a2Tune);
    for (int i = 0; i < A2_SPRITES; ++i) {
        vxpe_body_init(&a2Bodies[i], 40 + i * 28, 22 * A2_TH - A2_BH, A2_BW, A2_BH);
        vxpe_body_settle(&a2Bodies[i], &a2Solid);
    }
}

/* One simulation frame, shared by the full renderer and the physics-only
 * benchmark so both measure the identical amount of work. */
static void step_action2d(uint16_t dt_ms) {
    VxpeBodyIntent2D intent{};
    intent.x = (int8_t)(((a2Phase >> 5) & 1) ? 1 : -1);
    intent.jump = (uint8_t)((a2Phase & 31) == 0 ? 1 : 0);
    intent.jump_held = intent.jump;
    vxpe_body_control(&a2Bodies[0], &a2Solid, &a2Tune, &intent, dt_ms);
    for (int i = 1; i < A2_SPRITES; ++i) {
        a2Bodies[i].vx_q8 = ((i & 1) ? 1 : -1) * (30 + i * 6) * 256;
        vxpe_body_step(&a2Bodies[i], &a2Solid, &a2Tune, dt_ms);
    }
    vxpe_cam_follow(&a2Cam, (int)(a2Bodies[0].x_q8 >> 8), (int)(a2Bodies[0].y_q8 >> 8), dt_ms);
    if ((a2Phase & 15) == 0) vxpe_cam_shake(&a2Cam, 3, 140);
    vxpe_cam_update(&a2Cam, dt_ms);
}

static void render_action2d() {
    std::memset(a2Fb, 0, sizeof(a2Fb));
    const int cx = vxpe_cam_x(&a2Cam), cy = vxpe_cam_y(&a2Cam);
    VxpeTileDraw2D view{};
    vxpe_tile_view(&view, -cx, -cy);
    view.skip_blank = 0;  /* decor covers the whole viewport */
    vxpe_tilemap_draw(a2Fb, A2_W, A2_H, &a2Back, &view);
    vxpe_tile_view(&view, -cx, -cy);  /* solids only, blank cells skipped */
    vxpe_tilemap_draw(a2Fb, A2_W, A2_H, &a2Solid, &view);
    for (int i = 0; i < A2_SPRITES; ++i) {
        const VxpeBody2D* b = &a2Bodies[i];
        const int wx = (int)(b->x_q8 >> 8), wy = (int)(b->y_q8 >> 8);
        if (!vxpe_cam_visible(&a2Cam, wx, wy, A2_BW, A2_BH)) continue;
        VxpeBlit565 op{};
        op.src.x = (int16_t)(((a2Phase >> 4) & 1) * 16);
        op.src.w = 16; op.src.h = 24;
        op.dst_x = (int16_t)(vxpe_cam_to_screen_x(&a2Cam, wx) - 2);
        op.dst_y = (int16_t)(vxpe_cam_to_screen_y(&a2Cam, wy) - 2);
        op.dst_w = 16; op.dst_h = 24;
        op.tint565 = 0xFFFFu; op.alpha = 255u; op.blend = VXPE_BLEND_COPY;
        op.flip_x = (uint8_t)(b->facing ? 0 : 1);
        vxpe2d_blit(a2Fb, A2_W, A2_H, &a2Char, &op);
    }
    step_action2d(33);
    ++a2Phase;
}

/* The three ways to put the same 336 tiles on screen, at one fixed scroll. */
static void render_a2_tiles_copy() {
    std::memset(a2Fb, 0, sizeof(a2Fb));
    VxpeTileDraw2D view{};
    vxpe_tile_view(&view, -A2_SCROLL_X, -A2_SCROLL_Y);
    view.skip_blank = 0;
    vxpe_tilemap_draw(a2Fb, A2_W, A2_H, &a2BackFlat, &view);
}

/* Half the tiles carry FLIP_X, so those go through the general blitter instead
 * of the whole-tile copy - but still 1:1, so the identity branch applies. */
static void render_a2_tiles_flip() {
    std::memset(a2Fb, 0, sizeof(a2Fb));
    VxpeTileDraw2D view{};
    vxpe_tile_view(&view, -A2_SCROLL_X, -A2_SCROLL_Y);
    view.skip_blank = 0;
    vxpe_tilemap_draw(a2Fb, A2_W, A2_H, &a2Back, &view);
}

/* The same visible window forced through the generic sampler: flip_d keeps a
 * 1:1 blit out of the identity branch, so the only difference is the two
 * integer divides per pixel that ARMv5TE has to call __aeabi_uidivmod for.
 * The texels land in swapped axes, which is irrelevant here - the per-pixel
 * work, and only that, is what this number is for. */
static void render_a2_tiles_generic() {
    std::memset(a2Fb, 0, sizeof(a2Fb));
    const int tx0 = A2_SCROLL_X / A2_TW, tx1 = (A2_SCROLL_X + A2_W - 1) / A2_TW;
    const int ty0 = A2_SCROLL_Y / A2_TH, ty1 = (A2_SCROLL_Y + A2_H - 1) / A2_TH;
    for (int ty = ty0; ty <= ty1; ++ty) {
        for (int tx = tx0; tx <= tx1; ++tx) {
            const size_t i = (size_t)ty * A2_MAPW + (size_t)tx;
            const int id = a2BackCell[i], flags = a2BackFlag[i];
            VxpeBlit565 op{};
            op.src.x = (int16_t)((id % A2_COLS) * A2_TW);
            op.src.y = (int16_t)((id / A2_COLS) * A2_TH);
            op.src.w = (int16_t)A2_TW; op.src.h = (int16_t)A2_TH;
            op.dst_x = (int16_t)(tx * A2_TW - A2_SCROLL_X);
            op.dst_y = (int16_t)(ty * A2_TH - A2_SCROLL_Y);
            op.dst_w = (uint16_t)A2_TW; op.dst_h = (uint16_t)A2_TH;
            op.tint565 = 0xFFFFu; op.alpha = 255u; op.blend = VXPE_BLEND_COPY;
            op.flip_x = (uint8_t)((flags & VXPE_TF_FLIP_X) ? 1 : 0);
            op.flip_d = 1;
            vxpe2d_blit(a2Fb, A2_W, A2_H, &a2Atlas, &op);
        }
    }
}

static void simulate_action2d() {
    step_action2d(33);
    ++a2Phase;
}
static double median_ms(void(*render)(),int frames){
    for(int i=0;i<3;++i)render();double samples[9];
    for(int s=0;s<9;++s){auto start=Clock::now();for(int f=0;f<frames;++f)render();auto end=Clock::now();samples[s]=std::chrono::duration<double,std::milli>(end-start).count()/frames;}
    std::sort(samples,samples+9);return samples[4];
}
static bool useAffine;
static void render3d_dispatch(){render3d(width,height,useAffine);}
static void render25d_dispatch(){render25d();animationPhase=(animationPhase+1)&63;}
static void render_retro_dispatch(){draw_retro_mall(width,height,animationPhase++&63);}
static int differing_pixels(const uint16_t* a,const uint16_t* b,int n){int count=0;for(int i=0;i<n;++i)count+=a[i]!=b[i];return count;}
}

int main(int argc,char** argv){
    std::filesystem::create_directories("reports/graphics-benchmark");
    init_sprite();init_textures();int frames=argc>1?std::max(2,std::atoi(argv[1])):8;
    std::puts("VXPE GRAPHICS BENCHMARK (median per frame; host clock, not device FPS)");
    for(int scale=0;scale<2;++scale){width=scale?240:120;height=scale?320:160;
        animationPhase=0;double p25=median_ms(render25d_dispatch,frames);animationPhase=20;render25d();uint64_t sum25=checksum(pixels25,width*height);
        if(scale==1)write_ppm("reports/graphics-benchmark/2.5d_240x320.ppm",pixels25,width,height);
        else write_ppm("reports/graphics-benchmark/2.5d_120x160.ppm",pixels25,width,height);
        std::printf("2.5D billboards %dx%d: %.3f ms/frame; color buffer %d B; checksum %016llX\n",width,height,p25,width*height*2,(unsigned long long)sum25);
    }
    for(int scale=0;scale<2;++scale){width=scale?240:120;height=scale?320:160;animationPhase=0;
        double game=median_ms(render25d_game_dispatch,frames);animationPhase=20;render25d_game();
        if(scale==1)write_ppm("reports/graphics-benchmark/2.5d_ground_batch_240x320.ppm",pixels25,width,height);
        else write_ppm("reports/graphics-benchmark/2.5d_ground_batch_120x160.ppm",pixels25,width,height);
        std::printf("2.5D ground+batch %dx%d: %.3f ms/frame; color buffer %d B; checksum %016llX\n",width,height,game,width*height*2,(unsigned long long)checksum(pixels25,width*height));
    }
    for(int scale=0;scale<2;++scale){width=scale?240:120;height=scale?320:160;animationPhase=0;
        double mall=median_ms(render_retro_dispatch,frames);animationPhase=20;draw_retro_mall(width,height,animationPhase);
        if(scale==1)write_ppm("reports/graphics-benchmark/retro_mall_3d_240x320.ppm",pixels3d,width,height);
        else write_ppm("reports/graphics-benchmark/retro_mall_3d_120x160.ppm",pixels3d,width,height);
        std::printf("3D textured mall %dx%d: %.3f ms/frame; color+depth %d B; checksum %016llX\n",width,height,mall,width*height*4,(unsigned long long)checksum(pixels3d,width*height));
    }
    for(int scale=0;scale<2;++scale){width=scale?240:120;height=scale?320:160;useAffine=false;
        double exact=median_ms(render3d_dispatch,frames);int n=width*height;std::memcpy(exactImage,pixels3d,(size_t)n*sizeof(uint16_t));
        if(scale==1)write_ppm("reports/graphics-benchmark/3d_exact_240x320.ppm",pixels3d,width,height);
        std::printf("3D exact %dx%d: %.3f ms/frame; color+depth %d B; checksum %016llX\n",width,height,exact,n*4,(unsigned long long)checksum(pixels3d,n));
        useAffine=true;double fast=median_ms(render3d_dispatch,frames);int diff=differing_pixels(exactImage,pixels3d,n);
        if(scale==1)write_ppm("reports/graphics-benchmark/3d_affine_240x320.ppm",pixels3d,width,height);
        std::printf("3D affine %dx%d: %.3f ms/frame; speedup %.2fx; changed pixels %d/%d; checksum %016llX\n",width,height,fast,fast>0?exact/fast:0.0,diff,n,(unsigned long long)checksum(pixels3d,n));
    }
    init_action2d();
    {
        const double copy = median_ms(render_a2_tiles_copy, frames);
        const double flip = median_ms(render_a2_tiles_flip, frames);
        const double generic = median_ms(render_a2_tiles_generic, frames);
        a2Phase = 0;
        const double game = median_ms(render_action2d, frames);
        const double phys = median_ms(simulate_action2d, frames);
        a2Phase = 40; render_action2d();
        const int cols = (A2_SCROLL_X + A2_W - 1) / A2_TW - A2_SCROLL_X / A2_TW + 1;
        const int rows = (A2_SCROLL_Y + A2_H - 1) / A2_TH - A2_SCROLL_Y / A2_TH + 1;
        write_ppm("reports/graphics-benchmark/action2d_240x320.ppm", a2Fb, A2_W, A2_H);
        std::printf("action2d %dx%d-tile layer (%d px): whole-tile copy %.3f ms | 1:1 blit with flips %.3f ms | generic resample %.3f ms (copy %.2fx, 1:1 blit %.2fx)\n",
            cols, rows, cols * A2_TW * rows * A2_TH, copy, flip, generic,
            copy > 0 ? generic / copy : 0.0, flip > 0 ? generic / flip : 0.0);
        std::printf("action2d game frame 240x320 (2 tile layers + 7 masked sprites + 7 bodies + camera): %.3f ms/frame; color buffer %d B; checksum %016llX\n",
            game, A2_W * A2_H * 2, (unsigned long long)checksum(a2Fb, A2_W * A2_H));
        std::printf("action2d simulation only (1 controller + 6 steppers + camera follow/shake): %.3f ms\n", phys);
    }
    width=240;height=320;uint64_t firstFrame=0,lastFrame=0;
    for(int frame=0;frame<8;++frame){int phase=frame*8;draw_retro_mall(width,height,phase);uint64_t hash=checksum(pixels3d,width*height);
        if(frame==0)firstFrame=hash;if(frame==7)lastFrame=hash;
        char path[96];std::snprintf(path,sizeof(path),"reports/graphics-benchmark/retro_mall_motion_%02d.ppm",frame);
        write_ppm(path,pixels3d,width,height);
    }
    if(firstFrame==lastFrame){std::fputs("camera/water/fish frame sequence did not animate\n",stderr);return 2;}
    return 0;
}
