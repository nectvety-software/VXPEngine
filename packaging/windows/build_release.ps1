param(
    [string]$OutputDirectory = "",
    [string]$SigningCertificateThumbprint = "",
    [string]$TimestampUrl = "http://timestamp.digicert.com",
    [switch]$RequireSignature,
    [switch]$SkipSecurityScan,
    [switch]$ReuseStage
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$TempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
$WorkRoot = Join-Path $TempBase "VXPEngineReleaseBuild-2.0.0"
$Stage = Join-Path $WorkRoot "stage"
$PyDist = Join-Path $WorkRoot "pyinstaller-dist"
$PyWork = Join-Path $WorkRoot "pyinstaller-work"
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $Root "dist-installer" }
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
$Installer = Join-Path $OutputDirectory "VXPEngine-2.0.0-x64.msi"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Missing virtual environment: $Python"
}

function Reset-SafeWorkDirectory([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $parent = [IO.Path]::GetDirectoryName($full).TrimEnd('\')
    if ($parent -ne $TempBase -or [IO.Path]::GetFileName($full) -ne "VXPEngineReleaseBuild-2.0.0") {
        throw "Refusing to reset unsafe work directory: $full"
    }
    if (Test-Path -LiteralPath $full) { Remove-Item -LiteralPath $full -Recurse -Force }
    New-Item -ItemType Directory -Path $full | Out-Null
}

function Copy-Tree([string]$Source, [string]$Destination, [string[]]$Extra = @()) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $arguments = @($Source, $Destination, "/E", "/R:2", "/W:1", "/NFL", "/NDL", "/NJH", "/NJS", "/NP") + $Extra
    & robocopy.exe @arguments | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "Robocopy failed ($LASTEXITCODE): $Source" }
}

function Copy-ImmediateFiles([string]$Source, [string]$Destination) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Get-ChildItem -LiteralPath $Source -File | Copy-Item -Destination $Destination -Force
}

function Find-SignTool {
    $command = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $kits = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
    if (Test-Path -LiteralPath $kits) {
        $candidate = Get-ChildItem -LiteralPath $kits -Recurse -Filter signtool.exe -File |
            Where-Object { $_.FullName -match '\\x64\\signtool\.exe$' } |
            Sort-Object FullName -Descending | Select-Object -First 1
        if ($candidate) { return $candidate.FullName }
    }
    return ""
}

function Sign-ReleaseFile([string]$Path) {
    if (-not $SigningCertificateThumbprint) { return }
    $signTool = Find-SignTool
    if (-not $signTool) { throw "Signing requested but signtool.exe was not found" }
    & $signTool sign /sha1 $SigningCertificateThumbprint /fd SHA256 /tr $TimestampUrl /td SHA256 $Path
    if ($LASTEXITCODE -ne 0) { throw "Authenticode signing failed: $Path" }
    $signature = Get-AuthenticodeSignature -LiteralPath $Path
    if ($signature.Status -ne "Valid") { throw "Invalid Authenticode signature: $Path ($($signature.Status))" }
}

if ($RequireSignature -and -not $SigningCertificateThumbprint) {
    throw "Public MSI requires -SigningCertificateThumbprint <trusted code-signing certificate SHA1>"
}

$ArmTarget = Join-Path $Stage "engine\coremre\sdk\arm-toolchain"
if (-not $ReuseStage) {
Reset-SafeWorkDirectory $WorkRoot
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

if (-not $SkipSecurityScan) {
    Write-Host "[Security] Bandit source scan"
    & $Python -m bandit -r (Join-Path $Root "app") (Join-Path $Root "simulator") (Join-Path $Root "engine\coremre\tools") -x "*/__pycache__/*" -f json -o (Join-Path $Root "reports\security_bandit.json")
    $bandit = Get-Content (Join-Path $Root "reports\security_bandit.json") -Raw | ConvertFrom-Json
    if ($bandit.metrics._totals.'SEVERITY.HIGH' -gt 0) { throw "Bandit found high-severity issues" }
    Write-Host "[Security] Python dependency audit"
    & $Python -m pip_audit -r (Join-Path $Root "requirements.txt") --format json --output (Join-Path $Root "reports\security_dependencies.json")
    if ($LASTEXITCODE -ne 0) { throw "Dependency audit failed" }
}

Write-Host "[Package] Build terminal-free VXPEngine GUI"
& $Python -m PyInstaller --noconfirm --clean --distpath $PyDist --workpath $PyWork (Join-Path $PSScriptRoot "VXPEngine.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller GUI build failed" }

# PyInstaller brings the Python 3.12 MSVC runtime (14.38) into the contents
# root, while current PySide6 carries 14.44 and QtCore imports symbols added in
# that newer runtime. Windows loads the root copy first on a clean machine,
# causing "DLL load failed ... specified procedure could not be found". Make
# the first-search copy identical to the runtime shipped with PySide6.
$FrozenAppDir = Join-Path $PyDist "VXPEngine\app"
$PySideRuntimeDir = Join-Path $Root ".venv\Lib\site-packages\PySide6"
$MsvcRuntimeNames = @(
    "concrt140.dll", "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll",
    "msvcp140_codecvt_ids.dll", "vcruntime140.dll", "vcruntime140_1.dll"
)
foreach ($runtimeName in $MsvcRuntimeNames) {
    $runtimeSource = Join-Path $PySideRuntimeDir $runtimeName
    if (-not (Test-Path -LiteralPath $runtimeSource)) {
        throw "PySide6 MSVC runtime is incomplete: $runtimeSource"
    }
    Copy-Item -LiteralPath $runtimeSource -Destination (Join-Path $FrozenAppDir $runtimeName) -Force
}

# Qt 6.11 on Windows links to the stable Windows ICU shim (icuuc.dll).  On the
# build host PyInstaller can resolve that name to a versioned third-party ICU
# implementation instead and copy it beside the executable.  That DLL exports
# ucnv_open_78 while Qt imports ucnv_open, producing WinError 127 on a clean
# machine.  Never redistribute the build host's ICU here; the runtime hook
# explicitly loads the supported Windows System32 shim before QtCore.
Get-ChildItem -LiteralPath $FrozenAppDir -File -Filter "icu*.dll" -ErrorAction SilentlyContinue |
    ForEach-Object {
        Write-Host "[Package] Remove incompatible bundled ICU: $($_.Name)"
        Remove-Item -LiteralPath $_.FullName -Force
    }
Copy-Tree (Join-Path $PyDist "VXPEngine") $Stage

Write-Host "[Package] Build restricted SDK Python host"
$SdkPythonDir = Join-Path $Stage "engine\coremre\sdk\python"
New-Item -ItemType Directory -Path $SdkPythonDir -Force | Out-Null
& $Python -m PyInstaller --noconfirm --clean --onefile --console --name VXPEPython --distpath $SdkPythonDir --workpath (Join-Path $PyWork "sdk-python") --specpath (Join-Path $WorkRoot "sdk-spec") --hidden-import cryptography (Join-Path $PSScriptRoot "vxpe_python_dispatcher.py")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller SDK host build failed" }

Write-Host "[Package] Copy application data and integrated SDK"
Copy-Tree (Join-Path $Root "app\resources") (Join-Path $Stage "app\resources")
Copy-Tree (Join-Path $Root "assets") (Join-Path $Stage "assets")
Copy-Tree (Join-Path $Root "docs") (Join-Path $Stage "docs")
Copy-Tree (Join-Path $Root "ai") (Join-Path $Stage "ai") @("/XD", "__pycache__")
Copy-Tree (Join-Path $Root "template_blank") (Join-Path $Stage "template_blank") @("/XD", "build-arm", "build-arm-core", "build-arm-signed", "build-win32", "engine", "signing", "__pycache__")
Copy-Tree (Join-Path $Root "examples") (Join-Path $Stage "examples") @("/XD", "build-arm", "build-arm-signed", "build-win32", "__pycache__", "/XF", ".env", "*.pem")
Copy-Tree (Join-Path $Root "engine\coremre") (Join-Path $Stage "engine\coremre") @("/XD", "sdk", "__pycache__", "/XF", "*.pyc")
Copy-Tree (Join-Path $Root "engine\coremre\sdk\mre") (Join-Path $Stage "engine\coremre\sdk\mre")
Copy-Tree (Join-Path $Root "packaging\coremre\2.0.0") (Join-Path $Stage "packaging\coremre\2.0.0")
Copy-Item -LiteralPath (Join-Path $Root "packaging\vxp_sample_assets.zip") -Destination (Join-Path $Stage "packaging\vxp_sample_assets.zip") -Force
Copy-Item -LiteralPath (Join-Path $Root "README.md") -Destination $Stage -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "SECURITY.md") -Destination $Stage -Force
$updatePolicy = [ordered]@{
    require_authenticode = [bool]$SigningCertificateThumbprint
    signer_thumbprint = $SigningCertificateThumbprint.Replace(" ", "").ToUpperInvariant()
    channel_url = "https://api.github.com/repos/vxpstore/VXPEngine/releases/latest"
}
$updatePolicy | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Stage "update-policy.json") -Encoding utf8

Copy-Tree "D:\MRE\lib\w64devkit" (Join-Path $Stage "engine\coremre\sdk\w64devkit") @("/XD", "src")

$ArmSource = "C:\msys64\mingw64"
Copy-Tree (Join-Path $ArmSource "bin") (Join-Path $ArmTarget "bin")

# GCC's cc1.exe dynamically depends on zlib1.dll.  Robocopying the source bin
# should include it, but enforce it explicitly so an incomplete ARM runtime can
# never reach the MSI stage unnoticed.
$ArmZlibSource = Join-Path $ArmSource "bin\zlib1.dll"
$ArmZlibTarget = Join-Path $ArmTarget "bin\zlib1.dll"
if (-not (Test-Path -LiteralPath $ArmZlibSource)) {
    throw "ARM toolchain runtime missing on build host: $ArmZlibSource"
}
Copy-Item -LiteralPath $ArmZlibSource -Destination $ArmZlibTarget -Force
if (-not (Test-Path -LiteralPath $ArmZlibTarget)) {
    throw "Release ARM toolchain is missing required zlib1.dll: $ArmZlibTarget"
}

Copy-Tree (Join-Path $ArmSource "arm-none-eabi\bin") (Join-Path $ArmTarget "arm-none-eabi\bin")
Copy-Tree (Join-Path $ArmSource "arm-none-eabi\include") (Join-Path $ArmTarget "arm-none-eabi\include")
Copy-ImmediateFiles (Join-Path $ArmSource "arm-none-eabi\lib") (Join-Path $ArmTarget "arm-none-eabi\lib")
Copy-Tree (Join-Path $ArmSource "arm-none-eabi\lib\thumb\nofp") (Join-Path $ArmTarget "arm-none-eabi\lib\thumb\nofp")
$GccVersion = (Get-ChildItem (Join-Path $ArmSource "lib\gcc\arm-none-eabi") -Directory | Sort-Object Name -Descending | Select-Object -First 1).Name
$GccSource = Join-Path $ArmSource "lib\gcc\arm-none-eabi\$GccVersion"
$GccTarget = Join-Path $ArmTarget "lib\gcc\arm-none-eabi\$GccVersion"
Copy-ImmediateFiles $GccSource $GccTarget
foreach ($name in @("include", "include-fixed", "install-tools", "thumb\nofp")) {
    Copy-Tree (Join-Path $GccSource $name) (Join-Path $GccTarget $name)
}

$VxpEmuSource = $env:VXPE_VXPEMU_SOURCE
if (-not $VxpEmuSource) {
    $VxpEmuSource = @(
        "D:\MRE\VXPEmu\deploy",
        "D:\MRE\VXPEmu\build\Release"
    ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $VxpEmuSource -or -not (Test-Path -LiteralPath (Join-Path $VxpEmuSource "VXPEmu.exe"))) {
    throw "VXPEmu runtime not found. Set VXPE_VXPEMU_SOURCE or build VXPEmu first."
}
Write-Host "[Package] VXPEmu runtime: $VxpEmuSource"
Copy-Tree $VxpEmuSource (Join-Path $Stage "engine\coremre\sdk\vxpemu") @(
    "/XF", "*.log", "*.pdb", "*.lib", "*.exp"
)
New-Item -ItemType Directory -Path (Join-Path $Stage "libs") -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $Root "libs\ffmpeg.exe") -Destination (Join-Path $Stage "libs\ffmpeg.exe") -Force
} elseif (-not (Test-Path -LiteralPath (Join-Path $Stage "VXPEngine.exe"))) {
    throw "Cannot reuse missing release stage: $Stage"
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

Write-Host "[Verify] Frozen GUI, private-key exclusion and SDK dispatcher"
& $Python (Join-Path $PSScriptRoot "verify_release.py") $Stage
if ($LASTEXITCODE -ne 0) { throw "Release verification failed" }

Write-Host "[Verify] Build MedievalArcheryDemo with the packaged toolchain"
$BuildProbe = Join-Path $WorkRoot "build-probe"
if (Test-Path -LiteralPath $BuildProbe) {
    $resolvedProbe = [IO.Path]::GetFullPath($BuildProbe).TrimEnd('\')
    if ([IO.Path]::GetDirectoryName($resolvedProbe).TrimEnd('\') -ne [IO.Path]::GetFullPath($WorkRoot).TrimEnd('\')) {
        throw "Refusing to reset unsafe build probe: $resolvedProbe"
    }
    Remove-Item -LiteralPath $resolvedProbe -Recurse -Force
}
Copy-Tree (Join-Path $Root "examples\MedievalArcheryDemo") $BuildProbe @("/XD", "build-arm", "build-arm-signed", "build-win32", "__pycache__", "/XF", ".env", "*.pem")
$Cmake = Join-Path $Stage "engine\coremre\sdk\w64devkit\bin\cmake.exe"
$Ninja = Join-Path $Stage "engine\coremre\sdk\w64devkit\bin\ninja.exe"
$Toolchain = Join-Path $BuildProbe "cmake\toolchain-arm-none-eabi.cmake"
$MreSdk = Join-Path $Stage "engine\coremre\sdk\mre"
$SdkTools = Join-Path $Stage "engine\coremre\tools"
$CorePackage = Join-Path $Stage "packaging\coremre\2.0.0"
$SdkPython = Join-Path $Stage "engine\coremre\sdk\python\VXPEPython.exe"
$env:PATH = "$ArmTarget\bin;$(Join-Path $Stage 'engine\coremre\sdk\w64devkit\bin');$env:PATH"
& $Cmake -S $BuildProbe -B (Join-Path $BuildProbe "build-arm") -G "Ninja" "-DCMAKE_TOOLCHAIN_FILE=$Toolchain" -DCMAKE_BUILD_TYPE=Release "-DTOOLCHAIN_PREFIX=$ArmTarget" "-DCMAKE_MAKE_PROGRAM=$Ninja" "-DMRE_SDK=$MreSdk" "-DVXPE_PYTHON=$SdkPython" "-DVXPE_SDK_TOOLS=$SdkTools" "-DCOREMRE_PACKAGE_DIR=$CorePackage"
if ($LASTEXITCODE -ne 0) { throw "Packaged ARM configure probe failed" }
& $Cmake --build (Join-Path $BuildProbe "build-arm") --target main_vxp
if ($LASTEXITCODE -ne 0) { throw "Packaged ARM build probe failed" }
if (-not (Test-Path (Join-Path $BuildProbe "build-arm\main\arrowfall_duel.vxp"))) { throw "Packaged build did not create arrowfall_duel.vxp" }

Write-Host "[Package] Generate integrity manifest"
$manifest = Get-ChildItem -LiteralPath $Stage -Recurse -File | ForEach-Object {
    [pscustomobject]@{
        path = $_.FullName.Substring($Stage.Length + 1).Replace('\', '/')
        size = $_.Length
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }
}
$manifest | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $Stage "release-manifest.sha256.json") -Encoding utf8

if ($SigningCertificateThumbprint) {
    Write-Host "[Sign] Authenticode-sign application executables"
    Sign-ReleaseFile (Join-Path $Stage "VXPEngine.exe")
    Sign-ReleaseFile (Join-Path $Stage "engine\coremre\sdk\python\VXPEPython.exe")
    # Signing changes bytes, so refresh the integrity manifest afterwards.
    $manifest = Get-ChildItem -LiteralPath $Stage -Recurse -File | ForEach-Object {
        [pscustomobject]@{ path = $_.FullName.Substring($Stage.Length + 1).Replace('\', '/'); size = $_.Length; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
    }
    $manifest | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $Stage "release-manifest.sha256.json") -Encoding utf8
}

Write-Host "[Installer] Harvest runtime and compile MSI"
$Wix3 = "C:\Program Files (x86)\WiX Toolset v3.14\bin"
$Heat = Join-Path $Wix3 "heat.exe"
$Candle = Join-Path $Wix3 "candle.exe"
$Light = Join-Path $Wix3 "light.exe"
foreach ($tool in @($Heat, $Candle, $Light)) {
    if (-not (Test-Path -LiteralPath $tool)) { throw "WiX Toolset 3.14 missing: $tool" }
}
$WixWork = Join-Path $WorkRoot "wix"
New-Item -ItemType Directory -Path $WixWork -Force | Out-Null
$Harvest = Join-Path $WixWork "stage-files.wxs"
$HarvestObj = Join-Path $WixWork "stage-files.wixobj"
$ProductObj = Join-Path $WixWork "VXPEngine.wixobj"
& $Heat dir $Stage -cg VXPEngineFiles -dr INSTALLFOLDER -srd -sreg -gg -ke -var var.StageDir -out $Harvest
if ($LASTEXITCODE -ne 0) { throw "WiX heat harvest failed" }
& $Candle -nologo -arch x64 "-dStageDir=$Stage" "-dProjectRoot=$Root" -out $HarvestObj $Harvest
if ($LASTEXITCODE -ne 0) { throw "WiX candle harvest compile failed" }
& $Candle -nologo -arch x64 "-dProjectRoot=$Root" -out $ProductObj (Join-Path $PSScriptRoot "VXPEngine.wxs")
if ($LASTEXITCODE -ne 0) { throw "WiX candle product compile failed" }
& $Light -nologo -sice:ICE60 -out $Installer $ProductObj $HarvestObj
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $Installer)) { throw "WiX MSI link failed" }
Sign-ReleaseFile $Installer
$hash = (Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash
"$hash *$([IO.Path]::GetFileName($Installer))" | Set-Content -LiteralPath "$Installer.sha256" -Encoding ascii
Write-Host "[DONE] $Installer"
Write-Host "[SHA256] $hash"
