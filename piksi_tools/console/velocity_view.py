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

from __future__ import print_function

import numpy as np
from monotonic import monotonic
from chaco.api import ArrayPlotData, Plot
from chaco.tools.api import LegendTool
from enable.api import ComponentEditor
from sbp.navigation import SBP_MSG_VEL_NED
from traits.api import Dict, HasTraits, Instance, Enum
from traitsui.api import HGroup, Item, VGroup, View, Spring

from .gui_utils import GUI_UPDATE_PERIOD, UpdateScheduler
NUM_POINTS = 200
MPS2MPH = 2.236934
MPS2KPH = 3.6
velocity_units_list = ['m/s', 'mph', 'kph']

colors_list = [
    0xE41A1C,
    0x377EB8,
]


class VelocityView(HasTraits):
    python_console_cmds = Dict()
    plot = Instance(Plot)
    velocity_units = Enum(velocity_units_list)
    plot_data = Instance(ArrayPlotData)

    traits_view = View(
        VGroup(
            Spring(height=-2, springy=False),
            HGroup(
                Spring(width=-3, height=8, springy=False),
                Spring(springy=False, width=135),
                Item('velocity_units',
                     label="Display Units"),
                padding=0),
            Item(
                'plot',
                editor=ComponentEditor(bgcolor=(0.8, 0.8, 0.8)),
                label='Velocity',
                show_label=False),
        )
    )

    def _velocity_units_changed(self):
        if self.velocity_units == 'm/s':
            self.vel_sf = 1.0
        elif self.velocity_units == 'mph':
            self.vel_sf = MPS2MPH
        elif self.velocity_units == 'kph':
            self.vel_sf = MPS2KPH
        self.plot.value_axis.title = self.velocity_units

    def update_plot(self):
        self.last_plot_update_time = monotonic()
        self.plot_data.set_data('v_h', self.v_h * self.vel_sf)
        self.plot_data.set_data('v_z', self.v_z * self.vel_sf)
        if any(self.t == 0):
            pass
        else:
            self.plot_data.set_data('t', self.t)

    def vel_ned_callback(self, sbp_msg, **metadata):
        if sbp_msg.flags != 0:
            memoryview(self.v_h)[:-1] = memoryview(self.v_h)[1:]
            memoryview(self.v_z)[:-1] = memoryview(self.v_z)[1:]
            memoryview(self.t)[:-1] = memoryview(self.t)[1:]
            self.v_h[-1] = np.sqrt(sbp_msg.n * sbp_msg.n + sbp_msg.e * sbp_msg.e) / 1000.0
            self.v_z[-1] = -sbp_msg.d / 1000.0
            self.t[-1] = sbp_msg.tow / 1000.0

        if monotonic() - self.last_plot_update_time < GUI_UPDATE_PERIOD:
            return
        self.update_scheduler.schedule_update('update_plot', self.update_plot)

    def __init__(self, link):
        super(VelocityView, self).__init__()
        self.velocity_units = 'm/s'
        self.vel_sf = 1.0
        self.v_h = np.zeros(NUM_POINTS)
        self.v_z = np.zeros(NUM_POINTS)
        self.t = np.zeros(NUM_POINTS)

        self.last_plot_update_time = 0

        self.plot_data = ArrayPlotData(
            t=np.arange(NUM_POINTS),
            v_h=[0.0],
            v_z=[0.0]
        )
        self.plot = Plot(
            self.plot_data, auto_colors=colors_list, emphasized=True)
        self.plot.title_color = [0, 0, 0.43]
        self.plot.value_axis.orientation = 'right'
        self.plot.value_axis.axis_line_visible = False
        self.plot.value_axis.title = 'm/s'
        self.plot.value_axis.font = 'modern 8'
        self.plot.index_axis.title = 'GPS Time of Week'
        self.plot.index_axis.title_spacing = 40
        self.plot.index_axis.tick_label_font = 'modern 8'
        self.plot.value_axis.tick_color = 'gray'
        self.plot.index_axis.tick_label_rotate_angle = -45
        self.plot.title_visible = False
        self.legend_visible = True
        self.plot.legend.visible = True
        self.plot.legend.align = 'll'
        self.plot.legend.line_spacing = 1
        self.plot.legend.font = 'modern 8'
        self.plot.legend.draw_layer = 'overlay'
        self.plot.legend.tools.append(
            LegendTool(self.plot.legend, drag_button="right"))
        self.plot.padding_left = 35
        self.plot.padding_bottom = 60
        self.plot_paddint_top = -1
        self.plot.padding_right = 60

        self.plot.plot(
            ('t', 'v_h'), type='line', color='auto', name='Horizontal')
        self.plot.plot(
            ('t', 'v_z'), type='line', color='auto', name='Vertical')

        self.link = link
        self.link.add_callback(self.vel_ned_callback, SBP_MSG_VEL_NED)

        self.python_console_cmds = {'vel': self}

        self.update_scheduler = UpdateScheduler()
