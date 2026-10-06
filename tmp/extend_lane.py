from pathlib import Path
p=Path('examples/FoxRiftDemo/src/scene.h');s=p.read_text();s=s.replace('int cast_ms,heal_ms,facing','int respawn_ms,skin; int cast_ms,heal_ms,facing');s=s.replace('class FoxScene {','struct DuelStructure { int owner,y,hp,max_hp,attack_ms; };\nstruct DuelEffect { int x,y,life,hero,skill,owner; };\nclass FoxScene {');s=s.replace('int bot_decisions=0,bot_retreats=0;','int bot_decisions=0,bot_retreats=0;\n    int selected_skin=0,bot_skin=0,camera_y=0;\n    DuelStructure structures[6]={}; DuelEffect effects[12]={};\n    void damage_structure(int owner,int index,int amount);\n    void lane_update(unsigned short dt);');p.write_text(s)
p=Path('examples/FoxRiftDemo/src/scene.cpp');s=p.read_text();s=s.replace('void FoxScene::select_hero','static const char* skin_names[3][2]={{"PRISM","FROST PRISM"},{"COPPER","OBSIDIAN"},{"WIND","SUNSET"}};\nstatic const unsigned short skin_tints[3]={0x87FF,0xC5BF,0xFD30};\nvoid FoxScene::select_hero',1);s=s.replace('fighters[0].hero=selected;fighters[1].hero=bot_selected;','fighters[0].hero=selected;fighters[1].hero=bot_selected;\n    fighters[0].skin=selected_skin;fighters[1].skin=bot_skin;\n    memset(effects,0,sizeof(effects));\n    for(int i=0;i<6;++i){int owner=i/3;structures[i]={owner,owner?(90+(i%3)*130):(870-(i%3)*130),i%3?900:1800,i%3?900:1800,0};}');s=s.replace('f.y=i?139:211','f.y=i?210:750');s=s.replace('vxpe_particles_clear(&particles);','camera_y=clampi(fighters[0].y-190,0,640);vxpe_particles_clear(&particles);',1);s=s.replace('if(key==1){help=!help;return;}','if(key==7){selected_skin^=1;return;}\n        if(key==9){bot_skin^=1;return;}\n        if(key==1){help=!help;return;}',1)
a=s.index('void FoxScene::finish(){');b=s.index('void FoxScene::hit(',a)
s=s[:a]+'''void FoxScene::finish(){
    if(screen!=DUEL_MATCH)return;
    if(structures[0].hp<=0||structures[3].hp<=0||time_ms>=300000){
        int a=structures[0].hp,b=structures[3].hp;
        result=a==b?2:(a>b?1:-1);screen=DUEL_RESULT;held=paused=0;
    }
}
void FoxScene::damage_structure(int owner,int index,int amount){
    if(owner<0||owner>1||index<0||index>=6||amount<=0)return;
    auto& t=structures[index];if(t.owner==owner||t.hp<=0)return;
    int outer=t.owner*3+2,inner=t.owner*3+1;
    if(index!=outer&&structures[outer].hp>0)return;
    if(index%3==0&&structures[inner].hp>0)return;
    t.hp=clampi(t.hp-amount,0,t.max_hp);finish();
}
void FoxScene::lane_update(unsigned short dt){
    for(auto& t:structures){
        if(t.hp<=0)continue;t.attack_ms=clampi(t.attack_ms-dt,0,1200);
        auto& enemy=fighters[1-t.owner];
        if(enemy.hp>0&&absi(enemy.y-t.y)+absi(enemy.x-120)<105&&!t.attack_ms){
            t.attack_ms=1200;enemy.hp=clampi(enemy.hp-(t.owner*3==(&t-structures)?45:65),0,2000);
        }
    }
    for(int i=0;i<2;++i){auto& f=fighters[i];
        if(f.hp<=0){
            if(!f.respawn_ms)f.respawn_ms=5000;
            else {f.respawn_ms=clampi(f.respawn_ms-dt,0,5000);if(!f.respawn_ms){
                f.hp=duel_heroes[f.hero].max_hp;f.mana=duel_heroes[f.hero].max_mana;
                f.shield=f.stun_ms=f.slow_ms=0;f.x=120;f.y=i?160:800;
            }}continue;
        }
        if(absi(f.y-structures[i*3].y)<65){f.hp=clampi(f.hp+3,0,duel_heroes[f.hero].max_hp);f.mana=clampi(f.mana+2,0,duel_heroes[f.hero].max_mana);}
        if(f.attack_ms||f.stun_ms)continue;
        for(int j=(1-i)*3+2;j>=(1-i)*3;--j){auto& t=structures[j];
            if(t.hp>0&&absi(f.y-t.y)+absi(f.x-120)<=duel_heroes[f.hero].attack_range+30){
                f.attack_ms=duel_heroes[f.hero].attack_cd;damage_structure(i,j,duel_heroes[f.hero].attack);break;
            }
        }
    }
    camera_y=clampi(fighters[0].y-190,0,640);
}
''' +s[b:]
s=s.replace('if(defender.hero==1)','if(defender.hp<=0||attacker.hp<=0)return;\n    if(defender.hero==1)',1)
s=s.replace('if(f.stun_ms)return;','if(f.stun_ms||f.hp<=0)return;',1).replace(',112,239)',',80,880)');s=s.replace('if(f.heal_ms||f.stun_ms','if(f.hp<=0||f.heal_ms||f.stun_ms');s=s.replace('if(a.stun_ms||a.cooldown','if(a.hp<=0||a.stun_ms||a.cooldown');s=s.replace('sparks(a.x,a.y-20,h.color,10);','sparks(a.x,a.y-20,h.color,10);\n    for(auto& e:effects)if(!e.life){e={a.x,a.y,650,a.hero,skill,owner};break;}')
s=s.replace('if(bot.stun_ms)return;','if(bot.stun_ms||bot.hp<=0)return;\n    if(player.hp<=0||dist(bot,player)>210){\n        int target=0;for(int j=2;j>=0;--j)if(structures[j].hp>0){target=j;break;}\n        int y=structures[target].y;\n        if(absi(bot.y-y)>duel_heroes[bot.hero].attack_range+20)move(1,bot.x<120?1:(bot.x>120?-1:0),bot.y<y?1:-1);\n        return;\n    }',1)
s=s.replace('time_ms+=dt;vxpe_particles_update','time_ms+=dt;\n    for(auto& e:effects)e.life=clampi(e.life-dt,0,650);\n    lane_update(dt);\n    vxpe_particles_update',1);s=s.replace('if(!a.stun_ms&&!a.attack_ms&&dist','if(a.hp>0&&fighters[1-i].hp>0&&!a.stun_ms&&!a.attack_ms&&dist');s=s.replace('p.y<24||p.y>250','p.y<0||p.y>960')
s=s.replace('b.alpha=255;b.tint565=0xFFFF;b.blend=VXPE_BLEND_ALPHA;vxpe2d_blit_a8(fb,240,320,&heroes,&b);','b.alpha=255;b.tint565=0xFFFF;\n    int skin=screen==DUEL_SELECT?(hero==selected?selected_skin:0):fighters[0].skin;\n    if(screen!=DUEL_SELECT&&hero==fighters[1].hero)skin=fighters[1].skin;\n    if(skin)b.tint565=skin_tints[hero];\n    b.blend=VXPE_BLEND_ALPHA;vxpe2d_blit_a8(fb,240,320,&heroes,&b);')
s=s.replace('snprintf(value,sizeof(value),"BOT: %s  [2/8]"','snprintf(value,sizeof(value),"BOT: %s  [2/8]"');s=s.replace('vxpe2d_fill_rect(fb,240,320,25,258','snprintf(value,sizeof(value),"7 %s  9 BOT SKIN",skin_names[selected][selected_skin]);centered(fb,225,value,0xFFE9);\n    vxpe2d_fill_rect(fb,240,320,25,258',1);s=s.replace('SOLO / FIRST KNOCKOUT WINS','SOLO / DESTROY ENEMY CORE').replace('120s LIMIT: HP % WINS','TOWERS FIRST / 5s RESPAWN')
s=s.replace('void FoxScene::draw_match(unsigned short* fb){','''void FoxScene::draw_match(unsigned short* fb){
    // Scroll the original terrain in world coordinates, retaining a native QVGA framebuffer.
    for(int y=41;y<250;++y){int sy=(y+camera_y)%320;
        // Existing opaque VXA8 terrain stores RGB565 immediately after its 12-byte header.
        const unsigned char* row=duel_arena+12+sy*240*2;
        for(int x=0;x<240;++x)fb[y*240+x]=(unsigned short)(row[x*2]|(row[x*2+1]<<8));
    }
    for(auto& t:structures){int y=t.y-camera_y;if(y<55||y>246)continue;
        unsigned short c=t.owner?0xF980:0x57F7;
        vxpe2d_fill_rect(fb,240,320,100,y-35,40,35,t.hp?0x52AA:0x2945);
        if(t.hp){vxpe2d_fill_rect(fb,240,320,107,y-47,26,16,c);
            vxpe2d_fill_rect(fb,240,320,112,y-43,16,8,0xFFFF);
            bar(fb,95,y-56,50,t.hp,t.max_hp,c);text(fb,101,y-67,t.max_hp==1800?"CORE":"TOWER",c);
        }else text(fb,97,y-20,"RUINS",0xAD55);
    }
    for(auto& e:effects)if(e.life){int y=e.y-camera_y,r=12+(650-e.life)/14;
        unsigned short c=fighters[e.owner].skin?skin_tints[e.hero]:duel_heroes[e.hero].color;
        if(y<60||y>240)continue;
        if(e.hero==0){for(int n=0;n<4;++n){int d=r+n*4;vxpe2d_fill_rect(fb,240,320,e.x-d,y-22-n*6,2,12,c);vxpe2d_fill_rect(fb,240,320,e.x+d,y-22-n*6,2,12,c);}}
        else if(e.hero==1){for(int n=0;n<3;++n)vxpe2d_fill_rect(fb,240,320,e.x-r,y-n*5,r*2,2,c);}
        else {for(int n=0;n<5;++n)vxpe2d_fill_rect(fb,240,320,e.x-24+n*10,y-20-r+n*3,3,15,c);}
    }
''')
a=s.index('    int first=fighters');b=s.index('    vxpe2d_overlay_rect(fb,240,320,0,0',a);part=s[a:b];part=part.replace('const auto& f=fighters[i];const auto& h','auto f=fighters[i];f.y-=camera_y;if(f.hp<=0||f.y<70||f.y>249)continue;const auto& h');part=part.replace('p.x,p.y,9','p.x,p.y-camera_y,9').replace('p.x-2,p.y-2','p.x-2,p.y-camera_y-2');part=part.replace('vxpe_particles_draw(&particles,fb,240,320);','// World effects above replace screen-space particle rendering during lane play.');s=s[:a]+part+s[b:]
s=s.replace('"%s VS %s BOT",duel_heroes[fighters[0].hero].name,duel_heroes[fighters[1].hero].name','"CORE %d VS %d",structures[0].hp,structures[3].hp');s=s.replace('snprintf(value,sizeof(value),"1 HEAL %ds  * PAUSE",(p.heal_ms+999)/1000);','if(p.hp<=0)snprintf(value,sizeof(value),"RESPAWN %ds",(p.respawn_ms+999)/1000);\n    else snprintf(value,sizeof(value),"1 HEAL %ds  * PAUSE",(p.heal_ms+999)/1000);')
p.write_text(s)
