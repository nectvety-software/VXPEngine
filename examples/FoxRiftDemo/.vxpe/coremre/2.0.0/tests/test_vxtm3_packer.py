#!/usr/bin/env python3
import importlib.util
import json
import struct
import sys
import tempfile
from pathlib import Path

H=0x80000000
V=0x40000000
D=0x20000000

def load_module(path):
    spec=importlib.util.spec_from_file_location("vxpgdx_pack_tiled", path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def assert_raises(fn):
    try:
        fn()
    except Exception:
        return
    raise AssertionError("expected exception")

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: test_vxtm3_packer.py <vxpgdx_pack_tiled.py>")
    packer=load_module(Path(sys.argv[1]).resolve())

    expected=[
        0x0001,0x8001,0x4001,0xC001,
        0x2001,0xA001,0x6001,0xE001,
    ]
    raw=[
        1,1|H,1|V,1|H|V,
        1|D,1|H|D,1|V|D,1|H|V|D,
    ]
    got=[packer.encode_cell(x) for x in raw]
    assert got==expected,(got,expected)
    assert packer.encode_cell(0)==0xFFFF
    assert packer.encode_cell(8190)==8190
    assert_raises(lambda: packer.encode_cell(8191))

    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        tmj=td/"diag.tmj"
        out=td/"diag.vxtm"
        tmj.write_text(json.dumps({
            "orientation":"orthogonal",
            "width":4,"height":2,
            "tilewidth":16,"tileheight":16,
            "infinite":False,
            "tilesets":[{
                "firstgid":1,"name":"diag",
                "tilewidth":16,"tileheight":16,
                "tilecount":1,"columns":1
            }],
            "layers":[{
                "type":"tilelayer","name":"Diag",
                "width":4,"height":2,
                "visible":True,"opacity":1.0,
                "data":raw,
            }]
        }),encoding="utf-8")

        packer.pack_map(tmj,out,None)
        blob=out.read_bytes()
        assert blob[:4]==b"VXTM"
        assert blob[4]==3
        assert blob[5]==0
        assert blob[6]==1
        assert blob[7]==1

        # header 24 + one 8-byte tileset + one 28-byte tile-layer header.
        cell_offset=24+8+28
        cells=list(struct.unpack_from("<8H",blob,cell_offset))
        assert cells==expected,(cells,expected)

        # Truncation/limits remain deterministic.
        bad=td/"bad.tmj"
        bad.write_text(json.dumps({
            "orientation":"orthogonal",
            "width":1,"height":1,
            "tilewidth":16,"tileheight":16,
            "infinite":False,
            "tilesets":[{
                "firstgid":8191,"name":"overflow",
                "tilewidth":16,"tileheight":16,
                "tilecount":1,"columns":1
            }],
            "layers":[{
                "type":"tilelayer","name":"Bad",
                "width":1,"height":1,
                "data":[8191],
            }]
        }),encoding="utf-8")
        assert_raises(lambda: packer.pack_map(bad,td/"bad.vxtm",None))

    print("VXPGDX_VXTM3_PACKER_REGRESSION_PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
