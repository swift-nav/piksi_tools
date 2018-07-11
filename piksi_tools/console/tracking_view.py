#!/usr/bin/env python
# Copyright (C) 2011-2014, 2016 Swift Navigation Inc.
# Contact: Fergus Noble <fergus@swift-nav.com>
#          Pasi Miettinen <pasi.miettinen@exafore.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

import time
from collections import defaultdict, deque
import threading
from pyface.api import GUI
from chaco.api import ArrayPlotData, Plot
from chaco.tools.api import LegendTool
from enable.api import ComponentEditor
from sbp.tracking import SBP_MSG_MEASUREMENT_STATE, SBP_MSG_TRACKING_STATE
from traits.api import Bool, Dict, Instance, List
from traitsui.api import HGroup, Item, Spring, VGroup, View

from piksi_tools.acq_results import SNR_THRESHOLD
from piksi_tools.console.gui_utils import CodeFiltered
from piksi_tools.console.utils import (code_is_glo,
                                       code_is_sbas,
                                       code_is_bds,
                                       code_is_galileo,
                                       code_is_qzss,
                                       code_to_str)

NUM_POINTS = 200
TRK_RATE = 2.0

GLO_FCN_OFFSET = 8
# These colors should be distinguishable from eachother
color_dict = {
    '(0, 1)': 0xe58a8a,
    '(0, 2)': 0x664949,
    '(0, 3)': 0x590c00,
    '(0, 4)': 0xcc4631,
    '(0, 5)': 0xe56c1c,
    '(0, 6)': 0x4c2a12,
    '(0, 7)': 0x996325,
    '(0, 8)': 0xf2b774,
    '(0, 9)': 0xffaa00,
    '(0, 10)': 0xccb993,
    '(0, 11)': 0x997a00,
    '(0, 12)': 0x4c4700,
    '(0, 13)': 0xd0d94e,
    '(0, 14)': 0xaaff00,
    '(0, 15)': 0x4ea614,
    '(0, 16)': 0x123306,
    '(0, 17)': 0x18660c,
    '(0, 18)': 0x6e9974,
    '(0, 19)': 0x8ae6a2,
    '(0, 20)': 0x00ff66,
    '(0, 21)': 0x57f2e8,
    '(0, 22)': 0x1f7980,
    '(0, 23)': 0x263e40,
    '(0, 24)': 0x004d73,
    '(0, 25)': 0x37abe6,
    '(0, 26)': 0x7790a6,
    '(0, 27)': 0x144ea6,
    '(0, 28)': 0x263040,
    '(0, 29)': 0x152859,
    '(0, 30)': 0x1d39f2,
    '(0, 31)': 0x828ed9,
    '(0, 32)': 0x000073,
    '(0, 33)': 0x000066,
    '(0, 34)': 0x8c7aff,
    '(0, 35)': 0x1b0033,
    '(0, 36)': 0xd900ca,
    '(0, 37)': 0x730e6c,
}


def get_color(key):
    code, sat, ch = key

    # reuse palatte for glo signals
    if code_is_glo(code):
        sat += GLO_FCN_OFFSET
    elif code_is_sbas(code):
        sat -= 120
    elif code_is_qzss(code):
        sat -= 193
    if sat > 37:
        sat = sat % 37
    key = str((0, sat))
    color = color_dict.get(key, 0xff0000)
    return color


def get_label(key, extra):
    code, sat, ch = key
    lbl = 'Ch {ch:02d}: {code} '.format(ch=ch, code=code_to_str(code))

    if code_is_glo(code):
        lbl += 'F{sat:0=+3d}'.format(sat=sat)
        if ch in extra:
            lbl += ' R{slot:02d}'.format(slot=extra[ch])
    elif code_is_sbas(code):
        lbl += 'S{sat:3d}'.format(sat=sat)
    elif code_is_bds(code):
        lbl += 'C{sat:02d}'.format(sat=sat)
    elif code_is_qzss(code):
        lbl += 'J{sat:3d}'.format(sat=sat)
    elif code_is_galileo(code):
        lbl += 'E{sat:02d}'.format(sat=sat)
    else:
        lbl += 'G{sat:02d}'.format(sat=sat)

    return lbl


class TrackingView(CodeFiltered):
    python_console_cmds = Dict()
    legend_visible = Bool()
    plot = Instance(Plot)
    plots = List()
    plot_data = Instance(ArrayPlotData)

    traits_view = View(
        VGroup(
            Item(
                'plot',
                editor=ComponentEditor(bgcolor=(0.8, 0.8, 0.8)),
                show_label=False, ),
            HGroup(
                Spring(width=8, springy=False),
                Item('legend_visible', label="Show Legend:"),
                CodeFiltered.get_filter_group(), )))

    def measurement_state_callback(self, sbp_msg, **metadata):
        codes_that_came = []
        t = time.time() - self.t_init
        self.time.append(t)
        self.CN0_lock.acquire()
        # first we loop over all the SIDs / channel keys we have stored and set 0 in for CN0
        for i, s in enumerate(sbp_msg.states):
            if code_is_glo(s.mesid.code):
                # for Glonass satellites, store in two dictionaries FCN and SLOT
                # so that they can both be retrieved when displaying the channel
                if (s.mesid.sat > 90):
                    self.glo_fcn_dict[i] = s.mesid.sat - 100
                else:
                    self.glo_slot_dict[i] = s.mesid.sat
                sat = self.glo_fcn_dict.get(i, 0)
            else:
                sat = s.mesid.sat
            key = (s.mesid.code, sat, i)
            codes_that_came.append(key)
            if s.cn0 != 0:
                self.CN0_dict[key].append(s.cn0 / 4.0)
            received_code_list = getattr(self, "received_codes", [])
            if s.mesid.code not in received_code_list:
                received_code_list.append(s.mesid.code)
                self.received_codes = received_code_list
        for key, cno_array in self.CN0_dict.items():
            if key not in codes_that_came:
                cno_array.append(0)
        self.CN0_lock.release()
        GUI.invoke_later(self.update_plot)

    def tracking_state_callback(self, sbp_msg, **metadata):
        codes_that_came = []
        self.CN0_lock.acquire()
        t = time.time() - self.t_init
        self.time.append(t)
        # first we loop over all the SIDs / channel keys we have stored and set 0 in for CN0
        # for each SID, an array of size MAX PLOT with the history of CN0's stored
        # If there is no CN0 or not tracking for an epoch, 0 will be used
        # each array can be plotted against host_time, t
        for i, s in enumerate(sbp_msg.states):
            if code_is_glo(s.sid.code):
                sat = s.fcn - GLO_FCN_OFFSET
                self.glo_slot_dict[i] = s.sid.sat
            else:
                sat = s.sid.sat
            key = (s.sid.code, sat, i)
            codes_that_came.append(key)
            if s.cn0 != 0:
                self.CN0_dict[key].append(s.cn0 / 4.0)
            received_code_list = getattr(self, "received_codes", [])
            if s.sid.code not in received_code_list:
                received_code_list.append(s.sid.code)
                self.received_codes = received_code_list
        for key, cno_array in self.CN0_dict.items():
            if key not in codes_that_came:
                cno_array.append(0)
        self.CN0_lock.release()
        GUI.invoke_later(self.update_plot)

    def update_plot(self):
        self.CN0_lock.acquire()
        plot_labels = []
        plots = []
        # Update the underlying plot data from the CN0_dict for selected items
        new_plot_data = {'t': self.time}
        for k, cno_array in self.CN0_dict.items():
            key = str(k)
            # set plot data
            if (getattr(self, 'show_{}'.format(int(k[0])), True)):
                new_plot_data[key] = cno_array
        self.plot_data.update_data(new_plot_data)
        # Remove any stale plots that got removed from the dictionary
        for each in self.plot.plots.keys():
            if each not in [str(a) for a in self.CN0_dict.keys()] and each != 't':
                try:
                    self.plot.delplot(each)
                except KeyError:
                    pass
        # add/remove plot as neccesary and build legend
        for k, cno_array in self.CN0_dict.items():
            key = str(k)
            if (getattr(self, 'show_{}'.format(int(k[0])), True) and
               not cno_array.count(0) == NUM_POINTS):
                if key not in self.plot.plots.keys():
                    pl = self.plot.plot(('t', key), type='line',
                                        color=get_color(k), name=key)
                else:
                    pl = self.plot.plots[key]
                plots.append(pl)
                plot_labels.append(get_label(k, self.glo_slot_dict))
            # if not selected or all 0, remove
            else:
                if key in self.plot.plots.keys():
                    self.plot.delplot(key)
        plots = dict(zip(plot_labels, plots))
        self.plot.legend.plots = plots
        self.CN0_lock.release()

    def _legend_visible_changed(self):
        if self.plot:
            if not self.legend_visible:
                self.plot.legend.visible = False
            else:
                self.plot.legend.visible = True
            self.plot.legend.tools.append(
                LegendTool(self.plot.legend, drag_button="right"))

    def __init__(self, link):
        super(TrackingView, self).__init__()
        self.t_init = time.time()
        self.time = deque([x * 1 / TRK_RATE for x in range(-NUM_POINTS, 0, 1)], maxlen=NUM_POINTS)
        self.CN0_lock = threading.Lock()
        self.CN0_dict = defaultdict(lambda: deque([0] * NUM_POINTS, maxlen=NUM_POINTS))
        self.glo_fcn_dict = {}
        self.glo_slot_dict = {}
        self.n_channels = None
        self.plot_data = ArrayPlotData(t=[0.0])
        self.plot = Plot(self.plot_data, emphasized=True)
        self.plot.title = 'Tracking C/N0'
        self.plot.title_color = [0, 0, 0.43]
        self.ylim = self.plot.value_mapper.range
        self.ylim.low = SNR_THRESHOLD
        self.ylim.high = 60
        self.plot.value_range.bounds_func = lambda l, h, m, tb: (0, h * (1 + m))
        self.plot.value_axis.orientation = 'right'
        self.plot.value_axis.axis_line_visible = False
        self.plot.value_axis.title = 'dB-Hz'
        self.plot_data.set_data('t', self.time)
        self.plot.index_axis.title = 'seconds'
        self.plot.index_range.bounds_func = lambda l, h, m, tb: (h - 100, h)
        self.legend_visible = True
        self.plot.legend.visible = True
        self.plot.legend.align = 'll'
        self.plot.legend.line_spacing = 1
        self.plot.legend.font = 'monospace 8'
        self.plot.legend.draw_layer = 'overlay'
        self.plot.legend.tools.append(
            LegendTool(self.plot.legend, drag_button="right"))
        self.link = link
        self.link.add_callback(self.measurement_state_callback,
                               SBP_MSG_MEASUREMENT_STATE)
        self.link.add_callback(self.tracking_state_callback,
                               SBP_MSG_TRACKING_STATE)
        self.python_console_cmds = {'track': self}
