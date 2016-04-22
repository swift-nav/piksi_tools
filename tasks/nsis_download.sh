#!/bin/bash
wget "http://iweb.dl.sourceforge.net/project/nsis/NSIS%202/2.40/nsis-2.40-setup.exe" -O nsis_install.exe
chmod 777 nsis_install.exe
echo 'PATH=$PATH:/cygdrive/c/Program\ Files\ \(x86\)/NSIS/' >> ~/.bashrc
