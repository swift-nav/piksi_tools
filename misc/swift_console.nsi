; Swift Console NSIS Installer script

;--------------------------------

; The name of the installer
Name "Swift Console"

; The default installation directory
InstallDir "$PROGRAMFILES\Swift Navigation\Swift Console"

; The text to prompt the user to enter a directory
DirText "This will install Swift Console on your computer. Choose a directory"

; Show the message window in the uninstaller
ShowUninstDetails show
;--------------------------------

; The stuff to install
Section ""

; Set output path to the installation directory.
SetOutPath $INSTDIR

; file_to_check_for jump_if_present [jump_otherwise]
IfFileExists $INSTDIR\Uninstall.exe ask_to_uninstall inst
  
ask_to_uninstall:
  MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
  "There appears to be an existing installation of Swift Console in $INSTDIR.$\n \
  Click `OK` to remove the previous version or `Cancel` to cancel this upgrade." \
  IDOK silently_uninstall
  Abort

silently_uninstall:
  ; hack since the current uninstaller does not support silent mode
  ; ExecWait '"$INSTDIR\Uninstall.exe /S"'
  RMDir /r "$INSTDIR\*.*"

  Delete "$DESKTOP\Swift Console.lnk"
  Delete "$SMPROGRAMS\Swift Navigation\Swift Console.lnk"
  Delete "$SMPROGRAMS\Swift Navigation\Uninstall.lnk"
  RMDir "$SMPROGRAMS\Swift Navigation"

inst:
  ; Put a file there
  File /r "..\dist\console\*.*"

  ; Now create shortcuts
  CreateDirectory "$SMPROGRAMS\Swift Navigation"
  CreateShortCut "$SMPROGRAMS\Swift Navigation\Swift Console.lnk" "$INSTDIR\console.exe"
  CreateShortCut "$SMPROGRAMS\Swift Navigation\Uninstall.lnk" "$INSTDIR\Uninstall.exe"

  ;create desktop shortcut
  CreateShortCut "$DESKTOP\Swift Console.lnk" "$INSTDIR\console.exe" ""

  ; Tell the compiler to write an uninstaller and to look for a "Uninstall" section
  WriteUninstaller $INSTDIR\Uninstall.exe

SectionEnd ; end the section

; The uninstall section
Section "Uninstall"
SetOutPath $TEMP
MessageBox MB_OKCANCEL "The Uninstaller will remove the entire contents of folder $INSTDIR" IDYES true IDCancel false
true:
  Goto uninstall 
false: Goto uninstall_abort 

uninstall_abort:
     DetailPrint "Uninstall aborted"
     Abort

uninstall:
RMDir /r /REBOOTOK "$INSTDIR"

; Now remove shortcuts too
Delete "$DESKTOP\Swift Console.lnk"
Delete "$SMPROGRAMS\Swift Navigation\Swift Console.lnk"
Delete "$SMPROGRAMS\Swift Navigation\Uninstall.lnk"
RMDir "$SMPROGRAMS\Swift Navigation"


SectionEnd

