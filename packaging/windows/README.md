# Windows MSI release

VXPEngine is installed per-machine under Program Files and bundles the GUI, coremre, MRE SDK,
w64devkit, ARM GCC, VXP packers, restricted SDK Python and VXPEmu. Updating the
MSI replaces this frozen set atomically, so libraries cannot drift independently.

## Local test build

```powershell
.\packaging\windows\build_release.ps1 -SkipSecurityScan
.\packaging\windows\test_installer.ps1 -Installer .\dist-installer\VXPEngine-2.0.0-x64.msi
```

## Trusted public build

Import a trusted Code Signing certificate into the current user's certificate
store, then build with its SHA-1 thumbprint:

```powershell
.\packaging\windows\build_release.ps1 `
  -RequireSignature `
  -SigningCertificateThumbprint "CERTIFICATE_SHA1_THUMBPRINT"
```

The pipeline signs `VXPEngine.exe`, the restricted SDK host, and the MSI with
SHA-256 plus an RFC3161 timestamp. It fails if signing or signature validation
fails. Upload both `.msi` and `.msi.sha256` as assets of the same GitHub release.
The in-app updater downloads both, verifies SHA-256 and the pinned Authenticode
certificate, starts `msiexec`, and exits the running IDE before replacement.

An unsigned local build is suitable only for testing. No technical setting can
guarantee that SmartScreen, Smart App Control, enterprise policy, or antivirus
will allow an unsigned binary on every computer. Use a publicly trusted OV/EV
Code Signing certificate and keep its publisher reputation for public releases.
