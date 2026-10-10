# Lost in Latency: Mall Memory

First-person perspective sample for VXPEngine on 240×320 S30+ MRE devices. The mall clip supplies atrium/food-court/aquarium scene cues; the Skate 3 clips are references for continuous 3D camera movement and workload. Gameplay is mall exploration: cross four zones and scan the original QR memory plaques.

Controls: `2/8` walk, `4/6` turn, `5` scan/start, `0` journal, `9` pause, Back returns to menu/exit. The 3D world renders at 120×160 then uses core Scale2x to fill the native screen; UI stays at 240×320.

Build a signed ARM VXP from this checkout with `scripts\build_arm.bat`. Run host tests with `cmake -S tests -B build-host -G Ninja`, `cmake --build build-host`, then `ctest --test-dir build-host --output-on-failure`.

The static world color/depth buffers use 76,800 bytes total; cache stores only one byte of QR progress. The sky pass uses the core depth-only clear and the rasterizer skips projected triangles fully outside the viewport. See [graphics and art notes](docs/GRAPHICS_AND_ART.md).
