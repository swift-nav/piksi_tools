echo off
if exist C:\Python27\python.exe (
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
	cygwin_install --no-shortcuts --quiet-mode --disable-buggy-antivirus --packages git,make --root C:\cygwin --site http://cygwin.mirror.constant.com
)

echo "reinstalling python cryptography module"
echo y | C:\Python27\Scripts\pip uninstall cryptography
C:\Python27\Scripts\pip install cryptography

echo "cygwin config"
set PATH=C:\cygwin\bin;
c:\cygwin\bin\bash.exe tasks\win_build_dep_install.sh