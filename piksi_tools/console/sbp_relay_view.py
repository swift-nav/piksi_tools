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
from piksi_tools.serial_link import swriter, get_uuid, \
  DEFAULT_BASE, CHANNEL_UUID
from piksi_tools.console.utils import MultilineTextEditor
from sbp.client.drivers.network_drivers import HTTPDriver
from sbp.client.forwarder import Forwarder
from sbp.client.framer import Framer
from sbp.client.handler import Handler
from sbp.client.loggers.udp_logger import UdpLogger
from sbp.observation import SBP_MSG_OBS, SBP_MSG_OBS_DEP_C, SBP_MSG_OBS_DEP_B, \
  SBP_MSG_BASE_POS_LLH, SBP_MSG_BASE_POS_ECEF
from traits.api import HasTraits, String, Button, Instance, Int, Bool, \
                       on_trait_change, Enum
from traitsui.api import View, Item, VGroup, UItem, HGroup, TextEditor, \
  spring

import sys
import time

DEFAULT_UDP_ADDRESS = "127.0.0.1"
DEFAULT_UDP_PORT = 13320
OBS_MSGS = [ SBP_MSG_OBS_DEP_C,
           SBP_MSG_OBS_DEP_B,
           SBP_MSG_BASE_POS_LLH,
           SBP_MSG_BASE_POS_ECEF,
           SBP_MSG_OBS
          ]

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
                            "Skylark is Swift Navigation's Internet service for connecting Piksi receivers without the use of a radio. To receive GPS observations from the closest nearby Piksi base station (within 5km), click Connect to Skylark.\n\n")
  start = Button(label='Start', toggle=True, width=32)
  stop = Button(label='Stop', toggle=True, width=32)
  connected_rover = Bool(False)
  connect_rover = Button(label='Connect to Skylark', toggle=True, width=32)
  disconnect_rover = Button(label='Disconnect from Skylark', toggle=True, width=32)
  base_pragma = String()
  rover_pragma = String()
  base_device_uid = String()
  rover_device_uid = String()
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
                      editor=MultilineTextEditor(TextEditor(multi_line=True)), style='readonly',
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
                        Item('base_pragma',  label='Base option '),
                        Item('base_device_uid',  label='Base device '),
                        spring),
                 HGroup(spring,
                        Item('rover_pragma', label='Rover option'),
                        Item('rover_device_uid',  label='Rover device'),
                        spring),),
               VGroup(
                 Item('http_information', label="Notes", height=10,
                      editor=MultilineTextEditor(TextEditor(multi_line=True)), style='readonly',
                      show_label=False, resizable=True, padding=15),
                 spring,
               ),
             ),
             spring
           )
  )

  def __init__(self, link, device_uid=None, base=DEFAULT_BASE, 
               whitelist=None, rover_pragma='', base_pragma='', rover_uuid='', base_uuid='',
               connect=False):
    """
    Traits tab with UI for UDP broadcast of SBP.

    Parameters
    ----------
    link : sbp.client.handler.Handler
      Link for SBP transfer to/from Piksi.
    device_uid : str
      Piksi Device UUID (defaults to None)
    base : str
      HTTP endpoint
    whitelist : [int] | None
      Piksi Device UUID (defaults to None)

    """
    self.link = link
    self.http = HTTPDriver(None, base)
    self.net_link = None
    self.fwd = None
    self.func = None
    # Whitelist used for UDP broadcast view
    self.msgs = OBS_MSGS
    # register a callback when the msg_enum trait changes
    self.on_trait_change(self.update_msgs, 'msg_enum')
    # Whitelist used for Skylark broadcasting
    self.whitelist = whitelist
    self.device_uid = None
    self.python_console_cmds = {'update': self}
    self.rover_pragma = rover_pragma
    self.base_pragma = base_pragma
    self.rover_device_uid = rover_uuid
    self.base_device_uid = base_uuid
    if connect:
      self.connect_when_uuid_received=True
    else:
      self.connect_when_uuid_received=False

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

  def set_route(self, uuid=None, serial_id=None, channel=CHANNEL_UUID):
    """Sets serial_id hash for HTTP headers.

    Parameters
    ----------
    uuid: str
      real uuid of device
    serial_id : int
      Piksi device ID
    channel : str
      UUID namespace for device UUID

    """
    if uuid:
      device_uid = uuid
    elif serial_id:
      device_uid = str(get_uuid(channel, serial_id % 1000))
    else:
      print "Improper call of set_route, either a serial number or UUID should be passed"
      device_uid = str(get_uuid(channel, 1234))
      print "Setting UUID to default value of {0}".format(device_uid)
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

  def _retry_read(self):
    """Retry read connections. Intended to be called by
    _connect_rover_fired.

    """
    i = 0
    repeats = 5
    _rover_pragma = self.rover_pragma
    _rover_device_uid = self.rover_device_uid or self.device_uid
    while self.http and not self.http.connect_read(device_uid=_rover_device_uid, pragma=_rover_pragma):
      print "Attempting to read observation from Skylark..."
      time.sleep(0.1)
      i += 1
      if i >= repeats:
        msg = ("\nUnable to receive observations from Skylark!\n\n"
               "Please check that:\n"
               " - you have a network connection\n"
               " - your Piksi has a single-point position\n"
               " - a Skylark-connected Piksi receiver \n   is nearby (within 5km)")
        self._prompt_networking_error(msg)
        self.http.read_close()
        return
    print "Connected as a rover!"
    with Handler(Framer(self.http.read, self.http.write)) as net_link:
      self.net_link = net_link
      self.fwd = Forwarder(net_link, swriter(self.link))
      self.fwd.start()
      while True:
        time.sleep(1)
        if not net_link.is_alive():
          sys.stderr.write("Network observation stream disconnected!")
          break
    # Unless the user has initiated a reconnection, assume here that the rover
    # still wants to be connected, so if we break out of the handler loop,
    # cleanup rover connection and try reconnecting.
    if self.connected_rover:
      sys.stderr.write("Going for a networking reconnection!")
      self._disconnect_rover_fired()
      self._connect_rover_fired()

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
      _base_pragma = self.base_pragma
      _base_device_uid = self.base_device_uid or self.device_uid
      if not self.http.connect_write(self.link, self.whitelist, device_uid=_base_device_uid, pragma=_base_pragma):
        msg = ("\nUnable to connect to Skylark!\n\n"
               "Please check that you have a network connection.")
        self._prompt_networking_error(msg)
        self.http.close()
        self.connected_rover = False
        return
      self.connected_rover = True
      print "Connected as a base station!"
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
        if self.fwd and self.net_link:
          self.net_link.stop()
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
