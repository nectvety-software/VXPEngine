# Sprite fantasy stages and dialogue

`graphics/VxpStory2D.h` provides a C API for narrative 2.5D scenes on QVGA.
The runtime is fixed-capacity and allocation-free. It uses VxpSpriteFx's
RGB565+A8 batch and the shared VXPGDX 5×7 font.

## Characters on a shallow ground plane

Initialize `VxpeStoryStage2D` with far/near ground Y positions. Scale defaults
to Q8.8 192..256 (75%..100%). `vxpe_story_push_actor` accepts an atlas crop,
source foot anchor, ground X/Y, vertical lift, flip and optional sprite FX.
Its depth key is the ground foot Y: flying companions keep their intended
depth when lifted. Flush with `vxpe2d_batch_flush`; equal depths retain their
submission order. A full batch returns 0 and increments `dropped`.

Crop/anchor validation occurs before submission. Scale clamps to 1..1024;
missing or degenerate stages use 256. Camera offsets translate placement;
world ground depth controls scale so panning does not resize characters.

## Dialogue

`VxpeStoryDialogue` owns speaker/text/page buffers. Open with a column count
(1..48), line count (1..6) and milliseconds per glyph. Input text uses ASCII;
the owned text buffer holds 511 bytes plus NUL, speaker 47 plus NUL. Text is
word-wrapped and long words split. Explicit newlines are preserved.

Update advances the typewriter. Advance first reveals the current page,
then moves to the next page, then closes. Speed 0 reveals immediately.
Draw clips text within a translucent rounded rectangle. A 296×80 box fits
45 columns and 3 lines at scale 1. Choose a box tall enough for the configured
rows (approximately `40 + rows*10`) and wide enough (`20 + columns*6`).

The portrait sample uses a 220×100 box with 33 columns and 5 lines.

`vxpe_story_text` draws bounded ASCII text for HUDs without a Stage instance.

## Sample

`examples/EmberChronicleDemo` uses a native 240×320 portrait layout, three original fantasy backgrounds,
16 sprite frames, foot depth sorting, dialogue, a training duel and a
three-seal village rescue. PNG sources and deterministic VXA8 baking are
included. The runtime embeds asset bytes; there is no PNG decode or file IO
in the frame loop.

## Software sprite optimization

VxpSpriteFx now accelerates neutral-tint, full-global-alpha COPY/ALPHA draws
without diagonal transforms. Opaque unscaled crops use clipped row copies;
scaled/flipped sprites precompute source X once per column, source Y once
per row, and skip transparent pixels. The bounded scratch table uses 1280
stack bytes at most. Tint, additive/multiply and diagonal paths keep the
general renderer. A scalar reference regression compares pixel results for
partial alpha, padded color/alpha strides, crops, clipping, scale and flips.

## Story HUD and Asset Editor

`vxpe_story_hud_draw` draws a 44-pixel title/location/progress header and a
26-pixel footer with up to six controls in three columns. It supports both
QVGA orientations, clips long ASCII strings, and uses a caller-provided
`VxpeStoryHudStyle` or defaults from `vxpe_story_hud_default`. Strings are
borrowed only during the call; no allocations or retained pointers.

Editor Assets → Story HUD previews the shared 5×7 font at 240×320 or 320×240.
Edit title, RGB565 palette, opacity and six key/label pairs, then Save.
It writes `assets/ui/story_hud.json` and `src/story_hud_generated.h` in the
current project. Include that header and pass `story_hud_style`,
`story_hud_title`, `story_hud_keys`, `story_hud_labels` to the API; location,
chapter and status are supplied by gameplay. EmberChronicleDemo already
uses the generated header. Rebuild to apply changes. PNG backgrounds are
previewed without modifying their source files.
