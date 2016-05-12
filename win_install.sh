version=`cat piksi_tools/RELEASE-VERSION`
installer="piksi_tools/console/pyinstaller/piksi_console_v${version}_setup.exe"
chmod 777 $installer
cygstart  --action=runas $installer /S
