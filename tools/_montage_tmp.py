import base64,os,glob
base='examples/PromisedFutureDemo/docs'
names=['tower_only.png','tower_only_exact.png','noband_tower.png','shell.png','shell_exact.png','fixed.png','sbs.png','aff_compare.png','tower_crop.png','tower_hole_crop.png']
root='examples/PromisedFutureDemo'
extra=['promised_future_title.png','promised_future_island.png']
items=[]
for n in names:
    p=os.path.join(base,n)
    if os.path.exists(p): items.append((n,p))
for n in extra:
    p=os.path.join(root,n)
    if os.path.exists(p): items.append((n,p))
parts=['<html><head><style>body{background:#111;color:#ddd;font:12px monospace}.g{display:flex;flex-wrap:wrap;gap:14px}figure{margin:0}img{image-rendering:pixelated;background:#333;border:1px solid #555;max-width:420px}</style></head><body><h3>PromisedFuture render artifacts</h3><div class="g">']
for n,p in items:
    b=base64.b64encode(open(p,'rb').read()).decode()
    parts.append('<figure><figcaption>%s (%d B)</figcaption><img src="data:image/png;base64,%s"></figure>'%(n,os.path.getsize(p),b))
parts.append('</div></body></html>')
open('tmp/pf_montage.html','w',encoding='utf-8').write(''.join(parts))
print('wrote', len(items), 'images')
