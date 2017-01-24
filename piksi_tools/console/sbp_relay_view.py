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

from piksi_tools.console.callback_prompt import CallbackPrompt, close_button
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
from traits.api import HasTraits, String, Button, Int, Bool, Enum
from traitsui.api import View, Item, VGroup, UItem, HGroup, TextEditor, \
  spring, Spring

import sys
import time
import threading

DEFAULT_UDP_ADDRESS = "127.0.0.1"
DEFAULT_UDP_PORT = 13320
OBS_MSGS = [SBP_MSG_OBS_DEP_C,
           SBP_MSG_OBS_DEP_B,
           SBP_MSG_BASE_POS_LLH,
           SBP_MSG_BASE_POS_ECEF,
           SBP_MSG_OBS
          ]


class SkylarkConsoleConnectConfig(object):
  """ This class is intended to encase any skylark specific
      config that will come in.  Eventually should come from a file 
      or simpler command line yaml string. It should hold 
      skylark api connection info and separate it from the GUI"""
  def __init__(self, link, device_uid, skylark_url, whitelist,
               rover_pragma, base_pragma, rover_uuid, base_uuid):
    self.link = link
    self.skylark_url = skylark_url
    self.device_uid = device_uid
    self.whitelist = whitelist
    self.rover_pragma = rover_pragma
    self.base_pragma = base_pragma
    self.rover_uuid = rover_uuid
    self.base_uuid = base_uuid

  def __repr__(self):
    return ("link: {0}, skylark_url {1}, device_uid: {2}, "
            "whitelist {3}, rover pragma: {4}, base_pragma: {5}, "
            "rover_uuid: {6}, base_uuid {7}").format(
                self.link, self.skylark_url, self.device_uid, 
                self.whitelist, self.rover_pragma, self.base_pragma,
                self.rover_uuid, self.base_uuid)


class SkylarkWatchdogThread(threading.Thread):
  """ This thread handles connecting to skylark and auto reconnecting
      Parameters
        ----------
        link : - Sbp Handler
        skylark_config : SkylarkConsoleConnectConfig 
          object storing all skylark settings
        stopped_callback : function pointer 
          function to call when thread is stopped
        kwargs : dict 
           all remaining thread constructor arguments
  """
  def __init__(self, link=None, skylark_config=None, stopped_callback=None, 
               group=None, target=None, name=None,
               args=(), kwargs=None, verbose=None):
    threading.Thread.__init__(self, group=group, target=target, name=name,
                              verbose=verbose)
    self.args = args
    self.kwargs = kwargs
    self.link = link
    self.skylark_config = skylark_config
    self._stop = threading.Event()
    self.stopped_callback = stopped_callback
    self.verbose = verbose
    self._init_time = time.time()
    self._connect_time = None
    self._stop_time = None
    
    # Verify that api is being followed
    assert isinstance(self.skylark_config, SkylarkConsoleConnectConfig)
    assert isinstance(self.link, Handler)
    return

  def get_init_time(self):
    return self._init_time

  def get_connect_time(self):
    return self._connect_time

  def get_stop_time(self):
    return self._stop_time

  def stop(self):
    """ stops thread, sets _stop event"""
    self._stop.set()
    if self.stopped_callback:
       self.stopped_callback()
    self._stop_time = time.time()
    if self.verbose:
      print ("SkylarkWatchdogThread initialized "
             "at {0} and connected since {1} stopped at {2}").format(
                self.get_init_time(), self.get_connect_time(), self.get_stop_time())

  def stopped(self):
    """ determines if thread is stopped currently """
    return self._stop.isSet()

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

  def connect(self, link, read_config):
    """Retry read connections. Intended to be called when thread started
    Only shared resource here is the self.link
    Parameters
    ----------
    link : SbpHandler
    read_config :  SkylarkConsoleConnectConfig object 
    
    Returns
    ----------
    ret : int
       0 if exited normally by thread stopping
      -1 if unable to connect as base station
      -2 if unable to connect as rover
      -3 if we lost our net connection to skylark (we restart in this case unless stopped)

    """
    assert isinstance(read_config, SkylarkConsoleConnectConfig)
    self._connect_time = time.time()
    if self.verbose:
      print "SkylarkWatchdogThread connection attempted at time {0} with parameters {1}".format(
                 self.get_connect_time(), read_config) 
    i = 0
    repeats = 5
    http = HTTPDriver(device_uid=read_config.base_uuid, url=read_config.skylark_url)
    if not http.connect_write(link, read_config.whitelist, pragma=read_config.base_pragma):
        msg = ("\nUnable to connect to Skylark!\n\n" + 
               "Please check that you have a network connection.")
        self._prompt_networking_error(msg)
        http.close()
        self.stop()
        return -1 # unable to connect as base
    time.sleep(1)

    # If we get here, we were able to connect as a base
    print "Attempting to read observation from Skylark..."
    while (not self.stopped() and http 
           and not http.connect_read(device_uid=read_config.rover_uuid, pragma=read_config.rover_pragma)):
      time.sleep(0.1)
      i += 1
      if i >= repeats:
        msg = ("\nUnable to receive observations from Skylark!\n\n"
               "Please check that:\n"
               " - you have a network connection\n"
               " - your Piksi has a single-point position\n"
               " - a Skylark-connected Piksi receiver \n   is nearby (within 5km)")
        self._prompt_networking_error(msg)
        http.read_close()
        self.stop()
        return -2 # Unable to connect as rover

    # If we get here, we were able to connect as rover
    print "Connected as a rover!"
    with Handler(Framer(http.read, http.write)) as net_link:
      fwd = Forwarder(net_link, swriter(link))
      if self.verbose:
        print "Starting forwarder"
      fwd.start()
      # now we sleep until we stop the thread or our http handler dies
      while not self.stopped() and net_link.is_alive():
          time.sleep(0.1)

    # when we leave this loop, we are no longer connected to skylark so the fwd should be stopped
    if self.verbose:
      print "Stopping forwarder"
    fwd.stop()

    # now manage the return code
    if self.stopped():
      return 0 # If we stop from the event, it it intended and we return 0
    else:
      return -3 # Lost connection
  
  def run(self):
    """ Continuously try and reconnect until thread stopped by other means """
    while not self.stopped():
      print "Attempting to connect to skylark..."
      ret = self.connect(self.link, self.skylark_config)
      if self.verbose:
        "Returned from SkylarkWatchdogThread.connect with code {0}".format(ret)
      time.sleep(0.25)
      print "Network Observation Stream Disconnected."

class SbpRelayView(HasTraits):
  """
  SBP Relay view- Class allows user to specify port, IP address, and message set
  to relay over UDP and to configure a skylark connection
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
  skylark_url = String()
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
                   HGroup(Spring(springy=False, width=2),
                          Item('skylark_url', enabled_when='not connected_rover', show_label=True),
                          Spring(springy=False, width=2)
                          ),
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
               connect=False, verbose=False):
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
    self.verbose = verbose
    self.skylark_watchdog_thread = None
    self.skylark_url = base
    if connect:
      self.connect_when_uuid_received = True
    else:
      self.connect_when_uuid_received = False

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

  def _disconnect_rover_fired(self):
    """Handle callback for HTTP rover disconnects.

    """
    try:
      if isinstance(self.skylark_watchdog_thread, threading.Thread) and \
         not self.skylark_watchdog_thread.stopped():
        self.skylark_watchdog_thread.stop()
      else:
        print ("Unable to disconnect: Skylark watchdog thread "
               "inititalized at {0} and connected since {1} has " 
               "already been stopped").format(self.skylark_watchdog_thread.get_init_time(),
                                              self.skylark_watchdog_thread.get_connect_time())
      self.connected_rover = False
    except:
      self.connected_rover = False
      import traceback
      print traceback.format_exc()

  def _connect_rover_fired(self):
    """Handle callback for HTTP rover connections.  Launches an instance of skylark_watchdog_thread.
    """
    if not self.device_uid:
      msg = "\nDevice ID not found!\n\nConnection requires a valid Piksi device ID."
      self._prompt_setting_error(msg)
      return
    try:
      _base_device_uid = self.base_device_uid or self.device_uid
      _rover_device_uid = self.rover_device_uid or self.device_uid
      config = SkylarkConsoleConnectConfig(self.link, self.device_uid, 
               self.skylark_url, self.whitelist, self.rover_pragma, 
               self.base_pragma, _rover_device_uid, _base_device_uid)
      self.skylark_watchdog_thread = SkylarkWatchdogThread(link=self.link, skylark_config=config, 
                                        stopped_callback=self._disconnect_rover_fired,
                                        verbose=self.verbose)
      self.connected_rover = True
      self.skylark_watchdog_thread.start()
    except:
      if isinstance(self.skylark_watchdog_thread, threading.Thread) \
         and self.skylark_watchdog_thread.stopped():
        self.skylark_watchdog_thread.stop()
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
