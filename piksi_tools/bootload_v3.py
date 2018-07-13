#!/usr/bin/env python
#
# Bootloader for the Swift Navigation Piksi GPS Receiver
#
# Copyright (C) 2010 Gareth McMullin <gareth@blacksphere.co.nz>
# Copyright (C) 2011 Piotr Esden-Tempski <piotr@esden.net>
# Copyright (C) 2013-2014 Swift Navigation Inc <www.swift-nav.com>
#
# Contacts: Colin Beighley <colin@swift-nav.com>
#           Fergus Noble <fergus@swift-nav.com>
#
# Based on luftboot, a bootloader for the Paparazzi UAV project.
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.
"""
The :mod:`piksi_tools.bootload` module contains functions loading firmware
images.
"""
from __future__ import absolute_import, print_function

import random
import sys
import threading

from sbp.client import Framer, Handler
from sbp.logging import SBP_MSG_LOG, SBP_MSG_PRINT_DEP
from sbp.piksi import SBP_MSG_COMMAND_RESP, MsgCommandReq, MsgReset

from piksi_tools import serial_link
from piksi_tools.fileio import FileIO


def get_args():
    """
    Get and parse arguments.
    """
    import argparse
    parser = argparse.ArgumentParser(description='Piksi Bootloader')
    parser.add_argument("file", help="the image set file to write to flash.")
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
    parser.add_argument(
        "-f",
        "--ftdi",
        help="use pylibftdi instead of pyserial.",
        action="store_true")
    return parser.parse_args()


def shell_command(link, cmd, timeout=None, progress_cb=None):
    ev = threading.Event()
    seq = random.randint(0, 0xffffffff)
    ret = {}
    elapsed_intervals = 0

    def resp_handler(msg, **kwargs):
        if msg.sequence == seq:
            ret['code'] = msg.code
            ev.set()

    link.add_callback(resp_handler, SBP_MSG_COMMAND_RESP)
    link(MsgCommandReq(sequence=seq, command=cmd))
    while (elapsed_intervals < timeout):
        ev.wait(timeout)
        if progress_cb:
            progress_cb(float(elapsed_intervals) / float(timeout) * 100)
        elapsed_intervals += 1
    if len(ret.items()) == 0:
        print(("Shell command timeout: execution exceeded {0} "
               "seconds with no response.").format(timeout))
        return -255
    return ret['code']


def main():
    """
    Get configuration, get driver, and build handler and start it.
    """
    args = get_args()
    port = args.port[0]
    baud = args.baud[0]
    use_ftdi = args.ftdi
    # Driver with context
    with serial_link.get_driver(use_ftdi, port, baud) as driver:
        # Handler with context
        with Handler(Framer(driver.read, driver.write)) as link:
            link.add_callback(serial_link.log_printer, SBP_MSG_LOG)
            link.add_callback(serial_link.printer, SBP_MSG_PRINT_DEP)

            data = open(args.file, 'rb').read()

            def progress_cb(size):
                sys.stdout.write("\rProgress: %d%%    \r" %
                                 (100 * size / len(data)))
                sys.stdout.flush()

            print('Transferring image file...')
            FileIO(link).write(
                "upgrade.image_set.bin", data, progress_cb=progress_cb)
            print('Committing file to flash...')
            code = shell_command(link, "upgrade_tool upgrade.image_set.bin",
                                 300)
            if code != 0:
                print('Failed to perform upgrade (code = %d)' % code)
                return
            print('Resetting Piksi...')
            link(MsgReset(flags=0))


if __name__ == "__main__":
    main()
