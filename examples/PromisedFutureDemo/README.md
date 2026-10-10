# Promised Future

Original low-poly / pixel-filtered 3D exploration sample for VXPEngine at 240×320. It adapts the reference video's sunny eco-city mood: turquoise sea and sky, curved white-and-cyan towers, tropical greenery, floating bubbles and bright cloud colors. No video frames, logos, architecture textures, characters, or audio are bundled.

Walk the island promenade and scan four eco beacons to open short journal memories. Controls: `2/8` walk, `4/6` turn, `5` scan/start, `0` journal, `9` pause, Back returns to menu or exits. Player progress is stored as a four-bit payload in the versioned public cache at `@vxp_003000791`, with removable storage preferred and system storage as fallback.

The renderer uses the core low-poly polygon pipeline with a 120×160 RGB565 target and per-pixel depth buffer, then scales to 240×320. One sun drives per-vertex cel lighting across the arcologies, islands and palms; the sky is a dithered gradient with a sun glow and a horizon haze band, and the lagoon glints swell on a frame-counter wave with a surf line around each island. Color + depth use 76,800 bytes. Islands, tiered arcologies, clouds, palms, and water reflections are deterministic world-space geometry; the frame loop does not allocate memory or decode images.

## Build and test

Run `scripts\build_arm.bat` to build and sign the `.vxp`, or open this folder in VXPEngine. Output: `build-arm\main\promised_future_signed.vxp`. `scripts\run_vxpemu.bat` builds and opens it in VXPEmu. Host gameplay/bounds test:

```powershell
cmake -S tests -B build-host -G Ninja
cmake --build build-host
ctest --test-dir build-host --output-on-failure
```

Visual notes and the project-specific art brief are in `docs\GRAPHICS_AND_ART.md` and `docs\ART_PROVENANCE.md`.
