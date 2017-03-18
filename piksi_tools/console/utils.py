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
import datetime

from piksi_tools.utils import sopen
from sbp.navigation import *
from threading import Event, Thread

L1CA = 'L1CA'
L2CM = 'L2CM'
L1P = 'L1P'
L2P = 'L2P'
CODE_NOT_AVAILABLE = 'N/A'
EMPTY_STR = '--'

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

L1_CODES = [0,2,3]
L2_CODES = [1,4]

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

def determine_path():
    """Borrowed from wxglade.py"""
    try:
        root = __file__
        if os.path.islink(root):
          root = os.path.realpath(root)
        return os.path.dirname(os.path.abspath(root))
    except:
        print "There is no __file__ variable. Please contact the author."

def datetime_2_str(datetm):
  return (datetm.strftime('%Y-%m-%d %H:%M'), datetm.strftime('%S.%f')) 

def log_time_strings(week, tow):
  """Returns two tuples, first is local time, second is gps time
     Each tuple is a string with the date and a string with the 
     precise seconds in the minute which can be cast to a float as 
     needed
  """
  if week is not None and tow > 0:
    t_gps = datetime.datetime(1980, 1, 6) + \
            datetime.timedelta(weeks=week) + \
            datetime.timedelta(seconds=tow)
    (t_gps_date, t_gps_secs) = datetime_2_str(t_gps)
  else:
    t_gps_date = ""
    t_gps_secs =0
  t = datetime.datetime.now()
  (t_local_date, t_local_secs) = datetime_2_str(t)
  return ((t_local_date, t_local_secs), 
          (t_gps_date, t_gps_secs))

def call_repeatedly(interval, func, *args):
    stopped = Event()
    def loop():
        while not stopped.wait(interval): # the first call is in `interval` secs
            func(*args)
    Thread(target=loop).start()    
    return stopped.set
