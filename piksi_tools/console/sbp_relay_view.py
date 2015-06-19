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

from traits.api import HasTraits, String, Button, Instance, Int, Bool, \
                       on_trait_change, Enum, on_trait_change
from traitsui.api import View, Item, VGroup, UItem, HGroup, TextEditor, spring
from piksi_tools.udp_bridge import open_socket, register_udp_callbacks, \
                                   unregister_udp_callbacks, DEFAULT_UDP_PORT, \
                                   DEFAULT_UDP_ADDRESS, OBS_MSGS
import os

class MyTextEditor(TextEditor):
  def init(self,parent):
    parent.read_only = True
    parent.multi_line = True

class SbpRelayView(HasTraits):
  running = Bool(False)
  configured=Bool(False)
  broadcasting = Bool(False)
  msg_enum = Enum( 'Observations', 'All' )
  ip = String(DEFAULT_UDP_ADDRESS)
  port = Int(DEFAULT_UDP_PORT)
  information = String('This tab is used to broadcast SBP information received by'
  ' the console to other machines or processes over UDP. With the \'Observations\''
  ' radio button selected, the console will broadcast the necessary information'
  ' for a rover Piksi to acheive an RTK solution.'
  '\n\nThis tab can be used to stream observations to a remote Piksi through'
  ' aircraft telemetry via ground control software such as MAVProxy or '
  ' Mission Planner.')

  start = Button(label='Start', toggle=True, width=32)

  stop = Button(label='Stop', toggle=True, width=32)
  view = View(
          HGroup(
            VGroup(
              Item('running',show_label=True, style='readonly', visible_when='running'),
              Item('msg_enum', label="Messages to broadcast", style='custom', enabled_when='not running'),
              Item('ip', label='IP Address', enabled_when='not running'),
              Item('port', label="Port", enabled_when='not running'),
              HGroup(
                spring,
                UItem('start', enabled_when='not running',show_label=False),
                UItem('stop', enabled_when='running',show_label=False),
                spring
                )
              ),
              VGroup(
                Item('information', label="Notes", height=10,
                editor=MyTextEditor(TextEditor(multi_line=True)), style='readonly',
                show_label=False, resizable=True, padding=15),
                spring,
              ),
            )
          )
  def __init__(self, link):
    """
    Traits tab with UI for UDP broadcast of SBP.

    Parameters
    ----------
    link : sbp.client.handler.Handler
      Link for SBP transfer to/from Piksi.
    """
    self.funcs = []
    self.msgs = OBS_MSGS
    # register a callback when the msg_enum trait changes
    self.on_trait_change(self.update_msgs, 'msg_enum')
    self.link = link
    self.udp = open_socket()
    self.python_console_cmds = {
      'update': self
    }

  def update_msgs(self):
    """
    Updates the instance variable msgs which store the msgs that we will send over UDP
    """
    if self.msg_enum =='Observations':
      self.msgs=OBS_MSGS
    elif self.msg_enum == 'All':
      self.msgs=[None]

  def _start_fired(self):
    """
    Handle start udp broadcast button. Registers callbacks on self.link for each of the self.msgs
    If self.msgs is None, it registrs one generic callback for all messages
    """
    self.running = True
    try:
      self.funcs = register_udp_callbacks(self.link, self.udp, self.ip, self.port, self.msgs)
    except:
      import traceback
      print traceback.format_exc()

  def _stop_fired(self):
    """
    Handle the stop udp broadcast button. It uses the self.funcs and self.msgs to remove
    the callbacks that were registered when the start button was pressed.
    """
    try:
      unregister_udp_callbacks(self.link, self.funcs, self.msgs)
      self.funcs = []
      self.running = False
    except:
      import traceback
      print traceback.format_exc()

