# Project layout v2 and dynamic template contract

## User-facing tree

```text
project/
├── project.vxp.json          project identity, QVGA screen, MRE metadata
├── CMakeLists.txt            managed build entry
├── README.md                 managed until locally edited
├── src/                      user code and generated scene bindings
├── assets/                   source images, audio, maps, fonts, and scenes
├── resources/gen/            generated MRE resources; do not edit
├── resources/pack/           transient resource staging
├── scripts/                  build and VXPEmu launch helpers
├── docs/                     project documentation
└── .vxpe/                    managed build implementation and template state
```

`.vxpe/platform/` contains common startup/linker files and CMake targets.
`.vxpe/template-state.json` records hashes of the last managed base.

Canonical template source: `template_blank/` + `template_blank/template.manifest.json`
(`version`, `layout_version`, `directories`, `files[]` with `policy`).

## Ownership policies

- `seed`: copy only during creation. Missing or edited files are not restored.
  Use this for code, scenes, and other content the project author owns.
  Examples: `src/main.c`, `src/scene_bindings.h`, `assets/scenes/*.dtfe`.
- `managed`: update only when the current local hash equals the last base hash.
  Missing files are restored. Modified files are preserved and reported.
  Examples: `CMakeLists.txt`, `scripts/*.bat`, `.vxpe/cmake/*`, platform sources.

The manifest is `template_blank/template.manifest.json`. Every source and target
must be a safe relative path. Add required empty directories to `directories`.
Never enumerate the template directory and copy it wholesale.

## Identity fields (`project.vxp.json`)

Preserved across open/sync — do not regenerate casually:

| Field | Meaning |
|-------|---------|
| `app_id` | MRE App ID (engine-issued; retail wants ≠ 0) |
| `app_name` | Base name for `.vxp` |
| `developer` | Vendor string used in signing identity |
| `screen.width/height` | Only 240×320 or 320×240 |
| `template` / `template_version` / `layout_version` | Sync contract |
| `mre.api`, `mre.ram_kb`, `mre.imsi` | MRE metadata |

Unknown extra keys: **preserve** on rewrite.

## Changing the template

1. Edit the canonical source under `template_blank/`.
2. Add/move its manifest mapping and choose the correct ownership policy.
3. Increment `version`; increment `layout_version` only for a structural contract
   that needs a new migration strategy.
4. Update CMake/scripts and keep legacy path resolution in the IDE.
5. Run `reports/harness_project_layout_v2.py` and create a new blank project
   (portrait **and** landscape).
6. For build-plumbing changes, build that new project for ARM.

Opening a layout-v2 project calls `ProjectStore.sync_template`. Layout-v1 projects
are not silently migrated or overwritten; runtime path selection keeps supporting
their root `cmake/`, `main/`, `mreapi/`, `resources/`, and `run/` folders.

## Code entry points

| Concern | File |
|---------|------|
| Create/open/sync project | `app/project_store.py` |
| Template manager | `app/project_template.py` |
| Build/run pipeline | `app/vxp_runner.py` |
| SDK discovery | `app/sdk_layout.py` |
| Scene store | `app/scene_screen_store.py` |
| DTFE format | `docs/guides/DTFE_FORMAT.md` |
