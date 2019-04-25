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
from sbp.imu import SBP_MSG_IMU_AUX, SBP_MSG_IMU_RAW
from traits.api import Dict, Float, HasTraits, Instance, Int
from traitsui.api import HGroup, Item, VGroup, View

from .gui_utils import GUI_UPDATE_PERIOD, UpdateScheduler
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


class IMUView(HasTraits):
    python_console_cmds = Dict()
    plot = Instance(Plot)
    plot_data = Instance(ArrayPlotData)
    imu_temp = Float(0)
    imu_conf = Int(0)
    rms_acc_x = Float(0)
    rms_acc_y = Float(0)
    rms_acc_z = Float(0)

    traits_view = View(
        VGroup(
            Item(
                'plot',
                editor=ComponentEditor(bgcolor=(0.8, 0.8, 0.8)),
                show_label=False),
            HGroup(
                Item('imu_temp', format_str='%.2f C', height=-16, width=4),
                Item('imu_conf', format_str='0x%02X', height=-16, width=4),
                Item('rms_acc_x', format_str='%.2f g', height=-16, width=4),
                Item('rms_acc_y', format_str='%.2f g', height=-16, width=4),
                Item('rms_acc_z', format_str='%.2f g', height=-16, width=4),
            ),
        )
    )

    def update_plot(self):
        self.last_plot_update_time = monotonic()
        self.plot_data.set_data('acc_x', self.acc_x)
        self.plot_data.set_data('acc_y', self.acc_y)
        self.plot_data.set_data('acc_z', self.acc_z)
        self.plot_data.set_data('gyr_x', self.gyro_x)
        self.plot_data.set_data('gyr_y', self.gyro_y)
        self.plot_data.set_data('gyr_z', self.gyro_z)

    def imu_set_data(self):
        if monotonic() - self.last_plot_update_time < GUI_UPDATE_PERIOD:
            return
        if self.imu_conf is not None:
            acc_range = self.imu_conf & 0xF
            sf = 2. ** (acc_range + 1) / 2. ** 15
            self.rms_acc_x = sf * np.sqrt(np.mean(np.square(self.acc_x)))
            self.rms_acc_y = sf * np.sqrt(np.mean(np.square(self.acc_y)))
            self.rms_acc_z = sf * np.sqrt(np.mean(np.square(self.acc_z)))
        self.update_scheduler.schedule_update('update_plot', self.update_plot)

    def imu_aux_callback(self, sbp_msg, **metadata):
        if sbp_msg.imu_type == 0:
            self.imu_temp = 23 + sbp_msg.temp / 2. ** 9
            self.imu_conf = sbp_msg.imu_conf
        else:
            print("IMU type %d not known" % sbp_msg.imu_type)

    def imu_raw_callback(self, sbp_msg, **metadata):
        memoryview(self.acc_x)[:-1] = memoryview(self.acc_x)[1:]
        memoryview(self.acc_y)[:-1] = memoryview(self.acc_y)[1:]
        memoryview(self.acc_z)[:-1] = memoryview(self.acc_z)[1:]
        memoryview(self.gyro_x)[:-1] = memoryview(self.gyro_x)[1:]
        memoryview(self.gyro_y)[:-1] = memoryview(self.gyro_y)[1:]
        memoryview(self.gyro_z)[:-1] = memoryview(self.gyro_z)[1:]
        self.acc_x[-1] = sbp_msg.acc_x
        self.acc_y[-1] = sbp_msg.acc_y
        self.acc_z[-1] = sbp_msg.acc_z
        self.gyro_x[-1] = sbp_msg.gyr_x
        self.gyro_y[-1] = sbp_msg.gyr_y
        self.gyro_z[-1] = sbp_msg.gyr_z
        self.imu_set_data()

    def __init__(self, link):
        super(IMUView, self).__init__()

        self.acc_x = np.zeros(NUM_POINTS)
        self.acc_y = np.zeros(NUM_POINTS)
        self.acc_z = np.zeros(NUM_POINTS)
        self.gyro_x = np.zeros(NUM_POINTS)
        self.gyro_y = np.zeros(NUM_POINTS)
        self.gyro_z = np.zeros(NUM_POINTS)

        self.last_plot_update_time = 0

        self.plot_data = ArrayPlotData(
            t=np.arange(NUM_POINTS),
            acc_x=[0.0],
            acc_y=[0.0],
            acc_z=[0.0],
            gyr_x=[0.0],
            gyr_y=[0.0],
            gyr_z=[0.0])

        self.plot = Plot(
            self.plot_data, auto_colors=colours_list, emphasized=True)
        self.plot.title = 'Raw IMU Data'
        self.plot.title_color = [0, 0, 0.43]
        self.ylim = self.plot.value_mapper.range
        self.ylim.low = -32768
        self.ylim.high = 32767
        # self.plot.value_range.bounds_func = lambda l, h, m, tb: (0, h * (1 + m))
        self.plot.value_axis.orientation = 'right'
        self.plot.value_axis.axis_line_visible = False
        self.plot.value_axis.title = 'LSB count'

        self.legend_visible = True
        self.plot.legend.visible = True
        self.plot.legend.align = 'll'
        self.plot.legend.line_spacing = 1
        self.plot.legend.font = 'modern 8'
        self.plot.legend.draw_layer = 'overlay'
        self.plot.legend.tools.append(
            LegendTool(self.plot.legend, drag_button="right"))

        acc_x = self.plot.plot(
            ('t', 'acc_x'), type='line', color='auto', name='Accn. X')
        acc_x = self.plot.plot(
            ('t', 'acc_y'), type='line', color='auto', name='Accn. Y')
        acc_x = self.plot.plot(
            ('t', 'acc_z'), type='line', color='auto', name='Accn. Z')
        acc_x = self.plot.plot(
            ('t', 'gyr_x'), type='line', color='auto', name='Gyro X')
        acc_x = self.plot.plot(
            ('t', 'gyr_y'), type='line', color='auto', name='Gyro Y')
        acc_x = self.plot.plot(
            ('t', 'gyr_z'), type='line', color='auto', name='Gyro Z')

        self.link = link
        self.link.add_callback(self.imu_raw_callback, SBP_MSG_IMU_RAW)
        self.link.add_callback(self.imu_aux_callback, SBP_MSG_IMU_AUX)

        self.python_console_cmds = {'track': self}

        self.update_scheduler = UpdateScheduler()
