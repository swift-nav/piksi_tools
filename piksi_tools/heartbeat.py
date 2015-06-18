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

from sbp.system import SBP_MSG_HEARTBEAT, MsgHeartbeat

class Heartbeat(object):
  """
  Handle receiving heartbeat messages from Piksi.
  """

  def __init__(self, link):
    """
    Parameters
    ==========
    link : sbp.client.handler.Handler
      link to register Heartbeat message callback with
    """
    self.received = False
    self.link = link
    # SBP version is unset in older devices
    self.sbp_version = (0, 0)
    self.link.add_callback(self.heartbeat_callback, SBP_MSG_HEARTBEAT)

  def __enter__(self):
    return self

  def __exit__(self, *args):
    self.link.remove_callback(self.heartbeat_callback, SBP_MSG_HEARTBEAT)

  def heartbeat_callback(self, sbp_msg):
    hb = MsgHeartbeat(sbp_msg)
    self.sbp_version = ((hb.flags >> 8) & 0xF, hb.flags & 0xF)
    self.received = True
