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

import signal
import time

from piksi_tools.bootload import Bootloader
from piksi_tools.heartbeat import Heartbeat
from piksi_tools.flash import Flash

# Seconds to use for various timeouts.
TIMEOUT_FW_DOWNLOAD    = 30
TIMEOUT_BOOT           = 10
TIMEOUT_ERASE_STM      = 30
TIMEOUT_PROGRAM_STM    = 100
TIMEOUT_WRITE_STM      = TIMEOUT_ERASE_STM + TIMEOUT_PROGRAM_STM
TIMEOUT_WRITE_NAP      = 250
TIMEOUT_LOCK_SECTOR    = 5
TIMEOUT_READ_STM       = 5


def timeout_handler(signum, frame):
  raise Exception('Timeout handler called')

class Timeout(object):
  """
  Configurable timeout to raise an Exception after a certain number of seconds.

  Note: Will not work on Windows: uses SIGALRM.
  """

  def __init__(self, seconds):
    """
    Parameters
    ==========
    seconds : int
      Number of seconds before Exception is raised.
    """
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)

  def __enter__(self):
    return self

  def __exit__(self, *args):
    self.cancel()

  def cancel(self):
    """ Cancel scheduled Exception. """
    signal.alarm(0)


def setup_piksi(handler, stm_fw, nap_fw, verbose=False):
  """
  Set Piksi into a known state (STM / NAP firmware). Erases entire STM flash
  (except for bootloader sector). Requires Piksi have a valid STM firmware
  sending heartbeat messages and with the reset callback registered.

  Parameters
  ==========
  handler : sbp.client.handler.Handler
    handler to send/receive SBP messages to/from Piksi through.
  stm_fw : intelhex.IntelHex
    firmware to program Piksi STM with.
  nap_fw : intelhex.IntelHex
    firmware to program Piksi NAP with.
  verbose : bool
    Print more verbose output.

  """

  # Wait until we receive a heartbeat or bootloader handshake so we
  # know what state Piksi is in.
  with Bootloader(handler) as piksi_bootloader:

    with Heartbeat(handler) as heartbeat:
      # Throw an exception if a heartbeat or handshake
      # is not received for 5 seconds.
      with Timeout(TIMEOUT_BOOT) as timeout:
        if verbose: print "Waiting for Heartbeat or Bootloader Handshake"
        while not heartbeat.received and not piksi_bootloader.handshake_received:
          time.sleep(0.1)
      # If Piksi is in the application, reset it into the bootloader.
      if heartbeat.received:
        if verbose: print "Received Heartbeat, resetting Piksi"
        if verbose: print "Resetting Piksi"
        handler.send(SBP_MSG_RESET, "")

    with Timeout(TIMEOUT_BOOT) as timeout:
      piksi_bootloader.wait_for_handshake()
    piksi_bootloader.reply_handshake()
    bootloader_version = piksi_bootloader.version
    if verbose: print "Received bootloader handshake"

    with Flash(handler, flash_type="STM",
             sbp_version=piksi_bootloader.sbp_version) as piksi_flash:
      # Erase entire STM flash (except bootloader).
      if verbose: print "Erasing STM"
      with Timeout(TIMEOUT_ERASE_STM) as timeout:
        for s in range(1,12):
          piksi_flash.erase_sector(s)
      # Write STM firmware.
      if verbose: print "Programming STM"
      with Timeout(TIMEOUT_PROGRAM_STM) as timeout:
        piksi_flash.write_ihx(stm_fw, erase=False)

    with Flash(handler, flash_type="M25",
             sbp_version=piksi_bootloader.sbp_version) as piksi_flash:
      # Write NAP hexfile.
      if verbose: print "Programming NAP"
      with Timeout(TIMEOUT_WRITE_NAP) as timeout:
        piksi_flash.write_ihx(nap_fw)

    # Jump to the application firmware.
    if verbose: print "Jumping to application"
    piksi_bootloader.jump_to_app()

    if verbose: print ""

