# Copyright (C) 2019 Swift Navigation Inc.
# Contact: engineering@swiftnav.com
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

import sys
import subprocess
import pyface.qt

# A hack to use Windows legacy scaling mode when started on a high dpi screen
# using Qt5. Otherwise the layout would change somewhat, and plot legend fonts
# would become too small. The downside can be some blurriness due to scaling.
# See https://doc.qt.io/qt-5/highdpi.html
#
# Ideally would become unnecessary one day when all components, plots included,
# would properly work in a high dpi environment.

if '--print-dpi' in sys.argv:
    from PyQt5 import QtWidgets

    app = QtWidgets.QApplication([])
    dpi_list = [screen.logicalDotsPerInch() for screen in app.screens()]
    max_dpi = max(dpi_list)

    print(max_dpi, end="")
    sys.exit(0)

if sys.platform == "win32" and pyface.qt.qt_api.lower() in ['pyqt5', 'pyside2']:
    prog_str = b"""\
from PyQt5 import QtWidgets

app = QtWidgets.QApplication([])
dpi_list = [screen.logicalDotsPerInch() for screen in app.screens()]
max_dpi = max(dpi_list)

print(max_dpi, end="")
"""
    # initializing the application to use this Windows scaling mechanism is
    # only possible before initializing the QApplication for the first time,
    # so the dpi query, which also uses Qt, is done in a separate process
    helper_proc = subprocess.Popen([sys.executable, "-u", "-", '--print-dpi'],
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
    output, _ = helper_proc.communicate(input=prog_str)
    dpi = float(output)
    high_dpi = (dpi > 96.0)  # 96 is the standard windows logical dpi nowadays
    if high_dpi:
        sys.argv.extend(["-platform", "windows:dpiawareness=0"])
