/* IceNexusMobaDemo - original VXPEngine MOBA-style sample, native 240x320 portrait. */
#include "vmsys.h"
#include "vmio.h"
#include "vmgraph.h"
#include "vmtimer.h"
#include "vmres.h"
#include "vmmm.h"
#include "graphics/VxpRender2D.h"
#include "graphics/VxpCinematic2D.h"
#include "graphics/VxpLight2D.h"
#include "graphics/VxpSpriteFx.h"
#include "graphics/VxpVfx2D.h"
#include "graphics/particles/VxpParticlePool.h"
#include <string.h>
#include <stdio.h>

#define SCREEN_W 240
#define SCREEN_H 320
#define MAX_W SCREEN_W
#define MAX_SCENE_H 240
#define HUD_H 80
#define RGB565(r,g,b) vxpe2d_rgb565((r),(g),(b))

static VMINT g_layer=-1, g_timer=-1, g_tick=0;
static int g_started=0, g_px=72, g_py=176, g_face=1;
static int g_hp=1241, g_mp=517, g_level=6;
static int g_cd[4]={0,0,0,0};
static int g_match_ms=22000;
static int g_flash=0;
static VMUINT16 g_static[MAX_W*MAX_SCENE_H];
static VMUINT16 g_frame[SCREEN_W*SCREEN_H]; /* native portrait framebuffer */
static VxpeParticlePool g_fx;
static VxpeSpriteBatch g_sprite_batch;
static VxpeCinematic2D g_cinematic;
static VxpeLightmap2D g_lightmap;
static VxpeTrail2D g_magic_trail;
static int g_beam_fx=0,g_ring_fx=0,g_burst_fx=0,g_rot_fx=0;
static int g_beam_x0=0,g_beam_y0=0,g_beam_x1=0,g_beam_y1=0;
static VMUINT8 *g_ariya_res=0,*g_nexus_res=0,*g_skills_res=0,*g_floor_res=0;
static VMINT g_ariya_size=0,g_nexus_size=0,g_skills_size=0,g_floor_size=0;
static VxpeSpriteA8 g_ariya_sprite,g_nexus_sprite,g_skills_sprite,g_floor_sprite;
static int g_ariya_ok=0,g_nexus_ok=0,g_skills_ok=0,g_floor_ok=0;
static VMUINT32 g_rng=0xC0FFEE11u;

static VMUINT32 rnd(void){g_rng=g_rng*1664525u+1013904223u;return g_rng;}
static int rr(int a,int b){return b<=a?a:a+(int)(rnd()%(VMUINT32)(b-a+1));}
static int clampi(int v,int a,int b){return v<a?a:(v>b?b:v);}
static VMUINT16* fb(void){return (VMUINT16*)vm_graphic_get_layer_buffer(g_layer);}

static void fill(VMUINT16*d,int sw,int sh,int x,int y,int w,int h,VMUINT16 c){
    vxpe2d_fill_rect((uint16_t*)d,sw,sh,x,y,w,h,c);
}
static void line(VMUINT16*d,int sw,int sh,int x0,int y0,int x1,int y1,VMUINT16 c){
    int dx=x1>x0?x1-x0:x0-x1,sx=x0<x1?1:-1,dy0=y1>y0?y1-y0:y0-y1,dy=-dy0,sy=y0<y1?1:-1,err=dx+dy;
    for(;;){if(x0>=0&&x0<sw&&y0>=0&&y0<sh)d[y0*sw+x0]=c;if(x0==x1&&y0==y1)break;
        {int e2=err<<1;if(e2>=dy){err+=dy;x0+=sx;}if(e2<=dx){err+=dx;y0+=sy;}}}
}
static void frame(VMUINT16*d,int sw,int sh,int x,int y,int w,int h,VMUINT16 c){
    fill(d,sw,sh,x,y,w,1,c);fill(d,sw,sh,x,y+h-1,w,1,c);
    fill(d,sw,sh,x,y,1,h,c);fill(d,sw,sh,x+w-1,y,1,h,c);
}
static void circle(VMUINT16*d,int sw,int sh,int cx,int cy,int r,VMUINT16 c){
    int y;for(y=-r;y<=r;++y){int x=r;while(x>0&&x*x+y*y>r*r)--x;fill(d,sw,sh,cx-x,cy+y,x*2+1,1,c);}
}
static void ellipse(VMUINT16*d,int sw,int sh,int cx,int cy,int rx,int ry,VMUINT16 c){
    int y;for(y=-ry;y<=ry;++y){int yy=y*y, x=rx;while(x>0 && x*x*ry*ry+yy*rx*rx>rx*rx*ry*ry)--x;fill(d,sw,sh,cx-x,cy+y,x*2+1,1,c);}
}
static void diamond(VMUINT16*d,int sw,int sh,int cx,int cy,int rx,int ry,VMUINT16 c,VMUINT16 edge){
    int y;for(y=-ry;y<=ry;++y){int half=rx*(ry-(y<0?-y:y))/ry;fill(d,sw,sh,cx-half,cy+y,half*2+1,1,c);}
    line(d,sw,sh,cx-rx,cy,cx,cy-ry,edge);line(d,sw,sh,cx,cy-ry,cx+rx,cy,edge);
    line(d,sw,sh,cx+rx,cy,cx,cy+ry,edge);line(d,sw,sh,cx,cy+ry,cx-rx,cy,edge);
}

#define G(a,b,c,d,e) ((VMUINT16)(((a)<<12)|((b)<<9)|((c)<<6)|((d)<<3)|(e)))
static VMUINT16 glyph(char c){switch(c){
case'A':return G(2,5,7,5,5);case'B':return G(6,5,6,5,6);case'C':return G(3,4,4,4,3);case'D':return G(6,5,5,5,6);
case'E':return G(7,4,6,4,7);case'F':return G(7,4,6,4,4);case'G':return G(3,4,5,5,3);case'H':return G(5,5,7,5,5);
case'I':return G(7,2,2,2,7);case'J':return G(1,1,1,5,2);case'K':return G(5,5,6,5,5);case'L':return G(4,4,4,4,7);
case'M':return G(5,7,7,5,5);case'N':return G(5,7,7,7,5);case'O':return G(2,5,5,5,2);case'P':return G(6,5,6,4,4);
case'Q':return G(2,5,5,7,3);case'R':return G(6,5,6,5,5);case'S':return G(3,4,2,1,6);case'T':return G(7,2,2,2,2);
case'U':return G(5,5,5,5,7);case'V':return G(5,5,2,5,5);case'W':return G(5,5,7,7,5);case'X':return G(5,5,2,5,5);
case'Y':return G(5,5,2,2,2);case'Z':return G(7,1,2,4,7);case'0':return G(7,5,5,5,7);case'1':return G(2,6,2,2,7);
case'2':return G(6,1,7,4,7);case'3':return G(6,1,3,1,6);case'4':return G(5,5,7,1,1);case'5':return G(7,4,6,1,6);
case'6':return G(3,4,6,5,2);case'7':return G(7,1,2,2,2);case'8':return G(2,5,2,5,2);case'9':return G(2,5,3,1,6);
case':':return G(0,2,0,2,0);case'-':return G(0,0,7,0,0);case'/':return G(1,1,2,4,4);case'.':return G(0,0,0,0,2);
case'+':return G(0,2,7,2,0);default:return 0;}}
static int tw(const char*s,int z){return(int)strlen(s)*4*z-z;}
static void text(VMUINT16*d,int sw,int sh,int x,int y,const char*s,VMUINT16 c,int z){
    int i,r,k;VMUINT16 b;for(i=0;s[i];++i){char q=s[i]>='a'&&s[i]<='z'?(char)(s[i]-32):s[i];b=glyph(q);
    for(r=0;r<5;++r)for(k=0;k<3;++k)if(b&(1u<<(14-r*3-k)))fill(d,sw,sh,x+k*z,y+r*z,z,z,c);x+=4*z;}
}
static void load_sprite_assets(void){
    if(!g_ariya_res)g_ariya_res=vm_load_resource("ariya.vxa8",&g_ariya_size);
    if(!g_nexus_res)g_nexus_res=vm_load_resource("nexus.vxa8",&g_nexus_size);
    if(!g_skills_res)g_skills_res=vm_load_resource("skills.vxa8",&g_skills_size);
    if(!g_floor_res)g_floor_res=vm_load_resource("floor.vxa8",&g_floor_size);
    g_ariya_ok=g_ariya_res&&g_ariya_size>0&&vxpe2d_sprite_a8_from_vxa8(g_ariya_res,(uint32_t)g_ariya_size,&g_ariya_sprite);
    g_nexus_ok=g_nexus_res&&g_nexus_size>0&&vxpe2d_sprite_a8_from_vxa8(g_nexus_res,(uint32_t)g_nexus_size,&g_nexus_sprite);
    g_skills_ok=g_skills_res&&g_skills_size>0&&vxpe2d_sprite_a8_from_vxa8(g_skills_res,(uint32_t)g_skills_size,&g_skills_sprite);
    g_floor_ok=g_floor_res&&g_floor_size>0&&vxpe2d_sprite_a8_from_vxa8(g_floor_res,(uint32_t)g_floor_size,&g_floor_sprite);
}
static void free_sprite_assets(void){
    if(g_ariya_res){vm_free(g_ariya_res);g_ariya_res=0;} if(g_nexus_res){vm_free(g_nexus_res);g_nexus_res=0;}
    if(g_skills_res){vm_free(g_skills_res);g_skills_res=0;} if(g_floor_res){vm_free(g_floor_res);g_floor_res=0;}
    g_ariya_ok=g_nexus_ok=g_skills_ok=g_floor_ok=0;
}

static void build_scene(int play_h){
    int x,y,row,col; VMUINT16 *d=g_static;
    if(play_h>MAX_SCENE_H)play_h=MAX_SCENE_H;
    vxpe2d_gradient_vertical((uint16_t*)d,MAX_W,play_h,0,0,MAX_W,play_h,RGB565(25,45,69),RGB565(51,71,93));
    if(g_floor_ok){
        static uint16_t tiles[16*16];
        int mx,my;
        for(my=0;my<16;++my)for(mx=0;mx<16;++mx){
            int v=(mx*5+my*3+(mx^my))&3;
            if(((mx+my*3)%17)==0)v=3;
            tiles[my*16+mx]=(uint16_t)v;
        }
        vxpe2d_draw_isometric_a8((uint16_t*)d,MAX_W,play_h,&g_floor_sprite,
                                 tiles,16,16,32,16,4,120,-8,0xFFFFu);
    }else{
        for(row=-1;row<22;++row)for(col=-2;col<18;++col){
            x=col*24+((row&1)?12:0); y=row*12+8;
            diamond(d,MAX_W,play_h,x,y,12,6,
                RGB565(54+((row+col)&3)*4,75+((row+col)&3)*4,98+((row+col)&3)*5),
                RGB565(28,47,68));
            line(d,MAX_W,play_h,x,y-5,x+8,y-1,RGB565(92,122,149));
        }
    }
    /* Static Nexus floor illumination: rendered once into the scene cache. */
    vxpe2d_radial_light_fast((uint16_t*)d,MAX_W,play_h,154,90,36,
                             RGB565(30,165,255),36);
    /* snow banks and walls */
    for(x=0;x<MAX_W;x+=48){
        fill(d,MAX_W,play_h,x,0,32,6,RGB565(204,224,238));
        fill(d,MAX_W,play_h,x+8,5,28,3,RGB565(166,197,220));
    }
    fill(d,MAX_W,play_h,0,play_h-18,MAX_W,18,RGB565(33,45,60));
    for(x=0;x<MAX_W;x+=20){
        diamond(d,MAX_W,play_h,x+10,play_h-15,10,4,RGB565(44,61,79),RGB565(25,38,53));
    }
    /* circular rune path around the portrait-layout Nexus */
    for(x=0;x<MAX_W;++x){
        int dx=x-154;
        int yy=(dx*dx)/1450;
        y=178-yy;
        if(y>40&&y<play_h){if(y>=0)d[y*MAX_W+x]=RGB565(49,150,204);if(y+1<play_h)d[(y+1)*MAX_W+x]=RGB565(23,93,145);}
    }
    /* blue banners */
    for(x=22;x<MAX_W;x+=130){
        fill(d,MAX_W,play_h,x,13,3,39,RGB565(87,74,57));
        fill(d,MAX_W,play_h,x+3,18,16,29,RGB565(24,67,130));
        diamond(d,MAX_W,play_h,x+11,31,5,5,RGB565(111,196,233),RGB565(52,111,168));
    }
    /* braziers */
    for(x=40;x<MAX_W;x+=165){
        fill(d,MAX_W,play_h,x-5,37,11,18,RGB565(48,52,62));
        diamond(d,MAX_W,play_h,x,38,8,4,RGB565(105,94,79),RGB565(181,145,81));
        fill(d,MAX_W,play_h,x-2,30,5,8,RGB565(255,152,35));
        fill(d,MAX_W,play_h,x-1,27,3,6,RGB565(255,220,92));
    }
}

static void draw_nexus(VMUINT16*d,int sw,int sh){
    int cx=154,cy=88,pulse=(g_tick/3)&3;
    if(g_nexus_ok){
        VxpeBlit565 op;
        memset(&op,0,sizeof(op));
        op.src.x=0;op.src.y=0;op.src.w=(int16_t)g_nexus_sprite.width;op.src.h=(int16_t)g_nexus_sprite.height;
        op.dst_x=(int16_t)(cx-(int)g_nexus_sprite.width/2);op.dst_y=34;
        op.dst_w=g_nexus_sprite.width;op.dst_h=g_nexus_sprite.height;
        op.tint565=0xFFFFu;op.alpha=255;op.blend=VXPE_BLEND_ALPHA;
        vxpe2d_batch_push(&g_sprite_batch,&g_nexus_sprite,&op,90,0);
        return;
    }
    vxpe2d_radial_light_fast((uint16_t*)d,sw,sh,cx,cy+5,40+pulse,
        RGB565(22,143,255),(uint8_t)(58+pulse*7));
    ellipse(d,sw,sh,cx,cy+21,43,20,RGB565(40,47,59));
    ellipse(d,sw,sh,cx,cy+19,35,16,RGB565(16,94,137));
    ellipse(d,sw,sh,cx,cy+18,29,13,RGB565(19,134,190));
    diamond(d,sw,sh,cx-34,cy+16,6,11,RGB565(107,91,66),RGB565(203,163,95));
    diamond(d,sw,sh,cx+34,cy+16,6,11,RGB565(107,91,66),RGB565(203,163,95));
    diamond(d,sw,sh,cx,cy+34,7,7,RGB565(96,82,64),RGB565(202,162,92));
    diamond(d,sw,sh,cx,cy,7,7,RGB565(95,83,67),RGB565(202,166,102));
    diamond(d,sw,sh,cx,cy-2,15,28,RGB565(35,179,234),RGB565(180,246,255));
    diamond(d,sw,sh,cx-4,cy-4,7,24,RGB565(89,218,246),RGB565(211,255,255));
    line(d,sw,sh,cx,cy-30,cx,cy+23,RGB565(224,255,255));
    line(d,sw,sh,cx-8,cy-8,cx+10,cy-16,RGB565(139,238,255));
    {
        int px[4]={124,184,130,178},py[4]={64,64,118,118},i;
        for(i=0;i<4;++i){
            diamond(d,sw,sh,px[i],py[i],6,8,RGB565(87,77,65),RGB565(193,154,91));
            diamond(d,sw,sh,px[i],py[i]-7,3,6,RGB565(39,185,244),RGB565(183,249,255));
        }
    }
}

static void draw_ariya(VMUINT16*d,int sw,int sh,int x,int y){
    int bob=((g_tick/8)&1),ox=x,oy=y-bob;
    if(g_ariya_ok){
        VxpeBlit565 op;
        memset(&op,0,sizeof(op));
        op.src.x=0;op.src.y=0;op.src.w=(int16_t)g_ariya_sprite.width;op.src.h=(int16_t)g_ariya_sprite.height;
        op.dst_x=(int16_t)(ox-(int)g_ariya_sprite.width/2);op.dst_y=(int16_t)(oy-50);
        op.dst_w=g_ariya_sprite.width;op.dst_h=g_ariya_sprite.height;
        op.tint565=0xFFFFu;op.alpha=255;op.blend=VXPE_BLEND_ALPHA;op.flip_x=g_face<0?1:0;
        ellipse(d,sw,sh,ox,oy+31,22,6,RGB565(13,18,30));
        vxpe2d_batch_push(&g_sprite_batch,&g_ariya_sprite,&op,(int16_t)(120+oy),0);
        return;
    }
    /* shadow */
    ellipse(d,sw,sh,ox,oy+27,20,6,RGB565(18,31,48));
    /* six tails */
    ellipse(d,sw,sh,ox-20,oy+8,13,7,RGB565(236,224,246));
    ellipse(d,sw,sh,ox-24,oy+17,15,7,RGB565(244,226,246));
    ellipse(d,sw,sh,ox-17,oy+25,15,7,RGB565(239,220,244));
    ellipse(d,sw,sh,ox+15,oy+25,14,6,RGB565(239,220,244));
    ellipse(d,sw,sh,ox+22,oy+16,13,6,RGB565(239,220,244));
    ellipse(d,sw,sh,ox+18,oy+7,12,6,RGB565(239,220,244));
    circle(d,sw,sh,ox-32,oy+16,3,RGB565(243,151,207));
    circle(d,sw,sh,ox-28,oy+27,3,RGB565(243,151,207));
    circle(d,sw,sh,ox+29,oy+16,3,RGB565(243,151,207));
    /* legs, robe, body */
    fill(d,sw,sh,ox-6,oy+14,4,17,RGB565(235,205,196));
    fill(d,sw,sh,ox+4,oy+14,4,17,RGB565(235,205,196));
    fill(d,sw,sh,ox-7,oy+26,5,5,RGB565(100,42,77));
    fill(d,sw,sh,ox+4,oy+26,5,5,RGB565(100,42,77));
    diamond(d,sw,sh,ox,oy+12,11,15,RGB565(245,229,239),RGB565(172,58,104));
    diamond(d,sw,sh,ox-5,oy+14,7,12,RGB565(171,47,96),RGB565(227,169,73));
    /* head/hair */
    circle(d,sw,sh,ox,oy-4,10,RGB565(242,233,246));
    diamond(d,sw,sh,ox-5,oy-13,4,8,RGB565(244,234,247),RGB565(192,146,200));
    diamond(d,sw,sh,ox+6,oy-13,4,8,RGB565(244,234,247),RGB565(192,146,200));
    fill(d,sw,sh,ox-5,oy-5,2,2,RGB565(142,48,99));
    fill(d,sw,sh,ox+4,oy-5,2,2,RGB565(142,48,99));
    /* arm + magic orb */
    line(d,sw,sh,ox+8,oy+8,ox+17,oy+3,RGB565(235,205,196));
    circle(d,sw,sh,ox+22,oy,6,RGB565(74,211,255));
    circle(d,sw,sh,ox+22,oy,3,RGB565(218,255,255));
    vxpe2d_radial_light_fast((uint16_t*)d,sw,sh,ox+22,oy,11,RGB565(48,181,255),90);
}
static void draw_skill_icon(VMUINT16*d,int sw,int sh,int x,int y,int id,int cd){
    VMUINT16 edge=RGB565(179,144,81);
    fill(d,sw,sh,x,y,28,28,RGB565(6,11,22));frame(d,sw,sh,x,y,28,28,edge);
    if(g_skills_ok){
        VxpeBlit565 op;memset(&op,0,sizeof(op));
        op.src.x=(int16_t)(id*32);op.src.y=0;op.src.w=32;op.src.h=32;
        op.dst_x=(int16_t)(x+2);op.dst_y=(int16_t)(y+2);op.dst_w=24;op.dst_h=24;
        op.tint565=0xFFFFu;op.alpha=255;op.blend=VXPE_BLEND_ALPHA;
        vxpe2d_blit_a8((uint16_t*)d,sw,sh,&g_skills_sprite,&op);
    }else if(id==0){
        circle(d,sw,sh,x+14,y+13,8,RGB565(23,112,225));circle(d,sw,sh,x+14,y+13,4,RGB565(169,244,255));
        line(d,sw,sh,x+4,y+18,x+20,y+4,RGB565(91,213,255));
    }else if(id==1){
        diamond(d,sw,sh,x+13,y+13,10,8,RGB565(229,61,176),RGB565(255,173,236));
        diamond(d,sw,sh,x+19,y+9,5,5,RGB565(244,110,211),RGB565(255,218,246));
    }else if(id==2){
        int i;for(i=0;i<5;++i){int px=x+8+(i*7)%17,py=y+8+(i*11)%15;circle(d,sw,sh,px,py,3,RGB565(245,117,191));}
        circle(d,sw,sh,x+14,y+14,3,RGB565(255,224,241));
    }else{
        diamond(d,sw,sh,x+14,y+14,10,10,RGB565(36,143,242),RGB565(161,235,255));
        line(d,sw,sh,x+6,y+18,x+20,y+8,RGB565(212,254,255));
    }
    if(cd>0){
        int h=(cd>240?240:cd)*26/240;
        if(id<3){int maxcd=id==0?45:(id==1?90:120);h=cd*26/maxcd;}
        vxpe2d_overlay_rect((uint16_t*)d,sw,sh,x+1,y+1,26,h,RGB565(5,9,18),170,VXPE_BLEND_ALPHA);
    }
    {
        char key[2]; key[0]=(id==0?'Q':(id==1?'W':(id==2?'E':'R')));key[1]=0;
        text(d,sw,sh,x+2,y+20,key,RGB565(255,255,255),1);
    }
}
static void draw_portrait(VMUINT16*d,int sw,int sh,int x,int y){
    fill(d,sw,sh,x,y,38,46,RGB565(16,13,26));frame(d,sw,sh,x,y,38,46,RGB565(192,151,84));
    circle(d,sw,sh,x+19,y+18,12,RGB565(240,229,244));
    diamond(d,sw,sh,x+12,y+8,5,8,RGB565(242,232,247),RGB565(193,148,203));
    diamond(d,sw,sh,x+27,y+8,5,8,RGB565(242,232,247),RGB565(193,148,203));
    ellipse(d,sw,sh,x+19,y+21,9,8,RGB565(235,203,194));
    fill(d,sw,sh,x+14,y+19,2,2,RGB565(139,47,96));fill(d,sw,sh,x+23,y+19,2,2,RGB565(139,47,96));
    circle(d,sw,sh,x+30,y+7,4,RGB565(227,72,148));
    fill(d,sw,sh,x+27,y+40,10,6,RGB565(23,19,31));frame(d,sw,sh,x+27,y+40,10,6,RGB565(204,161,72));
    text(d,sw,sh,x+30,y+40,"6",RGB565(255,219,83),1);
}
static void draw_hud(VMUINT16*d,int sw,int sh){
    int y=sh-HUD_H,barx=47,barw=108,hpwid,mpwid;
    char b[32];
    fill(d,sw,sh,0,y,sw,HUD_H,RGB565(7,11,19));
    fill(d,sw,sh,0,y,sw,2,RGB565(178,137,75));
    fill(d,sw,sh,4,y+4,sw-8,HUD_H-7,RGB565(12,17,27));
    frame(d,sw,sh,4,y+4,sw-8,HUD_H-7,RGB565(122,92,56));
    draw_portrait(d,sw,sh,7,y+7);
    draw_skill_icon(d,sw,sh,47,y+7,0,g_cd[0]);
    draw_skill_icon(d,sw,sh,77,y+7,1,g_cd[1]);
    draw_skill_icon(d,sw,sh,107,y+7,2,g_cd[2]);
    draw_skill_icon(d,sw,sh,137,y+7,3,g_cd[3]);
    hpwid=barw*g_hp/1241;mpwid=barw*g_mp/517;
    fill(d,sw,sh,barx,y+40,barw,8,RGB565(28,31,38));fill(d,sw,sh,barx,y+40,hpwid,8,RGB565(22,191,41));
    frame(d,sw,sh,barx,y+40,barw,8,RGB565(189,155,83));
    fill(d,sw,sh,barx,y+50,barw,7,RGB565(24,30,42));fill(d,sw,sh,barx,y+50,mpwid,7,RGB565(26,119,226));
    snprintf(b,sizeof(b),"%d/%d",g_hp,1241);text(d,sw,sh,barx+27,y+41,b,RGB565(255,255,255),1);
    snprintf(b,sizeof(b),"%d/%d",g_mp,517);text(d,sw,sh,barx+30,y+50,b,RGB565(255,255,255),1);
    {
        int i;for(i=0;i<3;++i){int ix=164+i*24;fill(d,sw,sh,ix,y+8,22,22,RGB565(9,14,22));frame(d,sw,sh,ix,y+8,22,22,RGB565(104,82,50));
        if(i==0)diamond(d,sw,sh,ix+11,y+19,6,4,RGB565(159,116,52),RGB565(223,174,72));
        else if(i==1){circle(d,sw,sh,ix+11,y+19,6,RGB565(42,127,218));circle(d,sw,sh,ix+11,y+19,2,RGB565(151,235,255));}
        else diamond(d,sw,sh,ix+11,y+19,5,8,RGB565(139,48,196),RGB565(226,135,255));}
    }
    circle(d,sw,sh,188,y+58,5,RGB565(220,159,43));text(d,sw,sh,198,y+55,"50",RGB565(255,214,60),2);
}
static void draw_nameplate(VMUINT16*d,int sw,int sh){
    int x=g_px-22,y=g_py-42; text(d,sw,sh,g_px-tw("ARIYA",1)/2,y,"ARIYA",RGB565(255,255,255),1);
    fill(d,sw,sh,x,y+8,44,6,RGB565(4,8,12));fill(d,sw,sh,x+1,y+9,42*g_hp/1241,4,RGB565(34,211,52));
    frame(d,sw,sh,x,y+8,44,6,RGB565(2,2,3));fill(d,sw,sh,x-10,y+7,9,8,RGB565(5,8,12));
    text(d,sw,sh,x-7,y+8,"6",RGB565(255,218,69),1);
}
static void draw_top(VMUINT16*d,int sw,int sh){
    char t[32];int sec=g_match_ms/1000;
    fill(d,sw,sh,0,0,sw,14,RGB565(5,10,17));
    text(d,sw,sh,4,3,"FPS30 CPU40 MEM9.8M",RGB565(245,248,250),1);
    text(d,sw,sh,155,3,"0 VS 0",RGB565(187,223,255),1);
    snprintf(t,sizeof(t),"00:%02d",sec%60);text(d,sw,sh,205,3,t,RGB565(255,255,255),1);
}
static void draw_controls(VMUINT16*d,int sw,int sh){
    int y=sh-HUD_H-30;
    circle(d,sw,sh,30,y,24,RGB565(53,66,86));circle(d,sw,sh,30,y,13,RGB565(67,82,104));
    line(d,sw,sh,30,y-19,30,y+19,RGB565(104,122,146));line(d,sw,sh,11,y,49,y,RGB565(104,122,146));
    circle(d,sw,sh,sw-30,y,19,RGB565(48,62,83));diamond(d,sw,sh,sw-30,y,7,11,RGB565(91,117,151),RGB565(123,159,195));
}

static void spawn_fx(int x,int y,VMUINT16 color,int count,int power,uint8_t blend){
    int i;VxpeParticleSpawn p;
    for(i=0;i<count;++i){memset(&p,0,sizeof(p));p.x=(int16_t)(x+rr(-3,3));p.y=(int16_t)(y+rr(-3,3));
        p.vx_q8=rr(-power,power)*256;p.vy_q8=rr(-power,power)*256;p.ay_q8=rr(-8,8)*256;
        p.lifetime_ms=(uint16_t)rr(380,820);p.color565=0xFFFF;p.tint565=color;p.alpha_start=(uint8_t)rr(150,245);p.alpha_end=0;
        p.size_start=(uint8_t)rr(2,4);p.size_end=1;p.blend=blend;p.collide=0;vxpe_particles_spawn(&g_fx,&p);}
}
static int blocked(int x,int y){
    int dx=x-154,dy=y-98;return dx*dx+dy*dy<42*42;
}
static void move_player(int dx,int dy){
    int nx=clampi(g_px+dx,30,210),ny=clampi(g_py+dy,54,214);
    if(!blocked(nx,ny)){
        vxpe2d_trail_push(&g_magic_trail,g_px,g_py+12);
        g_px=nx;g_py=ny;
        vxpe2d_trail_push(&g_magic_trail,g_px,g_py+12);
    }
    if(dx)g_face=dx>0?1:-1;
}
static void cast_skill(int id){
    if(id<0||id>3||g_cd[id]>0)return;
    if(id==0&&g_mp>=35){
        g_mp-=35;g_cd[0]=45;spawn_fx(g_px+g_face*22,g_py-3,RGB565(59,190,255),12,45,VXPE_BLEND_ADD);
        g_beam_x0=g_px+g_face*15;g_beam_y0=g_py-5;g_beam_x1=clampi(g_px+g_face*105,5,235);g_beam_y1=g_py-15;g_beam_fx=7;g_flash=4;
        vxpe2d_cinematic_punch(&g_cinematic,(int16_t)(g_face*420),-80,90);
    }else if(id==1&&g_mp>=50){
        g_mp-=50;g_cd[1]=90;vxpe2d_trail_push(&g_magic_trail,g_px,g_py+10);
        move_player(g_face*22,0);spawn_fx(g_px,g_py,RGB565(239,80,190),14,55,VXPE_BLEND_ADD);
        g_ring_fx=7;vxpe2d_cinematic_shake(&g_cinematic,2,120);
        vxpe2d_cinematic_punch(&g_cinematic,(int16_t)(g_face*700),0,120);
    }else if(id==2&&g_mp>=70){
        g_mp-=70;g_cd[2]=120;spawn_fx(g_px,g_py,RGB565(245,120,199),24,65,VXPE_BLEND_ALPHA);
        g_ring_fx=15;g_burst_fx=11;g_flash=6;
        vxpe2d_cinematic_shake(&g_cinematic,3,150);vxpe2d_cinematic_hitstop(&g_cinematic,50);
    }else if(id==3&&g_mp>=110){
        g_mp-=110;g_cd[3]=240;spawn_fx(g_px+g_face*18,g_py-4,RGB565(55,158,255),38,95,VXPE_BLEND_ADD);
        g_beam_x0=g_px;g_beam_y0=g_py-8;g_beam_x1=154;g_beam_y1=88;g_beam_fx=13;g_burst_fx=13;g_rot_fx=20;g_flash=10;
        vxpe2d_cinematic_shake(&g_cinematic,5,220);
        vxpe2d_cinematic_punch(&g_cinematic,(int16_t)((154-g_px)>=0?640:-640),-220,180);
        vxpe2d_cinematic_hitstop(&g_cinematic,70);
    }
}
static void update_game(void){
    int i;uint16_t sim_dt;
    g_tick++;
    sim_dt=vxpe2d_cinematic_update(&g_cinematic,33);
    if(!sim_dt)return;
    g_match_ms+=sim_dt;
    for(i=0;i<4;++i)if(g_cd[i]>0)--g_cd[i];
    if((g_tick%10)==0&&g_mp<517)g_mp++;
    if(g_flash>0)--g_flash;
    if(g_beam_fx>0)--g_beam_fx;if(g_ring_fx>0)--g_ring_fx;if(g_burst_fx>0)--g_burst_fx;if(g_rot_fx>0)--g_rot_fx;
    vxpe2d_trail_update(&g_magic_trail,sim_dt);
    if((g_tick&3)==0)spawn_fx(154+rr(-12,12),78+rr(-17,17),RGB565(45,184,255),1,12,VXPE_BLEND_ADD);
    vxpe_particles_update(&g_fx,sim_dt);
}
static void draw_combat_vfx(VMUINT16*d,int sw,int sh){
    static const int16_t q14[8][2]={
        {0,16384},{11585,11585},{16384,0},{11585,-11585},
        {0,-16384},{-11585,-11585},{-16384,0},{-11585,11585}
    };
    vxpe2d_trail_draw(&g_magic_trail,(uint16_t*)d,sw,sh);
    if(g_beam_fx>0){
        VxpeBeamStyle bs;
        bs.outer_color=RGB565(38,64,255);bs.core_color=RGB565(36,213,255);bs.hot_color=RGB565(230,255,255);
        bs.outer_width=9;bs.core_width=5;bs.hot_width=1;
        bs.alpha=(uint8_t)(145+g_beam_fx*7);bs.blend=VXPE_BLEND_ADD;
        vxpe2d_draw_beam((uint16_t*)d,sw,sh,g_beam_x0,g_beam_y0,g_beam_x1,
                         g_beam_y1+((g_tick&1)?1:-1),&bs);
    }
    if(g_ring_fx>0){
        int age=15-g_ring_fx;if(age<0)age=0;
        int r=15+age*3;uint8_t a=(uint8_t)clampi(g_ring_fx*12,35,190);
        vxpe2d_draw_ring((uint16_t*)d,sw,sh,g_px,g_py+5,r,3,
                         RGB565(84,213,255),a,VXPE_BLEND_ADD);
    }
    if(g_burst_fx>0){
        int age=13-g_burst_fx;if(age<0)age=0;
        int outer=20+age*3;uint8_t a=(uint8_t)clampi(g_burst_fx*15,40,220);
        vxpe2d_draw_burst((uint16_t*)d,sw,sh,g_px,g_py-4,7,outer,12,
                          (uint8_t)(g_tick&15),RGB565(255,118,226),a,VXPE_BLEND_ADD);
    }
    if(g_rot_fx>0&&g_skills_ok){
        int k=g_tick&7;
        VxpeBlit565 op;memset(&op,0,sizeof(op));
        op.src.x=96;op.src.y=0;op.src.w=32;op.src.h=32;
        op.dst_w=24;op.dst_h=24;
        op.dst_x=(int16_t)(g_px-12+((q14[k][1]*28)>>14));
        op.dst_y=(int16_t)(g_py-18+((q14[k][0]*12)>>14));
        op.tint565=RGB565(150,220,255);op.alpha=(uint8_t)clampi(110+g_rot_fx*5,0,220);op.blend=VXPE_BLEND_ADD;
        vxpe2d_blit_a8_rot_q14((uint16_t*)d,sw,sh,&g_skills_sprite,&op,q14[k][0],q14[k][1]);
    }
}

static void present_frame(void){
    VMUINT16*out=fb();int pw,ph,y,cw,ch;
    if(!out||g_layer<0)return;
    pw=vm_graphic_get_screen_width();ph=vm_graphic_get_screen_height();
    if(pw==SCREEN_W&&ph==SCREEN_H){
        memcpy(out,g_frame,sizeof(g_frame));
    }else{
        cw=pw<SCREEN_W?pw:SCREEN_W;ch=ph<SCREEN_H?ph:SCREEN_H;
        fill(out,pw,ph,0,0,pw,ph,RGB565(4,8,15));
        for(y=0;y<ch;++y)memcpy(out+y*pw,g_frame+y*SCREEN_W,cw*2);
    }
    vm_graphic_flush_layer(&g_layer,1);
}
static void draw_game(void){
    VMUINT16*d=g_frame;const int sw=SCREEN_W,sh=SCREEN_H,play_h=SCREEN_H-HUD_H;int y;int16_t cam_x=0,cam_y=0;
    if(g_layer<0)return;
    for(y=0;y<play_h;++y)memcpy(d+y*sw,g_static+y*MAX_W,sw*2);
    fill(d,sw,sh,0,play_h,sw,HUD_H,RGB565(7,11,19));
    vxpe2d_lightmap_clear(&g_lightmap);
    vxpe2d_lightmap_add_radial(&g_lightmap,g_px+(g_face<0?-29:29),g_py-13,14,
                               RGB565(56,190,255),115);
    if(g_beam_fx>0)vxpe2d_lightmap_add_beam(&g_lightmap,g_beam_x0,g_beam_y0,g_beam_x1,g_beam_y1,
                                            14,RGB565(44,148,255),135);
    if(g_ring_fx>0||g_burst_fx>0)vxpe2d_lightmap_add_radial(&g_lightmap,g_px,g_py,38,
                                                            RGB565(230,75,210),85);
    vxpe2d_lightmap_composite_add(&g_lightmap,(uint16_t*)d,sw,sh,165,play_h);
    vxpe2d_batch_init(&g_sprite_batch);
    draw_nexus(d,sw,play_h);
    vxpe_particles_draw(&g_fx,(uint16_t*)d,sw,play_h);
    draw_combat_vfx(d,sw,play_h);
    draw_ariya(d,sw,play_h,g_px,g_py);
    vxpe2d_batch_flush(&g_sprite_batch,(uint16_t*)d,sw,play_h);
    draw_nameplate(d,sw,play_h);
    if(g_flash){
        vxpe2d_overlay_rect((uint16_t*)d,sw,sh,0,14,sw,play_h-14,
            g_cd[3]>225?RGB565(40,133,255):RGB565(255,135,214),
            (uint8_t)(g_flash*7),VXPE_BLEND_ADD);
    }
    vxpe2d_cinematic_offset(&g_cinematic,&cam_x,&cam_y);
    if(cam_x||cam_y)vxpe2d_cinematic_shift_rgb565((uint16_t*)d,sw,sh,play_h,cam_x,cam_y,RGB565(17,29,45));
    draw_controls(d,sw,sh);draw_hud(d,sw,sh);draw_top(d,sw,sh);
    present_frame();
}
static void tick(VMINT tid){(void)tid;update_game();draw_game();}

void handle_keyevt(VMINT event,VMINT key){
    if(event!=VM_KEY_EVENT_DOWN&&event!=VM_KEY_EVENT_REPEAT)return;
    if(key==VM_KEY_LEFT)move_player(-4,0);
    else if(key==VM_KEY_RIGHT)move_player(4,0);
    else if(key==VM_KEY_UP)move_player(0,-4);
    else if(key==VM_KEY_DOWN)move_player(0,4);
    else if(key==VM_KEY_NUM1||key==VM_KEY_OK||key==VM_KEY_NUM5)cast_skill(0);
    else if(key==VM_KEY_NUM3)cast_skill(1);
    else if(key==VM_KEY_NUM7)cast_skill(2);
    else if(key==VM_KEY_NUM9)cast_skill(3);
    else if(key==VM_KEY_RIGHT_SOFTKEY||key==VM_KEY_CLEAR||key==VM_KEY_BACK){vm_exit_app();return;}
    draw_game();
}
void handle_penevt(VMINT event,VMINT x,VMINT y){
    int hy=SCREEN_H-HUD_H;
    if(event!=VM_PEN_EVENT_TAP&&event!=VM_PEN_EVENT_MOVE)return;
    if(y>=hy+6){
        if(x>=47&&x<75)cast_skill(0);
        else if(x>=77&&x<105)cast_skill(1);
        else if(x>=107&&x<135)cast_skill(2);
        else if(x>=137&&x<165)cast_skill(3);
        draw_game();return;
    }
    if(x<72){
        int dx=x-30,dy=y-(hy-30);
        if(dx<-5)move_player(-4,0);else if(dx>5)move_player(4,0);
        if(dy<-5)move_player(0,-4);else if(dy>5)move_player(0,4);
    }else if(x>176)cast_skill(0);
    draw_game();
}
static void start(void){
    if(!g_started){
        load_sprite_assets();
        build_scene(SCREEN_H-HUD_H);
        vxpe_particles_init(&g_fx,VXPE_PARTICLE_POOL_MAX);
        vxpe2d_batch_init(&g_sprite_batch);
        vxpe2d_cinematic_init(&g_cinematic,0x51A7E123u);
        vxpe2d_lightmap_init(&g_lightmap,60,60,SCREEN_W,SCREEN_H-HUD_H);
        vxpe2d_trail_init(&g_magic_trail,420,RGB565(108,232,255),RGB565(228,94,224),
                          5,1,185,VXPE_BLEND_ADD);
        g_started=1;
    }
    if(g_layer<0)g_layer=vm_graphic_create_layer(0,0,
        vm_graphic_get_screen_width(),vm_graphic_get_screen_height(),-1);
    if(g_timer<0)g_timer=vm_create_timer(33,tick);
    draw_game();
}
static void stop(void){
    if(g_timer>=0){vm_delete_timer(g_timer);g_timer=-1;}
    if(g_layer>=0){vm_graphic_delete_layer(g_layer);g_layer=-1;}
}
void handle_sysevt(VMINT m,VMINT p){
    (void)p;if(m==VM_MSG_CREATE||m==VM_MSG_ACTIVE)start();
    else if(m==VM_MSG_PAINT)draw_game();
    else if(m==VM_MSG_INACTIVE)stop();
    else if(m==VM_MSG_QUIT){stop();free_sprite_assets();vm_exit_app();}
}
void vm_main(void){
    vm_reg_sysevt_callback(handle_sysevt);
    vm_reg_keyboard_callback(handle_keyevt);
    vm_reg_pen_callback(handle_penevt);
}
