# VXPEngine Windows release security

- The x64 MSI installs the immutable application/toolchain under Program Files
  with standard Windows Installer elevation. It uses a
  stable UpgradeCode so a newer release atomically replaces the entire frozen
  IDE, SDK and library set rather than mutating dependencies in place.
- `VXPEPython.exe` only executes the bundled SDK tool scripts; it is not a
  general-purpose script launcher.
- The release build fails if Bandit reports a high-severity issue, dependency
  audit reports a known vulnerability, or private-key material enters staging.
- `VXPEngine.exe` uses the Windows GUI subsystem, so it does not open a terminal.
- Public builds use `-RequireSignature -SigningCertificateThumbprint <SHA1>` and
  are Authenticode-signed and RFC3161 timestamped. An unsigned local MSI can be
  built for testing, but Windows SmartScreen may warn about it.
