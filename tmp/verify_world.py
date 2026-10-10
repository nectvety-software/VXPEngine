from pathlib import Path
p=Path('examples/FoxRiftDemo/src/scene.cpp');s=p.read_text().replace('f.cast_ms?2:((i?dist(fighters[i],fighters[0])>40:held)?1:0)','f.cast_ms?2:(f.moving?1:0)');s=s.replace('b.blend=VXPE_BLEND_ALPHA;vxpe2d_blit_a8(fb,240,320,&heroes,&b);','if(screen==DUEL_MATCH&&row!=3){b.clip_x=0;b.clip_y=41;b.clip_w=240;b.clip_h=209;}\n    b.blend=VXPE_BLEND_ALPHA;vxpe2d_blit_a8(fb,240,320,&heroes,&b);');p.write_text(s)
p=Path('examples/FoxRiftDemo/tests/preview.cpp');s=p.read_text().replace('    // Export ready skill icons','''    // Solid world geometry, grass passage, swept skills and bot navigation.
    s.selected=0;s.start_match();s.fighters[0].x=50;s.fighters[0].y=280;
    s.fighters[1].x=200;s.fighters[1].y=100;s.fighters[1].stun_ms=1900;
    assert(s.walkable(50,280)&&!s.walkable(50,300));
    s.hold(8,true);step(s,12);s.hold(8,false);assert(s.fighters[0].y==285&&s.walkable(s.fighters[0].x,s.fighters[0].y));
    s.fighters[0].x=202;s.fighters[0].y=575;s.hold(6,true);s.hold(8,true);step(s,8);s.hold(6,false);s.hold(8,false);
    assert(s.fighters[0].x==203&&s.fighters[0].y>575); // Slide along vertical wall.
    s.fighters[0].x=40;s.fighters[0].y=365;s.hold(8,true);step(s,8);s.hold(8,false);assert(s.fighters[0].y==381); // Tall grass is walkable.
    s.selected=1;s.start_match();s.fighters[0].x=50;s.fighters[0].y=280;s.fighters[1].x=50;s.fighters[1].y=340;
    s.cast(2);assert(s.fighters[0].y==285); // A 45px charge cannot tunnel through wall.
    s.selected=2;s.start_match();s.fighters[0].x=50;s.fighters[0].y=280;s.fighters[1].x=50;s.fighters[1].y=240;
    s.cast(1);assert(s.fighters[0].y==285); // Backward wind dash also sweeps collision.
    s.selected=0;s.bot_selected=1;s.start_match();s.fighters[0].x=65;s.fighters[0].y=850;s.fighters[0].stun_ms=1900;
    s.fighters[1].x=120;s.fighters[1].y=190;step(s,140);
    assert(s.fighters[1].y>240&&s.walkable(s.fighters[1].x,s.fighters[1].y)); // Bot gets around its own tower.
    s.start_match();assert(!s.walkable(120,350));s.damage_structure(0,5,900);assert(s.walkable(120,350));
    for(int y=80;y<=880;y+=80){s.fighters[0].x=82;s.fighters[0].y=y;s.camera_y=y<190?0:(y>830?640:y-190);char name[40];snprintf(name,sizeof(name),"19_world_%03d.ppm",y);save(s,name);}
    // Export ready skill icons''');p.write_text(s)
p=Path('examples/FoxRiftDemo/.vxpe/platform/main/CMakeLists.txt');s=p.read_text();s+='''
# Editable world placement drives runtime collision and environment rendering.
add_custom_command(OUTPUT "${CMAKE_SOURCE_DIR}/src/world_generated.h"
    COMMAND "${VXPE_PYTHON}" "${CMAKE_SOURCE_DIR}/tools/generate_world.py"
    DEPENDS "${CMAKE_SOURCE_DIR}/assets/gameplay/world.json" "${CMAKE_SOURCE_DIR}/tools/generate_world.py"
    VERBATIM)
add_custom_target(vaelora_world DEPENDS "${CMAKE_SOURCE_DIR}/src/world_generated.h")
add_dependencies(${TARGET_NAME} vaelora_world)
''';p.write_text(s)
p=Path('examples/FoxRiftDemo/tools/prepare_scene.py');s=p.read_text();s=s.replace('bg=node("Arena","assets/backgrounds/arena.png",0,0,240,320,-10)','bg=node("Arena","assets/backgrounds/lane_ground.png",0,0,240,320,-10)');s=s.replace('    for screen in ("main"','    world=json.loads((ROOT/"assets/gameplay/world.json").read_text())\n    environment=[]\n    for o in world["objects"]:\n        x,y=o["position"];w,h=o["size"]\n        n=node(o["id"],o["asset"],x+w/2-120,y+h/2-720,w,h,y+h)\n        n["world_position"]=o["position"];n["collision"]=dict(solid=o["solid"],rect=o["collision"])\n        environment.append(n)\n    for screen in ("main"');s=s.replace('extra=actors+combat if screen','extra=environment+actors+combat if screen');p.write_text(s)
