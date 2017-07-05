#!/usr/bin/env python
# Copyright (C) 2011-2014 Swift Navigation Inc.
# Contact: Colin Beighley <colin@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

from __future__ import absolute_import, print_function

import struct
import time

from sbp.client import Framer, Handler
from sbp.flash import (SBP_MSG_STM_UNIQUE_ID_RESP, MsgStmUniqueIdReq,
                       MsgStmUniqueIdResp)
from sbp.system import SBP_MSG_HEARTBEAT

from piksi_tools.heartbeat import Heartbeat

from . import serial_link


class STMUniqueID(object):
    """
    Retrieve the STM Unique ID from Piksi.
    """

    def __init__(self, link):
        """
        Parameters
        ==========
        link : sbp.client.handler.Handler
          link to register Heartbeat message callback with
        sbp_version : tuple (int, int)
          SBP version to use for STM Unique ID messages.
        """
        self.unique_id_returned = False
        self.unique_id = None
        self.link = link
        self.heartbeat = Heartbeat()

    def __enter__(self):
        self.link.add_callback(self.heartbeat, SBP_MSG_HEARTBEAT)
        self.link.add_callback(self.receive_stm_unique_id_callback,
                               SBP_MSG_STM_UNIQUE_ID_RESP)
        return self

    def __exit__(self, *args):
        self.link.remove_callback(self.heartbeat, SBP_MSG_HEARTBEAT)
        self.link.remove_callback(self.receive_stm_unique_id_callback,
                                  SBP_MSG_STM_UNIQUE_ID_RESP)

    def receive_stm_unique_id_callback(self, sbp_msg, **metadata):
        """
        Registered as a callback for the Heartbeat message
        with sbp.client.handler.Handler.
        """
        self.unique_id_returned = True
        self.unique_id = struct.unpack('<12B', sbp_msg.payload)

    def get_id(self):
        """ Retrieve the STM Unique ID. Blocks until it has received the ID. """
        while not self.heartbeat.received:
            time.sleep(0.1)
        self.unique_id_returned = False
        self.unique_id = None
        # < 0.45 of the bootloader, reuse single stm message.
        if self.heartbeat.sbp_version < (0, 45):
            self.link(MsgStmUniqueIdResp())
        else:
            self.link(MsgStmUniqueIdReq())
        while not self.unique_id_returned:
            time.sleep(0.1)
        return self.unique_id


def get_args():
    """
    Get and parse arguments.
    """
    import argparse
    parser = argparse.ArgumentParser(description='STM Unique ID')
    parser.add_argument(
        "-f",
        "--ftdi",
        help="use pylibftdi instead of pyserial.",
        action="store_true")
    parser.add_argument(
        '-p',
        '--port',
        default=[serial_link.SERIAL_PORT],
        nargs=1,
        help='specify the serial port to use.')
    parser.add_argument(
        "-b",
        "--baud",
        default=[serial_link.SERIAL_BAUD],
        nargs=1,
        help="specify the baud rate to use.")
    return parser.parse_args()


def main():
    """
    Get configuration, get driver, and build handler and start it.
    """
    args = get_args()
    port = args.port[0]
    baud = args.baud[0]
    # Driver with context
    with serial_link.get_driver(args.ftdi, port, baud) as driver:
        with Handler(Framer(driver.read, driver.write)) as link:
            with STMUniqueID(link) as stm_unique_id:
                unique_id = stm_unique_id.get_id()
            print("STM Unique ID =",
                  "0x" + ''.join(["%02x" % (b) for b in unique_id]))


if __name__ == "__main__":
    main()
