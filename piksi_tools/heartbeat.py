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

from sbp.system import MsgHeartbeat


class Heartbeat(object):
    """
    Handle receiving heartbeat messages from Piksi. Instance is callable and
    should be registered as callback for SBP_MSG_HEARTBEAT with
    sbp.client.handler.Handler.
    """

    def __init__(self):
        self.received = False
        # SBP version is unset in older devices
        self.sbp_version = (0, 0)

    def __call__(self, sbp_msg, **metadata):
        hb = MsgHeartbeat(sbp_msg)
        self.sbp_version = ((hb.flags >> 16) & 0xFF, (hb.flags >> 8) & 0xFF)
        self.received = True
