#!/usr/bin/env python
# Copyright (C) 2015 Swift Navigation Inc.
# Contact: Colin Beighley <colin@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

from __future__ import print_function

import errno
import os
import socket
import monotonic
import time

from sbp.client.drivers.network_drivers import TCPDriver
from sbp.client.drivers.base_driver import BaseDriver
from sbp.client.drivers.file_driver import FileDriver
from sbp.client.framer import Framer
from sbp.observation import MsgObs
import sbp.client as sbpc
import sbp.navigation as sbpn

import sched

class GPSTime:
    wn = 0
    tow = 0
    def __init__(self, wn, tow):
        self.wn = wn
        self.tow = tow

    def __repr__(self):
        return "WN {} TOW {}".format(self.wn, self.tow)

    def to_secs(self):
        return (self.wn * 604800) + (self.tow / 1000)

    def is_valid(self):
        return self.wn != 0

    def __lt__(self, other):
        return self.to_secs() < other.to_secs()

class RealTimeFramer(Framer):
    prev_t = None
    replay_speed = 1.0

    def __init__(self, read, write, verbose, replay_speed):
        super().__init__(read, write, verbose)
        if replay_speed == "Slow":
            self.replay_speed = 0.5
        elif replay_speed == "Regular":
            self.replay_speed = 1.0
        elif replay_speed == "Fast":
            self.replay_speed = 2.0
        elif replay_speed == "Ludicrous":
            self.replay_speed = 10.0
        else:
            print("Unknown speed value: {}".format(replay_speed))
            self.replay_speed = 1.0

    def __next__(self):
        (msg, metadata) = super().__next__()

        t = None
        if type(msg) == MsgObs:
            t = GPSTime(msg.header.t.wn, msg.header.t.tow)
        elif hasattr(msg, 'tow') and hasattr(msg, "wn"):
            t = GPSTime(msg.wn, msg.tow)

        if t != None and t.is_valid():
            if self.prev_t != None and self.prev_t < t:
                dt = t.to_secs() - self.prev_t.to_secs()
                dt /= self.replay_speed
                time.sleep(dt)
            self.prev_t = t

        return (msg, metadata)


def wrap_sbp_dict(data_dict, timestamp):
    return {'data': data_dict, 'time': timestamp}


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        # seems to be raised while calling os.makedirs on the root of a writable
        # directory
        elif getattr(exc, 'winerror', None) == 5:
            pass
        else:
            raise


def sopen(path, mode):
    ''' Open "path" for writing, creating any parent directories as needed.
    '''
    mkdir_p(os.path.dirname(path))
    return open(path, mode)


def get_tcp_driver(host, port=None):
    ''' Factory method helper for opening TCPDriver from host and port
    '''
    try:
        if port is None:
            host, port = host.split(':')
        return TCPDriver(host,
                         int(port),
                         raise_initial_timeout=True,
                         reconnect=True)
    except ValueError:
        raise Exception('Invalid format (use ip_address:port): {}'.format(host))
    except socket.timeout:
        raise Exception('TCP connection timed out. Check host: {}'.format(host))
    except Exception as e:
        raise Exception('Invalid host and/or port: {}'.format(str(e)))

def get_file_driver(file_path):
    return FileDriver(open(file_path, "rb"))


class Time(object):
    """
    Time object with millisecond resolution.  Used to inspect
    request expiration times.
    """

    __slots__ = ["_seconds", "_millis"]

    def __init__(self, seconds=0, millis=0):
        self._seconds = seconds
        self._millis = millis

    @staticmethod
    def now():
        now = monotonic.monotonic()
        return Time.from_float(now)

    @staticmethod
    def from_float(seconds):
        return Time(int(seconds), int((seconds * 1000) % 1000))

    @staticmethod
    def iter_since(last, now):
        """
        Iterate time slices since the `last` time given up to (and including)
        the `now` time but not including the `last` time.
        """
        increment = Time(0, 1)
        next_time = last
        while not next_time >= now:
            next_time += increment
            yield next_time

    def to_float(self):
        return self._seconds + (self._millis / 1000)

    def __hash__(self):
        return hash((self._seconds, self._millis))

    def __repr__(self):
        return "Time(s=%r,ms=%r)" % (self._seconds, self._millis)

    def __add__(a, b):
        new_time = (1000 * a._seconds) + (1000 * b._seconds) + a._millis + b._millis
        return Time(seconds=(new_time // 1000), millis=(new_time % 1000))

    def __sub__(a, b):
        new_time = (1000 * a._seconds) - (1000 * b._seconds) - a._millis - b._millis
        return Time(seconds=(new_time // 1000), millis=(new_time % 1000))

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

    def __le__(a, b):
        if a == b:
            return True
        return a < b

    def __lt__(a, b):
        if a._seconds > b._seconds:
            return False
        if a._seconds == b._seconds:
            return a._millis < b._millis
        return True
