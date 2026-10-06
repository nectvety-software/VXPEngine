from pathlib import Path
p=Path('examples/FoxRiftDemo/src/scene.cpp');s=p.read_text().replace('if(t.hp<=0)continue;t.attack_ms','if(t.hp<=0)continue;\n        t.attack_ms').replace(');text(fb,51,311,value,0xEDEB);',');\n    text(fb,51,311,value,0xEDEB);');s=s.replace('int w,int h,int flip){','int w,int h,int flip,int skin){');a=s.index('    int skin=screen==DUEL_SELECT');b=s.index('    if(skin)b.tint565',a);s=s[:a]+s[b:];s=s.replace('sprite(fb,i,3,x+35,111,62,62);','sprite(fb,i,3,x+35,111,62,62,0,i==selected?selected_skin:0);');s=s.replace('f.x,f.y,60,60,f.facing);','f.x,f.y,60,60,f.facing,f.skin);').replace('sprite(fb,p.hero,3,26,291,40,40);','sprite(fb,p.hero,3,26,291,40,40,0,p.skin);');p.write_text(s)
p=Path('examples/FoxRiftDemo/src/scene.h');s=p.read_text().replace('int flip=0);','int flip=0,int skin=0);');p.write_text(s)
p=Path('examples/FoxRiftDemo/tests/preview.cpp');s=p.read_text();a=s.index('    setup(s,0);s.hit(0,10000);');b=s.index('    s.input(-1);s.input(-1);',a);s=s[:a]+'''    setup(s,0);s.hit(0,10000);assert(s.screen==DUEL_MATCH&&s.fighters[1].hp==0);
    step(s,154);assert(s.fighters[1].hp>0&&s.fighters[1].y<250);
    s.damage_structure(0,3,9999);assert(s.structures[3].hp==1800);
    s.damage_structure(0,4,9999);assert(s.structures[4].hp==900);
    s.damage_structure(0,5,9999);s.damage_structure(0,4,9999);s.damage_structure(0,3,9999);
    assert(s.screen==DUEL_RESULT&&s.result==1);save(s,"09_victory.ppm");s.input(5);
    s.damage_structure(1,2,9999);s.damage_structure(1,1,9999);s.damage_structure(1,0,9999);
    assert(s.screen==DUEL_RESULT&&s.result==-1);save(s,"10_defeat.ppm");s.input(-1);
    s.input(7);s.input(9);assert(s.selected_skin==1&&s.bot_skin==1);s.start_match();
    assert(s.fighters[0].skin==1&&s.fighters[1].skin==1);
    int initial=s.camera_y;s.hold(2,true);step(s,80);s.hold(2,false);assert(s.camera_y<initial);save(s,"12_lane_skin.ppm");
    s.time_ms=299999;s.update();assert(s.result==2);save(s,"11_draw.ppm");
''' + s[b:];s=s.replace('knockout/time limit','respawn, guarded towers/core victory, camera, skins/time limit');p.write_text(s)
