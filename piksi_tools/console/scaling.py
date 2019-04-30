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
from traits.etsconfig.api import ETSConfig
from pyface.qt import QtGui

if '--scale' in sys.argv:
    ETSConfig._kiva_backend = 'qpainter'


def scaled_size(default_size):
    '''Scale a pixel size based on monitor's DPI.

       Primarily meant for Windows. If the DPI is 96, no scaling is done.'''
    if '--scale' in sys.argv:
        # this is before actual argument parsing
        primary_screen = QtGui.QApplication.primaryScreen()
        dpi = primary_screen.logicalDotsPerInch()
        size_after_scaling = int(default_size * dpi / 96.0)
        return size_after_scaling
    else:
        return default_size
