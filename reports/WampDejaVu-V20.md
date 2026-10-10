# WampDejaVu V20 / VXPEngine game project defaults

- New-project template is `2.0.3`. Fresh projects now include `src/vxp_public_cache.h`; it stores compact payloads in a unique public `@vxp_<APP_ID>` directory, preferring the removable drive and falling back to system storage. The blank sample saves/reloads a small checkpoint every 300 frames and at app shutdown.
- Reusable Codex guidance: `C:/Users/doxuanhop/.codex/skills/vxp-game-project-standards/SKILL.md`; the agent prompt is also checked in at `ai/prompts/vxp-game-project-prompt.md`.
- WampDejaVu adds eight fixed enemy projectile slots. Wisps fire frost bolts that immobilize the player briefly; ember enemies cause periodic burn damage; the third attack variant uses a brighter flame burst. Cast cues, projectile colors, ice shards/frame and burn sparks are drawn procedurally, without loading another atlas.
- Wamp cache advances from WDC2 to WDC3 and migrates existing WDC2 saves, including player/enemy state. Projectile and status state are part of pause/replay snapshots.
- Validation: host gameplay test passed; new-project template copy/manifest check passed; ARM/VXP package built and signed; VXPEmu smoke passed (menu/cache/storage path and gameplay). VXPEmu verified the existing Wamp save folder on the emulator's removable drive. Real-device card removal and power-loss behavior remain device-dependent.
- Signed VXP: `C:/Users/doxuanhop/Documents/VXP Projects/WampDejaVu/build-arm/main/dejavu_rooms_v4-V20-signed.vxp`
- SHA-256: `61773932133edf2c92444153af18cd1a07ccb027b2aa34c11d35d19ba3ceb6c8`; size 2,708,829 bytes.

