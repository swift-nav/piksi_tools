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

from callback_prompt import CallbackPrompt, close_button
from concurrent.futures import ThreadPoolExecutor
from piksi_tools.serial_link import DEFAULT_WHITELIST
from sbp.client.loggers.udp_logger import UdpLogger
from sbp.observation import SBP_MSG_OBS, SBP_MSG_BASE_POS
from traits.api import HasTraits, String, Button, Instance, Int, Bool, \
                       on_trait_change, Enum
from traitsui.api import View, Item, VGroup, UItem, HGroup, TextEditor, \
  spring
import time
import warnings

DEFAULT_UDP_ADDRESS = "127.0.0.1"
DEFAULT_UDP_PORT = 13320

OBS_MSGS = [SBP_MSG_OBS, SBP_MSG_BASE_POS,]

# TODO (Buro): Add a ButtonEditor for changing the text

class MyTextEditor(TextEditor):
  """
  Override of TextEditor Class for a multi-lin read only
  """
  def init(self, parent):
    parent.read_only = True
    parent.multi_line = True

class SbpRelayView(HasTraits):
  """
  UDP Relay view- Class allows user to specify port, IP address, and message set
  to relay over UDP
  """
  running = Bool(False)
  configured = Bool(False)
  broadcasting = Bool(False)
  msg_enum = Enum('Observations', 'All')
  ip_ad = String(DEFAULT_UDP_ADDRESS)
  port = Int(DEFAULT_UDP_PORT)
  information = String('UDP Streaming\n\nBroadcast SBP information received by'
    ' the console to other machines or processes over UDP. With the \'Observations\''
    ' radio button selected, the console will broadcast the necessary information'
    ' for a rover Piksi to acheive an RTK solution.'
    '\n\nThis can be used to stream observations to a remote Piksi through'
    ' aircraft telemetry via ground control software such as MAVProxy or'
    ' Mission Planner.')
  http_information = String('Skylark - Experimental Piksi Networking\n\n'
                            'Skylark is an Internet service for connecting Piksi receivers without the use of a radio. To receive GPS observations from the closest nearby Piksi base station (within 5km), click Connect to Skylark.\n\nTo hide your observations (and position) from other nearby Piksi receivers, select the checkbox Hide Observations From Other Receivers.\n\n')
  start = Button(label='Start', toggle=True, width=32)
  stop = Button(label='Stop', toggle=True, width=32)
  connected_rover = Bool(False)
  connect_rover = Button(label='Connect to Skylark', toggle=True, width=32)
  disconnect_rover = Button(label='Disconnect from Skylark', toggle=True, width=32)
  hide_observations_from_other_receivers = Bool(False)
  toggle=True
  view = View(
           VGroup(
             spring,
             HGroup(
               VGroup(
                 Item('running', show_label=True, style='readonly', visible_when='running'),
                 Item('msg_enum', label="Messages to broadcast",
                      style='custom', enabled_when='not running'),
                 Item('ip_ad', label='IP Address', enabled_when='not running'),
                 Item('port', label="Port", enabled_when='not running'),
                 HGroup(
                   spring,
                   UItem('start', enabled_when='not running', show_label=False),
                   UItem('stop', enabled_when='running', show_label=False),
                   spring)),
               VGroup(
                 Item('information', label="Notes", height=10,
                      editor=MyTextEditor(TextEditor(multi_line=True)), style='readonly',
                      show_label=False, resizable=True, padding=15),
                 spring,
               ),
             ),
             spring,
             HGroup(
               VGroup(
                 HGroup(
                   spring,
                   UItem('connect_rover', enabled_when='not connected_rover', show_label=False),
                   UItem('disconnect_rover', enabled_when='connected_rover', show_label=False),
                   spring),
                 HGroup(spring,
                        Item('hide_observations_from_other_receivers'),
                        spring),),
               VGroup(
                 Item('http_information', label="Notes", height=10,
                      editor=MyTextEditor(TextEditor(multi_line=True)), style='readonly',
                      show_label=False, resizable=True, padding=15),
                 spring,
               ),
             ),
             spring
           )
  )

  def __init__(self, link, http=None, device_uid=None, whitelist=DEFAULT_WHITELIST):
    """
    Traits tab with UI for UDP broadcast of SBP.

    Parameters
    ----------
    link : sbp.client.handler.Handler
      Link for SBP transfer to/from Piksi.
    http : sbp.client.handler.Handler
      Link for SBP transfer to/from an HTTP connection.
      Defaults to None
    device_uid : str
      Piksi Device UUID (defaults to None)
    whitelist : [int]
      Piksi Device UUID (defaults to None)

    """
    self.func = None
    # Whitelist used for UDP broadcast view
    self.msgs = OBS_MSGS
    # register a callback when the msg_enum trait changes
    self.on_trait_change(self.update_msgs, 'msg_enum')
    self.link = link
    self.http = http
    # Whitelist used for Skylark broadcasting
    self.whitelist = whitelist
    self.device_uid = None
    self.python_console_cmds = {'update': self}

  def update_msgs(self):
    """Updates the instance variable msgs which store the msgs that we
    will send over UDP.

    """
    if self.msg_enum == 'Observations':
      self.msgs = OBS_MSGS
    elif self.msg_enum == 'All':
      self.msgs = [None]
    else:
      raise NotImplementedError

  def set_route(self, device_uid):
    self.device_uid = device_uid
    if self.http:
      self.http.device_uid = device_uid

  def _prompt_networking_error(self, text):
    """Nonblocking prompt for a networking error.

    Parameters
    ----------
    text : str
      Helpful error message for the user

    """
    prompt = CallbackPrompt(title="Networking Error", actions=[close_button])
    prompt.text = text
    prompt.run(block=False)

  def _prompt_setting_error(self, text):
    """Nonblocking prompt for a device setting error.

    Parameters
    ----------
    text : str
      Helpful error message for the user

    """
    prompt = CallbackPrompt(title="Setting Error", actions=[close_button])
    prompt.text = text
    prompt.run(block=False)

  def _prompt_wait(self, text, interval=5.):
    """Configurable blocking prompt.

    Parameters
    ----------
    text : str
      Helpful wait message for the user.
    interval : float
      Time interval for waiting.

    """
    prompt = CallbackPrompt(title="waiting...", actions=[])
    prompt.text = text
    t0 = time.time()
    while not self.http.connect_read() or (time.time() - t0) < interval:
      prompt.run(block=True)
    return self.http.read_ok

  def _retry_read(self):
    """Retry read connections. Intended to be called by
    _connect_rover_fired.

    """
    i = 0
    repeats = 10
    while self.http and not self.http.connect_read():
      warnings.warn("Attempting to read observation from Skylark...")
      time.sleep(1)
      i += 1
      if i >= repeats:
        self._prompt_networking_error("\nUnable to receive observations!")
        self.http.close()
        self.connected_rover = False
        return False
    self.connected_rover = True
    return True

  def _connect_rover_fired(self):
    """Handle callback for HTTP rover connections.

    """
    if not self.device_uid:
      msg = "\nDevice ID not found!\n\nConnection requires a valid Piksi device ID."
      self._prompt_setting_error(msg)
      return
    if not self.http:
      self._prompt_networking_error("\nNetworking disabled!")
      return
    try:
      _passive = self.hide_observations_from_other_receivers
      if not self.http.connect_write(self.link, self.whitelist, passive=_passive):
        msg = ("\nUnable to connect to Skylark!\n\n"
               "Please check that:\n"
               " - you have a network connection\n"
               " - your Piksi has a single-point position\n"
               " - a Skylark-connected Piksi receiver \n   is nearby (within 10km)")
        self._prompt_networking_error(msg)
        self.http.close()
        self.connected_rover = False
        return
      executor = ThreadPoolExecutor(max_workers=2)
      executor.submit(self._retry_read)
    except:
      self.connected_rover = False
      import traceback
      print traceback.format_exc()

  def _disconnect_rover_fired(self):
    """Handle callback for HTTP rover disconnects.

    """
    if not self.device_uid:
      msg = "\nDevice ID not found!\n\nConnection requires a valid Piksi device ID."
      self._prompt_setting_error(msg)
      return
    if not self.http:
      self._prompt_networking_error("\nNetworking disabled!")
      return
    try:
      if self.connected_rover:
        self.http.close()
        self.connected_rover = False
    except:
      self.connected_rover = False
      import traceback
      print traceback.format_exc()

  def _start_fired(self):
    """Handle start udp broadcast button. Registers callbacks on
    self.link for each of the self.msgs If self.msgs is None, it
    registers one generic callback for all messages.

    """
    self.running = True
    try:
      self.func = UdpLogger(self.ip_ad, self.port)
      self.link.add_callback(self.func, self.msgs)
    except:
      import traceback
      print traceback.format_exc()

  def _stop_fired(self):
    """Handle the stop udp broadcast button. It uses the self.funcs and
    self.msgs to remove the callbacks that were registered when the
    start button was pressed.

    """
    try:
      self.link.remove_callback(self.func, self.msgs)
      self.func.__exit__()
      self.func = None
      self.running = False
    except:
      import traceback
      print traceback.format_exc()
