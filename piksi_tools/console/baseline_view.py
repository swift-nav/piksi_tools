# Copyright (C) 2011-2014 Swift Navigation Inc.
# Contact: Fergus Noble <fergus@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

from traits.api import Instance, Dict, HasTraits, Array, Float, on_trait_change, List, Int, Button, Bool
from traitsui.api import Item, View, HGroup, VGroup, ArrayEditor, HSplit, TabularEditor
from traitsui.tabular_adapter import TabularAdapter
from chaco.api import ArrayPlotData, Plot
from chaco.tools.api import ZoomTool, PanTool
from enable.api import ComponentEditor
from enable.savage.trait_defs.ui.svg_button import SVGButton
from pyface.api import GUI
from utils import plot_square_axes

import math
import os
import numpy as np
import datetime
import time

from sbp.piksi      import *
from sbp.navigation import *

class SimpleAdapter(TabularAdapter):
    columns = [('Item', 0), ('Value',  1)]
    width = 80

class BaselineView(HasTraits):
  python_console_cmds = Dict()

  table = List()

  plot = Instance(Plot)
  plot_data = Instance(ArrayPlotData)

  running = Bool(True)
  zoomall = Bool(False)
  position_centered = Bool(False)

  clear_button = SVGButton(
    label='', tooltip='Clear',
    filename=os.path.join(os.path.dirname(__file__), 'images', 'iconic', 'x.svg'),
    width=16, height=16
  )
  zoomall_button = SVGButton(
    label='', tooltip='Zoom All', toggle=True,
    filename=os.path.join(os.path.dirname(__file__), 'images', 'iconic', 'fullscreen.svg'),
    width=16, height=16
  )
  center_button = SVGButton(
    label='', tooltip='Center on Baseline', toggle=True,
    filename=os.path.join(os.path.dirname(__file__), 'images', 'iconic', 'target.svg'),
    width=16, height=16
  )
  paused_button = SVGButton(
    label='', tooltip='Pause', toggle_tooltip='Run', toggle=True,
    filename=os.path.join(os.path.dirname(__file__), 'images', 'iconic', 'pause.svg'),
    toggle_filename=os.path.join(os.path.dirname(__file__), 'images', 'iconic', 'play.svg'),
    width=16, height=16
  )

  reset_button = Button(label='Reset Filters')
  reset_iar_button = Button(label='Reset IAR')
  init_base_button = Button(label='Init. with known baseline')

  traits_view = View(
    HSplit(
      Item('table', style = 'readonly', editor = TabularEditor(adapter=SimpleAdapter()), show_label=False, width=0.3),
      VGroup(
        HGroup(
          Item('paused_button', show_label=False),
          Item('clear_button', show_label=False),
          Item('zoomall_button', show_label=False),
          Item('center_button', show_label=False),
          Item('reset_button', show_label=False),
          Item('reset_iar_button', show_label=False),
          Item('init_base_button', show_label=False),
        ),
        Item(
          'plot',
          show_label = False,
          editor = ComponentEditor(bgcolor = (0.8,0.8,0.8)),
        )
      )
    )
  )

  def _zoomall_button_fired(self):
    self.zoomall = not self.zoomall

  def _center_button_fired(self):
    self.position_centered = not self.position_centered

  def _paused_button_fired(self):
    self.running = not self.running

  def _reset_button_fired(self):
    self.link(MsgResetFilters(filter=0))

  def _reset_iar_button_fired(self):
    self.link(MsgResetFilters(filter=1))

  def _init_base_button_fired(self):
    self.link(MsgInitBase())

  def _clear_button_fired(self):
    self.neds[:] = np.NAN
    self.fixeds[:] = False
    self.plot_data.set_data('n_fixed', [])
    self.plot_data.set_data('e_fixed', [])
    self.plot_data.set_data('d_fixed', [])
    self.plot_data.set_data('n_float', [])
    self.plot_data.set_data('e_float', [])
    self.plot_data.set_data('d_float', [])
    self.plot_data.set_data('t', [])
    self.plot_data.set_data('cur_fixed_n', [])
    self.plot_data.set_data('cur_fixed_e', [])
    self.plot_data.set_data('cur_fixed_d', [])
    self.plot_data.set_data('cur_float_n', [])
    self.plot_data.set_data('cur_float_e', [])
    self.plot_data.set_data('cur_float_d', [])

  def _baseline_callback_ecef(self, data, **metadata):
    #Don't do anything for ECEF currently
    return

  def iar_state_callback(self, sbp_msg, **metadata):
    self.num_hyps = sbp_msg.num_hyps

  def _baseline_callback_ned(self, sbp_msg, **metadata):
    # Updating an ArrayPlotData isn't thread safe (see chaco issue #9), so
    # actually perform the update in the UI thread.
    if self.running:
      GUI.invoke_later(self.baseline_callback, sbp_msg)

  def update_table(self):
    self._table_list = self.table.items()

  def gps_time_callback(self, sbp_msg, **metadata):
    self.week = MsgGPSTime(sbp_msg).wn
    self.nsec = MsgGPSTime(sbp_msg).ns

  def baseline_callback(self, sbp_msg):
    soln = MsgBaselineNED(sbp_msg)
    table = []

    soln.n = soln.n * 1e-3
    soln.e = soln.e * 1e-3
    soln.d = soln.d * 1e-3

    dist = np.sqrt(soln.n**2 + soln.e**2 + soln.d**2)

    tow = soln.tow * 1e-3
    if self.nsec is not None:
      tow += self.nsec * 1e-9

    if self.week is not None:
      t = datetime.datetime(1980, 1, 6) + \
          datetime.timedelta(weeks=self.week) + \
          datetime.timedelta(seconds=tow)

      table.append(('GPS Time', t))
      table.append(('GPS Week', str(self.week)))

      if self.log_file is None:
        self.log_file = open(time.strftime("baseline_log_%Y%m%d-%H%M%S.csv"), 'w')
        self.log_file.write('time,north(meters),east(meters),down(meters),distance(meters),num_sats,flags,num_hypothesis\n')

      self.log_file.write('%s,%.4f,%.4f,%.4f,%.4f,%d,0x%02x,%d\n' % (
        str(t),
        soln.n, soln.e, soln.d, dist,
        soln.n_sats,
        soln.flags,
        self.num_hyps)
      )
      self.log_file.flush()

    table.append(('GPS ToW', tow))

    table.append(('N', soln.n))
    table.append(('E', soln.e))
    table.append(('D', soln.d))
    table.append(('Dist.', dist))
    table.append(('Num. Sats.', soln.n_sats))
    table.append(('Flags', '0x%02x' % soln.flags))
    fixed = (soln.flags & 1) == 1
    if fixed:
      table.append(('Mode', 'Fixed RTK'))
    else:
      table.append(('Mode', 'Float'))
    table.append(('IAR Num. Hyps.', self.num_hyps))

    # Rotate array, deleting oldest entries to maintain
    # no more than N in plot
    self.neds[1:] = self.neds[:-1]
    self.fixeds[1:] = self.fixeds[:-1]

    # Insert latest position
    self.neds[0][:] = [soln.n, soln.e, soln.d]
    self.fixeds[0] = fixed

    neds_fixed = self.neds[self.fixeds]
    neds_float = self.neds[np.logical_not(self.fixeds)]

    if not all(map(any, np.isnan(neds_fixed))):
      self.plot_data.set_data('n_fixed', neds_fixed.T[0])
      self.plot_data.set_data('e_fixed', neds_fixed.T[1])
      self.plot_data.set_data('d_fixed', neds_fixed.T[2])
    if not all(map(any, np.isnan(neds_float))):
      self.plot_data.set_data('n_float', neds_float.T[0])
      self.plot_data.set_data('e_float', neds_float.T[1])
      self.plot_data.set_data('d_float', neds_float.T[2])

    if fixed:
      self.plot_data.set_data('cur_fixed_n', [soln.n])
      self.plot_data.set_data('cur_fixed_e', [soln.e])
      self.plot_data.set_data('cur_fixed_d', [soln.d])
      self.plot_data.set_data('cur_float_n', [])
      self.plot_data.set_data('cur_float_e', [])
      self.plot_data.set_data('cur_float_d', [])
    else:
      self.plot_data.set_data('cur_float_n', [soln.n])
      self.plot_data.set_data('cur_float_e', [soln.e])
      self.plot_data.set_data('cur_float_d', [soln.d])
      self.plot_data.set_data('cur_fixed_n', [])
      self.plot_data.set_data('cur_fixed_e', [])
      self.plot_data.set_data('cur_fixed_d', [])

    self.plot_data.set_data('ref_n', [0.0])
    self.plot_data.set_data('ref_e', [0.0])
    self.plot_data.set_data('ref_d', [0.0])

    if self.position_centered:
      d = (self.plot.index_range.high - self.plot.index_range.low) / 2.
      self.plot.index_range.set_bounds(soln.e - d, soln.e + d)
      d = (self.plot.value_range.high - self.plot.value_range.low) / 2.
      self.plot.value_range.set_bounds(soln.n - d, soln.n + d)

    if self.zoomall:
      plot_square_axes(self.plot, ('e_fixed', 'e_float'), ('n_fixed', 'n_float'))
    self.table = table

  def __init__(self, link, plot_history_max=1000):
    super(BaselineView, self).__init__()

    self.log_file = None

    self.num_hyps = 0

    self.plot_data = ArrayPlotData(n_fixed=[0.0], e_fixed=[0.0], d_fixed=[0.0],
                                   n_float=[0.0], e_float=[0.0], d_float=[0.0],
                                   t=[0.0],
                                   ref_n=[0.0], ref_e=[0.0], ref_d=[0.0],
                                   cur_fixed_e=[], cur_fixed_n=[], cur_fixed_d=[],
                                   cur_float_e=[], cur_float_n=[], cur_float_d=[])
    self.plot_history_max = plot_history_max

    self.neds = np.empty((plot_history_max, 3))
    self.neds[:] = np.NAN
    self.fixeds = np.zeros(plot_history_max, dtype=bool)

    self.plot = Plot(self.plot_data)
    color_float = (0.5, 0.5, 1.0)
    color_fixed = 'orange'
    pts_float = self.plot.plot(('e_float', 'n_float'),
        type='scatter',
        color=color_float,
        marker='dot',
        line_width=0.0,
        marker_size=1.0)
    pts_fixed = self.plot.plot(('e_fixed', 'n_fixed'),
        type='scatter',
        color=color_fixed,
        marker='dot',
        line_width=0.0,
        marker_size=1.0)
    lin = self.plot.plot(('e_fixed', 'n_fixed'),
        type='line',
        color=(1, 0.65, 0, 0.1))
    ref = self.plot.plot(('ref_e', 'ref_n'),
        type='scatter',
        color='red',
        marker='plus',
        marker_size=5,
        line_width=1.5)
    cur_fixed = self.plot.plot(('cur_fixed_e', 'cur_fixed_n'),
        type='scatter',
        color=color_fixed,
        marker='plus',
        marker_size=5,
        line_width=1.5)
    cur_float = self.plot.plot(('cur_float_e', 'cur_float_n'),
        type='scatter',
        color=color_float,
        marker='plus',
        marker_size=5,
        line_width=1.5)
    plot_labels = ['Base Position','RTK Fixed','RTK Float']
    plots_legend = dict(zip(plot_labels, [ref, cur_fixed, cur_float]))
    self.plot.legend.plots = plots_legend
    self.plot.legend.visible = True

    self.plot.index_axis.tick_label_position = 'inside'
    self.plot.index_axis.tick_label_color = 'gray'
    self.plot.index_axis.tick_color = 'gray'
    self.plot.index_axis.title='E (meters)'
    self.plot.index_axis.title_spacing = 5
    self.plot.value_axis.tick_label_position = 'inside'
    self.plot.value_axis.tick_label_color = 'gray'
    self.plot.value_axis.tick_color = 'gray'
    self.plot.value_axis.title='N (meters)'
    self.plot.value_axis.title_spacing = 5
    self.plot.padding = (25, 25, 25, 25)

    self.plot.tools.append(PanTool(self.plot))
    zt = ZoomTool(self.plot, zoom_factor=1.1, tool_mode="box", always_on=False)
    self.plot.overlays.append(zt)

    self.week = None
    self.nsec = 0

    self.link = link
    self.link.add_callback(self._baseline_callback_ned, SBP_MSG_BASELINE_NED)
    self.link.add_callback(self._baseline_callback_ecef, SBP_MSG_BASELINE_ECEF)
    self.link.add_callback(self.iar_state_callback, SBP_MSG_IAR_STATE)
    self.link.add_callback(self.gps_time_callback, SBP_MSG_GPS_TIME)

    self.python_console_cmds = {
      'baseline': self
    }
