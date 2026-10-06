#include "scene.h"
#include <assert.h>
#include <stdio.h>

static void save(EmberScene& s,const char* name) {
    static uint16_t pixels[240*320+2];
    pixels[0]=pixels[240*320+1]=0xABCD;
    s.draw(pixels+1);
    assert(pixels[0]==0xABCD && pixels[240*320+1]==0xABCD);
    FILE* f=fopen(name,"wb"); assert(f);
    fprintf(f,"P6\n240 320\n255\n");
    for(int i=1;i<=240*320;++i) {
        uint16_t c=pixels[i]; unsigned char p[3]={(unsigned char)(((c>>11)&31)*255/31),
            (unsigned char)(((c>>5)&63)*255/63),(unsigned char)((c&31)*255/31)};
        fwrite(p,1,3,f);
    }
    fclose(f);
}
static void frames(EmberScene& s,int n) { for(int i=0;i<n;++i) s.update(); }
int main() {
    static EmberScene s;
    s.init(); assert(s.dialogue.active);
    frames(s,80); save(s,"library_dialogue.ppm");
    for(int i=0;i<8 && s.dialogue.active;++i) s.input(5);
    assert(!s.dialogue.active && s.quest==1);
    save(s,"library.ppm");
    s.hold(6,true); frames(s,12); s.hold(6,false);
    assert(s.hero_x>115); save(s,"walk.ppm");
    s.input(9); uint32_t time=s.time_ms; frames(s,20); assert(s.time_ms==time);
    save(s,"pause.ppm"); s.input(9);
    s.input(0); assert(s.area==EMBER_TERRACE);
    for(int i=0;i<3;++i) { s.cast(); frames(s,40); }
    assert(s.duel_hp==0 && s.quest==2);
    save(s,"terrace.ppm");
    s.input(5); frames(s,60); save(s,"terrace_dialogue.ppm");
    s.input(0); assert(s.area==EMBER_VILLAGE);
    frames(s,40); save(s,"village_fire.ppm");
    const int locations[]={38,120,202};
    for(int x:locations) { s.hero_x=x; s.cast(); frames(s,20); }
    assert(s.wards==3 && s.quest==3);
    save(s,"village_safe.ppm");
    s.input(5); frames(s,100); save(s,"ending.ppm");
    s.input(1); assert(s.area==0 && s.wards==0 && s.duel_hp==3);
    s.input(-1); assert(!s.dialogue.active && !s.exiting);
    s.input(-1); assert(s.exiting);
    puts("PASS: dialogue, movement, pause, duel, falling fire, three wards, ending, restart, exit, framebuffer guards");
}
