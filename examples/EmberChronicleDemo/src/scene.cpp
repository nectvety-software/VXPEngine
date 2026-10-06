#include "scene.h"
#include "assets_generated.h"
#include "story_hud_generated.h"
#include <string.h>
#include <stdio.h>

static int clampi(int v,int lo,int hi) { return v<lo?lo:(v>hi?hi:v); }
static int absi(int v) { return v<0?-v:v; }
static const int ward_x[3]={38,120,202};

uint32_t EmberScene::random() { rng=rng*1664525u+1013904223u; return rng; }

void EmberScene::init() {
    if(initialized) return;
    initialized=1;
    vxpe2d_sprite_a8_from_vxa8(ember_library,sizeof(ember_library),&backgrounds[0]);
    vxpe2d_sprite_a8_from_vxa8(ember_terrace,sizeof(ember_terrace),&backgrounds[1]);
    vxpe2d_sprite_a8_from_vxa8(ember_village,sizeof(ember_village),&backgrounds[2]);
    vxpe2d_sprite_a8_from_vxa8(ember_characters,sizeof(ember_characters),&characters);
    vxpe_story_stage_init(&stage,245,290);
    vxpe_particles_init(&particles,64);
    vxpe2d_batch_init(&batch);
    // Four flame frames, RGB565/A8 built once, no heap or frame-time baking.
    for(int f=0;f<4;++f) for(int y=0;y<32;++y) for(int x=0;x<24;++x) {
        int bend=((31-y)*((f&1)?2:-2))/14;
        int dx=x-12-bend;
        int width=2+(y*8)/31;
        int noise=(x*7+y*11+f*13)&7;
        int i=y*96+f*24+x;
        if(y>2 && absi(dx)<width && noise!=0) {
            int core=absi(dx)<width/2 && y>14;
            fire_pixels[i]=core?0xFFFC:(y>10?0xFD24:0xF9A0);
            fire_alpha[i]=(uint8_t)(core?255:220);
        }
    }
    fire={fire_pixels,fire_alpha,96,32,96,96,0};
    enter(EMBER_LIBRARY);
}

void EmberScene::enter(int next) {
    area=clampi(next,0,2); held=0; paused=0;
    hero_x=area==EMBER_TERRACE?60:115; hero_y=278;
    walk_left=cast_ms=cooldown=0;
    memset(bolts,0,sizeof(bolts));
    vxpe_particles_clear(&particles);
    dialogue.active=0; dialogue_step=0; rain_ms=0;
    if(area==EMBER_LIBRARY) talk();
}

void EmberScene::talk() {
    const char* speaker="Maelin";
    const char* text="The old library keeps our village's memories. But a rain of embers is coming. Take the silver ward to the terrace. Sir Rowan will show you how to awaken it.";
    if(area==EMBER_TERRACE) { speaker="Rowan"; text=duel_hp>0?
        "Keep your feet steady. Face me and cast three times with 7. The ward responds to courage. Use 2 / 8 to step between our paths.":
        "Well done, Lyra. The ward is awake. The village needs you now. Press 0 to reach the square."; }
    if(area==EMBER_VILLAGE) { speaker="Syl"; text=wards<3?
        "Three ember seals are burning in the square! Stand near each gold marker and press 7 to cleanse it. Watch the falling fire. We can still save these homes.":
        "You did it! The embers have faded, and every book and every home is safe. The village will remember this night."; }
    vxpe_story_dialogue_open(&dialogue,speaker,text,33,5,20);
}

void EmberScene::hold(int key,bool down) {
    uint8_t bit=key==4?1:(key==6?2:(key==2?4:(key==8?8:0)));
    if(down) held|=bit; else held&=(uint8_t)~bit;
}

void EmberScene::input(int key) {
    if(key==-1) { if(dialogue.active) dialogue.active=0; else exiting=1; return; }
    if(key==9) { paused=!paused; held=0; return; }
    if(key==1) { duel_hp=3; wards=quest=0; memset(ward_done,0,sizeof(ward_done)); enter(0); return; }
    if(paused) return;
    if(key==0) { enter((area+1)%3); return; }
    if(key==5) { action(); return; }
    if(key==7 && !dialogue.active) cast();
}

void EmberScene::action() {
    if(dialogue.active) {
        if(!vxpe_story_dialogue_advance(&dialogue)) {
            if(area==EMBER_LIBRARY && dialogue_step==0) {
                ++dialogue_step;
                vxpe_story_dialogue_open(&dialogue,"Lyra",
                    "I'll bring everyone home. Syl, keep close!\n0 changes scene. 2/4/6/8 move. 7 casts a spell. 5 speaks to friends.",33,5,20);
                quest=1;
            }
        }
    } else talk();
}

void EmberScene::sparkle(int x,int y,uint16_t color,int count) {
    for(int i=0;i<count;++i) {
        VxpeParticleSpawn p={};
        p.x=(int16_t)x; p.y=(int16_t)y;
        p.vx_q8=((int)(random()%81)-40)*256;
        p.vy_q8=-((int)(random()%65)+15)*256; p.ay_q8=45*256;
        p.lifetime_ms=350+(uint16_t)(random()%450);
        p.color565=color; p.tint565=0xFFFF;
        p.alpha_start=240; p.size_start=3; p.size_end=1; p.blend=VXPE_BLEND_ADD;
        vxpe_particles_spawn(&particles,&p);
    }
}

void EmberScene::cast() {
    if(cooldown || paused || dialogue.active) return;
    cast_ms=420; cooldown=500;
    sparkle(hero_x+(facing?-20:20),hero_y-58,0xD77F,12);
    if(area==EMBER_VILLAGE) {
        for(int i=0;i<3;++i) if(!ward_done[i] && absi(hero_x-ward_x[i])<36) {
            ward_done[i]=1; ++wards; sparkle(ward_x[i],253,0xAFE9,18);
        }
        for(auto& bolt:bolts) if(bolt.active && bolt.hostile &&
            absi(bolt.x-hero_x)<75 && absi(bolt.y-hero_y)<100) {
            bolt.active=0; sparkle(bolt.x,bolt.y,0xFFEA,4);
        }
        if(wards==3) quest=3;
    }
    for(auto& bolt:bolts) if(!bolt.active) {
        bolt={ (int16_t)(hero_x+(facing?-22:22)),(int16_t)(hero_y-45),
            (int16_t)(facing?-6:6),0,0,1,0}; break;
    }
}

void EmberScene::update(uint16_t dt) {
    init();
    if(paused) return;
    time_ms+=dt;
    vxpe_story_dialogue_update(&dialogue,dt);
    vxpe_particles_update(&particles,dt);
    if(dialogue.active) { held=0; return; }
    cooldown=clampi(cooldown-dt,0,500);
    cast_ms=clampi(cast_ms-dt,0,420);
    hurt_ms=clampi(hurt_ms-dt,0,600);
    walk_left=clampi(walk_left-dt,0,160);
    int dx=((held&2)?2:0)-((held&1)?2:0);
    int dy=((held&8)?1:0)-((held&4)?1:0);
    if(dx || dy) {
        hero_x=clampi(hero_x+dx,28,212); hero_y=clampi(hero_y+dy,248,289);
        if(dx) facing=dx<0;
        walk_left=150; walk_ms+=dt;
    } else if(!walk_left) walk_ms=0;
    // Fixed step of 33 ms: trajectory velocity is pixels per tick.
    for(auto& bolt:bolts) if(bolt.active) {
        bolt.x+=bolt.vx; bolt.y+=bolt.vy; bolt.age+=dt;
        if(bolt.x<-20 || bolt.x>260 || bolt.y>294 || bolt.age>2400) { bolt.active=0; continue; }
        if(!bolt.hostile && area==EMBER_TERRACE && duel_hp>0 &&
            absi(bolt.x-185)<24 && absi(bolt.y-233)<36) {
            --duel_hp; bolt.active=0; sparkle(185,240,0xFFEA,18);
            if(!duel_hp) quest=2;
        }
        if(bolt.hostile && absi(bolt.x-hero_x)<16 && absi(bolt.y-(hero_y-30))<24) {
            bolt.active=0; hurt_ms=500; sparkle(hero_x,hero_y-35,0xFD20,6);
        }
    }
    if(area==EMBER_VILLAGE && wards<3) {
        rain_ms+=dt;
        if(rain_ms>=450) {
            rain_ms=0;
            for(auto& bolt:bolts) if(!bolt.active) {
                bolt={(int16_t)(20+random()%200),-10,(int16_t)((random()&1)?-1:1),3,0,1,1}; break;
            }
        }
    }
    if((time_ms/33)%4==0) sparkle(hero_x+28,hero_y-90,0xAFF5,1);
}

void EmberScene::actor(int index,int x,int y,int lift,int flip) {
    VxpeRectI frame={(int16_t)((index%4)*80),(int16_t)((index/4)*96),80,96};
    // Artwork includes the fairy's luminous edge; no extra outline pass needed.
    vxpe_story_push_actor(&batch,&stage,&characters,frame,40,92,
        (int16_t)x,(int16_t)y,(int16_t)lift,(uint8_t)flip,0);
}

void EmberScene::flame(uint16_t* fb,int x,int y,int size,int frame) {
    VxpeBlit565 op={};
    op.src={(int16_t)((frame&3)*24),0,24,32};
    op.dst_x=(int16_t)(x-size/2); op.dst_y=(int16_t)(y-size);
    op.dst_w=(uint16_t)size; op.dst_h=(uint16_t)size;
    op.alpha=255; op.tint565=0xFFFF; op.blend=VXPE_BLEND_ALPHA;
    vxpe2d_blit_a8(fb,240,320,&fire,&op);
}

void EmberScene::draw(uint16_t* fb) {
    init(); if(!fb) return;
    VxpeBlit565 bg={}; bg.dst_w=240; bg.dst_h=320;
    bg.tint565=0xFFFF; bg.alpha=255; bg.blend=VXPE_BLEND_COPY;
    vxpe2d_blit_a8(fb,240,320,&backgrounds[area],&bg);
    const int f=(time_ms/110)&3;
    if(area==EMBER_VILLAGE && wards<3) {
        for(int i=0;i<3;++i) if(!ward_done[i]) {
            vxpe2d_radial_light(fb,240,320,ward_x[i],247,30,0xFC42,50);
            flame(fb,ward_x[i],254,36,f+i);
            vxpe2d_fill_rect(fb,240,320,ward_x[i]-10,280,20,2,0xFF28);
        }
    }
    const int fairy_bob=(int)((time_ms/170)%6); // triangular, no floats
    vxpe2d_overlay_rect(fb,240,320,hero_x-15,hero_y-2,30,3,0,130,VXPE_BLEND_ALPHA);
    int hero_frame=cast_ms?3:(walk_left?1+(walk_ms/140)%2:0);
    if(!hurt_ms || (time_ms/80)%2) actor(hero_frame,hero_x,hero_y,0,facing);
    actor(12,hero_x+28,hero_y-1,62+(fairy_bob>3?6-fairy_bob:fairy_bob));
    if(area==EMBER_LIBRARY) {
        vxpe2d_overlay_rect(fb,240,320,32,275,26,3,0,100,VXPE_BLEND_ALPHA);
        actor(8,46,278); actor(4,192,280);
        actor(13,clampi(hero_x+38,20,218),hero_y+4); actor(14,clampi(hero_x+62,20,222),hero_y+3);
    } else if(area==EMBER_TERRACE) {
        actor(15,185,278);
        vxpe2d_overlay_rect(fb,240,320,168,178,35,4,0,150,VXPE_BLEND_ALPHA);
        vxpe2d_fill_rect(fb,240,320,169,179,duel_hp*11,2,0xBF53);
    }
    vxpe2d_batch_flush(&batch,fb,240,320);
    for(const auto& bolt:bolts) if(bolt.active) {
        flame(fb,bolt.x,bolt.y,bolt.hostile?28:17,f);
        if(!bolt.hostile) vxpe2d_radial_light(fb,240,320,bolt.x,bolt.y-8,12,0xC77F,55);
    }
    vxpe_particles_draw(&particles,fb,240,320);
    static const char* areas[]={"ARCHIVE OF MOSS","THE SILVER TERRACE","EMBERFALL SQUARE"};
    static const char* chapters[]={"I / THE CALL","II / THE WARD","III / EMBERFALL"};
    char status[32];
    if(area==EMBER_TERRACE) snprintf(status,sizeof(status),"DUEL %d/3",3-duel_hp);
    else if(area==EMBER_VILLAGE) snprintf(status,sizeof(status),"SEALS %d/3",wards);
    else strcpy(status,"LYRA + SYL");
    vxpe_story_hud_draw(fb,240,320,&story_hud_style,story_hud_title,
        areas[area],chapters[area],status,story_hud_keys,story_hud_labels,6);
    if(area==EMBER_VILLAGE && wards==3 && !dialogue.active) {
        vxpe2d_overlay_rect(fb,240,320,42,50,156,22,0x1B25,200,VXPE_BLEND_ALPHA);
        vxpe_story_text(fb,240,320,51,58,"THE VILLAGE IS SAFE",0xBFF1);
    }
    VxpeRectI box={10,50,220,100};
    vxpe_story_dialogue_draw(fb,240,320,&dialogue,box);
    if(paused) {
        vxpe2d_overlay_rect(fb,240,320,0,44,240,250,0,155,VXPE_BLEND_ALPHA);
        vxpe_story_text(fb,240,320,99,145,"PAUSED",0xFFE9);
        vxpe_story_text(fb,240,320,61,165,"9 RESUME / 1 RESTART",0xFFFF);
    }
}
