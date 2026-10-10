from pathlib import Path
p=Path('examples/FoxRiftDemo/tests/preview.cpp');s=p.read_text();s=s.replace('    s.input(-1);s.input(-1);assert(s.exiting);','''    // Symmetric minion waves and periodic siege carts.
    s.selected=0;s.start_match();s.spawn_wave();int blue=0,red=0,carts=0;
    for(const auto& m:s.minions)if(m.active){m.owner?++red:++blue;if(m.kind==2)++carts;}
    assert(blue==3&&red==3&&carts==0);s.spawn_wave();s.spawn_wave();carts=0;
    for(const auto& m:s.minions)if(m.active&&m.kind==2)++carts;assert(carts==2);
    // Exact last-hit bounty, no duplicate reward and no gold from allied kills.
    s.start_match();s.minions[0]={1,1,0,150,500,20,220,0,0,0};int money=s.fighters[0].gold;
    s.hurt_minion(0,0,30);assert(s.fighters[0].gold==money+32&&s.fighters[0].last_hits==1);
    s.hurt_minion(0,0,30);assert(s.fighters[0].gold==money+32);
    s.minions[1]={1,0,0,150,500,20,220,0,0,0};s.hurt_minion(0,1,30);assert(s.minions[1].hp==20);
    // Skills can farm a wave, and ranged spells acquire minions when the hero is distant.
    s.start_match();s.fighters[0].x=100;s.fighters[0].y=500;s.fighters[1].x=179;s.fighters[1].y=100;
    s.minions[0]={1,1,0,140,500,100,220,0,0,0};s.minions[1]={1,1,0,150,500,100,220,0,0,0};s.cast(1);
    assert(s.fighters[0].last_hits==2&&s.fighters[0].gold==184);
    s.start_match();s.fighters[0].x=100;s.fighters[0].y=500;s.fighters[1].x=179;s.fighters[1].y=100;s.fighters[1].stun_ms=1900;
    s.minions[0]={1,1,1,150,500,100,150,1000,0,0};s.fighters[0].attack_ms=999;s.cast(0);step(s,12);assert(s.fighters[0].last_hits==1);
    // Shop uses one wallet, unique items and persistent stats through death/respawn.
    s.start_match();s.input(11);assert(s.shop_open);s.input(5);assert(s.fighters[0].gold==0&&s.attack_power(0)==48);
    assert(!s.buy_item(0,0)&&!s.buy_item(0,1));s.fighters[0].gold=1000;
    for(int i=1;i<6;++i)assert(s.buy_item(0,i));
    assert(s.fighters[0].items==63&&s.fighters[0].gold==300&&s.max_hp(0)==1480&&s.max_mana(0)==760&&s.move_speed(0)==3&&s.attack_delay(0)==670&&s.skill_power(0)==25);
    save(s,"20_equipment_shop.ppm");s.input(11);int hp=s.fighters[0].hp;s.take_damage(0,100);assert(s.fighters[0].hp==hp-88);
    s.hit(1,10000);step(s,155);assert(s.fighters[0].hp==s.max_hp(0)&&s.fighters[0].items==63);
    // Towers shoot minions first, but attacking a defended hero draws tower aggro.
    s.start_match();s.fighters[0].x=86;s.fighters[0].y=320;s.fighters[0].attack_ms=999;
    s.fighters[1].x=150;s.fighters[1].y=330;s.fighters[1].attack_ms=999;
    s.minions[0]={1,0,0,86,330,220,220,999,0,0};hp=s.fighters[0].hp;s.lane_update(33);
    assert(s.fighters[0].hp==hp&&s.minions[0].hp==145);s.hit(0,10);s.structures[5].attack_ms=0;s.lane_update(33);assert(s.fighters[0].hp<hp);
    // A siege cart's cannon damages the next unlocked tower.
    s.start_match();s.fighters[0].x=65;s.fighters[0].y=850;s.minions[0]={1,0,2,86,330,480,480,0,0,0};s.army_update(33);assert(s.structures[5].hp==804);
    s.camera_y=200;s.fighters[0].x=100;s.fighters[0].y=390;s.minions[1]={1,0,0,90,375,220,220,0,0,1};s.minions[2]={1,1,0,150,385,220,220,0,0,1};s.minions[3]={1,1,1,150,415,150,150,0,0,0};save(s,"21_minion_siege.ppm");
    s.start_match();for(int i=0;i<12;++i)s.spawn_wave();int count=0;for(const auto& m:s.minions)if(m.active)++count;assert(count==48);save(s,"22_waves.ppm");
    s.input(10);int waves=s.wave_count,gold=s.fighters[0].gold;step(s,100);assert(s.wave_count==waves&&s.fighters[0].gold==gold);s.input(10);
    s.restart();assert(s.fighters[0].items==0&&s.fighters[0].gold==120&&s.wave_count==0);for(const auto& m:s.minions)assert(!m.active);
    // Basic attack targets vulnerable enemy minions and the bot buys according to its archetype.
    s.start_match();s.fighters[0].x=100;s.fighters[0].y=500;s.fighters[1].stun_ms=1900;s.minions[0]={1,1,0,120,500,5,220,999,0,0};s.army_update(33);assert(s.fighters[0].last_hits==1&&s.fighters[0].basic_ms>0);
    s.bot_selected=2;s.start_match();s.fighters[1].gold=150;s.army_update(33);assert(s.fighters[1].items==(1<<4)&&s.fighters[1].gold==0);
    s.input(-1);s.input(-1);assert(s.exiting);''');p.write_text(s)
