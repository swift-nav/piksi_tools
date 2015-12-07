piksi_tools Development Procedures
==================================

This document summarizes some practices around contributions to Piksi
tools. This repository includes the Piksi console, bootloader, and a
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

The steps to build the console are roughly:

```shell
# Check out the repository and the current release tag
git clone https://github.com/swift-nav/piksi_tools.git
git checkout <release-tag-name>

# Install the dependencies
make deps

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
[AWS S3 bucket](http://downloads.swiftnav.com/piksi_console/) and
update the console version number in the `index.json` there.

# Contributions

This library is developed internally by Swift Navigation. We welcome
Github issues and pull requests, as well as discussions of potential
problems and enhancement suggestions on the
[forum](https://groups.google.com/forum/#!forum/swiftnav-discuss).
