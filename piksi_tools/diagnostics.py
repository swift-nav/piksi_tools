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
import yaml

from sbp.client.handler import *
from sbp.bootload       import *
from sbp.deprecated     import *
from sbp.piksi          import *
from sbp.settings       import *
from sbp.system         import *

DIAGNOSTICS_FILENAME = "diagnostics.yaml"

class Diagnostics(object):
  """
  Diagnostics

  The :class:`Diagnostics` class collects devices diagnostics.
  """
  def __init__(self, link):
    self.diagnostics = {}
    self.diagnostics['versions'] = {}
    self.diagnostics['settings'] = {}
    self.settings_received = False
    self.heartbeat_received = False
    self.handshake_received = False
    self.link = link
    self.link.add_callback(self._settings_callback, SBP_MSG_SETTINGS_READ_BY_INDEX)
    self.link.add_callback(self._heartbeat_callback, SBP_MSG_HEARTBEAT)
    self.link.add_callback(self._deprecated_callback, SBP_MSG_BOOTLOADER_HANDSHAKE_DEPRECATED)
    self.link.add_callback(self._handshake_callback, SBP_MSG_BOOTLOADER_HANDSHAKE_RESPONSE)
    self.link.send_msg(MsgSettingsReadByIndex(index=0))
    while not self.settings_received or not self.heartbeat_received:
      time.sleep(0.1)
    expire = time.time() + 10.0
    self.link.send(SBP_MSG_RESET, '')
    while not self.handshake_received:
      time.sleep(0.1)
      if time.time() > expire:
        expire = time.time() + 10.0
        self.link.send(SBP_MSG_RESET, '')

  def _deprecated_callback(self, sbp_msg):
    if len(sbp_msg.payload)==1 and struct.unpack('B', sbp_msg.payload[0]) == 0:
      self.diagnostics['versions']['bootloader'] = "v0.1"
    else:
      self.diagnostics['versions']['bootloader'] = sbp_msg.payload
    self.handshake_received = True
    self.link.send(SBP_MSG_BOOTLOADER_JUMP_TO_APP, '\x00')

  def _handshake_callback(self, sbp_msg):
    self.diagnostics['versions']['bootloader'] = MsgBootloaderHandshakeDevice(sbp_msg).version
    self.handshake_received = True
    self.link.send(SBP_MSG_BOOTLOADER_JUMP_TO_APP, '\x00')

  def _heartbeat_callback(self, sbp_msg):
    self.diagnostics['versions']['sbp'] = (MsgHeartbeat(sbp_msg).flags >> 8) & 0xFF
    self.heartbeat_received = True

  def _settings_callback(self, sbp_msg):
    if not sbp_msg.payload:
      self.settings_received = True
    else:
      section, setting, value, format_type = sbp_msg.payload[2:].split('\0')[:4]
      if not self.diagnostics['settings'].has_key(section):
        self.diagnostics['settings'][section] = {}
      self.diagnostics['settings'][section][setting] = value
      index = struct.unpack('<H', sbp_msg.payload[:2])[0]
      self.link.send_msg(MsgSettingsReadByIndex(index=index+1))


def parse_device_details_yaml(device_details):
  """Parse from yaml string the device settings.

  """
  return yaml.load(device_details)['settings']['system_info']


def check_diagnostics(diagnostics_filename, version):
  """Check that Piksi's firmware/nap settings are properly set.

  Given a diagnostics_filename output and an expected firmware/NAP
  versions (via a Yaml string), returns True if expected fw/nap are
  properly loaded.

  """
  if version is None:
    raise Exception("Empty version string!")
  parsed = yaml.load(version)
  fw = parsed.get('fw', None)
  nap = parsed.get('hdl', None)
  with open(diagnostics_filename, 'r+') as f:
    details = parse_device_details_yaml(f.read())
    firmware_version = details.get('firmware_version', None)
    nap_version = details.get('nap_version', None)
    return (firmware_version and nap_version) \
        and (firmware_version == fw and nap_version == nap)


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
  parser.add_argument("-o", "--diagnostics-filename",
                      default=[DIAGNOSTICS_FILENAME], nargs=1,
                      help="file to write diagnostics to.")
  return parser.parse_args()

def main():
  """
  Get configuration, get driver, and build handler and start it.
  """
  args = get_args()
  port = args.port[0]
  baud = args.baud[0]
  diagnostics_filename = args.diagnostics_filename[0]
  # Driver with context
  with serial_link.get_driver(args.ftdi, port, baud) as driver:
    with Handler(driver.read, driver.write) as link:
      diagnostics = Diagnostics(link).diagnostics
      with open(diagnostics_filename, 'w') as diagnostics_file:
        yaml.dump(diagnostics, diagnostics_file, default_flow_style=False)

if __name__ == "__main__":
  main()
