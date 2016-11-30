# Copyright (C) 2011-2014, 2016 Swift Navigation Inc.
# Contact: Gareth McMullin <gareth@swift-nav.com>
#          Pasi Miettinen  <pasi.miettinen@exafore.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

import sys
import traceback
import os

from traitsui.api import TextEditor
from piksi_tools.utils import sopen
from sbp.navigation import *

L1CA = 'L1CA'
L2CM = 'L2CM'
L1P = 'L1P'
L2P = 'L2P'
CODE_NOT_AVAILABLE = 'N/A'
EMPTY_STR = '---'

FIXED_MODE  = 4
FLOAT_MODE  = 3
DGNSS_MODE  = 2
SPP_MODE    = 1
NO_FIX_MODE = 0

mode_dict = {
 NO_FIX_MODE: 'No Fix',
 SPP_MODE:    'SPP',
 DGNSS_MODE:  'DGPS',
 FLOAT_MODE:  'Float RTK',
 FIXED_MODE:  'Fixed RTK'}

color_dict = {
 NO_FIX_MODE: None,
 SPP_MODE: (0, 0, 1.0),
 DGNSS_MODE: (0, 0.7, 1.0),
 FLOAT_MODE: (0.75, 0, 0.75),
 FIXED_MODE: 'orange'}


def code_to_str(code):
  if code == 0:
    return L1CA
  elif code == 1:
    return L2CM
  elif code == 5:
    return L1P
  elif code == 6:
    return L2P
  else:
    return CODE_NOT_AVAILABLE


def code_is_gps(code):
  if code == 0:
    return True
  elif code == 1:
    return True
  elif code == 5:
    return True
  elif code == 6:
    return True
  else:
    return False


def get_mode(msg):
  mode = msg.flags & 0x7
  if msg.msg_type == SBP_MSG_BASELINE_NED_DEP_A:
    if mode == 1:
      mode = 4
    else:
      mode = 3
  elif msg.msg_type == SBP_MSG_POS_LLH_DEP_A:
    if mode == 0:
      mode = 1
    elif mode == 1:
      mode = 4
    elif mode == 2:
      mode = 3
  elif msg.msg_type not in [SBP_MSG_BASELINE_NED_DEP_A, SBP_MSG_POS_LLH_DEP_A, 
                            SBP_MSG_POS_LLH, SBP_MSG_BASELINE_NED] :
    print "called get_mode with unsupported message type: {0}".format(msg.msg_type)
  return mode

class MultilineTextEditor(TextEditor):
  """
  Override of TextEditor Class for a multi-line read only
  """

  def init(self, parent):
    parent.read_only = True
    parent.multi_line = True


def plot_square_axes(plot, xnames, ynames):
  try:
    if type(xnames) is str:
      xs = plot.data.get_data(xnames)
      ys = plot.data.get_data(ynames)
      minx = min(xs)
      maxx = max(xs)
      miny = min(ys)
      maxy = max(ys)
    else:
      minx = min(min(plot.data.get_data(xname)) for xname in xnames)
      maxx = max(max(plot.data.get_data(xname)) for xname in xnames)
      miny = min(min(plot.data.get_data(yname)) for yname in ynames)
      maxy = max(max(plot.data.get_data(yname)) for yname in ynames)
    rangex = maxx - minx
    rangey = maxy - miny
    try:
      aspect = float(plot.width) / plot.height
    except:
      aspect = 1
    if aspect * rangey > rangex:
      padding = (aspect * rangey - rangex) / 2
      plot.index_range.low_setting = minx - padding
      plot.index_range.high_setting = maxx + padding
      plot.value_range.low_setting = miny
      plot.value_range.high_setting = maxy
    else:
      padding = (rangex / aspect - rangey) / 2
      plot.index_range.low_setting = minx
      plot.index_range.high_setting = maxx
      plot.value_range.low_setting = miny - padding
      plot.value_range.high_setting = maxy + padding
  except:
    sys.__stderr__.write(traceback.format_exc() + '\n')


def determine_path():
    """Borrowed from wxglade.py"""
    try:
        root = __file__
        if os.path.islink(root):
          root = os.path.realpath(root)
        return os.path.dirname(os.path.abspath(root))
    except:
        print "There is no __file__ variable. Please contact the author."
