/* Arrowfall Duel - standalone turn-based medieval archery sample for MRE VXP. */
#include "vmsys.h"
#include "vmio.h"
#include "vmgraph.h"
#include "vmtimer.h"
#include "vmres.h"
#include "vmmm.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

#define RGB565(r,g,b) (VMUINT16)((((r)&0xF8)<<8)|(((g)&0xFC)<<3)|((b)>>3))
#define C_SKY RGB565(35,52,80)
#define C_INK RGB565(17,23,31)
#define C_CREAM RGB565(255,239,190)
#define C_GOLD RGB565(237,197,91)
#define C_BRONZE RGB565(174,110,48)
#define C_PLAYER RGB565(65,176,112)
#define C_ENEMY RGB565(205,76,67)
#define C_TEAL RGB565(58,130,133)
#define PI 3.14159265358979323846f
#define WORLD_PLAYER_X 48.0f
#define WORLD_ENEMY_X 492.0f
#define MAX_TRAIL 14
#define POWER_MIN 30
#define POWER_MAX 90
#define POWER_FULL 84
#define MAX_PARTS 28

typedef enum { ST_TITLE, ST_HELP, ST_PLAYER_AIM, ST_ARROW, ST_AI_THINK, ST_ROUND_RESULT, ST_MATCH_RESULT } GameState;
typedef struct { float x, y, vx, vy; int owner, active, full; } Arrow;
typedef struct { float x, y, vx, vy; int life; VMUINT16 col; } Particle;

static VMINT g_layer = -1, g_timer = -1, g_tick = 0;
static GameState g_state = ST_TITLE;
static int g_paused = 0, g_difficulty = 1, g_angle = 45, g_power = 58;
static int g_player_hp = 100, g_enemy_hp = 100, g_player_rounds = 0, g_enemy_rounds = 0;
static int g_round = 1, g_wind = 0, g_state_ticks = 0, g_ai_misses = 0;
static int g_last_damage = 0, g_last_headshot = 0, g_last_full = 0, g_message_ticks = 0;
static int g_charging = 0, g_charge_dir = 1, g_charge_ticks = 0, g_pen_y0 = 0, g_angle0 = 0;
static int g_pred_angle = -1, g_pred_power = -1;
static float g_pred_x = 0, g_pred_hy = -1;
static Particle g_parts[MAX_PARTS];
static int g_shake = 0, g_flash_player = 0, g_flash_enemy = 0;
static int g_ghost_player = 100, g_ghost_enemy = 100, g_flash_all = 0;
static float g_cloud_x[3] = { 60.0f, 260.0f, 430.0f };
static float g_camera_x = WORLD_PLAYER_X, g_camera_y = 0.0f;
static Arrow g_arrow;
static float g_trail_x[MAX_TRAIL], g_trail_y[MAX_TRAIL];
static int g_trail_count = 0;
static VMUINT32 g_rng = 0xA17F2B39u, g_vfx_rng = 0x5EED1234u;
static VMUINT8 *g_bg = 0, *g_player = 0, *g_enemy = 0, *g_logo = 0;
static VMUINT8 *g_sfx_bow = 0, *g_sfx_hit = 0, *g_sfx_victory = 0;
static VMINT g_sfx_bow_size = 0, g_sfx_hit_size = 0, g_sfx_victory_size = 0;

static VMUINT16 *fb(void) { return (VMUINT16*)vm_graphic_get_layer_buffer(g_layer); }
static int clampi(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }
static float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }
static VMUINT32 rnd(void) { g_rng = g_rng * 1664525u + 1013904223u; return g_rng; }
static VMUINT32 vrnd(void) { g_vfx_rng = g_vfx_rng * 1664525u + 1013904223u; return g_vfx_rng; }
static float rndf(void) { return (float)(rnd() >> 8) / 16777216.0f; }
static float simulate_landing(int owner,int angle,int power);
static float predict_hit_height(int angle,int power);
static void burst(int owner,int hit,int head){int i;float x=owner?WORLD_PLAYER_X:WORLD_ENEMY_X;
    for(i=0;i<MAX_PARTS;++i){Particle*p=&g_parts[i];if(p->life>0)continue;
        p->x=x+(rndf()*30-15);p->y=hit?(30+rndf()*30):(2+rndf()*8);p->vx=(rndf()*2-1)*(hit?90:40);p->vy=hit?(rndf()*160-60):(rndf()*120+30);
        p->life=18+(int)(rndf()*14);p->col=hit?(head?C_GOLD:C_CREAM):RGB565(139,115,80);
        if(i-(i/8)*8==7)break;}}

static void fill_rect(VMUINT16 *d, int sw, int sh, int x, int y, int w, int h, VMUINT16 c) {
    int xx, yy, x0 = clampi(x,0,sw), y0 = clampi(y,0,sh), x1 = clampi(x+w,0,sw), y1 = clampi(y+h,0,sh);
    for (yy=y0; yy<y1; ++yy) for (xx=x0; xx<x1; ++xx) d[yy*sw+xx]=c;
}
static void line(VMUINT16 *d,int sw,int sh,int x0,int y0,int x1,int y1,VMUINT16 c) {
    int dx=x1>x0?x1-x0:x0-x1,sx=x0<x1?1:-1,dy0=y1>y0?y1-y0:y0-y1,dy=-dy0,sy=y0<y1?1:-1,err=dx+dy;
    for(;;){ if(x0>=0&&x0<sw&&y0>=0&&y0<sh)d[y0*sw+x0]=c; if(x0==x1&&y0==y1)break;
        {int e2=2*err;if(e2>=dy){err+=dy;x0+=sx;}if(e2<=dx){err+=dx;y0+=sy;}} }
}
static void frame_rect(VMUINT16*d,int sw,int sh,int x,int y,int w,int h,VMUINT16 c){
    fill_rect(d,sw,sh,x,y,w,1,c);fill_rect(d,sw,sh,x,y+h-1,w,1,c);fill_rect(d,sw,sh,x,y,1,h,c);fill_rect(d,sw,sh,x+w-1,y,1,h,c);
}

#define G(a,b,c,d,e) ((VMUINT16)(((a)<<12)|((b)<<9)|((c)<<6)|((d)<<3)|(e)))
static VMUINT16 glyph(char c){switch(c){
case'A':return G(2,5,7,5,5);case'B':return G(6,5,6,5,6);case'C':return G(3,4,4,4,3);case'D':return G(6,5,5,5,6);
case'E':return G(7,4,6,4,7);case'F':return G(7,4,6,4,4);case'G':return G(3,4,5,5,3);case'H':return G(5,5,7,5,5);
case'I':return G(7,2,2,2,7);case'J':return G(1,1,1,5,2);case'K':return G(5,5,6,5,5);case'L':return G(4,4,4,4,7);
case'M':return G(5,7,7,5,5);case'N':return G(5,7,7,7,5);case'O':return G(2,5,5,5,2);case'P':return G(6,5,6,4,4);
case'Q':return G(2,5,5,7,3);case'R':return G(6,5,6,5,5);case'S':return G(3,4,2,1,6);case'T':return G(7,2,2,2,2);
case'U':return G(5,5,5,5,7);case'V':return G(5,5,5,5,2);case'W':return G(5,5,7,7,5);case'X':return G(5,5,2,5,5);
case'Y':return G(5,5,2,2,2);case'Z':return G(7,1,2,4,7);case'0':return G(7,5,5,5,7);case'1':return G(2,6,2,2,7);
case'2':return G(6,1,7,4,7);case'3':return G(6,1,3,1,6);case'4':return G(5,5,7,1,1);case'5':return G(7,4,6,1,6);
case'6':return G(3,4,6,5,2);case'7':return G(7,1,2,2,2);case'8':return G(2,5,2,5,2);case'9':return G(2,5,3,1,6);
case':':return G(0,2,0,2,0);case'-':return G(0,0,7,0,0);case'/':return G(1,1,2,4,4);case'.':return G(0,0,0,0,2);
case'!':return G(2,2,2,0,2);case'<':return G(1,2,4,2,1);case'>':return G(4,2,1,2,4);case'+':return G(0,2,7,2,0);default:return 0;}}
static int text_width(const char*s,int z){return(int)strlen(s)*4*z-z;}
static void text(VMUINT16*d,int sw,int sh,int x,int y,const char*s,VMUINT16 c,int z){int i,r,k;VMUINT16 b;
    for(i=0;s[i];++i){char q=s[i]>='a'&&s[i]<='z'?(char)(s[i]-32):s[i];b=glyph(q);for(r=0;r<5;++r)for(k=0;k<3;++k)
        if(b&(1u<<(14-r*3-k)))fill_rect(d,sw,sh,x+k*z,y+r*z,z,z,c);x+=4*z;}}
static void text_center(VMUINT16*d,int sw,int sh,int y,const char*s,VMUINT16 c,int z){text(d,sw,sh,(sw-text_width(s,z))/2,y,s,c,z);}

static void blit_raw(VMUINT16*d,int sw,int sh,const VMUINT8*data,int x,int y,int flip){int w,h,o,xx,yy;const VMUINT16*p;const VMUINT8*m;
    if(!data)return;w=data[0]|(data[1]<<8);h=data[2]|(data[3]<<8);o=data[4];p=(const VMUINT16*)(data+8);m=data+8+w*h*2;
    for(yy=0;yy<h;++yy)for(xx=0;xx<w;++xx){int sx=flip?w-1-xx:xx,n=yy*w+sx,dx=x+xx,dy=y+yy;
        if(dx>=0&&dx<sw&&dy>=0&&dy<sh&&(o||(m[n>>3]&(0x80>>(n&7)))))d[dy*sw+dx]=p[n];}}
static void load_assets(void){VMINT n;g_bg=vm_load_resource("battlefield.raw",&n);g_player=vm_load_resource("player_archer.raw",&n);
    g_enemy=vm_load_resource("enemy_archer.raw",&n);g_logo=vm_load_resource("logo.raw",&n);
    g_sfx_bow=vm_load_resource("bow.wav",&g_sfx_bow_size);g_sfx_hit=vm_load_resource("hit.wav",&g_sfx_hit_size);g_sfx_victory=vm_load_resource("victory.wav",&g_sfx_victory_size);}
static void free_assets(void){VMUINT8**a[]={&g_bg,&g_player,&g_enemy,&g_logo,&g_sfx_bow,&g_sfx_hit,&g_sfx_victory};int i;for(i=0;i<7;++i)if(*a[i]){vm_free(*a[i]);*a[i]=0;}}
static void play_sfx(VMUINT8*d,VMINT n){if(d&&n>44)vm_audio_play_bytes_no_block(d,(VMUINT)n,VM_FORMAT_WAV,VM_DEVICE_LOUDSPEAKER,0);else vm_audio_play_beep();}

static void new_round(void){int i;g_player_hp=g_enemy_hp=100;g_ghost_player=g_ghost_enemy=100;g_round=g_player_rounds+g_enemy_rounds+1;g_wind=(int)(rnd()%13u)-6;g_angle=45;g_power=58;g_charging=0;g_pred_angle=g_pred_power=-1;
    g_arrow.active=0;g_trail_count=0;g_camera_x=WORLD_PLAYER_X;g_camera_y=0;g_state=ST_PLAYER_AIM;g_state_ticks=0;
    for(i=0;i<MAX_PARTS;++i)g_parts[i].life=0;g_shake=0;g_flash_all=0;g_flash_player=g_flash_enemy=0;
    g_pred_x=simulate_landing(0,g_angle,g_power);g_pred_hy=predict_hit_height(g_angle,g_power);}
static void new_match(void){g_player_rounds=g_enemy_rounds=g_ai_misses=0;g_charging=0;new_round();}
static void finish_round(int won){if(won)++g_player_rounds;else++g_enemy_rounds;play_sfx(g_sfx_victory,g_sfx_victory_size);
    g_state=(g_player_rounds>=2||g_enemy_rounds>=2)?ST_MATCH_RESULT:ST_ROUND_RESULT;g_state_ticks=0;g_camera_x=(WORLD_PLAYER_X+WORLD_ENEMY_X)*.5f;g_camera_y=0;}
static void launch_arrow(int owner,int angle,int power){float r=(float)angle*PI/180.0f,dir=owner?-1.0f:1.0f,s=(float)power*1.34f;
    g_arrow.owner=owner;g_arrow.active=1;g_arrow.full=(owner==0&&power>=POWER_FULL);g_arrow.x=owner?WORLD_ENEMY_X-23:WORLD_PLAYER_X+23;g_arrow.y=36;g_arrow.vx=cosf(r)*s*dir;g_arrow.vy=sinf(r)*s;
    g_trail_count=0;g_state=ST_ARROW;g_state_ticks=0;play_sfx(g_sfx_bow,g_sfx_bow_size);}
static float simulate_landing(int owner,int angle,int power){float r=(float)angle*PI/180,dir=owner?-1.0f:1.0f,x=owner?WORLD_ENEMY_X-23:WORLD_PLAYER_X+23,y=36;
    float vx=cosf(r)*power*1.34f*dir,vy=sinf(r)*power*1.34f;int i;for(i=0;i<500&&y>=0;++i){vx+=g_wind*.033f;x+=vx*.033f;vy-=18*.033f;y+=vy*.033f;}return x;}
/* Height at which the player's arrow crosses the boss's x, or -1 if it never reaches. */
static float predict_hit_height(int angle,int power){float r=(float)angle*PI/180,x=WORLD_PLAYER_X+23,y=36,vx=cosf(r)*power*1.34f,vy=sinf(r)*power*1.34f,ox,oy;int i;
    for(i=0;i<500;++i){ox=x;oy=y;vx+=g_wind*.033f;x+=vx*.033f;vy-=18*.033f;y+=vy*.033f;
        if(x>=WORLD_ENEMY_X&&ox<WORLD_ENEMY_X){float t=(WORLD_ENEMY_X-ox)/(x-ox);return oy+(y-oy)*t;}
        if(y<0)break;}return -1;}
static void ai_fire(void){int a,p,ba=45,bp=55,span=g_difficulty==0?52:(g_difficulty==1?25:9);float error,target,best=100000;
    span=clampi(span-g_ai_misses*(g_difficulty==0?5:3),5,60);error=(float)((int)(rnd()%(VMUINT32)(span*2+1))-span);target=WORLD_PLAYER_X+error;
    for(a=28;a<=68;a+=2)for(p=34;p<=88;p+=2){float m=simulate_landing(1,a,p)-target;if(m<0)m=-m;if(m<best){best=m;ba=a;bp=p;}}launch_arrow(1,ba,bp);}
static void arrow_landed(int hit,int head){g_arrow.active=0;g_last_headshot=head;g_last_full=(g_arrow.owner==0&&g_arrow.full&&hit);
    g_last_damage=head?(g_last_full?65:50):(hit?(g_last_full?45:30):0);g_message_ticks=45;
    burst(g_arrow.owner,hit,head);
    if(hit){g_shake=head?10:6;g_flash_all=2;
        if(g_arrow.owner==0){g_flash_enemy=8;g_enemy_hp=clampi(g_enemy_hp-g_last_damage,0,100);}else{g_flash_player=8;g_player_hp=clampi(g_player_hp-g_last_damage,0,100);g_ai_misses=0;}play_sfx(g_sfx_hit,g_sfx_hit_size);}
    else if(g_arrow.owner==1)++g_ai_misses;if(g_enemy_hp<=0)finish_round(1);else if(g_player_hp<=0)finish_round(0);
    else if(g_arrow.owner==0){g_state=ST_AI_THINK;g_state_ticks=0;}else{g_state=ST_PLAYER_AIM;g_state_ticks=0;}}
static void update_arrow(void){float ox=g_arrow.x,oy=g_arrow.y,target=g_arrow.owner==0?WORLD_ENEMY_X:WORLD_PLAYER_X,crossed,hy=-1;int hit=0,head=0,i;if(!g_arrow.active)return;
    if(g_trail_count<MAX_TRAIL)++g_trail_count;for(i=g_trail_count-1;i>0;--i){g_trail_x[i]=g_trail_x[i-1];g_trail_y[i]=g_trail_y[i-1];}g_trail_x[0]=g_arrow.x;g_trail_y[0]=g_arrow.y;
    g_arrow.vx+=g_wind*.033f;g_arrow.x+=g_arrow.vx*.033f;g_arrow.vy-=18*.033f;g_arrow.y+=g_arrow.vy*.033f;crossed=(target-ox)*(target-g_arrow.x);
    if(crossed<=0&&g_arrow.x!=ox){float t=(target-ox)/(g_arrow.x-ox);hy=oy+(g_arrow.y-oy)*t;if(hy>=7&&hy<=51){hit=1;head=hy>=36;}}
    g_camera_x+=(g_arrow.x-g_camera_x)*.20f;g_camera_x=clampf(g_camera_x,120,WORLD_ENEMY_X-120);g_camera_y+=(clampf(g_arrow.y-120,0,180)-g_camera_y)*.18f;
    if(hit||g_arrow.y<=0||g_arrow.x<-30||g_arrow.x>WORLD_ENEMY_X+40)arrow_landed(hit,head);}
static void update(void){int i;if(g_paused)return;++g_tick;++g_state_ticks;if(g_message_ticks>0)--g_message_ticks;
    {int cw=g_wind;for(i=0;i<3;++i){g_cloud_x[i]+=(2+cw)*.012f;if(g_cloud_x[i]>560)g_cloud_x[i]-=560;if(g_cloud_x[i]<-20)g_cloud_x[i]+=560;}}
    for(i=0;i<MAX_PARTS;++i){Particle*p=&g_parts[i];if(p->life<=0)continue;p->vy-=220*.033f;p->x+=p->vx*.033f;p->y+=p->vy*.033f;if(p->y<0){p->y=0;p->vy=0;p->vx*=.6f;}--p->life;}
    if(g_shake>0)--g_shake;if(g_flash_all>0)--g_flash_all;if(g_flash_player>0)--g_flash_player;if(g_flash_enemy>0)--g_flash_enemy;
    if(g_ghost_player>g_player_hp)g_ghost_player-=(g_ghost_player-g_player_hp+7)/8;if(g_ghost_enemy>g_enemy_hp)g_ghost_enemy-=(g_ghost_enemy-g_enemy_hp+7)/8;
    if(g_state==ST_ARROW)update_arrow();
    else if(g_state==ST_AI_THINK){g_camera_x+=(WORLD_ENEMY_X-g_camera_x)*.13f;if(g_state_ticks>28)ai_fire();}
    else if(g_state==ST_PLAYER_AIM){g_camera_x+=(WORLD_PLAYER_X-g_camera_x)*.18f;g_camera_y*=.8f;
        if(g_charging){int step=g_charge_ticks<25?1:2;g_power+=g_charge_dir*step;g_charge_ticks++;
            if(g_power>=POWER_MAX){g_power=POWER_MAX;g_charge_dir=-1;}if(g_power<=POWER_MIN){g_power=POWER_MIN;g_charge_dir=1;}}
        if(g_pred_angle!=g_angle||g_pred_power!=g_power){g_pred_angle=g_angle;g_pred_power=g_power;
            g_pred_x=simulate_landing(0,g_angle,g_power);g_pred_hy=predict_hit_height(g_angle,g_power);}}}

static void draw_world(VMUINT16*d,int sw,int sh){int ground=sh-54+(int)g_camera_y,x,sp,se,bob=(g_tick/8)&1,shx=0,shy=0,i;float cam;
    if(g_shake>0){shx=(int)(vrnd()%9u)-4;shy=(int)(vrnd()%9u)-4;shx=shx*g_shake/10;shy=shy*g_shake/10;}
    cam=g_camera_x-shx;
    if(g_bg)blit_raw(d,sw,sh,g_bg,0,0,0);else fill_rect(d,sw,sh,0,0,sw,sh,C_SKY);
    /* sun with glow ring */
    {int sx=(int)(430-cam*.10f+sw*.5f),sy=ground-215;fill_rect(d,sw,sh,sx-8,sy-8,16,16,RGB565(60,72,96));fill_rect(d,sw,sh,sx-6,sy-6,12,12,RGB565(212,178,102));fill_rect(d,sw,sh,sx-4,sy-4,8,8,C_GOLD);}
    /* drifting clouds, parallax 0.15 */
    for(i=0;i<3;++i){int cx=(int)(g_cloud_x[i]-cam*.15f+sw*.5f),cy=ground-235+((i*29)&31),cw=26+(i*11)%14;
        if(cx>-40&&cx<sw+40){fill_rect(d,sw,sh,cx,cy,cw,4,RGB565(52,66,90));fill_rect(d,sw,sh,cx+4,cy-3,cw-8,3,RGB565(44,56,78));}}
    /* distant castle, parallax 0.28 */
    x=(int)(330-cam*.28f+sw*.5f);fill_rect(d,sw,sh,x,ground-104,42,58,RGB565(32,39,51));fill_rect(d,sw,sh,x+7,ground-124,12,25,RGB565(32,39,51));
    fill_rect(d,sw,sh,x+27,ground-119,10,20,RGB565(32,39,51));fill_rect(d,sw,sh,x+4,ground-112,8,10,RGB565(24,29,39));fill_rect(d,sw,sh,x+30,ground-60,8,34,RGB565(24,29,39));
    /* ground + tree line, parallax 0.62 */
    fill_rect(d,sw,sh,0,ground+shy,sw,sh-ground-shy,RGB565(59,74,43));fill_rect(d,sw,sh,0,ground+shy,sw,4,RGB565(126,145,71));
    for(x=-60;x<600;x+=34){int sx=(int)(x-cam*.62f+sw*.5f);line(d,sw,sh,sx,ground+shy,sx+6,ground+shy-18-(x&7),RGB565(30,53,44));line(d,sw,sh,sx+12,ground+shy,sx+6,ground+shy-18-(x&7),RGB565(30,53,44));}
    /* wind-blown leaves */
    for(i=0;i<10;++i){int ph=(int)((g_tick*3+i*61)%240),lx=(int)((ph*3+i*57)%(sw+40))-20,ly=(int)(ground+shy-20-((ph*7+i*37)%150));int ldx=(int)(sinf((g_tick*.06f+i)*3)*4)+g_wind*2;
        fill_rect(d,sw,sh,lx+ldx,ly+((g_tick/3+i)&7),2,2,(i&1)?RGB565(96,124,62):RGB565(116,142,74));}
    sp=(int)(WORLD_PLAYER_X-cam+sw*.5f)-20;se=(int)(WORLD_ENEMY_X-cam+sw*.5f)-20;
    /* shadows under archers */
    fill_rect(d,sw,sh,sp+9,ground+shy-2,22,2,RGB565(36,48,28));fill_rect(d,sw,sh,se+9,ground+shy-2,22,2,RGB565(36,48,28));
    if(g_player_hp>0&&!(g_flash_player&&(g_tick&1)))blit_raw(d,sw,sh,g_player,sp,ground+shy-53-bob,0);
    if(g_enemy_hp>0&&!(g_flash_enemy&&(g_tick&1)))blit_raw(d,sw,sh,g_enemy,se,ground+shy-53-bob,1);
    /* aim guide + landing marker */
    if(g_state==ST_PLAYER_AIM){float r=(float)g_angle*PI/180;int i2,mx;for(i2=1;i2<=4;++i2){int px=(int)(WORLD_PLAYER_X+18+cosf(r)*i2*9-cam+sw*.5f),py=ground+shy-36-(int)(sinf(r)*i2*9);fill_rect(d,sw,sh,px,py,2,2,C_GOLD);}
        mx=(int)(g_pred_x-cam+sw*.5f);
        if(g_pred_hy>=7&&g_pred_hy<=51){int hy2=ground+shy-(int)g_pred_hy,ok=g_pred_hy>=36;
            line(d,sw,sh,mx-6,hy2,mx+6,hy2,ok?C_PLAYER:C_CREAM);line(d,sw,sh,mx,hy2-6,mx,hy2+6,ok?C_PLAYER:C_CREAM);
            frame_rect(d,sw,sh,mx-8,hy2-8,17,17,ok?C_PLAYER:C_CREAM);
            text_center(d,sw,sh,78,ok?"LOCKED HEAD":"LOCKED BODY",ok?C_PLAYER:C_CREAM,1);}
        else if((g_tick/3)&1){fill_rect(d,sw,sh,mx-2,ground+shy-3,5,3,C_GOLD);fill_rect(d,sw,sh,mx-1,ground+shy-7,3,4,C_GOLD);}}
    /* arrow flight: two-tone head, trail fades */
    if(g_state==ST_ARROW&&g_arrow.active){int ax=(int)(g_arrow.x-cam+sw*.5f),ay=ground+shy-(int)g_arrow.y;VMUINT16 tip=g_arrow.owner==0?C_GOLD:C_CREAM;
        for(i=g_trail_count-1;i>=0;--i){int tx=(int)(g_trail_x[i]-cam+sw*.5f),ty=ground+shy-(int)g_trail_y[i];fill_rect(d,sw,sh,tx,ty,1,1,i<4?tip:C_BRONZE);}
        line(d,sw,sh,ax-(g_arrow.vx>0?8:-8),ay+(int)(g_arrow.vy/14),ax,ay,tip);fill_rect(d,sw,sh,ax-1,ay-1,3,3,tip);}
    /* impact particles */
    for(i=0;i<MAX_PARTS;++i){Particle*p=&g_parts[i];if(p->life<=0)continue;{int px=(int)(p->x-cam+sw*.5f),py=ground+shy-(int)p->y;fill_rect(d,sw,sh,px,py,p->life>6?2:1,p->life>6?2:1,p->col);}}
    /* hit flash: sparse white sparkles over the scene */
    if(g_flash_all>0){int n;for(n=0;n<40;++n){int px=(int)(vrnd()%(VMUINT32)sw),py=(int)(vrnd()%(VMUINT32)sh);d[py*sw+px]=RGB565(255,244,214);}}}
static void health_bar(VMUINT16*d,int sw,int sh,int x,int y,int hp,int ghost,VMUINT16 c){fill_rect(d,sw,sh,x,y,86,9,C_INK);frame_rect(d,sw,sh,x,y,86,9,C_CREAM);
    if(ghost>hp)fill_rect(d,sw,sh,x+2,y+2,(82*ghost)/100,5,RGB565(235,235,235));
    fill_rect(d,sw,sh,x+2,y+2,(82*hp)/100,5,c);if(hp>0&&(82*hp)/100<82)fill_rect(d,sw,sh,x+2+(82*hp)/100,y+2,1,5,RGB565(255,255,255));}
/* Tactical strip under the HUD: world 0..540 mapped to the band; shows both archers,
   the predicted landing marker (wind included), camera frame and a wind chevron row. */
static void draw_minimap(VMUINT16*d,int sw,int sh){static const int MW=540;int x0=4,x1=sw-4,mw=x1-x0,my=43,i,mx,ex,px,dx;char t[16];
    fill_rect(d,sw,sh,0,37,sw,12,RGB565(9,22,32));fill_rect(d,sw,sh,x0,my-4,mw,9,C_INK);frame_rect(d,sw,sh,x0,my-4,mw,9,RGB565(60,80,92));
    for(i=0;i<=MW;i+=100){int tx=x0+i*mw/MW;fill_rect(d,sw,sh,tx,my-4,1,2,RGB565(60,80,92));fill_rect(d,sw,sh,tx,my+3,1,2,RGB565(60,80,92));}
    ex=x0+WORLD_ENEMY_X*mw/MW;px=x0+WORLD_PLAYER_X*mw/MW;
    fill_rect(d,sw,sh,ex-3,my-2,7,5,C_ENEMY);fill_rect(d,sw,sh,px-3,my-2,7,5,C_PLAYER);
    if(g_arrow.active){int ax=x0+(int)(g_arrow.x*mw/MW);fill_rect(d,sw,sh,ax-1,my-2,3,5,C_GOLD);}
    else if(g_state==ST_PLAYER_AIM){mx=x0+(int)(g_pred_x*mw/MW);
        if(mx>=x0&&mx<x1){fill_rect(d,sw,sh,mx-1,my-3,3,7,g_pred_hy>=7&&g_pred_hy<=51?(g_pred_hy>=36?C_PLAYER:C_CREAM):C_GOLD);}}
    {int cx=x0+(int)(g_camera_x*mw/MW),cw=sw*mw/MW;fill_rect(d,sw,sh,cx-cw/2,my-4,cw,1,RGB565(90,110,124));fill_rect(d,sw,sh,cx-cw/2,my+4,cw,1,RGB565(90,110,124));}
    if(g_wind){int cw2=g_wind<0?-g_wind:g_wind,sx=sw/2-(g_wind<0?5:cw2*5-3),sy=my-1,dir=g_wind<0?-1:1;
        for(i=0;i<cw2;++i){int bx=sx+dir*i*10;line(d,sw,sh,bx,sy,bx+dir*4,sy-2,C_TEAL);line(d,sw,sh,bx+dir*4,sy-2,bx+dir*8,sy,C_TEAL);line(d,sw,sh,bx+dir*4,sy-2,bx+dir*4,sy+1,C_TEAL);}}
    if(g_state==ST_PLAYER_AIM){dx=(int)g_pred_x-(int)WORLD_ENEMY_X;snprintf(t,sizeof(t),"%s%d",dx<0?"L":(dx>0?"R+":"0"),dx<0?-dx:dx);
        {int tw=text_width(t,1);fill_rect(d,sw,sh,(sw-tw)/2-2,50,tw+4,8,RGB565(9,22,32));text_center(d,sw,sh,52,t,dx==0?C_GOLD:C_CREAM,1);}}}
static void draw_hud(VMUINT16*d,int sw,int sh){char b[32];int wx;fill_rect(d,sw,sh,0,0,sw,36,RGB565(13,31,42));fill_rect(d,sw,sh,0,35,sw,2,C_BRONZE);
    text(d,sw,sh,5,4,"YOU",C_CREAM,1);text(d,sw,sh,sw-30,4,"CPU",C_CREAM,1);health_bar(d,sw,sh,5,13,g_player_hp,g_ghost_player,C_PLAYER);health_bar(d,sw,sh,sw-91,13,g_enemy_hp,g_ghost_enemy,C_ENEMY);
    snprintf(b,sizeof(b),"%d-%d",g_player_rounds,g_enemy_rounds);text_center(d,sw,sh,14,b,C_GOLD,1);snprintf(b,sizeof(b),"WIND %c%d",g_wind<0?'<':'>',g_wind<0?-g_wind:g_wind);text_center(d,sw,sh,27,b,C_CREAM,1);wx=sw/2+g_wind*4;line(d,sw,sh,sw/2,33,wx,33,C_TEAL);
    draw_minimap(d,sw,sh);
    if(g_state==ST_PLAYER_AIM){int bx,bw,bl,cur,i;VMUINT16 bc;char b2[32];fill_rect(d,sw,sh,0,sh-42,sw,42,RGB565(13,31,42));
        snprintf(b,sizeof(b),"ANGLE %d",g_angle);text(d,sw,sh,8,sh-35,b,C_GOLD,1);snprintf(b,sizeof(b),"P %d",g_power);text(d,sw,sh,sw-34,sh-35,b,g_power>=POWER_FULL?C_PLAYER:C_GOLD,1);
        bx=62;bw=sw-104;fill_rect(d,sw,sh,bx,sh-31,bw,7,C_INK);frame_rect(d,sw,sh,bx,sh-31,bw,7,C_CREAM);
        bl=(bw-6)*(POWER_FULL-POWER_MIN)/(POWER_MAX-POWER_MIN)+3;fill_rect(d,sw,sh,bx+bl,sh-29,bw-bl-4,3,C_ENEMY);
        fill_rect(d,sw,sh,bx+3,sh-29,bl-4,3,C_BRONZE);
        if(g_charging&&(g_tick/2)&1){cur=bx+3+(bw-6)*(g_power-POWER_MIN)/(POWER_MAX-POWER_MIN);fill_rect(d,sw,sh,cur-1,sh-32,3,9,g_power>=POWER_FULL?C_PLAYER:C_CREAM);}
        for(i=0;i<7;++i){cur=bx+(bw-1)*i/6;fill_rect(d,sw,sh,cur,sh-22,1,2,RGB565(60,80,92));}
        snprintf(b2,sizeof(b2),g_power>=POWER_FULL?"FULL DRAW":(g_charging?"CHARGING":"HOLD A - CHARGE"));
        text_center(d,sw,sh,sh-19,b2,g_power>=POWER_FULL?C_PLAYER:C_CREAM,1);}
    else if(g_state==ST_AI_THINK)text_center(d,sw,sh,sh-18,"IRON STAG IS AIMING",C_CREAM,1);
    if(g_message_ticks>0){if(g_last_damage){snprintf(b,sizeof(b),g_last_headshot?"HEADSHOT -%d":(g_last_full?"FULL DRAW -%d":"HIT -%d"),g_last_damage);text_center(d,sw,sh,62,b,g_last_headshot?C_GOLD:(g_last_full?C_PLAYER:C_CREAM),2);}else text_center(d,sw,sh,62,"MISS",C_CREAM,2);}}
static void panel(VMUINT16*d,int sw,int sh,int y,int h){fill_rect(d,sw,sh,12,y,sw-24,h,RGB565(15,35,48));frame_rect(d,sw,sh,12,y,sw-24,h,C_BRONZE);}
static void draw_title(VMUINT16*d,int sw,int sh){char diff[24];int i;if(g_bg)blit_raw(d,sw,sh,g_bg,0,0,0);else fill_rect(d,sw,sh,0,0,sw,sh,C_SKY);
    for(i=0;i<3;++i){int cx=(int)g_cloud_x[i]-40,cy=40+((i*23)&15);if(cx>-40&&cx<sw){fill_rect(d,sw,sh,cx,cy,30+i*8,4,RGB565(52,66,90));fill_rect(d,sw,sh,cx+5,cy-3,20+i*8,3,RGB565(44,56,78));}}
    if(g_logo)blit_raw(d,sw,sh,g_logo,(sw-176)/2,38,0);
    text_center(d,sw,sh,116,"ARROWFALL",C_GOLD,3);text_center(d,sw,sh,136,"DUEL",C_CREAM,3);panel(d,sw,sh,184,68);strcpy(diff,g_difficulty==0?"< EASY >":(g_difficulty==1?"< NORMAL >":"< HARD >"));text_center(d,sw,sh,197,"DIFFICULTY",C_CREAM,1);
    {int tw=text_width(diff,2);frame_rect(d,sw,sh,(sw-tw)/2-6,209,tw+12,15,(g_tick/5&1)?C_GOLD:C_BRONZE);text_center(d,sw,sh,214,diff,C_GOLD,2);}
    text_center(d,sw,sh,268,(g_tick/6&1)?"A START":"",C_CREAM,2);text_center(d,sw,sh,290,"UP HELP",C_CREAM,1);text_center(d,sw,sh,sh-16,"BEST OF THREE",C_BRONZE,1);}
static void draw_help(VMUINT16*d,int sw,int sh){fill_rect(d,sw,sh,0,0,sw,sh,RGB565(18,31,45));text_center(d,sw,sh,22,"HOW TO PLAY",C_GOLD,2);panel(d,sw,sh,58,205);
    text(d,sw,sh,28,76,"UP DOWN ANGLE",C_CREAM,2);text(d,sw,sh,28,98,"HOLD A TO CHARGE",C_CREAM,2);text(d,sw,sh,28,120,"RELEASE A FIRE",C_CREAM,2);text(d,sw,sh,28,142,"TOUCH HOLD CHARGE",C_CREAM,2);text(d,sw,sh,28,164,"DRAG UP DOWN ANGLE",C_CREAM,2);text(d,sw,sh,28,186,"START  PAUSE",C_CREAM,2);text(d,sw,sh,28,210,"BODY 30 DAMAGE",C_PLAYER,1);text(d,sw,sh,28,224,"FULL DRAW 45 65",C_PLAYER,1);text(d,sw,sh,28,246,"HEAD 50 65 DAMAGE",C_ENEMY,1);text_center(d,sw,sh,286,"A PLAY  BACK TITLE",C_CREAM,1);}
static void draw_results(VMUINT16*d,int sw,int sh){int won=g_player_hp>0;draw_world(d,sw,sh);fill_rect(d,sw,sh,18,78,sw-36,158,RGB565(13,31,42));frame_rect(d,sw,sh,18,78,sw-36,158,C_BRONZE);text_center(d,sw,sh,98,g_state==ST_MATCH_RESULT?"MATCH RESULT":"ROUND RESULT",C_GOLD,2);text_center(d,sw,sh,137,won?"VICTORY":"DEFEAT",won?C_PLAYER:C_ENEMY,3);text_center(d,sw,sh,186,g_state==ST_MATCH_RESULT?"A REMATCH":"A NEXT ROUND",C_CREAM,2);text_center(d,sw,sh,216,"BACK TITLE",C_CREAM,1);}
static void draw_pause(VMUINT16*d,int sw,int sh){fill_rect(d,sw,sh,32,sh/2-50,sw-64,100,RGB565(12,27,38));frame_rect(d,sw,sh,32,sh/2-50,sw-64,100,C_GOLD);text_center(d,sw,sh,sh/2-29,"PAUSED",C_GOLD,3);text_center(d,sw,sh,sh/2+14,"START RESUME",C_CREAM,1);}
static void draw(void){VMUINT16*d=fb();int sw,sh;if(!d||g_layer<0)return;sw=vm_graphic_get_screen_width();sh=vm_graphic_get_screen_height();if(g_state==ST_TITLE)draw_title(d,sw,sh);else if(g_state==ST_HELP)draw_help(d,sw,sh);else if(g_state==ST_ROUND_RESULT||g_state==ST_MATCH_RESULT)draw_results(d,sw,sh);else{draw_world(d,sw,sh);draw_hud(d,sw,sh);}if(g_paused)draw_pause(d,sw,sh);vm_graphic_flush_layer(&g_layer,1);}
static void timer_tick(VMINT tid){(void)tid;update();draw();}
static int is_action(int k){return k==VM_KEY_OK||k==VM_KEY_A||k==VM_KEY_NUM5;}static int is_start(int k){return k==VM_KEY_LEFT_SOFTKEY||k==VM_KEY_NUM0;}
static void key_down(int k){if(is_start(k)&&g_state!=ST_TITLE&&g_state!=ST_HELP&&g_state!=ST_ROUND_RESULT&&g_state!=ST_MATCH_RESULT){g_paused=!g_paused;g_charging=0;draw();return;}if(g_paused)return;
    if(g_state==ST_TITLE){if(k==VM_KEY_LEFT||k==VM_KEY_DOWN)g_difficulty=(g_difficulty+2)%3;else if(k==VM_KEY_RIGHT)g_difficulty=(g_difficulty+1)%3;else if(k==VM_KEY_UP)g_state=ST_HELP;else if(is_action(k))new_match();}
    else if(g_state==ST_HELP){if(is_action(k))new_match();else if(k==VM_KEY_RIGHT_SOFTKEY||k==VM_KEY_BACK)g_state=ST_TITLE;}
    else if(g_state==ST_PLAYER_AIM){if(k==VM_KEY_UP)g_angle=clampi(g_angle+1,15,78);else if(k==VM_KEY_DOWN)g_angle=clampi(g_angle-1,15,78);else if(k==VM_KEY_RIGHT)g_power=clampi(g_power+1,POWER_MIN,POWER_MAX);else if(k==VM_KEY_LEFT)g_power=clampi(g_power-1,POWER_MIN,POWER_MAX);
        else if(is_action(k)&&!g_charging){g_charging=1;g_charge_dir=1;g_charge_ticks=0;}}
    else if(g_state==ST_ROUND_RESULT&&is_action(k))new_round();else if(g_state==ST_MATCH_RESULT&&is_action(k))new_match();if((g_state==ST_ROUND_RESULT||g_state==ST_MATCH_RESULT)&&(k==VM_KEY_RIGHT_SOFTKEY||k==VM_KEY_BACK))g_state=ST_TITLE;draw();}
static void key_up(int k){if(is_action(k)&&g_charging&&g_state==ST_PLAYER_AIM&&!g_paused){g_charging=0;launch_arrow(0,g_angle,g_power);draw();}}
void handle_keyevt(VMINT e,VMINT k){if(e==VM_KEY_EVENT_DOWN||e==VM_KEY_EVENT_REPEAT)key_down(k);if(e==VM_KEY_EVENT_UP)key_up(k);if(e==VM_KEY_EVENT_DOWN&&k==VM_KEY_CLEAR&&g_state==ST_TITLE)vm_exit_app();}
void handle_penevt(VMINT e,VMINT x,VMINT y){int sw=vm_graphic_get_screen_width();
    if(g_state==ST_TITLE){if(e!=VM_PEN_EVENT_TAP)return;if(y<184)g_state=ST_HELP;else if(y>256)new_match();else if(x<sw/3)g_difficulty=(g_difficulty+2)%3;else if(x>sw*2/3)g_difficulty=(g_difficulty+1)%3;else new_match();draw();}
    else if(g_state==ST_HELP){if(e!=VM_PEN_EVENT_TAP)return;if(x<sw/3)g_state=ST_TITLE;else new_match();draw();}
    else if(g_state==ST_ROUND_RESULT||g_state==ST_MATCH_RESULT){if(e!=VM_PEN_EVENT_TAP)return;if(x<sw/4)g_state=ST_TITLE;else if(g_state==ST_ROUND_RESULT)new_round();else new_match();draw();}
    else if(g_state==ST_PLAYER_AIM&&!g_paused){
        if(e==VM_PEN_EVENT_TAP){g_charging=1;g_charge_dir=1;g_charge_ticks=0;g_pen_y0=y;g_angle0=g_angle;}
        else if(e==VM_PEN_EVENT_MOVE&&g_charging)g_angle=clampi(g_angle0-(y-g_pen_y0)/4,15,78);
        else if(e==VM_PEN_EVENT_RELEASE&&g_charging){g_charging=0;launch_arrow(0,g_angle,g_power);draw();}
        else if(e==VM_PEN_EVENT_ABORT&&g_charging)g_charging=0;}}
static void start(void){if(g_layer<0){g_layer=vm_graphic_create_layer(0,0,vm_graphic_get_screen_width(),vm_graphic_get_screen_height(),-1);load_assets();}if(g_timer<0)g_timer=vm_create_timer(33,timer_tick);draw();}
static void stop(void){if(g_timer>=0){vm_delete_timer(g_timer);g_timer=-1;}vm_audio_stop_all();free_assets();if(g_layer>=0){vm_graphic_delete_layer(g_layer);g_layer=-1;}}
void handle_sysevt(VMINT m,VMINT p){(void)p;if(m==VM_MSG_CREATE||m==VM_MSG_ACTIVE)start();else if(m==VM_MSG_PAINT)draw();else if(m==VM_MSG_INACTIVE||m==VM_MSG_QUIT){stop();if(m==VM_MSG_QUIT)vm_exit_app();}}
void vm_main(void){vm_reg_sysevt_callback(handle_sysevt);vm_reg_keyboard_callback(handle_keyevt);vm_reg_pen_callback(handle_penevt);}
