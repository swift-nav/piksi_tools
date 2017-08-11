# -*- mode: python -*-

# Settings for PyInstaller

from PyInstaller import is_linux
from PyInstaller.depend.bindepend import findLibrary

# hack to prevent segfault on ubuntu 16.04
binaries = []
if is_linux:
  lol = ['libgtk-x11-2.0.so.0', 'libgio-2.0.so.0', 'libatk-1.0.so.0']
  binaries += [(findLibrary(x), '.') for x in lol]

a = Analysis(['../console.py'],
             hiddenimports = [
              'PySide.QtOpenGL',
              'pyface.ui.qt4.init',
              'pyface.ui.qt4.action.menu_manager',
              'pyface.ui.qt4.action.menu_bar_manager',
              'pyface.ui.qt4.action.status_bar_manager',
              'pyface.ui.qt4.action.tool_bar_manager',
              'pyface.ui.qt4.resource_manager',
              'pyface.ui.qt4.clipboard',
              'pyface.ui.qt4.gui',
              'pyface.ui.qt4.image_resource',
              'pyface.ui.qt4.window',
              'pyface.ui.qt4.dialog',
              'pyface.ui.qt4.file_dialog',
              'pyface.ui.qt4.progress_dialog',
              'pyface.ui.qt4.python_shell',
              'pyface.i_gui',
              'pyface.i_clipboard',
              'pyface.i_progress_dialog',
              'pyface.i_image_resource',
              'pyface.i_file_dialog',
              'pyface.i_dialog',
              'pyface.i_window',
              'pyface.i_python_shell',
              'pyface.qt.QtOpenGL',
              'enable.qt4.image',
              'enable.qt4.base_window',
              'enable.qt4.constants',
              'enable.toolkit_constants',
              'enable.qt4.scrollbar',
              'enable.savage.trait_defs.ui.qt4',
              'enable.savage.trait_defs.ui.qt4.svg_button_editor',
              'pyface.ui.qt4.python_editor',
              'pyface.i_python_editor',
             ],
             binaries = binaries,
             hookspath=None,
             runtime_hooks=[])

resources = [
  ('settings.yaml', '../settings.yaml', 'DATA'),
  ('README.txt', '../README.txt', 'DATA'),
  ('cacert.pem', '../cacert.pem', 'DATA'),
  ('piksi_tools/console/cacert.pem', '../cacert.pem', 'DATA'),
  ('configure_udev_rules.sh', '../../../tasks/configure_udev_rules.sh', 'DATA'),
]
resources += Tree('../images', prefix='piksi_tools/console/images')

import sys, os

kwargs = {}
exe_ext = ''
if os.name == 'nt':
  kwargs['icon'] = 'icon.ico'
  exe_ext = '.exe'
elif sys.platform.startswith('darwin'):
  kwargs['icon'] = 'icon.icns'

pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='console'+exe_ext,
          debug=False,
          strip=None,
          upx=True,
          console=False,
          **kwargs
          )
coll = COLLECT(exe,
               resources,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=None,
               upx=True,
               name='console')

if sys.platform.startswith('darwin'):
  app = BUNDLE(coll,
               name='Swift Console.app',
               icon='icon.icns')
