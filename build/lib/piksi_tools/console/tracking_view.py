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
from sbp.tracking import SBP_MSG_TRACKING_STATE
from traits.api import Instance, Dict, HasTraits, Float, List, Int
from traitsui.api import Item, View, HSplit
import numpy as np
from piksi_tools.acq_results import SNR_THRESHOLD
from piksi_tools.console.utils import code_to_str

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


class TrackingState(HasTraits):
  state = Int()
  cn0 = Float()
  prn = Int()
  code = Int()

  def __init__(self, *args, **kwargs):
    self.update(*args, **kwargs)

  def update(self, state, prn, cn0, code):
    self.state = state
    self.cn0 = 0 if cn0 == -1 else cn0
    self.prn = prn
    self.code = code

  def __repr__(self):
    return "TS: %d %f %d" % (self.prn, self.cn0, self.code)


class TrackingView(HasTraits):
  python_console_cmds = Dict()
  states = List(Instance(TrackingState))
  cn0_history = List()

  plot = Instance(Plot)
  plots = List()
  plot_data = Instance(ArrayPlotData)

  traits_view = View(
    HSplit(
      Item(
        'plot',
        editor=ComponentEditor(bgcolor=(0.8, 0.8, 0.8)),
        show_label=False,
      )
    )
  )

  def tracking_state_callback(self, sbp_msg, **metadata):
    n_channels = len(sbp_msg.states)
    if n_channels != self.n_channels:
      # Update number of channels
      self.n_channels = n_channels
      self.states = [TrackingState(0, 0, 0, 0) for _ in range(n_channels)]
      for pl in self.plot.plots.iterkeys():
        self.plot.delplot(pl.name)
      self.plots = []
      for n in range(n_channels):
        self.plot_data.set_data('ch' + str(n), [0.0])
        pl = self.plot.plot(('t', 'ch' + str(n)), type='line', color='auto',
                            name='ch' + str(n))
        self.plots.append(pl)
      print 'Number of tracking channels changed to {0}'.format(n_channels)
    for n, k in enumerate(self.states):
      s = sbp_msg.states[n]
      prn = s.sid.sat
      if (s.sid.code == 0 or s.sid.code == 1):
        prn += 1
      k.update(s.state, prn, s.cn0, s.sid.code)
    GUI.invoke_later(self.update_plot)

  def update_plot(self):
    self.cn0_history.append([s.cn0 for s in self.states])
    self.cn0_history = self.cn0_history[-1000:]

    chans = np.transpose(self.cn0_history[-NUM_POINTS:])
    plot_labels = []
    for n in range(self.n_channels):
      self.plot_data.set_data('ch' + str(n), chans[n])
      if self.states[n].state == 0:
        plot_labels.append('Ch %02d (Disabled)' % n)
      else:
        plot_labels.append('Ch %02d (PRN%02d (%s))' %
          (n, self.states[n].prn, code_to_str(self.states[n].code)))
    plots = dict(zip(plot_labels, self.plots))
    self.plot.legend.plots = plots

  def __init__(self, link):
    super(TrackingView, self).__init__()
    self.n_channels = None
    self.plot_data = ArrayPlotData(t=[0.0])
    self.plot = Plot(self.plot_data, auto_colors=colours_list, emphasized=True)
    self.plot.title = 'Tracking C/N0'
    self.plot.title_color = [0, 0, 0.43]
    self.ylim = self.plot.value_mapper.range
    self.ylim.low = SNR_THRESHOLD
    self.ylim.high = 60
    self.plot.value_range.bounds_func = lambda l, h, m, tb: (0, h * (1 + m))
    self.plot.value_axis.orientation = 'right'
    self.plot.value_axis.axis_line_visible = False
    self.plot.value_axis.title = 'dB-Hz'
    t = range(NUM_POINTS)
    self.plot_data.set_data('t', t)
    self.plot.legend.visible = True
    self.plot.legend.align = 'ul'
    self.plot.legend.tools.append(LegendTool(self.plot.legend,
                                  drag_button="right"))
    self.link = link
    self.link.add_callback(self.tracking_state_callback, SBP_MSG_TRACKING_STATE)
    self.python_console_cmds = {
      'track': self
    }
