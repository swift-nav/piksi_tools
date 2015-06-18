#!/usr/bin/env python
# Copyright (C) 2014 Swift Navigation Inc.
# Contact: Colin Beighley <colin@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

from traits.api import HasTraits, Event, String, Button, Instance, Int, Bool, \
                       on_trait_change
from traitsui.api import View, Handler, Action, Item, VGroup, UItem, InstanceEditor, \
                         VSplit, HSplit, HGroup, BooleanEditor
from piksi_tools.mavlinkbridge import open_socket, send_udp_callback_generator

class SbpBroadcastView(HasTraits):
  update_firmware = Button(label='Update Piksi Firmware')
  test = String('test string')
  test2 = String('test string 2')

  broadcasting = Bool(False)
  view = View(
    VGroup(
      HGroup(
        VGroup(
          Item('test', label='test string'),
        ),
        VGroup(
          Item('test2', style='custom', label='test2'),
        ),
      ),
      UItem('update_firmware', enabled_when='broadcasting'),
    )
  )

  def __init__(self, link):
    """
    Traits tab with UI for updating Piksi firmware.

    Parameters
    ----------
    link : sbp.client.handler.Handler
      Link for SBP transfer to/from Piksi.
    prompt : bool
      Prompt user to update console/firmware if out of date.
    """
    self.link = link
    self.python_console_cmds = {
      'update': self

    }

  def _update_firmware_fired(self):
    """
    Handle update_firmware button. Starts thread so as not to block the GUI
    thread.
    """
    print "fired"
