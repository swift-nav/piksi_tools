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

import time
import struct
import sys
import serial_link

from sbp.flash          import *
from sbp.system         import *
from sbp.client.handler import *

class STMUniqueID:

  def __init__(self, link):
    self.heartbeat_received = False
    self.unique_id_returned = False
    # SBP version is unset in older devices.
    self.sbp_version = (0, 0)
    self.unique_id = None
    self.link = link
    link.add_callback(self.receive_heartbeat, SBP_MSG_HEARTBEAT)
    link.add_callback(self.receive_stm_unique_id_callback, SBP_MSG_STM_UNIQUE_ID_RESP)

  def receive_heartbeat(self, sbp_msg):
    msg = MsgHeartbeat(sbp_msg)
    self.sbp_version = ((msg.flags >> 16) & 0xFF, (msg.flags >> 8) & 0xFF)
    self.heartbeat_received = True

  def receive_stm_unique_id_callback(self,sbp_msg):
    self.unique_id = struct.unpack('<12B',sbp_msg.payload)
    self.unique_id_returned = True

  def get_id(self):
    while not self.heartbeat_received:
      time.sleep(0.1)
    self.unique_id_returned = False
    self.unique_id = None
    # < 0.45 of the bootloader, reuse single stm message.
    if self.sbp_version < (0, 45):
      self.link.send(SBP_MSG_STM_UNIQUE_ID_RESP, struct.pack("<I",0))
    else:
      self.link.send(SBP_MSG_STM_UNIQUE_ID_REQ, struct.pack("<I",0))
    while not self.unique_id_returned:
      time.sleep(0.1)
    return self.unique_id

  def __enter__(self):
    return self

  def __exit__(self, *args):
    self.link.remove_callback(self.receive_heartbeat, SBP_MSG_HEARTBEAT)
    self.link.remove_callback(self.receive_stm_unique_id_callback, SBP_MSG_STM_UNIQUE_ID_RESP)


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
    with Handler(driver.read, driver.write) as link:
      unique_id = STMUniqueID(link).get_id()
      print "STM Unique ID =", "0x" + ''.join(["%02x" % (b) for b in unique_id])

if __name__ == "__main__":
  main()
