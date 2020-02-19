#!/usr/bin/env python
# Copyright (C) 2020 Swift Navigation Inc.
# Contact: Swift Navigation <dev@swiftnav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

import argparse
import os

from sbp.client.loggers.json_logger import JSONLogger, JSONLogIterator

def get_args():
    """
    Get and parse arguments.
    """
    parser = argparse.ArgumentParser(description='SBP JSON payload expander')

    parser.add_argument(
        'filename',
        help="The SBP log file to extract data from. Default format is sbp json")

    parser.add_argument(
        '-i',
        '--ignore',
        default=[],
        type=int,
        nargs='*',
        help="Filter message types")

    args = parser.parse_args()

    return args

def main():
    args = get_args()
    logger = JSONLogger(None)

    name, ext = os.path.splitext(args.filename)

    outfile = "{name}-expanded{ext}".format(name=name, ext=ext)

    with open(args.filename, 'r') as infile, open(outfile, 'w') as outfile:
        for (msg, meta) in JSONLogIterator(infile).__next__():

            if msg.msg_type in args.ignore:
                continue

            outfile.write(logger.dump(msg))
            outfile.write('\n')

if __name__ == '__main__':
    main()
