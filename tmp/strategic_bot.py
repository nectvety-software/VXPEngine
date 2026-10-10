from pathlib import Path
p=Path('examples/FoxRiftDemo/src/scene.cpp');s=p.read_text().replace('i%3?900:1800,0};','i%3?900:1800,0,0};');s=s.replace('if(dist(a,b)>180&&farm>=0)','if((b.hp<=0||dist(a,b)>180)&&farm>=0)');s=s.replace('bool retreat=bot.hp<h.max_hp*30/100;','bool retreat=bot.hp<max_hp(1)*30/100;').replace('bot.hp<h.max_hp*65/100','bot.hp<max_hp(1)*65/100');s=s.replace('        int y=structures[target].y;','''        int y=structures[target].y;
        if(h.attack_range<100&&absi(bot.y-y)+absi(bot.x-120)<150){
            bool cover=false;for(const auto& m:minions)if(m.active&&m.owner==1&&absi(m.x-120)+absi(m.y-y)<105)cover=true;
            if(!cover){if(absi(bot.y-y)+absi(bot.x-120)<125)bot_move(0,-1);return;}
        }''');p.write_text(s)
p=Path('examples/FoxRiftDemo/tests/preview.cpp');s=p.read_text().replace('step(s,200); assert(s.structures[2].hp<900);','step(s,200); assert(s.fighters[1].y>240);');p.write_text(s)
