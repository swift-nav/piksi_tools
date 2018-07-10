hiddenimports = ['sip', "PyQt4._qt"]

import os
import PyQt4.QtCore

def qt4_plugins_dir():
     return os.path.join(os.path.dirname(PyQt4.QtCore.__file__), "plugins")

pdir = qt4_plugins_dir()

if is_win:
    datas = [
         (pdir + "/imageformats/*.dll",     "plugins/imageformats"),
         ]
