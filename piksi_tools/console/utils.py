from __future__ import print_function

import datetime
import pkg_resources
import time
import os

from functools import partial
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
CODE_GPS_L1CI = 56
CODE_GPS_L1CQ = 57
CODE_GPS_L1CX = 58
CODE_AUX_GPS = 59

CODE_GLO_L1OF = 3
CODE_GLO_L2OF = 4
CODE_GLO_L1P = 29
CODE_GLO_L2P = 30

CODE_SBAS_L1CA = 2
CODE_SBAS_L5I = 41
CODE_SBAS_L5Q = 42
CODE_SBAS_L5X = 43
CODE_AUX_SBAS = 60

CODE_BDS2_B1 = 12
CODE_BDS2_B2 = 13
CODE_BDS3_B1CI = 44
CODE_BDS3_B1CQ = 45
CODE_BDS3_B1CX = 46
CODE_BDS3_B5I = 47
CODE_BDS3_B5Q = 48
CODE_BDS3_B5X = 49
CODE_BDS3_B7I = 50
CODE_BDS3_B7Q = 51
CODE_BDS3_B7X = 52
CODE_BDS3_B3I = 53
CODE_BDS3_B3Q = 54
CODE_BDS3_B3X = 55

CODE_GAL_E1B = 14
CODE_GAL_E1C = 15
CODE_GAL_E1X = 16
CODE_GAL_E6B = 17
CODE_GAL_E6C = 18
CODE_GAL_E6X = 19
CODE_GAL_E7I = 20
CODE_GAL_E7Q = 21
CODE_GAL_E7X = 22
CODE_GAL_E8I = 23
CODE_GAL_E8Q = 24
CODE_GAL_E8X = 25
CODE_GAL_E5I = 26
CODE_GAL_E5Q = 27
CODE_GAL_E5X = 28
CODE_AUX_GAL = 61

CODE_QZS_L1CA = 31
CODE_QZS_L1CI = 32
CODE_QZS_L1CQ = 33
CODE_QZS_L1CX = 34
CODE_QZS_L2CM = 35
CODE_QZS_L2CL = 36
CODE_QZS_L2CX = 37
CODE_QZS_L5I = 38
CODE_QZS_L5Q = 39
CODE_QZS_L5X = 40
CODE_AUX_QZS = 62

SUPPORTED_CODES = [
    CODE_GPS_L1CA,
    CODE_GPS_L2CM,
    CODE_GPS_L2CL,
    CODE_GPS_L2CX,
    CODE_GPS_L1P,
    CODE_GPS_L2P,
    CODE_GPS_L5I,
    CODE_GPS_L5Q,
    CODE_GPS_L5X,
    CODE_GPS_L1CI,
    CODE_GPS_L1CQ,
    CODE_GPS_L1CX,
    CODE_AUX_GPS,

    CODE_GLO_L1OF,
    CODE_GLO_L2OF,
    CODE_GLO_L1P,
    CODE_GLO_L2P,

    CODE_SBAS_L1CA,
    CODE_SBAS_L5I,
    CODE_SBAS_L5Q,
    CODE_SBAS_L5X,
    CODE_AUX_SBAS,

    CODE_BDS2_B1,
    CODE_BDS2_B2,
    CODE_BDS3_B1CI,
    CODE_BDS3_B1CQ,
    CODE_BDS3_B1CX,
    CODE_BDS3_B5I,
    CODE_BDS3_B5Q,
    CODE_BDS3_B5X,
    CODE_BDS3_B7I,
    CODE_BDS3_B7Q,
    CODE_BDS3_B7X,
    CODE_BDS3_B3I,
    CODE_BDS3_B3Q,
    CODE_BDS3_B3X,

    CODE_GAL_E1B,
    CODE_GAL_E1C,
    CODE_GAL_E1X,
    CODE_GAL_E5I,
    CODE_GAL_E5Q,
    CODE_GAL_E5X,
    CODE_GAL_E6B,
    CODE_GAL_E6C,
    CODE_GAL_E6X,
    CODE_GAL_E7I,
    CODE_GAL_E7Q,
    CODE_GAL_E7X,
    CODE_GAL_E8I,
    CODE_GAL_E8Q,
    CODE_GAL_E8X,
    CODE_AUX_GAL,

    CODE_QZS_L1CA,
    CODE_QZS_L2CM,
    CODE_QZS_L2CL,
    CODE_QZS_L2CX,
    CODE_QZS_L5I,
    CODE_QZS_L5Q,
    CODE_QZS_L5X,
    CODE_AUX_QZS]

GUI_CODES = {
    'GPS': [
        CODE_GPS_L1CA,
        CODE_GPS_L2CM,
        CODE_GPS_L2CL,
        CODE_GPS_L2CX,
        CODE_GPS_L1P,
        CODE_GPS_L2P,
        CODE_GPS_L5I,
        CODE_GPS_L5Q,
        CODE_GPS_L5X,
        CODE_GPS_L1CI,
        CODE_GPS_L1CQ,
        CODE_GPS_L1CX,
        CODE_AUX_GPS],

    'GLO': [
        CODE_GLO_L1OF,
        CODE_GLO_L2OF,
        CODE_GLO_L1P,
        CODE_GLO_L2P],

    'GAL': [
        CODE_GAL_E1B,
        CODE_GAL_E1C,
        CODE_GAL_E1X,
        CODE_GAL_E6B,
        CODE_GAL_E6C,
        CODE_GAL_E6X,
        CODE_GAL_E7I,
        CODE_GAL_E7Q,
        CODE_GAL_E7X,
        CODE_GAL_E8I,
        CODE_GAL_E8Q,
        CODE_GAL_E8X,
        CODE_GAL_E5I,
        CODE_GAL_E5Q,
        CODE_GAL_E5X,
        CODE_AUX_GAL],

    'QZS': [
        CODE_QZS_L1CA,
        CODE_QZS_L2CM,
        CODE_QZS_L2CL,
        CODE_QZS_L2CX,
        CODE_QZS_L5I,
        CODE_QZS_L5Q,
        CODE_QZS_L5X,
        CODE_AUX_QZS],

    'BDS': [
        CODE_BDS2_B1,
        CODE_BDS2_B2,
        CODE_BDS3_B1CI,
        CODE_BDS3_B1CQ,
        CODE_BDS3_B1CX,
        CODE_BDS3_B5I,
        CODE_BDS3_B5Q,
        CODE_BDS3_B5X,
        CODE_BDS3_B7I,
        CODE_BDS3_B7Q,
        CODE_BDS3_B7X,
        CODE_BDS3_B3I,
        CODE_BDS3_B3Q,
        CODE_BDS3_B3X],

    'SBAS': [
        CODE_SBAS_L1CA,
        CODE_SBAS_L5I,
        CODE_SBAS_L5Q,
        CODE_SBAS_L5X,
        CODE_AUX_SBAS]
}

GPS_L1CA_STR = 'GPS L1CA'
GPS_L2CM_STR = 'GPS L2C M'
GPS_L2CL_STR = 'GPS L2C L'
GPS_L2CX_STR = 'GPS L2C M+L'
GPS_L1P_STR = 'GPS L1P'
GPS_L2P_STR = 'GPS L2P'
GPS_L5I_STR = 'GPS L5 I'
GPS_L5Q_STR = 'GPS L5 Q'
GPS_L5X_STR = 'GPS L5 I+Q'
GPS_AUX_STR = 'AUX GPS L1'

SBAS_L1_STR = 'SBAS L1'
SBAS_L5I_STR = 'SBAS L5 I'
SBAS_L5Q_STR = 'SBAS L5 Q'
SBAS_L5X_STR = 'SBAS L5 I+Q'
SBAS_AUX_STR = 'AUX SBAS L1'

GLO_L1OF_STR = 'GLO L1OF'
GLO_L2OF_STR = 'GLO L2OF'
GLO_L1P_STR = 'GLO L1P'
GLO_L2P_STR = 'GLO L2P'

BDS2_B1_STR = 'BDS2 B1 I'
BDS2_B2_STR = 'BDS2 B2 I'
BDS3_B1CI_STR = 'BDS3 B1C I'
BDS3_B1CQ_STR = 'BDS3 B1C Q'
BDS3_B1CX_STR = 'BDS3 B1C I+Q'
BDS3_B5I_STR = 'BDS3 B2a I'
BDS3_B5Q_STR = 'BDS3 B2a Q'
BDS3_B5X_STR = 'BDS3 B2a X'
BDS3_B7I_STR = 'BDS3 B2b I'
BDS3_B7Q_STR = 'BDS3 B2b Q'
BDS3_B7X_STR = 'BDS3 B2b X'
BDS3_B3I_STR = 'BDS3 B3I'
BDS3_B3Q_STR = 'BDS3 B3Q'
BDS3_B3X_STR = 'BDS3 B3X'
BDS3_AUX_STR = 'AUX BDS B1'

GAL_E1B_STR = 'GAL E1 B'
GAL_E1C_STR = 'GAL E1 C'
GAL_E1X_STR = 'GAL E1 B+C'
GAL_E5I_STR = 'GAL E5a I'
GAL_E5Q_STR = 'GAL E5a Q'
GAL_E5X_STR = 'GAL E5a I+Q'
GAL_E6B_STR = 'GAL E6 B'
GAL_E6C_STR = 'GAL E6 C'
GAL_E6X_STR = 'GAL E6 B+C'
GAL_E8I_STR = 'GAL AltBOC'
GAL_E8Q_STR = 'GAL AltBOC'
GAL_E8X_STR = 'GAL AltBOC'
GAL_E7I_STR = 'GAL E5b I'
GAL_E7Q_STR = 'GAL E5b Q'
GAL_E7X_STR = 'GAL E5b I+Q'
GAL_AUX_STR = 'AUX GAL E1'

QZS_L1CA_STR = 'QZS L1CA'
QZS_L2CM_STR = 'QZS L2C M'
QZS_L2CL_STR = 'QZS L2C L'
QZS_L2CX_STR = 'QZS L2C M+L'
QZS_L5I_STR = 'QZS L5 I'
QZS_L5Q_STR = 'QZS L5 Q'
QZS_L5X_STR = 'QZS L5 I+Q'
QZS_AUX_STR = 'AUX QZS L1'

CODE_TO_STR_MAP = {
    CODE_GPS_L1CA: GPS_L1CA_STR,
    CODE_GPS_L2CM: GPS_L2CM_STR,
    CODE_GPS_L2CL: GPS_L2CL_STR,
    CODE_GPS_L2CX: GPS_L2CX_STR,
    CODE_GPS_L1P: GPS_L1P_STR,
    CODE_GPS_L2P: GPS_L2P_STR,
    CODE_GPS_L5I: GPS_L5I_STR,
    CODE_GPS_L5Q: GPS_L5Q_STR,
    CODE_GPS_L5X: GPS_L5X_STR,
    CODE_AUX_GPS: GPS_AUX_STR,

    CODE_GLO_L1OF: GLO_L1OF_STR,
    CODE_GLO_L2OF: GLO_L2OF_STR,
    CODE_GLO_L1P: GLO_L1P_STR,
    CODE_GLO_L2P: GLO_L2P_STR,

    CODE_SBAS_L1CA: SBAS_L1_STR,
    CODE_SBAS_L5I: SBAS_L5I_STR,
    CODE_SBAS_L5Q: SBAS_L5Q_STR,
    CODE_SBAS_L5X: SBAS_L5X_STR,
    CODE_AUX_SBAS: SBAS_AUX_STR,

    CODE_BDS2_B1: BDS2_B1_STR,
    CODE_BDS2_B2: BDS2_B2_STR,
    CODE_BDS3_B1CI: BDS3_B1CI_STR,
    CODE_BDS3_B1CQ: BDS3_B1CQ_STR,
    CODE_BDS3_B1CX: BDS3_B1CX_STR,
    CODE_BDS3_B5I: BDS3_B5I_STR,
    CODE_BDS3_B5Q: BDS3_B5Q_STR,
    CODE_BDS3_B5X: BDS3_B5X_STR,
    CODE_BDS3_B7I: BDS3_B7I_STR,
    CODE_BDS3_B7Q: BDS3_B7Q_STR,
    CODE_BDS3_B7X: BDS3_B7X_STR,
    CODE_BDS3_B3I: BDS3_B3I_STR,
    CODE_BDS3_B3Q: BDS3_B3Q_STR,
    CODE_BDS3_B3X: BDS3_B3X_STR,

    CODE_GAL_E1B: GAL_E1B_STR,
    CODE_GAL_E1C: GAL_E1C_STR,
    CODE_GAL_E1X: GAL_E1X_STR,
    CODE_GAL_E6B: GAL_E6B_STR,
    CODE_GAL_E6C: GAL_E6C_STR,
    CODE_GAL_E6X: GAL_E6X_STR,
    CODE_GAL_E7I: GAL_E7I_STR,
    CODE_GAL_E7Q: GAL_E7Q_STR,
    CODE_GAL_E7X: GAL_E7X_STR,
    CODE_GAL_E8I: GAL_E8I_STR,
    CODE_GAL_E8Q: GAL_E8Q_STR,
    CODE_GAL_E8X: GAL_E8X_STR,
    CODE_GAL_E5I: GAL_E5I_STR,
    CODE_GAL_E5Q: GAL_E5Q_STR,
    CODE_GAL_E5X: GAL_E5X_STR,
    CODE_AUX_GAL: GAL_AUX_STR,

    CODE_QZS_L1CA: QZS_L1CA_STR,
    CODE_QZS_L2CM: QZS_L2CM_STR,
    CODE_QZS_L2CL: QZS_L2CL_STR,
    CODE_QZS_L2CX: QZS_L2CX_STR,
    CODE_QZS_L5I: QZS_L5I_STR,
    CODE_QZS_L5Q: QZS_L5Q_STR,
    CODE_QZS_L5X: QZS_L5X_STR
}

STR_TO_CODE_MAP = {
    GPS_L1CA_STR: CODE_GPS_L1CA,
    GPS_L2CM_STR: CODE_GPS_L2CM,
    GPS_L2CL_STR: CODE_GPS_L2CL,
    GPS_L2CX_STR: CODE_GPS_L2CX,
    GPS_L5I_STR: CODE_GPS_L5I,
    GPS_L5Q_STR: CODE_GPS_L5Q,
    GPS_L5X_STR: CODE_GPS_L5X,
    GPS_L1P_STR: CODE_GPS_L1P,
    GPS_L2P_STR: CODE_GPS_L2P,
    GPS_AUX_STR: CODE_AUX_GPS,

    SBAS_L1_STR: CODE_SBAS_L1CA,
    SBAS_L5I_STR: CODE_SBAS_L5I,
    SBAS_L5Q_STR: CODE_SBAS_L5Q,
    SBAS_L5X_STR: CODE_SBAS_L5X,
    SBAS_AUX_STR: CODE_AUX_SBAS,

    GLO_L1OF_STR: CODE_GLO_L1OF,
    GLO_L2OF_STR: CODE_GLO_L2OF,
    GLO_L1P_STR: CODE_GLO_L1P,
    GLO_L2P_STR: CODE_GLO_L2P,

    BDS2_B1_STR: CODE_BDS2_B1,
    BDS2_B2_STR: CODE_BDS2_B2,
    BDS3_B1CI_STR: CODE_BDS3_B1CI,
    BDS3_B1CQ_STR: CODE_BDS3_B1CQ,
    BDS3_B1CX_STR: CODE_BDS3_B1CX,
    BDS3_B5I_STR: CODE_BDS3_B5I,
    BDS3_B5Q_STR: CODE_BDS3_B5Q,
    BDS3_B5X_STR: CODE_BDS3_B5X,
    BDS3_B7I_STR: CODE_BDS3_B7I,
    BDS3_B7Q_STR: CODE_BDS3_B7Q,
    BDS3_B7X_STR: CODE_BDS3_B7X,
    BDS3_B3I_STR: CODE_BDS3_B3I,
    BDS3_B3Q_STR: CODE_BDS3_B3Q,
    BDS3_B3X_STR: CODE_BDS3_B3X,

    GAL_E1B_STR: CODE_GAL_E1B,
    GAL_E1C_STR: CODE_GAL_E1C,
    GAL_E1X_STR: CODE_GAL_E1X,
    GAL_E5I_STR: CODE_GAL_E5I,
    GAL_E5Q_STR: CODE_GAL_E5Q,
    GAL_E5X_STR: CODE_GAL_E5X,
    GAL_E6B_STR: CODE_GAL_E6B,
    GAL_E6C_STR: CODE_GAL_E6C,
    GAL_E6X_STR: CODE_GAL_E6X,
    GAL_E7I_STR: CODE_GAL_E7I,
    GAL_E7Q_STR: CODE_GAL_E7Q,
    GAL_E7X_STR: CODE_GAL_E7X,
    GAL_E8I_STR: CODE_GAL_E8I,
    GAL_E8Q_STR: CODE_GAL_E8Q,
    GAL_E8X_STR: CODE_GAL_E8X,
    GAL_AUX_STR: CODE_AUX_GAL,

    QZS_L1CA_STR: CODE_QZS_L1CA,
    QZS_L2CM_STR: CODE_QZS_L2CM,
    QZS_L2CL_STR: CODE_QZS_L2CL,
    QZS_L2CX_STR: CODE_QZS_L2CX,
    QZS_L5I_STR: CODE_QZS_L5I,
    QZS_L5Q_STR: CODE_QZS_L5Q,
    QZS_L5X_STR: CODE_QZS_L5X,
    QZS_AUX_STR: CODE_AUX_QZS
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

DIFFERENTIAL_MODES = [FIXED_MODE, FLOAT_MODE, DGNSS_MODE]

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


gps_codes = {
    CODE_GPS_L1CA,
    CODE_GPS_L2CM,
    CODE_GPS_L2CL,
    CODE_GPS_L2CX,
    CODE_GPS_L1P,
    CODE_GPS_L2P,
    CODE_GPS_L5I,
    CODE_GPS_L5Q,
    CODE_GPS_L5X,
    CODE_AUX_GPS}


def code_is_gps(code):
    return code in gps_codes


glo_codes = {
    CODE_GLO_L1OF,
    CODE_GLO_L2OF,
    CODE_GLO_L1P,
    CODE_GLO_L2P}


def code_is_glo(code):
    return code in glo_codes


sbas_codes = {
    CODE_SBAS_L1CA,
    CODE_SBAS_L5I,
    CODE_SBAS_L5Q,
    CODE_SBAS_L5X,
    CODE_AUX_SBAS}


def code_is_sbas(code):
    return code in sbas_codes


bds_codes = {
    CODE_BDS2_B1,
    CODE_BDS2_B2,
    CODE_BDS3_B1CI,
    CODE_BDS3_B1CQ,
    CODE_BDS3_B1CX,
    CODE_BDS3_B5I,
    CODE_BDS3_B5Q,
    CODE_BDS3_B5X,
    CODE_BDS3_B3I,
    CODE_BDS3_B3Q,
    CODE_BDS3_B3X,
    CODE_BDS3_B7I,
    CODE_BDS3_B7Q,
    CODE_BDS3_B7X}


def code_is_bds(code):
    return code in bds_codes


gal_codes = {
    CODE_GAL_E1B,
    CODE_GAL_E1C,
    CODE_GAL_E1X,
    CODE_GAL_E6B,
    CODE_GAL_E6C,
    CODE_GAL_E6X,
    CODE_GAL_E7I,
    CODE_GAL_E7Q,
    CODE_GAL_E7X,
    CODE_GAL_E8I,
    CODE_GAL_E8Q,
    CODE_GAL_E8X,
    CODE_GAL_E5I,
    CODE_GAL_E5Q,
    CODE_GAL_E5X,
    CODE_AUX_GAL}


def code_is_galileo(code):
    return code in gal_codes


qzss_codes = {
    CODE_QZS_L1CA,
    CODE_QZS_L2CM,
    CODE_QZS_L2CL,
    CODE_QZS_L2CX,
    CODE_QZS_L5I,
    CODE_QZS_L5Q,
    CODE_QZS_L5X,
    CODE_AUX_QZS}


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

    Thread(target=loop).start()
    return stopped.set


resource_filename = partial(pkg_resources.resource_filename, 'piksi_tools')
resource_stream = partial(pkg_resources.resource_stream, 'piksi_tools')
icon = ImageResource(resource_filename('console/images/icon.png'))

swift_path = os.path.normpath(os.path.join(os.path.expanduser("~"), 'SwiftNav'))
