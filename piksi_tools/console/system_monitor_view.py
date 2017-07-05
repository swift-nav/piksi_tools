#!/usr/bin/env python
# Copyright (C) 2011-2014 Swift Navigation Inc.
# Contact: Fergus Noble <fergus@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

import os
from traits.api import Dict, HasTraits, List, Int
from traitsui.api import Item, View, HGroup, VGroup, TabularEditor, Spring
from traitsui.tabular_adapter import TabularAdapter

from traits.etsconfig.api import ETSConfig
if ETSConfig.toolkit != 'null':
  from enable.savage.trait_defs.ui.svg_button import SVGButton

from sbp.piksi  import SBP_MSG_THREAD_STATE, SBP_MSG_NETWORK_STATE_RESP, SBP_MSG_UART_STATE, SBP_MSG_UART_STATE_DEPA, MsgReset, MsgNetworkStateReq
from sbp.system import SBP_MSG_HEARTBEAT
from piksi_tools.console.utils import determine_path

def ip_bytes_to_string(ip_bytes):
  return '.'.join(str(x) for x in ip_bytes)

class SimpleAdapter(TabularAdapter):
  columns = [('Thread Name', 0), ('CPU %',  1), ('Stack Free',  2)]

class SimpleNetworkAdapter(TabularAdapter):
  columns = [('Interface Name', 0), ('IPv4 Addr',  1), ('Running',  2)]

class SystemMonitor(HasTraits):
  python_console_cmds = Dict()

  _threads_table_list = List()
  threads = List()
  
  _network_info = List()
  
  msg_obs_avg_latency_ms    = Int(0)
  msg_obs_min_latency_ms    = Int(0)
  msg_obs_max_latency_ms    = Int(0)
  msg_obs_window_latency_ms = Int(0)

  msg_obs_avg_period_ms    = Int(0)
  msg_obs_min_period_ms    = Int(0)
  msg_obs_max_period_ms    = Int(0)
  msg_obs_window_period_ms = Int(0)

  piksi_reset_button = SVGButton(
    label='Reset Piksi', tooltip='Reset Piksi',
    filename=os.path.join(determine_path(), 'images', 'fontawesome', 'power27.svg'),
    width=16, height=16, aligment='center'
   )

  network_refresh_button = SVGButton(
    label='Refresh Network Status', tooltip='Refresh Network Status',
    filename=os.path.join(determine_path(), 'images', 'fontawesome', 'refresh.svg'),
    width=16, height=16, aligment='center'
  )

  traits_view = View(
    VGroup(
      Item(
        '_threads_table_list', style = 'readonly',
        editor = TabularEditor(adapter=SimpleAdapter()),
        show_label=False, width=0.85,
      ),
      HGroup(
        VGroup(
          HGroup(
            VGroup(
              Item('msg_obs_window_latency_ms', label='Curr',
                style='readonly', format_str='%dms'),
              Item('msg_obs_avg_latency_ms', label='Avg',
                style='readonly', format_str='%dms'),
              Item('msg_obs_min_latency_ms', label='Min',
                style='readonly', format_str='%dms'),
              Item('msg_obs_max_latency_ms', label='Max',
                style='readonly', format_str='%dms'),
              label='Latency', show_border=True
            ),
            VGroup(
              Item('msg_obs_window_period_ms', label='Curr',
                style='readonly', format_str='%dms'),
              Item('msg_obs_avg_period_ms', label='Avg',
                style='readonly', format_str='%dms'),
              Item('msg_obs_min_period_ms', label='Min',
                style='readonly', format_str='%dms'),
              Item('msg_obs_max_period_ms', label='Max',
                style='readonly', format_str='%dms'),
              label='Period', show_border=True, 
            ),
            show_border=True, label="Observation Connection Monitor"
          ),
          Item('piksi_reset_button', show_label=False, width=0.50),
        ),
        VGroup(
          Item(
            '_network_info', style = 'readonly',
            editor = TabularEditor(adapter=SimpleNetworkAdapter()),
            show_label=False,
          ),
          Item('network_refresh_button', show_label=False, width=0.50),
          show_border=True, label="Network"
        ),
      ),
    ),
  )

  def update_threads(self):
    self._threads_table_list = [(thread_name, state.cpu, state.stack_free)
      for thread_name, state in sorted(
        self.threads, key=lambda x: x[1].cpu, reverse=True)]

  def heartbeat_callback(self, sbp_msg, **metadata):
    if self.threads != []:
      self.update_threads()
      self.threads = []

  def thread_state_callback(self, sbp_msg, **metadata):
    if sbp_msg.name == '':
      sbp_msg.name = '(no name)'
    sbp_msg.cpu /= 10.
    self.threads.append((sbp_msg.name, sbp_msg))

  def _piksi_reset_button_fired(self):
    self.link(MsgReset(flags=0))

  def _network_refresh_button_fired(self):
    self._network_info = []
    self.link(MsgNetworkStateReq())

  def _network_callback(self, m, **metadata):
    self._network_info.append((m.interface_name, ip_bytes_to_string(m.ipv4_address.ipv4_address), ((m.flags & (1 << 6)) != 0)))

  def uart_state_callback(self, m, **metadata):

    self.msg_obs_avg_latency_ms = m.latency.avg
    self.msg_obs_min_latency_ms = m.latency.lmin
    self.msg_obs_max_latency_ms = m.latency.lmax
    self.msg_obs_window_latency_ms = m.latency.current
    if m.msg_type == SBP_MSG_UART_STATE:
      self.msg_obs_avg_period_ms = m.obs_period.avg
      self.msg_obs_min_period_ms = m.obs_period.pmin
      self.msg_obs_max_period_ms = m.obs_period.pmax
      self.msg_obs_window_period_ms = m.obs_period.current

  def __init__(self, link):
    super(SystemMonitor, self).__init__()
    self.link = link
    self.link.add_callback(self.heartbeat_callback, SBP_MSG_HEARTBEAT)
    self.link.add_callback(self.thread_state_callback, SBP_MSG_THREAD_STATE)
    self.link.add_callback(self.uart_state_callback, [SBP_MSG_UART_STATE, SBP_MSG_UART_STATE_DEPA])
    self.link.add_callback(self._network_callback, SBP_MSG_NETWORK_STATE_RESP)

    self.python_console_cmds = {
      'mon': self
    }
