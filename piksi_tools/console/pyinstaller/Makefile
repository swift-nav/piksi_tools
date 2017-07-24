piksi_tools_directory=../../
spec_file=console.spec
pyinstaller=pyinstaller
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

UNAME_LOWER = $(shell echo $(UNAME) | tr A-Z a-z)


console: $(spec_file)
	make clean
	echo $(UNAME)
	pyinstaller --clean --log-level=WARN --paths=$(piksi_tools_directory) --debug $(PLAT_ARGS) $(spec_file) -y
	echo "Pyinstaller completed. Building platform installer."
	make $(UNAME)

Windows:
	export VERSION=$(shell ./dist/console/console -V 2>&1 | cut -d ' ' -f 3)
	makensis "-XOutfile swift_console_v$(VERSION)_windows.exe" win_installer.nsi
Cygwin:
	export VERSION=$(shell ./dist/console/console -V 2>&1 | cut -d ' ' -f 3)
	makensis '-XOutfile swift_console_v$(VERSION)_windows.exe' win_installer.nsi
Darwin:
	export VERSION=$(shell ./dist/console/console -V 2>&1 | cut -d ' ' -f 3)
	sudo ./create-dmg-installer.sh swift_console_v$(VERSION)_osx.dmg
tar:
	export VERSION=$(shell ./dist/console/console -V 2>&1 | cut -d ' ' -f 3)
	mv ./dist/console ./dist/swift_console_v$(VERSION)_$(UNAME_LOWER)
	cd dist && tar cfvz swift_console_v$(VERSION)_$(UNAME_LOWER).tar.gz swift_console_v$(VERSION)_$(UNAME_LOWER)
Linux:
	make tar
clean:
	rm -rf build dist
