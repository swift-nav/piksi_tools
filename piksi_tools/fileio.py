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

import sys
import random
import time
import itertools

from sbp.client import Framer, Handler
from sbp.client.drivers.network_drivers import TCPDriver
from sbp.file_io import (SBP_MSG_FILEIO_READ_DIR_RESP,
                         SBP_MSG_FILEIO_READ_RESP, SBP_MSG_FILEIO_WRITE_RESP,
                         MsgFileioReadDirReq, MsgFileioReadDirResp,
                         MsgFileioReadReq, MsgFileioRemove, MsgFileioWriteReq)

from piksi_tools import serial_link

MAX_PAYLOAD_SIZE = 255
SBP_FILEIO_WINDOW_SIZE = 40
SBP_FILEIO_TIMEOUT = 5.0


class PendingWrite(object):
    __slots__ = ["message", "sequence", "time", "tries", "complete"]


class SelectiveRepeater(object):
    """Selective repeater for SBP file transfers"""

    def __init__(self, link, msg_type, cb=None):
        self.window = [PendingWrite() for X in range(SBP_FILEIO_WINDOW_SIZE)]
        self.pending = []
        self.link = link
        self.msg_type = msg_type
        self.cb = cb
        self.retry_total = 0
        self.packet_count = 0
        self.packet_max_rtt = 0
        self.packet_avg_rtt = 0

    def _return_pending_write(self, pending_write):
        rtt = time.time() - pending_write.time
        self.packet_max_rtt = max(rtt, self.packet_max_rtt)
        self.packet_count += 1
        self.packet_avg_rtt -= (self.packet_avg_rtt/100)
        self.packet_avg_rtt += (rtt/100)
        self.pending.pop(self.pending.index(pending_write))
        self.window.append(pending_write)

    def _fetch_pending_write(self, msg):
        pending_write = self.window.pop()
        self.pending.append(pending_write)
        pending_write.message = msg
        pending_write.sequence = msg.sequence
        pending_write.time = time.time()
        pending_write.tries = 0
        pending_write.complete = False

    def _window_available(self):
        return len(self.window) != 0

    def __enter__(self):
        self.link.add_callback(self._cb, self.msg_type)
        return self

    def __exit__(self, type, value, traceback):
        self.link.source.driver.buffer_writes(0)
        self.link.remove_callback(self._cb, self.msg_type)

    def _cb(self, msg, **metadata):
        for pending_write in self.pending[:]:
            if msg.sequence == pending_write.sequence:
                if self.cb:
                    self.cb(pending_write.message, msg)
                pending_write.complete = True
                self._return_pending_write(pending_write)

    def _check_pending(self):
        for pending_write in self.pending[:]:
            if pending_write.complete:
                continue
            tnow = time.time()
            if tnow - pending_write.time > SBP_FILEIO_TIMEOUT:
                if pending_write.tries >= 3:
                    raise Exception('Timed out')
                pending_write.tries += 1
                self.retry_total += 1
                pending_write.time = tnow
                self.link(pending_write.message)

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
        filename : str
            Name of the file to read.

        Returns
        -------
        out : str
            Contents of the file.
        """
        offset = 0
        chunksize = MAX_PAYLOAD_SIZE - 4
        closure = {'done': False, 'buf': []}

        def cb(req, resp):
            if len(closure['buf']) < req.offset:
                closure['buf'] += [0] * (req.offset - len(closure['buf']))
            closure['buf'][req.offset:
                           req.offset + len(resp.contents)] = resp.contents
            if req.chunk_size != len(resp.contents):
                closure['done'] = True

        with SelectiveRepeater(self.link, SBP_MSG_FILEIO_READ_RESP, cb) as sr:
            while not closure['done']:
                seq = self.next_seq()
                msg = MsgFileioReadReq(
                    sequence=seq,
                    offset=offset,
                    chunk_size=chunksize,
                    filename=filename)
                sr.send(msg)
                offset += chunksize
            return bytearray(closure['buf'])

    def readdir(self, dirname='.'):
        """
        List the files in a directory.

        Parameters
        ----------
        dirname : str (optional)
            Name of the directory to list. Defaults to the root directory.

        Returns
        -------
        out : [str]
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
                raise Exception("Reply FILEIO_READ_DIR doesn't match request")
            chunk = str(bytearray(reply.contents)).rstrip('\0')
            if len(chunk) == 0:
                return files
            files += chunk.split('\0')

    def remove(self, filename):
        """
        Delete a file.

        Parameters
        ----------
        filename : str
            Name of the file to delete.
        """
        msg = MsgFileioRemove(filename=filename)
        self.link(msg)

    def write(self, filename, data, offset=0, trunc=True, progress_cb=None):
        """
        Write to a file.

        Parameters
        ----------
        filename : str
            Name of the file to write to.
        data : str
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

        # How do we calculate this from the MsgFileioWriteRequest class?
        chunksize = MAX_PAYLOAD_SIZE - len(filename) - 9
        current_index = 0

        report_time = time.time()
        send_count = 0
        send_total = 0

        with SelectiveRepeater(self.link, SBP_MSG_FILEIO_WRITE_RESP) as sr:
            while offset < len(data):
                seq = self.next_seq()
                end_index = offset + chunksize - 1
                if end_index > len(data):
                    end_index = len(data)
                # print "going from {0} to {1} in array for chunksize {2}".format(offset, end_index, chunksize)
                chunk = data[offset:offset + chunksize - 1]
                #print("len is {0}".format(len(chunk)))
                msg = MsgFileioWriteReq(
                    sequence=seq,
                    filename=(filename + '\0' + chunk),
                    offset=offset,
                    data='')
                sr.send(msg)
                send_count += len(chunk)
                send_total += len(chunk)
                now = time.time()
                if now - report_time >= 1:
                    throughput = send_count / (now-report_time) / 1024
                    sys.stdout.write("\r%02.02f kB/s (%d retries, rtt avg %02.02f, rtt max %02.02f, packets %d, bytes sent %d)"
                                     % (throughput, sr.retry_total, sr.packet_avg_rtt, sr.packet_max_rtt, sr.packet_count, send_total))
                    sys.stdout.flush()
                    report_time = now
                    send_count = 0
                offset += len(chunk)
                if progress_cb is not None:
                    progress_cb(offset)
            sr.flush()


def hexdump(data):
    """
    Print a hex dump.

    Parameters
    ----------
    data : indexable
        Datalto display dump of, can be anything that supports length and index
        operations.
    """
    ret = ''
    ofs = 0
    while data:
        chunk = data[:16]
        data = data[16:]
        s = "%08X  " % ofs
        s += " ".join("%02X" % ord(c) for c in chunk[:8]) + "  "
        s += " ".join("%02X" % ord(c) for c in chunk[8:])
        s += "".join(" " for i in range(60 - len(s))) + "|"
        for c in chunk:
            s += c if 32 <= ord(c) < 128 else '.'
        s += '|\n'
        ofs += 16
        ret += s
    return ret


def print_dir_listing(files):
    """
    Print a directory listing.

    Parameters
    ----------
    files : [str]
        List of file names in the directory.
    """
    for f in files:
        print(f)


def get_args():
    """
    Get and parse arguments.
    """
    import argparse
    parser = argparse.ArgumentParser(description='Swift Nav File I/O Utility.')
    parser.add_argument('-w', '--write', nargs=1, help='write a file')
    parser.add_argument('-r', '--read', nargs=1, help='read a file')
    parser.add_argument(
        '-l', '--list', default=None, nargs=1, help='list a directory')
    parser.add_argument('-d', '--delete', nargs=1, help='delete a file')
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
    parser.add_argument(
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


def main():
    args = get_args()
    port = args.port[0]
    baud = args.baud[0]
    if args.tcp:
        try:
            host, port = port.split(':')
            selected_driver = TCPDriver(host, int(port))
        except: # noqa
            raise Exception('Invalid host and/or port')
    else:
        selected_driver = serial_link.get_driver(args.ftdi, port, baud)

    # Driver with context
    with selected_driver as driver:
        # Handler with context
        with Handler(Framer(driver.read, driver.write, args.verbose)) as link:
            f = FileIO(link)
            try:
                if args.write:
                    f.write(args.write[0], open(args.write[0]).read())
                elif args.read:
                    data = f.read(args.read[0])
                    if args.hex:
                        print(hexdump(data))
                    else:
                        print(data)
                elif args.delete:
                    f.remove(args.delete[0])
                elif args.list is not None:
                    print_dir_listing(f.readdir(args.list[0]))
                else:
                    print("No command given, listing root directory:")
                    print_dir_listing(f.readdir())
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
