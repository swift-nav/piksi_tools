from __future__ import absolute_import, print_function

import datetime
import os
import warnings

import pandas as pd
from pymavlink.DFReader import DFReader_binary

NUMLEAPSECONDS = 17


def extractMAVLINK(filename, outfile, msg_types_to_save):
    """
    From dataflash file save an HDF5 store of PANDAS dataframes for each msg

    Parameters
      ----------
      filename : str
        Name of the file to split.
      outfile: str
        Name of the output file
      msg_types_to_save: list
        list of string identifiers of Mavlink Messages to put in Pandas Frame
    """
    log = DFReader_binary(filename)
    last_m = None
    num_msgs = 0
    out_dict = {}
    first = True
    init_time = 0
    while True:
        # we use mavlinks recv_match function to iterate through logs
        m = log.recv_match(type=msg_types_to_save)
        if m:
            timestamp = m._timestamp
            if first:
                init_time = timestamp
            delta = timestamp - init_time
            dt = datetime.datetime.utcfromtimestamp(timestamp + NUMLEAPSECONDS)
            msg_timestamp_dict = out_dict.get(m.get_type(), {})
            msg_timestamp_dict[dt] = m.to_dict()
            out_dict[m.get_type()] = msg_timestamp_dict
        else:
            if os.path.exists(outfile):
                print("Unlinking %s, which already exists!" % outfile)
                os.unlink(outfile)
            f = pd.HDFStore(outfile, mode='w')
            try:
                tabs = [key for key in out_dict.iterkeys()]
                for tab in tabs:
                    attr = out_dict[tab]
                    f.put(tab, pd.DataFrame(attr))
                    if f.get(tab).empty:
                        warnings.warn('%s is empty.' % tab)
            finally:
                f.close()
            break


def get_args():
    """
    Get and parse arguments.

    """
    import argparse
    parser = argparse.ArgumentParser(description='Mavlink to Pandas table')
    parser.add_argument("dataflashfile", help="the dataflashfile to convert.")
    parser.add_argument(
        '-o',
        '--outfile',
        default=["mavlink_convert.hdf5"],
        nargs=1,
        help='specify the name of the file output.')
    parser.add_argument(
        '-t',
        '--types',
        default=['GPS', 'GPS2'],
        nargs='+',
        help='specify the mavlink messages to convert.')
    args = parser.parse_args()
    return args


def main():
    args = get_args()
    filename = args.dataflashfile
    outfile = args.outfile[0]
    if extractMAVLINK(filename, outfile, args.types):
        print("Mavlink log succesfully written to {0}.".format(outfile))


if __name__ == "__main__":
    main()
