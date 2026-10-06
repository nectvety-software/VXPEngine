# Hero gameplay / Vaelora Duel

## Shared rules

Player and bot share `cast_for`, `hit`, `move`, `heal` and `HeroDef`.
Damage first applies Torvan's 15% reduction, then consumes shield, then HP.
Shield cap: 400 for Iron Guard, 300 for mage/ranger grants. Shield persists
until absorbed or rematch. Mana regenerates 4 per 300 ms; attack cooldowns
are per hero. Basic attacks hit immediately in Manhattan distance range.
Skill projectiles move 6 pixels/tick along the initial target direction,
expire at 1600 ms or the arena edge, and collide within 20 pixels of the
target chest. Movement is clamped to x=26..214, ground y=112..239. Gameplay
uses a fixed 33-ms timer. Casts outside AoE range still consume mana/cooldown.

| Hero | Basic damage / range / cooldown | Movement |
|---|---|---|
| Velin | 34 / 108 / 850 ms | 2 px/tick |
| Torvan | 60 / 40 / 700 ms | 2 px/tick |
| Nimara | 30 / 125 / 750 ms | 3 px/tick |

## Velin — Prism Keeper

Human keeper, short silver hair, violet coat and floating triangular brass
lantern. Prismatic light shards are the visual motif.

| Key / skill | Effect | Mana | Cooldown |
|---|---|---|---|
| 5 Prism Bolt | Projectile, 190 damage; slow 350 ms | 40 | 1.1s |
| 7 Light Burst | 140 damage within 85 | 65 | 3.0s |
| 9 Anchor Ray | Projectile, 90 damage; stun 1000 ms | 60 | 4.0s |
| 0 Prism Nova | 300 damage within 130; slow 900 ms | 100 | 6.5s |

Passive: every third accepted skill cast grants 50 shield (cap 300).
Play at medium range; Anchor Ray sets up a Nova, then use shield to survive
counterattacks. The bot tries to maintain roughly 80 pixels of distance.

## Torvan — Iron Vanguard

Human engineer knight, copper/moss armor, square mechanical hammer and a
rectangular tower shield. Passive reduces all incoming damage by 15%.

| Key / skill | Effect | Mana | Cooldown |
|---|---|---|---|
| 5 Hammer Arc | 180 damage within 65 | 35 | 1.3s |
| 7 Iron Guard | Gain 240 shield, cap 400 | 55 | 4.0s |
| 9 Charge | Dash up to 45 per dominant axis toward target; 100 damage + 600-ms stun within 60 of destination | 45 | 3.3s |
| 0 Earth Break | 300 damage + 900-ms stun within 95 | 90 | 7.0s |

Close the gap with Charge and time Iron Guard before incoming projectiles.
The bot maintains about 30 pixels, shields below 65% HP, charges from medium
range and uses Earth Break only when in range.

## Nimara — Wind Ranger

Brown-skinned human ranger, short braids, teal scarf, cream jacket and wooden
crossbow. Passive grants 2 extra mana per regen tick if she moved that frame.

| Key / skill | Effect | Mana | Cooldown |
|---|---|---|---|
| 5 Wind Bolt | Projectile, 165 damage; slow 350 ms | 40 | 1.0s |
| 7 Gust Step | Dash up to 35 per dominant axis away from target; gain 90 shield | 55 | 2.8s |
| 9 Pinning Shot | Projectile, 100 damage + 650-ms stun | 60 | 4.2s |
| 0 Arrow Storm | 240 damage within 180; slow 900 ms | 110 | 6.0s |

Keep moving, fire from range and use Gust Step when Torvan gets close.
The bot maintains about 100 pixels, retreats from melee and uses Pinning Shot
to interrupt pursuit. Gust Step does not teleport through a collision map;
this demo uses an open bounded arena.

## AI and outcome

AI decisions every 350 ms. Movement updates every second fixed tick so bot
has a modest reaction disadvantage. Below 30% HP, bot retreats and uses the
shared recovery action (300 HP/120 mana, 15s cooldown) if ready. It cannot
cast, recover or attack while stunned, and cannot bypass mana or cooldowns.
Match ends on knockout or after 120s; timeout compares HP percentage. Equal
percentages draw. Result shows actual HP damage and accepted cast counts.

Balance values are prototype values and may be tuned in
`assets/gameplay/heroes.json`, then regenerated. Ability damage/ranges and AI
logic currently live in `src/scene.cpp`. These are original hero concepts
using common combat primitives such as shields, projectiles and movement.
