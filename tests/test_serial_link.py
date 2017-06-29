#!/usr/bin/env python
# Copyright (C) 2015 Swift Navigation Inc.
# Contact: Bhaskar Mookerj <mookerji@swiftnav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

from uuid import UUID

import piksi_tools.serial_link as l


def test_uuid():
    """Test UUID generation from device serial IDs.

    """
    assert l.get_uuid(l.CHANNEL_UUID, 1291) \
        == UUID('3efc8b52-73a8-5f75-bb03-550eee537f46')
    assert l.get_uuid(l.CHANNEL_UUID, 1291).version == 5
    assert l.get_uuid(l.CHANNEL_UUID, -1) == l.get_uuid(l.CHANNEL_UUID, 1)
    assert l.get_uuid(l.CHANNEL_UUID, 'x') is None
    assert l.get_uuid(l.CHANNEL_UUID, None) is None
