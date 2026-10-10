# Waves, gold and equipment

Native viewport remains 240x320 with a 240x960 world. The supplied compendium is a pose reference; the three original heroes now have two running strides, basic attack, raised cast/guard, forward cast/slam and dash poses. Cast pose depends on hero and skill. Fixed arrays support 48 minions, 24 effects and 16 projectiles without gameplay allocations.

## Waves and pushing

First wave arrives at 3 seconds; subsequent waves every 12 seconds. Both sides spawn two melee soldiers and one crossbow soldier. Every third wave also spawns a siege wagon. Melee/ranged/siege have 220/150/480 HP; siege damage against structures is doubled. Units march along clear lane sides, respect walls and structures, fight opposing units and nearby heroes, then attack the next unlocked enemy tower/core.

Towers prioritize enemy minions. Attacking a defended enemy hero draws tower aggro for 2.2 seconds, even with a friendly wave nearby. Towers, minions and heroes share armor/shield damage rules. Destroying outer tower, inner tower and core remains the win path. The melee bot waits for allied minion cover before approaching enemy towers and avoids chasing farm under an uncovered enemy tower.

## Gold and strategy

Each hero starts with 120 gold and gains 4 gold per second. Hero last hits grant 32/40/65 gold for melee/ranged/siege; a nearby allied-unit kill grants 8 gold. Hero kills grant 120; destroying a tower grants the attacking team hero 100. Rewards are issued once. Basic attacks farm the lowest-HP reachable minion when no hero is in range. Projectile skills acquire an enemy minion when the opposing hero is distant/dead; area skills can hit several minions. Aim by positioning and time skills to secure last hits.

## Shop controls

Press # to open/close. Use 2/8 or up/down to choose, 5/OK to buy, Back to close. The battle continues while the shop is open, so buy in a safe position. Each of the six items is unique and can be bought once; no selling or item upgrades in this version. Inventory and gold survive death and reset on rematch. The bottom HUD shows G (gold), F (last hits), and # SHOP. Key 1 still recovers HP/mana; 3 rematches; * pauses.

| Item | Price | Effect |
| --- | ---: | --- |
| Edge Blade | 120 | +14 basic attack |
| Stone Mail | 160 | +260 max HP and 12% incoming damage reduction |
| Prism Orb | 160 | +160 max mana and +25 skill damage |
| Wind Boots | 100 | +1 movement speed, capped at 4 |
| Rapid Bow | 150 | -180ms basic attack delay, minimum 250ms |
| Life Charm | 130 | +120 max HP and +3 HP per 300ms while alive |

Bot uses the same wallet, prices, unique ownership and stats. Mage prioritizes Orb, ranger Bow, and knight Mail; it farms nearby waves before pushing. Protect a wave to absorb tower shots, defend siege carts, and choose offensive or defensive equipment for your matchup.

Individual original PNGs, action/unit atlases, frame metadata and running .ani..dtfe files are saved under assets/sprites for Editor Assets. Bake script: tools/generate_army_assets.py. Prompts and source provenance: ARMY_ARTWORK_PROMPTS.md. Gameplay constants reside in src/lane_warfare.cpp.

Validation covers wave symmetry/carts, capacity limits, last hits, no duplicate/friendly rewards, projectile and AoE farming, shop affordability/uniqueness/stat changes, retained items through respawn, tower targeting/aggro, siege damage, basic farming, bot purchases and a multi-wave end-to-end simulation.

Tactical tower escalation and bot plans are documented in MOBA_BOT_AND_TOWERS.md. HUD plan labels: FARM, DUEL, DEFEND, PUSH, RECOVER, WAIT.
