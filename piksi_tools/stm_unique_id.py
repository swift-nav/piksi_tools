#!/usr/bin/env python2
# Copyright (C) 2011-2014 Swift Navigation Inc.
# Contact: Colin Beighley <colin@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

import time
import struct
import sys
import serial_link

from sbp.flash          import SBP_MSG_STM_UNIQUE_ID_DEVICE
from sbp.client.handler import *

class STMUniqueID:

  def __init__(self, link, version):
    self.unique_id_returned = False
    self.unique_id = None
    self.link = link
    self.version = version
    link.add_callback(self.receive_stm_unique_id_callback, SBP_MSG_STM_UNIQUE_ID_DEVICE)

  def receive_stm_unique_id_callback(self,sbp_msg):
    self.unique_id_returned = True
    self.unique_id = struct.unpack('<12B',sbp_msg.payload)

  def get_id(self):
    self.unique_id_returned = False
    self.unique_id = None
    # < v2.0 of the bootloader, reuse single stm message.
    if self.version < "v2.0":
      self.link.send(SBP_MSG_STM_UNIQUE_ID_DEVICE, struct.pack("<I",0))
    else:
      self.link.send(SBP_MSG_STM_UNIQUE_ID_HOST, struct.pack("<I",0))
    while not self.unique_id_returned:
      time.sleep(0.1)
    return self.unique_id

def get_args():
  """
  Get and parse arguments.
  """
  import argparse
  parser = argparse.ArgumentParser(description='Acquisition Monitor')
  parser.add_argument("-f", "--ftdi",
                      help="use pylibftdi instead of pyserial.",
                      action="store_true")
  parser.add_argument('-p', '--port',
                      default=[serial_link.SERIAL_PORT], nargs=1,
                      help='specify the serial port to use.')
  parser.add_argument("-b", "--baud",
                      default=[serial_link.SERIAL_BAUD], nargs=1,
                      help="specify the baud rate to use.")
  parser.add_argument("-v", "--version",
                      default=[None], nargs=1,
                      help="bootloader version to use.")
  return parser.parse_args()

def main():
  """
  Get configuration, get driver, and build handler and start it.
  """
  args = get_args()
  port = args.port[0]
  baud = args.baud[0]
  version = args.version[0]
  # Driver with context
  with serial_link.get_driver(args.ftdi, port, baud) as driver:
    with Handler(driver.read, driver.write) as link:
      link.start()
      unique_id = STMUniqueID(link, version).get_id()
      print "STM Unique ID =", "0x" + ''.join(["%02x" % (b) for b in unique_id])

if __name__ == "__main__":
  main()
