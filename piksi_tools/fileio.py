#!/usr/bin/env python
# Copyright (C) 2014 Swift Navigation Inc.
# Contact: Gareth McMullin <gareth@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

from __future__ import absolute_import, print_function
from future.builtins import bytes  # makes python 2 bytes more similar to python 3

import copy
import itertools
import random
import time
import threading
import sys

from sbp.client import Framer, Handler
from sbp.file_io import (SBP_MSG_FILEIO_READ_DIR_RESP,
                         SBP_MSG_FILEIO_READ_RESP, SBP_MSG_FILEIO_WRITE_RESP,
                         MsgFileioReadDirReq, MsgFileioReadDirResp,
                         MsgFileioReadReq, MsgFileioRemove, MsgFileioWriteReq)

from piksi_tools import serial_link

MAX_PAYLOAD_SIZE = 255
SBP_FILEIO_WINDOW_SIZE = 100
SBP_FILEIO_TIMEOUT = 5.0
MINIMUM_RETRIES = 3
PROGRESS_CB_REDUCTION_FACTOR = 100
TEXT_ENCODING = 'utf-8'  # used for printing out directory listings and files


class PendingWrite(object):
    """
    Represents a write that is spending.

    Fields
    ----------
    message : MsgFileioWriteReq
      The write request that's pending
    time : float (seconds from epoch)
      The time the message was sent (or re-sent at)
    tries : int
      The number of times we've attemptted to send the write message
    complete : bool
      If the message is complete
    """

    __slots__ = ["message", "time", "tries", "complete"]

    def invalidate(self):
        """
        Mark the data in the object invalid.

        Data here is set such that operations on the `time` and `tries` fields
        will succeed even if the object is invalidated.  The methods
        `_write_cb` and `_return_pending_write` can race on individual fields
        in the object.

        The field `self.message` is not cleared so that it can still be
        referenced in `_write_cb`.

        The result of this racy-ness is that the time-out check is not entirely
        consistent.  Occasionally, a message may be retried even if it was
        completed and we may decide that a file-transfer has timed out if the
        write completion event and the pending check occur around the same
        time.
        """
        self.complete = None
        self.tries = 0
        return self

    def is_pending(self):
        """
        Return true if this object is still pending.
        """
        if self.complete is None:
            return False
        if self.complete:
            return False
        return True

    def track(self, pending_write, time, tries=0, complete=False):
        """
        Load information about the pending write so that it can be tracked.
        """
        self.message = pending_write
        self.time = time
        self.tries = 0
        self.complete = complete
        return self

    def record_retry(self, retry_time):
        """
        Record a retry event, indicates that the SelectiveRepeater decided to
        retry sending the tracked MsgFileioWriteReq message.
        """
        self.tries += 1
        self.time = retry_time
        return self


class SelectiveRepeater(object):
    """Selective repeater for SBP file transfers"""

    def __init__(self, link, msg_type, cb=None):
        self.write_pool = [PendingWrite() for X in range(SBP_FILEIO_WINDOW_SIZE)]
        self.pending = []
        self.link = link
        self.msg_type = msg_type
        self.cb = cb
        self.cb_thread = None
        self.link_thread = None

    def _verify_cb_thread(self):
        """
        Verify that the same (singular) thread is accessing the `self.pending`
        and the `self.write_pool` lists.  Only the cb thread should free window
        space by removing (popping) from `self.pending` and appending it to the
        `self.write_pool` list.
        """
        if self.cb_thread is None:
            self.cb_thread = threading.currentThread().ident
        assert self.cb_thread == threading.currentThread().ident

    def _verify_link_thread(self):
        """
        Verify that the same (singular) thread is accessing the `self.pending`
        and the `self.write_pool` lists.  Only the link thread should consume
        window by removing a PendingWrite object from the `self.write_pool`
        list and appending it to the `self.pending` list.
        """
        if self.link_thread is None:
            self.link_thread = threading.currentThread().ident
        assert self.link_thread == threading.currentThread().ident

    def _return_pending_write(self, pending_write):
        """
        Increases the count of available pending writes by move a PendingWrite
        object from `self.pending` to `self.write_pool`.

        Threading: only the callback thread should access this function.  The
        cb thread is the consumer of `self.pending`, and the producer of
        `self.write_pool`.
        """
        self._verify_cb_thread()
        self.pending.pop(self.pending.index(pending_write))
        self.write_pool.append(pending_write.invalidate())

    def _fetch_pending_write(self, msg):
        """
        Decrease the number of available oustanding writes by popping from
        `self.write_pool` and appending to `self.pending`.

        Threading: only the link (network) thread should access this function.
        The link thread is the producer of `self.pending`, and the consumer of
        `self.write_pool`.
        """
        self._verify_link_thread()
        pending_write = self.write_pool.pop(0)
        self.pending.append(pending_write.track(msg, time.time()))

    def _window_available(self):
        return len(self.write_pool) != 0

    def __enter__(self):
        self.link.add_callback(self._write_cb, self.msg_type)
        return self

    def __exit__(self, type, value, traceback):
        self.link.remove_callback(self._write_cb, self.msg_type)

    def _write_cb(self, msg, **metadata):
        for pending_write in self.pending[:]:
            if msg.sequence == pending_write.message.sequence:
                if self.cb:
                    self.cb(pending_write.message, msg)
                pending_write.complete = True
                self._return_pending_write(pending_write)

    def _check_pending(self):
        # Get a copy of all the records so they won't change while we're
        #   checking for a time-out.
        pending_writes = ((P, copy.copy(P)) for P in self.pending[:])
        for pending_write, pending_write_copy in pending_writes:
            if not pending_write_copy.is_pending():
                continue
            tnow = time.time()
            if tnow - pending_write_copy.time > SBP_FILEIO_TIMEOUT:
                if pending_write_copy.tries >= MINIMUM_RETRIES:
                    raise Exception('Timed out')
                # Update the live record
                pending_write.record_retry(tnow)
                self.link(pending_write_copy.message)

    def _wait_window_available(self):
        while not self._window_available():
            self._check_pending()
            if not self._window_available():
                time.sleep(0.01)

    def send(self, msg):
        self._wait_window_available()
        self._fetch_pending_write(msg)
        self.link(msg)

    def flush(self):
        while len(self.pending) > 0:
            self._check_pending()
            time.sleep(0.01)


class FileIO(object):
    def __init__(self, link):
        self.link = link
        self._seq = random.randint(0, 0xffffffff)

    def next_seq(self):
        self._seq += 1
        return self._seq

    def read(self, filename):
        """
        Read the contents of a file.

        Parameters
        ----------
        filename : bytes
            Name of the file to read.

        Returns
        -------
        out : bytearray
            Contents of the file.
        """
        offset = 0
        chunksize = MAX_PAYLOAD_SIZE - 4
        closure = {'mostly_done': False, 'done': False, 'buf': {}, 'pending': set()}

        def cb(req, resp):
            closure['pending'].remove(req.offset)
            closure['buf'][req.offset] = resp.contents
            if req.chunk_size != len(resp.contents):
                closure['mostly_done'] = True
            if closure['mostly_done'] and len(closure['pending']) == 0:
                closure['done'] = True

        with SelectiveRepeater(self.link, SBP_MSG_FILEIO_READ_RESP, cb) as sr:
            while not closure['mostly_done']:
                seq = self.next_seq()
                msg = MsgFileioReadReq(
                    sequence=seq,
                    offset=offset,
                    chunk_size=chunksize,
                    filename=filename)
                closure['pending'].add(offset)
                sr.send(msg)
                offset += chunksize
            while not closure['done']:
                time.sleep(0.01)
            sorted_buffers = sorted(closure['buf'].items(), key=lambda kv: kv[0])
            return bytearray(itertools.chain.from_iterable(kv[1] for kv in sorted_buffers))

    def readdir(self, dirname=b'.'):
        """
        List the files in a directory.

        Parameters
        ----------
        dirname : bytes (optional)
            Name of the directory to list. Defaults to the root directory.

        Returns
        -------
        out : [bytes]
            List of file names.
        """
        files = []
        while True:
            seq = self.next_seq()
            msg = MsgFileioReadDirReq(
                sequence=seq, offset=len(files), dirname=dirname)
            self.link(msg)
            reply = self.link.wait(SBP_MSG_FILEIO_READ_DIR_RESP, timeout=1.0)
            if not reply:
                raise Exception("Timeout waiting for FILEIO_READ_DIR reply")
            # Why isn't this already decoded?
            reply = MsgFileioReadDirResp(reply)
            if reply.sequence != seq:
                raise Exception("Reply FILEIO_READ_DIR doesn't match request (%d vs %d)" % (reply.sequence, seq))
            chunk = bytes(reply.contents).rstrip(b'\0')

            if len(chunk) == 0:
                return files
            files += chunk.split(b'\0')

    def remove(self, filename):
        """
        Delete a file.

        Parameters
        ----------
        filename : bytes
            Name of the file to delete.
        """
        msg = MsgFileioRemove(filename=filename)
        self.link(msg)

    def write(self, filename, data, offset=0, trunc=True, progress_cb=None):
        """
        Write to a file.

        Parameters
        ----------
        filename : bytes
            Name of the file to write to.
        data : bytearray
            Data to write
        offset : int (optional)
            Offset into the file at which to start writing in bytes.
        trunc : bool (optional)
            Overwite the file, i.e. delete any existing file before writing. If
            this option is not specified and the existing file is longer than the
            current write then the contents of the file beyond the write will
            remain. If offset is non-zero then this flag is ignored.

        Returns
        -------
        out : str
            Contents of the file.
        """
        if trunc and offset == 0:
            self.remove(filename)

        # How do we calculate this from the MsgFileioWriteReq class?
        chunksize = MAX_PAYLOAD_SIZE - len(filename) - 9
        current_index = 0

        with SelectiveRepeater(self.link, SBP_MSG_FILEIO_WRITE_RESP) as sr:
            while offset < len(data):
                seq = self.next_seq()
                end_index = offset + chunksize - 1
                if end_index > len(data):
                    end_index = len(data)
                chunk = data[offset:offset + chunksize - 1]
                msg = MsgFileioWriteReq(
                    sequence=seq,
                    offset=offset,
                    filename=filename + b'\x00',
                    data=chunk)
                sr.send(msg)
                offset += len(chunk)
                if (progress_cb is not None and seq % PROGRESS_CB_REDUCTION_FACTOR == 0):
                    progress_cb(offset)
            sr.flush()


def hexdump(data):
    """
    Print a hex dump.

    Parameters
    ----------
    data : indexable
        Data to display dump of, can be anything that supports length and index
        operations.
    """
    ret = ''
    ofs = 0
    while data:
        # get 16 bytes from byte array and store in "chunk"
        chunk = data[:16]
        # remove bytes from data
        data = data[16:]
        s = "%08X  " % ofs
        s += " ".join("%02X" % c for c in chunk[:8]) + "  "
        s += " ".join("%02X" % c for c in chunk[8:])
        s += "".join(" " for i in range(60 - len(s))) + "|"
        for c in chunk:
            s += chr(c) if 32 <= c < 128 else '.'
        s += '|\n'
        ofs += 16
        ret += s
    return ret


def print_dir_listing(files):
    """
    Print a directory listing.

    Parameters
    ----------
    files : [bytes]
        List of file names in the directory.
    """
    for f in files:
        print(printable_text_from_device(f))


def get_args():
    """
    Get and parse arguments.
    """
    import argparse
    parser = argparse.ArgumentParser(description='Swift Nav File I/O Utility.')
    parser.add_argument(
        '-w',
        '--write',
        nargs=2,
        help='Write a file from local SOURCE to remote destination DEST',
        metavar=('SOURCE', 'DEST'))
    parser.add_argument(
        '-r',
        '--read',
        nargs='+',
        help='read a file from remote SOURCE to local DEST. If no DEST is provided, file is read to stdout.',
        metavar=('SOURCE', 'DEST'))
    parser.add_argument('-l', '--list', default=None, nargs=1, help='list a directory')
    parser.add_argument('-d', '--delete', nargs=1, help='delete a file')
    parser.add_argument(
        '-p',
        '--port',
        default=serial_link.SERIAL_PORT,
        help='specify the serial port to use.')
    parser.add_argument(
        "-b",
        "--baud",
        default=serial_link.SERIAL_BAUD,
        help="specify the baud rate to use.")
    parser.add_argument(
        "-t",
        "--tcp",
        action="store_true",
        default=False,
        help="Use a TCP connection instead of a local serial port. \
                      If TCP is selected, the port is interpreted as host:port"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="print extra debugging information.",
        action="store_true")
    parser.add_argument(
        "-x", "--hex", help="output in hex dump format.", action="store_true")
    parser.add_argument(
        "-f",
        "--ftdi",
        help="use pylibftdi instead of pyserial.",
        action="store_true")
    return parser.parse_args()


def raw_filename(str_filename):
    """Return a filename in raw bytes from a command line option string."""
    # Non-unicode characters/bytes in the command line options are decoded by
    # using 'surrogateescape' and file system encoding, and this reverts that.
    # References:
    # https://www.python.org/dev/peps/pep-0383/
    # https://docs.python.org/3/library/os.html#file-names-command-line-arguments-and-environment-variables
    return bytes(str_filename, sys.getfilesystemencoding(), 'surrogateescape')


def printable_text_from_device(data):
    """Takes text data from the device as bytes and returns a string where any
       characters incompatible with stdout have been replaced with '?'"""
    str = data.decode(TEXT_ENCODING, 'replace')\
              .encode(sys.stdout.encoding, 'replace')\
              .decode(sys.stdout.encoding)
    return str


def main():
    args = get_args()
    selected_driver = serial_link.get_base_args_driver(args)

    # Driver with context
    with selected_driver as driver:
        # Handler with context
        with Handler(Framer(driver.read, driver.write, args.verbose)) as link:
            f = FileIO(link)
            try:
                if args.write:
                    f.write(raw_filename(args.write[1]), bytearray(open(args.write[0], 'rb').read()))
                elif args.read:
                    if len(args.read) not in [1, 2]:
                        sys.stderr.write("Error: fileio read requires either 1 or 2 arguments, SOURCE and optionally DEST.")
                        sys.exit(1)
                    data = f.read(raw_filename(args.read[0]))
                    if len(args.read) == 2:
                        with open(args.read[1], ('w' if args.hex else 'wb')) as fd:
                            fd.write(hexdump(data) if args.hex else data)
                    elif args.hex:
                        print(hexdump(data))
                    else:
                        print(printable_text_from_device(data))
                elif args.delete:
                    f.remove(raw_filename(args.delete[0]))
                elif args.list is not None:
                    print_dir_listing(f.readdir(raw_filename(args.list[0])))
                else:
                    print("No command given, listing root directory:")
                    print_dir_listing(f.readdir())
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
