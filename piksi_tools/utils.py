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

import sys
import time

from piksi_tools.bootload import Bootloader
from piksi_tools.flash import Flash
from piksi_tools.timeout import *
from piksi_tools.heartbeat import Heartbeat
from sbp.system import SBP_MSG_HEARTBEAT
from sbp.piksi import SBP_MSG_RESET

def set_app_mode(handler, verbose=False):
  """
  Set Piksi into the application firmware, regardless of whether it is
  currently in the application firmware or the bootloader. Will raise a
  piksi_tools.timeout.TimeoutError if Piksi responses appear to have hung.

  Parameters
  ==========
  handler : sbp.client.handler.Handler
    handler to send/receive messages from/to Piksi.
  verbose : bool
    Print more verbose output.

  """

  if verbose: print "Setting device into application mode"

  # Wait until we receive a heartbeat or bootloader handshake so we
  # know what state Piksi is in.
  with Bootloader(handler) as piksi_bootloader:

    heartbeat = Heartbeat()
    handler.add_callback(heartbeat, SBP_MSG_HEARTBEAT)

    if verbose: print "Waiting for bootloader handshake or heartbeat from device"
    with Timeout(TIMEOUT_BOOT) as timeout:
      while not heartbeat.received and not piksi_bootloader.handshake_received:
        time.sleep(0.1)

    handler.remove_callback(heartbeat, SBP_MSG_HEARTBEAT)

    # If Piksi is in the application, simply return.
    if heartbeat.received:
      if verbose: print "Received heartbeat"
      return

    # Piksi is in the bootloader, tell Piksi to jump into the application.
    with Timeout(TIMEOUT_BOOT) as timeout:
      if verbose: print "Waiting for bootloader handshake from device"
      piksi_bootloader.wait_for_handshake()
    piksi_bootloader.jump_to_app()
    if verbose: print "Received handshake"
    if verbose: print "Telling device to jump to application"

    # Wait for Heartbeat to ensure we're in the application firmware.
    heartbeat = Heartbeat()
    handler.add_callback(heartbeat, SBP_MSG_HEARTBEAT)

    if verbose: print "Waiting for heartbeat"
    with Timeout(TIMEOUT_BOOT) as timeout:
      while not heartbeat.received:
        time.sleep(0.1)
    if verbose: print "Received heartbeat"

    handler.remove_callback(heartbeat, SBP_MSG_HEARTBEAT)

def set_btldr_mode(handler, verbose=False):
  """
  Reset Piksi (if necessary) and handshake with bootloader. Will raise a
  piksi_tools.timeout.TimeoutError if Piksi responses appear to have hung.

  Parameters
  ==========
  handler : sbp.client.handler.Handler
    handler to send/receive messages from/to Piksi.
  verbose : bool
    Print more verbose output.

  """

  if verbose: print "Setting device into bootloader mode"

  # Wait until we receive a heartbeat or bootloader handshake so we
  # know what state Piksi is in.
  with Bootloader(handler) as piksi_bootloader:

    heartbeat = Heartbeat()
    handler.add_callback(heartbeat, SBP_MSG_HEARTBEAT)

    if verbose: print "Waiting for bootloader handshake or heartbeat from device"
    with Timeout(TIMEOUT_BOOT) as timeout:
      while not heartbeat.received and not piksi_bootloader.handshake_received:
        time.sleep(0.1)
      if verbose: print "Received bootloader handshake or heartbeat"
    # If Piksi is in the application, reset it into the bootloader.
    if heartbeat.received:
      if verbose: print "Sending reset"
      handler.send(SBP_MSG_RESET, "")

    handler.remove_callback(heartbeat, SBP_MSG_HEARTBEAT)

    # Set Piksi into bootloader mode.
    with Timeout(TIMEOUT_BOOT) as timeout:
      if verbose: print "Waiting for bootloader handshake from device"
      piksi_bootloader.wait_for_handshake()
    piksi_bootloader.reply_handshake()
    if verbose: print "Replying to bootloader handshake"

def setup_piksi(handler, stm_fw, nap_fw, verbose=False):
  """
  Set Piksi into a known state (STM / NAP firmware). Erases entire STM flash
  (except for bootloader sector). Requires Piksi have a valid STM firmware
  sending heartbeat messages and with the reset callback registered. Will raise
  a timeout.TimeoutError if Piksi responses appear to have hung.

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

    heartbeat = Heartbeat()
    handler.add_callback(heartbeat, SBP_MSG_HEARTBEAT)

    # Throw an exception if a heartbeat or handshake
    # is not received for 5 seconds.
    with Timeout(TIMEOUT_BOOT) as timeout:
      if verbose: print "Waiting for Heartbeat or Bootloader Handshake"
      while not heartbeat.received and not piksi_bootloader.handshake_received:
        time.sleep(0.1)
    # If Piksi is in the application, reset it into the bootloader.
    if heartbeat.received:
      if verbose: print "Received Heartbeat, resetting Piksi"
      handler.send(SBP_MSG_RESET, "")

    handler.remove_callback(heartbeat, SBP_MSG_HEARTBEAT)

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
      with Timeout(TIMEOUT_PROGRAM_STM) as timeout:
        if verbose:
          if verbose: print "Programming STM"
          piksi_flash.write_ihx(stm_fw, sys.stdout, 0x10, erase=False)
        else:
          piksi_flash.write_ihx(stm_fw, sys.stdout, 0x10, erase=False)

    with Flash(handler, flash_type="M25",
             sbp_version=piksi_bootloader.sbp_version) as piksi_flash:
      # Write NAP hexfile.
      with Timeout(TIMEOUT_WRITE_NAP) as timeout:
        if verbose:
          if verbose: print "Programming NAP"
          piksi_flash.write_ihx(nap_fw, sys.stdout, 0x10)
        else:
          piksi_flash.write_ihx(nap_fw, sys.stdout, 0x10)

    # Jump to the application firmware.
    if verbose: print "Jumping to application"
    piksi_bootloader.jump_to_app()

