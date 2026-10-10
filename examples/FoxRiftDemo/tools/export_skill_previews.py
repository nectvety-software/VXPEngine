from pathlib import Path
from PIL import Image,ImageDraw
root=Path('examples/FoxRiftDemo');src=root/'build-preview';out=root/'tests/runtime_screenshots/skill_fx';out.mkdir(parents=True,exist_ok=True)
names=[['PRISM BOLT','LIGHT BURST','ANCHOR RAY','PRISM NOVA'],['HAMMER ARC','IRON GUARD','CHARGE','EARTHBREAK'],['WIND BOLT','GUST STEP','PINNING SHOT','ARROWSTORM']]
montage=[]
for frame in range(10):
    board=Image.new('RGB',(960,1020),(8,16,24));draw=ImageDraw.Draw(board)
    for h in range(3):
        for k in range(4):
            im=Image.open(src/f'fx_{h}_{k}_{frame:02}.ppm').convert('RGB')
            board.paste(im,(k*240,h*340+20));draw.text((k*240+6,h*340+4),['VELIN','TORVAN','NIMARA'][h]+' / '+names[h][k],fill=['#dbb9ff','#ffd797','#87ffea'][h])
    montage.append(board)
for h in range(3):
    for k in range(4):
        frames=[Image.open(src/f'fx_{h}_{k}_{f:02}.ppm').convert('RGB') for f in range(10)]
        frames[0].save(out/f'hero_{h}_skill_{k}.gif',save_all=True,append_images=frames[1:],duration=132,loop=0,disposal=2)
        frames[3].save(out/f'hero_{h}_skill_{k}.png')
montage[0].save(out/'all_12_skills.gif',save_all=True,append_images=montage[1:],duration=132,loop=0,disposal=2)
montage[3].save(out/'all_12_skills.png')
print('Exported 12 animated skill previews plus comparison grid')
