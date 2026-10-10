# Basic attack, movement and memory — 2026-10-07

Left softkey (LSK / Soft1) performs a basic attack; hold it to repeat at the hero/item attack cadence. Four skill keys 5/7/9/0 remain unchanged. Basic attacks spend no mana and share the existing automatic attack cooldown: pressing cannot double-hit or bypass item cadence. Target priority: enemy hero in range, weakest enemy minion in range, next unlocked tower/core. An empty attack animates and consumes the attack interval. Attack input is ignored during pause, shop, death, stun and skill cast. Damage uses the same armor/shield, tower aggro and last-hit rewards as automatic attacks. Mage bolt, hammer sweep and crossbow tracer have distinct brief feedback.

Three original heroes now have north/south running A/B frames. North shows the back, south shows the face, horizontal movement uses existing lateral poses. Direction is chosen from actual collision-resolved displacement, with vertical priority on diagonal ties. Blocked movement preserves the previous direction. Stopping retains the last direction using a stationary first frame. Attacks/casts temporarily use their existing action poses.

Memory/render changes:
- One RGB565 framebuffer replaces two: 153600 bytes (150 KiB) less canvas memory, before platform allocation overhead.
- Wave units use 32px atlas cells instead of 48px: 23040 fewer embedded bytes; new north/south art uses 57600 bytes. Existing action detail stays 48px.
- Removed an unused particle pool and invisible spark updates. The actual 12 skill effects remain unchanged.
- Match background rows use direct RGB565 copies; each row is initialized once, retaining HUD borders and framebuffer determinism.
- Only visible world objects enter depth sorting; no keyboard-repeat rendering outside the 33ms match timer; fighter rendering uses a reference instead of copying state.

The RAM allowance remains 1500 KiB. Savings describe canvas and embedded data, not measured peak heap or a guaranteed FPS on every phone. No dynamic allocations are introduced in the game loop.

Validation: manual damage/mana/cooldown, last-hit gold, held attack repetition, pause/shop/stun/death guards, four actual movement directions for all heroes, existing combat/skill/world tests, framebuffer boundary and clipping tests, ARM build and signed package verification. Runtime smoke exercises held Soft1, north/south movement, purchase, pause/rematch at 240x320.
