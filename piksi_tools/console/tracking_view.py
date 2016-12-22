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
import time
from chaco.tools.api import LegendTool
from enable.api import ComponentEditor
from pyface.api import GUI
from sbp.tracking import SBP_MSG_TRACKING_STATE
from traits.api import Instance, Dict, HasTraits, Float, List, Int, Bool
from traitsui.api import Item, View, HSplit, VGroup, HGroup, Spring
import numpy as np
from piksi_tools.acq_results import SNR_THRESHOLD
from piksi_tools.console.utils import code_to_str, code_is_gps, L1_CODES, L2_CODES

NUM_POINTS = 200

# These colors should be distinguishable from eachother
color_dict = {'(0, 1)': 0xe58a8a, '(0, 2)': 0x664949, '(0, 3)': 0x590c00, 
'(0, 4)': 0xcc4631, '(0, 5)': 0xe56c1c, '(0, 6)': 0x4c2a12, '(0, 7)': 0x996325, 
'(0, 8)': 0xf2b774, '(0, 9)': 0xffaa00, '(0, 10)': 0xccb993, '(0, 11)': 0x997a00, 
'(0, 12)': 0x4c4700, '(0, 13)': 0xd0d94e, '(0, 14)': 0xaaff00, '(0, 15)': 0x4ea614, 
'(0, 16)': 0x123306, '(0, 17)': 0x18660c, '(0, 18)': 0x6e9974, '(0, 19)': 0x8ae6a2, 
'(0, 20)': 0x00ff66, '(0, 21)': 0x57f2e8, '(0, 22)': 0x1f7980, '(0, 23)': 0x263e40, 
'(0, 24)': 0x004d73, '(0, 25)': 0x37abe6, '(0, 26)': 0x7790a6, '(0, 27)': 0x144ea6, 
'(0, 28)': 0x263040, '(0, 29)': 0x152859, '(0, 30)': 0x1d39f2, '(0, 31)': 0x828ed9, 
'(0, 32)': 0x000073, '(1, 1)': 0x000066, '(1, 2)': 0x8c7aff, '(1, 3)': 0x1b0033, 
'(1, 4)': 0xd900ca, '(1, 5)': 0x730e6c, '(1, 6)': 0x402e3f, '(1, 7)': 0xcc7abc, 
'(1, 8)': 0xcc1978, '(1, 9)': 0x7f0033, '(1, 10)': 0xff1f5a, '(1, 11)': 0x330c11, 
'(1, 12)': 0xcc627e, '(1, 13)': 0x73000f, '(1, 14)': 0x663d43, '(1, 15)': 0xd9b6bb, 
'(1, 16)': 0xff0000, '(1, 17)': 0xf20000, '(1, 18)': 0xe56653, '(1, 19)': 0x4c1b09, 
'(1, 20)': 0xffbfa8, '(1, 21)': 0xf2843a, '(1, 22)': 0x8c5b3b, '(1, 23)': 0x402d17, 
'(1, 24)': 0xffdeb8, '(1, 25)': 0xd99e27, '(1, 26)': 0x736c0e, '(1, 27)': 0xfff23d, 
'(1, 28)': 0x999777, '(1, 29)': 0xf1ffb8, '(1, 30)': 0x1f2610, '(1, 31)': 0x366600, 
'(1, 32)': 0x71bf17
}


def get_color(key):
  color = 0xff0000
  try:
   key = str((key[0], key[1]%32))
   color = color_dict.get(key, 0xff0000)
  except:
   pass
  return color

class TrackingView(HasTraits):
  python_console_cmds = Dict()
  legend_visible = Bool()
  show_l1 = Bool()
  show_l2 = Bool()
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
      HGroup(Spring(width=4, springy=False), 
             Item('legend_visible', label="Show Legend:"),
             Spring(width=8, springy=False),  
             Item('show_l1', label = "Show L1:"),
             Spring(width=8, springy=False), 
             Item('show_l2', label = "Show L2:")),
    )
  )

  def tracking_state_callback(self, sbp_msg, **metadata):
    t = time.time() - self.t_init
    self.time[0:-1] = self.time[1:]
    self.time[-1] = t
    # first we loop over all the SIDs / channel keys we have stored and set 0 in for CN0
    for key, cno_array in self.CN0_dict.items():
      # p
      if (cno_array==0).all():
        self.CN0_dict.pop(key)
      else:
        self.CN0_dict[key][0:-1] = cno_array[1:]
        self.CN0_dict[key][-1] = 0
      # If the whole array is 0 we remove it
    # for each satellite, we have a (code, prn, channel) keyed dict
    # for each SID, an array of size MAX PLOT with the history of CN0's stored
    # If there is no CN0 or not tracking for an epoch, 0 will be used
    # each array can be plotted against host_time, t
    for i,s in enumerate(sbp_msg.states):
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
      if each not in [str(a) for a in self.CN0_dict.keys()] and each != 't':
        try:
          self.plot_data.del_data(each)
          self.plot.delplot(each)
        except KeyError:
          pass
    for k, cno_array in self.CN0_dict.items():
      key = str(k)
      # set plot data and create plot for any selected for display
      if ((self.show_l2 and int(k[0]) in L2_CODES) or
          (self.show_l1 and int(k[0]) in L1_CODES)):
          self.plot_data.set_data(key, cno_array)
          if key not in self.plot.plots.keys():
            pl = self.plot.plot(('t', key), type='line', color=get_color(k),
                                name=key)
          else:
            pl = self.plot.plots[key]
          # if channel is still active:
          plots.append(pl)
          plot_labels.append('Ch %02d (PRN%02d (%s))' %
            (k[2], k[1], code_to_str(k[0])))
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
      if self.legend_visible==False:
        self.plot.legend.visible = False
      else:
        self.plot.legend.visible = True
      self.plot.legend.tools.append(LegendTool(self.plot.legend,
                                    drag_button="right"))

  def __init__(self, link):
    super(TrackingView, self).__init__()
    self.t_init = time.time()
    self.time = range(-NUM_POINTS, 0, 1)
    self.CN0_dict = {}
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
    self.legend_visible = True
    self.show_l1 = True
    self.show_l2 = True
    self.plot.legend.visible = True
    self.plot.legend.align = 'll'
    self.plot.legend.line_spacing = 1
    self.plot.legend.font = 'modern 8'
    self.plot.legend.draw_layer= 'overlay'
    self.plot.legend.tools.append(LegendTool(self.plot.legend,
                                  drag_button="right"))
    self.link = link
    self.link.add_callback(self.tracking_state_callback, SBP_MSG_TRACKING_STATE)
    self.python_console_cmds = {
      'track': self
    }
