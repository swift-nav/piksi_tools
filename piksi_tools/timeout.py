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

# Seconds to use for various timeouts.
TIMEOUT_FW_DOWNLOAD = 30
TIMEOUT_BOOT = 30
TIMEOUT_ERASE_STM = 30
TIMEOUT_PROGRAM_STM = 100
TIMEOUT_WRITE_STM = TIMEOUT_ERASE_STM + TIMEOUT_PROGRAM_STM
TIMEOUT_WRITE_NAP = 250
TIMEOUT_LOCK_SECTOR = 5
TIMEOUT_READ_STM = 5
TIMEOUT_READ_M25 = 5
TIMEOUT_WRITE_M25 = 5
TIMEOUT_ERASE_SECTOR = 5
TIMEOUT_READ_SETTINGS = 10
TIMEOUT_READ_DNA = 5
TIMEOUT_CREATE_LINK = 5
TIMEOUT_GET_UNIQUE_ID = 5
TIMEOUT_WRITE_M25_STATUS = 5


class TimeoutError(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutError


class Timeout(object):
    """
    Configurable timeout to raise an Exception after a certain number of
    seconds.

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
        self.seconds = seconds

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.cancel()

    def start(self):
        signal.alarm(self.seconds)

    def cancel(self):
        """ Cancel scheduled Exception. """
        signal.alarm(0)
