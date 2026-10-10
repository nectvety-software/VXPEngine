# Lost in Latency: Mall Memory

Original 240×320 first-person mall exploration inspired by the supplied video’s bright indoor atrium, arcade, food court and aquarium scenes. The project recreates those broad location cues with its own low-poly geometry, layout, colors and text; it does not include video frames, trademarks, photographs, music or copied game assets.

## S30+ MRE renderer path

The world uses VXPEngine `VxpToon3D` perspective triangles in a 120×160 RGB565 render target with a matching 16-bit depth buffer. The core RGB565 Scale2x helper enlarges it to the 240×320 device layer; the title, controls and journal are then drawn at native resolution. The two scene buffers occupy 76,800 bytes total, one quarter of a full-resolution color-plus-depth pair. Geometry and QR codes are generated from fixed data; the game performs no heap allocation or texture decode in the frame loop. Camera yaw uses a 32-entry Q14 lookup table to avoid runtime trigonometry on the low-power target.

The core triangle rasterizer steps its three edge equations with additions across scanlines, advances ARM perspective quotients with exact remainders, and rejects triangles whose projected bounds are fully outside the viewport. Barycentric coverage, depth, texture, lighting, fog and clipping remain unchanged. This scene fills the world color buffer with a sky gradient, so it uses `vxpe_toon3d_clear_depth` and skips a redundant clear of 38,400 RGB565 pixels (76.8 KB of writes) on each 120×160 frame. Static color/depth buffer RAM remains 76.8 KB.

## Loop and controls

Walk the mall’s atrium, arcade, food court and aquarium passage. Approach each of four glowing QR plaques and press `5` to recover a short memory fragment. `2/8` walk forward/back, `4/6` turn, `0` open the memory journal, `9` pause. The four-bit scan progress is stored in the app’s versioned public cache at `@vxp_<APP_ID>`; no video or image data is copied into cache.

The art brief used for the code-drawn scene: “Design an original nostalgic indoor shopping mall for a compact portrait first-person low-poly game: a tall glass atrium roof with warm brass ribs, glossy checker terrazzo, a small turquoise fountain, varied storefront windows, retro game displays, round food court tables beneath muted coral and ochre parasols, and a blue glass aquarium passage with small faceted fish. Use a modest PS1-era palette, strong perspective, clear geometry at 120×160, no logos, recognizable brands, readable text, photographs or copied architecture.”
