#!/usr/bin/python

from unittest import TestCase
from intelhex import IntelHex

from piksi_tools import serial_link
from piksi_tools import flash
from piksi_tools.bootload import Bootloader

from sbp.piksi import SBP_MSG_RESET

# VCP to communicate with Piksi Under Test.
PORT1 = None
# VCP to communicate with second Piksi connected via UART to Piksi Under Test.
PORT2 = None

# Firmware to flash in tests.
STM_FW = IntelHex('piksi_firmware_v0.16.hex')
NAP_FW = IntelHex('swift_nap_v0.12.hex')

class TestBootloader(TestCase):
  """
  Piksi bootloader tests.
  """

  def setUp(self):
    """ Set Piksi into a known state (STM / NAP firmware) before each test. """
    with serial_link.get_driver(use_ftdi=False, port=PORT1) as driver:
      with Handler(driver.read, driver.write) as link:
        link.start()

        # Reset Piksi.
        link.send(SBP_MSG_RESET, "")
        time.sleep(0.2)

        with Bootloader(link) as piksi_bootloader:
          # Set Piksi into bootloader mode.
          piksi_bootloader.wait_for_handshake()
          piksi_bootloader.reply_handshake()

          with flash.Flash(link, flash_type="STM",
                           sbp_version=piksi_bootloader.sbp_version) as piksi_flash:
            # Erase entire STM flash (except bootloader).
            for s in range(1,12):
                sys.stdout.flush()
                piksi_flash.erase_sector(s)
            # Write STM firmware.
            piksi_flash.write_ihx(STM_FW, erase=False)

          with flash.Flash(link, flash_type="NAP",
                           sbp_version=piksi_bootloader.sbp_version) as piksi_flash:
            # Write NAP hexfile.
            piksi_flash.write_ihx(NAP_FW)

          # Jump to the application firmware.
          piksi_bootloader.jump_to_app()
          # Give Piksi time to start up and enter the application firmware.
          time.sleep(5)

  def set_into_btldr_mode(self, port):
    """
    Reset Piksi and handshake with bootloader.

    Parameters
    ==========
    port : string
      File name of virtual com port connected to Piksi UART.
    """
    with serial_link.get_driver(use_ftdi=False, port=PORT1) as driver:
      with Handler(driver.read, driver.write) as link:
        link.start()
        # Reset Piksi.
        link.send(SBP_MSG_RESET, "")
        with Bootloader(link) as piksi_bootloader:
          # Set Piksi into bootloader mode.
          handshake = piksi_bootloader.wait_for_handshake(timeout=5)
          self.assertTrue(handshake,
                          "Timeout while waiting for bootloader handshake")
          piksi_bootloader.reply_handshake()

  def test_set_btldr_mode(self):
    """ Test setting Piksi into bootloader mode. """
    self.set_into_btldr_mode(PORT1)
    with serial_link.get_driver(use_ftdi=False, port=PORT1) as driver:
      with Handler(driver.read, driver.write) as link:
        link.start()
        with Bootloader(link) as piksi_bootloader:
          # If the Piksi bootloader successfully received our handshake, we
          # should be receiving handshakes from it for a while.
          for i in range(10):
            time.sleep(1)
            handshake = piksi_bootloader.wait_for_handshake(timeout=2)
            self.assertTrue(handshake,
                            "Piksi did not stay in bootloader mode")

  def test_flash_stm_firmware(self):
    """ Test flashing STM hexfile. """
    self.set_into_btldr_mode(PORT1)
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
    self.set_into_btldr_mode(PORT1)
    with serial_link.get_driver(use_ftdi=False, port=PORT1) as driver:
      with Handler(driver.read, driver.write) as link:
        link.start()
        with Bootloader(link) as piksi_bootloader:
          piksi_bootloader.wait_for_handshake()
          with flash.Flash(link, flash_type='NAP', piksi_bootloader.version) \
              as piksi_flash:
            piksi_flash.write_ihx(NAP_FW)

  """ Test erasing the bootloader once it's sector is locked (should fail). """
  def test_erase_btldr(self):
    pass

  """
  Test setting Piksi into bootloader mode with an incorrect sender ID
  (should fail).
  """
  def test_set_btldr_mode_wrong_sender_id(self):
    pass

  """ Test flashing using an incorrect sender ID (should fail). """
  def test_flashing_wrong_sender_id(self):
    pass

  """
  Test if two Piksies can set eachother into bootloader mode (should fail).
  """
  def test_two_piksies_btldr_mode(self):
    if self.link2 == None:
      return

  """ Test if two Piksies can simultaneously bootload. """
  def test_two_piksies_simultaneous_bootloading(self):
    if self.link2 == None:
      return

  """
  Test if queuing too many operations causes a UART RX buffer overflow when
  another Piksi is sending data via another UART (should fail).
  """
  def test_uart_rx_buffer_overflow(self):
    if self.link2 == None:
      return

  """ Test if flashing Piksi is redundant to SBP packet drops. """
  def test_packet_drop(self):
    pass

  """ Test if we can lock / unlock sectors. """
  def test_sector_lock_unlock(self):
    pass

  """ Test if we can recover from a reset while flashing. """
  def test_recover_from_reset(self):
    pass

  """
  Test if we can recover from aborting the bootloader script while flashing.
  """
  def test_recover_from_abort(self):
    pass

  """ Test writing an invalid firmware file and see if device will run it. """
  def test_invalid_firmware(self):
    pass

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
                      help="serial port for the Piksi whose UART is " \
                           "connected to the Piksi Under Test")
  return parser.parse_args()

def main():
  args = get_args()

  global PORT1 = args.port1[0]
  global PORT2 = args.port2[0]

if __name__ == "__main__":
  main()
