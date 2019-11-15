#!/usr/bin/env python
# Copyright (C) 2015 Swift Navigation Inc.
# Contact: Fergus Noble <fergus@swiftnav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR
"""
Combines a base and rover JSON SBP log file into a single JSON SBP log,
interleaving messages to produce a stream that increases monotonically in GPS time.
Further, sets the sender id of base log messages to zero.

This script only passes through a subset of all SBP messages. Only messages
necessary during post-processing observations to produce navigation solutions
are preserved. Specifically, observations, ephemeris, ionosphere, and base positions.

This script supports a post-processing use case for Piksi.
You can separately record a log file on a rover and on a base Piksi.
Use this script to create a single log file, which can be passed to
libswiftnav-private's run_filter command to produce a RTK baseline stream.

Requirements:

  pip install json
  sudo pip install sbp

"""
from __future__ import print_function
import argparse
import sys

import sbp.client.loggers.json_logger as json_logger
from sbp.client.drivers.file_driver import FileDriver
from sbp.client import Framer
import sbp.observation as ob
import sbp.navigation as nv
import sbp.imu as imu 

SECONDS_IN_WEEK = 7 * 24 * 60 * 60

obs_msgs = [
    ob.SBP_MSG_OBS, ob.SBP_MSG_EPHEMERIS_GPS, ob.SBP_MSG_EPHEMERIS_SBAS,
    ob.SBP_MSG_EPHEMERIS_GLO, ob.SBP_MSG_IONO, ob.SBP_MSG_BASE_POS_LLH,
    ob.SBP_MSG_BASE_POS_ECEF
]

pvt_msgs = [ nv.SBP_MSG_GPS_TIME, nv.SBP_MSG_UTC_TIME,
    nv.SBP_MSG_POS_LLH_COV, nv.SBP_MSG_POS_ECEF_COV, nv.SBP_MSG_VEL_NED_COV, nv.SBP_MSG_VEL_ECEF_COV,
    nv.SBP_MSG_POS_LLH, nv.SBP_MSG_POS_ECEF, nv.SBP_MSG_VEL_NED, nv.SBP_MSG_VEL_ECEF]

ins_msgs = [imu.SBP_MSG_IMU_RAW, imu.SBP_MSG_IMU_AUX ]

last_time_stream_dict = {'base': {}, 'rover': {}}

def extract_gpstime_wn_unk(msg, stream_id, last_gpstime=(0, 0)):
    '''
    Returns (wn,tow) tuple. returns last_gpstime if none in this message
    '''
    if msg.msg_type == imu.SBP_MSG_IMU_RAW:
        # TODO: handle other kinds of timestamps other than absolute
        if msg.tow > SECONDS_IN_WEEK: # time greater than seconds in week indicates invalid time at present
            return last_gpstime # -1 will be invalid / unknown time
    # first, check and see if we have a week number in our history dict for this message, if not, set one
    last_time = last_time_stream_dict[stream_id].get(msg.msg_type, None)
    if msg_type_last_time == None:
        last_time_stream_dict[stream_id].update({msg.msg_type: (0, msg.tow)})
        last_time = last_time_stream_dict[stream_id].get(msg.msg_type, None)
    # if we have gone back in time, increment week number in the last_time_stream_dict
    if msg.tow < last_time[1]:
        current_wn = last_time[0] + 1
        last_time_stream_dict[stream_id][msg.msg_type] = (current_wn, msg.tow)
    return (last_time_stream_dict[stream_id][msg.msg_type][0], msg.tow)


def extract_gpstime(msg, last_gpstime=(0, 0)):
    '''
    Returns (wn,tow) tuple. returns last_gpstime if none in this message
    '''
    if msg.msg_type == ob.SBP_MSG_OBS:
        return (msg.header.t.wn, msg.header.t.tow)
    elif msg.msg_type == ob.SBP_MSG_EPHEMERIS_GPS or msg.msg_type == ob.SBP_MSG_EPHEMERIS_SBAS or msg.msg_type == ob.SBP_MSG_EPHEMERIS_GLO:
        return (msg.toc.wn, msg.toc.tow)
    elif msg.msg_type == ob.SBP_MSG_IONO:
        return (msg.t_nmct.wn, msg.t_nmct.tow)
    elif msg.msg_type == ob.SBP_MSG_BASE_POS_ECEF or msg.msg_type == ob.SBP_MSG_BASE_POS_LLH:
        return last_gpstime


def compare_gpstime(g0, g1):
    '''
    Returns the index of the earlier GPSTIME (wn,tow) tow.
    '''
    wn0 = g0[0]
    tow0 = g0[1]
    wn1 = g1[0]
    tow1 = g1[1]
    if wn0 < wn1:
        return 0
    elif wn0 > wn1:
        return 1
    else:
        if tow0 < tow1:
            return 0
        elif tow0 > tow1:
            return 1
        else:
            return 0


def print_emit_json(msg):
    print(msg.to_json())

def print_emit_bin(msg):
    sys.stdout.write(msg.to_binary())

def zip_generators(base_gen, rove_gen, emit_fn, ins):
    '''
    Zips together two generators.
    Runs in constant space.
    Sends messages to the emit_fn

    Here's the algorithm:
      We assume we might have a message from every logfile
      For the logfiles we don't have a message, we retrieve one.
      We get timestamps for all our messages.
      We consume and discard the one with the oldest timestamp, keeping the other around
      Repeat!
    '''
    if ins:
        msg_filters_base = ins_msgs 
        msg_filters_rover = pvt_msgs
    else:
        msg_filters_base = obs_msgs
        msg_filters_rover = obs_msgs
    
    base_msg = None
    rove_msg = None

    last_gpstime = (0, 0)
    while True:

        # Get a base_msg if we don't have one waiting
        while base_msg is None:
            try:
                base_msg = base_gen.next()[0]
                if base_msg.msg_type in msg_filters_base:
                    if not ins: # Fix up base id for obs zipping
                        base_msg.sender = 0
                    break
                else:
                    base_msg = None
            except StopIteration:
                base_done = True
                break

        # Get a rover_msg if we don't have one waiting
        while rove_msg is None:
            try:
                rove_msg = rove_gen.next()[0]
                if rove_msg.msg_type in msg_filters_rover:
                    break
                else:
                    rove_msg = None
            except StopIteration:
                rove_done = True
                break

        if base_msg is None and rove_msg is None:
            return  # We are done.

        if base_msg is None:
            emit_fn(rove_msg)
            rove_msg = None
            continue  # Loop!

        if rove_msg is None:
            emit_fn(base_msg)
            base_msg = None
            continue  # Loop!

        # We have a message from both. Which one do we emit?
        if ins:
            base_time = extract_gpstime_wn_unknown(base_msg, 'base', last_gpstime)
            rove_time = extract_gpstime_wn_unknown(rove_msg, 'rover', last_gpstime)
        else:
            base_time = extract_gpstime(base_msg, last_gpstime)
            rove_time = extract_gpstime(rove_msg, last_gpstime)
        which = compare_gpstime(rove_time, base_time)
        if which == 1:
            emit_fn(base_msg)
            base_msg = None
            last_gpstime = base_time
        else:
            emit_fn(rove_msg)
            rove_msg = None
            last_gpstime = rove_time


def zip_json_files(base_log_handle, rove_log_handle, emit_fn, ins):
    with json_logger.JSONLogIterator(base_log_handle) as base_logger:
        with json_logger.JSONLogIterator(rove_log_handle) as rove_logger:

            base_gen = next(base_logger)
            rove_gen = next(rove_logger)

            zip_generators(base_gen, rove_gen, emit_fn, ins)

def zip_binary_files(log1_handle, log2_handle, emit_fn, ins):
    log1_driver = FileDriver(log1_handle)
    log2_driver = FileDriver(log2_handle)
    iterator1 = Framer(log1_driver.read, log1_driver.write)
    iterator2 = Framer(log2_driver.read, log2_driver.read)
    zip_generators(iterator1, iterator2, emit_fn, ins)

def main():
    parser = argparse.ArgumentParser(
        description="Swift Navigation SBP Rover-Base Log Zipper")
    parser.add_argument("base_log")
    parser.add_argument("rover_log")
    parser.add_argument('--binary', 
                     action='store_true',
                     default=False,
                     help='expect binary logs as input and output binary logs')
    parser.add_argument('--ins',
                     action='store_true',
                     default=False,
                     help='expect "base_log" to have ins meaurements, and "rover_log" to gnss pvt solutions')

    args = parser.parse_args()
    if args.binary:
        open_type = 'rb'
    else:
        open_type = 'r'
    with open(args.base_log, open_type) as base_log_handle:
        with open(args.rover_log, open_type) as rover_log_handle:
            if args.binary:
                zip_binary_files(base_log_handle, rover_log_handle, print_emit_bin, args.ins)
            else:
                zip_json_files(base_log_handle, rover_log_handle, print_emit_json, args.ins)

if __name__ == "__main__":
    main()
