#!/usr/bin/env python

# Unlock all sectors of the Piksi STM32 flash.

import sys

from sbp.client.handler import Handler

from piksi_tools import serial_link
from piksi_tools.bootload import Bootloader
from piksi_tools.flash import Flash


def get_args():
    """
    Get and parse arguments.
    """
    import argparse
    parser = argparse.ArgumentParser(
        description='Unlock all Piksi STM32 sectors')
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
    args = parser.parse_args()
    return args


def main():
    """
    Get configuration, get driver, build handler, and unlock sectors.
    """
    args = get_args()
    port = args.port[0]
    baud = args.baud[0]

    # Driver with context
    with serial_link.get_driver(
            use_ftdi=False, port=port, baud=baud) as driver:
        # Handler with context
        with Handler(driver.read, driver.write) as link:
            with Bootloader(link) as piksi_bootloader:
                print "Waiting for bootloader handshake message from Piksi ...",
                sys.stdout.flush()
                try:
                    piksi_bootloader.handshake()
                except KeyboardInterrupt:
                    return
                print "received."
                print "Piksi Onboard Bootloader Version:", piksi_bootloader.version
                if piksi_bootloader.sbp_version > (0, 0):
                    print "Piksi Onboard SBP Protocol Version:", piksi_bootloader.sbp_version

                # Catch all other errors and exit cleanly.
                try:
                    with Flash(
                            link,
                            flash_type="STM",
                            sbp_version=piksi_bootloader.sbp_version
                    ) as piksi_flash:
                        for s in range(0, 12):
                            print "\rUnlocking STM Sector", s,
                            sys.stdout.flush()
                            piksi_flash.unlock_sector(s)
                        print
                except:
                    import traceback
                    traceback.print_exc()


if __name__ == "__main__":
    main()
