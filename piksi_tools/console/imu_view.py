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

from chaco.api import ArrayPlotData, Plot
from chaco.tools.api import LegendTool
from enable.api import ComponentEditor
from pyface.api import GUI
from sbp.imu import SBP_MSG_IMU_RAW
from traits.api import Instance, Dict, HasTraits, Float, List, Int, Bool
from traitsui.api import Item, View, HSplit, VGroup, HGroup
import numpy as np
from piksi_tools.acq_results import SNR_THRESHOLD
from piksi_tools.console.utils import code_to_str, code_is_gps

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

  traits_view = View(
    VGroup(
      Item(
        'plot',
        editor=ComponentEditor(bgcolor=(0.8, 0.8, 0.8)),
        show_label=False,
      )
    )
  )

  def imu_raw_callback(self, sbp_msg, **metadata):
      self.acc[:-1,:] = self.acc[1:,:]
      self.gyro[:-1,:] = self.gyro[1:,:]
      self.acc[-1] = (sbp_msg.acc_x, sbp_msg.acc_y, sbp_msg.acc_z)
      self.gyro[-1] = (sbp_msg.gyr_x, sbp_msg.gyr_y, sbp_msg.gyr_z)
      self.plot_data.set_data('acc_x', self.acc[:,0])
      self.plot_data.set_data('acc_y', self.acc[:,1])
      self.plot_data.set_data('acc_z', self.acc[:,2])
      self.plot_data.set_data('gyr_x', self.gyro[:,0])
      self.plot_data.set_data('gyr_y', self.gyro[:,1])
      self.plot_data.set_data('gyr_z', self.gyro[:,2])

  def __init__(self, link):
    super(IMUView, self).__init__()

    self.acc = np.empty((NUM_POINTS, 3))
    self.gyro = np.empty((NUM_POINTS, 3))

    self.plot_data = ArrayPlotData(t=np.arange(NUM_POINTS),
                                   acc_x=[0.0], acc_y=[0.0], acc_z=[0.0],
                                   gyr_x=[0.0], gyr_y=[0.0], gyr_z=[0.0])

    self.plot = Plot(self.plot_data, auto_colors=colours_list, emphasized=True)
    self.plot.title = 'Raw IMU Data'
    self.plot.title_color = [0, 0, 0.43]
    self.ylim = self.plot.value_mapper.range
    self.ylim.low = -32768
    self.ylim.high = 32767
    #self.plot.value_range.bounds_func = lambda l, h, m, tb: (0, h * (1 + m))
    self.plot.value_axis.orientation = 'right'
    self.plot.value_axis.axis_line_visible = False
    self.plot.value_axis.title = 'LSB count'

    self.legend_visible = True
    self.plot.legend.visible = True
    self.plot.legend.align = 'll'
    self.plot.legend.line_spacing = 1
    self.plot.legend.font = 'modern 8'
    self.plot.legend.draw_layer= 'overlay'
    self.plot.legend.tools.append(LegendTool(self.plot.legend,
                                  drag_button="right"))

    acc_x = self.plot.plot(('t', 'acc_x'), type='line', color='auto',
                           name='Accn. X')
    acc_x = self.plot.plot(('t', 'acc_y'), type='line', color='auto',
                           name='Accn. Y')
    acc_x = self.plot.plot(('t', 'acc_z'), type='line', color='auto',
                           name='Accn. Z')
    acc_x = self.plot.plot(('t', 'gyr_x'), type='line', color='auto',
                           name='Gyro X')
    acc_x = self.plot.plot(('t', 'gyr_y'), type='line', color='auto',
                           name='Gyro Y')
    acc_x = self.plot.plot(('t', 'gyr_z'), type='line', color='auto',
                           name='Gyro Z')

    self.link = link
    self.link.add_callback(self.imu_raw_callback, SBP_MSG_IMU_RAW)
    self.python_console_cmds = {
      'track': self
    }
