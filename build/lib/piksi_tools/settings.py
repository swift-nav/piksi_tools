#!/usr/bin/env python
# Copyright (C) 2016 Swift Navigation Inc.
# Contact: Leith Bade <leith@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

import serial_link
import struct
import time
import yaml
import sys

from sbp.bootload       import *
from sbp.client         import Handler, Framer
from sbp.piksi          import *
from sbp.settings       import *
from sbp.system         import *
from sbp.logging        import *

class Settings(object):
  """
  Settings

  The :class:`Settings` class retrieves and sends settings.
  """
  def __init__(self, link):
    self.link = link
    self.settings_list = {}
    self.settings_list_received = False
    self.setting_value = {}
    self.setting_received = False
    self.link.add_callback(self._settings_callback,
                           SBP_MSG_SETTINGS_READ_RESP)
    self.link.add_callback(self._settings_list_callback,
                           SBP_MSG_SETTINGS_READ_BY_INDEX_RESP)
    self.link.add_callback(self._settings_done_callback,
                           SBP_MSG_SETTINGS_READ_BY_INDEX_DONE)
    self.link.add_callback(self._print_callback,
                           SBP_MSG_LOG)

  def read_all(self):
    self.settings_list_received = False
    self.link(MsgSettingsReadByIndexReq(index=0))
    while not self.settings_list_received:
      time.sleep(0.1)
    for section in self.settings_list:
        print '%s:' % (section)
        for setting, value in self.settings_list[section].iteritems():
            print '- %s = %s' % (setting, value)

  def read(self, section, setting):
    self.setting_received = False
    self.link(MsgSettingsReadReq(setting='%s\0%s\0' % (section, setting)))
    while not self.setting_received:
      time.sleep(0.1)
    print self.setting_value

  def write(self, section, setting, value):
    self.link(MsgSettingsWrite(setting='%s\0%s\0%s\0' % (section, setting, value)))

  def save(self):
    self.link(MsgSettingsSave())

  def reset(self):
    self.link(MsgReset())

  def _print_callback(self, msg, **metadata):
    print msg.text

  def _settings_callback(self, sbp_msg, **metadata):
    section, setting, value, format_type = sbp_msg.payload[2:].split('\0')[:4]
    self.setting_value = value
    self.setting_received = True

  def _settings_list_callback(self, sbp_msg, **metadata):
    section, setting, value, format_type = sbp_msg.payload[2:].split('\0')[:4]
    if not self.settings_list.has_key(section):
      self.settings_list[section] = {}
    self.settings_list[section][setting] = value
    index = struct.unpack('<H', sbp_msg.payload[:2])[0]
    self.link(MsgSettingsReadByIndexReq(index=index+1))

  def _settings_done_callback(self, sbp_msg, **metadata):
    self.settings_list_received = True

def get_args():
  """
  Get and parse arguments.
  """
  import argparse
  parser = argparse.ArgumentParser(description='Piksi Settings Tool')
  parser.add_argument("-f", "--ftdi",
                      help="use pylibftdi instead of pyserial.",
                      action="store_true")
  parser.add_argument('-p', '--port',
                      default=[serial_link.SERIAL_PORT], nargs=1,
                      help='specify the serial port to use.')
  parser.add_argument("-b", "--baud",
                      default=[serial_link.SERIAL_BAUD], nargs=1,
                      help="specify the baud rate to use.")

  subparsers = parser.add_subparsers(dest="command")
  save = subparsers.add_parser('save',
                      help='save all the current settings to flash.')

  reset = subparsers.add_parser('reset',
                      help='reset the device after the action.')

  read = subparsers.add_parser('read',
                      help='read the current setting.')
  read.add_argument("section",
                      help="the setting section.")
  read.add_argument("setting",
                      help="the setting name.")

  read_all = subparsers.add_parser('all',
                      help='read all the settings.')

  write = subparsers.add_parser('write',
                      help='write the current setting.')
  write.add_argument("section",
                      help="the setting section.")
  write.add_argument("setting",
                      help="the setting name.")
  write.add_argument("value",
                      help="the setting value.")

  return parser.parse_args()

def main():
  """
  Get configuration, get driver, and build handler and start it.
  """
  args = get_args()
  port = args.port[0]
  baud = args.baud[0]
  command = args.command

  with serial_link.get_driver(args.ftdi, port, baud) as driver:
    with Handler(Framer(driver.read, driver.write)) as link:
      settings = Settings(link)
      if command == 'write':
        settings.write(args.section, args.setting, args.value)
      elif command == 'read':
        settings.read(args.section, args.setting)
      elif command == 'all':
        settings.read_all()
      elif command == 'save':
        settings.save()
      elif command == 'reset':
        settings.reset()
      # Wait a few seconds for any relevant print messages
      settings.link.wait(MsgLog, 8)

if __name__ == "__main__":
  main()
