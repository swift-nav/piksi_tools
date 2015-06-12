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


console: $(spec_file)
	make clean
	pyinstaller --clean --log-level=DEBUG --paths=$(piksi_tools_directory) --debug $(PLAT_ARGS) $(spec_file) -y >& Make.out
	echo "Pyinstaller completed. View output in Make.out"
	make $(UNAME)

Windows:
	makensis win_installer.nsi 
Cygwin:
	makensis win_installer.nsi

Darwin:
	sudo ./create-dmg-installer.sh
clean:
	rm -rf build dist manifest.out


