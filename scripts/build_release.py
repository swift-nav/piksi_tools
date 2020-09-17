#!/usr/bin/env python

import glob
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile

from subprocess import check_call, check_output, CalledProcessError

from six.moves import reload_module

BIONIC_DOCKER_TAG = 'swiftnav/piksi-tools-bionic:2019.06.20'
S3_BUCKET = 'swiftnav-artifacts'

appveyor_pr = os.environ.get("APPVEYOR_PULL_REQUEST_NUMBER", "")
travis_pr = os.environ.get("TRAVIS_PULL_REQUEST", "false")

if (appveyor_pr != "" or travis_pr != "false"):
    S3_BUCKET = 'swiftnav-artifacts-pull-requests'

print("S3_BUCKET: {} (APPVEYOR_PULL_REQUEST_NUMBER: {}, TRAVIS_PULL_REQUEST: {})".format(S3_BUCKET, appveyor_pr, travis_pr))


def maybe_remove(path):
    if os.path.exists(path):
        shutil.rmtree(str(path))


def _check_output(cmd, default=None):
    try:
        v = check_output(cmd, stderr=subprocess.STDOUT)
        return v.strip().split()[-1]
    except CalledProcessError as cpe:
        print("Output:\n" + str(cpe.output))
        print("Return Code:\n" + str(cpe.returncode))
        raise cpe
    return default


def get_version():
    # tox writes _version.py, doing a delayed import and a reload after that
    from piksi_tools import _version
    reload_module(_version)
    return _version.version


def build(env):
    check_call(['tox', '-e', env, '-vv'])
    out_pyi = os.path.join(os.getcwd(), os.path.join('dist', 'console'))
    ver = get_version()
    print("build version:", ver)
    return out_pyi, ver


def build_linux():

    print('>>> Building console for Legacy Linux (Ubuntu 16.04)')

    out_pyi, version = build('pyinstaller-linux')
    out_dist = os.path.join('dist', 'swift_console_{}_linux_legacy'.format(version))
    out = os.path.join(os.getcwd(), out_dist)
    maybe_remove(out)

    print(">>> Moving '{}' to '{}'...".format(out_pyi, out))
    shutil.move(out_pyi, out)

    # prevents missing export error on ubuntu 16.04 with intel graphics
    os.remove(os.path.join(out, 'libdrm.so.2'))

    fname = '{}.tar.gz'.format(out)

    print('>>> Creating tar archive Legacy Linux (Ubuntu 16.04)')
    with tarfile.open(fname, 'w:gz') as tar:
        tar.add(out, arcname=os.path.basename(out))

    print('>>> Listing dist dir:')
    print(os.listdir("dist"))

    s3_fname = "{}.tar.gz".format(os.path.basename(out_dist))
    s3_path = 's3://{}/piksi_tools/{}/linux_legacy/{}'.format(S3_BUCKET, version, s3_fname)

    print(">>> Uploading to {}".format(s3_path))
    check_call(['aws', 's3', 'cp', fname, s3_path])



def build_linux_bionic():

    print('>>> Building console for Linux (Ubuntu 18.04)')

    cwd = os.getcwd()
    check_call(['docker', 'run', '-e', 'AWS_SECRET_ACCESS_KEY', '-e', 'AWS_ACCSS_KEY_ID', '-e', 'AWS_DEFAULT_REGION',
                '-v', cwd + ':/work', '-it', '--rm', BIONIC_DOCKER_TAG,
                'tox', '-e', 'pyinstaller36-linux', '-vv'])

    version = get_version()
    print("build version:", version)

    out_dist = os.path.join('dist', 'swift_console_{}_linux'.format(version))
    out = os.path.join(os.getcwd(), out_dist)
    out_pyi = os.path.join(os.getcwd(), os.path.join('dist', 'console'))

    uid, gid = os.getuid(), os.getgid()
    check_call(['sudo', 'chown', '-R', '{}:{}'.format(uid, gid), out_pyi, 'dist'])

    print(">>> Moving '{}' to '{}'...".format(out_pyi, out))

    maybe_remove(out)
    shutil.move(out_pyi, out)

    fname = '{}.tar.gz'.format(out)

    print('>>> Creating tar archive for Ubuntu Bionic: ' + fname)
    with tarfile.open(fname, 'w:gz') as tar:
        tar.add(out, arcname=os.path.basename(out))

    print('>>> Listing dist dir:')
    print(os.listdir("dist"))

    s3_fname = "{}.tar.gz".format(os.path.basename(out_dist))
    s3_path = 's3://{}/piksi_tools/{}/linux/{}'.format(S3_BUCKET, version, s3_fname)

    print(">>> Uploading to {}".format(s3_path))
    check_call(['aws', 's3', 'cp', fname, s3_path])


def build_macos():
    _out, version = build('pyinstaller-macos')
    fname = 'swift_console_{}_macos.dmg'.format(version)
    check_call([
        'sudo',
        os.path.join(os.getcwd(), os.path.join('misc', 'create-dmg-installer.sh')),
        fname 
    ])

    dmg_rel_path = "dist/{}".format(fname)

    print(">>> Fix .dmg file owner:group info")
    uid, gid = os.getuid(), os.getgid()
    check_call(['sudo', 'chown', '{}:{}'.format(uid, gid), dmg_rel_path])

    print(">>> Verify AWS CLI tool is in path")
    check_call(['command', '-v', 'aws'])

    s3_path = 's3://{}/piksi_tools/{}/darwin/{}'.format(S3_BUCKET, version, fname)

    print(">>> Uploading to {}".format(s3_path))
    check_call(['aws', 's3', 'cp', dmg_rel_path, s3_path])


def build_win():
    out, version = build('pyinstaller-win')

    # workaround for https://github.com/pyinstaller/pyinstaller/issues/1793
    srcs = ['msvcp90.dll', 'msvcr90.dll', 'msvcm90.dll', 'Microsoft.VC90.CRT.manifest']
    dst_dirs = glob.glob(os.path.join(out, 'qt4_plugins', '*/'))
    for dst in dst_dirs:
        for src in srcs:
            shutil.copy(os.path.join(out, src), dst)

    nsis = 'C:\\Program Files (x86)\\NSIS\\makensis.exe'

    fname = 'swift_console_{}_windows.exe'.format(version)
    installer_path = 'dist/{}'.format(fname)

    check_call([
        nsis,
        '-XOutfile ../{}'.format(installer_path),
        'misc/swift_console.nsi'
    ])

    check_call(['where', 'aws'])

    s3_path = 's3://{}/piksi_tools/{}/windows/{}'.format(S3_BUCKET, version, fname)

    print(">>> Uploading to {}".format(s3_path))
    check_call(['aws', 's3', 'cp', installer_path, s3_path])


def zipdir(path, ziph):
    # https://stackoverflow.com/questions/1855095/how-to-create-a-zip-archive-of-a-directory-in-python
    for root, dirs, files in os.walk(path):
        for file in files:
            arcname = os.path.relpath(os.path.join(root, file), os.path.join(path, '..')) 
            ziph.write(os.path.join(root, file), arcname)


def build_cli_tools(plat):
    version = get_version()
    _check_output(['tox', '-e', 'pyinstaller-cmdline_tools'])
    out = os.path.join('dist', 'cmd_line')
    fname = 'cmdline_tools_{}.zip'.format(version)
    if not plat.startswith('win'):
        with zipfile.ZipFile(fname, 'w') as ziph:
            zipdir(out, ziph)
        s3_path = 's3://{}/piksi_tools/{}/{}/{}'.format(S3_BUCKET, version, plat, fname)
        print(">>> Uploading to {}".format(s3_path))
        check_call(['aws', 's3', 'cp', fname, s3_path])


def main():
    plat = sys.platform
    if plat.startswith('linux'):
        build_linux()
        build_linux_bionic()
    elif plat.startswith('darwin'):
        build_macos()
    elif plat.startswith('win'):
        plat = "windows"
        build_win()
    build_cli_tools(plat)


if __name__ == '__main__':
    main()