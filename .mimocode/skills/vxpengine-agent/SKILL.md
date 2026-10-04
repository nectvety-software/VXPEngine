---
name: vxpengine-agent
description: Develop, inspect, repair, build, and test VXPEngine IDE/coremre projects and S30+ MRE .vxp games/apps. Use for VXPEngine source changes, Camera2D/DTFE/UI work, creating a new game or app project, ARM builds, VXPEmu runs, SDK/toolchain issues, template_blank sync, ModuleNotFoundError/verify_core, MSI install or "Run shows nothing" errors, and migration of layout-v2 projects.
---

# VXPEngine Agent

Work from the repository root `D:\MRE\VXPEngine` (or the installed copy under
`C:\Program Files\VXPEngine` when debugging a release). Read `project.vxp.json`
before changing a game project and preserve its App ID, vendor, viewport, and
unknown descriptor fields.

Full docs live in the repo skill pack:

`ai/skills/vxpengine-agent/` → `PROMPT.md` + `SKILL.md` + `references/`.

## Route the task

| Task | Read first (relative to repo root) |
|------|--------------------------------------|
| Create a new game/app project | `ai/skills/vxpengine-agent/references/create-project.md` |
| Folder layout, template sync, ownership | `ai/skills/vxpengine-agent/references/project-layout.md` |
| Build, emulator, DTFE/C bindings, tests | `ai/skills/vxpengine-agent/references/workflows.md` |
| coremre, SDK, packaging, MSI | `ai/skills/vxpengine-agent/references/workflows.md` |
| Runtime/install/Run errors | `ai/skills/vxpengine-agent/references/troubleshooting.md` |
| Full agent system prompt (VN) | `ai/skills/vxpengine-agent/PROMPT.md` |

If those paths are missing, use the copies under this skill folder’s `references/`
when present, or ask the user which checkout is authoritative.

## Operating rules

1. Treat `src/`, `assets/`, and project-authored docs as user-owned.
2. Treat `.vxpe/` as manifest-managed engine plumbing. Change its source in
   `template_blank/`, bump the template version, and let synchronization apply it.
3. Never edit `resources/gen/` or `src/scene_bindings.h` manually when an editor
   or generator owns the output. Change the `.dtfe` source and regenerate.
4. Support only physical QVGA orientations `240x320` and `320x240` unless the
   user explicitly changes the runtime contract.
5. Use VXPEmu only. Do not add MREmu, TinyMRESDK, or fallback paths to them.
6. Keep secrets out of projects, logs, examples, archives, and commits.
7. Prefer the integrated w64devkit, ARM GCC, MRE SDK, coremre tools, and packaged
   core selected by `app/sdk_layout.py` and `app/vxp_runner.py`.
8. Preserve legacy-project fallbacks when changing layout-v2 paths.
9. Add or update a focused harness under `reports/`, then run the smallest
   relevant harnesses plus syntax checks. Perform a real ARM build for build,
   CMake, SDK, resource, or packaging changes.
10. When a frozen `VXPEngine.exe` fails, check
    `%LOCALAPPDATA%\VXPEngine\logs\native_crash.log` and the troubleshooting
    reference before rewriting large code paths.

## Create a game or app (happy path)

1. Confirm viewport: **240×320 portrait** or **320×240 landscape** only.
2. Create via IDE dialog or `ProjectStore.create_project(...)` — never hand-copy
   `template_blank/` wholesale.
3. Identity comes from `project.vxp.json` (`app_id`, `app_name`, `developer`).
   Do not invent or regenerate App ID on every build.
4. Design in `assets/scenes/*.dtfe` → regenerate `src/scene_bindings.h` and
   `resources/gen/*.raw`.
5. Implement gameplay in user-owned `src/` (start from `template_blank/src/main.c`
   design-mode pattern).
6. Build: `scripts\build_arm.bat` or IDE **Build ARM**; run: `scripts\run_vxpemu.bat`
   or IDE **Run** (VXPEmu only).

## Error triage

| Symptom | First check |
|---------|-------------|
| Run/Build does nothing / silent | `native_crash.log`; dialog `Build/Run thất bại`; Ctrl+J console |
| `ModuleNotFoundError: verify_core` | Frozen build missing `hiddenimports=["verify_core"]` — rebuild MSI/spec |
| `Thieu core coremre` / signature fail | `packaging/coremre/<ver>/` integrity; do not bypass `verify_core` |
| MSI 1603 / Error 1730 | Need elevated install for per-machine Program Files |
| Wrong screen size | Only 240×320 or 320×240; fix `project.vxp.json` + `.dtfe` viewport |
| Template overwrote my code | Policy bug: user files must be `seed`, not `managed` |

## Completion criteria

- The requested behavior is implemented in the actual runtime, not only the UI.
- Project data survives close/reopen and generated files match their sources.
- Template synchronization never overwrites locally modified project files.
- No build/cache/core artifact is introduced into `template_blank`.
- Report exact tests and generated `.vxp` artifacts, or state the concrete blocker.
