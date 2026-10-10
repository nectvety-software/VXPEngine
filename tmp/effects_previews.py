from pathlib import Path
p=Path('examples/FoxRiftDemo/tests/preview.cpp');s=p.read_text();s=s.replace('    s.input(-1);s.input(-1);assert(s.exiting);','''    // Render animated ability sequences with the bot and basic attacks held still.
    for(int hero=0;hero<3;++hero)for(int skill=0;skill<4;++skill){
        s.selected=hero;s.bot_selected=1;s.selected_skin=0;s.start_match();
        s.fighters[0].x=100;s.fighters[0].y=500;s.fighters[1].x=150;s.fighters[1].y=500;s.camera_y=310;
        s.fighters[1].stun_ms=1900;s.cast(skill);
        bool spawned=false;for(const auto& e:s.effects)if(e.life)spawned=true;assert(spawned);
        int effect_life=s.effects[0].life;s.input(10);step(s,5);assert(s.effects[0].life==effect_life);s.input(10);
        for(int frame=0;frame<40;++frame){
            s.fighters[1].stun_ms=1900;s.fighters[0].attack_ms=s.fighters[1].attack_ms=999;
            if(frame%4==0){char name[64];snprintf(name,sizeof(name),"fx_%d_%d_%02d.ppm",hero,skill,frame/4);save(s,name);}
            s.update();
        }
        for(int frame=0;frame<20;++frame){s.fighters[1].stun_ms=1900;s.fighters[0].attack_ms=s.fighters[1].attack_ms=999;s.update();}
        for(const auto& e:s.effects)assert(e.life==0);
        s.restart();for(const auto& e:s.effects)assert(e.life==0);for(const auto& p:s.projectiles)assert(!p.active);
    }
    // Binding impact is generated only by a real projectile collision.
    setup(s,0);s.fighters[1].stun_ms=1900;s.cast(2);step(s,12);
    bool bound=false;for(const auto& e:s.effects)if(e.life&&e.impact&&e.skill==2)bound=true;assert(bound);
    // Clipped VFX cannot bleed through translucent HUD panels at viewport boundaries.
    s.selected=0;s.start_match();s.cast(3);s.effects[0].x=0;s.effects[0].y=s.camera_y+42;
    unsigned short with_fx[240*320],without_fx[240*320];s.draw(with_fx);
    for(auto& e:s.effects)e.life=0;for(auto& p:s.projectiles)p.active=0;s.draw(without_fx);
    for(int y=0;y<320;++y)if(y<41||y>=250)for(int x=0;x<240;++x)assert(with_fx[y*240+x]==without_fx[y*240+x]);
    s.input(-1);s.input(-1);assert(s.exiting);''');p.write_text(s)
