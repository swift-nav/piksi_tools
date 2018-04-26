from __future__ import print_function

import datetime
import pkg_resources
import time
import os
import gc

from functools import partial
import threading
from threading import Event, Thread

from pyface.image_resource import ImageResource
from sbp.navigation import (SBP_MSG_BASELINE_NED, SBP_MSG_BASELINE_NED_DEP_A,
                            SBP_MSG_POS_LLH, SBP_MSG_POS_LLH_DEP_A)

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

CODE_GPS_L1CA = 0
CODE_GPS_L2CM = 1
CODE_GPS_L2CL = 7
CODE_GPS_L2CX = 8
CODE_GPS_L1P = 5
CODE_GPS_L2P = 6
CODE_GPS_L5I = 9
CODE_GPS_L5Q = 10
CODE_GPS_L5X = 11

CODE_GLO_L1OF = 3
CODE_GLO_L2OF = 4

CODE_SBAS_L1CA = 2

CODE_BDS2_B11 = 12
CODE_BDS2_B2 = 13

CODE_GAL_E1B = 14
CODE_GAL_E1C = 15
CODE_GAL_E1X = 16
CODE_GAL_E6B = 17
CODE_GAL_E6C = 18
CODE_GAL_E6X = 19
CODE_GAL_E7I = 20
CODE_GAL_E7Q = 21
CODE_GAL_E7X = 22
CODE_GAL_E8 = 23
CODE_GAL_E5I = 24
CODE_GAL_E5Q = 25
CODE_GAL_E5X = 26

CODE_QZS_L1CA = 27
CODE_QZS_L2CM = 28
CODE_QZS_L2CL = 29
CODE_QZS_L2CX = 30
CODE_QZS_L5I = 31
CODE_QZS_L5Q = 32
CODE_QZS_L5X = 33

SUPPORTED_CODES = [CODE_GPS_L1CA,
                   CODE_GPS_L2CM,
                   CODE_GPS_L1P,
                   CODE_GPS_L2P,
                   CODE_GLO_L1OF,
                   CODE_GLO_L2OF,
                   CODE_SBAS_L1CA,
                   CODE_BDS2_B11,
                   CODE_BDS2_B2,
                   CODE_GPS_L5Q,
                   CODE_QZS_L1CA,
                   CODE_QZS_L2CM]

L1CA_STR = 'GPS L1CA'
L2CM_STR = 'GPS L2C'
L2CX_STR = 'GPS L2C'
L5Q_STR = 'GPS L5'
L1P_STR = 'GPS L1P'
L2P_STR = 'GPS L2P'
SBAS_STR = 'SBAS L1'
L1OF_STR = 'GLO L1OF'
L2OF_STR = 'GLO L2OF'
BDS_B1_STR = 'BDS B1'
BDS_B2_STR = 'BDS B2'
QZS_L1CA_STR = 'QZSS L1CA'
QZS_L2CM_STR = 'QZSS L2CM'
QZS_L2CX_STR = 'QZSS L2C'

CODE_TO_STR_MAP = {
    CODE_GPS_L1CA: L1CA_STR,
    CODE_GPS_L2CM: L2CM_STR,
    CODE_GPS_L2CX: L2CX_STR,
    CODE_GPS_L5Q: L5Q_STR,
    CODE_GPS_L1P: L1P_STR,
    CODE_GPS_L2P: L2P_STR,
    CODE_SBAS_L1CA: SBAS_STR,
    CODE_GLO_L1OF: L1OF_STR,
    CODE_GLO_L2OF: L2OF_STR,
    CODE_BDS2_B11: BDS_B1_STR,
    CODE_BDS2_B2: BDS_B2_STR,
    CODE_QZS_L1CA: QZS_L1CA_STR,
    CODE_QZS_L2CM: QZS_L2CM_STR,
    CODE_QZS_L2CX: QZS_L2CX_STR
}

STR_TO_CODE_MAP = {
    L1CA_STR: CODE_GPS_L1CA,
    L2CM_STR: CODE_GPS_L2CM,
    L2CX_STR: CODE_GPS_L2CX,
    L5Q_STR: CODE_GPS_L5Q,
    L1P_STR: CODE_GPS_L1P,
    L2P_STR: CODE_GPS_L2P,
    SBAS_STR: CODE_SBAS_L1CA,
    L1OF_STR: CODE_GLO_L1OF,
    L2OF_STR: CODE_GLO_L2OF,
    BDS_B1_STR: CODE_BDS2_B11,
    BDS_B2_STR: CODE_BDS2_B2,
    QZS_L1CA_STR: CODE_QZS_L1CA,
    QZS_L2CM_STR: CODE_QZS_L2CM,
    QZS_L2CX_STR: CODE_QZS_L2CX
}

CODE_NOT_AVAILABLE = 'N/A'
EMPTY_STR = '--'

SBAS_MODE = 6
DR_MODE = 5
FIXED_MODE = 4
FLOAT_MODE = 3
DGNSS_MODE = 2
SPP_MODE = 1
NO_FIX_MODE = 0

mode_dict = {
    NO_FIX_MODE: 'No Fix',
    SPP_MODE: 'SPP',
    DGNSS_MODE: 'DGPS',
    FLOAT_MODE: 'Float RTK',
    FIXED_MODE: 'Fixed RTK',
    DR_MODE: 'Dead Reckoning',
    SBAS_MODE: 'SBAS'
}

color_dict = {
    NO_FIX_MODE: None,
    SPP_MODE: (0, 0, 1.0),
    DGNSS_MODE: (0, 0.7, 1.0),
    FLOAT_MODE: (0.75, 0, 0.75),
    FIXED_MODE: 'orange',
    DR_MODE: 'black',
    SBAS_MODE: 'green'
}


def code_to_str(code):
    if code in CODE_TO_STR_MAP:
        return CODE_TO_STR_MAP[code]
    else:
        return CODE_NOT_AVAILABLE


gps_codes = {CODE_GPS_L1CA,
             CODE_GPS_L2CM,
             CODE_GPS_L2CL,
             CODE_GPS_L2CX,
             CODE_GPS_L1P,
             CODE_GPS_L2P,
             CODE_GPS_L5I,
             CODE_GPS_L5Q,
             CODE_GPS_L5X}


def code_is_gps(code):
    return code in gps_codes


glo_codes = {CODE_GLO_L1OF,
             CODE_GLO_L2OF}


def code_is_glo(code):
    return code in glo_codes


sbas_codes = {CODE_SBAS_L1CA}


def code_is_sbas(code):
    return code in sbas_codes


bds2_codes = {CODE_BDS2_B11,
              CODE_BDS2_B2}


def code_is_bds2(code):
    return code in bds2_codes


qzss_codes = {CODE_QZS_L1CA,
              CODE_QZS_L2CM,
              CODE_QZS_L2CL,
              CODE_QZS_L2CX,
              CODE_QZS_L5I,
              CODE_QZS_L5Q,
              CODE_QZS_L5X
              }


def code_is_qzss(code):
    return code in qzss_codes


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
    elif msg.msg_type not in [
        SBP_MSG_BASELINE_NED_DEP_A, SBP_MSG_POS_LLH_DEP_A, SBP_MSG_POS_LLH,
        SBP_MSG_BASELINE_NED
    ]:
        print("called get_mode with unsupported message type: {0}".format(
            msg.msg_type))
    return mode


def datetime_2_str(datetm):
    return (datetm.strftime('%Y-%m-%d %H:%M'), datetm.strftime('%S.%f'))


# Modified based on https://stackoverflow.com/a/1094933
def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return "{:3.1f}{}{}".format(num, unit, suffix)
        num /= 1024.0
    return "{:.1f}{}{}".format(num, 'Y', suffix)


def log_time_strings(week, tow):
    """Returns two tuples, first is local time, second is gps time
       Each tuple is a string with the date and a string with the
       precise seconds in the minute which can be cast to a float as
       needed
    """
    if week is not None and tow > 0:
        t_gps = (datetime.datetime(1980, 1, 6) +
                 datetime.timedelta(weeks=week) +
                 datetime.timedelta(seconds=tow))
        (t_gps_date, t_gps_secs) = datetime_2_str(t_gps)
    else:
        t_gps_date = ""
        t_gps_secs = 0
    t = datetime.datetime.now()
    (t_local_date, t_local_secs) = datetime_2_str(t)
    return ((t_local_date, t_local_secs), (t_gps_date, t_gps_secs))


def call_repeatedly(interval, func, *args):
    stopped = Event()

    def loop():
        # https://stackoverflow.com/questions/29082268/python-time-sleep-vs-event-wait
        while not stopped.is_set():
            func(*args)
            time.sleep(interval)

    thread = Thread(target=loop)
    thread.daemon = True
    thread.start()

    return stopped.set


GARBAGE_COLLECT_INTERVAL_SEC = 60


def start_gc_collect_thread():
    def loop():
        while True:
            time.sleep(GARBAGE_COLLECT_INTERVAL_SEC)
            gc.collect()
    thread = Thread(target=loop)
    thread.daemon = True
    thread.start()


resource_filename = partial(pkg_resources.resource_filename, 'piksi_tools')
resource_stream = partial(pkg_resources.resource_stream, 'piksi_tools')
icon = ImageResource(resource_filename('console/images/icon.png'))

swift_path = os.path.normpath(os.path.join(os.path.expanduser("~"), 'SwiftNav'))
