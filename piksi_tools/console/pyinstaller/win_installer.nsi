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

; Put a file there
File /r dist\console\*

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

