# Art direction and provenance

## Project-specific visual brief

“Create an original, optimistic tropical eco-city for a portrait 240×320 retro 3D exploration game. First-person camera glides along a shallow turquoise lagoon promenade toward a cluster of white, rounded, low-poly glass towers with cyan horizontal bands and planted terraces. Frame the horizon with a vivid cobalt sky, broad chunky ivory clouds, tiny palm islands, bright green palms, faceted rocks, a small fountain, blue water reflections and a few floating soap bubbles. Use simple PS1-era geometry, saturated RGB565 colors, low-resolution pixel textures, fixed bright daylight, gentle distance haze and strong centered perspective. Keep the view legible when rendered at 120×160 and enlarged with nearest-neighbor scaling. Avoid copied video frames, named brands, exact buildings, logos, text in the environment, photorealistic assets and external textures.”

## Runtime art implementation

The shipped environment is generated deterministically as low-poly world-space geometry in `src/scene.cpp`. It includes an ocean plane, water glints, faceted islands and palms, tapering arcologies with cyan glass bays, cloud clusters, and scan beacons. No video pixels, external textures, or runtime image conversions are used. Menu and HUD text use the game's bitmap font.

## Reference use

The user-supplied video was used only to identify broad mood and composition: bright ocean, green islands, white/cyan futuristic towers, palms, clouds, bubbles and a slow first-person camera. No video frames, music, logos, branded signs, or exact structures are included in the project.
