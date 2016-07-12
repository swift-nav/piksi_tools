#!/usr/bin/env python
# Copyright (C) 2011-2014 Swift Navigation Inc.
# Contact: Fergus Noble <fergus@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

from traits.api import Instance, Dict, HasTraits, Array, Float, on_trait_change, List, Int, Button, Bool, Str, File
from traitsui.api import Item, View, HGroup, VGroup, ArrayEditor, HSplit, TextEditor, TabularEditor, UItem, Tabbed
from traitsui.tabular_adapter import TabularAdapter
from chaco.api import ArrayPlotData, Plot
from chaco.tools.api import ZoomTool, PanTool
from enable.api import ComponentEditor
from enable.savage.trait_defs.ui.svg_button import SVGButton
from pyface.api import GUI
from piksi_tools.console.utils import plot_square_axes, determine_path, MultilineTextEditor

from traitsui.file_dialog \
    import open_file

import math
import os
import numpy as np
import datetime
import time

from sbp.navigation import *

class SimpleAdapter(TabularAdapter):
  columns = [('Item', 0), ('Value',  1)]
  width = 80

class SolutionView(HasTraits):
  python_console_cmds = Dict()
  # we need to doubleup on Lists to store the psuedo absolutes separately
  # without rewriting everything
  lats = List()
  lngs = List()
  alts = List()

  """
  logging_v : toggle logging for velocity files
  directory_name_v : location and name of velocity files
  logging_p : toggle logging for position files
  directory_name_p : location and name of velocity files
  """

  logging_v = Bool(False)
  directory_name_v = File

  logging_p = Bool(False)
  directory_name_p = File

  json = Bool(False)

  lats_psuedo_abs = List()
  lngs_psuedo_abs = List()
  alts_psuedo_abs = List()

  table_spp = List()
  table_psuedo_abs = List()
  dops_table = List()
  pos_table_spp = List()
  vel_table = List()

  rtk_pos_note = Str("It is necessary to enter the \"Surveyed Position\" settings for the base station in order to view the psuedo-absolute RTK Positions in this tab.")

  plot = Instance(Plot)
  plot_data = Instance(ArrayPlotData)
  # Store plots we care about for legend

  running = Bool(True)
  zoomall = Bool(False)
  position_centered = Bool(False)

  clear_button = SVGButton(
    label='', tooltip='Clear',
    filename=os.path.join(determine_path(), 'images', 'iconic', 'x.svg'),
    width=16, height=16
  )
  zoomall_button = SVGButton(
    label='', tooltip='Zoom All', toggle=True,
    filename=os.path.join(determine_path(), 'images', 'iconic', 'fullscreen.svg'),
    width=16, height=16
  )
  center_button = SVGButton(
    label='', tooltip='Center on Solution', toggle=True,
    filename=os.path.join(determine_path(), 'images', 'iconic', 'target.svg'),
    width=16, height=16
  )
  paused_button = SVGButton(
    label='', tooltip='Pause', toggle_tooltip='Run', toggle=True,
    filename=os.path.join(determine_path(), 'images', 'iconic', 'pause.svg'),
    toggle_filename=os.path.join(determine_path(), 'images', 'iconic', 'play.svg'),
    width=16, height=16
  )

  traits_view = View(
    HSplit(
      Tabbed(
        VGroup(
          Item('', label='Single Point Position (SPP)', emphasized=True),
          Item('table_spp', style='readonly',
                editor=TabularEditor(adapter=SimpleAdapter()),
                show_label=False, width=0.3),
          label='Single Point Position'),
        VGroup(
          Item('', label='RTK Position', emphasized=True),
          Item('table_psuedo_abs',style='readonly',
               editor=TabularEditor(adapter=SimpleAdapter()),
               show_label=False, width=0.3, height=0.9),
          Item('rtk_pos_note', show_label=False, resizable=True,
            editor=MultilineTextEditor(TextEditor(multi_line=True)), 
            style='readonly', width=0.3, height=-40),
          label='RTK Position')
      ),
      VGroup(
        HGroup(
          Item('paused_button', show_label=False),
          Item('clear_button', show_label=False),
          Item('zoomall_button', show_label=False),
          Item('center_button', show_label=False),
        ),
        Item('plot',
          show_label=False,
          editor=ComponentEditor(bgcolor=(0.8,0.8,0.8))),
      )
    )
  )

  def _zoomall_button_fired(self):
    self.zoomall = not self.zoomall

  def _center_button_fired(self):
    self.position_centered = not self.position_centered

  def _paused_button_fired(self):
    self.running = not self.running

  def _clear_button_fired(self):
    self.lats = []
    self.lngs = []
    self.alts = []
    self.lats_psuedo_abs = []
    self.lngs_psuedo_abs = []
    self.alts_psuedo_abs = []
    self.plot_data.set_data('lat', [])
    self.plot_data.set_data('lng', [])
    self.plot_data.set_data('alt', [])
    self.plot_data.set_data('t', [])
    self.plot_data.set_data('lat_ps', [])
    self.plot_data.set_data('lng_ps', [])
    self.plot_data.set_data('alt_ps', [])
    self.plot_data.set_data('t_ps', [])

  def _pos_llh_callback(self, sbp_msg, **metadata):
    # Updating an ArrayPlotData isn't thread safe (see chaco issue #9), so
    # actually perform the update in the UI thread.
    if self.running:
      GUI.invoke_later(self.pos_llh_callback, sbp_msg)

  def mode_string(self, msg):
    if msg:
      if (msg.flags & 0xff) == 0:
        return 'SPP (single point position)'
      elif (msg.flags & 0xff) == 1:
        return 'Fixed RTK'
      elif (msg.flags & 0xff) == 2:
        return 'Float RTK'
    return 'None'

  def update_table(self):
    self._table_list = self.table_spp.items()

  def pos_llh_callback(self, sbp_msg, **metadata):
    self.last_stime_update = time.time()
    soln = MsgPosLLH(sbp_msg)
    self.last_soln = soln
    masked_flag = soln.flags & 0x7
    if masked_flag == 0:
      psuedo_absolutes = False
    else:
      psuedo_absolutes = True
    pos_table = []

    tow = soln.tow * 1e-3
    if self.nsec is not None:
      tow += self.nsec * 1e-9

    if self.week is not None:
      t = datetime.datetime(1980, 1, 6) + \
          datetime.timedelta(weeks=self.week) + \
          datetime.timedelta(seconds=tow)
      pos_table.append(('GPS Time', t))
      pos_table.append(('GPS Week', str(self.week)))

      if(self.directory_name_p == ''):
          filepath_p = time.strftime("position_log_%Y%m%d-%H%M%S.csv")
      else:
          filepath_p = self.directory_name_p + '/' + time.strftime("position_log_%Y%m%d-%H%M%S.csv")

      if self.logging_p ==  False:
        self.log_file = None

      if self.logging_p:
        if self.log_file is None:
          self.log_file = open(filepath_p, 'w')
          self.log_file.write("time,latitude(degrees),longitude(degrees),altitude(meters),n_sats,flags\n")
          self.log_file.write('%s,%.10f,%.10f,%.4f,%d,%d\n' % (
            str(t),
            soln.lat, soln.lon, soln.height,
            soln.n_sats, soln.flags)
          )
          self.log_file.flush()

    pos_table.append(('GPS ToW', tow))

    pos_table.append(('Num. sats', soln.n_sats))

    pos_table.append(('Lat', soln.lat))
    pos_table.append(('Lng', soln.lon))
    pos_table.append(('Alt', soln.height))
    pos_table.append(('Flags', '0x%02x' % soln.flags))

    pos_table.append(('Mode', self.mode_string(soln)))

    if psuedo_absolutes:
      # setup_plot variables
      self.lats_psuedo_abs.append(soln.lat)
      self.lngs_psuedo_abs.append(soln.lon)
      self.alts_psuedo_abs.append(soln.height)

      self.lats_psuedo_abs = self.lats_psuedo_abs[-1000:]
      self.lngs_psuedo_abs = self.lngs_psuedo_abs[-1000:]
      self.alts_psuedo_abs = self.alts_psuedo_abs[-1000:]

      self.plot_data.set_data('lat_ps', self.lats_psuedo_abs)
      self.plot_data.set_data('lng_ps', self.lngs_psuedo_abs)
      self.plot_data.set_data('alt_ps', self.alts_psuedo_abs)
      self.plot_data.set_data('cur_lat_ps', [soln.lat])
      self.plot_data.set_data('cur_lng_ps', [soln.lon])
      t_psuedo_abs = range(len(self.lats))
      self.plot_data.set_data('t', t)
      self.plot_data.set_data('t_ps', t_psuedo_abs)
      # set-up table variables
      self.table_psuedo_abs = pos_table

    else:
      # setup_plot variables
      self.lats.append(soln.lat)
      self.lngs.append(soln.lon)
      self.alts.append(soln.height)

      self.lats = self.lats[-1000:]
      self.lngs = self.lngs[-1000:]
      self.alts = self.alts[-1000:]

      self.plot_data.set_data('lat', self.lats)
      self.plot_data.set_data('lng', self.lngs)
      self.plot_data.set_data('alt', self.alts)
      self.plot_data.set_data('cur_lat', [soln.lat])
      self.plot_data.set_data('cur_lng', [soln.lon])
      t = range(len(self.lats))
      self.plot_data.set_data('t', t)

      # set-up table variables
      self.pos_table_spp = pos_table
      self.table_spp = self.pos_table_spp + self.vel_table + self.dops_table
      # TODO: figure out how to center the graph now that we have two separate messages
      # when we selectivtely send only SPP, the centering function won't work anymore
      if self.position_centered:
        d = (self.plot.index_range.high - self.plot.index_range.low) / 2.
        self.plot.index_range.set_bounds(soln.lon - d, soln.lon + d)
        d = (self.plot.value_range.high - self.plot.value_range.low) / 2.
        self.plot.value_range.set_bounds(soln.lat - d, soln.lat + d)
    if self.zoomall:
      plot_square_axes(self.plot, 'lng', 'lat')

  def dops_callback(self, sbp_msg, **metadata):
    dops = MsgDops(sbp_msg)
    self.dops_table = [
      ('PDOP', '%.1f' % (dops.pdop * 0.01)),
      ('GDOP', '%.1f' % (dops.gdop * 0.01)),
      ('TDOP', '%.1f' % (dops.tdop * 0.01)),
      ('HDOP', '%.1f' % (dops.hdop * 0.01)),
      ('VDOP', '%.1f' % (dops.vdop * 0.01))
    ]
    self.table_spp = self.pos_table_spp + self.vel_table + self.dops_table

  def vel_ned_callback(self, sbp_msg, **metadata):
    vel_ned = MsgVelNED(sbp_msg)

    tow = vel_ned.tow * 1e-3
    if self.nsec is not None:
      tow += self.nsec * 1e-9

    if self.week is not None:
      t = datetime.datetime(1980, 1, 6) + \
          datetime.timedelta(weeks=self.week) + \
          datetime.timedelta(seconds=tow)

      if self.directory_name_v == '':
          filepath_v = time.strftime("velocity_log_%Y%m%d-%H%M%S.csv")
      else:
          filepath_v = self.directory_name_v + '/' + time.strftime("velocity_log_%Y%m%d-%H%M%S.csv")

      if self.logging_v ==  False:
        self.vel_log_file = None

      if self.logging_v:

        if self.vel_log_file is None:
          self.vel_log_file = open(filepath_v, 'w')
          self.vel_log_file.write('time,north(m/s),east(m/s),down(m/s),speed(m/s),num_sats\n')

        

          self.vel_log_file.write('%s,%.6f,%.6f,%.6f,%.6f,%d\n' % (
            str(t),
            vel_ned.n * 1e-3, vel_ned.e * 1e-3, vel_ned.d * 1e-3,
            math.sqrt(vel_ned.n*vel_ned.n + vel_ned.e*vel_ned.e) * 1e-3,
            vel_ned.n_sats)
          )
          self.vel_log_file.flush()

    self.vel_table = [
      ('Vel. N', '% 8.4f' % (vel_ned.n * 1e-3)),
      ('Vel. E', '% 8.4f' % (vel_ned.e * 1e-3)),
      ('Vel. D', '% 8.4f' % (vel_ned.d * 1e-3)),
    ]
    self.table_spp = self.pos_table_spp + self.vel_table + self.dops_table

  def gps_time_callback(self, sbp_msg, **metadata):
    self.week = MsgGPSTime(sbp_msg).wn
    self.nsec = MsgGPSTime(sbp_msg).ns

  def __init__(self, link):
    super(SolutionView, self).__init__()

    self.log_file = None
    self.vel_log_file = None
    self.last_stime_update = 0
    self.last_soln = None

    self.plot_data = ArrayPlotData(lat=[], lng=[], alt=[], t=[],
      cur_lat=[], cur_lng=[], cur_lat_ps=[], cur_lng_ps=[],
      lat_ps=[], lng_ps=[], alt_ps=[], t_ps=[])
    self.plot = Plot(self.plot_data)

    # 1000 point buffer
    self.plot.plot(('lng', 'lat'), type='line',  name='', color=(0, 0, 0.9, 0.1))
    self.plot.plot(('lng', 'lat'), type='scatter',  name='',
      color='blue', marker='dot', line_width=0.0, marker_size=1.0)
    self.plot.plot(('lng_ps', 'lat_ps'), type='line',  name='', color=(1, 0.4, 0, 0.1))
    self.plot.plot(('lng_ps', 'lat_ps'), type='scatter', name='',
      color='orange', marker='diamond', line_width=0.0, marker_size=1.0)
    # current values
    spp = self.plot.plot(('cur_lng', 'cur_lat'), type='scatter', name='SPP',
      color='blue', marker='plus', line_width=1.5, marker_size=5.0)
    rtk = self.plot.plot(('cur_lng_ps', 'cur_lat_ps'), type='scatter',
      name='RTK', color='orange', marker='plus', line_width=1.5, marker_size=5.0)
    plot_labels = ['SPP','RTK']
    plots_legend = dict(zip(plot_labels, [spp,rtk]))
    self.plot.legend.plots = plots_legend
    self.plot.legend.visible = True



    self.plot.index_axis.tick_label_position = 'inside'
    self.plot.index_axis.tick_label_color = 'gray'
    self.plot.index_axis.tick_color = 'gray'
    self.plot.index_axis.title='Longitude (degrees)'
    self.plot.index_axis.title_spacing = 5
    self.plot.value_axis.tick_label_position = 'inside'
    self.plot.value_axis.tick_label_color = 'gray'
    self.plot.value_axis.tick_color = 'gray'
    self.plot.value_axis.title='Latitude (degrees)'
    self.plot.value_axis.title_spacing = 5
    self.plot.padding = (25, 25, 25, 25)

    self.plot.tools.append(PanTool(self.plot))
    zt = ZoomTool(self.plot, zoom_factor=1.1, tool_mode="box", always_on=False)
    self.plot.overlays.append(zt)

    self.link = link
    self.link.add_callback(self._pos_llh_callback, SBP_MSG_POS_LLH)
    self.link.add_callback(self.vel_ned_callback, SBP_MSG_VEL_NED)
    self.link.add_callback(self.dops_callback, SBP_MSG_DOPS)
    self.link.add_callback(self.gps_time_callback, SBP_MSG_GPS_TIME)

    self.week = None
    self.nsec = 0

    self.python_console_cmds = {
      'solution': self,
    }
