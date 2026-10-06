from pathlib import Path
p=Path('examples/FoxRiftDemo/tests/preview.cpp');s=p.read_text();s=s.replace('    s.input(-1);s.input(-1);assert(s.exiting);','''    // Export ready skill icons for all heroes and both teams' structures for visual review.
    for(int hero=0;hero<3;++hero){
        s.selected=hero;s.selected_skin=0;s.start_match();s.fighters[0].x=55;s.fighters[0].y=740;
        s.camera_y=560;char name[40];snprintf(name,sizeof(name),"13_icons_%d.ppm",hero);save(s,name);
    }
    s.fighters[0].y=835;s.camera_y=640;save(s,"14_blue_core.ppm");
    s.fighters[0].y=370;s.camera_y=180;save(s,"15_red_tower.ppm");
    s.structures[5].hp=0;save(s,"16_tower_ruins.ppm");
    s.fighters[0].y=150;s.camera_y=0;save(s,"17_red_core.ppm");
    s.structures[3].hp=0;save(s,"18_core_ruins.ppm");
    s.input(-1);s.input(-1);assert(s.exiting);''');p.write_text(s)
