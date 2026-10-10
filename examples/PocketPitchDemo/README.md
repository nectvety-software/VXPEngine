# Pocket Pitch

Original 240×320 portrait arcade soccer pinball game for VXPEngine/MRE.

Build a signed ARM package from the VXPEngine checkout:

```bat
scripts\build_arm.bat
```

The game uses the number pad: `4/6` flippers, `5` kick/start, `2/8` launch lane, `1/3` curve skills, `9` pause, and Back for menu/exit. Touch controls work on the lower flipper area. The match lasts 45 seconds; goals award points and the best score is cached under `@vxp_1869076` on removable storage or system storage fallback.

Run the host regression with the engine's w64devkit CMake/Ninja:

```bat
D:\MRE\lib\w64devkit\bin\cmake.exe -S tests -B build-host -G Ninja -DCMAKE_MAKE_PROGRAM=D:/MRE/lib/w64devkit/bin/ninja.exe -DCMAKE_CXX_COMPILER=D:/MRE/lib/w64devkit/bin/g++.exe
D:\MRE\lib\w64devkit\bin\cmake.exe --build build-host
D:\MRE\lib\w64devkit\bin\ctest.exe --test-dir build-host --output-on-failure
```

The game state is fixed-size, has five bumpers and twelve particles, and allocates no memory in its update/render loops.

See [ART_AND_GAMEPLAY.md](docs/ART_AND_GAMEPLAY.md) for mechanics and art provenance.
