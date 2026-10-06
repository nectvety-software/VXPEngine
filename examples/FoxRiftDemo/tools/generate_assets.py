"""Bake original Vaelora assets from saved sources; no online generation."""
from pathlib import Path
import json,struct
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
def encode(im):
    im=im.convert("RGBA");p=list(im.get_flattened_data());alpha=bytes(a for r,g,b,a in p)
    opaque=min(alpha)==255
    return struct.pack("<4sHHBBH",b"VXA8",im.width,im.height,int(opaque),1,12)+struct.pack("<"+"H"*len(p),*[((r>>3)<<11)|((g>>2)<<5)|(b>>3) for r,g,b,a in p])+(b"" if opaque else alpha)
def main():
    assets=ROOT/"assets"
    arena=Image.open(assets/"source/arena.png").convert("RGB")
    width=arena.height*3//4;x=(arena.width-width)//2
    arena=arena.crop((x,0,x+width,arena.height)).resize((240,320),Image.Resampling.NEAREST)
    arena.save(assets/"backgrounds/arena.png")
    source=Image.open(assets/"source/heroes.png").convert("RGBA")
    atlas=Image.new("RGBA",(192,256));frames=[]
    # Actual saved row gutters, expressed relative to original 1436px height.
    seams=[round(y*source.height/1436) for y in (0,382,755,1110,1436)]
    for row,pose in enumerate(("idle","walk","cast","portrait")):
        for col,name in enumerate(("velin","torvan","nimara")):
            piece=source.crop((col*source.width//3,seams[row],(col+1)*source.width//3,seams[row+1]))
            box=piece.getbbox()
            if not box:raise ValueError("Missing sprite")
            piece=piece.crop(box);ratio=min(60/piece.width,60/piece.height)
            piece=piece.resize((max(1,round(piece.width*ratio)),max(1,round(piece.height*ratio))),Image.Resampling.NEAREST)
            cell=Image.new("RGBA",(64,64));cell.alpha_composite(piece,((64-piece.width)//2,62-piece.height))
            cell.save(assets/f"sprites/{name}_{pose}.png");atlas.alpha_composite(cell,(col*64,row*64))
            frames.append(dict(name=name+"_"+pose,rect=[col*64,row*64,64,64],foot_anchor=[32,62]))
    atlas.save(assets/"sprites/heroes_atlas.png")
    (assets/"sprites/frames.json").write_text(json.dumps(dict(frame_size=[64,64],frames=frames),indent=2))
    logo=Image.open(assets/"source/logo.png").convert("RGBA");logo=logo.crop(logo.getbbox())
    ratio=min(200/logo.width,114/logo.height);logo=logo.resize((round(logo.width*ratio),round(logo.height*ratio)),Image.Resampling.NEAREST)
    logo_canvas=Image.new("RGBA",(200,114));logo_canvas.alpha_composite(logo,((200-logo.width)//2,(114-logo.height)//2))
    (assets/"ui").mkdir(exist_ok=True);logo_canvas.save(assets/"ui/logo.png")
    header=["#pragma once", "#include <stdint.h>"]
    for name,im in (("arena",arena),("heroes_atlas",atlas),("logo",logo_canvas)):
        data=encode(im);(assets/f"runtime/{name}.vxa8").write_bytes(data)
        header.append(f"alignas(4) static const uint8_t duel_{name}[]={{")
        header.extend(",".join(str(v) for v in data[i:i+32])+"," for i in range(0,len(data),32));header.append("};")
    (ROOT/"src/assets_generated.h").write_text("\n".join(header)+"\n")
    print("Baked 240x320 arena, 12 original hero frames and logo")
if __name__=="__main__":main()
