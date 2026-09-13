Unicode true
RequestExecutionLevel admin
SetCompressor /SOLID lzma
SetCompressorDictSize 32

!include "MUI2.nsh"

!ifndef ROOT_DIR
  !define ROOT_DIR "."
!endif
!ifndef OUT_FILE
  !define OUT_FILE "MilkWeigh-Setup.exe"
!endif
!ifndef APP_ICON
  !define APP_ICON "${ROOT_DIR}/app.ico"
!endif
!ifndef APP_VERSION
  !define APP_VERSION "1.0.0"
!endif

!define PAYLOAD_DIR "${ROOT_DIR}/payload"
!define CONFIG_DIR "${ROOT_DIR}/config"
!define PRODUCT_NAME "牧衡辅料称重防错系统"
!define PRODUCT_KEY "MilkWeigh"
!define SERVICE_SCRIPT "$INSTDIR\server\MilkWeighService.py"

Name "${PRODUCT_NAME}"
OutFile "${OUT_FILE}"
Icon "${APP_ICON}"
UninstallIcon "${APP_ICON}"
InstallDir "$PROGRAMFILES64\MilkWeigh"
InstallDirRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MilkWeigh" "InstallLocation"
BrandingText "${PRODUCT_NAME}"
VIProductVersion "1.0.0.0"
VIAddVersionKey /LANG=2052 "ProductName" "${PRODUCT_NAME}"
VIAddVersionKey /LANG=2052 "CompanyName" "牧衡"
VIAddVersionKey /LANG=2052 "FileDescription" "${PRODUCT_NAME} 安装程序"
VIAddVersionKey /LANG=2052 "FileVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=2052 "ProductVersion" "${APP_VERSION}"

!define MUI_ABORTWARNING
!define MUI_ICON "${APP_ICON}"
!define MUI_UNICON "${APP_ICON}"
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "打开管理后台"
!define MUI_FINISHPAGE_RUN_FUNCTION OpenAdminUi

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "SimpChinese"

Function OpenAdminUi
  ExecShell "open" "http://127.0.0.1:8011/"
FunctionEnd

Function StopExistingService
  IfFileExists "${SERVICE_SCRIPT}" 0 done
  nsExec::ExecToLog '"$INSTDIR\python\python.exe" "${SERVICE_SCRIPT}" stop'
  Sleep 1200
  nsExec::ExecToLog '"$INSTDIR\python\python.exe" "${SERVICE_SCRIPT}" remove'
  Sleep 600
  done:
FunctionEnd

Section "Install"
  SetShellVarContext all
  SetRegView 64
  Call StopExistingService

  SetOutPath "$INSTDIR"
  File /r "${PAYLOAD_DIR}/*.*"

  SetOutPath "$COMMONPROGRAMDATA\MilkWeigh\config"
  File /nonfatal "${CONFIG_DIR}/.env"
  File /r "${CONFIG_DIR}/*.*"
  CreateDirectory "$COMMONPROGRAMDATA\MilkWeigh\data"
  CreateDirectory "$COMMONPROGRAMDATA\MilkWeigh\logs"

  nsExec::ExecToLog 'icacls "$COMMONPROGRAMDATA\MilkWeigh" /inheritance:r /grant:r SYSTEM:(OI)(CI)F Administrators:(OI)(CI)F'
  nsExec::ExecToLog '"$INSTDIR\python\python.exe" "$INSTDIR\server\seed_install.py"'

  ExecWait '"$INSTDIR\python\python.exe" "${SERVICE_SCRIPT}" install' $0
  nsExec::ExecToLog 'sc config MilkWeighBackend start= auto'
  nsExec::ExecToLog 'sc failure MilkWeighBackend reset= 86400 actions= restart/5000/restart/10000/restart/30000'
  ExecWait '"$INSTDIR\python\python.exe" "${SERVICE_SCRIPT}" start' $0

  nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="MilkWeigh Backend"'
  nsExec::ExecToLog 'netsh advfirewall firewall add rule name="MilkWeigh Backend" dir=in action=allow protocol=TCP localport=8011'

  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MilkWeigh" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MilkWeigh" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MilkWeigh" "Publisher" "牧衡"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MilkWeigh" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MilkWeigh" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MilkWeigh" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MilkWeigh" "NoRepair" 1

  SetOutPath "$INSTDIR"
  CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" "http://127.0.0.1:8011/" "" "$INSTDIR\app.ico" 0
  CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\打开管理后台.lnk" "http://127.0.0.1:8011/" "" "$INSTDIR\app.ico" 0
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\卸载.lnk" "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
  SetShellVarContext all
  SetRegView 64
  nsExec::ExecToLog '"$INSTDIR\python\python.exe" "${SERVICE_SCRIPT}" stop'
  Sleep 1200
  nsExec::ExecToLog '"$INSTDIR\python\python.exe" "${SERVICE_SCRIPT}" remove'

  Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
  RMDir /r "$SMPROGRAMS\${PRODUCT_NAME}"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MilkWeigh"
  RMDir /r "$INSTDIR"
SectionEnd
