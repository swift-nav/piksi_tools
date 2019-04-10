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

from sbp.client.drivers.network_drivers import TCPDriver
import socket


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
