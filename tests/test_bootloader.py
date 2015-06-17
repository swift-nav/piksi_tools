#!/usr/bin/python

import unittest
import sys
import time

from intelhex import IntelHex

from piksi_tools import serial_link
from piksi_tools import flash
from piksi_tools.bootload import Bootloader
from piksi_tools.console.update_downloader import UpdateDownloader

from sbp.client.handler import Handler

from sbp.piksi  import SBP_MSG_RESET
from sbp.system import SBP_MSG_HEARTBEAT

# VCP to communicate with Piksi Under Test.
PORT1 = None
# VCP to communicate with second Piksi connected via UART to Piksi Under Test.
PORT2 = None

VERBOSE = False

# Firmware to flash in tests.
STM_FW_URL = \
  "http://downloads.swiftnav.com/piksi_v2.3.1/stm_fw/piksi_firmware_v0.17.hex"
NAP_FW_URL = \
  "http://downloads.swiftnav.com/piksi_v2.3.1/nap_fw/swift_nap_v0.13.hex"
STM_FW = None
NAP_FW = None

class Heartbeat():
  """
  Handle receiving heartbeat messages from Piksi. If we receive a heartbeat
  from Piksi, we know that Piksi is in the application firmware.
  """
  def __init__(self, link):
    self.received = False
    self.link = link
    self.link.add_callback(self.heartbeat_callback, SBP_MSG_HEARTBEAT)

  def __enter__(self):
    return self

  def __exit__(self, *args):
    self.link.remove_callback(self.heartbeat_callback, SBP_MSG_HEARTBEAT)

  def heartbeat_callback(self, sbp_msg):
    self.received = True

def set_known_state(port):
  """ Set Piksi into a known state (STM / NAP firmware). """
  if VERBOSE: print "Setting up Piksi at '%s' to known state" % port
  with serial_link.get_driver(use_ftdi=False, port=port) as driver:
    with Handler(driver.read, driver.write) as link:
      link.start()

      # Wait until we receive a heartbeat or bootloader handshake so we
      # know what state Piksi is in.
      if VERBOSE: print "  Waiting for Heartbeat or Bootloader Handshake"
      with Bootloader(link) as piksi_bootloader:
        with Heartbeat(link) as heartbeat:
          while not heartbeat.received and not piksi_bootloader.handshake_received:
            time.sleep(0.1)
          if VERBOSE: print "  Received Heartbeat or Bootloader Handshake"
          # If Piksi is in the application, reset it into the bootloader.
          if heartbeat.received:
            if VERBOSE: print "  Resetting Piksi"
            link.send(SBP_MSG_RESET, "")

      with Bootloader(link) as piksi_bootloader:
        # Set Piksi into bootloader mode.
        no_timeout = piksi_bootloader.wait_for_handshake(2)
        if not no_timeout:
          raise Exception('Timeout while waiting for bootloader handshake')
        piksi_bootloader.reply_handshake()
        if VERBOSE: print "  Received bootloader handshake"

        with flash.Flash(link, flash_type="STM",
                 sbp_version=piksi_bootloader.sbp_version) as piksi_flash:
          # Erase entire STM flash (except bootloader).
          if VERBOSE: print "  Erasing STM"
          for s in range(1,12):
            piksi_flash.erase_sector(s)
          # Write STM firmware.
          if VERBOSE: print "  Programming STM"
          piksi_flash.write_ihx(STM_FW, erase=False)

        with flash.Flash(link, flash_type="M25",
                 sbp_version=piksi_bootloader.sbp_version) as piksi_flash:
          # Write NAP hexfile.
          if VERBOSE: print "  Programming NAP"
          piksi_flash.write_ihx(NAP_FW)

        # Jump to the application firmware.
        if VERBOSE: print "  Jumping to application"
        piksi_bootloader.jump_to_app()

        if VERBOSE: print ""

class TestBootloader(unittest.TestCase):
  """
  Piksi bootloader tests.
  """

  @classmethod
  def setUpClass(self):
    """ Do set up before running tests. """
    set_known_state(PORT1)

  def set_btldr_mode(self, port):
    """
    Reset Piksi and handshake with bootloader.

    Parameters
    ==========
    port : string
      File name of virtual com port connected to Piksi UART.
    """
    with serial_link.get_driver(use_ftdi=False, port=port) as driver:
      with Handler(driver.read, driver.write) as link:
        link.start()

        # Wait until we receive a heartbeat or bootloader handshake so we
        # know what state Piksi is in.
        with Bootloader(link) as piksi_bootloader:
          with Heartbeat(link) as heartbeat:
            while not heartbeat.received and not piksi_bootloader.handshake_received:
              time.sleep(0.1)
            # If Piksi is in the application, reset it into the bootloader.
            if heartbeat.received:
              link.send(SBP_MSG_RESET, "")

        with Bootloader(link) as piksi_bootloader:
          # Set Piksi into bootloader mode.
          handshake = piksi_bootloader.wait_for_handshake(timeout=2)
          self.assertTrue(handshake,
                          "Timeout while waiting for bootloader handshake")
          piksi_bootloader.reply_handshake()

  def test_set_btldr_mode(self):
    """ Test setting Piksi into bootloader mode. """
    self.set_btldr_mode(PORT1)

    with serial_link.get_driver(use_ftdi=False, port=PORT1) as driver:
      with Handler(driver.read, driver.write) as link:
        link.start()
        with Bootloader(link) as piksi_bootloader:
          # If the Piksi bootloader successfully received our handshake, we
          # should be able to receive handshakes from it indefinitely.
          for i in range(10):
            time.sleep(1)
            handshake = piksi_bootloader.wait_for_handshake(timeout=2)
            self.assertTrue(handshake,
                            "Piksi did not stay in bootloader mode")

  def test_flash_stm_firmware(self):
    """ Test flashing STM hexfile. """
    self.set_btldr_mode(PORT1)

    with serial_link.get_driver(use_ftdi=False, port=PORT1) as driver:
      with Handler(driver.read, driver.write) as link:
        link.start()
        with Bootloader(link) as piksi_bootloader:
          piksi_bootloader.wait_for_handshake()
          with flash.Flash(link, flash_type='STM', piksi_bootloader.version) \
              as piksi_flash:
            piksi_flash.write_ihx(STM_FW)

  def test_flash_nap_firmware(self):
    """ Test flashing NAP hexfile. """
    self.set_btldr_mode(PORT1)

    with serial_link.get_driver(use_ftdi=False, port=PORT1) as driver:
      with Handler(driver.read, driver.write) as link:
        link.start()
        with Bootloader(link) as piksi_bootloader:
          piksi_bootloader.wait_for_handshake()
          with flash.Flash(link, flash_type='NAP', piksi_bootloader.version) \
              as piksi_flash:
            piksi_flash.write_ihx(NAP_FW)

#  def test_program_btldr(self):
#    """ Test programming the bootloader once its sector is locked. """
#    self.set_btldr_mode(PORT1)
#    with serial_link.get_driver(use_ftdi=False, port=PORT1) as driver:
#      with Handler(driver.read, driver.write) as link:
#        link.start()
#        with Bootloader(link) as piksi_bootloader:
#          piksi_bootloader.wait_for_handshake()
#          with flash.Flash(link, flash_type='STM', piksi_bootloader.version) \
#              as piksi_flash:
#            # Make sure the bootloader sector is locked.
#            piksi_flash.lock_sector(0)
#            # Make sure the address to test isn't already programmed.
#            piksi_flash.read(0x08003FFF, 1)
#            waiting_for_read = piksi_flash.get_n_queued_ops() > 0
#            while waiting_for_read:
#              waiting_for_read = piksi_flash.get_n_queued_ops() > 0
#            byte_read = piksi_flash._read_callback_ihx.gets(0x08003FFF, 1)
#            self.assertEqual('\xFF', byte_read,
#                             "Address to program is already programmed")
#            # Attempt to write 0x00 to last address of the sector.
#            piksi_flash.program(0x08003FFF, '\x00')
#            waiting_for_read = piksi_flash.get_n_queued_ops() > 0
#            while waiting_for_read:
#              waiting_for_read = piksi_flash.get_n_queued_ops() > 0
#            byte_read = piksi_flash._read_callback_ihx.gets(0x08003FFF, 1)
#            self.assertEqual('\xFF', byte_read,
#                             "Bootloader sector was programmed")
#
#  def test_erase_btldr(self):
#    """ Test erasing the bootloader once its sector is locked. """
#    pass
#
#  def test_set_btldr_mode_wrong_sender_id(self):
#    """
#    Test setting Piksi into bootloader mode with an incorrect sender ID
#    (should fail).
#    """
#    pass
#
#  """ Test flashing using an incorrect sender ID (should fail). """
#  def test_flashing_wrong_sender_id(self):
#    pass
#
#  """
#  Test if two Piksies can set eachother into bootloader mode (should fail).
#  """
#  def test_two_piksies_btldr_mode(self):
#    if self.link2 == None:
#      return
#
#  """ Test if two Piksies can simultaneously bootload. """
#  def test_two_piksies_simultaneous_bootloading(self):
#    if self.link2 == None:
#      return
#
#  """
#  Test if queuing too many operations causes a UART RX buffer overflow when
#  another Piksi is sending data via another UART (should fail).
#  """
#  def test_uart_rx_buffer_overflow(self):
#    if self.link2 == None:
#      return
#
#  """ Test if flashing Piksi is redundant to SBP packet drops. """
#  def test_packet_drop(self):
#    pass
#
#  """ Test if we can lock / unlock sectors. """
#  def test_sector_lock_unlock(self):
#    pass
#
#  """ Test if we can recover from a reset while flashing. """
#  def test_recover_from_reset(self):
#    pass
#
#  """
#  Test if we can recover from aborting the bootloader script while flashing.
#  """
#  def test_recover_from_abort(self):
#    pass
#
#  """ Test writing an invalid firmware file and see if device will run it. """
#  def test_invalid_firmware(self):
#    pass

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

  global STM_FW
  global NAP_FW
  update_downloader = UpdateDownloader()
  if VERBOSE: print "Downloading STM firmware"
  STM_FW = IntelHex(update_downloader._download_file_from_url(STM_FW_URL))
  if VERBOSE: print "Downloading NAP firmware"
  NAP_FW = IntelHex(update_downloader._download_file_from_url(NAP_FW_URL))
  if VERBOSE: print ""

   # Delete args used in main() before calling unittest.main()
  sys.argv[1:] = args.unittest_args

  unittest.main()

if __name__ == "__main__":
  main()
