#!/usr/bin/env python

import glob
import os
import shutil
import subprocess
import sys
from subprocess import check_call, check_output, CalledProcessError


def maybe_remove(path):
    if os.path.exists(path):
        shutil.rmtree(str(path))

def build(env):
    from six.moves import reload_module
    check_call(['tox', '-e', env])
    out_pyi = os.path.join(os.getcwd(), os.path.join('dist', 'console'))
    # tox writes _version.py, doing a delayed import and a reload after that
    from piksi_tools import _version
    reload_module(_version)
    ver = _version.version
    print("build version:", ver)
    return out_pyi, ver


def build_linux():
    import tarfile
    out_pyi, version = build('pyinstaller-linux')
    out = os.path.join(os.getcwd(), os.path.join('dist', 'swift_console_{}_linux'.format(version)))
    maybe_remove(out)
    shutil.move(out_pyi, out)

    # prevents missing export error on ubuntu 16.04 with intel graphics
    os.remove(os.path.join(out, 'libdrm.so.2'))

    print('Creating tar archive')
    with tarfile.open(out + '.tar.gz', 'w:gz') as tar:
        tar.add(out, arcname=os.path.basename(out))


def build_macos():
    out, version = build('pyinstaller-macos')
    check_call([
        'sudo',
        os.path.join(os.getcwd(), os.path.join('misc',
                     'create-dmg-installer.sh')),
        'swift_console_{}_macos.dmg'.format(version)
    ])


def build_win():
    out, version = build('pyinstaller-win')

    # workaround for https://github.com/pyinstaller/pyinstaller/issues/1793
    srcs = ['msvcp90.dll', 'msvcr90.dll', 'msvcm90.dll', 'Microsoft.VC90.CRT.manifest']
    dst_dirs = glob.glob(os.path.join(out, 'qt4_plugins', '*/'))
    for dst in dst_dirs:
        for src in srcs:
            shutil.copy(os.path.join(out, src), dst)

    nsis = 'C:\\Program Files (x86)\\NSIS\\makensis.exe'

    check_call([
        nsis,
        '-XOutfile ../dist/swift_console_{}_windows.exe'.format(version),
        'misc/swift_console.nsi'
    ])


def build_cli_tools():
    check_call(['tox', '-e', 'pyinstaller-cmdline_tools'])


def main():
    plat = sys.platform
    if plat.startswith('linux'):
        build_linux()
    elif plat.startswith('darwin'):
        build_macos()
    elif plat.startswith('win'):
        build_win()
    build_cli_tools()


if __name__ == '__main__':
    main()
