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

from sbp.piksi import (SBP_MSG_THREAD_STATE,
                       SBP_MSG_UART_STATE, SBP_MSG_UART_STATE_DEPA,
                       SBP_MSG_DEVICE_MONITOR, MsgReset)
from sbp.system import SBP_MSG_HEARTBEAT, SBP_MSG_CSAC_TELEMETRY, SBP_MSG_CSAC_TELEMETRY_LABELS
from traits.api import Dict, HasTraits, Int, Float, List, Bool
from traits.etsconfig.api import ETSConfig
from traitsui.api import HGroup, Item, TabularEditor, VGroup, View
from piksi_tools.console.gui_utils import ReadOnlyTabularAdapter

from .utils import resource_filename

if ETSConfig.toolkit != 'null':
    from enable.savage.trait_defs.ui.svg_button import SVGButton


def ip_bytes_to_string(ip_bytes):
    return '.'.join(str(x) for x in ip_bytes)


class SimpleAdapter(ReadOnlyTabularAdapter):
    columns = [('Thread Name', 0), ('CPU %', 1), ('Stack Free', 2)]


class SimpleCSACAdapter(ReadOnlyTabularAdapter):
    columns = [('Metric Name', 0), ('Value', 1)]


class SystemMonitorView(HasTraits):
    python_console_cmds = Dict()

    _threads_table_list = List()
    _csac_telem_list = List()
    _csac_received = Bool(False)
    threads = List()

    msg_obs_avg_latency_ms = Int(0)
    msg_obs_min_latency_ms = Int(0)
    msg_obs_max_latency_ms = Int(0)
    msg_obs_window_latency_ms = Int(0)

    msg_obs_avg_period_ms = Int(0)
    msg_obs_min_period_ms = Int(0)
    msg_obs_max_period_ms = Int(0)
    msg_obs_window_period_ms = Float(0)

    zynq_temp = Float(0)
    fe_temp = Float(0)

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
                            show_border=True
                        ),
                        show_border=True,
                        label="Observation Connection Monitor"),
                    Item('piksi_reset_button', show_label=False, width=0.50)
                ),
                VGroup(
                    Item(
                        'zynq_temp',
                        label='Zynq CPU Temp',
                        style='readonly',
                        format_str='%.1fC'),
                    Item(
                        'fe_temp',
                        label='RF Frontend Temp',
                        style='readonly',
                        format_str='%.1fC'),
                    show_border=True,
                    label="Device Monitor",
                ),
                VGroup(
                    Item(
                        '_csac_telem_list',
                        style='readonly',
                        editor=TabularEditor(adapter=SimpleCSACAdapter()),
                        show_label=False),
                    show_border=True,
                    label="Metrics",
                    visible_when='_csac_received'
                )
            )
        ),
    )

    def update_threads(self):
        self._threads_table_list = [
            (thread_name.decode('ascii', 'replace'), state.cpu, state.stack_free)
            for thread_name, state in sorted(
                self.threads, key=lambda x: x[1].cpu, reverse=True)
        ]

    def update_network_state(self):
        self._network_refresh_button_fired()

    def heartbeat_callback(self, sbp_msg, **metadata):
        if self.threads != []:
            self.update_threads()
            self.threads = []

    def device_callback(self, sbp_msg, **metadata):
        self.zynq_temp = float(sbp_msg.cpu_temperature) / 100.
        self.fe_temp = float(sbp_msg.fe_temperature) / 100.

    def thread_state_callback(self, sbp_msg, **metadata):
        if sbp_msg.name == '':
            sbp_msg.name = '(no name)'
        sbp_msg.cpu //= 10
        self.threads.append((sbp_msg.name, sbp_msg))

    def csac_header_callback(self, sbp_msg, **metadata):
        self.headers = sbp_msg.telemetry_labels.split(',')
        self.telem_header_index = sbp_msg.id

    def csac_telem_callback(self, sbp_msg, **metadata):
        self._csac_telem_list = []
        if self.telem_header_index is not None:
            if sbp_msg.id == self.telem_header_index:
                self._csac_received = True
                metrics_of_interest = ['Status', 'Alarm', 'Mode', 'Phase', 'DiscOK']
                telems = sbp_msg.telemetry.split(',')
                for i, each in enumerate(self.headers):
                    if each in metrics_of_interest:
                        self._csac_telem_list.append((each, telems[i]))

    def _piksi_reset_button_fired(self):
        self.link(MsgReset(flags=0))

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
        self.telem_header_index = None
        self.link.add_callback(self.heartbeat_callback, SBP_MSG_HEARTBEAT)
        self.link.add_callback(self.device_callback, SBP_MSG_DEVICE_MONITOR)
        self.link.add_callback(self.thread_state_callback,
                               SBP_MSG_THREAD_STATE)
        self.link.add_callback(self.uart_state_callback,
                               [SBP_MSG_UART_STATE, SBP_MSG_UART_STATE_DEPA])
        self.link.add_callback(self.csac_telem_callback,
                               SBP_MSG_CSAC_TELEMETRY)
        self.link.add_callback(self.csac_header_callback,
                               SBP_MSG_CSAC_TELEMETRY_LABELS)

        self.python_console_cmds = {'mon': self}
