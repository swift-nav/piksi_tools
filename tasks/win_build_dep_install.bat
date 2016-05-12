echo off
setlocal
SET PATH=%PATH%;C:\cygwin\bin;
if exist "C:\Program Files (x86)\pythonxy" (
	echo "python already installed"
) else (
	if exist xy_install.exe (
		echo "python xy install cached"
	) else (
		echo "python xy install downloading"
		powershell -Command "Invoke-WebRequest 'http://ftp.ntua.gr/pub/devel/pythonxy/Python(x,y)-2.7.10.0.exe' -OutFile xy_install.exe"
	)
	echo "installing python xy"
	xy_install /S /FULL
)

echo "reinstalling python cryptography module"
echo y | C:\Python27\Scripts\pip uninstall cryptography
C:\Python27\Scripts\pip install cryptography

if exist C:\cygwin\bin\run.exe (
	echo "cygwin already installed"
) else (
	if exist cygwin_install.exe (
		echo "cygwin install cached"
	) else (
		echo "cygwin install downloading"
		powershell -Command "Invoke-WebRequest https://cygwin.com/setup-x86_64.exe -OutFile cygwin_install.exe"
	)
	echo "installing cygwin"
	cygwin_install --no-shortcuts --quiet-mode --disable-buggy-antivirus --packages git,make,wget --root C:\cygwin --site http://cygwin.mirror.constant.com
	set /p=Hit ENTER when install complete
)
echo "cygwin config"
c:\cygwin\bin\bash.exe tasks\win_build_dep_install.sh

SET Result=0
IF exist "C:\Program Files (x86)\NSIS\NSIS.exe" SET Result=1
IF exist "C:\Program Files\NSIS\NSIS.exe" SET Result=1

if %Result% EQU 1 (
	echo "NSIS already installed"
) else (
	if exist nsis_install.exe (
		echo "NSIS install cached"
	) else (
		echo "NSIS install downloading"
		c:\cygwin\bin\bash.exe tasks\nsis_download.sh
	)
	echo "installing NSIS"
	nsis_install /S
)
