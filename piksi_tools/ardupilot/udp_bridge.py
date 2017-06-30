#!/usr/bin/env python
# Copyright (C) 2015 Swift Navigation Inc.
# Contact: Fergus Noble <fergus@swiftnav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.
"""
the :mod:`piksi_tools.udp_bridge` module contains an example of reading SBP
messages from a serial port, filtering for observations, and sending them over udp
to a mavproxy instance or Mission Planner for transmission to an ArduCopter quad.
"""

import time

from sbp.client import Framer, Handler
from sbp.client.drivers.pyserial_driver import PySerialDriver
from sbp.client.loggers.udp_logger import UdpLogger
from sbp.observation import SBP_MSG_OBS_DEP_C, SBP_MSG_BASE_POS_ECEF, SBP_MSG_BASE_POS_LLH

OBS_MSGS = [SBP_MSG_OBS_DEP_C, SBP_MSG_BASE_POS_ECEF, SBP_MSG_BASE_POS_LLH]

DEFAULT_SERIAL_PORT = "/dev/ttyUSB0"
DEFAULT_SERIAL_BAUD = 1000000

DEFAULT_UDP_ADDRESS = "127.0.0.1"
DEFAULT_UDP_PORT = 13320


def get_args():
    """
    Get and parse arguments.
    """
    import argparse
    parser = argparse.ArgumentParser(
        description="Swift Navigation UDP Relay tool.")
    parser.add_argument(
        "-s",
        "--serial-port",
        default=[DEFAULT_SERIAL_PORT],
        nargs=1,
        help="specify the serial port to use.")
    parser.add_argument(
        "-b",
        "--baud",
        default=[DEFAULT_SERIAL_BAUD],
        nargs=1,
        help="specify the baud rate to use.")
    parser.add_argument(
        "-a",
        "--address",
        default=[DEFAULT_UDP_ADDRESS],
        nargs=1,
        help="specify the UDP IP Address to use.")
    parser.add_argument(
        "-p",
        "--udp-port",
        default=[DEFAULT_UDP_PORT],
        nargs=1,
        help="specify the UDP Port to use.")
    return parser.parse_args()


def main():
    """Simple command line interface for running the udp bridge to
    forward observation messages

    """
    args = get_args()
    port = int(args.udp_port[0])
    address = args.address[0]
    with PySerialDriver(args.serial_port[0], args.baud[0]) as driver:
        with Handler(Framer(driver.read, driver.write)) as handler:
            with UdpLogger(address, port) as udp:
                handler.add_callback(udp, OBS_MSGS)
                # Note, we may want to send the ephemeris message in the future
                # but the message is too big for MAVProxy right now
                try:
                    while True:
                        time.sleep(0.1)
                except KeyboardInterrupt:
                    pass


if __name__ == "__main__":
    main()
