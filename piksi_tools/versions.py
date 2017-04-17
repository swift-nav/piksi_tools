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

import serial_link
import time
import struct
import json

from sbp.client.handler import *
from sbp.bootload       import *
from sbp.deprecated     import *
from sbp.piksi          import *
from sbp.system         import *

VERSIONS_FILENAME = "versions.json"

class Versions(object):
  """
  Versions
  The :class:`Versions` class collects devices versions.
  """
  def __init__(self, link):
    self.versions = {}
    self.handshake_received = False
    self.heartbeat_received = False
    self.link = link
    self.link.add_callback(self._deprecated_callback, SBP_MSG_BOOTLOADER_HANDSHAKE_DEPRECATED)
    self.link.add_callback(self._handshake_callback, SBP_MSG_BOOTLOADER_HANDSHAKE_DEVICE)
    self.link.add_callback(self._heartbeat_callback, SBP_MSG_HEARTBEAT)
    self.link.send(SBP_MSG_RESET, '')
    while not self.handshake_received or not self.heartbeat_received:
      time.sleep(0.1)

  def _deprecated_callback(self, sbp_msg):
    if len(sbp_msg.payload)==1 and struct.unpack('B', sbp_msg.payload[0]) == 0:
      self.versions['bootloader'] = "v0.1"
    else:
      self.versions['bootloader'] = sbp_msg.payload
    self.link.send(SBP_MSG_BOOTLOADER_JUMP_TO_APP, '\x00')
    self.handshake_received = True

  def _handshake_callback(self, sbp_msg):
    self.versions['bootloader'] = MsgBootloaderHandshakeDevice(sbp_msg).version
    self.link.send(SBP_MSG_BOOTLOADER_JUMP_TO_APP, '\x00')
    self.handshake_received = True

  def _heartbeat_callback(self, sbp_msg):
    self.versions['sbp'] = (MsgHeartbeat(sbp_msg).flags >> 8) & 0xFF
    self.heartbeat_received = True

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
  parser.add_argument("-o", "--versions-filename",
                      default=[VERSIONS_FILENAME], nargs=1,
                      help="file to write versions to.")
  return parser.parse_args()

def main():
  """
  Get configuration, get driver, and build handler and start it.
  """
  args = get_args()
  port = args.port[0]
  baud = args.baud[0]
  versions_filename = args.versions_filename[0]
  # Driver with context
  with serial_link.get_driver(args.ftdi, port, baud) as driver:
    with Handler(driver.read, driver.write) as link:
      versions = Versions(link).versions
      with open(versions_filename, 'w') as versions_file:
        json.dump(versions, versions_file, sort_keys=True, indent=2, separators=(',', ': '))

if __name__ == "__main__":
  main()
