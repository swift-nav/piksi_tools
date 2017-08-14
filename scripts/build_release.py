#!/usr/bin/env python

import os
import shutil
import subprocess
import sys
from subprocess import check_call, check_output


def maybe_remove(path):
    if os.path.exists(path):
        shutil.rmtree(str(path))


def build(extra_env=None):
    if extra_env is not None:
        extra_env = os.environ.copy().update(extra_env)
    check_call(['tox', '-e', 'pyinstaller'], env=extra_env)
    out_pyi = os.path.join('dist', 'console')

    exe = os.path.join(out_pyi, 'console')

    # https://bugs.python.org/issue18920
    v = check_output([str(exe), '-V'], stderr=subprocess.STDOUT)
    v = v.strip().split()[-1]

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
    out, version = build(extra_env={'PYSIDE_VERSION': '1.2.2'})
    check_call([
        'sudo',
        os.path.join('piksi_tools', 'console', 'pyinstaller',
                     'create_dmg_installer.sh'),
        'swift_console_v{}_osx.dmg'.format(version)
    ])


def build_win():
    out, version = build()
    check_call([
        'makensis.exe',
        '-XOutfile',
        'swift_console_v{}_windows.exe'.format(version),
        'piksi_tools/console/pyinstaller/win_installer.nsi'
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
