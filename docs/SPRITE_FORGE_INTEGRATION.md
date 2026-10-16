# Sprite forge integration

VXPEngine now has a second art route. The first one — the one every sample uses
today — is a hand-written Python generator that draws each sprite pixel by pixel
(`examples/VampireVeilDemo/tools/generate_vampireveil_assets.py` is 50,403 bytes
of it). That route stays: it is fast, deterministic, and it never needs an image
model. The new route is for art authored with
[`agent-sprite-forge`](https://github.com/0x0funky/agent-sprite-forge), vendored
under `third_party/agent-sprite-forge`, plus one bridge tool that turns its PNG
frames into the exact byte layout the core reads.

```
PixelSpec / rig SVG / fx.v1 spec
        |  third_party/agent-sprite-forge/skills/codeart2d/scripts
        v
frames/*.png  +  codeart-meta.json  (+ bundle/animation-clips.json with --build-clips)
        |  tools/vxp_import_sprite_forge.py
        v
a C header of const uint16_t RGB565 + const uint8_t 1-bit masks
        |
        v
VxpeSprite565 table, or a VxpTilemap2D atlas plus VxpeAnimClip records
```

Nothing in the engine depends on the vendored tree. It is a build-time tool
chain; the shipped `.vxp` contains only the generated header.

## What is vendored

`third_party/VENDOR-agent-sprite-forge.json` is the provenance record: origin,
MIT licence, upstream commit `5324342fdfab72430f4e9604f3fe427009f8596d`
(2026-10-06T14:09:38Z), what was taken, what was left out and why.

Two skills ship: `codeart2d` (the code-drawn route — PixelSpec JSON, rig SVG,
`fx.v1`, autotiles, layouts, parallax, ambient plates, `pixel_qa.py`) and
`generate2dsprite` (only because `codeart2d --build-clips` calls its
`build_animation_clips.py`, and the clip bundles it writes are what the importer
consumes). The image-model skills (`video2dsprite`, `generate2dmedia`,
`generate2dmap`) and 81 MB of upstream demo PNGs were excluded.

Measured tree: **91 files, 3,304,730 bytes**, `__pycache__` excluded because it
is bytecode our own runs generate, not vendored source. Recompute the digest
with:

```python
import hashlib, os
root = "third_party/agent-sprite-forge"
recs = []
for dirpath, dirs, files in os.walk(root):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for name in files:
        p = os.path.join(dirpath, name)
        rel = os.path.relpath(p, root).replace(os.sep, "/")
        recs.append((rel, hashlib.sha256(open(p, "rb").read()).hexdigest()))
recs.sort()
print(hashlib.sha256("".join("%s\0%s\n" % r for r in recs).encode()).hexdigest())
```

The result must equal `verification.digest_sha256` in the JSON:
`44d742820f4e1ecf980247618be928fe5f1d7cc1d67148455b95f4bdcf95447d`.

Two things make that number portable rather than machine-local, and both were
added only after they failed:

* `.gitattributes` pins `third_party/agent-sprite-forge/**` to `-text`. Without
  it this repo's `* text=auto` plus `core.autocrlf=true` rewrites every vendored
  `.py` on checkout, so the digest computed on a clone differs from the one
  computed here. `git show :<path>` byte-compares equal to the working tree now.
* The digest counts only committed files. An earlier value of `38273524…` was
  measured over 94 files and never reproduced, because three `__pycache__`
  `.pyc` files were in that count while being gitignored — so they could not be
  in any clone. That value is retired, not reconciled.

**The vendored tree is read-only.** Never patch upstream files in place; if a
fix is needed, do it in the bridge tool or in the project's own spec files.

## Environment

`D:/Program/Python/python.exe` has numpy 2.2.6, Pillow 11.3.0 and scipy 1.18.1.
The `python` that Git-Bash puts on `PATH` (`C:/msys64/mingw64/bin`) has none of
them, so both the upstream renderers and the importer must be run with the
absolute interpreter path, and with `PYTHONUTF8=1` (upstream's own
`forge_doctor.py` checks stdout encoding for the same reason).

## The route, end to end

From the project root, one line per step:

```sh
PY=/d/Program/Python/python.exe
SF=third_party/agent-sprite-forge/skills
PYTHONUTF8=1 $PY $SF/codeart2d/scripts/render_pixelspec.py \
    --spec slime.pixelspec.json --output-dir out/slime-v1 \
    --preview-scale 8 --build-clips --strict-qc
PYTHONUTF8=1 $PY tools/vxp_import_sprite_forge.py \
    --input out/slime-v1 --prefix slime --out src/slime_assets.h
```

`--strict-qc` publishes nothing when a check fails, and the renderers refuse an
existing `--output-dir`, so a fresh directory per attempt is the upstream
contract. The importer's own gates are below.

Two shapes of input work:

* **a codeart2d output tree** — `<dir>/frames/*.png`, or `<dir>/<variant>/frames/*.png`
  for palette variants (`--variant green --variant red` selects). Frame names
  come from the file names.
* **a clip bundle** — `animation-clips.json` (or `bundle/animation-clips.json`)
  written by `--build-clips`. Frame names, order, per-frame durations, loop
  flags and the shared anchor come from the manifest, and every frame PNG is
  sha256-checked against it before a single pixel is read.

Two shapes of output:

* `--mode sprites` — one `VxpeSprite565` per frame, plus an index enum
  (`<PREFIX>_SPR_<NAME>`) and `<PREFIX>_NSPRITE`. Use this for characters and
  props drawn at arbitrary positions, the way `VampireVeilDemo` uses its
  `VvSprite` table.
* `--mode atlas` — one `VxpeSprite565` atlas of uniform cells (`<prefix>_atlas`,
  `<PREFIX>_ATLAS_COLS/_TILE_W/_TILE_H`), a `<PREFIX>_FRAME_<NAME>` enum, and
  for every clip a `VxpeRectI[]`, a `uint16_t[]` of durations and a
  `VxpeAnimClip`. This is what `VxpTilemap2D` and `vxpe2d_anim_*` consume
  directly.

### The byte contract

The importer emits data for the reader that already exists in the core, so the
rules come from `engine/coremre/src/graphics/VxpRender2D.cpp`:

* `pixels` is row-major RGB565, and **0 wherever the source pixel is
  transparent** — `mask_visible()` skips those pixels so their value is never
  read, and zeroing them keeps a header diff between two imports readable.
* `mask` is 1 bit per source pixel, **bit `y * width + x`, MSB first, no row
  padding**, `ceil(width*height/8)` bytes. That is `mask_visible()` verbatim.
* A frame with no transparent pixel gets `mask = 0, opaque = 1`, which is the
  condition for `vxpe2d_blit`'s `memcpy` fast path
  (`VxpRender2D.cpp:341-355`). On a 240x320 map layer that is the difference
  between a row copy and 2048 per-pixel branches.
* `stride` is always written equal to `width`. For an atlas that means cells are
  packed with no padding, because `mask_visible()` indexes with `width`, not
  `stride` — a padded atlas row would shift every mask bit after the first cell.

## Gates

Every gate fails closed (exit 1, nothing written) and every override is an
explicit flag.

| Gate | Default | Override | What it catches |
|---|---|---|---|
| Blank frame | fail | `--allow-blank` | a frame that is 100% transparent, i.e. a spec that rendered nothing |
| Manifest digest | fail | none | a PNG on disk that is not the one the manifest hashed |
| RGB565 collapse | fail | `--allow-collapse` | two source colours that quantise to the same 565 value, so the art loses an edge silently |
| Frame size vs manifest | fail | none | a resampled or resized frame sneaking into a bundle |
| Uniform atlas cells | fail | none | mixed sizes in `--mode atlas` |
| `w`/`h` limit | 255 | `--max-dimension N` | a frame too big for the uint8 wrappers games use, and far too big for 240x320 |
| Colour budget | 32 distinct 565 | `--max-colors N` (0 = off) | a photoreal render arriving instead of pixel art |
| Atlas pixel budget | 16384 | `--max-atlas-pixels N` (0 = off) | an atlas that eats the .rodata headroom a handset app has |
| Partial alpha | warn | `--alpha-threshold N` (default 128) | the core mask is 1 bit per pixel; soft edges cannot survive, so the count is reported |
| Determinism | always | — | no clock, no absolute path, no dict order in the header |

Provenance inside the header is content only: the manifest sha256 (bundle
inputs), the forge anchor, and one sha256 line per frame PNG. No filesystem
path, so the same frames bake to the same bytes on any machine — which is what
makes the fixture gate below possible.

## Verification

Two ctest cases, both added to `engine/coremre/tests/CMakeLists.txt`:

* `vxpe_sprite_forge_importer` —
  `engine/coremre/tests/test_sprite_forge_importer.py` re-bakes the two
  committed fixture headers byte for byte, proves two runs are identical,
  re-packs the hero mask with an independent implementation and compares, and
  drives 15 named checks plus the exit-code gates (blank, collapse, stale
  manifest digest, mixed sizes, colour budget, dimension, atlas budget, unknown
  clip, missing input, `--variant` against a manifest directory, alpha threshold
  up and down, `--clip` selection, JSON summary).
* `vxpe_sprite_forge_c_api` —
  `engine/coremre/tests/vxpe_sprite_forge_c_api.c` compiles the same fixtures as
  **C99** (the language of the project template) and reads every pixel back
  through the real core: `vxpe2d_blit_simple` for a masked sprite and an opaque
  tile, `vxpe2d_blit` with a src rect for each atlas cell, and
  `vxpe2d_anim_reset/_update/_frame_rect` for clip timing, including the
  per-frame durations and a non-looping clip that must stop on its last frame.

Both fixture headers are pinned with `text eol=lf` in `.gitattributes`. That is
not cosmetic: the byte-for-byte re-bake check passed on this machine and failed
two of fifteen checks in a fresh clone of the pushed remote, because
`core.autocrlf=true` checked the golden headers out as CRLF while the importer
writes LF. Verified by cloning `main` and running
`test_sprite_forge_importer.py` inside the clone. While fixing it, a `text`
rule scoped to a whole directory also stripped one CR byte out of each fixture
PNG — real binary corruption, which is why the image extensions are now
explicitly `binary` and the LF rule names `*.h`.

Fixtures live in `engine/coremre/tests/data/sprite_forge`: two loose frames
(`loose/frames`, a fully opaque 8x8 tile and a 12x10 masked hero) and a four-frame
8x8 clip bundle with a hand-written `animation-clips.json` carrying real frame
digests (`fixture_loose.h` 2,833 bytes / 383 bytes of .rodata, `fixture_atlas.h`
4,718 bytes / 544 bytes of .rodata). If the importer changes on purpose, say so
and regenerate:

```sh
PY=/d/Program/Python/python.exe
D=engine/coremre/tests/data/sprite_forge
$PY tools/vxp_import_sprite_forge.py --input $D/loose  --prefix ff_loose  --out $D/fixture_loose.h
$PY tools/vxp_import_sprite_forge.py --input $D/bundle --prefix ff_bundle --mode atlas --atlas-cols 2 --out $D/fixture_atlas.h
```

Results, all from 2026-10-16 runs in this tree:

* Full suite: **31/31 passed, 3.63 s total**, of which the importer case is
  2.94 s and the C fixture case 0.02 s (`ctest -C Debug
  --test-dir tmp/veil-action2d-tests`, log archived at
  `tmp/sforge_full_ctest.log`). The suite was 29 tests before this route; both
  new cases are in the 31.
* The assertion harness is not vacuous: with one expectation deliberately
  mutated to a wrong colour, the Debug build aborts with `Assertion failed:
  fb[6 * FB_W + 6] == C_K` and exit code 3. Reverted and re-run before
  committing the numbers above.
* Real forge output, imported and rendered back: `tmp/asf_probe/walker-v1/forest`
  (12 frames of 16x24, 4 clips) → `tmp/asf_import/walker_gen.h`, 45,773 bytes of
  header, 9,792 bytes of .rodata, 11 distinct RGB565 values, **0.16 s**.
  `tmp/asf_probe/slime-v1 --variant green` (3 frames of 32x32) →
  `tmp/asf_import/slime_gen.h`, 29,496 bytes, 6,528 bytes of .rodata, 5 distinct
  RGB565, **0.15 s**.
* Both headers were decoded back to PNG by `tmp/sf_preview.py` and looked at:
  `tmp/asf_import/walker_roundtrip.png` (4x3 grid of a walking character, grey
  where the mask is clear) and `tmp/asf_import/slime_roundtrip.png` (rest /
  squash / stretch, outline, shadow and highlight all distinct). Silhouettes and
  palette match the forge's own contact sheets, so the 565 bake cost nothing
  visible.

## Limits, honestly

* **1 bit of alpha.** The core has no per-pixel alpha in the masked path, so a
  forge frame with soft edges loses them; the importer warns and counts instead
  of blending. Anti-aliased output from any of the forge skills is the wrong
  input for this route.
* **RGB565 is 65,536 colours, and the collapse gate is per import.** Two hues
  that differ only in the low 3 bits of one channel are the same colour on the
  handset. The gate tells you; it cannot fix the spec.
* **Atlas cells must be uniform.** The forge's `frame_size` guarantees that for
  clip bundles; loose frames must be sized by hand.
* **Anchor semantics.** `anchor_px` in a clip bundle is the shared canvas root
  (often a ground reference), not each frame's visible bottom — the importer
  copies it into the header comment but does not reposition anything. Games that
  want feet-on-the-floor must author the canvas that way, like
  `VampireVeilDemo` does with its fixed 16x24 hero cell.
* **No sample uses this route yet.** Every `examples/*` project still ships its
  own generator; the first conversion is listed as a next step in
  `docs/CORE_ACTION2D.md` and should be a character with a walk cycle, because
  that is where clip timing plus per-frame durations earn their keep.
* **Upstream `--strict-qc` needs seam-proven tilesets**, and `pixel_qa.py`
  review sheets are a human step. The importer only guarantees the bytes it
  emits; it does not judge the art.
