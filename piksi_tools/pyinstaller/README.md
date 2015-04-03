Piksi Tools pyinstaller
===========
The pyinstaller directory allows a user to use pyinstaller to package the console for different platforms

Hints
==========
 * The console.spec file contains all the information pyinstaller needs to install the console.
 * All commands to create the installer should be run from within the pyinstaller directory.
 * If you run the pyinstaller scrip with different argurments it might overwrite console.spec

Procedure
==========
You can use the Makefile to perform these steps, or use the following procedure:

1. Run pyinstaller with the following arguments:

    sudo pyinstaller --clean --log-level=DEBUG --paths=../ --debug -w console.spec -y

2. Package the console

 **Macosx:** Run the following command

    ./create-dmg-installer.sh

 Note, if run from the pyinstaller directory you don't need any arguments to this little script

 **Windows:** Use Nsis

 **Linux** TBD
