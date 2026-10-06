# Artwork generation record

Generated with the built-in `image_gen` tool, two calls. References provided
by the user guided the fantasy RPG mood. The saved sources are original
generated artwork; the reference JPGs were not altered or embedded in the VXP.

Saved sources: `assets/source/environments.png` and `assets/source/characters.png`.
Deterministic runtime outputs: `assets/backgrounds/`, `assets/sprites/`,
`assets/runtime/`, and `src/assets_generated.h`.

## Environment prompt

Use case: stylized-concept. Create a production game background asset sheet for a 320x240 retro fantasy 2.5D sprite RPG, inspired by detailed PlayStation-era prerendered scenery, earthy olive-brown stone, timber, moss, candlelight. Output exactly 1024x1536 portrait image containing THREE equally sized 1024x512 landscape panels stacked edge to edge, no gaps, no labels, no text, no border, no UI, NO characters. Top panel: richly detailed medieval timber-and-stone apothecary library interior, bookshelves, green stained glass, herbs, wooden beams, arched doorway, floor in bottom 30%, atmospheric amber light. Middle panel: mossy ancient stone terrace/cliff, layered rocks and ferns, broad unobstructed walkable stone ground in bottom 30%, side-on RPG stage. Bottom panel: dramatic rustic village square, stone timber houses with steep shingled roofs, purple dusk mountains, broad empty cobblestone street in bottom 30%, no actual fire (game adds fire). All three are eye-level side-on shallow perspective stages, intricate textured pixel artwork with coherent large pixel clusters, no smooth painterly brushstrokes. Strong layered depth and warm atmospheric fantasy mood. Keep central floor empty for sprites. These are ORIGINAL environments, no existing game names or copied characters.

## Sprite prompt

Use case: stylized-concept. Production sprite atlas on a truly transparent background, ORIGINAL fantasy RPG characters inspired by richly shaded 1990s pixel animation. Exactly 1024x1024 square, a precise 4 COLUMN by 4 ROW grid, 256x256 invisible cells. Each cell contains one fully visible sprite centered horizontally with feet baseline at y=224 relative to its cell. No shadow on floor, no text, no labels, no grid lines. Preserve generous empty transparent padding each side; sprites never overlap adjacent cells. Pixel clusters and crisp edges, no soft gradients. Row1 (four frames same woman): a lavender-haired young adult knight in violet and silver armor, white scarf and short lilac tunic, original face, with small steel sword, facing right, frames standing, walk left leg forward, walk right leg forward, spell casting raised hand. Entire body about180 pixels tall, width100px. Row2 (four consistent frames): wise old white-bearded wizard in midnight blue robe with staff, facing left, same standing/walking/walking/casting sequence. Row3: four consistent frames of female auburn-haired witch in burgundy dress and broad crimson pointed hat, facing right, same sequence. Row4 special companions each fully contained in one cell: column1 a small blonde fairy in mint dress with radiant pale green insect wings; column2 white duck orange bill and feet facing right; column3 small vivid green frog facing right; column4 silver armored male knight with blond hair holding a broad sword vertically facing left. All beautiful expressive detailed Japanese fantasy pixel-art sprites, readable strong silhouettes, transparent alpha, NO backdrop. Alignment of all frames important, 4x4 evenly spaced grid.

The generator uses actual source dimensions (environment 1024×1536, sprites
1254×1254), saves the original alpha, normalizes each crop's foot baseline,
and bakes nearest-neighbor QVGA images. Environment panel seams are at 472
and 968 pixels in the saved output; these are specified in the bake script.

Runtime backgrounds are center-cropped to 3:4 and baked at native 240×320. Original generation prompts are preserved.
