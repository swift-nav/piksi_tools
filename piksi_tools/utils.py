#!/usr/bin/env python
# Copyright (C) 2015 Swift Navigation Inc.
# Contact: Colin Beighley <colin@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

from __future__ import print_function

import errno
import os
import sys
import time

from sbp.piksi import SBP_MSG_RESET
from sbp.system import SBP_MSG_HEARTBEAT

from piksi_tools.flash import Flash
from piksi_tools.heartbeat import Heartbeat
from piksi_tools.timeout import (TIMEOUT_BOOT, TIMEOUT_ERASE_STM,
                                 TIMEOUT_PROGRAM_STM, TIMEOUT_WRITE_NAP,
                                 Timeout)


def set_app_mode(handler, verbose=False):
    """
  Set Piksi into the application firmware, regardless of whether it is
  currently in the application firmware or the bootloader. Will raise a
  piksi_tools.timeout.TimeoutError if Piksi responses appear to have hung.

  Parameters
  ==========
  handler : sbp.client.handler.Handler
    handler to send/receive messages from/to Piksi.
  verbose : bool
    Print more verbose output.

  """
    from piksi_tools.bootload import Bootloader

    if verbose:
        print("Setting device into application mode")

    # Wait until we receive a heartbeat or bootloader handshake so we
    # know what state Piksi is in.
    with Bootloader(handler) as piksi_bootloader:

        heartbeat = Heartbeat()
        handler.add_callback(heartbeat, SBP_MSG_HEARTBEAT)

        if verbose:
            print("Waiting for bootloader handshake or heartbeat from device")
        with Timeout(TIMEOUT_BOOT) as timeout:
            while not heartbeat.received and not piksi_bootloader.handshake_received:
                time.sleep(0.1)

        handler.remove_callback(heartbeat, SBP_MSG_HEARTBEAT)

        # If Piksi is in the application, simply return.
        if heartbeat.received:
            if verbose:
                print("Received heartbeat")
            return

        # Piksi is in the bootloader, tell Piksi to jump into the application.
        with Timeout(TIMEOUT_BOOT) as timeout:
            if verbose:
                print("Waiting for bootloader handshake from device")
            piksi_bootloader.handshake()
        piksi_bootloader.jump_to_app()
        if verbose:
            print("Received handshake")
        if verbose:
            print("Telling device to jump to application")

        # Wait for Heartbeat to ensure we're in the application firmware.
        heartbeat = Heartbeat()
        handler.add_callback(heartbeat, SBP_MSG_HEARTBEAT)

        if verbose:
            print("Waiting for heartbeat")
        with Timeout(TIMEOUT_BOOT) as timeout:
            while not heartbeat.received:
                time.sleep(0.1)
        if verbose:
            print("Received heartbeat")

        handler.remove_callback(heartbeat, SBP_MSG_HEARTBEAT)

def wrap_sbp_dict(data_dict, timestamp):
    return {'data': data_dict, 'time': timestamp}


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        # seems to be raised while calling os.makedirs on the root of a writable
        # directory
        elif getattr(exc, 'winerror', None) == 5:
            pass
        else:
            raise


def sopen(path, mode):
    ''' Open "path" for writing, creating any parent directories as needed.
    '''
    mkdir_p(os.path.dirname(path))
    return open(path, mode)
