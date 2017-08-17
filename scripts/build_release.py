#!/usr/bin/env python

import os
import shutil
import subprocess
import sys
from subprocess import check_call, check_output


def maybe_remove(path):
    if os.path.exists(path):
        shutil.rmtree(str(path))


def build(env='pyinstaller'):
    check_call(['tox', '-e', env])
    out_pyi = os.path.join('dist', 'console')

    exe = os.path.join(out_pyi, 'console')

    # https://bugs.python.org/issue18920
    v = "unknown"
    try:
      v = check_output([str(exe), '-V'], stderr=subprocess.STDOUT)
      v = v.strip().split()[-1]
    except CalledProcessError as cpe:
      print("Output:\n" + cpe.output)
      print("Return Code:\n" + cpe.returncode)

    return out_pyi, v


def build_linux():
    import tarfile
    out_pyi, version = build()
    out = os.path.join('dist', 'swift_console_v{}_linux'.format(version))
    maybe_remove(out)
    shutil.move(out_pyi, out)

    print('Creating tar archive')
    with tarfile.open(out + '.tar.gz', 'w:gz') as tar:
        tar.add(out, arcname=os.path.basename(out))


def build_macos():
    out, version = build('pyinstaller-macos')
    check_call([
        'sudo',
        os.path.join('misc',
                     'create-dmg-installer.sh'),
        'swift_console_v{}_osx.dmg'.format(version)
    ])


def build_win():
    out, version = build()
    
    # hack since PySide's qsvg4.dll does not seem to work on win7
    shutil.copy(
        os.path.join('misc', 'hacks', 'qsvg4.dll'),
        os.path.join(out, 'qt4_plugins', 'imageformats')
    )

    nsis = 'C:\\Program Files (x86)\\NSIS\\makensis.exe'

    check_call([
        nsis,
        '-XOutfile ../dist/swift_console_v{}_windows.exe'.format(version),
        'misc/swift_console.nsi'
    ])


def main():
    plat = sys.platform
    if plat.startswith('linux'):
        build_linux()
    elif plat.startswith('darwin'):
        build_macos()
    elif plat.startswith('win'):
        build_win()


if __name__ == '__main__':
    main()
