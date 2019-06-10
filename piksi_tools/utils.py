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

from sbp.client.drivers.network_drivers import TCPDriver


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
        new_time = (1000 * a._seconds) - (1000 * b._seconds) + (a._millis - b._millis)
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
