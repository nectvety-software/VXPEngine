# Twelve original skill animations

The runtime draws crisp pixel effects in src/skill_effects.cpp, using integer coordinates, a fixed 24-slot effect pool and 16 projectile slots. No allocations or trigonometry are needed during gameplay. Skin palettes apply to both cast and projectile/impact effects. Every effect pixel clips to the world area y=41..249 in the native 240x320 framebuffer. Pause freezes effect time; rematch clears effects and projectiles.

| Hero | Skill | Cast / movement | Projectile / impact |
| --- | --- | --- | --- |
| Velin | Prism Bolt | Bright prism launch sigil, 420ms | Faceted prism with three shard trails; exploding shards on hit |
| Velin | Light Burst | Eight outward-moving golden shard spokes and violet ring, 650ms | Nearby area hit |
| Velin | Anchor Ray | Two gold gate rings and violet beam, 500ms | Chain of ring gates; three locking rings around the target only on hit |
| Velin | Prism Nova | Expanding dual rune wheel and rotating rising crystal crown, 1050ms | Nearby nova hit |
| Torvan | Hammer Arc | Aimed moving crescent with a square hammer head, 450ms | Melee sweep |
| Torvan | Iron Guard | Riveted shield outline and pulsing cross follows caster, 1400ms | Stops rendering when shield is depleted or caster is defeated |
| Torvan | Charge | Three speed rails and dust rings along the actual collision-limited dash, 600ms | Landing ring at actual destination |
| Torvan | Earthbreak | Ground shockwave, branching jagged cracks and debris spokes, 950ms | Nearby area stun |
| Nimara | Wind Bolt | Curling launch wind, 380ms | Silver arrow with moving wind spiral; wind spokes on hit |
| Nimara | Gust Step | Three fading silhouettes and wind ribbons along the actual retreat dash, 650ms | Wind ellipse at landing |
| Nimara | Pinning Shot | Wind crosshair at the bow, 600ms | Long arrow with diamond trail; vertical wind cage only on hit |
| Nimara | Arrowstorm | Target ellipse with nine staggered falling arrows and landing ripples, 1250ms | Uses target location if in range, otherwise casts a visual storm at caster |

Animations visualize the existing damage, cooldown, mana, stun, slow and swept movement rules. Area damage is still resolved instantly by gameplay; arrowstorm volleys are visual, not nine additional damage ticks. The brief shield visual is independent of the persistent shield amount.

Run host tests, then tools/export_skill_previews.py to export individual GIFs and the 12-skill comparison grid into tests/runtime_screenshots/skill_fx. The previews hold the bot still for visual inspection. These pixel animations are code-native artwork and do not reuse franchise imagery.
