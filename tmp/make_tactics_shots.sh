#!/bin/sh
# Rebuild and run the TacticsVanguard2D host screen harness, then compose the
# contact sheets. The engine objects only depend on coremre, so they are
# compiled once and kept between runs.
set -e
cd "$(dirname "$0")/.."
SDK="/d/MRE/template/XimikBoda/third_party/mre-sdk/app/include"
INC="-I$SDK -Iengine/coremre/include -Iexamples/TacticsVanguard2D/src"
GCC=/c/msys64/mingw64/bin/gcc.exe
GXX=/c/msys64/mingw64/bin/g++.exe
mkdir -p tmp/tshots
$GCC -c -O1 -w $INC -o tmp/tshots/main.o examples/TacticsVanguard2D/src/main.c
$GCC -c -O1 -w $INC -o tmp/tshots/shim.o tmp/tactics_shim.c
$GCC -c -O1 -w $INC -o tmp/tshots/shots.o tmp/tactics_shots.c
for f in VxpRender2D VxpPixelFont; do
    [ -f "tmp/tshots/$f.o" ] || \
        $GXX -c -O1 -w $INC -o "tmp/tshots/$f.o" "engine/coremre/src/graphics/$f.cpp"
done
$GXX -O1 -w -o tmp/tshots/tactics_shots.exe tmp/tshots/main.o tmp/tshots/shim.o \
    tmp/tshots/shots.o tmp/tshots/VxpRender2D.o tmp/tshots/VxpPixelFont.o
rm -f tmp/tshots/*.565
tmp/tshots/tactics_shots.exe
# The msys python on PATH has no Pillow, and the py launcher resolves to a
# different install when it runs a script under tools/, so name it outright.
/d/Program/Python/python.exe tmp/tactics_sheet.py
