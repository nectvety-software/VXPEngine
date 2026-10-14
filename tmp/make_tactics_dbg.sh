#!/bin/sh
# Build and run the TacticsVanguard2D state dumper. It compiles main.c through
# tmp/tactics_dbg.c (which #includes it) so the app's statics are readable, so
# main.o must NOT be linked in alongside it or every symbol would collide.
set -e
cd "$(dirname "$0")/.."
SDK="/d/MRE/template/XimikBoda/third_party/mre-sdk/app/include"
INC="-I$SDK -Iengine/coremre/include -Iexamples/TacticsVanguard2D/src"
GCC=/c/msys64/mingw64/bin/gcc.exe
GXX=/c/msys64/mingw64/bin/g++.exe
mkdir -p tmp/tshots
$GCC -c -O1 -w $INC -o tmp/tshots/dbg.o tmp/tactics_dbg.c
$GCC -c -O1 -w $INC -o tmp/tshots/shim.o tmp/tactics_shim.c
for f in VxpRender2D VxpPixelFont; do
    [ -f "tmp/tshots/$f.o" ] || \
        $GXX -c -O1 -w $INC -o "tmp/tshots/$f.o" "engine/coremre/src/graphics/$f.cpp"
done
$GXX -O1 -w -o tmp/tshots/tactics_dbg.exe tmp/tshots/dbg.o tmp/tshots/shim.o \
    tmp/tshots/VxpRender2D.o tmp/tshots/VxpPixelFont.o
tmp/tshots/tactics_dbg.exe
