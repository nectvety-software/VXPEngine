# VXPEngine Windows release security

- The x64 MSI installs the immutable application/toolchain under Program Files
  with standard Windows Installer elevation. It uses a
  stable UpgradeCode so a newer release atomically replaces the entire frozen
  IDE, SDK and library set rather than mutating dependencies in place.
- No development or application private key is included. Signing identities are
  generated per App ID/vendor under `%LOCALAPPDATA%\VXPEngine\signing`.
- `VXPEPython.exe` only executes the bundled `vxp_pack.py`, `vxp_resource.py`, and
  `vxp_signer.py` tools; it is not a general-purpose script launcher.
- The release build fails if Bandit reports a high-severity issue, dependency
  audit reports a known vulnerability, or private-key material enters staging.
- `VXPEngine.exe` uses the Windows GUI subsystem, so it does not open a terminal.
- Public builds use `-RequireSignature -SigningCertificateThumbprint <SHA1>` and
  are Authenticode-signed and RFC3161 timestamped. An unsigned local MSI can be
  built for testing, but Windows SmartScreen may warn about it.
- RSA-512/SHA-1 remains in VXP signing solely because the legacy S30+/MRE VXP
  format requires it. SHA-256 is used for release and artifact integrity.
