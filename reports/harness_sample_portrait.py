from pathlib import Path
import json
count=0
for folder in Path('examples').iterdir():
    project=folder/'project.vxp.json'
    if not project.is_file():continue
    data=json.loads(project.read_text(encoding='utf-8'));assert (data['screen']['width'],data['screen']['height'])==(240,320),folder
    for scene in (folder/'assets').rglob('*.dtfe'):
        try:data=json.loads(scene.read_text(encoding='utf-8'))
        except ValueError:continue
        if isinstance(data,dict) and isinstance(data.get('viewport'),dict):assert (data['viewport']['width'],data['viewport']['height'])==(240,320),scene
    count+=1
assert count==13
print('PASS: all 13 sample project descriptors and scene viewports are portrait 240x320')
