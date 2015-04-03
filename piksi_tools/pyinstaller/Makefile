piksi_tools_directory=../
spec_file=console.spec
pyinstaller=pyinstaller

LIBS=-lm

ifneq (,$(findstring /cygdrive/,$(PATH)))
    UNAME := Cygwin
else
ifneq (,$(findstring WINDOWS,$(PATH)))
    UNAME := Windows
else
    UNAME := $(shell uname -s)
endif
endif


console: $(spec_file)
	make clean
	sudo pyinstaller --clean --log-level=DEBUG --paths=$(piksi_tools_directory) --debug -w $(spec_file) -y >& manifest.out
	echo "Pyinstaller completed. View output in manifest.out"
	make $(UNAME)

Windows:
		echo "Makefile not configured to build Windows installers"
Darwin:
		sudo ./create-dmg-installer.sh
clean:
	sudo rm -rf build dist manifest.out
