"""
Takes in a dataflish BIN file and splits it into multiple files.
Intent is to split it  each time it is armed

Requirements:

  pip install pymavlink

"""
from __future__ import print_function

from pymavlink.DFReader import DFReader_binary


def split_logs(filename, seconds2split, prefix=None, verbose=False):
    """
    This splits an ArduPilot binary dataflash log into each flight segment

    Parameters
      ----------
      filename : str
        Name of the file to split.
      seconds2split: int
        number of seconds gap in the file which will cause a file split
    """
    log = DFReader_binary(filename)
    # save the ehader
    header = '\n'.join(log.data.split('\n', 10)[0:9]) + '\n'
    first = True
    previous_ts = 0
    starting_offset = 0
    part = 0
    if prefix:
        outfile = prefix + filename
    else:
        outfile = filename
    # receive messages and check for large gaps
    while True:
        m = log.recv_msg()
        # if m is none we hit the end of the file so we write out the last segment
        if m is None:
            with open(outfile + "." + str(part), 'w') as fd:
                fd.write(header + log.data[starting_offset:])
            print("split {0} into {1} segments".format(filename, part + 1))
            break
        elif not first:
            timediff = m._timestamp - previous_ts
            if timediff > seconds2split:
                if verbose:
                    print("Breaking at {0} for type{1}".format(
                        m._timestamp, m.get_type()))
                with open(outfile + "." + str(part), 'w') as fd:
                    before_message = log.offset - len(m.binary)
                    # if we are in the first message, no need to repeat the header
                    if part == 0:
                        fd.write(log.data[starting_offset:before_message])
                    # repeat the header for other segments
                    else:
                        fd.write(header +
                                 log.data[starting_offset:before_message])
                    starting_offset = before_message
                    part += 1
        else:
            first = False
        # each timestamp store the previous timestamp
        previous_ts = m._timestamp


def get_args():
    """
    Get and parse arguments.

    """
    import argparse
    parser = argparse.ArgumentParser(
        description='Mavlink to SBP JSON converter')
    parser.add_argument("dataflashfile", help="the dataflashfile to convert.")
    parser.add_argument(
        '-t',
        '--timestep',
        default=[10],
        nargs=1,
        help='number of seconds gap at which to split a file')
    parser.add_argument(
        '-p', '--prefix', default=[None], nargs=1, help='file prefix')
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="print extra debugging information.")
    args = parser.parse_args()
    return args


def main():
    args = get_args()
    filename = args.dataflashfile
    split_logs(filename, float(args.timestep[0]), args.prefix[0], args.verbose)
    return 0


if __name__ == "__main__":
    main()
