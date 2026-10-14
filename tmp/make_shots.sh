#!/bin/sh
# Rebuild and run the StormArena25D host screen harness, then compose the sheet.
# The engine objects only depend on coremre, so they are compiled once and kept.
set -e
cd "$(dirname "$0")/.."
SDK="/d/MRE/template/XimikBoda/third_party/mre-sdk/app/include"
INC="-I$SDK -Iengine/coremre/include -Iexamples/StormArena25D/src"
GCC=/c/msys64/mingw64/bin/gcc.exe
GXX=/c/msys64/mingw64/bin/g++.exe
mkdir -p tmp/shots
$GCC -c -O1 -w $INC -o tmp/shots/main.o examples/StormArena25D/src/main.c
$GCC -c -O1 -w $INC -o tmp/shots/shim.o tmp/storm_shim.c
$GCC -c -O1 -w $INC -o tmp/shots/shots.o tmp/storm_shots.c
for f in VxpRender2D VxpSpriteFx VxpScene25D VxpVfx2D VxpPixelFont; do
    [ -f "tmp/shots/$f.o" ] || \
        $GXX -c -O1 -w $INC -o "tmp/shots/$f.o" "engine/coremre/src/graphics/$f.cpp"
done
$GXX -O1 -w -o tmp/shots/storm_shots.exe tmp/shots/main.o tmp/shots/shim.o \
    tmp/shots/shots.o tmp/shots/Vxp*.o
rm -f tmp/shots/*.565
tmp/shots/storm_shots.exe
PYTHONIOENCODING=utf-8 python tmp/shots_sheet.py
