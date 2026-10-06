# InfiltrateMissionDemo

240x320 VXPEngine sample inspired by a feature-phone stealth/action storyboard.

## Mission flow

1. **Deployment** — highway/city approach. Press 5/OK to deploy.
2. **Park** — steer the red car with 4/6 into the yellow parking box, then press 5.
3. **Entry** — move to the building door with 4/6 and press 5 to start the wrench interaction. The wrench animates, a progress bar fills and the door opens before the mission advances.
4. **Sneak** — use 4/6 + 2/8 to approach guards. Guards patrol between waypoints and expose a vision cone. Detection advances through PATROL -> WATCH -> ALERT. Press 5 for a close takedown.
5. **Pistol** — one armed target remains; press 5 when aligned to fire.
6. **Exit** — move forward with 2 until reaching the exit, then press 5. HUD shows MISSION DONE.

## Guard AI

- Fixed-memory waypoint patrol; no heap allocation.
- World-space detection cone projected through VxpScene25D.
- Cone colours: green = patrol, yellow = watch/suspicious, red = alert.
- Detection meter rises while the player remains inside the cone and decays after leaving it.
- Alert guard tracks the player laterally and advances down the corridor.
- HUD action changes between SNEAK, WATCH and ALERT.

## Entry interaction

- 5 / OK near the door starts a timed wrench action instead of instantly changing scenes.
- Wrench rotates through four poses.
- Interaction progress bar and sliding door animation are rendered procedurally.
- Player horizontal movement is locked while the interaction is active.
- On completion the state machine enters Sneak.

## Visual pipeline

- 240x320 portrait framebuffer.
- Procedural city/highway, parking alley, building entry and interior corridor scenes.
- VxpScene25D depth projection for player/guard billboards and guard vision geometry.
- RGB565 cel-shaded characters and ground shadows.
- Lightmap + impact flash/ring for indoor combat.
- Mission-aware minimap, phase label, target counter, detection meter and action prompt.

## Controls

- 4 / Left: move or steer left
- 6 / Right: move or steer right
- 2 / Up: advance
- 8 / Down: move back
- 5 / OK: context action
- RSK / Back: exit
