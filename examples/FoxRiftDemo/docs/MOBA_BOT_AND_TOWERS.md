# Towers and solo MOBA bot — 2026-10-07

Towers and cores attack opposing minions and heroes from either team inside 105 Manhattan-distance units. Minions take priority unless a hero draws aggro by attacking the defended hero under that structure. Hero aggro lasts 2.2 seconds and is refreshed by further attacks. Shots occur every 1.2 seconds and display a team-colored beam. Tower hero damage is 65, core damage 45; consecutive hero shots add 20 per shot, capped at +60. Leaving range or a shot switching to minions resets escalation. Armor and shields mitigate shots through the shared damage function. Destroyed structures stop firing.

Bot plans displayed on the HUD:
- RECOVER: low HP, low MP, or a clearly unfavorable close duel; walk to the home fountain, use available healing/defensive escape, and stay until HP is at least 75% and MP 50%. No basic attacks while retreating.
- DEFEND: enemies threaten friendly objectives. The deepest threatened structure takes priority, with extra urgency for siege carts. Move to intercept the attacker rather than chase a nearby farm target.
- DUEL: engage a nearby hero when health/attack comparison favors a fight or an objective needs protection. Melee closes range; ranged heroes maintain distance and use their distinct skill rules.
- FARM: move to a reachable enemy wave, favor low-HP last hits, and use a basic skill to clear while preserving control/ultimate for hero combat.
- PUSH: attack the next unlocked enemy tower with allied wave cover; ranged heroes can poke outside tower firing range.
- WAIT: melee stays outside danger until allied minions arrive. Avoid enemy tower dives and withdraw when tower aggro is active.

All movement respects walls/live buildings. Recovery and tower danger are checked even when the player is distant. State is reevaluated from live health, mana, enemy positions, waves and objectives; skill decisions use the existing 350ms think interval. No heap allocations or extra sprite atlases were added.

Bot shops with its earned gold under the same six-item rules as the player. Low HP prioritizes Stone Mail; low mana prioritizes Prism Orb; otherwise the archetype-specific purchase order applies. HP/MP items increase current and maximum values on purchase; Edge Blade increases normal damage; Prism Orb increases skill damage. Armor, speed, cadence and regeneration also affect actual gameplay. Inventory survives death and resets on rematch. HUD shows bot plan, current HP, normal attack (A) and current mana (M).

Validation covers both-team tower damage/escalation/reset, minion-first targeting and hero aggro, core defense overriding farm, wave farm, melee wait/push with cover, recovery hysteresis and fountain regeneration, safe basic-attack suppression while retreating, favorable duel selection, shared-wallet purchases and real HP/MP/damage upgrades, plus the existing multi-wave simulation and framebuffer/skills/world tests.
