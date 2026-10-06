# ParticleFireDemo

Demo for VXPEngine's fixed-capacity C particle API with lightweight physics.

- Pool: 64 particles, zero runtime heap allocation.
- Dense active-index list: update/draw scale with live particles instead of scanning every slot.
- Fire: additive RGB565 particles, shrinking size, alpha fade, warm tint.
- Smoke: alpha blended particles, growing size, grey tint.
- Sparks: gravity, world-bound collision and AABB collision with bounce/friction/restitution.
- Collision events expose slot, normal, collider tag and response.
- Radial-light hot path uses one reciprocal per light instead of a divide per pixel.
- 30 FPS timer target.

Controls:
- Left/Right: move the emitter.
- Up: spawn a stress-test spark burst.
- OK or 5: toggle the continuous emitter and clear the pool.
- Tap upper half: spawn a spark burst.
- Right softkey / Back / Clear: exit.

Build: `build_arm.bat`
Run: `run_vxpemu.bat`
