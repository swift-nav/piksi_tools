#!/usr/bin/python
# Copyright (C) 2011-2014 Swift Navigation Inc.
# Contact: Colin Beighley <colin@swiftnav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

# Hack: Skip TestBootloader class if running in Travis-CI, as we need to
# be connected to a Piksi over a COM port.
import sys
import os
if os.environ.get('TRAVIS'):
  import pytest
  pytest.skip("Skipping TestBootloader, as we're running in Travis")

import unittest
import time

from intelhex import IntelHex

from sbp.system import SBP_MSG_HEARTBEAT
from sbp.client.handler import Handler
from sbp.piksi  import SBP_MSG_RESET

from piksi_tools import serial_link
from piksi_tools.flash import Flash
from piksi_tools.bootload import Bootloader
from piksi_tools.heartbeat import Heartbeat
from piksi_tools.utils import *
from piksi_tools.timeout import *

from piksi_tools.console.update_downloader import UpdateDownloader
from piksi_tools.console.settings_view import SettingsView


# VCP to communicate with Piksi Under Test.
PORT1 = None
# VCP to communicate with second Piksi connected via UART to Piksi Under Test.
PORT2 = None

# Level of verbosity in print output.
VERBOSE = False

# Firmware to use in tests.
STM_FW_URL = \
  "http://downloads.swiftnav.com/piksi_v2.3.1/stm_fw/piksi_firmware_v0.17.hex"
NAP_FW_URL = \
  "http://downloads.swiftnav.com/piksi_v2.3.1/nap_fw/swift_nap_v0.13.hex"
STM_FW = None
NAP_FW = None


class TestBootloader(unittest.TestCase):
  """
  Piksi bootloader tests. Tests assume that Piksies have a valid bootloader
  and STM / NAP firmware, such that it sends bootloader handshake messages and
  will enter bootloader mode upon receiving a bootloader handshake message,
  sends heartbeat messages, and can be reset through receiving a reset message.
  All tests should leave device in this state upon returning.
  """

  def __init__(self, testname):
    super(TestBootloader, self).__init__(testname)

  @classmethod
  def setUpClass(self):
    """ Do set up before running tests. """

    if VERBOSE: print "--- Setting up device for tests ---"

    with serial_link.get_driver(use_ftdi=False, port=PORT1) as driver:
      with Handler(driver.read, driver.write) as handler:
        setup_piksi(handler, STM_FW, NAP_FW, VERBOSE)

  def tearDown(self):
    """ Clean up after running each test. """
    # Hack: Wait a bit for 'Piksi Disconnected'
    # print from sbp.client.handler.Handler
    time.sleep(0.1)

  def _piksi_settings_cb(self):
    """ Callback to set flag indicating Piksi settings have been received. """
    self.settings_received = True

  def get_piksi_settings(self, handler):
    """
    Get settings from Piksi.

    Parameters
    ==========
    handler : sbp.client.handler.Handler
      Handler to send messages to Piksi over and register callbacks with.
    """

    self.settings_received = False

    with SettingsView(handler, read_finished_functions=[self._piksi_settings_cb],
                      gui_mode=False) as sv:
      with Timeout(TIMEOUT_READ_SETTINGS) as timeout:
        sv._settings_read_button_fired()
        while not self.settings_received:
          time.sleep(0.1)

    return sv.settings

  def test_get_versions(self):
    """ Get Piksi bootloader/firmware/NAP version from device. """

    if VERBOSE: print "--- test_get_versions ---"

    with serial_link.get_driver(use_ftdi=False, port=PORT1) as driver:
      with Handler(driver.read, driver.write) as handler:

        set_btldr_mode(handler, VERBOSE)

        with Bootloader(handler) as piksi_bootloader:

          # Get bootloader version, print, and jump to application firmware.
          with Timeout(TIMEOUT_BOOT) as timeout:
            if VERBOSE: print "Waiting for bootloader handshake"
            piksi_bootloader.wait_for_handshake()
          piksi_bootloader.reply_handshake()
          piksi_bootloader.jump_to_app()
          print "Piksi Bootloader Version:", piksi_bootloader.version

        # Wait for heartbeat, get settings, print firmware/NAP versions.
        heartbeat = Heartbeat()
        handler.add_callback(heartbeat, SBP_MSG_HEARTBEAT)
        if VERBOSE: print "Waiting to receive heartbeat"
        while not heartbeat.received:
          time.sleep(0.1)
        if VERBOSE: print "Received hearbeat"
        handler.remove_callback(heartbeat, SBP_MSG_HEARTBEAT)

        if VERBOSE: print "Getting Piksi settings"
        settings = self.get_piksi_settings(handler)

        if VERBOSE: print "Piksi Firmware Version:", \
                          settings['system_info']['firmware_version']

        if VERBOSE: print "Piksi NAP Version:", \
                          settings['system_info']['nap_version']

  def test_set_btldr_mode(self):
    """ Test setting Piksi into bootloader mode. """

    if VERBOSE: print "--- test_set_btldr_mode ---"

    with serial_link.get_driver(use_ftdi=False, port=PORT1) as driver:
      with Handler(driver.read, driver.write) as handler:

        set_btldr_mode(handler, VERBOSE)

        with Bootloader(handler) as piksi_bootloader:
          # If the Piksi bootloader successfully received our handshake, we
          # should be able to receive handshakes from it indefinitely. Test
          # this a few times.
          if VERBOSE: print "Testing bootloader handshake replies"
          for i in range(10):
            time.sleep(1)
            with Timeout(TIMEOUT_BOOT) as timeout:
              piksi_bootloader.wait_for_handshake()

  def test_flash_stm_firmware(self):
    """ Test flashing STM hexfile. """

    if VERBOSE: print "--- test_flash_stm_firmware ---"

    with serial_link.get_driver(use_ftdi=False, port=PORT1) as driver:
      with Handler(driver.read, driver.write) as handler:

        set_btldr_mode(handler, VERBOSE)

        with Bootloader(handler) as piksi_bootloader:
          with Timeout(TIMEOUT_BOOT) as timeout:
            if VERBOSE: print "Waiting for bootloader handshake"
            piksi_bootloader.wait_for_handshake()
          with Flash(handler, flash_type='STM',
                     sbp_version=piksi_bootloader.version) as piksi_flash:
            with Timeout(TIMEOUT_WRITE_STM) as timeout:
              if VERBOSE:
                print "Writing firmware to STM flash"
                piksi_flash.write_ihx(STM_FW, sys.stdout, mod_print=0x10)
              else:
                piksi_flash.write_ihx(STM_FW)

  def test_flash_nap_firmware(self):
    """ Test flashing NAP hexfile. """

    if VERBOSE: print "--- test_flash_nap_firmware ---"

    with serial_link.get_driver(use_ftdi=False, port=PORT1) as driver:
      with Handler(driver.read, driver.write) as handler:

        set_btldr_mode(handler, VERBOSE)

        with Bootloader(handler) as piksi_bootloader:
          with Timeout(TIMEOUT_BOOT) as timeout:
            if VERBOSE: print "Waiting for bootloader handshake"
            piksi_bootloader.wait_for_handshake()
          with Flash(handler, flash_type='M25',
                     sbp_version=piksi_bootloader.version) as piksi_flash:
            with Timeout(TIMEOUT_WRITE_NAP) as timeout:
              if VERBOSE:
                print "Writing firmware to NAP flash"
                piksi_flash.write_ihx(NAP_FW, sys.stdout, mod_print=0x10)
              else:
                piksi_flash.write_ihx(NAP_FW)

  def test_program_btldr(self):
    """ Test programming the bootloader once its sector is locked. """
    SECTOR = 0
    ADDRESS = 0x08003FFF

    if VERBOSE: print "--- test_program_btldr ---"

    with serial_link.get_driver(use_ftdi=False, port=PORT1) as driver:
      with Handler(driver.read, driver.write) as handler:

        set_btldr_mode(handler, VERBOSE)

        with Bootloader(handler) as piksi_bootloader:
          with Timeout(TIMEOUT_BOOT) as timeout:
            if VERBOSE: print "Waiting for bootloader handshake"
            piksi_bootloader.wait_for_handshake()
          with Flash(handler, flash_type='STM',
                     sbp_version=piksi_bootloader.version) as piksi_flash:
            # Make sure the bootloader sector is locked.
            with Timeout(TIMEOUT_LOCK_SECTOR) as timeout:
              if VERBOSE: print "Locking STM sector:", SECTOR
              piksi_flash.lock_sector(SECTOR)
            # Make sure the address to test isn't already programmed.
            with Timeout(TIMEOUT_READ_STM) as timeout:
              byte_read = piksi_flash.read(ADDRESS, 1, block=True)
            self.assertEqual('\xFF', byte_read,
                             "Address to program is already programmed")
            # Attempt to write 0x00 to last address of the sector.
            if VERBOSE: print "Attempting to lock STM sector:", SECTOR
            piksi_flash.program(0x08003FFF, '\x00')
            with Timeout(TIMEOUT_READ_STM) as timeout:
              byte_read = piksi_flash.read(0x08003FFF, 1, block=True)
            self.assertEqual('\xFF', byte_read,
                             "Bootloader sector was programmed")

  def test_erase_btldr(self):
    """ Test erasing the bootloader once its sector is locked. """
    SECTOR = 0

    if VERBOSE: print "--- test_erase_btldr ---"

    with serial_link.get_driver(use_ftdi=False, port=PORT1) as driver:
      with Handler(driver.read, driver.write) as handler:

        set_btldr_mode(handler, VERBOSE)

        with Bootloader(handler) as piksi_bootloader:
          with Timeout(TIMEOUT_BOOT) as timeout:
            if VERBOSE: print "Waiting for bootloader handshake"
            piksi_bootloader.wait_for_handshake()
          with Flash(handler, flash_type='STM',
                     sbp_version=piksi_bootloader.version) as piksi_flash:
            # Make sure the bootloader sector is locked.
            with Timeout(TIMEOUT_LOCK_SECTOR) as timeout:
              if VERBOSE: print "Locking STM sector:", SECTOR
              piksi_flash.lock_sector(SECTOR)
            # Attempt to erase the sector.
            with Timeout(TIMEOUT_ERASE_SECTOR) as timeout:
              if VERBOSE: print "Attempting to erase STM sector:", SECTOR
              piksi_flash.erase_sector(SECTOR, warn=False)
            # If the sector was successfully erased, we should timeout here
            # as the bootloader will stop sending handshakes.
            with Timeout(TIMEOUT_BOOT) as timeout:
              if VERBOSE: print "Waiting for bootloader handshake"
              piksi_bootloader.wait_for_handshake()

  def test_jump_to_app(self):
    """ Test that we can jump to the application after programming. """

    if VERBOSE: print "--- test_jump_to_app ---"

    with serial_link.get_driver(use_ftdi=False, port=PORT1) as driver:
      with Handler(driver.read, driver.write) as handler:

        set_btldr_mode(handler, VERBOSE)

        with Bootloader(handler) as piksi_bootloader:
          if VERBOSE: print "Jumping to application"
          piksi_bootloader.jump_to_app()

        # If we succesfully jump to the application, we should receive
        # Heartbeat messages.
        with Timeout(TIMEOUT_BOOT) as timeout:

          heartbeat = Heartbeat()
          handler.add_callback(heartbeat, SBP_MSG_HEARTBEAT)

          if VERBOSE: print "Waiting to receive heartbeat"
          while not heartbeat.received:
            time.sleep(0.1)
          if VERBOSE: print "Received hearbeat"

          handler.remove_callback(heartbeat, SBP_MSG_HEARTBEAT)

  @unittest.skip("Not implemented yet")
  def test_set_btldr_mode_wrong_sender_id(self):
    """
    Test setting Piksi into bootloader mode with an incorrect sender ID
    (should fail).
    """
    pass

  @unittest.skip("Not implemented yet")
  def test_flashing_wrong_sender_id(self):
    """ Test flashing using an incorrect sender ID (should fail). """
    pass

  @unittest.skip("Not implemented yet")
  def test_two_piksies_btldr_mode(self):
    """
    Test if two Piksies can set eachother into bootloader mode (should fail).
    """
    if PORT2 is None:
      return

  @unittest.skip("Not implemented yet")
  def test_two_piksies_simultaneous_bootloading(self):
    """ Test if two Piksies can simultaneously bootload. """
    if PORT2 is None:
      return

  @unittest.skip("Not implemented yet")
  def test_uart_rx_buffer_overflow(self):
    """
    Test if queuing too many operations causes a UART RX buffer overflow when
    another Piksi is sending data via another UART (should fail).
    """
    if PORT2 is None:
      return

  @unittest.skip("Not implemented yet")
  def test_packet_drop(self):
    """ test if flashing Piksi is redundant to SBP packet drops. """
    pass

  @unittest.skip("Not implemented yet")
  def test_sector_lock_unlock(self):
    """ Test if we can lock / unlock sectors. """
    pass

  @unittest.skip("Not implemented yet")
  def test_recover_from_reset(self):
    """ Test if we can recover from a reset while flashing. """
    pass

  @unittest.skip("Not implemented yet")
  def test_recover_from_abort(self):
    """
    Test if we can recover from aborting the bootloader script while flashing.
    """
    pass

  @unittest.skip("Not implemented yet")
  def test_invalid_firmware(self):
    """ Test writing an invalid firmware file and see if device will run it. """
    pass

def get_suite():
  """
  Build test suite for TestBootloader.
  """
  suite = unittest.TestSuite()

  suite.addTest(TestBootloader("test_get_versions"))
  suite.addTest(TestBootloader("test_set_btldr_mode"))
  suite.addTest(TestBootloader("test_flash_stm_firmware"))
  suite.addTest(TestBootloader("test_flash_nap_firmware"))
  suite.addTest(TestBootloader("test_program_btldr"))
  suite.addTest(TestBootloader("test_erase_btldr"))
  suite.addTest(TestBootloader("test_jump_to_app"))
  suite.addTest(TestBootloader("test_set_btldr_mode_wrong_sender_id"))
  suite.addTest(TestBootloader("test_flashing_wrong_sender_id"))
  suite.addTest(TestBootloader("test_two_piksies_btldr_mode"))
  suite.addTest(TestBootloader("test_two_piksies_simultaneous_bootloading"))
  suite.addTest(TestBootloader("test_uart_rx_buffer_overflow"))
  suite.addTest(TestBootloader("test_packet_drop"))
  suite.addTest(TestBootloader("test_sector_lock_unlock"))
  suite.addTest(TestBootloader("test_recover_from_reset"))
  suite.addTest(TestBootloader("test_recover_from_abort"))
  suite.addTest(TestBootloader("test_invalid_firmware"))

  return suite

def get_args():
  """
  Get and parse arguments.
  """
  import argparse
  parser = argparse.ArgumentParser(description='Piksi Bootloader Tester')
  parser.add_argument('-p1', '--port1', nargs=1,
                      default=[serial_link.SERIAL_PORT],
                      help='serial port for the Piksi Under Test')
  parser.add_argument("-p2", "--port2", nargs=1,
                      default=[None],
                      help="serial port for a Piksi whose UART is " \
                           "connected to the Piksi Under Test")
  parser.add_argument("-v", "--verbose",
                      default=False, action="store_true",
                      help="print more verbose output")
  parser.add_argument('unittest_args', nargs='*')
  return parser.parse_args()

def main():
  args = get_args()

  global PORT1
  global PORT2
  PORT1 = args.port1[0]
  PORT2 = args.port2[0]

  global VERBOSE
  VERBOSE = args.verbose

  # Download firmware for use in tests.
  global STM_FW
  global NAP_FW
  with Timeout(TIMEOUT_FW_DOWNLOAD) as timeout:
    update_downloader = UpdateDownloader()
    if VERBOSE: print "Downloading STM firmware"
    STM_FW = IntelHex(update_downloader._download_file_from_url(STM_FW_URL))
    if VERBOSE: print "Downloading NAP firmware"
    NAP_FW = IntelHex(update_downloader._download_file_from_url(NAP_FW_URL))
    if VERBOSE: print ""

   # Delete args used in main() before running unittests.
  sys.argv[1:] = args.unittest_args

  suite = get_suite()

  unittest.TextTestRunner().run(suite)

if __name__ == "__main__":
  main()
