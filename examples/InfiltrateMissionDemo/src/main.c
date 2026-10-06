/* InfiltrateMissionDemo - 240x320 multi-scene stealth mission. */
#include "vmsys.h"
#include "vmio.h"
#include "vmgraph.h"
#include "vmtimer.h"
#include "graphics/VxpRender2D.h"
#include "graphics/VxpSpriteFx.h"
#include "graphics/VxpScene25D.h"
#include "graphics/VxpLight2D.h"
#include "graphics/VxpVfx2D.h"
#include <stdint.h>
#include <string.h>

#define SW 240
#define SH 320
#define GAME_TOP 16
#define GAME_BOTTOM 238
#define HUD_TOP 240

typedef enum MissionPhase {
    PHASE_DEPLOYMENT=0,
    PHASE_PARK,
    PHASE_ENTRY,
    PHASE_SNEAK,
    PHASE_PISTOL,
    PHASE_EXIT
} MissionPhase;

typedef enum GuardState {
    GUARD_PATROL=0,
    GUARD_WATCH,
    GUARD_ALERT
} GuardState;

static VMINT g_layer=-1;
static VMINT g_timer=-1;
static uint32_t g_tick=0;
static uint8_t g_started=0;
static MissionPhase g_phase=PHASE_DEPLOYMENT;
static uint8_t g_phase_flash=0;
static uint8_t g_alert=0;
static uint8_t g_done=0;

static int32_t g_player_x=0;
static int32_t g_player_z=110;
static int32_t g_guard_x=22;
static int32_t g_guard_z=220;
static int g_targets=0;
static int g_guard_alive=0;
static int g_car_x=112;
static int g_drive_progress=0;
static int g_entry_x=120;
static int g_entry_action_tick=0;
static int g_door_open=0;
static int g_exit_progress=0;
static int g_shot_flash=0;

static GuardState g_guard_state=GUARD_PATROL;
static int g_guard_patrol_dir=1;
static int g_guard_detection=0;
static int g_guard_patrol_left=-34;
static int g_guard_patrol_right=38;

static uint16_t g_player_px[24*48];
static uint8_t g_player_a[24*48];
static uint16_t g_guard_px[24*48];
static uint8_t g_guard_a[24*48];
static VxpeSpriteA8 g_player_sprite;
static VxpeSpriteA8 g_guard_sprite;
static VxpeCamera25D g_camera;
static VxpeLightmap2D g_lightmap;

static const uint8_t FONT5X7[36][7]={
 {14,17,17,31,17,17,17},{30,17,17,30,17,17,30},{14,17,16,16,16,17,14},
 {30,17,17,17,17,17,30},{31,16,16,30,16,16,31},{31,16,16,30,16,16,16},
 {14,17,16,23,17,17,15},{17,17,17,31,17,17,17},{31,4,4,4,4,4,31},
 {7,2,2,2,18,18,12},{17,18,20,24,20,18,17},{16,16,16,16,16,16,31},
 {17,27,21,21,17,17,17},{17,25,21,19,17,17,17},{14,17,17,17,17,17,14},
 {30,17,17,30,16,16,16},{14,17,17,17,21,18,13},{30,17,17,30,20,18,17},
 {15,16,16,14,1,1,30},{31,4,4,4,4,4,4},{17,17,17,17,17,17,14},
 {17,17,17,17,17,10,4},{17,17,17,21,21,21,10},{17,17,10,4,10,17,17},
 {17,17,10,4,4,4,4},{31,1,2,4,8,16,31},
 {14,17,19,21,25,17,14},{4,12,4,4,4,4,14},{14,17,1,2,4,8,31},
 {30,1,1,14,1,1,30},{2,6,10,18,31,2,2},{31,16,16,30,1,1,30},
 {14,16,16,30,17,17,14},{31,1,2,4,8,8,8},{14,17,17,14,17,17,14},
 {14,17,17,15,1,1,14}
};

static VMUINT16* framebuffer(void){return (VMUINT16*)vm_graphic_get_layer_buffer(g_layer);}
static int clampi(int v,int lo,int hi){return v<lo?lo:(v>hi?hi:v);}

static void pixel(uint16_t* fb,int x,int y,uint16_t c){
    if(x>=0&&y>=0&&x<SW&&y<SH)fb[y*SW+x]=c;
}

static void line(uint16_t* fb,int x0,int y0,int x1,int y1,uint16_t c){
    int dx=x1>x0?x1-x0:x0-x1,sx=x0<x1?1:-1;
    int dy=y1>y0?y0-y1:y1-y0,sy=y0<y1?1:-1;
    int err=dx+dy;
    for(;;){
        pixel(fb,x0,y0,c);
        if(x0==x1&&y0==y1)break;
        {int e2=err<<1;if(e2>=dy){err+=dy;x0+=sx;}if(e2<=dx){err+=dx;y0+=sy;}}
    }
}

static void fill_scan_quad(uint16_t* fb,int x0a,int x0b,int y0,int x1a,int x1b,int y1,uint16_t c){
    int y,span=y1-y0;if(span<=0)return;
    for(y=y0;y<=y1;++y){
        int t=(y-y0)*256/span;
        int xa=x0a+((x1a-x0a)*t>>8),xb=x0b+((x1b-x0b)*t>>8);
        if(xa>xb){int tmp=xa;xa=xb;xb=tmp;}
        vxpe2d_fill_rect(fb,SW,SH,xa,y,xb-xa+1,1,c);
    }
}

static void fill_scan_quad_alpha(
    uint16_t* fb,
    int x0a,int x0b,int y0,
    int x1a,int x1b,int y1,
    uint16_t c,uint8_t alpha)
{
    int y,span=y1-y0;
    if(span==0)return;
    if(span<0){
        int ty=y0;y0=y1;y1=ty;span=-span;
        ty=x0a;x0a=x1a;x1a=ty;
        ty=x0b;x0b=x1b;x1b=ty;
    }
    for(y=y0;y<=y1;++y){
        int t=(y-y0)*256/span;
        int xa=x0a+((x1a-x0a)*t>>8),xb=x0b+((x1b-x0b)*t>>8);
        if(xa>xb){int tmp=xa;xa=xb;xb=tmp;}
        vxpe2d_overlay_rect(fb,SW,SH,xa,y,xb-xa+1,1,c,alpha,VXPE_BLEND_ALPHA);
    }
}

static const uint8_t* glyph(char c){
    if(c>='A'&&c<='Z')return FONT5X7[c-'A'];
    if(c>='0'&&c<='9')return FONT5X7[26+c-'0'];
    return 0;
}

static void text5(uint16_t* fb,int x,int y,const char* s,uint16_t color,int scale){
    while(*s){
        char c=*s++;
        const uint8_t* g=glyph(c);
        if(c==':'){
            vxpe2d_fill_rect(fb,SW,SH,x+2*scale,y+2*scale,scale,scale,color);
            vxpe2d_fill_rect(fb,SW,SH,x+2*scale,y+5*scale,scale,scale,color);
        }else if(g){
            int yy,xx;
            for(yy=0;yy<7;++yy)for(xx=0;xx<5;++xx)
                if(g[yy]&(1<<(4-xx)))
                    vxpe2d_fill_rect(fb,SW,SH,x+xx*scale,y+yy*scale,scale,scale,color);
        }
        x+=6*scale;
    }
}

static void actor_px(uint16_t* p,uint8_t* a,int x,int y,uint16_t c,uint8_t alpha){
    if(x<0||y<0||x>=24||y>=48)return;
    p[y*24+x]=c;a[y*24+x]=alpha;
}

static void build_actor(uint16_t* p,uint8_t* a,uint16_t shirt,uint16_t pants,uint16_t skin,uint16_t hair,int guard){
    int x,y;
    memset(p,0,24*48*2);memset(a,0,24*48);
    for(y=2;y<14;++y)for(x=6;x<18;++x){
        int dx=x-12,dy=y-8;
        if(dx*dx+dy*dy<=38)actor_px(p,a,x,y,vxpe2d_rgb565(19,21,25),255);
        if(dx*dx+dy*dy<=28)actor_px(p,a,x,y,skin,255);
    }
    for(y=2;y<7;++y)for(x=7;x<18;++x)
        if(((x-12)*(x-12)+(y-7)*(y-7))<32)actor_px(p,a,x,y,hair,255);
    if(guard){for(x=6;x<18;++x)actor_px(p,a,x,2,vxpe2d_rgb565(22,27,36),255);}
    for(y=13;y<31;++y)for(x=5;x<19;++x)actor_px(p,a,x,y,vxpe2d_rgb565(18,20,24),255);
    for(y=14;y<30;++y)for(x=6;x<18;++x)actor_px(p,a,x,y,shirt,255);
    for(y=16;y<31;++y){
        actor_px(p,a,3,y,vxpe2d_rgb565(18,20,24),255);actor_px(p,a,4,y,skin,255);
        actor_px(p,a,19,y,skin,255);actor_px(p,a,20,y,vxpe2d_rgb565(18,20,24),255);
    }
    for(x=6;x<18;++x)actor_px(p,a,x,29,vxpe2d_rgb565(24,25,28),255);
    for(y=30;y<46;++y){
        for(x=6;x<11;++x)actor_px(p,a,x,y,pants,255);
        for(x=13;x<18;++x)actor_px(p,a,x,y,pants,255);
    }
    for(x=5;x<11;++x)for(y=45;y<48;++y)actor_px(p,a,x,y,vxpe2d_rgb565(16,18,20),255);
    for(x=13;x<19;++x)for(y=45;y<48;++y)actor_px(p,a,x,y,vxpe2d_rgb565(16,18,20),255);
}

static void build_assets(void){
    build_actor(g_player_px,g_player_a,vxpe2d_rgb565(225,229,229),vxpe2d_rgb565(46,60,83),vxpe2d_rgb565(208,157,121),vxpe2d_rgb565(74,49,35),0);
    build_actor(g_guard_px,g_guard_a,vxpe2d_rgb565(103,133,173),vxpe2d_rgb565(38,45,59),vxpe2d_rgb565(190,143,110),vxpe2d_rgb565(44,39,34),1);
    memset(&g_player_sprite,0,sizeof(g_player_sprite));
    g_player_sprite.pixels=g_player_px;g_player_sprite.alpha=g_player_a;g_player_sprite.width=24;g_player_sprite.height=48;g_player_sprite.stride=24;g_player_sprite.alpha_stride=24;
    memset(&g_guard_sprite,0,sizeof(g_guard_sprite));
    g_guard_sprite.pixels=g_guard_px;g_guard_sprite.alpha=g_guard_a;g_guard_sprite.width=24;g_guard_sprite.height=48;g_guard_sprite.stride=24;g_guard_sprite.alpha_stride=24;
}

static void setup_scene(void){
    vxpe25d_camera_init(&g_camera,SW,SH,76,150);
    g_camera.world_y=120;g_camera.near_z=80;g_camera.far_z=520;
    g_camera.min_scale_q8=70;g_camera.max_scale_q8=520;
    g_camera.fog_near_z=260;g_camera.fog_far_z=500;
    g_camera.fog_color565=vxpe2d_rgb565(67,83,103);g_camera.fog_strength=90;
    vxpe2d_lightmap_init(&g_lightmap,60,80,SW,SH);
}

static const char* phase_name(void){
    switch(g_phase){
        case PHASE_DEPLOYMENT:return "DEPLOYMENT";
        case PHASE_PARK:return "PARK";
        case PHASE_ENTRY:return "ENTRY";
        case PHASE_SNEAK:return "SNEAK";
        case PHASE_PISTOL:return "PISTOL";
        default:return "EXIT";
    }
}

static const char* action_name(void){
    if(g_done)return "DONE";
    switch(g_phase){
        case PHASE_DEPLOYMENT:return "DRIVE";
        case PHASE_PARK:return "PARK";
        case PHASE_ENTRY:return g_entry_action_tick?"WORK":"WRENCH";
        case PHASE_SNEAK:
            if(g_guard_state==GUARD_ALERT)return "ALERT";
            if(g_guard_state==GUARD_WATCH)return "WATCH";
            return "SNEAK";
        case PHASE_PISTOL:return "FIRE";
        default:return "EXIT";
    }
}

static void reset_guard_ai(void){
    g_guard_state=GUARD_PATROL;
    g_guard_detection=0;
    g_guard_patrol_dir=1;
}

static void enter_phase(MissionPhase phase){
    g_phase=phase;g_phase_flash=10;g_alert=0;g_shot_flash=0;
    g_entry_action_tick=0;
    if(phase!=PHASE_ENTRY)g_door_open=0;
    switch(phase){
        case PHASE_DEPLOYMENT:
            g_car_x=112;g_drive_progress=0;g_targets=2;g_done=0;break;
        case PHASE_PARK:
            g_car_x=62;g_targets=2;break;
        case PHASE_ENTRY:
            g_entry_x=70;g_targets=2;g_door_open=0;break;
        case PHASE_SNEAK:
            g_player_x=-28;g_player_z=110;g_guard_x=22;g_guard_z=220;
            g_targets=2;g_guard_alive=1;reset_guard_ai();break;
        case PHASE_PISTOL:
            g_player_x=-12;g_player_z=122;g_guard_x=34;g_guard_z=245;
            g_targets=1;g_guard_alive=1;break;
        case PHASE_EXIT:
            g_player_x=-8;g_player_z=120;g_targets=0;g_guard_alive=0;g_exit_progress=0;break;
    }
}

static void draw_actor_world(uint16_t* fb,const VxpeSpriteA8* sprite,int32_t x,int32_t z,int player){
    VxpeBillboard25D b;
    memset(&b,0,sizeof(b));
    b.src.x=0;b.src.y=0;b.src.w=24;b.src.h=48;
    b.world_x=x;b.world_y=0;b.world_z=z;b.world_w=36;b.world_h=72;
    b.pivot_x_q8=128;b.pivot_y_q8=256;b.tint565=0xFFFF;b.alpha=255;b.blend=VXPE_BLEND_ALPHA;
    vxpe25d_draw_ground_shadow(fb,SW,SH,&g_camera,x,z,player?18:13,player?5:4,vxpe2d_rgb565(10,13,18),105,VXPE_BLEND_ALPHA);
    vxpe25d_draw_billboard(fb,SW,SH,&g_camera,sprite,&b);
}

static int guard_player_in_cone(void){
    int dz=(int)(g_guard_z-g_player_z);
    int center,half,dx;
    if(!g_guard_alive||g_phase!=PHASE_SNEAK)return 0;
    if(dz<18||dz>155)return 0;
    center=(int)g_guard_x + g_guard_patrol_dir*(dz/9);
    half=16+dz/5;
    dx=(int)g_player_x-center;
    if(dx<0)dx=-dx;
    return dx<=half;
}

static void update_guard_ai(void){
    int sees;
    if(g_phase!=PHASE_SNEAK||!g_guard_alive)return;

    if(g_guard_state==GUARD_ALERT){
        g_guard_detection=100;
        g_alert=30;
        if(g_guard_x<g_player_x)++g_guard_x;
        else if(g_guard_x>g_player_x)--g_guard_x;
        if((g_tick&3u)==0u && g_guard_z-g_player_z>68)--g_guard_z;
        return;
    }

    sees=guard_player_in_cone();
    if(sees)g_guard_detection=clampi(g_guard_detection+4,0,100);
    else g_guard_detection=clampi(g_guard_detection-2,0,100);

    if(g_guard_detection>=65){
        g_guard_state=GUARD_ALERT;
        g_alert=30;
    }else if(g_guard_detection>=24){
        g_guard_state=GUARD_WATCH;
        g_guard_patrol_dir=(g_player_x>=g_guard_x)?1:-1;
    }else{
        g_guard_state=GUARD_PATROL;
        if((g_tick&1u)==0u){
            g_guard_x+=g_guard_patrol_dir;
            if(g_guard_x<=g_guard_patrol_left){
                g_guard_x=g_guard_patrol_left;
                g_guard_patrol_dir=1;
            }else if(g_guard_x>=g_guard_patrol_right){
                g_guard_x=g_guard_patrol_right;
                g_guard_patrol_dir=-1;
            }
        }
    }
}

static void draw_guard_vision(uint16_t* fb){
    VxpeProjected25D gp,lp,rp;
    int near_z,dz,center,half,base_y;
    uint16_t color;
    uint8_t alpha;
    if(!g_guard_alive||g_phase!=PHASE_SNEAK)return;
    near_z=(int)g_guard_z-150;
    if(near_z<92)near_z=92;
    dz=(int)g_guard_z-near_z;
    if(g_guard_state==GUARD_ALERT){
        center=(int)g_player_x;
        half=34;
        color=vxpe2d_rgb565(238,61,52);
        alpha=68;
    }else{
        center=(int)g_guard_x+g_guard_patrol_dir*(dz/9);
        half=20+dz/4;
        color=(g_guard_state==GUARD_WATCH)
            ?vxpe2d_rgb565(242,194,66)
            :vxpe2d_rgb565(106,204,127);
        alpha=(g_guard_state==GUARD_WATCH)?54:38;
    }
    if(!vxpe25d_project(&g_camera,g_guard_x,0,g_guard_z,&gp))return;
    if(!vxpe25d_project(&g_camera,center-half,0,near_z,&lp))return;
    if(!vxpe25d_project(&g_camera,center+half,0,near_z,&rp))return;
    base_y=(lp.y+rp.y)/2;
    fill_scan_quad_alpha(fb,gp.x,gp.x,gp.y-3,lp.x,rp.x,base_y,color,alpha);
    line(fb,gp.x,gp.y-3,lp.x,base_y,color);
    line(fb,gp.x,gp.y-3,rp.x,base_y,color);
}

static void draw_city(uint16_t* fb,int day){
    int i,j;
    uint16_t sky=day?vxpe2d_rgb565(165,203,219):vxpe2d_rgb565(10,31,60);
    vxpe2d_gradient_vertical(fb,SW,SH,0,GAME_TOP,SW,GAME_BOTTOM-GAME_TOP,sky,day?vxpe2d_rgb565(229,214,170):vxpe2d_rgb565(25,52,77));
    for(i=0;i<7;++i){
        int bx=10+i*34;int bh=54+(i*17)%80;int top=155-bh;
        uint16_t bc=vxpe2d_rgb565((uint8_t)(73+i*8),(uint8_t)(91+i*5),(uint8_t)(104+i*4));
        vxpe2d_fill_rect(fb,SW,SH,bx,top,27,bh,bc);
        for(j=0;j<4;++j){
            if(((i+j)&1)==0)vxpe2d_fill_rect(fb,SW,SH,bx+5+(j&1)*10,top+9+j*15,5,7,day?vxpe2d_rgb565(55,75,89):vxpe2d_rgb565(246,211,99));
        }
    }
}

static void draw_car(uint16_t* fb,int x,int y,int scale){
    uint16_t dark=vxpe2d_rgb565(52,29,31),red=vxpe2d_rgb565(193,55,50),light=vxpe2d_rgb565(239,78,66);
    int w=50*scale/10,h=25*scale/10;
    vxpe2d_fill_rect(fb,SW,SH,x-w/2,y-h,w,h,red);
    vxpe2d_fill_rect(fb,SW,SH,x-w/3,y-h-9*scale/10,w*2/3,11*scale/10,dark);
    vxpe2d_fill_rect(fb,SW,SH,x-w/3+3,y-h-7*scale/10,w*2/3-6,6*scale/10,vxpe2d_rgb565(78,115,143));
    vxpe2d_fill_rect(fb,SW,SH,x-w/2+4,y-h+4,8*scale/10,4*scale/10,light);
    vxpe2d_fill_rect(fb,SW,SH,x+w/2-12*scale/10,y-h+4,8*scale/10,4*scale/10,light);
    vxpe2d_fill_rect(fb,SW,SH,x-w/2+3,y-4,9*scale/10,5,vxpe2d_rgb565(20,22,25));
    vxpe2d_fill_rect(fb,SW,SH,x+w/2-12*scale/10,y-4,9*scale/10,5,vxpe2d_rgb565(20,22,25));
}

static void draw_deployment(uint16_t* fb){
    int horizon=122,road_center=120,road_top=28,road_bottom=196;
    draw_city(fb,1);
    vxpe2d_fill_rect(fb,SW,SH,0,151,SW,87,vxpe2d_rgb565(197,183,146));
    fill_scan_quad(fb,road_center-road_top/2,road_center+road_top/2,horizon,road_center-road_bottom/2,road_center+road_bottom/2,GAME_BOTTOM,vxpe2d_rgb565(53,58,64));
    line(fb,road_center-road_top/2,horizon,road_center-road_bottom/2,GAME_BOTTOM,0xFFFF);
    line(fb,road_center+road_top/2,horizon,road_center+road_bottom/2,GAME_BOTTOM,0xFFFF);
    {
        int y;
        for(y=horizon+12;y<GAME_BOTTOM;y+=26){
            int half=(y-horizon)/3;
            vxpe2d_fill_rect(fb,SW,SH,118,y,4+half/9,10+half/2,0xFFFF);
        }
    }
    draw_car(fb,g_car_x,215,12);
    vxpe2d_fill_rect(fb,SW,SH,12,177,55,5,vxpe2d_rgb565(70,76,79));
    vxpe2d_fill_rect(fb,SW,SH,174,177,54,5,vxpe2d_rgb565(70,76,79));
    text5(fb,63,30,"CITY APPROACH",vxpe2d_rgb565(30,38,45),1);
}

static void draw_park(uint16_t* fb){
    uint16_t wall=vxpe2d_rgb565(116,127,135),asphalt=vxpe2d_rgb565(64,68,72),outline=vxpe2d_rgb565(24,27,30);
    draw_city(fb,1);
    vxpe2d_fill_rect(fb,SW,SH,0,67,59,171,vxpe2d_rgb565(125,75,58));
    vxpe2d_fill_rect(fb,SW,SH,59,87,71,151,wall);
    vxpe2d_fill_rect(fb,SW,SH,130,70,110,168,vxpe2d_rgb565(75,82,94));
    fill_scan_quad(fb,82,164,112,20,220,GAME_BOTTOM,asphalt);
    line(fb,82,112,20,GAME_BOTTOM,outline);line(fb,164,112,220,GAME_BOTTOM,outline);
    vxpe2d_fill_rect(fb,SW,SH,22,95,29,48,vxpe2d_rgb565(66,45,43));
    vxpe2d_fill_rect(fb,SW,SH,184,100,40,42,vxpe2d_rgb565(94,66,44));
    line(fb,184,100,224,142,outline);line(fb,224,100,184,142,outline);
    draw_car(fb,g_car_x,207,11);
    line(fb,154,184,201,184,vxpe2d_rgb565(244,220,93));
    line(fb,154,184,154,224,vxpe2d_rgb565(244,220,93));
    line(fb,201,184,201,224,vxpe2d_rgb565(244,220,93));
    text5(fb,151,168,"PARK",vxpe2d_rgb565(244,220,93),1);
}

static void draw_entry(uint16_t* fb){
    uint16_t building=vxpe2d_rgb565(130,155,173),dark=vxpe2d_rgb565(24,39,54),outline=vxpe2d_rgb565(20,25,29);
    uint16_t door=vxpe2d_rgb565(83,110,130),wrench=vxpe2d_rgb565(235,236,231);
    int door_w=52*(100-g_door_open)/100;
    int phase=(g_entry_action_tick/3)&3;
    vxpe2d_gradient_vertical(fb,SW,SH,0,GAME_TOP,SW,GAME_BOTTOM-GAME_TOP,vxpe2d_rgb565(131,190,214),vxpe2d_rgb565(201,211,194));
    vxpe2d_fill_rect(fb,SW,SH,0,36,SW,202,building);
    vxpe2d_fill_rect(fb,SW,SH,89,60,72,178,vxpe2d_rgb565(102,133,155));
    vxpe2d_fill_rect(fb,SW,SH,99,84,52,154,dark);
    if(door_w>0){
        vxpe2d_fill_rect(fb,SW,SH,99,84,door_w,154,door);
        line(fb,99+door_w-1,84,99+door_w-1,238,outline);
        if(door_w>12)vxpe2d_fill_rect(fb,SW,SH,99+door_w-10,155,5,8,vxpe2d_rgb565(221,195,97));
    }
    line(fb,99,84,151,84,outline);line(fb,99,84,99,238,outline);line(fb,151,84,151,238,outline);
    {
        int i;for(i=0;i<5;++i){
            vxpe2d_fill_rect(fb,SW,SH,17+i*42,54+(i&1)*16,20,35,vxpe2d_rgb565(47,79,104));
        }
    }
    g_player_x=clampi(g_entry_x-120,-70,70);
    g_player_z=125;
    draw_actor_world(fb,&g_player_sprite,g_player_x,g_player_z,1);

    if(g_entry_action_tick){
        if(phase==0)line(fb,168,181,190,181,wrench);
        else if(phase==1)line(fb,170,176,190,193,wrench);
        else if(phase==2)line(fb,180,174,180,197,wrench);
        else line(fb,190,176,170,193,wrench);
        vxpe2d_fill_rect(fb,SW,SH,165,205,62,6,vxpe2d_rgb565(31,42,51));
        vxpe2d_fill_rect(fb,SW,SH,166,206,(60*g_door_open)/100,4,vxpe2d_rgb565(246,214,76));
        text5(fb,170,215,"WORK",vxpe2d_rgb565(246,214,76),1);
    }else{
        line(fb,172,172,190,190,wrench);
        vxpe2d_fill_rect(fb,SW,SH,187,186,8,4,wrench);
        text5(fb,157,198,"WRENCH",vxpe2d_rgb565(246,214,76),1);
    }
}

static void draw_corridor(uint16_t* fb,int combat){
    uint16_t outline=vxpe2d_rgb565(15,19,25),wall=vxpe2d_rgb565(111,125,139),wall_dark=vxpe2d_rgb565(63,77,94);
    uint16_t ceil=vxpe2d_rgb565(72,79,88),floor=vxpe2d_rgb565(76,82,91);
    int y;
    vxpe2d_fill_rect(fb,SW,SH,0,GAME_TOP,SW,GAME_BOTTOM-GAME_TOP,vxpe2d_rgb565(28,37,50));
    /* city right */
    vxpe2d_fill_rect(fb,SW,SH,136,GAME_TOP,104,GAME_BOTTOM-GAME_TOP,vxpe2d_rgb565(10,31,60));
    {int i,j;for(i=0;i<4;++i){int bx=146+i*25,top=40+(i&1)*24,bw=20+(i&1)*5;
        vxpe2d_fill_rect(fb,SW,SH,bx,top,bw,150-top,vxpe2d_rgb565(24+i*6,47+i*5,73+i*4));
        for(j=0;j<5;++j)if(((i+j)&1)==0)vxpe2d_fill_rect(fb,SW,SH,bx+4+(j&1)*8,top+9+j*22,4,7,vxpe2d_rgb565(242,201,91));}}
    fill_scan_quad(fb,0,240,GAME_TOP,96,144,78,ceil);
    fill_scan_quad(fb,42,198,GAME_BOTTOM,103,137,78,floor);
    for(y=GAME_TOP;y<=GAME_BOTTOM;++y){
        int right=y<=78?40+(56*(y-GAME_TOP)/(78-GAME_TOP)):96-(54*(y-78)/(GAME_BOTTOM-78));
        vxpe2d_fill_rect(fb,SW,SH,0,y,right,1,wall);
    }
    fill_scan_quad(fb,184,240,GAME_BOTTOM,142,240,78,wall_dark);
    line(fb,198,GAME_BOTTOM,142,78,outline);line(fb,42,GAME_BOTTOM,103,78,outline);
    for(y=104;y<GAME_BOTTOM;y+=22){
        int spread=(y-78)*78/(GAME_BOTTOM-78);
        line(fb,120-spread,y,120+spread,y,vxpe2d_rgb565(92,98,106));
    }
    vxpe2d_fill_rect(fb,SW,SH,5,60,27,72,vxpe2d_rgb565(34,52,73));
    vxpe2d_fill_rect(fb,SW,SH,37,84,18,48,vxpe2d_rgb565(39,57,75));
    vxpe2d_fill_rect(fb,SW,SH,24,99,14,31,vxpe2d_rgb565(103,37,36));
    vxpe2d_fill_rect(fb,SW,SH,27,104,8,12,vxpe2d_rgb565(154,74,66));
    vxpe2d_fill_rect(fb,SW,SH,106,30,28,7,vxpe2d_rgb565(43,41,35));
    vxpe2d_fill_rect(fb,SW,SH,109,31,22,5,vxpe2d_rgb565(255,219,129));
    vxpe2d_fill_rect(fb,SW,SH,112,54,17,5,vxpe2d_rgb565(255,222,145));
    vxpe2d_fill_rect(fb,SW,SH,175,154,43,48,vxpe2d_rgb565(105,72,44));
    vxpe2d_fill_rect(fb,SW,SH,179,158,35,40,vxpe2d_rgb565(133,91,55));
    line(fb,179,158,214,198,outline);line(fb,214,158,179,198,outline);
    if(combat)vxpe2d_fill_rect(fb,SW,SH,85,89,70,4,vxpe2d_rgb565(91,43,40));
}

static void draw_sneak(uint16_t* fb){
    draw_corridor(fb,0);
    draw_guard_vision(fb);
    if(g_guard_alive)draw_actor_world(fb,&g_guard_sprite,g_guard_x,g_guard_z,0);
    if(g_targets>1)draw_actor_world(fb,&g_guard_sprite,-18,315,0);
    draw_actor_world(fb,&g_player_sprite,g_player_x,g_player_z,1);
}

static void draw_pistol(uint16_t* fb){
    VxpeProjected25D gp;
    draw_corridor(fb,1);
    if(g_guard_alive)draw_actor_world(fb,&g_guard_sprite,g_guard_x,g_guard_z,0);
    draw_actor_world(fb,&g_player_sprite,g_player_x,g_player_z,1);
    if(vxpe25d_project(&g_camera,g_guard_x,0,g_guard_z,&gp)){
        int cx=gp.x,cy=gp.y-22;
        line(fb,cx-8,cy,cx-2,cy,0xFFFF);line(fb,cx+2,cy,cx+8,cy,0xFFFF);
        line(fb,cx,cy-8,cx,cy-2,0xFFFF);line(fb,cx,cy+2,cx,cy+8,0xFFFF);
        if(g_shot_flash>0){
            vxpe2d_radial_light_fast(fb,SW,SH,cx,cy,18,vxpe2d_rgb565(115,218,255),180);
            vxpe2d_draw_ring(fb,SW,SH,cx,cy,6+(g_shot_flash&3),1,0xFFFF,210,VXPE_BLEND_ADD);
        }
    }
}

static void draw_exit(uint16_t* fb){
    uint16_t dark=vxpe2d_rgb565(27,30,38),wall=vxpe2d_rgb565(61,65,77),floor=vxpe2d_rgb565(56,60,70);
    vxpe2d_fill_rect(fb,SW,SH,0,GAME_TOP,SW,GAME_BOTTOM-GAME_TOP,dark);
    fill_scan_quad(fb,0,240,GAME_TOP,74,166,92,wall);
    fill_scan_quad(fb,28,212,GAME_BOTTOM,92,148,92,floor);
    vxpe2d_fill_rect(fb,SW,SH,93,57,55,77,vxpe2d_rgb565(35,45,56));
    vxpe2d_fill_rect(fb,SW,SH,101,65,39,61,vxpe2d_rgb565(20,31,42));
    vxpe2d_fill_rect(fb,SW,SH,105,72,31,8,g_done?vxpe2d_rgb565(75,205,106):vxpe2d_rgb565(195,65,57));
    text5(fb,102,97,g_done?"OPEN":"EXIT",g_done?vxpe2d_rgb565(112,236,130):vxpe2d_rgb565(244,214,78),1);
    g_player_x=0;g_player_z=120+g_exit_progress;
    draw_actor_world(fb,&g_player_sprite,g_player_x,g_player_z,1);
    if(g_done)text5(fb,76,154,"MISSION DONE",vxpe2d_rgb565(244,219,83),1);
}

static void draw_minimap(uint16_t* fb){
    int mx=5,my=247,mw=104,mh=68;
    int px=mx+52,py=my+52;
    vxpe2d_fill_rect(fb,SW,SH,mx,my,mw,mh,vxpe2d_rgb565(60,82,69));
    if(g_phase==PHASE_DEPLOYMENT){
        line(fb,mx+10,my+56,mx+91,my+12,vxpe2d_rgb565(211,205,176));
        px=mx+19+g_drive_progress*65/100;py=my+54-g_drive_progress*35/100;
    }else if(g_phase==PHASE_PARK){
        vxpe2d_fill_rect(fb,SW,SH,mx+10,my+8,84,52,vxpe2d_rgb565(117,123,111));
        line(fb,mx+20,my+52,mx+88,my+13,vxpe2d_rgb565(54,69,61));
        px=mx+15+g_car_x*75/220;py=my+47;
    }else if(g_phase==PHASE_ENTRY){
        vxpe2d_fill_rect(fb,SW,SH,mx+9,my+8,86,51,vxpe2d_rgb565(122,132,119));
        vxpe2d_fill_rect(fb,SW,SH,mx+61,my+8,25,35,vxpe2d_rgb565(65,77,71));
        px=mx+8+g_entry_x*88/240;py=my+52;
    }else{
        vxpe2d_fill_rect(fb,SW,SH,mx+10,my+7,29,20,vxpe2d_rgb565(131,137,124));
        vxpe2d_fill_rect(fb,SW,SH,mx+47,my+5,19,32,vxpe2d_rgb565(142,142,131));
        vxpe2d_fill_rect(fb,SW,SH,mx+72,my+12,25,20,vxpe2d_rgb565(130,136,125));
        vxpe2d_fill_rect(fb,SW,SH,mx+16,my+40,34,18,vxpe2d_rgb565(120,129,115));
        px=mx+52+(int)(g_player_x*28/90);
        py=my+mh-8-(int)((g_player_z-90)*44/250);
        if(g_guard_alive){
            int gx=mx+52+(int)(g_guard_x*28/90);
            int gy=my+mh-8-(int)((g_guard_z-90)*44/250);
            vxpe2d_fill_rect(fb,SW,SH,gx-2,gy-2,5,5,vxpe2d_rgb565(232,50,48));
        }
    }
    pixel(fb,px,py-3,0xFFFF);pixel(fb,px-1,py-2,0xFFFF);pixel(fb,px+1,py-2,0xFFFF);
    pixel(fb,px-2,py-1,0xFFFF);pixel(fb,px+2,py-1,0xFFFF);pixel(fb,px,py,0xFFFF);
    line(fb,mx,my,mx+mw,my,0xFFFF);line(fb,mx,my+mh,mx+mw,my+mh,0xFFFF);
    line(fb,mx,my,mx,my+mh,0xFFFF);line(fb,mx+mw,my,mx+mw,my+mh,0xFFFF);
}

static void draw_hud(uint16_t* fb){
    uint16_t white=vxpe2d_rgb565(240,242,240),yellow=vxpe2d_rgb565(251,216,77);
    char count_text[2]={'0',0};
    int panel_x=113;
    vxpe2d_fill_rect(fb,SW,SH,0,HUD_TOP,SW,SH-HUD_TOP,vxpe2d_rgb565(4,7,10));
    draw_minimap(fb);
    line(fb,111,HUD_TOP,111,SH-1,vxpe2d_rgb565(180,185,186));
    text5(fb,panel_x+3,246,phase_name(),white,1);
    if(g_phase==PHASE_SNEAK||g_phase==PHASE_PISTOL){
        text5(fb,panel_x+3,257,"TARGETS:",white,1);
        count_text[0]=(char)('0'+clampi(g_targets,0,9));
        text5(fb,222,257,count_text,g_targets?white:yellow,1);
    }
    vxpe2d_fill_rect(fb,SW,SH,panel_x+3,270,48,19,vxpe2d_rgb565(18,25,35));
    vxpe2d_fill_rect(fb,SW,SH,panel_x+55,270,48,19,vxpe2d_rgb565(18,25,35));
    if(g_phase==PHASE_SNEAK){
        uint16_t meter=(g_guard_state==GUARD_ALERT)
            ?vxpe2d_rgb565(244,68,56)
            :(g_guard_state==GUARD_WATCH?vxpe2d_rgb565(242,190,66):vxpe2d_rgb565(89,190,116));
        vxpe2d_fill_rect(fb,SW,SH,panel_x+58,276,42,5,vxpe2d_rgb565(46,54,63));
        vxpe2d_fill_rect(fb,SW,SH,panel_x+58,276,(42*g_guard_detection)/100,5,meter);
        line(fb,panel_x+62,284,panel_x+80,272,meter);
        line(fb,panel_x+80,272,panel_x+96,284,meter);
    }
    if(g_phase==PHASE_PISTOL){
        line(fb,panel_x+8,282,panel_x+35,275,white);vxpe2d_fill_rect(fb,SW,SH,panel_x+29,278,11,3,white);
    }else if(g_phase==PHASE_ENTRY){
        line(fb,panel_x+11,275,panel_x+32,286,white);line(fb,panel_x+31,273,panel_x+39,280,white);
    }else{
        line(fb,panel_x+8,284,panel_x+37,275,vxpe2d_rgb565(96,105,116));
    }
    {
        uint16_t action_color=yellow;
        if(g_phase==PHASE_SNEAK&&g_guard_state==GUARD_ALERT)action_color=vxpe2d_rgb565(255,83,72);
        else if(g_phase==PHASE_SNEAK&&g_guard_state==GUARD_WATCH)action_color=vxpe2d_rgb565(247,194,71);
        else if(g_alert)action_color=vxpe2d_rgb565(255,83,72);
        text5(fb,panel_x+3,296,action_name(),action_color,1);
    }
}

static void draw_topbar(uint16_t* fb){
    vxpe2d_fill_rect(fb,SW,SH,0,0,SW,16,vxpe2d_rgb565(3,6,9));
    text5(fb,4,4,"VXPE INFILTRATE",0xFFFF,1);
    vxpe2d_fill_rect(fb,SW,SH,207,9,2,4,0xFFFF);vxpe2d_fill_rect(fb,SW,SH,211,7,2,6,0xFFFF);vxpe2d_fill_rect(fb,SW,SH,215,5,2,8,0xFFFF);
    vxpe2d_fill_rect(fb,SW,SH,222,4,14,8,vxpe2d_rgb565(194,201,199));vxpe2d_fill_rect(fb,SW,SH,224,6,9,4,vxpe2d_rgb565(91,194,112));
}

static void draw_scene(uint16_t* fb){
    switch(g_phase){
        case PHASE_DEPLOYMENT:draw_deployment(fb);break;
        case PHASE_PARK:draw_park(fb);break;
        case PHASE_ENTRY:draw_entry(fb);break;
        case PHASE_SNEAK:draw_sneak(fb);break;
        case PHASE_PISTOL:draw_pistol(fb);break;
        case PHASE_EXIT:draw_exit(fb);break;
    }
    if(g_phase==PHASE_SNEAK||g_phase==PHASE_PISTOL){
        vxpe2d_lightmap_clear(&g_lightmap);
        vxpe2d_lightmap_add_radial(&g_lightmap,120,35,48,vxpe2d_rgb565(255,220,135),78);
        vxpe2d_lightmap_composite_add(&g_lightmap,fb,SW,SH,70,286);
    }
    if(g_phase_flash>0){
        vxpe2d_overlay_rect(fb,SW,SH,0,GAME_TOP,SW,GAME_BOTTOM-GAME_TOP,0xFFFF,(uint8_t)(g_phase_flash*7),VXPE_BLEND_ALPHA);
    }
}

static void draw(void){
    uint16_t* fb=(uint16_t*)framebuffer();
    VxpeGrade25D grade;
    if(!fb||g_layer<0)return;
    draw_scene(fb);
    memset(&grade,0,sizeof(grade));
    grade.tint565=vxpe2d_rgb565(63,77,97);
    grade.tint_alpha=(g_phase==PHASE_DEPLOYMENT||g_phase==PHASE_PARK||g_phase==PHASE_ENTRY)?5:12;
    grade.vignette_alpha=16;grade.dither_strength=2;grade.fog_horizon_alpha=6;
    vxpe25d_apply_grade(fb,SW,SH,&grade,76);
    draw_topbar(fb);draw_hud(fb);
    vm_graphic_flush_layer(&g_layer,1);
}

static void action(void){
    if(g_done)return;
    if(g_phase==PHASE_DEPLOYMENT){
        g_drive_progress=100;enter_phase(PHASE_PARK);
    }else if(g_phase==PHASE_PARK){
        if(g_car_x>=145&&g_car_x<=205)enter_phase(PHASE_ENTRY);
        else g_alert=18;
    }else if(g_phase==PHASE_ENTRY){
        if(g_entry_action_tick)return;
        if(g_entry_x>=100&&g_entry_x<=155){
            g_entry_action_tick=1;
            g_door_open=0;
            g_alert=0;
        }else g_alert=18;
    }else if(g_phase==PHASE_SNEAK){
        int dz=(int)(g_guard_z-g_player_z),dx=(int)(g_guard_x-g_player_x);if(dx<0)dx=-dx;
        if(g_guard_alive&&dz>=0&&dz<95&&dx<48){
            --g_targets;g_phase_flash=6;
            if(g_targets>0){
                g_guard_x=-18;g_guard_z=315;g_guard_alive=1;reset_guard_ai();
            }else{
                g_guard_alive=0;enter_phase(PHASE_PISTOL);
            }
        }else g_alert=22;
    }else if(g_phase==PHASE_PISTOL){
        int dx=(int)(g_guard_x-g_player_x);if(dx<0)dx=-dx;
        g_shot_flash=7;
        if(dx<70&&g_guard_alive){
            g_guard_alive=0;g_targets=0;g_phase_flash=7;enter_phase(PHASE_EXIT);
        }else g_alert=20;
    }else if(g_phase==PHASE_EXIT){
        if(g_exit_progress>=95){g_done=1;g_phase_flash=10;}
        else g_alert=18;
    }
}

static void tick(VMINT tid){
    (void)tid;++g_tick;
    if(g_phase_flash>0)--g_phase_flash;
    if(g_alert>0)--g_alert;
    if(g_shot_flash>0)--g_shot_flash;

    if(g_phase==PHASE_ENTRY&&g_entry_action_tick>0){
        ++g_entry_action_tick;
        g_door_open=clampi((g_entry_action_tick*100)/30,0,100);
        if(g_entry_action_tick>=32){
            g_entry_action_tick=0;
            enter_phase(PHASE_SNEAK);
        }
    }else if(g_phase==PHASE_SNEAK){
        update_guard_ai();
    }
    draw();
}

void handle_keyevt(VMINT event,VMINT keycode){
    if(event!=VM_KEY_EVENT_DOWN&&event!=VM_KEY_EVENT_REPEAT)return;
    if(keycode==VM_KEY_LEFT||keycode==VM_KEY_NUM4){
        if(g_phase==PHASE_PARK)g_car_x=clampi(g_car_x-9,28,212);
        else if(g_phase==PHASE_ENTRY&&g_entry_action_tick==0)g_entry_x=clampi(g_entry_x-9,20,220);
        else g_player_x=clampi((int)g_player_x-7,-78,78);
    }else if(keycode==VM_KEY_RIGHT||keycode==VM_KEY_NUM6){
        if(g_phase==PHASE_PARK)g_car_x=clampi(g_car_x+9,28,212);
        else if(g_phase==PHASE_ENTRY&&g_entry_action_tick==0)g_entry_x=clampi(g_entry_x+9,20,220);
        else g_player_x=clampi((int)g_player_x+7,-78,78);
    }else if(keycode==VM_KEY_UP||keycode==VM_KEY_NUM2){
        if(g_phase==PHASE_DEPLOYMENT)g_drive_progress=clampi(g_drive_progress+12,0,100);
        else if(g_phase==PHASE_EXIT)g_exit_progress=clampi(g_exit_progress+12,0,110);
        else if(g_phase==PHASE_SNEAK||g_phase==PHASE_PISTOL)g_player_z=clampi((int)g_player_z+10,96,315);
    }else if(keycode==VM_KEY_DOWN||keycode==VM_KEY_NUM8){
        if(g_phase==PHASE_DEPLOYMENT)g_drive_progress=clampi(g_drive_progress-12,0,100);
        else if(g_phase==PHASE_EXIT)g_exit_progress=clampi(g_exit_progress-12,0,110);
        else if(g_phase==PHASE_SNEAK||g_phase==PHASE_PISTOL)g_player_z=clampi((int)g_player_z-10,96,315);
    }else if(keycode==VM_KEY_OK||keycode==VM_KEY_NUM5){
        action();
    }else if(keycode==VM_KEY_RIGHT_SOFTKEY||keycode==VM_KEY_CLEAR||keycode==VM_KEY_BACK){
        vm_exit_app();return;
    }
    draw();
}

void handle_penevt(VMINT event,VMINT x,VMINT y){
    if(event!=VM_PEN_EVENT_TAP&&event!=VM_PEN_EVENT_MOVE)return;
    if(g_phase==PHASE_PARK)g_car_x=clampi(x,28,212);
    else if(g_phase==PHASE_ENTRY&&g_entry_action_tick==0)g_entry_x=clampi(x,20,220);
    else if(g_phase==PHASE_SNEAK||g_phase==PHASE_PISTOL){
        g_player_x=clampi((x-120)*2/3,-78,78);
        g_player_z=clampi(96+(GAME_BOTTOM-y)*210/(GAME_BOTTOM-GAME_TOP),96,315);
    }else if(g_phase==PHASE_EXIT)g_exit_progress=clampi((GAME_BOTTOM-y)*110/(GAME_BOTTOM-GAME_TOP),0,110);
    if(event==VM_PEN_EVENT_TAP)action();
    draw();
}

static void start(void){
    if(g_layer<0)g_layer=vm_graphic_create_layer(0,0,SW,SH,-1);
    if(!g_started){build_assets();setup_scene();enter_phase(PHASE_DEPLOYMENT);g_started=1;}
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
