Unicode True
SetCompressor /SOLID lzma
SetCompressorDictSize 64

!include "MUI2.nsh"

!ifndef STAGE_DIR
  !error "STAGE_DIR is required"
!endif
!ifndef OUTPUT_EXE
  !error "OUTPUT_EXE is required"
!endif

Name "VXPEngine 2.0.0"
OutFile "${OUTPUT_EXE}"
InstallDir "$LOCALAPPDATA\Programs\VXPEngine"
InstallDirRegKey HKCU "Software\VXPEngine\Installer" "InstallDir"
RequestExecutionLevel user
ShowInstDetails show
ShowUninstDetails show
BrandingText "VXPEngine · MRE VXP SDK"

!define MUI_ABORTWARNING
!define MUI_ICON "..\..\app\resources\resources\app-icon.ico"
!define MUI_UNICON "..\..\app\resources\resources\app-icon.ico"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Vietnamese"
!insertmacro MUI_LANGUAGE "English"

Section "VXPEngine" SEC_MAIN
  SetOutPath "$INSTDIR"
  File /r "${STAGE_DIR}\*.*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\VXPEngine\Installer" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VXPEngine" "DisplayName" "VXPEngine 2.0.0"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VXPEngine" "DisplayVersion" "2.0.0"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VXPEngine" "Publisher" "VXPEngine"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VXPEngine" "UninstallString" "$\"$INSTDIR\Uninstall.exe$\""
  CreateDirectory "$SMPROGRAMS\VXPEngine"
  CreateShortcut "$SMPROGRAMS\VXPEngine\VXPEngine.lnk" "$INSTDIR\VXPEngine.exe"
  CreateShortcut "$DESKTOP\VXPEngine.lnk" "$INSTDIR\VXPEngine.exe"
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\VXPEngine.lnk"
  Delete "$SMPROGRAMS\VXPEngine\VXPEngine.lnk"
  RMDir "$SMPROGRAMS\VXPEngine"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VXPEngine"
  DeleteRegKey HKCU "Software\VXPEngine\Installer"
  RMDir /r "$INSTDIR"
  ; Project files and per-user signing identities in AppData are retained.
SectionEnd
