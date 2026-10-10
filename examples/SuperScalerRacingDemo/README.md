# Horizon Rider — Super Scaler test game

Original 240×320 portrait arcade racer for VXPEngine/MRE. It recreates the broad visual language of classic Super Scaler racers with a fixed-point scanline road, changing bends, alternating curbs, textured terrain, layered mesas, roadside cactus/rocks, cast shadows and depth-scaled traffic. The rider and scenery use original RGB565 pixel primitives and swatches; no game logos or copied sprites are included. Native 8×8 road/sand swatches are available under `assets/pixel_art/` for Editor Assets.

Controls: `4/6` steer, `2` accelerate, `8` brake, `5` boost/start, `9` pause/resume, `0` return to title, Back pauses or exits from title. The best score is saved as a small versioned cache in `\@vxp_001c8520\` on removable storage, with system storage fallback. The sample keeps three traffic records and the device framebuffer; update/draw allocate no heap memory.

Build for ARM/MRE from this checkout:

```bat
scripts\build_arm.bat
scripts\run_vxpemu.bat
```

Host regression:

```bat
cmake -S tests -B build-host -G "MinGW Makefiles"
cmake --build build-host
ctest --test-dir build-host --output-on-failure
```

The scanline renderer uses a 257-byte compile-time Q8 depth LUT, one reciprocal per frame, integer span fills and caller-owned RGB565 output. Regenerate pixel sources with `python tools/generate_pixel_assets.py`. Host regression verifies texture sampling, road bounds, curvature, controls, traffic motion and pause behavior. Device FPS must be measured on the target handset; host timing does not establish a 25–30 FPS device result.
