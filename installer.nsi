; FinanceDesk v1.1 — installer.nsi
; Script NSIS pour créer l'installateur Windows professionnel
; Prérequis : NSIS 3.x installé sur la machine de build
; Commande : makensis installer.nsi

;===========================================================================
; CONFIGURATION GÉNÉRALE
;===========================================================================

!define APP_NAME        "FinanceDesk"
!define APP_VERSION     "1.1"
!define APP_PUBLISHER   "SAIM Ltd"
!define APP_URL         "https://www.saim.com"
!define APP_EXE         "FinanceDesk.exe"
!define APP_ICON        "assets\logo.ico"
!define INSTALL_DIR     "$PROGRAMFILES64\${APP_NAME}"
!define REG_KEY         "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
!define OUTPUT_FILE     "FinanceDesk_v1.1_Setup.exe"

Name              "${APP_NAME} v${APP_VERSION}"
OutFile           "${OUTPUT_FILE}"
InstallDir        "${INSTALL_DIR}"
InstallDirRegKey  HKLM "${REG_KEY}" "InstallLocation"
RequestExecutionLevel admin
SetCompressor     /SOLID lzma

;===========================================================================
; INTERFACE MODERNE
;===========================================================================

!include "MUI2.nsh"
!include "FileFunc.nsh"

!define MUI_ABORTWARNING
!define MUI_ICON   "${APP_ICON}"
!define MUI_UNICON "${APP_ICON}"

; Couleur d'en-tête (bleu FinanceDesk)
!define MUI_HEADERIMAGE
!define MUI_BGCOLOR "FFFFFF"

; Pages installateur
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; Pages désinstallateur
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Langue
!insertmacro MUI_LANGUAGE "French"

;===========================================================================
; SECTION INSTALLATION
;===========================================================================

Section "FinanceDesk" SecMain

  SectionIn RO  ; Section obligatoire

  SetOutPath "$INSTDIR"

  ; Copier tous les fichiers depuis dist\FinanceDesk\
  File /r "dist\FinanceDesk\*.*"

  ; Créer le raccourci Bureau
  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" \
    "$INSTDIR\${APP_EXE}" "" \
    "$INSTDIR\${APP_EXE}" 0

  ; Créer le raccourci Menu Démarrer
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
    "$INSTDIR\${APP_EXE}" "" \
    "$INSTDIR\${APP_EXE}" 0
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\Désinstaller ${APP_NAME}.lnk" \
    "$INSTDIR\uninstall.exe"

  ; Écriture dans le registre Windows (Programmes & fonctionnalités)
  WriteRegStr   HKLM "${REG_KEY}" "DisplayName"      "${APP_NAME} v${APP_VERSION}"
  WriteRegStr   HKLM "${REG_KEY}" "DisplayVersion"   "${APP_VERSION}"
  WriteRegStr   HKLM "${REG_KEY}" "Publisher"        "${APP_PUBLISHER}"
  WriteRegStr   HKLM "${REG_KEY}" "URLInfoAbout"     "${APP_URL}"
  WriteRegStr   HKLM "${REG_KEY}" "InstallLocation"  "$INSTDIR"
  WriteRegStr   HKLM "${REG_KEY}" "UninstallString"  "$INSTDIR\uninstall.exe"
  WriteRegDWORD HKLM "${REG_KEY}" "NoModify"         1
  WriteRegDWORD HKLM "${REG_KEY}" "NoRepair"         1

  ; Calculer la taille installée
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKLM "${REG_KEY}" "EstimatedSize" "$0"

  ; Créer le désinstallateur
  WriteUninstaller "$INSTDIR\uninstall.exe"

SectionEnd

;===========================================================================
; SECTION DÉSINSTALLATION
;===========================================================================

Section "Uninstall"

  ; Supprimer les fichiers installés
  RMDir /r "$INSTDIR"

  ; Supprimer les raccourcis
  Delete "$DESKTOP\${APP_NAME}.lnk"
  RMDir /r "$SMPROGRAMS\${APP_NAME}"

  ; Supprimer les clés de registre
  DeleteRegKey HKLM "${REG_KEY}"

  ; Note : on NE supprime PAS les données utilisateur
  ; (%APPDATA%\FinanceDesk\) pour ne pas perdre la base SQLite

SectionEnd

;===========================================================================
; FONCTIONS
;===========================================================================

Function .onInit
  ; Vérifier si déjà installé — proposer désinstallation
  ReadRegStr $0 HKLM "${REG_KEY}" "UninstallString"
  StrCmp $0 "" done
    MessageBox MB_OKCANCEL|MB_ICONQUESTION \
      "FinanceDesk est déjà installé.$\n$\nCliquez OK pour le désinstaller avant de continuer." \
      IDOK uninst IDCANCEL done
    uninst:
      ExecWait '$0 /S'
  done:
FunctionEnd

Function .onInstSuccess
  ; Proposer de lancer l'app après installation
  MessageBox MB_YESNO "Installation terminée !$\n$\nLancer FinanceDesk maintenant ?" \
    IDYES launch IDNO done
  launch:
    Exec "$INSTDIR\${APP_EXE}"
  done:
FunctionEnd
