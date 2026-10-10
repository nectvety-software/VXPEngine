from pathlib import Path
p=Path('examples/FoxRiftDemo/tools/generate_army_assets.py');s=p.read_text().replace('box=piece.getbbox()','box=piece.getchannel("A").point(lambda a:255 if a>=128 else 0).getbbox()');s=s.replace('piece=piece.crop(box);ratio=','l,t,r,b=box;box=(max(0,l-6),max(0,t-6),min(piece.width,r+6),min(piece.height,b+6));piece=piece.crop(box);ratio=');p.write_text(s)
p=Path('examples/FoxRiftDemo/src/scene.cpp');s=p.read_text();s=s.replace('if(farm>=0){const auto& m=minions[farm];int d=absi(bot.x-m.x)+absi(bot.y-m.y);','''if(farm>=0){const auto& m=minions[farm];int d=absi(bot.x-m.x)+absi(bot.y-m.y);
            if(h.attack_range<100){for(int j=0;j<3;++j)if(structures[j].hp>0&&absi(m.x-120)+absi(m.y-structures[j].y)<105){
                bool cover=false;for(const auto& ally:minions)if(ally.active&&ally.owner==1&&absi(ally.x-120)+absi(ally.y-structures[j].y)<105)cover=true;
                if(!cover)return;
            }}''');p.write_text(s)
p=Path('examples/FoxRiftDemo/tools/prepare_scene.py');s=p.read_text();a=s.index('    for col,name in enumerate(("velin","torvan","nimara")):');s=s[:a]+'''    for row,name in enumerate(("velin","torvan","nimara")):
        animation=dict(format="VXPEngine Animation",format_version=2,extension=".ani..dtfe",asset="assets/sprites/action_poses_atlas.png",texture="assets/sprites/action_poses_atlas.png",source_mode="atlas_frames",asset_kind="character",package="atlas+descriptor",animation=dict(name=name+"_walk",fps=8,loop=True,frame_count=2,source_mode="atlas_frames",asset_kind="character",selected_indices=[row*6,row*6+1]),frames=[dict(name=name+"_run_"+str(i),x=i*48,y=row*48,width=48,height=48,source_index=row*6+i,duration_ms=120) for i in range(2)])
        (ROOT/f"assets/sprites/{name}_walk.ani..dtfe").write_text(json.dumps(animation,indent=2))
    print("Prepared editable screens, environment and two-frame hero running animations")
if __name__=="__main__":main()
''';p.write_text(s)
