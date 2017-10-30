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
from collections import defaultdict

import numpy as np
from chaco.api import ArrayPlotData, Plot
from chaco.tools.api import LegendTool
from enable.api import ComponentEditor
from pyface.api import GUI
from sbp.tracking import SBP_MSG_TRACKING_STATE, SBP_MSG_TRACKING_STATE_DEP_B
from traits.api import Bool, Dict, Instance, List
from traitsui.api import HGroup, Item, Spring, VGroup, View

from piksi_tools.acq_results import SNR_THRESHOLD
from piksi_tools.console.gui_utils import CodeFiltered
from piksi_tools.console.utils import (SUPPORTED_CODES,
                                       code_is_glo,
                                       code_is_gps,
                                       code_is_sbas,
                                       code_is_bds2,
                                       code_is_qzss,
                                       code_to_str)

NUM_POINTS = 200
TRK_RATE = 2.0

GLO_FCN_OFFSET = 8

# These colors should be distinguishable from eachother
color_dict = {
    '(0, 1)':  0x0000ff,
    '(0, 2)':  0x00ff00,
    '(0, 3)':  0xff0000,
    '(0, 4)':  0x000035,
    '(0, 5)':  0xff00b0,
    '(0, 6)':  0x004f00,
    '(0, 7)':  0xffd300,
    '(0, 8)':  0x009eff,
    '(0, 9)':  0x9e4f46,
    '(0, 10)': 0x35ffb9,
    '(0, 11)': 0x7235b9,
    '(0, 12)': 0x127b84,
    '(0, 13)': 0xffb0ff,
    '(0, 14)': 0x7bb91a,
    '(0, 15)': 0xd37200,
    '(0, 16)': 0xc1b06a,
    '(0, 17)': 0xe500ff,
    '(0, 18)': 0x231a00,
    '(0, 19)': 0xed0958,
    '(0, 20)': 0x7b0058,
    '(0, 21)': 0x4ff6ff,
    '(0, 22)': 0x7b6a95,
    '(0, 23)': 0x58a772,
    '(0, 24)': 0x6a4f00,
    '(0, 25)': 0xdcff00,
    '(0, 26)': 0x9e0000,
    '(0, 27)': 0xffb0b0,
    '(0, 28)': 0xcaff9e,
    '(0, 29)': 0x00469e,
    '(0, 30)': 0xed72ff,
    '(0, 31)': 0x95caf6,
    '(0, 32)': 0xed6a9e,
    '(0, 33)': 0x6aff72,
    '(0, 34)': 0x847b6a,
    '(0, 35)': 0xff7b61,
    '(0, 36)': 0x2372ff,
    '(0, 37)': 0x3e001a
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
    key = str((0, sat))
    color = color_dict.get(key, 0xff0000)
    return color


def get_label(key, extra):
    code, sat, ch = key
    lbl = 'Ch {ch:02d}: {code} '.format(ch=ch, code=code_to_str(code))

    if code_is_glo(code):
        lbl += 'F{sat:0=+3d}'.format(sat=sat)
        if sat in extra:
            lbl += ' R{slot:02d}'.format(slot=extra[sat])
    elif code_is_sbas(code):
        lbl += 'S{sat:3d}'.format(sat=sat)
    elif code_is_bds2(code):
        lbl += 'C{sat:02d}'.format(sat=sat)
    elif code_is_sbas(code):
        lbl += 'J{sat:3d}'.format(sat=sat)
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

    def tracking_state_callback(self, sbp_msg, **metadata):
        t = time.time() - self.t_init
        self.time[0:-1] = self.time[1:]
        self.time[-1] = t
        # first we loop over all the SIDs / channel keys we have stored and set 0 in for CN0
        for key, cno_array in self.CN0_dict.items():
            # p
            if (cno_array == 0).all():
                self.CN0_dict.pop(key)
            else:
                new_arr = np.roll(cno_array, -1)
                new_arr[-1] = 0
                self.CN0_dict[key] = new_arr

        # If the whole array is 0 we remove it
        # for each satellite, we have a (code, prn, channel) keyed dict
        # for each SID, an array of size MAX PLOT with the history of CN0's stored
        # If there is no CN0 or not tracking for an epoch, 0 will be used
        # each array can be plotted against host_time, t
        for i, s in enumerate(sbp_msg.states):
            if code_is_glo(s.sid.code):
                sat = s.fcn - GLO_FCN_OFFSET
                self.glo_slot_dict[sat] = s.sid.sat
            else:
                sat = s.sid.sat
            key = (s.sid.code, sat, i)
            if s.cn0 != 0:
                self.CN0_dict[key][-1] = s.cn0 / 4.0

        GUI.invoke_later(self.update_plot)

    def tracking_state_callback_dep_b(self, sbp_msg, **metadata):
        t = time.time() - self.t_init
        self.time[0:-1] = self.time[1:]
        self.time[-1] = t
        # first we loop over all the SIDs / channel keys we have stored and set 0 in for CN0
        for key, cno_array in self.CN0_dict.items():
            # p
            if (cno_array == 0).all():
                self.CN0_dict.pop(key)
            else:
                self.CN0_dict[key][0:-1] = cno_array[1:]
                self.CN0_dict[key][-1] = 0
            # If the whole array is 0 we remove it
            # for each satellite, we have a (code, prn, channel) keyed dict
            # for each SID, an array of size MAX PLOT with the history of CN0's stored
            # If there is no CN0 or not tracking for an epoch, 0 will be used
            # each array can be plotted against host_time, t
        for i, s in enumerate(sbp_msg.states):
            prn = s.sid.sat
            if code_is_gps(s.sid.code):
                prn += 1
            key = (s.sid.code, prn, i)
            if s.state != 0:
                if len(self.CN0_dict.get(key, [])) == 0:
                    self.CN0_dict[key] = np.zeros(NUM_POINTS)
                self.CN0_dict[key][-1] = s.cn0
        GUI.invoke_later(self.update_plot)

    def update_plot(self):
        plot_labels = []
        plots = []
        self.plot_data.set_data('t', self.time)
        # Remove any stale plots that got removed from the dictionary
        for each in self.plot_data.list_data():
            if each not in [str(a)
                            for a in self.CN0_dict.keys()] and each != 't':
                try:
                    self.plot_data.del_data(each)
                    self.plot.delplot(each)
                except KeyError:
                    pass
        for k, cno_array in self.CN0_dict.items():
            if int(k[0]) not in SUPPORTED_CODES:
                continue
            key = str(k)
            # set plot data and create plot for any selected for display
            if (getattr(self, 'show_{}'.format(int(k[0])))):
                self.plot_data.set_data(key, cno_array)
                if key not in self.plot.plots.keys():
                    pl = self.plot.plot(
                        ('t', key), type='line', color=get_color(k), name=key)
                else:
                    pl = self.plot.plots[key]
                # if channel is still active:
                if cno_array[-1] != 0:
                    plots.append(pl)
                    plot_labels.append(get_label(k, self.glo_slot_dict))
            # Remove plot data and plots not selected
            else:
                if key in self.plot_data.list_data():
                    self.plot_data.del_data(key)
                if key in self.plot.plots.keys():
                    self.plot.delplot(key)
        plots = dict(zip(plot_labels, plots))
        self.plot.legend.plots = plots

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
        self.time = [x * 1 / TRK_RATE for x in range(-NUM_POINTS, 0, 1)]
        self.CN0_dict = defaultdict(lambda: np.zeros(NUM_POINTS))
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
        self.link.add_callback(self.tracking_state_callback,
                               SBP_MSG_TRACKING_STATE)
        self.link.add_callback(self.tracking_state_callback_dep_b,
                               SBP_MSG_TRACKING_STATE_DEP_B)
        self.python_console_cmds = {'track': self}
