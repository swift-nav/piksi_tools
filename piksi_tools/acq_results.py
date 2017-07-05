#!/usr/bin/env python
# Copyright (C) 2011-2014, 2016 Swift Navigation Inc.
# Contact: Colin Beighley <colin@swift-nav.com>
#          Pasi Miettinen <pasi.miettinen@exafore.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.
"""
The :mod:`piksi_tools.acq_results` module contains functions related to
monitoring acquisition.
"""
from __future__ import absolute_import, print_function

import time

from numpy import mean
from sbp.acquisition import SBP_MSG_ACQ_RESULT, MsgAcqResult, MsgAcqResultDepA
from sbp.client import Framer, Handler
from sbp.logging import SBP_MSG_LOG, SBP_MSG_PRINT_DEP

from . import serial_link

N_RECORD = 0  # Number of results to keep in memory, 0 = no limit.
N_PRINT = 32

SNR_THRESHOLD = 15


class AcqResults():
    """
    AcqResults

    The :class:`AcqResults` collects acquisition results.
    """

    def __init__(self, link):
        self.acqs = []
        self.link = link
        self.link.add_callback(self._receive_acq_result, SBP_MSG_ACQ_RESULT)
        self.max_corr = 0

    def __str__(self):
        tmp = "Last %d acquisitions:\n" % len(self.acqs[-N_PRINT:])
        for a in self.acqs[-N_PRINT:]:
            tmp += "PRN %2d, SNR: %3.2f\n" % (a.sid.sat, a.snr)
        tmp += "Max SNR         : %3.2f\n" % (self.max_snr())
        tmp += "Mean of max SNRs: %3.2f\n" % (
            self.mean_max_snrs(SNR_THRESHOLD))
        return tmp

    # Return the maximum SNR received.
    def max_snr(self):
        try:
            return max([a.snr for a in self.acqs])
        except (ValueError, KeyError):
            return 0

    # Return the mean of the max SNR (above snr_threshold) of each PRN.
    def mean_max_snrs(self, snr_threshold):
        snrs = []
        # Get the max SNR for each PRN.
        for prn in set([a.sid.sat for a in self.acqs]):
            acqs_prn = filter(lambda x: x.sid.sat == prn, self.acqs)
            acqs_prn_max_snr = max([a.snr for a in acqs_prn])
            if acqs_prn_max_snr >= snr_threshold:
                snrs += [max([a.snr for a in acqs_prn])]
        if snrs:
            return mean(snrs)
        else:
            return 0

    def _receive_acq_result(self, sbp_msg, **metadata):
        while N_RECORD > 0 and len(self.acqs) >= N_RECORD:
            self.acqs.pop(0)
        self.acqs.append(MsgAcqResult(sbp_msg))

    def _receive_acq_result_dep_a(self, sbp_msg, **metadata):
        while N_RECORD > 0 and len(self.acqs) >= N_RECORD:
            self.acqs.pop(0)
        self.acqs.append(MsgAcqResultDepA(sbp_msg))


def get_args():
    """
    Get and parse arguments.
    """
    import argparse
    parser = argparse.ArgumentParser(description='Acquisition Monitor')
    parser.add_argument(
        "-f",
        "--ftdi",
        help="use pylibftdi instead of pyserial.",
        action="store_true")
    parser.add_argument(
        '-p',
        '--port',
        default=[serial_link.SERIAL_PORT],
        nargs=1,
        help='specify the serial port to use.')
    parser.add_argument(
        "-b",
        "--baud",
        default=[serial_link.SERIAL_BAUD],
        nargs=1,
        help="specify the baud rate to use.")
    return parser.parse_args()


def main():
    """
    Get configuration, get driver, and build handler and start it.
    """
    args = get_args()
    port = args.port[0]
    baud = args.baud[0]
    use_ftdi = args.ftdi
    # Driver with context
    with serial_link.get_driver(use_ftdi, port, baud) as driver:
        # Handler with context
        with Handler(Framer(driver.read, driver.write)) as link:
            link.add_callback(serial_link.log_printer, SBP_MSG_LOG)
            link.add_callback(serial_link.printer, SBP_MSG_PRINT_DEP)
            acq_results = AcqResults(link)

            try:
                while True:
                    print(acq_results)
                    time.sleep(0.1)
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
