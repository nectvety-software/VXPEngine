# Security, SDK, coremre, and signing

## Core

- `engine/coremre/` is the only core and SDK integration point.
- Distributable package: `packaging/coremre/<version>/` with
  `manifest.json`, `manifest.sig`, `coremre-sign-pub.pem`.
- Validated before build by `tools/verify_core.py` (RSA + per-file SHA-256).
- **Do not bypass** integrity/signature checks to make a build pass.
- CMake receives `-DCOREMRE_PACKAGE_DIR=...` from `VxpRunner._core_defines()`.
  Empty list `[]` only when no package exists (legacy in-tree core); `None` means
  package present but **invalid** → stop build.

## Signing

- Identity keyed by stable **App ID + vendor**, owned by VXPEngine.
- Store: `signing/apps/<appid>-<vendor>/` (engine), **never** inside a project.
- Tools: `app/signing_service.py`, `engine/coremre/tools/vxp_signer.py`.
- Do not invent a certificate ID or regenerate identity on every build.
- Unsigned development builds and signed retail builds are separate outputs.
- RSA-512/SHA-1 PKCS#1 v1.5 exists for **MRE compatibility**, not modern
  cryptographic strength; do not describe it as strong general-purpose security.
- A self-created key runs only when the device/firmware trust store accepts the
  corresponding public identity. Do not hide this compatibility limit.

## Secrets hygiene

Never place in project, example, template, console message, report, or installer:

- `signing/`, `.env`, `*.pem`, `*.key`, private key bytes, passphrases

`verify_release.py` scans staged files for PEM private-key patterns and fails
the release if found.

## SDK discovery (`app/sdk_layout.py`)

| Tool | Primary | Env override | Fallback examples |
|------|---------|--------------|-------------------|
| w64devkit | `engine/coremre/sdk/w64devkit` | `VXPE_W64DEVKIT` | `D:/MRE/lib/w64devkit` |
| ARM GCC | `engine/coremre/sdk/arm-toolchain` | `VXPE_ARM_TOOLCHAIN` | `C:/msys64/mingw64` |
| MRE SDK | `engine/coremre/sdk/mre` | `MRE_SDK` | legacy XimikBoda path |
| Tools | `engine/coremre/tools` | — | no legacy packer fallback |
| VXPEPython | `engine/coremre/sdk/python/VXPEPython.exe` | — | `sys.executable` |
| VXPEmu | `engine/coremre/sdk/vxpemu/VXPEmu.exe` | `VXPE_VXPEMU` | `D:/MRE/VXPEmu/...` |

Prefer integrated paths. Do not shell out to undocumented signers or include
external legacy SDKs (MREmu, TinyMRESDK).

## Frozen release (`packaging/windows/`)

- `VXPEngine.spec`: GUI, `console=False`, `contents_directory="app"`,
  `hiddenimports` must include every late import (`verify_core`).
- `qt_runtime_hook.py`: pin MSVC + System32 ICU + Qt6Core before app import.
- `build_release.ps1`: PyInstaller → stage → verify → ARM probe → WiX MSI.
- `verify_release.py`: subsystem GUI, no private keys, SDK probe, offscreen GUI
  startup with `VXPE_RELEASE_ACTION_PROBE=1` (imports `verify_core`).
- MSI is **per-machine** (`Program Files`) → install needs Administrator.

## Reporting

When touching signing/core/release, report:

- which package version / thumbprint / artifact paths  
- which verify steps ran  
- explicit statement that no private material was written outside the key store  
