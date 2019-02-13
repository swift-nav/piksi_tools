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
import re

from sbp.client.drivers.network_drivers import TCPDriver
from pkg_resources import parse_version as pkparse_version
import socket

def parse_version(version):
    # coerce ersion strings into something that is semver.org and PEP 440 version string  compatible
                       #prefix_string vX.X.X  pre-release-identifier         20190901 
    match = re.search('[a-zA-Z0-9-]*v([0-9]*\.[0-9]*\.[0-9])([a-zA-Z\-\_\+]*)([0-9]*).*', version)
    if match is not None:
       print("got match" + str(match.group(1) + match.group(3)))
       return pkparse_version(match.group(1) + match.group(3))
    else:
       print("no match trying raw string {}".format(version))
       return pkparse_version(version)

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
                         raise_initial_timeout=True)
    except ValueError:
        raise Exception('Invalid format (use ip_address:port): {}'.format(host))
    except socket.timeout:
        raise Exception('TCP connection timed out. Check host: {}'.format(host))
    except Exception as e:
        raise Exception('Invalid host and/or port: {}'.format(str(e)))
