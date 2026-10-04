# VXPEngine 2.0.0 Windows release — security summary

Date: 2026-09-14

- Python dependency audit: 0 known vulnerabilities.
- Bandit: 0 High, 2 Medium, 15 Low findings across 23,492 lines.
- The two Medium findings are the RSA-512/SHA-1 operation required by the
  legacy S30+/MRE VXP signature format. Release/artifact integrity uses SHA-256.
- Private PEM keys in release staging: 0.
- Windows Defender signature 1.459.201.0: no threats found in the final installer.
- `VXPEngine.exe` PE subsystem: Windows GUI (no console window).
- Bundled SDK probe: passed.
- Packaged toolchain ARM build of MedievalArcheryDemo: passed.
- Silent install, installed GUI/SDK probe, settings-preserving uninstall: passed.
- Windows Authenticode: not signed (no commercial code-signing certificate was supplied).

Artifact: `dist-installer/VXPEngine-2.0.0-Setup.exe`

SHA-256: `80416A5FDAAF10E82609640F1989A40E38F83414D883084DBAE28DAAFFBEA89E`
