# -*- mode: python -*-

block_cipher = None


from PyInstaller.compat import is_linux, is_darwin, is_win
from PyInstaller.depend.bindepend import findLibrary
from PyInstaller.utils.hooks import collect_data_files

# collect the package_data of piksi_tools.
# This allows us to use pack
datas = collect_data_files('piksi_tools')

resources = [
  ('README.txt', 'piksi_tools/console/README.txt', 'DATA'),
  ('configure_udev_rules.sh', 'tasks/configure_udev_rules.sh', 'DATA'),
]

if is_win:
  icon = 'misc/icons/swift_console.ico'
elif is_darwin:
  icon = 'misc/icons/swift_console.icns'
else:
  icon = None

if is_win:
  binaries = [('../lib/libsettings/libsettings.pyd', '.')]
else:
  binaries = [('../piksi_tools/lib/libsettings/libsettings.so', '.')]

# hack to prevent segfault on ubuntu 16.04
if is_linux:
  libs = ['libgtk-x11-2.0.so.0', 'libgio-2.0.so.0', 'libatk-1.0.so.0']
  binaries += [(findLibrary(l), '.') for l in libs]


a = Analysis(['../piksi_tools/console/console.py'],
             binaries=binaries,
             datas=datas,
             hiddenimports=[],
             hookspath=['misc/pyi-hooks'],
             runtime_hooks=['misc/pyi-hooks/runtime-hook.py'],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='console',
          icon=icon,
          debug=False,
          strip=False,
          upx=True,
          console=False )
coll = COLLECT(exe,
               resources,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='console')

if is_darwin:
  app = BUNDLE(coll,
               name='Swift Console.app',
               icon=icon)
