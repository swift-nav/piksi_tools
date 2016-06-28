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

import time
import struct
import sys
import serial_link

from sbp.bootload import *
from sbp.logging import *
from sbp.piksi import *
from sbp.client import Handler, Framer

class Bootloader():
  """
  Bootloader

  The :class:`Bootloader` loads firmware.
  """
  def __init__(self, link):
    self.stopped = False
    self.handshake_received = False
    self.version = None
    # SBP version is unset in older devices.
    self.sbp_version = (0, 0)
    self.link = link
    self.link.add_callback(self._deprecated_callback, SBP_MSG_BOOTLOADER_HANDSHAKE_DEP_A)
    self.link.add_callback(self._handshake_callback, SBP_MSG_BOOTLOADER_HANDSHAKE_RESP)

  def __enter__(self):
    return self

  def __exit__(self, *args):
    if not self.stopped:
      self.stop()

  def stop(self):
    """ Remove Bootloader instance callbacks from serial link. """
    self.stopped = True
    self.link.remove_callback(self._deprecated_callback, SBP_MSG_BOOTLOADER_HANDSHAKE_DEP_A)
    self.link.remove_callback(self._handshake_callback, SBP_MSG_BOOTLOADER_HANDSHAKE_RESP)

  def _deprecated_callback(self, sbp_msg, **metadata):
    """ Bootloader handshake for deprecated message ID. """
    hs_device = MsgBootloaderHandshakeDepA(sbp_msg)
    if len(hs_device.handshake)==1 and hs_device.handshake[0]==0:
      # == v0.1 of the bootloader, returns hardcoded version number 0.
      self.version = "v0.1"
    else:
      # > v0.1 of the bootloader, returns git commit string.
      self.version = ''.join([chr(i) for i in hs_device.handshake])
      if self.version == '':
        self.version = "Unknown"
    self.handshake_received = True

  def _handshake_callback(self, sbp_msg, **metadata):
    """ Bootloader handshake callback. """
    hs_device = MsgBootloaderHandshakeResp(sbp_msg)
    self.version = hs_device.version
    self.sbp_version = ((hs_device.flags >> 8) & 0xFF, hs_device.flags & 0xFF)
    self.handshake_received = True

  def handshake(self, timeout=None):
    """
    Handshake device into bootloader mode. If handshake is not received from device, attempt
    to reset it.

    Parameters
    ==========
    timeout: int
      Time to wait before returning False.

    Returns
    =======
    out : bool
      Returns True if handshake was received, False if timeout was reached before a handshake
      was received.
    """
    if timeout is not None:
      t0 = time.time()
    self.handshake_received = False
    expire = time.time() + 15.0
    self.link(MsgReset())
    while not self.handshake_received:
      time.sleep(0.1)
      if timeout is not None:
        if time.time()-timeout > t0:
          return False
      if time.time() > expire:
        expire = time.time() + 15.0
        self.link(MsgReset())
    # < 0.45 of SBP protocol, reuse single handshake message.
    if self.sbp_version < (0, 45):
      self.link(MsgBootloaderHandshakeDepA(handshake=''))
    else:
      self.link(MsgBootloaderHandshakeReq())
    return True

  def jump_to_app(self):
    """ Request Piksi bootloader jump to application. """
    self.link(MsgBootloaderJumpToApp(jump=0))

def get_args():
  """
  Get and parse arguments.
  """
  import argparse
  parser = argparse.ArgumentParser(description='Piksi Bootloader')
  parser.add_argument("file",
                      help="the Intel hex file to write to flash.")
  parser.add_argument('-m', '--m25',
                      help='write the file to the M25 (FPGA) flash.',
                      action="store_true")
  parser.add_argument('-s', '--stm',
                      help='write the file to the STM flash.',
                      action="store_true")
  parser.add_argument('-e', '--erase',
                      help='erase sectors 1-11 of the STM flash.',
                      action="store_true")
  parser.add_argument('-p', '--port',
                      default=[serial_link.SERIAL_PORT], nargs=1,
                      help='specify the serial port to use.')
  parser.add_argument("-b", "--baud",
                      default=[serial_link.SERIAL_BAUD], nargs=1,
                      help="specify the baud rate to use.")
  parser.add_argument("-q", "--max-queued-ops",
                      default=[1], nargs=1,
                      help="Maximum number of queued operations.")
  parser.add_argument("-f", "--ftdi",
                      help="use pylibftdi instead of pyserial.",
                      action="store_true")
  parser.add_argument("-t", "--timeout", nargs=1, type=int,
                      default=[None], 
                      help="Specify Timeout for which to wait for handshake.",
                      )
  args = parser.parse_args()
  if args.stm and args.m25:
    parser.error("Only one of -s or -m options may be chosen")
    sys.exit(2)
  elif not args.stm and not args.m25:
    parser.error("One of -s or -m options must be chosen")
    sys.exit(2)
  elif args.erase and not args.stm:
    parser.error("The -e option requires the -s option to also be chosen")
    sys.exit(2)
  return args

def main():
  """
  Get configuration, get driver, and build handler and start it.
  """
  args = get_args()
  port = args.port[0]
  baud = args.baud[0]
  use_ftdi = args.ftdi
  use_m25 = args.m25
  use_stm = args.stm
  erase = args.erase
  # Driver with context
  with serial_link.get_driver(use_ftdi, port, baud) as driver:
    # Handler with context
    with Handler(Framer(driver.read, driver.write)) as link:
      link.add_callback(serial_link.log_printer, SBP_MSG_LOG)
      link.add_callback(serial_link.printer, SBP_MSG_PRINT_DEP)

      # Tell Bootloader we want to write to the flash.
      with Bootloader(link) as piksi_bootloader:
        print "Waiting for bootloader handshake message from Piksi ...",
        sys.stdout.flush()
        try:
          handshake_received = piksi_bootloader.handshake(args.timeout[0])
        except KeyboardInterrupt:
          return
        if not (handshake_received and piksi_bootloader.handshake_received):
          print "No handshake received."
          sys.exit(1) 
        print "received."
        print "Piksi Onboard Bootloader Version:", piksi_bootloader.version
        if piksi_bootloader.sbp_version > (0, 0):
          print "Piksi Onboard SBP Protocol Version:", piksi_bootloader.sbp_version

        # Catch all other errors and exit cleanly.
        try:
          import flash
          with flash.Flash(link, flash_type=("STM" if use_stm else "M25"),
                           sbp_version=piksi_bootloader.sbp_version, max_queued_ops=int(args.max_queued_ops[0])) as piksi_flash:
            if erase:
              for s in range(1,12):
                print "\rErasing STM Sector", s,
                sys.stdout.flush()
                piksi_flash.erase_sector(s)
              print

            from intelhex import IntelHex
            ihx = IntelHex(args.file)
            piksi_flash.write_ihx(ihx, sys.stdout, mod_print=0x10)

            print "Bootloader jumping to application"
            piksi_bootloader.jump_to_app()
        except:
          import traceback
          traceback.print_exc()

if __name__ == "__main__":
  main()
