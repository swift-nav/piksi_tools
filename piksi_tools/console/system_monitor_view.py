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

from __future__ import absolute_import

from sbp.piksi import (SBP_MSG_NETWORK_STATE_RESP, SBP_MSG_THREAD_STATE,
                       SBP_MSG_UART_STATE, SBP_MSG_UART_STATE_DEPA,
                       MsgNetworkStateReq, MsgReset)
from sbp.system import SBP_MSG_HEARTBEAT
from traits.api import Dict, HasTraits, Int, List
from traits.etsconfig.api import ETSConfig
from traitsui.api import HGroup, Item, TabularEditor, VGroup, View
from traitsui.tabular_adapter import TabularAdapter

from .utils import resource_filename, sizeof_fmt

if ETSConfig.toolkit != 'null':
    from enable.savage.trait_defs.ui.svg_button import SVGButton


def ip_bytes_to_string(ip_bytes):
    return '.'.join(str(x) for x in ip_bytes)


class SimpleAdapter(TabularAdapter):
    columns = [('Thread Name', 0), ('CPU %', 1), ('Stack Free', 2)]


class SystemMonitorView(HasTraits):
    python_console_cmds = Dict()

    _threads_table_list = List()
    threads = List()

    _network_info = List()

    msg_obs_avg_latency_ms = Int(0)
    msg_obs_min_latency_ms = Int(0)
    msg_obs_max_latency_ms = Int(0)
    msg_obs_window_latency_ms = Int(0)

    msg_obs_avg_period_ms = Int(0)
    msg_obs_min_period_ms = Int(0)
    msg_obs_max_period_ms = Int(0)
    msg_obs_window_period_ms = Int(0)

    piksi_reset_button = SVGButton(
        label='Reset Device',
        tooltip='Reset Device',
        filename=resource_filename('console/images/fontawesome/power27.svg'),
        width=16,
        height=16,
        aligment='center')

    traits_view = View(
        VGroup(
            Item(
                '_threads_table_list',
                style='readonly',
                editor=TabularEditor(adapter=SimpleAdapter()),
                show_label=False,
                width=0.85, ),
            HGroup(
                VGroup(
                    HGroup(
                        VGroup(
                            Item(
                                'msg_obs_window_latency_ms',
                                label='Curr',
                                style='readonly',
                                format_str='%dms'),
                            Item(
                                'msg_obs_avg_latency_ms',
                                label='Avg',
                                style='readonly',
                                format_str='%dms'),
                            Item(
                                'msg_obs_min_latency_ms',
                                label='Min',
                                style='readonly',
                                format_str='%dms'),
                            Item(
                                'msg_obs_max_latency_ms',
                                label='Max',
                                style='readonly',
                                format_str='%dms'),
                            label='Latency',
                            show_border=True),
                        VGroup(
                            Item(
                                'msg_obs_window_period_ms',
                                label='Curr',
                                style='readonly',
                                format_str='%dms'),
                            Item(
                                'msg_obs_avg_period_ms',
                                label='Avg',
                                style='readonly',
                                format_str='%dms'),
                            Item(
                                'msg_obs_min_period_ms',
                                label='Min',
                                style='readonly',
                                format_str='%dms'),
                            Item(
                                'msg_obs_max_period_ms',
                                label='Max',
                                style='readonly',
                                format_str='%dms'),
                            label='Period',
                            show_border=True, ),
                        show_border=True,
                        label="Observation Connection Monitor"),
                    Item('piksi_reset_button', show_label=False, width=0.50)
                ),
            ),
        )
    )

    def update_threads(self):
        self._threads_table_list = [
            (thread_name, state.cpu, state.stack_free)
            for thread_name, state in sorted(
                self.threads, key=lambda x: x[1].cpu, reverse=True)
        ]

    def update_network_state(self):
        self._network_refresh_button_fired()

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
        self._network_info.append(
            (m.interface_name, ip_bytes_to_string(m.ipv4_address),
             ((m.flags & (1 << 6)) != 0),
             sizeof_fmt(m.tx_bytes), sizeof_fmt(m.rx_bytes)))

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
        super(SystemMonitorView, self).__init__()
        self.link = link
        self.link.add_callback(self.heartbeat_callback, SBP_MSG_HEARTBEAT)
        self.link.add_callback(self.thread_state_callback,
                               SBP_MSG_THREAD_STATE)
        self.link.add_callback(self.uart_state_callback,
                               [SBP_MSG_UART_STATE, SBP_MSG_UART_STATE_DEPA])
        self.link.add_callback(self._network_callback,
                               SBP_MSG_NETWORK_STATE_RESP)

        self.python_console_cmds = {'mon': self}
