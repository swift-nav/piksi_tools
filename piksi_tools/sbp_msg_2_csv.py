#!/usr/bin/env python2.7
# Copyright (C) 2015 Swift Navigation Inc.
# Contact: Dennis Zollo <dzollo@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

from sbp.client.loggers.json_logger import JSONLogIterator
from sbp.client import Framer
from sbp.client.drivers.file_driver import FileDriver
from sbp.table import _SBP_TABLE


def get_list_of_columns(msgClass, metadata):
    if metadata:
        return ['time'] + msgClass.__slots__
    else:
        return msgClass.__slots__


class MsgExtractor(object):
    def __init__(self, outfile, msgclass, metadata=False):
        self.outfile = outfile
        self.columns = get_list_of_columns(msgclass, metadata)
        print("selected columns are: {}".format("\n    ".join(self.columns)))
        self.outfile.write(",".join(self.columns) + "\n")

    def _callback(self, msg, data):
        for each in self.columns:
            try:
                self.outfile.write("{0},".format(getattr(msg, each)))
            except AttributeError:
                print(data)
                self.outfile.write("{0},".format(data[each]))
        self.outfile.write("\n")


def get_args():
    import argparse
    parser = argparse.ArgumentParser(
        description="write msg fields to a csv file, one column per field")
    parser.add_argument("file",
                        help="specify the SBP JSON/binary file for which to dump fields to CSV.")
    parser.add_argument("-o", "--outfile", default="out.csv",
                        help="Output .csv file postfix")
    parser.add_argument("-t", "--type", default="MsgBaselineNED",
                        help="Message Type to csvify (classname)")
    parser.add_argument("-i", "--id", default=None,
                        help="Message ID to csvify")
    parser.add_argument("-f", "--format", default="binary",
                        help="Input Format (bin or json)")
    return parser.parse_args()


def main():
    args = get_args()
    open_args = 'rb' if args.format == 'bin' else 'r'
    with open(args.file, open_args) as fd:
        if args.format == 'json':
            iterator = JSONLogIterator(fd)
        elif args.format == 'bin':
            driver = FileDriver(fd)
            iterator = Framer(driver.read, driver.write)
        else:
            raise Exception(
                "Usage Error: Unknown input format. Valid input formats for -f arg are bin and json.")
        with open(args.type + "_" + args.outfile, 'w+') as outfile:
            msg_class = None
            for my_id, my_class in _SBP_TABLE.iteritems():
                if my_class.__name__ == args.type or (args.id and my_id == args.id):
                    print("Extracing class {} with msg_id {}".format(my_class, my_id))
                    msg_class = my_class
            assert msg_class is not None, "Invalid message type specified"
            conv = MsgExtractor(outfile, msg_class, metadata=(args.format == 'json'))
            if args.format == 'json':
                iterator = iterator.next()
            while True:
                try:
                    (msg, data) = iterator.next()
                    if isinstance(msg, msg_class):
                        conv._callback(msg, data)
                except StopIteration:
                    break


if __name__ == "__main__":
    main()
