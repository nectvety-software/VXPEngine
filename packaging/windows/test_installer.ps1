param([Parameter(Mandatory = $true)][string]$Installer)

$ErrorActionPreference = "Stop"
$Installer = (Resolve-Path -LiteralPath $Installer).Path
$TempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
$Probe = [IO.Path]::GetFullPath((Join-Path $TempRoot "VXPEngineInstallProbe")).TrimEnd('\')
if ([IO.Path]::GetDirectoryName($Probe).TrimEnd('\') -ne $TempRoot -or [IO.Path]::GetFileName($Probe) -ne "VXPEngineInstallProbe") {
    throw "Unsafe installer test path: $Probe"
}
if (Test-Path -LiteralPath $Probe) {
    Remove-Item -LiteralPath $Probe -Recurse -Force
}

$IsAdministrator = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $IsAdministrator) {
    $MsiLog = Join-Path $TempRoot "VXPEngineAdminImageProbe.log"
    Remove-Item -LiteralPath $MsiLog -Force -ErrorAction SilentlyContinue
    $extractArgs = @("/a", ('"' + $Installer + '"'), "/qn", "/norestart", ('TARGETDIR="' + $Probe + '"'), "/l*v", ('"' + $MsiLog + '"'))
    $extract = Start-Process -FilePath msiexec.exe -ArgumentList $extractArgs -WindowStyle Hidden -Wait -PassThru
    if ($extract.ExitCode -ne 0) { throw "MSI administrative extraction exited $($extract.ExitCode). Log: $MsiLog" }
    $ExtractedRoot = Join-Path $Probe "VXPEngine"
    $Python = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path ".venv\Scripts\python.exe"
    & $Python (Join-Path $PSScriptRoot "verify_release.py") $ExtractedRoot
    if ($LASTEXITCODE -ne 0) { throw "Extracted MSI release verification failed. Log: $MsiLog" }
    Remove-Item -LiteralPath $Probe -Recurse -Force
    Write-Host "PASS: non-elevated MSI extraction -> GUI/SDK/Qt collision smoke"
    exit 0
}

$SettingsKey = "HKCU:\Software\VXPEngine\VXPEngine"
New-Item -Path $SettingsKey -Force | Out-Null
New-ItemProperty -Path $SettingsKey -Name "InstallerPreserveProbe" -Value "keep" -PropertyType String -Force | Out-Null

$MsiLog = Join-Path $TempRoot "VXPEngineInstallProbe.log"
Remove-Item -LiteralPath $MsiLog -Force -ErrorAction SilentlyContinue
$installArgs = @("/i", ('"' + $Installer + '"'), "/qn", "/norestart", ('INSTALLFOLDER="' + $Probe + '"'), "/l*v", ('"' + $MsiLog + '"'))
$install = Start-Process -FilePath msiexec.exe -ArgumentList $installArgs -WindowStyle Hidden -Wait -PassThru
if ($install.ExitCode -ne 0) { throw "Installer exited $($install.ExitCode). Log: $MsiLog" }

$required = @(
    "VXPEngine.exe",
    "engine\coremre\sdk\w64devkit\bin\cmake.exe",
    "engine\coremre\sdk\arm-toolchain\bin\arm-none-eabi-gcc.exe",
    "engine\coremre\sdk\arm-toolchain\bin\zlib1.dll",
    "engine\coremre\sdk\mre\include\vmsys.h",
    "engine\coremre\sdk\vxpemu\VXPEmu.exe",
    "engine\coremre\sdk\python\VXPEPython.exe",
    "release-manifest.sha256.json"
)
foreach ($item in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $Probe $item))) {
        throw "Installed file missing: $item. Log: $MsiLog"
    }
}

$Python = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path ".venv\Scripts\python.exe"
& $Python (Join-Path $PSScriptRoot "verify_release.py") $Probe
if ($LASTEXITCODE -ne 0) { throw "Installed release verification failed" }

$uninstall = Start-Process -FilePath msiexec.exe -ArgumentList @("/x", $Installer, "/qn", "/norestart") -WindowStyle Hidden -Wait -PassThru
if ($uninstall.ExitCode -ne 0) { throw "Uninstaller exited $($uninstall.ExitCode)" }
Start-Sleep -Milliseconds 800
if (Test-Path -LiteralPath $Probe) { throw "Uninstaller left install directory: $Probe" }
if ((Get-ItemPropertyValue -Path $SettingsKey -Name "InstallerPreserveProbe" -ErrorAction SilentlyContinue) -ne "keep") {
    throw "Uninstaller removed VXPEngine user settings"
}
Remove-ItemProperty -Path $SettingsKey -Name "InstallerPreserveProbe" -ErrorAction SilentlyContinue
Write-Host "PASS: silent MSI -> installed runtime -> GUI/SDK smoke -> clean uninstall"
