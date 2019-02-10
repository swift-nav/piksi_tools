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


def _check_output(cmd, default=None):
    try:
        v = check_output(cmd, stderr=subprocess.STDOUT)
        return v.strip().split()[-1]
    except CalledProcessError as cpe:
        print("Output:\n" + cpe.output)
        print("Return Code:\n" + str(cpe.returncode))
        raise CalledProcessError
    return default


def build(env):
    check_call(['tox', '-e', env])
    out_pyi = os.path.join(os.getcwd(), os.path.join('dist', 'console'))
    exe = os.path.join(out_pyi, 'console')
    # https://bugs.python.org/issue18920
    print("Running {} to determine its version.".format(str(exe)))
    v = _check_output([str(exe), '-V'], default="unknown")
    return out_pyi, v


def build_linux():
    import tarfile
    out_pyi, version = build('pyinstaller-linux')
    out = os.path.join(os.getcwd(), os.path.join('dist', 'swift_console_v{}_linux'.format(version)))
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
        'swift_console_v{}_macos.dmg'.format(version)
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
        '-XOutfile ../dist/swift_console_v{}_windows.exe'.format(version),
        'misc/swift_console.nsi'
    ])


def build_cli_tools_nix():
    _check_output(['tox', '-e', 'pyinstaller_cmdline_tools-nix'])


def build_cli_tools_win():
    _check_output(['tox', '-e', 'pyinstaller_cmdline_tools-win'])


def main():
    plat = sys.platform
    if plat.startswith('linux'):
        build_linux()
        build_cli_tools_nix()
    elif plat.startswith('darwin'):
        build_macos()
        build_cli_tools_nix()
    elif plat.startswith('win'):
        build_win()
        build_cli_tools_win()


if __name__ == '__main__':
    main()
