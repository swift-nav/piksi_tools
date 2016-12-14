piksi_tools_directory=../../
spec_file=console.spec
pyinstaller=pyinstaller
VERSION=$(shell cat ../../RELEASE-VERSION)
LIBS=-lm

ifneq (,$(findstring /cygdrive/,$(PATH)))
    UNAME := Cygwin
    PLAT_ARGS="-F"
else
ifneq (,$(findstring WINDOWS,$(PATH)))
    UNAME := Windows
    PLAT_ARGS="-F"
else
    UNAME := $(shell uname -s)
    PLAT_ARGS="-w"
endif
endif


console: $(spec_file)
	make clean
	echo $(UNAME)
	pyinstaller --clean --log-level=WARN --paths=$(piksi_tools_directory) --debug $(PLAT_ARGS) $(spec_file) -y
	echo "Pyinstaller completed. Building platform installer."
	make $(UNAME)

Windows:
	makensis "-XOutfile swift_console_v$(VERSION)_setup.exe" win_installer.nsi
Cygwin:
	makensis '-XOutfile swift_console_v$(VERSION)_setup.exe' win_installer.nsi
Darwin:
	sudo ./create-dmg-installer.sh
Linux:
	tar cfvz swift_console_v$(VERSION).tar.gz ./dist/console 
	mv swift_console_v$(VERSION).tar.gz ./dist/
clean:
	rm -rf build dist


