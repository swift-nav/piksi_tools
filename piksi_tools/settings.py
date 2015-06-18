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
from sbp.settings       import *
from sbp.msg            import *
from sbp.logging        import SBP_MSG_PRINT

SETTINGS_FILENAME = "settings.json"

class Settings(object):
  """
  Settings

  The :class:`Settings` class collects devices settings.
  """
  def __init__(self, link):
    self.settings = {}
    self.settings_received = False
    self.link = link
    self.link.add_callback(self._read_callback, SBP_MSG_SETTINGS_READ_BY_INDEX)
    self.link.send_msg(MsgSettingsReadByIndex(index=0))
    while not self.settings_received:
      time.sleep(0.1)

  def _read_callback(self, sbp_msg):
    if not sbp_msg.payload:
      self.settings_received = True
    else:
      section, setting, value, format_type = sbp_msg.payload[2:].split('\0')[:4]
      if not self.settings.has_key(section):
        self.settings[section] = {}
      self.settings[section][setting] = value

      index = struct.unpack('<H', sbp_msg.payload[:2])[0]
      self.link.send_msg(MsgSettingsReadByIndex(index=index+1))

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
  parser.add_argument("-o", "--settings-filename",
                      default=[SETTINGS_FILENAME], nargs=1,
                      help="file to write settings to.")
  return parser.parse_args()

def main():
  """
  Get configuration, get driver, and build handler and start it.
  """
  args = get_args()
  port = args.port[0]
  baud = args.baud[0]
  settings_filename = args.settings_filename[0]
  # Driver with context
  with serial_link.get_driver(args.ftdi, port, baud) as driver:
    with Handler(driver.read, driver.write) as link:
      settings = Settings(link).settings
      with open(settings_filename, 'w') as settings_file:
        json.dump(settings, settings_file, sort_keys=True, indent=2, separators=(',', ': '))

if __name__ == "__main__":
  main()
