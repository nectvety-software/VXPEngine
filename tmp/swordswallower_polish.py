from pathlib import Path
root=Path(r'C:/Users/doxuanhop/Documents/VXP Projects/Swordswallower')
p=root/'src/main.c';s=p.read_text(encoding='utf-8')
s=s.replace('#include "vmsys.h"','#ifdef SW_HOST_TEST\n#include "../tests/mre_host.h"\n#else\n#include "vmsys.h"').replace('#include "vmmm.h"','#include "vmmm.h"\n#endif\n#include "graphics/VxpPixelFont.h"\n#include "art_generated.h"\n#include <string.h>\n#include <stdio.h>')
s=s.replace('static int g_tick = 0;','static int g_tick = 0;\nstatic int g_room=0,g_paused=0,g_help=0,g_invul=0,g_started=0,g_font_big=0;\nstatic int cp_x=30,cp_y=282,cp_active=0,pull_ticks=0;\nstatic int relic_taken[2]={0,0},relic_x[2],relic_y[2];\nstatic int impact_x=0,impact_y=0,impact_ticks=0;\nstatic const char* room_names[3]={"THE BLUE NAVE","THORN CHOIR","MIDNIGHT BELFRY"};')
a=s.index('/* text ascii');b=s.index('/* ---------------- level',a)
s=s[:a]+'''static void set_font(int big){g_font_big=big;}
static void draw_text(VMUINT8* buf,int x,int y,const char* text,VMUINT16 color){
    VxpeFontStyle style;vxpe_font_style_default(&style);
    style.font_id=g_font_big?VXPE_FONT_DISPLAY:VXPE_FONT_UI;style.scale=g_font_big?2:1;
    style.color565=color;style.effects=VXPE_FONT_SHADOW;
    vxpe_font_draw((uint16_t*)buf,SW,SH,x,y,text,&style,(VxpeRectI){0,0,SW,SH});
}
static void cell(VMUINT16* fb,int index,int x,int y,int w,int h,int flip,int rotate){
    int dx,dy;for(dy=0;dy<h;++dy)for(dx=0;dx<w;++dx){
        int sx=dx*32/w,sy=dy*32/h,tx=sx,ty=sy;
        if(rotate==1){tx=sy;ty=31-sx;}else if(rotate==2){tx=31-sx;ty=31-sy;}else if(rotate==3){tx=31-sy;ty=sx;}
        if(flip)tx=31-tx;
        int i=((index/4)*32+ty)*128+(index%4)*32+tx;
        if(sw_art_mask[i>>3]&(128>>(i&7)))fb_px(fb,SW,SH,x+dx,y+dy,sw_art_pixels[i]);
    }
}
static void refresh_aim(void){
    int dx=k_right-k_left,dy=k_down-k_up;
    if(dx||dy){aim_dx=dx;aim_dy=dy;if(dx)facing=dx;}
}
''' +s[b:]
s=s.replace('    g_pl_n = 9;','    g_pl_n = 9;\n    cp_active=g_invul=pull_ticks=g_paused=g_help=0;cp_x=30;cp_y=282;\n    relic_taken[0]=relic_taken[1]=0;')
# Three staged, reachable single-screen puzzle arenas retain the original first layout.
needle='    door_x = 152; door_y = 78; door_w = 26; door_h = 32;'
s=s.replace(needle,needle+'''
    if(g_room==1){
        g_pl[3]=(Plat){12,260,88,10};g_pl[4]=(Plat){148,244,76,10};
        g_pl[5]=(Plat){60,206,68,10};g_pl[6]=(Plat){155,174,68,10};
        g_pl[7]=(Plat){20,136,64,10};g_pl[8]=(Plat){120,100,104,10};door_y=68;
    }else if(g_room==2){
        g_pl[3]=(Plat){12,260,80,10};g_pl[4]=(Plat){146,238,78,10};
        g_pl[5]=(Plat){56,198,72,10};g_pl[6]=(Plat){152,164,72,10};
        g_pl[7]=(Plat){16,126,72,10};g_pl[8]=(Plat){116,90,108,10};door_y=58;
    }
    relic_x[0]=g_pl[5].x+32;relic_y[0]=g_pl[5].y-16;
    relic_x[1]=g_pl[7].x+32;relic_y[1]=g_pl[7].y-16;
''')
# Reset enemy positions from actual platform geometry, with more flying pressure in later rooms.
end=s.index('\n}\n\nstatic int rect_overlap',s.index('static void level_reset'))
s=s[:end]+'''
    {int i;for(i=0;i<4;++i){int platform=i==0?4:(i==1?6:(i==3?8:7));
        if(i!=2){g_en[i].x=g_pl[platform].x+12;g_en[i].y=g_pl[platform].y-10;
            g_en[i].x0=g_pl[platform].x;g_en[i].x1=g_pl[platform].x+g_pl[platform].w;g_en[i].base_y=g_en[i].y;}
        if(g_room>0&&i==2)g_en[i].speed=2+g_room;
    }}
''' +s[end:]
s=s.replace('    if (sw_state != SW_HELD) return;','    if (sw_state != SW_HELD) return;\n    refresh_aim();',1)
s=s.replace('    dash_kill = 1;','    dash_kill = 1;pull_ticks=0;',1)
s=s.replace('if (g_state == ST_TITLE) { level_reset(); g_state = ST_PLAY; return; }','if (g_state == ST_TITLE) { g_room=0;level_reset();g_state=ST_PLAY;k_left=k_right=k_up=k_down=0;return; }')
s=s.replace('    /* ST_PLAY */','    if(g_paused||g_help)return;\n    /* ST_PLAY */')
s=s.replace('    hp--;','    if(g_invul)return;\n    hp--;g_invul=45;')
s=s.replace('    px = 30; py = 282; pvx = 0; pvy = 0;\n    recall_sword();','    px=cp_x;py=cp_y;pvx=pvy=0;\n    recall_sword();')
a=s.index('    /* cap nhat aim');b=s.index('    /* --- kiem bay',a);s=s[:a]+'    refresh_aim();\n    if(g_invul)--g_invul;\n    if(impact_ticks)--impact_ticks;\n\n'+s[b:]
s=s.replace('ty > SH - 2 || sw_fly > 150','ty > SH - 2')
s=s.replace('            swx = tx; swy = ty;','            if(sw_fly>150){recall_sword();break;}\n            swx = tx; swy = ty;')
s=s.replace('g_en[i].alive = 0; souls++;','g_en[i].alive = 0; souls++;impact_x=g_en[i].x;impact_y=g_en[i].y;impact_ticks=12;')
s=s.replace('    if (pulling && sw_state == SW_STUCK) {','    if(pulling&&++pull_ticks>75)recall_sword();\n    if (pulling && sw_state == SW_STUCK) {')
s=s.replace('                px = swx - pw / 2; py = swy - ph / 2;','                if(!rect_hits_world(swx-pw/2,swy-ph/2,pw,ph)){px=swx-pw/2;py=swy-ph/2;}')
# Sweep dash movement and mantle only a nearby thin ledge that holds the anchor.
a=s.index('                nx = px + mx;');b=s.index('                pvy = 0;',a)
s=s[:a]+'''                {int steps=mx<0?-mx:mx,ay=my<0?-my:my,j,last_x=0,last_y=0;
                    if(ay>steps)steps=ay;
                    for(j=1;j<=steps;++j){int sx=mx*j/steps,sy=my*j/steps;
                        nx=px+sx-last_x;ny=py+sy-last_y;
                        if(!rect_hits_world(nx,py,pw,ph))px=nx;
                        if(!rect_hits_world(px,ny,pw,ph))py=ny;
                        last_x=sx;last_y=sy;
                    }
                    for(j=3;j<g_pl_n;++j){Plat* ledge=&g_pl[j];int dx=swx-(px+pw/2),dy=swy-(py+ph/2);
                        if(dx<0)dx=-dx;if(dy<0)dy=-dy;
                        if(ledge->h<=12&&swx>=ledge->x&&swx<ledge->x+ledge->w&&swy>=ledge->y-3&&swy<=ledge->y+ledge->h&&dx<=18&&dy<=28){
                            int lx=swx-pw/2,ly=ledge->y-ph;
                            if(!rect_hits_world(lx,ly,pw,ph)){px=lx;py=ly;on_ground=1;recall_sword();break;}
                        }
                    }
                }
''' +s[b:]
s=s.replace('else if (sw_state == SW_FLYING) { g_en[i].alive = 0; souls++;impact_x=g_en[i].x;impact_y=g_en[i].y;impact_ticks=12; }','')
a=s.index('    /* --- toi cua? --- */');b=s.index('\n}\n\n/* ---------------- ve',a)
s=s[:a]+'''    {int center_x=px+pw/2,center_y=py+ph/2;
        for(i=0;i<2;++i)if(!relic_taken[i]){
            int dx=center_x-relic_x[i],dy=center_y-relic_y[i];if(dx<0)dx=-dx;if(dy<0)dy=-dy;
            int bx=swx-relic_x[i],by=swy-relic_y[i];if(bx<0)bx=-bx;if(by<0)by=-by;
            if(dx+dy<22||(sw_state!=SW_HELD&&bx+by<16)){relic_taken[i]=1;impact_x=relic_x[i];impact_y=relic_y[i];impact_ticks=12;}
        }
        int checkpoint_x=g_pl[5].x+10,checkpoint_y=g_pl[5].y-ph;
        if(rect_overlap(px,py,pw,ph,checkpoint_x-8,checkpoint_y-8,26,26)){
            cp_x=checkpoint_x;cp_y=checkpoint_y;cp_active=1;
        }
        if(g_room>0&&rect_overlap(px,py,pw,ph,102,290,34,10)){hurt_player();return;}
    }
    if(relic_taken[0]&&relic_taken[1]&&rect_overlap(px,py,pw,ph,door_x,door_y,door_w,door_h)){
        if(g_room<2){int old_hp=hp,old_souls=souls;++g_room;level_reset();hp=old_hp<3?old_hp+1:3;souls=old_souls;}
        else {g_state=ST_WIN;g_win_tick=0;}
    }
''' +s[b:]
# Replace background, character, enemies, HUD and menu rendering with original assets and fixed pixel fonts.
def replace_function(name,next_name,body):
 global s
 a=s.index('static void '+name+'(');b=s.index('static void '+next_name+'(',a);s=s[:a]+body+'\n\n'+s[b:]
replace_function('draw_bg','draw_plats','''static void draw_bg(VMUINT16* fb,int sw,int sh){
    (void)sw;(void)sh;memcpy(fb,sw_background,sizeof(sw_background));
}''')
replace_function('draw_door','draw_player','''static void draw_door(VMUINT16* fb,int sw,int sh){
    (void)sw;(void)sh;cell(fb,10,door_x-8,door_y-8,42,46,0,0);
    if(!relic_taken[0]||!relic_taken[1])fb_frame(fb,SW,SH,door_x+6,door_y+10,14,15,RGB565(255,65,157));
    else fb_frame(fb,SW,SH,door_x,door_y,door_w,door_h,RGB565(162,247,255));
    cell(fb,8,g_pl[5].x+1,g_pl[5].y-26,24,26,0,0);
    if(cp_active)fb_frame(fb,SW,SH,g_pl[5].x+3,g_pl[5].y-26,18,21,RGB565(80,247,255));
    {int i;for(i=0;i<2;++i)if(!relic_taken[i])cell(fb,9,relic_x[i]-9,relic_y[i]-9+((g_tick/8)&1),18,18,0,0);}
    if(g_room>0){int x;for(x=102;x<136;x+=6){fb_fill(fb,SW,SH,x,294,5,6,RGB565(230,64,138));fb_px(fb,SW,SH,x+2,290,RGB565(255,145,190));}}
}''')
replace_function('draw_player','draw_sword','''static void draw_player(VMUINT16* fb,int sw,int sh){
    int frame=pulling?3:((pvx&&on_ground)?1+(g_tick/4)%2:0);(void)sw;(void)sh;
    if(!g_invul||(g_tick&2))cell(fb,frame,px-8,py+ph-29,26,30,facing<0,0);
    if(sw_state==SW_HELD){int k;for(k=1;k<=4;++k)fb_fill(fb,SW,SH,px+pw/2+aim_dx*k*7,py+ph/2+aim_dy*k*7,2,2,RGB565(255,83,163));}
}''')
replace_function('draw_sword','draw_enemies','''static void draw_sword(VMUINT16* fb,int sw,int sh){
    (void)sw;(void)sh;
    if(sw_state==SW_HELD)cell(fb,4,px-6,py-10,34,34,facing<0,3);
    else {int rotation=swvx==0?(swvy<0?3:1):(swvx<0?2:0);
        cell(fb,4,swx-20,swy-20,40,40,0,rotation);
        if(sw_state==SW_STUCK)fb_frame(fb,SW,SH,swx-5,swy-5,10,10,RGB565(255,82,164));
        if(pulling){int n;for(n=0;n<=16;++n)fb_px(fb,SW,SH,px+pw/2+(swx-px-pw/2)*n/16,py+ph/2+(swy-py-ph/2)*n/16,RGB565(244,82,174));}
    }
    if(impact_ticks)cell(fb,11,impact_x-15,impact_y-15,30,30,0,0);
}''')
replace_function('draw_enemies','draw_hud','''static void draw_enemies(VMUINT16* fb,int sw,int sh){
    int i;(void)sw;(void)sh;for(i=0;i<MAX_ENEMY;++i)if(g_en[i].alive)
        cell(fb,g_en[i].fly?5+(g_tick/5)%2:7,g_en[i].x-5,g_en[i].y-12,24,24,g_en[i].dir<0,0);
}''')
replace_function('draw_hud','draw_title','''static void draw_hud(VMUINT16* fb,int sw,int sh){
    int i;char value[48];(void)sw;(void)sh;set_font(0);
    fb_fill(fb,SW,SH,0,0,SW,HUD_H,RGB565(5,8,21));fb_hline(fb,SW,SH,0,29,SW,RGB565(65,134,203));
    for(i=0;i<3;++i)fb_fill(fb,SW,SH,7+i*10,7,7,7,i<hp?RGB565(255,75,155):RGB565(55,32,57));
    snprintf(value,sizeof(value),"%d/3  SEALS %d/2  SOUL %d",g_room+1,relic_taken[0]+relic_taken[1],souls);
    draw_text((VMUINT8*)fb,46,6,value,RGB565(216,232,250));
    draw_text((VMUINT8*)fb,7,18,pulling?"PULLING":(sw_state==SW_HELD?"5 THROW":(sw_state==SW_FLYING?"SWORD IN FLIGHT":"5 PULL / 7 RECALL")),RGB565(255,110,193));
    draw_text((VMUINT8*)fb,164,18,"0 PAUSE",RGB565(107,167,203));
}''')
replace_function('draw_title','draw_win','''static void draw_title(VMUINT16* fb,int sw,int sh){
    draw_bg(fb,sw,sh);cell(fb,0,92,44,56,64,0,0);cell(fb,4,77,64,82,82,0,3);
    set_font(1);draw_text((VMUINT8*)fb,48,123,"SWORD",RGB565(220,246,255));
    draw_text((VMUINT8*)fb,26,148,"SWALLOWER",RGB565(248,96,171));set_font(0);
    draw_text((VMUINT8*)fb,50,180,"PORTRAIT DEMAKE",RGB565(96,177,220));
    draw_text((VMUINT8*)fb,29,201,"NO JUMP. THROW AND PULL.",RGB565(235,231,226));
    draw_text((VMUINT8*)fb,33,218,"4/6 WALK  2/8 AIM  5 ACT",RGB565(163,203,231));
    fb_fill(fb,SW,SH,31,242,178,24,RGB565(34,45,84));
    draw_text((VMUINT8*)fb,77,250,"5 START",RGB565(238,213,244));
    draw_text((VMUINT8*)fb,56,281,"# GUIDE / BACK EXIT",RGB565(143,164,193));
    draw_text((VMUINT8*)fb,41,300,"INSPIRED BY UTI AZULAY",RGB565(101,136,179));
}''')
replace_function('draw_win','draw_dead','''static void draw_win(VMUINT16* fb,int sw,int sh){
    draw_bg(fb,sw,sh);set_font(1);draw_text((VMUINT8*)fb,32,121,"ESCAPED",RGB565(140,238,255));set_font(0);
    draw_text((VMUINT8*)fb,44,160,"THREE CHAMBERS CLEARED",RGB565(244,137,204));
    draw_text((VMUINT8*)fb,62,192,"5 RETURN TO TITLE",RGB565(222,231,242));
}''')
replace_function('draw_dead','draw','''static void draw_dead(VMUINT16* fb,int sw,int sh){
    draw_bg(fb,sw,sh);set_font(1);draw_text((VMUINT8*)fb,32,126,"CONSUMED",RGB565(246,80,149));set_font(0);
    draw_text((VMUINT8*)fb,53,169,"THE BLADE REMEMBERS",RGB565(159,186,214));
    draw_text((VMUINT8*)fb,67,206,"5 RETURN / RETRY",RGB565(237,215,231));
}''')
s=s.replace('    vm_graphic_flush_layer(&g_layer, 1);','''    if(g_paused||g_help){
        fb_fill(fb,SW,SH,12,83,216,158,RGB565(8,17,38));set_font(0);
        draw_text((VMUINT8*)fb,29,98,g_help?"SWORD PILGRIM GUIDE":"PAUSED",RGB565(250,123,199));
        draw_text((VMUINT8*)fb,24,119,"4/6 WALK / 2/8 AIM",RGB565(211,229,245));
        draw_text((VMUINT8*)fb,24,137,"5 THROW, THEN 5 TO PULL",RGB565(211,229,245));
        draw_text((VMUINT8*)fb,24,155,"7 RECALL / 0 PAUSE",RGB565(211,229,245));
        draw_text((VMUINT8*)fb,24,173,"COLLECT 2 SEALS, FIND GATE",RGB565(211,229,245));
        draw_text((VMUINT8*)fb,24,191,"LANTERN SAVES CHECKPOINT",RGB565(211,229,245));
        draw_text((VMUINT8*)fb,24,215,g_help?"# CLOSE GUIDE":"0 RESUME / * RESTART",RGB565(250,123,199));
    }
    vm_graphic_flush_layer(&g_layer, 1);''')
s=s.replace('    if (g_state == ST_PLAY) update_play();','    if (g_state == ST_PLAY&&!g_paused&&!g_help) update_play();')
s=s.replace('    vm_graphic_set_font(VM_SMALL_FONT);\n    level_reset();','    if(!g_started){level_reset();g_started=1;}')
s=s.replace('vm_create_timer(50, tick)','vm_create_timer(33, tick)')
s=s.replace('    if (g_timer >= 0) { vm_delete_timer(g_timer); g_timer = -1; }','    k_left=k_right=k_up=k_down=0;\n    if (g_timer >= 0) { vm_delete_timer(g_timer); g_timer = -1; }')
s=s.replace('    if (event == VM_KEY_EVENT_DOWN) {','''    if (event == VM_KEY_EVENT_DOWN) {
        if(keycode==VM_KEY_NUM7&&g_state==ST_PLAY){if(!g_paused&&!g_help)recall_sword();return;}
        if(keycode==VM_KEY_NUM0&&g_state==ST_PLAY){g_paused=!g_paused;k_left=k_right=k_up=k_down=0;return;}
        if(keycode==VM_KEY_POUND){g_help=!g_help;k_left=k_right=k_up=k_down=0;return;}
        if(keycode==VM_KEY_STAR&&g_state==ST_PLAY){g_room=0;level_reset();return;}
''')
s=s.replace('if (event != 1 && event != 2) return;','if (event != VM_PEN_EVENT_TAP) return;')
s=s.replace('if (g_state != ST_PLAY) { press_action(); return; }','if (g_state != ST_PLAY) { press_action(); return; }\n    if(g_paused||g_help)return;')
p.write_text(s,encoding='utf-8')
print('Patched original project: three chambers, seals, checkpoints, safe grapple/mantle, pause/help, original art and pixel fonts')
