/* RetroBeachFighterDemo - VxpStage2D 240x320 sample. */
#include "vmsys.h"
#include "vmio.h"
#include "vmgraph.h"
#include "vmtimer.h"
#include "graphics/VxpRender2D.h"
#include "graphics/VxpSpriteFx.h"
#include "graphics/VxpStage2D.h"
#include "graphics/particles/VxpParticlePool.h"
#include <stdint.h>
#include <string.h>

#define SW 240
#define SH 320
#define WORLD_W 480
#define WATER_Y 92
#define GROUND_Y 232

static VMINT g_layer=-1;
static VMINT g_timer=-1;
static uint32_t g_tick=0;
static uint32_t g_rng=0xB34C2026u;
static int g_player_x=108;
static int g_enemy_x=198;
static int g_jump_tick=0;
static int g_attack_tick=0;
static uint8_t g_started=0;

static uint16_t g_cliff_px[96*40];
static uint16_t g_water_px[64*12];
static uint16_t g_ground_px[64*24];
static uint16_t g_fighter_a_px[22*52];
static uint16_t g_fighter_b_px[22*52];
static uint8_t g_fighter_a8[22*52];

static VxpeSprite565 g_cliff;
static VxpeSprite565 g_water;
static VxpeSprite565 g_ground;
static VxpeSpriteA8 g_fighter_a;
static VxpeSpriteA8 g_fighter_b;
static VxpeStageCamera2D g_camera;
static VxpeParticlePool g_particles;

static uint32_t rnd32(void){
    g_rng=g_rng*1664525u+1013904223u;
    return g_rng;
}
static int rnd_range(int lo,int hi){
    if(hi<=lo)return lo;
    return lo+(int)(rnd32()%(uint32_t)(hi-lo+1));
}
static int clampi(int v,int lo,int hi){return v<lo?lo:(v>hi?hi:v);}

static VMUINT16* framebuffer(void){
    return (VMUINT16*)vm_graphic_get_layer_buffer(g_layer);
}

static void put_fighter_pixel(uint16_t* px,uint8_t* a,int x,int y,uint16_t c,uint8_t alpha){
    if(x<0||y<0||x>=22||y>=52)return;
    px[y*22+x]=c;
    a[y*22+x]=alpha;
}

static void build_fighter(uint16_t* px,uint8_t* a,uint16_t hair,uint16_t cloth,uint16_t accent){
    int x,y;
    uint16_t skin=vxpe2d_rgb565(246,194,162);
    memset(px,0,22*52*2);
    memset(a,0,22*52);
    for(y=2;y<14;++y){
        for(x=4;x<18;++x){
            int dx=x-11,dy=y-8;
            if(dx*dx+dy*dy<=36) put_fighter_pixel(px,a,x,y,skin,255);
        }
    }
    for(y=1;y<9;++y)for(x=4;x<18;++x){
        int dx=x-11,dy=y-7;
        if(dx*dx+dy*dy<=42 && (y<5 || x<7 || x>15))
            put_fighter_pixel(px,a,x,y,hair,255);
    }
    for(y=13;y<28;++y)for(x=7;x<15;++x)
        put_fighter_pixel(px,a,x,y,cloth,255);
    for(y=24;y<32;++y)for(x=5;x<17;++x)
        put_fighter_pixel(px,a,x,y,accent,255);
    for(y=16;y<27;++y){
        put_fighter_pixel(px,a,5,y,skin,245);
        put_fighter_pixel(px,a,16,y,skin,245);
    }
    for(y=31;y<49;++y){
        for(x=6;x<10;++x) put_fighter_pixel(px,a,x,y,skin,255);
        for(x=12;x<16;++x) put_fighter_pixel(px,a,x,y,skin,255);
    }
    for(x=4;x<10;++x)for(y=47;y<51;++y)put_fighter_pixel(px,a,x,y,vxpe2d_rgb565(244,244,240),255);
    for(x=12;x<19;++x)for(y=47;y<51;++y)put_fighter_pixel(px,a,x,y,vxpe2d_rgb565(244,244,240),255);
}

static void build_assets(void){
    int x,y;
    for(y=0;y<40;++y){
        for(x=0;x<96;++x){
            uint16_t c;
            if(x<50-(y/3)){
                int n=((x*13+y*7)&15);
                c=vxpe2d_rgb565((uint8_t)(88+n*3),(uint8_t)(55+n*2),(uint8_t)(54+n));
                if(((x+y*3)&11)==0)c=vxpe2d_rgb565(145,96,75);
            }else{
                int n=((x+y)&7);
                c=vxpe2d_rgb565((uint8_t)(88+n*2),(uint8_t)(119+n*3),(uint8_t)(162+n*4));
            }
            g_cliff_px[y*96+x]=c;
        }
    }
    for(y=0;y<12;++y){
        for(x=0;x<64;++x){
            int stripe=((x+(y*3))&15);
            int bright=(stripe<4)||(((x*5+y*7)&31)<3);
            int r=58+y*2+(bright?35:0);
            int g=76+y*3+(bright?45:0);
            int b=132+y*5+(bright?55:0);
            if(r>255)r=255;if(g>255)g=255;if(b>255)b=255;
            g_water_px[y*64+x]=vxpe2d_rgb565((uint8_t)r,(uint8_t)g,(uint8_t)b);
        }
    }
    for(y=0;y<24;++y){
        for(x=0;x<64;++x){
            int n=(x*17+y*11+(x*y))&31;
            int r=78+n*2, g=47+n, b=49+n/2;
            if(((x+y*2)&13)==0){r+=45;g+=24;b+=14;}
            if(r>180)r=180;
            g_ground_px[y*64+x]=vxpe2d_rgb565((uint8_t)r,(uint8_t)g,(uint8_t)b);
        }
    }

    g_cliff.pixels=g_cliff_px;g_cliff.mask=0;g_cliff.width=96;g_cliff.height=40;g_cliff.stride=96;g_cliff.opaque=1;
    g_water.pixels=g_water_px;g_water.mask=0;g_water.width=64;g_water.height=12;g_water.stride=64;g_water.opaque=1;
    g_ground.pixels=g_ground_px;g_ground.mask=0;g_ground.width=64;g_ground.height=24;g_ground.stride=64;g_ground.opaque=1;

    build_fighter(g_fighter_a_px,g_fighter_a8,vxpe2d_rgb565(126,58,91),vxpe2d_rgb565(242,241,232),vxpe2d_rgb565(215,77,125));
    build_fighter(g_fighter_b_px,g_fighter_a8,vxpe2d_rgb565(103,45,35),vxpe2d_rgb565(238,235,225),vxpe2d_rgb565(33,53,89));
    g_fighter_a.pixels=g_fighter_a_px;g_fighter_a.alpha=g_fighter_a8;g_fighter_a.width=22;g_fighter_a.height=52;g_fighter_a.stride=22;g_fighter_a.alpha_stride=22;g_fighter_a.opaque=0;
    g_fighter_b.pixels=g_fighter_b_px;g_fighter_b.alpha=g_fighter_a8;g_fighter_b.width=22;g_fighter_b.height=52;g_fighter_b.stride=22;g_fighter_b.alpha_stride=22;g_fighter_b.opaque=0;
}

static void spawn_splash(int screen_x,int y){
    int i;
    for(i=0;i<14;++i){
        VxpeParticleSpawn p;
        memset(&p,0,sizeof(p));
        p.x=(int16_t)(screen_x+rnd_range(-5,5));
        p.y=(int16_t)(y+rnd_range(-2,2));
        p.vx_q8=rnd_range(-45,45)*256;
        p.vy_q8=-rnd_range(30,90)*256;
        p.ay_q8=rnd_range(110,170)*256;
        p.lifetime_ms=(uint16_t)rnd_range(240,520);
        p.color565=0xFFFF;
        p.tint565=(rnd32()&1u)?vxpe2d_rgb565(220,235,255):vxpe2d_rgb565(171,205,244);
        p.alpha_start=(uint8_t)rnd_range(170,245);
        p.alpha_end=0;
        p.size_start=(uint8_t)rnd_range(2,4);
        p.size_end=1;
        p.blend=VXPE_BLEND_ALPHA;
        vxpe_particles_spawn(&g_particles,&p);
    }
}

static void setup(void){
    vxpe_stage_camera_init(&g_camera,SW,WORLD_W);
    g_camera.deadzone_left=78;
    g_camera.deadzone_right=162;
    vxpe_particles_init(&g_particles,VXPE_PARTICLE_POOL_MAX);
}

static void draw_hud(uint16_t* fb){
    vxpe2d_fill_rect(fb,SW,SH,0,0,SW,42,vxpe2d_rgb565(20,18,27));
    vxpe2d_fill_rect(fb,SW,SH,7,7,26,26,vxpe2d_rgb565(67,39,66));
    vxpe2d_fill_rect(fb,SW,SH,207,7,26,26,vxpe2d_rgb565(68,42,34));
    vxpe2d_fill_rect(fb,SW,SH,38,8,66,7,vxpe2d_rgb565(48,31,43));
    vxpe2d_fill_rect(fb,SW,SH,38,9,60,5,vxpe2d_rgb565(235,185,51));
    vxpe2d_fill_rect(fb,SW,SH,136,8,66,7,vxpe2d_rgb565(48,31,43));
    vxpe2d_fill_rect(fb,SW,SH,142,9,60,5,vxpe2d_rgb565(235,185,51));
    vxpe2d_fill_rect(fb,SW,SH,108,7,24,26,vxpe2d_rgb565(43,52,70));
    {
        int t=99-(int)((g_tick/30)%100);
        int bars=clampi(t/10,0,9);
        int i;
        for(i=0;i<bars;++i)vxpe2d_fill_rect(fb,SW,SH,111+i*2,15,1,10,vxpe2d_rgb565(185,218,147));
    }
}

static void draw_stage(uint16_t* fb){
    VxpeStageBand2D cliff;
    VxpeStageBand2D water;
    VxpeStageBand2D ground;
    uint16_t sky_top=vxpe_stage_cycle565(vxpe2d_rgb565(184,218,171),vxpe2d_rgb565(215,228,163),(uint8_t)(g_tick>>2));
    uint16_t sky_bottom=vxpe2d_rgb565(137,187,170);

    vxpe2d_gradient_vertical(fb,SW,SH,0,42,SW,72,sky_top,sky_bottom);

    memset(&cliff,0,sizeof(cliff));
    cliff.src.x=0;cliff.src.y=0;cliff.src.w=96;cliff.src.h=40;
    cliff.dst_y=72;cliff.dst_h=62;cliff.parallax_q8=64;
    cliff.tint565=0xFFFF;cliff.alpha=255;cliff.blend=VXPE_BLEND_COPY;cliff.repeat_x=1;
    vxpe_stage_draw_band565(fb,SW,SH,&g_cliff,&g_camera,&cliff);

    memset(&water,0,sizeof(water));
    water.src.x=0;water.src.y=0;water.src.w=64;water.src.h=12;
    water.dst_y=WATER_Y;water.dst_h=GROUND_Y-WATER_Y;
    water.parallax_q8=90;water.scroll_x=(int16_t)(g_tick/2);water.scroll_y=(int16_t)(g_tick/12);
    water.tint565=vxpe_stage_cycle565(vxpe2d_rgb565(198,203,255),vxpe2d_rgb565(165,193,233),(uint8_t)(g_tick>>1));
    water.alpha=255;water.blend=VXPE_BLEND_COPY;water.repeat_x=1;
    water.raster_wave=1;water.wave_amplitude=3;water.wave_phase=(uint8_t)(g_tick&15);water.wave_shift=2;
    vxpe_stage_draw_band565(fb,SW,SH,&g_water,&g_camera,&water);

    vxpe2d_fill_rect(fb,SW,SH,0,GROUND_Y-3,SW,3,vxpe2d_rgb565(195,184,166));

    memset(&ground,0,sizeof(ground));
    ground.src.x=0;ground.src.y=0;ground.src.w=64;ground.src.h=24;
    ground.dst_y=GROUND_Y;ground.dst_h=SH-GROUND_Y;
    ground.parallax_q8=256;ground.tint565=0xFFFF;ground.alpha=255;ground.blend=VXPE_BLEND_COPY;ground.repeat_x=1;
    vxpe_stage_draw_band565(fb,SW,SH,&g_ground,&g_camera,&ground);
}

static int jump_offset(void){
    if(g_jump_tick<=0)return 0;
    {
        int p=18-g_jump_tick;
        int rise=p<=9?p:(18-p);
        return -(rise*5);
    }
}

static void draw_fighter(uint16_t* fb,const VxpeSpriteA8* spr,int world_x,int base_y,uint8_t flip){
    VxpeBlit565 op;
    int sx=vxpe_stage_world_to_screen_x(&g_camera,world_x);
    memset(&op,0,sizeof(op));
    op.src.x=0;op.src.y=0;op.src.w=22;op.src.h=52;
    op.dst_x=(int16_t)(sx-11);op.dst_y=(int16_t)(base_y-52);
    op.dst_w=22;op.dst_h=52;op.tint565=0xFFFF;op.alpha=255;op.blend=VXPE_BLEND_ALPHA;op.flip_x=flip;
    vxpe2d_overlay_rect(fb,SW,SH,sx-9,base_y-3,18,3,vxpe2d_rgb565(35,24,28),110,VXPE_BLEND_ALPHA);
    vxpe2d_blit_a8(fb,SW,SH,spr,&op);
}

static void draw(void){
    uint16_t* fb=(uint16_t*)framebuffer();
    int player_sx;
    if(!fb||g_layer<0)return;

    draw_stage(fb);
    draw_fighter(fb,&g_fighter_b,g_enemy_x,GROUND_Y+52,1);
    draw_fighter(fb,&g_fighter_a,g_player_x,GROUND_Y+52+jump_offset(),0);

    player_sx=vxpe_stage_world_to_screen_x(&g_camera,g_player_x);
    if(g_attack_tick>0){
        int reach=14+(8-g_attack_tick)*2;
        vxpe2d_fill_rect(fb,SW,SH,player_sx+8,GROUND_Y+15,reach,3,vxpe2d_rgb565(245,238,220));
    }

    vxpe_particles_draw(&g_particles,fb,SW,SH);
    draw_hud(fb);
    vm_graphic_flush_layer(&g_layer,1);
}

static void tick(VMINT tid){
    (void)tid;
    ++g_tick;
    if(g_jump_tick>0){
        --g_jump_tick;
        if(g_jump_tick==1)spawn_splash(vxpe_stage_world_to_screen_x(&g_camera,g_player_x),GROUND_Y+48);
    }
    if(g_attack_tick>0)--g_attack_tick;

    g_enemy_x=190+(int)((g_tick/8)%20);
    vxpe_stage_camera_follow(&g_camera,g_player_x,64);
    vxpe_particles_update(&g_particles,33);
    draw();
}

void handle_keyevt(VMINT event,VMINT keycode){
    if(event!=VM_KEY_EVENT_DOWN&&event!=VM_KEY_EVENT_REPEAT)return;
    if(keycode==VM_KEY_LEFT||keycode==VM_KEY_NUM4){
        g_player_x=clampi(g_player_x-8,20,WORLD_W-20);
    }else if(keycode==VM_KEY_RIGHT||keycode==VM_KEY_NUM6){
        g_player_x=clampi(g_player_x+8,20,WORLD_W-20);
    }else if(keycode==VM_KEY_UP||keycode==VM_KEY_NUM2){
        if(g_jump_tick==0){g_jump_tick=18;spawn_splash(vxpe_stage_world_to_screen_x(&g_camera,g_player_x),GROUND_Y+48);}
    }else if(keycode==VM_KEY_OK||keycode==VM_KEY_NUM5){
        g_attack_tick=8;
        spawn_splash(vxpe_stage_world_to_screen_x(&g_camera,g_player_x)+18,GROUND_Y+42);
    }else if(keycode==VM_KEY_RIGHT_SOFTKEY||keycode==VM_KEY_CLEAR||keycode==VM_KEY_BACK){
        vm_exit_app();return;
    }
    vxpe_stage_camera_follow(&g_camera,g_player_x,128);
    draw();
}

void handle_penevt(VMINT event,VMINT x,VMINT y){
    if(event==VM_PEN_EVENT_TAP||event==VM_PEN_EVENT_MOVE){
        int world=(int)(g_camera.x_q8>>8)+x;
        g_player_x=clampi(world,20,WORLD_W-20);
        if(event==VM_PEN_EVENT_TAP&&y<GROUND_Y)g_jump_tick=18;
        vxpe_stage_camera_follow(&g_camera,g_player_x,128);
        draw();
    }
}

static void start(void){
    if(g_layer<0)g_layer=vm_graphic_create_layer(0,0,SW,SH,-1);
    if(!g_started){build_assets();setup();g_started=1;}
    if(g_timer<0)g_timer=vm_create_timer(33,tick);
    draw();
}

static void stop(void){
    if(g_timer>=0){vm_delete_timer(g_timer);g_timer=-1;}
    if(g_layer>=0){vm_graphic_delete_layer(g_layer);g_layer=-1;}
}

void handle_sysevt(VMINT message,VMINT param){
    (void)param;
    if(message==VM_MSG_CREATE||message==VM_MSG_ACTIVE)start();
    else if(message==VM_MSG_PAINT)draw();
    else if(message==VM_MSG_INACTIVE||message==VM_MSG_QUIT){stop();if(message==VM_MSG_QUIT)vm_exit_app();}
}

void vm_main(void){
    vm_reg_sysevt_callback(handle_sysevt);
    vm_reg_keyboard_callback(handle_keyevt);
    vm_reg_pen_callback(handle_penevt);
}
