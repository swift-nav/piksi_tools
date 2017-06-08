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

from random import randint
import time

from chaco.api import ArrayPlotData, Plot
from chaco.tools.api import LegendTool
from enable.api import ComponentEditor
from pyface.api import GUI

from traits.api import Instance, Dict, List, Int, Bool
from traitsui.api import Item, View, VGroup, HGroup, Spring

import numpy as np

from piksi_tools.acq_results import SNR_THRESHOLD
from piksi_tools.console.gui_utils import CodeFiltered
from piksi_tools.console.utils import code_to_str, code_is_gps, code_is_glo,\
                                      SUPPORTED_CODES

from sbp.tracking import SBP_MSG_TRACKING_STATE, SBP_MSG_TRACKING_STATE_DEP_B

NUM_POINTS = 200
TRK_RATE = 2.0
CHANNEL_COUNT = 64

color_code = lambda: int('0x%02x%02x%02x' %
                         (randint(0,255), randint(0,255), randint(0,255)), 16)
color_list = [color_code() for c in xrange(CHANNEL_COUNT)]

marker_list = ['circle', 'square', 'pixel', 'plus',
               'cross', 'triangle', 'inverted_triangle', 'diamond']

def get_color(channel):
  try:
    return color_list[channel]
  except:
    return color_code()


def get_marker(code):
  marker = 'square'

  try:
    marker = marker_list[code]
  except:
    pass

  return marker


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
        show_label=False,
      ),
      HGroup(
        Spring(width=8, springy=False),
        Item('legend_visible', label="Show Legend:"),
        CodeFiltered.get_filter_group(),
      )
    )
  )

  def _shift_data_arrays(self):
    # first we loop over all the arrays we have stored and set 0 in for CN0.
    # Lists are added for Python3 compatibility while deleting.
    for code in list(self.data_dict.keys()):
      for key, cno_array in list(self.data_dict[code].items()):
        self.data_dict[code][key] =\
          np.lib.pad(cno_array, ((0,1),(0,0)), "constant")[1:,:]
        if (cno_array==0).all():
          del self.data_dict[code][key]

  def _update_data_arrays(self, sbp_msg):

    for i,s in enumerate(sbp_msg.states):

      code = s.sid.code
      if int(code) not in SUPPORTED_CODES:
        continue

      if SBP_MSG_TRACKING_STATE == sbp_msg.msg_type and 0 == s.cn0:
        continue
      if SBP_MSG_TRACKING_STATE_DEP_B == sbp_msg.msg_type and 0 == s.state:
        continue

      prn = s.sid.sat + 1 if code_is_gps(code) else s.sid.sat

      if SBP_MSG_TRACKING_STATE == sbp_msg.msg_type:
        key = (s.fcn, i) if code_is_glo(code) else (prn, i)
        cn0 = s.cn0 / 4.0
      elif SBP_MSG_TRACKING_STATE_DEP_B == sbp_msg.msg_type:
        key = (None, i) if code_is_glo(code) else (prn, i)
        cn0 = s.cn0

      if key not in self.data_dict[code]:
        self.data_dict[code][key] = np.zeros(NUM_POINTS, dtype='2float')

      self.data_dict[code][key][-1] = (cn0, prn)

  def tracking_state_callback(self, sbp_msg, **metadata):
    t = time.time() - self.t_init
    self.time = np.lib.pad(self.time, (0,1), 'constant', constant_values=t)[1:]

    self._shift_data_arrays()

    self._update_data_arrays(sbp_msg)

    GUI.invoke_later(self.update_plot)

  def _remove_stail_plots(self):
    keys = []
    for code, data in self.data_dict.items():
      keys += [str((code,) + key) for key in data.keys()]

    # remove any stale plots that got removed from the dictionary
    for each in self.plot_data.list_data():
      if each not in keys and each != 't':
        try:
          self.plot_data.del_data(each)
          self.plot.delplot(each)
        except KeyError:
          pass

  def _update_code_plots(self, code, plot_labels, plots):
    for k, cno_array in self.data_dict[code].items():

      key = str((code,) + k)

      if not getattr(self, 'show_{}'.format(int(code))):
        # remove plot data and plots not selected
        if key in self.plot_data.list_data():
          self.plot_data.del_data(key)
        if key in self.plot.plots.keys():
          self.plot.delplot(key)
        continue

      # set plot data and create plot for any selected for display
      cn0_values = cno_array[:,:-1]
      self.plot_data.set_data(key, cn0_values.reshape(len(cn0_values)))

      # if channel is inactive:
      if 0 == cno_array[-1][0]:
        continue

      if key in self.plot.plots.keys():
        pl = self.plot.plots[key]
      else:
        pl = self.plot.plot(('t', key),
                            type='scatter',
                            marker=get_marker(code),
                            marker_size=2.7,
                            line_width=0,
                            color=get_color(k[1]),
                            name=key)

      plots.append(pl)

      if code_is_glo(code):
        # TODO check if PRN changes (cno_array[-1][1] vs cno_array[-2][1]).
        # If it does, it means slot ID is finally decoded (changes from unknown
        # to valid) OR a new SV took the frequency channel (valid to valid,
        # can happen if antenna rises high enough)
        label = 'Ch %02d (PRN%02d (%s))' % (k[1],
                                            cno_array[-1][1],
                                            code_to_str(code))
        if k[0] is not None:
          label += ' FCN %02d' % (k[0])
      else:
        label = 'Ch %02d (PRN%02d (%s))' % (k[1], k[0], code_to_str(code))

      plot_labels.append(label)


  def update_plot(self):
    plot_labels = []
    plots = []
    self.plot_data.set_data('t', self.time)

    self._remove_stail_plots()

    for code in self.data_dict.keys():
      self._update_code_plots(code, plot_labels, plots)

    plots = dict(zip(plot_labels, plots))
    self.plot.legend.plots = plots

  def _legend_visible_changed(self):
    if self.plot:
      if self.legend_visible==False:
        self.plot.legend.visible = False
      else:
        self.plot.legend.visible = True
      self.plot.legend.tools.append(LegendTool(self.plot.legend,
                                    drag_button="right"))

  def __init__(self, link):
    super(TrackingView, self).__init__()
    self.t_init = time.time()
    self.time = np.arange(-NUM_POINTS, 0, 1) / TRK_RATE
    self.data_dict = dict((code, {}) for code in SUPPORTED_CODES)
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
    self.plot.legend.font = 'modern 8'
    self.plot.legend.draw_layer= 'overlay'
    self.plot.legend.tools.append(LegendTool(self.plot.legend,
                                  drag_button="right"))
    self.link = link

    self.link.add_callback(self.tracking_state_callback,
                           [SBP_MSG_TRACKING_STATE,
                            SBP_MSG_TRACKING_STATE_DEP_B])
    self.python_console_cmds = {
      'track': self
    }
