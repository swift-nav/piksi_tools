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
import construct
from piksi_tools import __version__ as VERSION

base_class_slots = ['sender', 'length']
metadata_slots = ['time']


def get_list_of_columns(msgClass, metadata):
    if metadata:
        return (metadata_slots, base_class_slots, msgClass.__slots__)
    else:
        return ([], base_class_slots, msgClass.__slots__)


class MsgExtractor(object):
    def __init__(self, outfile, msgClass, metadata=False):
        self.msgClass = msgClass
        self.outfile = outfile
        self.metadata_columns, self.base_class_slots, self.msg_slots = get_list_of_columns(self.msgClass, metadata)
        columns = self.metadata_columns + self.base_class_slots + self.msg_slots
        headers = []
        for i, col in enumerate(columns):
            if col not in headers:
                headers.append(col)
            else:
                headers.append(col + str(headers.count(col)))
        print("selected columns are:\n    {}".format("\n    ".join(headers)))
        self.outfile.write(",".join(headers) + "\n")

    def _callback(self, msg, metadata):
        msg_object = self.msgClass(msg)
        outstringlist = []
        for each in self.metadata_columns:
            outstringlist.append("{0}".format(metadata.get(each)))
        for each in self.base_class_slots:
            outstringlist.append("{0}".format(getattr(msg, each)))
        for each in self.msg_slots:
            attr = getattr(msg_object, each)
            if isinstance(attr, construct.lib.ListContainer):
                for list_element in attr:
                    outstringlist.append("{0}".format(list_element))
            else:
                outstringlist.append("{0}".format(attr))
        self.outfile.write(",".join(outstringlist) + "\n")


def get_args():
    import argparse
    parser = argparse.ArgumentParser(
        description="sbp_msg_2_csv version " + VERSION + ". Writes SBP msg fields to a csv file, one column per field.")
    parser.add_argument("file",
                        help="specify the SBP JSON/binary file for which to dump fields to CSV.")
    parser.add_argument("-o", "--outfile", default="out",
                        help="Output .csv file postfix (.csv will be appended automatically)")
    parser.add_argument("-t", "--type", default=None,
                        help="Message Type to csvify (classname)")
    parser.add_argument("-i", "--id", default=None,
                        help="Message ID to csvify")
    parser.add_argument("-f", "--format", default="binary",
                        help="Input Format (bin or json)")
    return parser.parse_args()


def main():
    args = get_args()
    open_args = 'rb' if args.format == 'bin' else 'r'
    json = False
    with open(args.file, open_args) as fd:
        if args.format == 'json':
            json = True
            iterator = JSONLogIterator(fd, conventional=True)
        elif args.format == 'bin':
            driver = FileDriver(fd)
            iterator = Framer(driver.read, driver.write, dispatcher=None)
        else:
            raise Exception(
                "Usage Error: Unknown input format. Valid input formats for -f arg are bin and json.")
        msg_class = None
        msg_id = None
        for my_id, my_class in _SBP_TABLE.items():
            if my_class.__name__ == args.type or (args.id and my_id == int(args.id)):
                msg_class = my_class
                msg_id = my_id
        assert msg_class is not None, "Invalid message type specified"
        outfile = msg_class.__name__
        if args.outfile:
            outfile += "_" + args.outfile
        outfile += ".csv"
        print("Extracing class {} with msg_id {} to csv file {}".format(msg_class, msg_id, outfile))
        with open(outfile, 'w+') as outfp:
            conv = MsgExtractor(outfp, msg_class, metadata=json)
            while True:
                try:
                    msg, data = iterator.__next__()
                    if msg.msg_type == msg_id:
                        conv._callback(msg, data)
                    if msg is None:
                        break
                except StopIteration:
                    break


if __name__ == "__main__":
    main()
