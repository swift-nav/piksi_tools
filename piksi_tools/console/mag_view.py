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
from chaco.api import ArrayPlotData, Plot
from chaco.tools.api import LegendTool
from enable.api import ComponentEditor
from sbp.mag import SBP_MSG_MAG_RAW
from traits.api import Dict, HasTraits, Instance
from traitsui.api import Item, VGroup, View

from piksi_tools.console.utils import call_repeatedly

NUM_POINTS = 200

colours_list = [
    0xE41A1C,
    0x377EB8,
    0x4DAF4A,
    0x984EA3,
    0xFF7F00,
    0xFFFF33,
    0xA65628,
    0xF781BF,
]


class MagView(HasTraits):
    python_console_cmds = Dict()
    plot = Instance(Plot)
    plot_data = Instance(ArrayPlotData)

    traits_view = View(
        VGroup(
            Item(
                'plot',
                editor=ComponentEditor(bgcolor=(0.8, 0.8, 0.8)),
                show_label=False),
        )
    )

    def mag_set_data(self):
        self.plot_data.set_data('mag_x', self.mag[:, 0])
        self.plot_data.set_data('mag_y', self.mag[:, 1])
        self.plot_data.set_data('mag_z', self.mag[:, 2])

    def mag_raw_callback(self, sbp_msg, **metadata):
        self.mag[:-1, :] = self.mag[1:, :]
        self.mag[-1] = (sbp_msg.mag_x / 16.0,
                        sbp_msg.mag_y / 16.0,
                        sbp_msg.mag_z / 16.0)

    def __init__(self, link):
        super(MagView, self).__init__()

        self.mag = np.zeros((NUM_POINTS, 3))

        self.plot_data = ArrayPlotData(
            t=np.arange(NUM_POINTS),
            mag_x=[0.0],
            mag_y=[0.0],
            mag_z=[0.0])

        self.plot = Plot(
            self.plot_data, auto_colors=colours_list, emphasized=True)
        self.plot.title = 'Raw Magnetometer Data'
        self.plot.title_color = [0, 0, 0.43]
        self.ylim = self.plot.value_mapper.range
        self.ylim.low = -150
        self.ylim.high = 150
        # self.plot.value_range.bounds_func = lambda l, h, m, tb: (0, h * (1 + m))
        self.plot.value_axis.orientation = 'right'
        self.plot.value_axis.axis_line_visible = False
        self.plot.value_axis.title = 'LSB count'
        call_repeatedly(0.2, self.mag_set_data)

        self.legend_visible = True
        self.plot.legend.visible = True
        self.plot.legend.align = 'll'
        self.plot.legend.line_spacing = 1
        self.plot.legend.font = 'modern 8'
        self.plot.legend.draw_layer = 'overlay'
        self.plot.legend.tools.append(
            LegendTool(self.plot.legend, drag_button="right"))

        mag_x = self.plot.plot(
            ('t', 'mag_x'), type='line', color='auto', name='Mag. X (uT)')
        mag_y = self.plot.plot(
            ('t', 'mag_y'), type='line', color='auto', name='Mag. Y (uT)')
        mag_z = self.plot.plot(
            ('t', 'mag_z'), type='line', color='auto', name='Mag. Z (uT)')

        self.link = link
        self.link.add_callback(self.mag_raw_callback, SBP_MSG_MAG_RAW)
        self.python_console_cmds = {'track': self}
