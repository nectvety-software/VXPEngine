from pathlib import Path
p=Path('examples/FoxRiftDemo/src/scene.h');s=p.read_text().replace('VxpeSpriteA8 background={},heroes={},logo={};','VxpeSpriteA8 background={},heroes={},logo={},structure_art={},skill_art={};');s=s.replace('void draw_menu(unsigned short* fb);','void skill_icon(unsigned short* fb,int hero,int skill,int x,int y,int size);\n    void draw_menu(unsigned short* fb);');p.write_text(s)
p=Path('examples/FoxRiftDemo/src/scene.cpp');s=p.read_text().replace('#include "assets_generated.h"','#include "assets_generated.h"\n#include "combat_assets_generated.h"');s=s.replace('vxpe_particles_init(&particles,48);','vxpe2d_sprite_a8_from_vxa8(duel_structures,sizeof(duel_structures),&structure_art);\n    vxpe2d_sprite_a8_from_vxa8(duel_skill_icons,sizeof(duel_skill_icons),&skill_art);\n    vxpe_particles_init(&particles,48);');s=s.replace('void FoxScene::draw_menu(unsigned short* fb){','''void FoxScene::skill_icon(unsigned short* fb,int hero,int skill,int x,int y,int size){
    VxpeBlit565 b={};b.src={(short)(skill*32),(short)(hero*32),32,32};
    b.dst_x=x;b.dst_y=y;b.dst_w=b.dst_h=size;b.alpha=255;b.tint565=0xFFFF;
    b.blend=VXPE_BLEND_ALPHA;vxpe2d_blit_a8(fb,240,320,&skill_art,&b);
}
void FoxScene::draw_menu(unsigned short* fb){''');s=s.replace('int y=185+i*12;text(fb,21,y,keys[i]','int y=185+i*12;skill_icon(fb,selected,i,6,y-1,10);text(fb,21,y,keys[i]');a=s.index('        vxpe2d_fill_rect(fb,240,320,96,y-6');b=s.index('    for(auto& e:effects)',a);s=s[:a]+'''        int core=t.max_hp==1800,col=t.hp?t.owner:2;
        VxpeBlit565 art={};art.src={(short)(col*64),(short)(core*80),64,80};
        art.dst_w=core?68:56;art.dst_h=core?80:70;
        art.dst_x=120-art.dst_w/2;art.dst_y=y-art.dst_h+2;
        art.alpha=255;art.tint565=0xFFFF;art.blend=VXPE_BLEND_ALPHA;
        art.clip_x=0;art.clip_y=41;art.clip_w=240;art.clip_h=209;
        vxpe2d_blit_a8(fb,240,320,&structure_art,&art);
        if(t.hp){int label_y=y-(core?75:81);
            bar(fb,95,label_y+10,50,t.hp,t.max_hp,c);
            text(fb,101,label_y,core?"CORE":"TOWER",c);
        }else text(fb,97,y-14,"RUINS",0xAD55);
    }
''' +s[b:];s=s.replace('char short_name[4]={h.skills[i][0],h.skills[i][1],h.skills[i][2],0};text(fb,x+11,259,short_name,h.color);\n        text(fb,x+11,275,keys[i],0xFFE9);','''skill_icon(fb,p.hero,i,x+2,257,24);
        vxpe2d_fill_rect(fb,240,320,x+28,273,10,10,0x0862);
        text(fb,x+30,275,keys[i],0xFFE9);''');s=s.replace('x+17,262,value','x+10,264,value');p.write_text(s)
p=Path('examples/FoxRiftDemo/tools/prepare_scene.py');s=p.read_text();s=s.replace('for screen in ("main"','combat=[node("BlueTower","assets/sprites/tower_blue.png",0,20,56,70),node("RedTower","assets/sprites/tower_red.png",0,-95,56,70)]+[node("Skill"+str(i),"assets/ui/velin_"+name+".png",-55+i*44,109,24,24,20) for i,name in enumerate(("prism_bolt","light_burst","anchor_ray","prism_nova"))]\n    for screen in ("main"');s=s.replace('extra=actors if screen','extra=actors+combat if screen');p.write_text(s)
