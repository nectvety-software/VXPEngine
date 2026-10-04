# VXPEngine workflows

## Source-of-truth map

| Concern | Source of truth | Generated / derived |
|---------|-----------------|---------------------|
| Project metadata | `project.vxp.json` | — |
| Scene / layout | `assets/scenes/*.dtfe` | — |
| Screen registry | `assets/scenes/screens.dtfe` | — |
| C bindings | — | `src/scene_bindings.h` |
| Resource pixels | `assets/**` | `resources/gen/*.raw` |
| Project create/sync | `app/project_store.py`, `app/project_template.py` | — |
| Build/run | `app/vxp_runner.py` | `build-arm/**/*.vxp` |
| SDK paths | `app/sdk_layout.py` | — |
| Core package verify | `tools/verify_core.py` | — |
| Emulator | packaged `sdk/vxpemu/VXPEmu.exe` or `D:/MRE/VXPEmu` | — |
| Frozen release | `packaging/windows/*` | `dist-installer/*.msi` |

## Common checks

```powershell
.\.venv\Scripts\python.exe -m py_compile app\project_store.py app\project_template.py app\vxp_runner.py
.\.venv\Scripts\python.exe reports\harness_project_layout_v2.py
.\.venv\Scripts\python.exe reports\harness_no_template.py
.\.venv\Scripts\python.exe reports\harness_design_pipeline.py
run_windows.bat check
```

Full self-test (editor + SDK + demos):

```bat
run_windows.bat test
```

## Layout-v2 project commands

```bat
scripts\build_arm.bat
scripts\run_vxpemu.bat
```

Use the IDE's `VxpRunner` for authoritative signed builds because it injects the
validated core package and signing identity. A successful build produces
`build-arm/main/<app_name>.vxp` or its signed counterpart.

## Create → design → build loop

```text
create_project  →  edit .dtfe / src  →  regenerate bindings
       →  build_arm (CMake + **Ninja** + arm-none-eabi)  →  run_vxpemu
       →  (optional) build_arm_signed
```

Generator là **Ninja** (không phải MinGW Makefiles) vì path cài đặt/project
thường chứa khoảng trắng (`Program Files`, `VXP Projects`) — Make sẽ fail
try_compile với `'C:/Program' is not recognized`.

Details: `create-project.md`.

## Verification depth

- **UI-only change**: focused offscreen harness and reopen/persistence check.
- **DTFE/generator change**: regenerate bindings/resources and compare semantics.
- **CMake/toolchain/core/resource change**: clean configure and real ARM build.
- **Signing change**: build signed, cryptographically verify, and scan output/project
  for private-key leakage.
- **Template change**: create new portrait and landscape projects, test safe sync,
  and verify no build/cache/engine/signing directories are materialized.
- **Frozen/MSI change**: `verify_release.py` probe (`VXPE_RELEASE_ACTION_PROBE=1`),
  confirm dynamic imports (`verify_core`) in archive, elevated MSI smoke.

## Release packaging (Windows)

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File packaging\windows\build_release.ps1 -SkipSecurityScan
# optional: packaging\windows\test_installer.ps1 -Installer .\dist-installer\VXPEngine-2.0.0-x64.msi
```

Notes:

- Spec must list every late/dynamic import (`hiddenimports`).
- Per-machine MSI install needs Administrator (error 1730 otherwise).
- Stage reuse: `-ReuseStage` skips PyInstaller/toolchain copy — only after stage
  is known good and GUI sources unchanged **or** you re-synced PyInstaller output.

## When something fails

Read `troubleshooting.md` first. Always capture:

1. Exact message / traceback  
2. `native_crash.log` tail if GUI  
3. Whether source mode (`run_windows.bat`) or frozen (`Program Files`)  
4. Artifact paths that were or were not produced  
