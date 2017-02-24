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

from traits.api import Instance, Dict, HasTraits, Array, Enum, Float, on_trait_change, List, Int, Button, Bool
from traitsui.api import Item, View, HGroup, VGroup, ArrayEditor, HSplit, TabularEditor, Spring
from traitsui.tabular_adapter import TabularAdapter

from traits.etsconfig.api import ETSConfig
if ETSConfig.toolkit != 'null':
  from enable.savage.trait_defs.ui.svg_button import SVGButton

import math
import os
import numpy as np
import datetime

from sbp.piksi  import SBP_MSG_THREAD_STATE, SBP_MSG_UART_STATE, SBP_MSG_UART_STATE_DEPA, MsgReset, MsgCommandReq
from sbp.system import SBP_MSG_HEARTBEAT
from sbp.logging import SBP_MSG_LOG, MsgLog
from piksi_tools.console.utils import determine_path

class SimpleAdapter(TabularAdapter):
    columns = [('Thread Name', 0), ('CPU %',  1), ('Stack Free',  2)]
    
class SimpleNetworkAdapter(TabularAdapter):
    columns = [('Network', 0)]

class SystemMonitorView(HasTraits):
  python_console_cmds = Dict()

  _threads_table_list = List()
  threads = List()
  uart_a_crc_error_count = Int(0)
  uart_a_io_error_count = Int(0)
  uart_a_rx_buffer = Float(0)
  uart_a_tx_buffer = Float(0)
  uart_a_tx_KBps = Float(0)
  uart_a_rx_KBps = Float(0)

  uart_b_crc_error_count = Int(0)
  uart_b_io_error_count = Int(0)
  uart_b_rx_buffer = Float(0)
  uart_b_tx_buffer = Float(0)
  uart_b_tx_KBps = Float(0)
  uart_b_rx_KBps = Float(0)


  ftdi_crc_error_count = Int(0)
  ftdi_io_error_count = Int(0)
  ftdi_rx_buffer = Float(0)
  ftdi_tx_buffer = Float(0)
  ftdi_tx_KBps = Float(0)
  ftdi_rx_KBps = Float(0)

  msg_obs_avg_latency_ms    = Int(0)
  msg_obs_min_latency_ms    = Int(0)
  msg_obs_max_latency_ms    = Int(0)
  msg_obs_window_latency_ms = Int(0)

  msg_obs_avg_period_ms    = Int(0)
  msg_obs_min_period_ms    = Int(0)
  msg_obs_max_period_ms    = Int(0)
  msg_obs_window_period_ms = Int(0)

  _network_info = List()
  
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
           HGroup(
            Spring(width=50, springy=False),
            Item('piksi_reset_button', show_label=False, width=0.50),
            ),
          ),
        VGroup(
          Item('uart_a_crc_error_count', label='CRC Errors', style='readonly'),
          Item('uart_a_io_error_count', label='IO Errors', style='readonly'),
          Item('uart_a_tx_buffer', label='TX Buffer %',
               style='readonly', format_str='%.1f'),
          Item('uart_a_rx_buffer', label='RX Buffer %',
               style='readonly', format_str='%.1f'),
          Item('uart_a_tx_KBps', label='TX KBytes/s',
               style='readonly', format_str='%.2f'),
          Item('uart_a_rx_KBps', label='RX KBytes/s',
               style='readonly', format_str='%.2f'),
          label='UART A', show_border=True,
        ),
        VGroup(
          Item('uart_b_crc_error_count', label='CRC Errors', style='readonly'),
          Item('uart_b_io_error_count', label='IO Errors', style='readonly'),
          Item('uart_b_tx_buffer', label='TX Buffer %',
               style='readonly', format_str='%.1f'),
          Item('uart_b_rx_buffer', label='RX Buffer %',
               style='readonly', format_str='%.1f'),
          Item('uart_b_tx_KBps', label='TX KBytes/s',
               style='readonly', format_str='%.2f'),
          Item('uart_b_rx_KBps', label='RX KBytes/s',
               style='readonly', format_str='%.2f'),
          label='UART B', show_border=True,
        ),
        VGroup(
          Item('ftdi_crc_error_count', label='CRC Errors', style='readonly'),
          Item('ftdi_io_error_count', label='IO Errors', style='readonly'),
          Item('ftdi_tx_buffer', label='TX Buffer %',
               style='readonly', format_str='%.1f'),
          Item('ftdi_rx_buffer', label='RX Buffer %',
               style='readonly', format_str='%.1f'),
          Item('ftdi_tx_KBps', label='TX KBytes/s',
               style='readonly', format_str='%.2f'),
          Item('ftdi_rx_KBps', label='RX KBytes/s',
               style='readonly', format_str='%.2f'),
          label='USB UART', show_border=True,
        ),
        VGroup(
          VGroup(
            Item(
              '_network_info', style = 'readonly',
              editor = TabularEditor(adapter=SimpleNetworkAdapter()),
              show_label=False, width=0.85,
            ),
            show_border=True, label="Network"
           ),
           HGroup(
            Spring(width=50, springy=False),
            Item('network_refresh_button', show_label=False, width=0.50),
            ),
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
    self.link(MsgCommandReq(sequence=1, command='ifconfig'))

  def log_callback(self, m, **metadata):
    if 'IF: ' in m.text:
      self._network_info.append((m.text[4:],))
  
  def uart_state_callback(self, m, **metadata):
    self.uart_a_tx_KBps = m.uart_a.tx_throughput
    self.uart_a_rx_KBps = m.uart_a.rx_throughput
    self.uart_a_crc_error_count = m.uart_a.crc_error_count
    self.uart_a_io_error_count = m.uart_a.io_error_count
    self.uart_a_tx_buffer = 100 * m.uart_a.tx_buffer_level / 255.0
    self.uart_a_rx_buffer = 100 * m.uart_a.rx_buffer_level / 255.0

    self.uart_b_tx_KBps = m.uart_b.tx_throughput
    self.uart_b_rx_KBps = m.uart_b.rx_throughput
    self.uart_b_crc_error_count = m.uart_b.crc_error_count
    self.uart_b_io_error_count = m.uart_b.io_error_count
    self.uart_b_tx_buffer = 100 * m.uart_b.tx_buffer_level / 255.0
    self.uart_b_rx_buffer = 100 * m.uart_b.rx_buffer_level / 255.0

    self.uart_ftdi_tx_KBps = m.uart_ftdi.tx_throughput
    self.uart_ftdi_rx_KBps = m.uart_ftdi.rx_throughput
    self.uart_ftdi_crc_error_count = m.uart_ftdi.crc_error_count
    self.uart_ftdi_io_error_count = m.uart_ftdi.io_error_count
    self.uart_ftdi_tx_buffer = 100 * m.uart_ftdi.tx_buffer_level / 255.0
    self.uart_ftdi_rx_buffer = 100 * m.uart_ftdi.rx_buffer_level / 255.0

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
    super(SystemMonitorView, self).__init__()
    self.link = link
    self.link.add_callback(self.heartbeat_callback, SBP_MSG_HEARTBEAT)
    self.link.add_callback(self.thread_state_callback, SBP_MSG_THREAD_STATE)
    self.link.add_callback(self.uart_state_callback, [SBP_MSG_UART_STATE, SBP_MSG_UART_STATE_DEPA])
    self.link.add_callback(self.log_callback, SBP_MSG_LOG)

    self.python_console_cmds = {
      'mon': self
    }
