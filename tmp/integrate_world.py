from pathlib import Path
p=Path('examples/FoxRiftDemo/src/scene.h');s=p.read_text().replace('void lane_update(unsigned short dt);','void lane_update(unsigned short dt);\n    bool walkable(int x,int y) const;');s=s.replace('structure_art={},skill_art={};','structure_art={},skill_art={},environment_art={};');s=s.replace('void move(int owner,int dx,int dy);','void translate(int owner,int dx,int dy); void bot_move(int dx,int dy);\n    void draw_map_object(unsigned short* fb,int index);\n    void draw_structure(unsigned short* fb,int index);\n    void draw_fighter(unsigned short* fb,int index);\n    void move(int owner,int dx,int dy);');p.write_text(s)
p=Path('examples/FoxRiftDemo/src/scene.cpp');s=p.read_text().replace('#include "combat_assets_generated.h"','#include "combat_assets_generated.h"\n#include "environment_assets_generated.h"\n#include "world_generated.h"');s=s.replace('duel_arena,sizeof(duel_arena),&background','duel_lane_ground,sizeof(duel_lane_ground),&background');s=s.replace('vxpe_particles_init(&particles,48);','vxpe2d_sprite_a8_from_vxa8(duel_environment,sizeof(duel_environment),&environment_art);\n    vxpe_particles_init(&particles,48);');a=s.index('void FoxScene::move(');b=s.index('void FoxScene::heal(',a);s=s[:a]+'''bool FoxScene::walkable(int x,int y) const{
    if(x<26||x>214||y<80||y>880)return false;
    const int radius=7;
    for(const auto& o:duel_map_objects)if(o.solid){
        int left=o.x+o.cx,top=o.y+o.cy;
        if(x+radius>left&&x-radius<left+o.cw&&y+radius>top&&y-radius<top+o.ch)return false;
    }
    for(const auto& t:structures)if(t.hp>0){
        int half=t.max_hp==1800?26:22;
        if(x+radius>120-half&&x-radius<120+half&&y+radius>t.y-10&&y-radius<t.y+2)return false;
    }
    return true;
}
void FoxScene::translate(int owner,int dx,int dy){
    auto& f=fighters[owner];int old_x=f.x,old_y=f.y;
    int n=absi(dx)>absi(dy)?absi(dx):absi(dy);
    int previous_x=0,previous_y=0;
    for(int i=1;i<=n;++i){int sx=dx*i/n,sy=dy*i/n;
        int nx=clampi(f.x+sx-previous_x,26,214),ny=clampi(f.y+sy-previous_y,80,880);
        // Sweep one pixel at a time; resolve axes separately so walking slides along walls.
        if(walkable(nx,f.y))f.x=nx;
        if(walkable(f.x,ny))f.y=ny;
        previous_x=sx;previous_y=sy;
    }
    if(dx)f.facing=dx<0;
    f.moving|=old_x!=f.x||old_y!=f.y;
}
void FoxScene::move(int owner,int dx,int dy){
    auto& f=fighters[owner];if(f.stun_ms||f.hp<=0)return;
    int step=f.slow_ms?1:duel_heroes[f.hero].speed;
    translate(owner,dx*step,dy*step);
}
void FoxScene::bot_move(int dx,int dy){
    auto& bot=fighters[1];int step=bot.slow_ms?1:duel_heroes[bot.hero].speed;
    if(dy&&!walkable(bot.x+dx*step,bot.y+dy*step)){
        int side=bot.x<=120?-1:1;
        if(walkable(bot.x+side*step,bot.y))move(1,side,0);
        else move(1,-side,0);
    }else move(1,dx,dy);
}
''' +s[b:];s=s.replace('a.x=clampi(a.x+dx*45/norm,26,214);a.y=clampi(a.y+dy*45/norm,80,880);','translate(owner,dx*45/norm,dy*45/norm);');s=s.replace('a.x=clampi(a.x-dx*35/norm,26,214);a.y=clampi(a.y-dy*35/norm,80,880);','translate(owner,-dx*35/norm,-dy*35/norm);');s=s.replace('move(1,bot.x<120?1:(bot.x>120?-1:0),bot.y<y?1:-1)','bot_move(bot.x<120?1:(bot.x>120?-1:0),bot.y<y?1:-1)');s=s.replace('move(1,-dx,-dy)','bot_move(-dx,-dy)').replace('move(1,dx,dy);','bot_move(dx,dy);')
# Keep the helper itself calling ordinary movement (replacement above also matched that line).
s=s.replace('}else bot_move(dx,dy);','}else move(1,dx,dy);')
# The camera must see this frame\'s movement, not the preceding frame.
s=s.replace('    finish();\n}\nstatic VxpeFontStyle','    camera_y=clampi(fighters[0].y-190,0,640);\n    finish();\n}\nstatic VxpeFontStyle')
# Extract the existing sprite renderers into depth-sorted world nodes.
a=s.index('    for(auto& t:structures){int y=',s.index('void FoxScene::draw_match'));b=s.index('    for(auto& e:effects)',a)
structure=s[a:b];structure=structure.replace('    for(auto& t:structures){int y=t.y-camera_y;if(y<55||y>246)continue;','    const auto& t=structures[index];int y=t.y-camera_y;if(y<41||y>330)return;');structure=structure.rsplit('    }',1)[0]
af=s.index('    int first=fighters',b);bf=s.index('    for(auto& p:projectiles)',af)
fighter=s[af:bf];fighter=fighter[fighter.index('        vxpe2d_overlay_rect'):];fighter=fighter.rsplit('    }',1)[0]
prefix='''void FoxScene::draw_map_object(unsigned short* fb,int index){
    const auto& o=duel_map_objects[index];int y=o.y-camera_y;
    if(y+o.h<41||y>=250)return;
    VxpeBlit565 art={};art.src={(short)((o.kind%3)*64),(short)((o.kind/3)*80),64,80};
    art.dst_x=o.x;art.dst_y=y;art.dst_w=o.w;art.dst_h=o.h;
    art.alpha=255;art.tint565=0xFFFF;art.blend=VXPE_BLEND_ALPHA;
    art.clip_x=0;art.clip_y=41;art.clip_w=240;art.clip_h=209;
    vxpe2d_blit_a8(fb,240,320,&environment_art,&art);
}
void FoxScene::draw_structure(unsigned short* fb,int index){
'''+structure+'''\n}
void FoxScene::draw_fighter(unsigned short* fb,int i){
    auto f=fighters[i];f.y-=camera_y;
    if(f.hp<=0||f.y<41||f.y>310)return;
    const auto& h=duel_heroes[f.hero];
'''+fighter+'''\n}
'''
s=s[:af]+s[bf:];s=s[:a]+'''    struct Node {int depth,kind,index;};Node nodes[duel_map_count+8];int count=0;
    for(int i=0;i<duel_map_count;++i){const auto& o=duel_map_objects[i];nodes[count++]={o.y+o.h,0,i};}
    for(int i=0;i<6;++i)nodes[count++]={structures[i].y,1,i};
    for(int i=0;i<2;++i)nodes[count++]={fighters[i].y,2,i};
    for(int i=1;i<count;++i){Node n=nodes[i];int j=i;while(j>0&&nodes[j-1].depth>n.depth){nodes[j]=nodes[j-1];--j;}nodes[j]=n;}
    for(int i=0;i<count;++i){const auto& n=nodes[i];
        if(n.kind==0)draw_map_object(fb,n.index);else if(n.kind==1)draw_structure(fb,n.index);else draw_fighter(fb,n.index);
    }
''' +s[b:];s=s.replace('void FoxScene::draw_match(unsigned short* fb){',prefix+'void FoxScene::draw_match(unsigned short* fb){');s=s.replace('duel_arena+12+sy*240*2','duel_lane_ground+12+sy*240*2');p.write_text(s)
