"""Validate editable hero stats and emit the shared player/bot roster."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    heroes=json.loads((ROOT/"assets/gameplay/heroes.json").read_text())["heroes"]
    if [h["id"] for h in heroes]!=["velin","torvan","nimara"]:raise ValueError("Keep the three archetypes in order")
    header=['#pragma once','const HeroDef duel_heroes[3]={']
    for h in heroes:
        for k,limit in (("name",6),("role",24),("passive",32)):
            value=h[k]
            if not isinstance(value,str) or not 1<=len(value)<=limit or any(ord(c)<32 or ord(c)>126 for c in value):raise ValueError("Invalid ASCII "+k)
        if len(h["skills"])!=4 or any(not isinstance(v,str) or not 1<=len(v)<=20 or any(ord(c)<32 or ord(c)>126 for c in v) for v in h["skills"]):raise ValueError("Invalid skills")
        limits=dict(max_hp=(1,5000),max_mana=(1,2000),speed=(1,4),attack=(1,300),attack_range=(10,180),attack_cd=(100,1000),color=(0,65535))
        for k,(lo,hi) in limits.items():
            if type(h[k]) is not int or not lo<=h[k]<=hi:raise ValueError("Invalid stat "+k)
        for k,lo,hi in (("cost",1,h["max_mana"]),("cd",100,7000)):
            if len(h[k])!=4 or any(type(v) is not int or not lo<=v<=hi for v in h[k]):raise ValueError("Invalid "+k)
        quote=json.dumps
        values=[quote(h[k]) for k in ("name","role","passive")]
        values.append('{'+','.join(map(quote,h["skills"]))+'}')
        values.extend(str(h[k]) for k in ("max_hp","max_mana","speed","attack","attack_range","attack_cd"))
        values.extend('{'+','.join(map(str,h[k]))+'}' for k in ("cost","cd"))
        values.append(str(h["color"]))
        header.append('{'+','.join(values)+'},')
    header.append('};')
    (ROOT/"src/hero_roster_generated.h").write_text('\n'.join(header)+'\n')
    print("Validated and generated three original hero definitions")
if __name__=="__main__":main()
