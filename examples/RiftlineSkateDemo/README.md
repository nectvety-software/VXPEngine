# Riftline: Concrete Flow

An original 240×320 portrait skateboarding arcade sample for VXPEngine. The video was used only to understand the camera and skatepark vocabulary: a follow camera, concrete bowls, quarter pipes, rails, ollies, aerial tricks and score combos. The game has its own name, character presentation, park layout, palette and geometry; it contains no Skate 3 marks or copied video assets.

Controls: `5` / OK drops in or ollies; `4` / `6` steers; `2` / `8` accelerates or brakes; `1` / `3` performs different aerial tricks; `7` grinds a rail; `0` changes camera; `9` pauses; Back exits.

The demo reuses the original VXPEngine low-poly skater mesh and Editor Assets atlas. The board, curved bowl, quarterpipe, coping, plaza blocks, rails, floodlights, floor markings and shadows are built from compact original geometry. Concrete panels use faceted lighting and subtle color variation; the camera tracks the skater vertically as they ride up the ramp. World geometry renders into a 120×160 RGB565/depth target and scales to 240×320; the two targets use 76,800 bytes, with fixed actor/geometry storage and no per-frame allocation or cache writes.

Open `project.vxp.json` in VXPEngine and Build/Run ARM, or run `scripts/build_arm.bat`. The sample has a separate App ID and creates `riftline_skate_signed.vxp`.

© VXPstore. All rights reserved. https://qeafivels.com/
