piksi_tools Development Procedures
==================================

This document summarizes some practices around contributions to Piksi
tools. This repository includes the console, bootloader, and a
smattering of other tools. Of these, we typically do binary releases
of the console. These instructions don't come with a warranty yet, so
please feel free to update it to mirror reality.

# Build, Test, and Release New Versions of the Console

We build and distribute binary releases of the console for OS X and
Windows. pyinstaller does not cross-compile binaries, so you'll have
to build the binary on the target system. There is no bootstrapping
script for windows installation of the tools and its dependencies.
You will need to install NSIS for creating the setup executable,
Cygwin for bash shell scripting ablility, and the Python(X,Y)
distribution with the ETS and PySerial Module extras for Python and
console dependencies.

If needed, tag a release version of the console:

```shell
# Example tag: v0.26

git tag -a <release-tag-name> -m "<helpful annotation message>"
git push upstream <release-tag-name> --tags

```

Use conda, venv or virtualenv to development the console with Python 3.5+, that is:
- ```
  conda create -n piksi_tools python=3.7
  conda activate piksi_tools
  ```
- ```
  python3.7 -m venv .venv/piksi_tools
  source .venv/piksi_tools/bin/activate
  ```
- ```
  virtualenv -p `which python3.7` .venv/piksi_tools
  source .venv/piksi_tools/bin/activate
  ```

The steps to run GUI from source are roughly:

```shell
# Check out the repository and the current release tag
git clone https://github.com/swift-nav/piksi_tools.git
git checkout <release-tag-name> # optional

# Activate isolated Python environment
conda activate piksi_tools <or> source .venv/piksi_tools/bin/activate

# Install the dependencies
make deps
pip install -r requirements.txt
pip install -r requirements_dev.txt
pip install pyinstaller==3.4            # get currently used version from tox.ini
pip install pyqt5==5.10.0               # again, currently used version is in tox.ini
pip install -r requirements_gui.txt
pip install -e .

# To run the console
python -m piksi_tools.console
```

To build the console after getting setup to run it from source, roughly:
```shell
# Run the console to re-generate the RELEASE-VERSION file
PYTHONPATH=. piksi_tools/console/console.py

# Build the console binary and installer
make build_console
```

The console installer (`.dmg` or `.exe`) should now be in `dist/`.

To test the console installer, install it from the generated installer
and test in OSX and Windows:

OSX:
- Do all the tabs appear to be working properly?
- Can you update a Piksi with the new console which has the previously
  released STM Firmware / NAP HDL on it?

Windows:
- Do all the tabs appear to be working properly?
- Can you update a Piksi with the new console which has the previously
  released STM Firmware / NAP HDL on it?
- Test on the following versions of (32-bit and 64-bit) Windows
  (Windows XP, Windows 7,Windows 8, Windows 10).

Linux (no generated binary):
- Test the install of and function of the console on a fresh linux VM
  snapshot.

Upload the console binaries from `dist/` to the
[AWS S3 bucket](http://downloads.swiftnav.com/swift_console/) and
update the console version number in the `index.json` there.

# Custom libsbp version

To use a custom libsbp from Git without publishing to PyPI add to following to `requirements.txt`:

```
git+https://github.com/swift-nav/libsbp.git@<COMMIT_HASH>#subdirectory=python&egg=sbp
```

Where `<COMMIT_HASH>` is the tip of Git branch you want to use.  Alternately, a local checkout can be installed via:

```
pip install -e file://$PWD/libsbp#subdirectory=python&egg=sbp
```

# Contributions

This library is developed internally by Swift Navigation. We welcome
Github issues and pull requests, as well as discussions of potential
problems and enhancement suggestions on the
[forum](https://groups.google.com/forum/#!forum/swiftnav-discuss).
