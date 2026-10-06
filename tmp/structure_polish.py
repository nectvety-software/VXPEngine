from pathlib import Path
p=Path('examples/FoxRiftDemo/src/scene.cpp');s=p.read_text();s=s.replace('vxpe2d_fill_rect(fb,240,320,100,y-35,40,35,t.hp?0x52AA:0x2945);','''vxpe2d_fill_rect(fb,240,320,96,y-6,48,7,0x2945);
        vxpe2d_fill_rect(fb,240,320,101,y-10,38,5,0xA514);
        vxpe2d_fill_rect(fb,240,320,107,y-35,26,25,t.hp?0x52AA:0x2945);
        vxpe2d_fill_rect(fb,240,320,108,y-33,4,22,0xAD55);
        vxpe2d_fill_rect(fb,240,320,129,y-33,3,22,0x3186);''');s=s.replace('vxpe2d_fill_rect(fb,240,320,107,y-47,26,16,c);','''vxpe2d_fill_rect(fb,240,320,101,y-38,38,5,0xB388);
            vxpe2d_fill_rect(fb,240,320,104,y-46,6,10,0xAD55);
            vxpe2d_fill_rect(fb,240,320,130,y-46,6,10,0xAD55);
            for(int n=0;n<8;++n)vxpe2d_fill_rect(fb,240,320,120-n,y-54+n,n*2+1,1,c);
            vxpe2d_fill_rect(fb,240,320,114,y-46,13,14,c);''');p.write_text(s)
