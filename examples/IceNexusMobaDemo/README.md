# IceNexusMobaDemo

VXPEngine sample game rendered natively at 240x320 portrait.

Features:
- native MRE QVGA portrait framebuffer, no landscape rotate-blit
- full-colour VXA8 isometric tile atlas cached into the RGB565 scene
- VXA8 per-pixel alpha sprites for Ariya, Nexus and the Q/W/E/R skill atlas
- baked anti-aliased outlines, static cached Nexus illumination and low-resolution RGB565 dynamic lightmap
- depth-sorted VxpSpriteBatch rendering; VxpSpriteFx also exposes one-pass silhouette, A8 animation and optional shadow/outline/glow APIs
- VxpVfx2D fixed-memory trail, multi-layer beam, expanding ring, radial burst, rotated A8 glyphs, wave distortion and A8 parallax
- VxpCinematic2D C API for whole-scene shake/punch, hit-stop and HUD-safe RGB565 camera shifting
- portrait MOBA HUD with level/name/HP/MP, Q/W/E/R skills, items, scoreboard and timer
- zero-dependency supersampled asset generator in tools/generate_vxa8_assets.py
- fixed-pool additive/alpha particles using VxpParticlePool
- player collision against the Nexus footprint
- touch/keypad controls and 30 FPS update loop

Controls:
- Arrow keys: move Ariya
- 1 or OK/5: Q orb
- 3: W dash
- 7: E blossom burst
- 9: R spirit burst
- touch the bottom skill buttons to cast

Build: build_arm.bat
Run: run_vxpemu.bat
