# Pocket Pitch: gameplay and original art

Pocket Pitch is a portrait arcade soccer-pachinko game for 240×320 MRE screens. It borrows the broad idea of fast, pinball-like soccer play from the supplied video. All field art, teams, interface and effects are original code-drawn shapes; the video frame, its field, characters, name, interface and audio are not included.

## Loop

- Start a 45-second match. A fixed-size ball is served upfield; it rebounds from five colour-coded bumpers and the side rails.
- The keeper tracks the ball across the goal mouth. Reaching the upper goal scores; a keeper save knocks the ball back into play. Missing the goal returns the ball for another serve.
- Press 4/6 or tap the matching lower flipper to kick across the field. Press 5 to shoot straight. During the short serve window, 2/8 adjusts the launch lane.
- Press 1/3 to apply left/right curve. Two charges of each are available per match, with a 2.5-second shared cooldown.
- Goals add 100 points plus a small combo bonus. The best score is saved as a two-byte payload through the versioned `@vxp_1869076` public cache.

## Art direction and prompt

The native artwork is drawn by the renderer from reusable shapes: deep indigo stadium frame, alternating emerald turf, clean ivory markings, brushed-steel pinball bumpers with distinct mint/gold/ice/pink cores, original miniature teams and a bright ball. The crisp outlines, narrow highlights and 240×320 layout keep the scene readable without a large texture atlas.

Reproducible art brief: “Create an original portrait 240×320 arcade soccer pinball game scene. Top-down emerald indoor football pitch with broad alternating grass bands, precise ivory goal/penalty/centre markings, compact dark indigo broadcast HUD, steel-and-brass circular bumpers with separate mint, gold, ice-blue and coral cores, tiny original cyan and vermilion uniformed players, a luminous black-and-ivory ball, and a sliding keeper. Strong contrast, crisp pixel-aligned edges, restrained highlights, readable native-size type. No logos, text baked into artwork, copied game assets, recognizable uniforms or branded field design.”

No external bitmap, font, sound or video asset is bundled. This keeps the runtime art footprint at zero extra texture bytes and avoids loading/decoding image assets. The game state uses fixed arrays for five bumpers and twelve short-lived particles; no per-frame allocation is used.
