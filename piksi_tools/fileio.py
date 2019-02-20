#!/usr/bin/env python

# Copyright (C) 2014-2019 Swift Navigation Inc.
# Contact: Swift Navigation <dev@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

from __future__ import absolute_import, print_function
from future.builtins import bytes  # makes python 2 `bytes()` more similar to python 3

from collections import defaultdict

import itertools
import random
import time
import threading
import sys

from six.moves.queue import Queue

from sbp.client import Framer, Handler
from sbp.file_io import (SBP_MSG_FILEIO_READ_DIR_RESP, SBP_MSG_FILEIO_READ_RESP,
                         SBP_MSG_FILEIO_WRITE_RESP, SBP_MSG_FILEIO_CONFIG_RESP,
                         MsgFileioReadDirReq, MsgFileioReadDirResp,
                         MsgFileioReadReq, MsgFileioRemove, MsgFileioWriteReq,
                         MsgFileioConfigReq, MsgFileioConfigResp)

from piksi_tools import serial_link

MAX_PAYLOAD_SIZE = 255
SBP_FILEIO_WINDOW_SIZE = 100
SBP_FILEIO_BATCH_SIZE = 1
SBP_FILEIO_TIMEOUT = 3
MAXIMUM_RETRIES = 20
PROGRESS_CB_REDUCTION_FACTOR = 100
TEXT_ENCODING = 'utf-8'  # used for printing out directory listings and files
WAIT_SLEEP_S = 0.001
CONFIG_REQ_RETRY_MS = 100
CONFIG_REQ_TIMEOUT_MS = 1000


class PendingRequest(object):
    """
    Represents a request that is pending.

    Fields
    ----------
    message : MsgFileioWriteReq, MsgFileioReadDirReq, MsgFileioReadReq
      The request that's pending
    time : Time
      The time the message was sent (or re-sent at)
    time_expire : Time
      The time the message will be considered expired (and then retried)
    tries : int
      The number of times we've attemptted to send the write message
    index : int
      The index of this object into the pending write map
    completed : bool
      If the request is already completed
    """

    __slots__ = ["message", "time", "time_expire", "tries", "index", "completed"]

    def __init__(self, index):
        self.index = index
        self.completed = None

    def __repr__(self):
        return "PendingRequest(offset=%r,seq=%r,time=%r,tries=%r,index=%r)" % (
            self.message.offset, self.message.sequence, self.time, self.tries, self.index)

    def track(self, pending_req, time, time_expire, tries=0):
        """
        Load information about the pending write so that it can be tracked.
        """
        self.message = pending_req
        self.time = time
        self.time_expire = time_expire
        self.tries = 0
        self.completed = False
        return self

    def record_retry(self, retry_time, new_expire_time):
        """
        Record a retry event, indicates that the SelectiveRepeater decided to
        retry sending the tracked MsgFileioWriteReq message.
        """
        self.tries += 1
        self.time = retry_time
        self.time_expire = new_expire_time
        return self


class Time(object):
    """
    Time object with millisecond resolution.  Used to inspect
    request expiration times.
    """

    __slots__ = ["_seconds", "_millis"]

    def __init__(self, seconds=0, millis=0):
        self._seconds = seconds
        self._millis = millis

    @classmethod
    def now(cls):
        now = time.time()
        return Time(int(now), int((now * 1000) % 1000))

    @classmethod
    def iter_since(cls, last, now):
        """
        Iterate time slices since the `last` time given up to (and including)
        the `now` time but not including the `last` time.
        """
        increment = Time(0, 1)
        next_time = last
        while not next_time >= now:
            next_time += increment
            yield next_time

    def __hash__(self):
        return hash((self._seconds, self._millis))

    def __repr__(self):
        return "Time(s=%r,ms=%r)" % (self._seconds, self._millis)

    def __add__(a, b):
        new_time = (1000 * a._seconds) + (1000 * b._seconds) + a._millis + b._millis
        return Time(seconds=(new_time / 1000), millis=(new_time % 1000))

    def __eq__(a, b):
        return a._seconds == b._seconds and a._millis == b._millis

    def __ge__(a, b):
        if a == b:
            return True
        return a > b

    def __gt__(a, b):
        if a._seconds < b._seconds:
            return False
        if a._seconds == b._seconds:
            return a._millis > b._millis
        return True


class SelectiveRepeater(object):
    """
    Selective repeater for SBP file I/O requests

    Fields
    ----------
    _pending_map : list(PendingRequest)
      List (used as a map) of PendingRequest objects, used to track
      outstanding requests.
    _request_pool : Queue
      Queue of available requests (recorded by index number)
    _seqmap : dict(int,int)
      Dictionary mapping SBP request sequence IDs to their corresponding
      request index.
    _batch_msgs : list
      Collector for a batch of messages to be sent in one
      buffer via the link
    _last_check_time : Time
      The last time we checked if any packets had expired
    _expire_map : dict(Time, dict(PendingRequest, PendingRequest))
      Dictionary which records the future time at which a request
      will expire.

    _msg_type : int
      The message type we're currently sending
    _link : Handler
      The link over which we're sending data

    _callback_thread : int
      ID of the thread that we expect callbacks from
    _link_thread : int
      ID of the thread that handles link writes
    """

    def __init__(self, link, msg_type, cb=None):
        """
        Args
        ---
        link : Handler
          Link over which messages will be sent.
        msg_type :
          The type of message being sent
        cb :
          Invoked when SBP message with type `msg_type` is received
        """

        self._link = link
        self._msg_type = msg_type
        self._callback = cb

        self._seqmap = {}
        self._batch_msgs = []
        self._last_check_time = Time.now()
        self._expire_map = defaultdict(dict)

        self._init_fileio_config(SBP_FILEIO_WINDOW_SIZE, SBP_FILEIO_BATCH_SIZE, PROGRESS_CB_REDUCTION_FACTOR)

        self._callback_thread = None
        self._link_thread = None

        self._total_sends = 1.0
        self._total_retries = 0

        now = Time.now()
        self._config_retry_time = now + Time(0, CONFIG_REQ_RETRY_MS)
        self._config_timeout = now + Time(0, CONFIG_REQ_TIMEOUT_MS)
        self._config_seq = random.randint(0, 0xffffffff)
        self._config_msg = None
        self._link(MsgFileioConfigReq(sequence=self._config_seq))

    def _init_fileio_config(self, window_size, batch_size, progress_cb_reduction_factor):
        self._pending_map = [PendingRequest(X) for X in range(window_size)]
        self._request_pool = Queue(window_size)
        for pending_req in self._pending_map:
            self._request_pool.put(pending_req)
        self._batch_size = batch_size
        self._progress_cb_reduction_factor = progress_cb_reduction_factor

    def __enter__(self):
        self._link.add_callback(self._request_cb, self._msg_type)
        self._link.add_callback(self._config_cb, SBP_MSG_FILEIO_CONFIG_RESP)
        return self

    def __exit__(self, type, value, traceback):
        self._link.remove_callback(self._request_cb, self._msg_type)
        self._link.remove_callback(self._config_cb, SBP_MSG_FILEIO_CONFIG_RESP)

    def _verify_cb_thread(self):
        """
        Verify that only one thread is consuming requests.
        """
        if self._callback_thread is None:
            self._callback_thread = threading.currentThread().ident
        assert self._callback_thread == threading.currentThread().ident

    def _verify_link_thread(self):
        """
        Verify that only one thread is producing requests.
        """
        if self._link_thread is None:
            self._link_thread = threading.currentThread().ident
        assert self._link_thread == threading.currentThread().ident

    def _return_pending_req(self, pending_req):
        """
        Return a pending request to the write pool and clean any
        entries in the expiration map.
        """
        self._verify_cb_thread()
        pending_req.completed = True
        try:
            msg = pending_req.message
        except AttributeError:
            # Got a completion for something that was never requested
            return
        self._try_remove_keys(self._seqmap, msg.sequence)
        if self._try_remove_keys(self._expire_map[pending_req.time_expire], pending_req):
            # Only put the request back if it was successfully removed
            self._request_pool.put(pending_req)

    def _record_pending_req(self, msg, time_now, expiration_time):
        """
        Acquire a pending request object and record it's future
        expiration time in a map.
        """
        self._verify_link_thread()
        # Queue.get will block if no requests are available
        pending_req = self._request_pool.get(True)
        assert self._pending_map[pending_req.index].index == pending_req.index
        self._seqmap[msg.sequence] = pending_req.index
        self._pending_map[pending_req.index].track(msg, time_now, expiration_time)
        self._expire_map[expiration_time][pending_req] = pending_req

    def _config_cb(self, msg, **metadata):
        self._config_msg = msg
        self._init_fileio_config(msg.window_size, msg.batch_size, PROGRESS_CB_REDUCTION_FACTOR * 2)

    def _request_cb(self, msg, **metadata):
        """
        Process request completions.
        """
        index = self._seqmap.get(msg.sequence)
        if index is None:
            return
        pending_req = self._pending_map[index]
        if self._callback:
            self._callback(pending_req.message, msg)
        self._return_pending_req(pending_req)

    def _has_pending(self):
        return self._request_pool.qsize() != len(self._pending_map)

    def _retry_send(self, check_time, pending_req, delete_keys):
        """
        Retry a request by updating it's expire time on the object
        itself and in the expiration map.
        """
        self._total_retries += 1
        self._total_sends += 1
        timeout_delta = Time(SBP_FILEIO_TIMEOUT)
        send_time = Time.now()
        new_expire = send_time + timeout_delta
        pending_req.record_retry(send_time, new_expire)
        self._expire_map[new_expire][pending_req] = pending_req
        self._link(pending_req.message)
        delete_keys.append(pending_req)

    def _try_remove_keys(self, d, *keys):
        success = True
        for key in keys:
            try:
                del d[key]
            except KeyError:
                success = False
        return success

    def _check_pending(self):
        """
        Scans from the last check time to the current time looking
        for requests that are due to expire and retries them if
        necessary.
        """
        time_now = Time.now()
        timeout_delta = Time(SBP_FILEIO_TIMEOUT)
        for check_time in Time.iter_since(self._last_check_time, time_now):
            pending_reqs = self._expire_map[check_time]
            retried_writes = []
            for pending_req in pending_reqs.keys():
                time_expire = pending_req.time + timeout_delta
                if time_now >= time_expire:
                    if pending_req.tries >= MAXIMUM_RETRIES:
                        raise Exception('Timed out')
                    # If the completion map becomes inconsistent (because
                    #   things are completing at the same time they're
                    #   being re-tried) then the `completed` field should
                    #   prevent us from re-sending a write in this case.
                    if not pending_req.completed:
                        self._retry_send(check_time, pending_req, retried_writes)
            # Pending writes can be marked completed while this function
            #   is running, so a key error means is was marked completed
            #   after we sent a retry (therefore _try_remove_keys ignores
            #   key errors).
            self._try_remove_keys(self._expire_map[check_time], *retried_writes)
        self._last_check_time = time_now

    def _window_available(self, batch_size):
        return self._request_pool.qsize() >= batch_size

    def _config_received(self):
        if self._config_msg is not None:
            return True
        now = Time.now()
        if now >= self._config_retry_time:
            self._link(MsgFileioConfigReq(sequence=self._config_seq))
            self._config_retry_time = now + Time(0, CONFIG_REQ_RETRY_MS)
        if now >= self._config_timeout:
            self._config_msg = MsgFileioConfigResp(sequence=0,
                                                   window_size=100,
                                                   batch_size=1,
                                                   fileio_version=0)
        return self._config_msg is not None

    def _wait_config_received(self):
        while not self._config_received():
            time.sleep(WAIT_SLEEP_S)

    def _wait_window_available(self, batch_size):
        self._wait_config_received()
        while not self._window_available(batch_size):
            self._check_pending()
            if not self._window_available(batch_size):
                time.sleep(WAIT_SLEEP_S)

    @property
    def total_retries(self):
        return self._total_retries

    @property
    def total_sends(self):
        return self._total_sends

    @property
    def progress_cb_reduction_factor(self):
        return self._progress_cb_reduction_factor

    def send(self, msg, batch_size=None):
        if batch_size is not None:
            self._send(msg, batch_size)
        else:
            self._send(msg, self._batch_size)

    def _send(self, msg, batch_size):
        """
        Sends data via the current link, potentially batching it together.

        Parameters
        ----------
        msg : MsgFileioReadReq, MsgFileioReadDirReq, MsgFileioWriteReq, MsgFileioRemove
          The message to be sent via the current link
        batch_size : int
          The number of message to batch together before actually sending
        """
        if msg is not None:
            self._batch_msgs.append(msg)
        if len(self._batch_msgs) >= batch_size:
            self._wait_window_available(batch_size)
            time_now = Time.now()
            expiration_time = time_now + Time(SBP_FILEIO_TIMEOUT)
            for msg in self._batch_msgs:
                self._record_pending_req(msg, time_now, expiration_time)
            self._link(*self._batch_msgs)
            self._total_sends += len(self._batch_msgs)
            del self._batch_msgs[:]

    def flush(self):
        """
        Flush any pending requests (batched or otherwise) and wait for all
        pending requests to complete.
        """
        self.send(None, batch_size=0)
        while self._has_pending():
            self._check_pending()
            time.sleep(WAIT_SLEEP_S)


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
                time.sleep(WAIT_SLEEP_S)
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
            reply = self.link.wait(SBP_MSG_FILEIO_READ_DIR_RESP, timeout=5.0)
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
                    filename=filename + b'\x00' + chunk,  # Note: We put "chunk" into the name because
                                                          #   putting in the correct place (the data
                                                          #   field) results in a huge slowdown
                                                          #   (presumably because an issue in the
                                                          #    construct library).
                    data=b'')
                sr.send(msg)
                offset += len(chunk)
                if (progress_cb is not None and seq % sr.progress_cb_reduction_factor == 0):
                    progress_cb(offset, sr)
            progress_cb(offset, sr)
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


def mk_progress_cb(file_length):

    time_last = [time.time()]
    offset_last = [0]

    b_to_mb = 1024 * 1024.0
    file_mb = file_length / b_to_mb
    rolling_avg_len = 20
    rolling_avg_pts = []
    previous_avg = [None]

    def compute_rolling_average(speed_kbs):
        removed_pt = None
        if len(rolling_avg_pts) >= rolling_avg_len:
            removed_pt = rolling_avg_pts.pop(0)
        rolling_avg_pts.append(speed_kbs)
        if removed_pt is not None:
            assert previous_avg[0] is not None
            new_avg_contrib = speed_kbs / rolling_avg_len
            removed_avg_contrib = removed_pt / rolling_avg_len
            previous_avg[0] -= removed_avg_contrib
            previous_avg[0] += new_avg_contrib
            return previous_avg[0]
        else:
            previous_avg[0] = sum(rolling_avg_pts) / len(rolling_avg_pts)
            return previous_avg[0]

    def the_callback(offset, repeater):
        time_current = time.time()
        offset_delta = offset - offset_last[0]
        time_delta = time_current - time_last[0]
        percent_done = 100 * (offset / float(file_length))
        mb_confirmed = offset / b_to_mb
        speed_kbs = offset_delta / time_delta / 1024
        rolling_avg = compute_rolling_average(speed_kbs)
        fmt_str = "\r[{:02.02f}% ({:.02f}/{:.02f} MB) at {:.02f} kB/s ({:0.02f}% retried)]"
        percent_retried = 100 * (repeater.total_retries / repeater.total_sends)
        status_str = fmt_str.format(percent_done,
                                    mb_confirmed,
                                    file_mb,
                                    rolling_avg,
                                    percent_retried,
                                    repeater.total_retries,
                                    repeater.total_sends)
        sys.stdout.write(status_str)
        sys.stdout.flush()
        time_last[0] = time_current
        offset_last[0] = offset

    return the_callback


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
                    file_data = bytearray(open(args.write[0], 'rb').read())
                    f.write(raw_filename(args.write[1]), file_data, progress_cb=mk_progress_cb(len(file_data)))
                    sys.stdout.write("\n")
                    sys.stdout.flush()
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
