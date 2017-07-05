#!/usr/bin/env python
# Copyright (C) 2015 Swift Navigation Inc.
# Contact: Dennis Zollo <dzollo@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

from __future__ import print_function

import argparse
import json
import sys

from piksi_tools.utils import wrap_sbp_dict


def get_args():
    parser = argparse.ArgumentParser(
        description="Swift Navigation JSON wrapper tool.")
    return parser.parse_args()


def main():
    """Simple command line interface for wrapping up the output of SBP2JSON"

    """
    index = 0
    timestamp = 0
    time_increment_guess = 10  # ms
    index_increment_guess = 10  # ms
    for line in sys.stdin:
        data = json.loads(line)
        outdata = wrap_sbp_dict(data, index, timestamp)
        print(json.dumps(outdata))
        index += index_increment_guess
        timestamp += time_increment_guess


if __name__ == "__main__":
    main()
