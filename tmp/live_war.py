from pathlib import Path
p=Path('examples/FoxRiftDemo/src/scene.cpp');s=p.read_text().replace('screen=DUEL_RESULT;held=paused=0;','screen=DUEL_RESULT;held=paused=shop_open=0;');p.write_text(s)
p=Path('examples/FoxRiftDemo/tests/preview.cpp');s=p.read_text().replace('save(s,"21_minion_siege.ppm");','s.minions[0].x=105;s.minions[0].y=425;save(s,"21_minion_siege.ppm");');s=s.replace('    s.input(-1);s.input(-1);assert(s.exiting);','''    // End-to-end lane economy over multiple live waves.
    s.selected=0;s.bot_selected=2;s.start_match();
    for(int frame=0;frame<1900&&s.screen==DUEL_MATCH;++frame){s.update();if(frame%500==0)save(s,"23_live_waves.ppm");}
    assert(s.wave_count>=5&&s.fighters[1].gold>=0&&s.fighters[1].items!=0);
    for(const auto& m:s.minions)if(m.active)assert(m.hp>0&&m.x>=26&&m.x<=214&&m.y>=80&&m.y<=880);
    s.input(-1);s.input(-1);assert(s.exiting);''');p.write_text(s)
