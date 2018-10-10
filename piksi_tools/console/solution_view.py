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

from __future__ import absolute_import

import datetime
import math
import os
import time
import threading
from collections import deque

import numpy as np
from pyface.api import GUI
from chaco.api import ArrayPlotData, Plot
from chaco.tools.api import PanTool, ZoomTool
from enable.api import ComponentEditor
from enable.savage.trait_defs.ui.svg_button import SVGButton
from sbp.navigation import (
    SBP_MSG_AGE_CORRECTIONS, SBP_MSG_DOPS, SBP_MSG_DOPS_DEP_A,
    SBP_MSG_GPS_TIME, SBP_MSG_GPS_TIME_DEP_A, SBP_MSG_POS_LLH,
    SBP_MSG_POS_LLH_DEP_A, SBP_MSG_UTC_TIME, SBP_MSG_VEL_NED,
    SBP_MSG_VEL_NED_DEP_A, MsgAgeCorrections, MsgDops, MsgDopsDepA, MsgGPSTime,
    MsgGPSTimeDepA, MsgPosLLH, MsgPosLLHDepA, MsgUtcTime, MsgVelNED,
    MsgVelNEDDepA)
from traits.api import (Bool, Dict, File, HasTraits, Instance, Int, Float, List,
                        Str, Enum)
from traitsui.api import (HGroup, HSplit, Item, TabularEditor, TextEditor,
                          VGroup, View)
from traitsui.tabular_adapter import TabularAdapter

from piksi_tools.console.gui_utils import MultilineTextEditor, plot_square_axes
from piksi_tools.console.utils import (
    DGNSS_MODE, EMPTY_STR, FIXED_MODE, FLOAT_MODE, SBAS_MODE, DR_MODE,
    SPP_MODE, color_dict, datetime_2_str, get_mode, log_time_strings,
    mode_dict)
from piksi_tools.utils import sopen
from .utils import resource_filename
from .gui_utils import GUI_UPDATE_PERIOD, STALE_DATA_PERIOD

PLOT_HISTORY_MAX = 1000

mode_string_dict = {1: 'spp',
                    2: 'dgnss',
                    3: 'float',
                    4: 'fixed',
                    5: 'dr',
                    6: 'sbas'}


def meters_per_deg(lat):
    m1 = 111132.92  # latitude calculation term 1
    m2 = -559.82    # latitude calculation term 2
    m3 = 1.175      # latitude calculation term 3
    m4 = -0.0023    # latitude calculation term 4
    p1 = 111412.84  # longitude calculation term 1
    p2 = -93.5      # longitude calculation term 2
    p3 = 0.118      # longitude calculation term 3

    # Calculate the length of a degree of latitude and longitude in meters
    latlen = m1 + (m2 * math.cos(2 * lat * math.pi / 180)) + (
        m3 * math.cos(4 * lat * math.pi / 180)) + \
        (m4 * math.cos(6 * lat * math.pi / 180))
    longlen = (p1 * math.cos(lat * math.pi / 180)) + (
        p2 * math.cos(3 * lat * math.pi / 180)) + \
        (p3 * math.cos(5 * lat * math.pi / 180))
    return (latlen, longlen)


class SimpleAdapter(TabularAdapter):
    columns = [('Item', 0), ('Value', 1)]
    width = 80


class SolutionView(HasTraits):
    python_console_cmds = Dict()
    # we need to doubleup on Lists to store the psuedo absolutes separately
    # without rewriting everything
    """
  logging_v : toggle logging for velocity files
  directory_name_v : location and name of velocity files
  logging_p : toggle logging for position files
  directory_name_p : location and name of velocity files
  """
    plot_history_max = Int(1000)
    last_plot_update_time = Float()
    last_stale_update_time = Float()
    logging_v = Bool(False)
    display_units = Enum(["degrees", "meters"])
    directory_name_v = File

    logging_p = Bool(False)
    directory_name_p = File

    lats_psuedo_abs = List()
    lngs_psuedo_abs = List()
    alts_psuedo_abs = List()

    table = List()
    dops_table = List()
    pos_table = List()
    vel_table = List()

    rtk_pos_note = Str(
        "It is necessary to enter the \"Surveyed Position\" settings for the base station in order to view the RTK Positions in this tab."
    )

    plot = Instance(Plot)
    plot_data = Instance(ArrayPlotData)
    # Store plots we care about for legend

    running = Bool(True)
    zoomall = Bool(False)
    position_centered = Bool(False)

    clear_button = SVGButton(
        label='',
        tooltip='Clear',
        filename=resource_filename('console/images/iconic/x.svg'),
        width=16,
        height=16)
    zoomall_button = SVGButton(
        label='',
        tooltip='Zoom All',
        toggle=True,
        filename=resource_filename('console/images/iconic/fullscreen.svg'),
        width=16,
        height=16)
    center_button = SVGButton(
        label='',
        tooltip='Center on Solution',
        toggle=True,
        filename=resource_filename('console/images/iconic/target.svg'),
        width=16,
        height=16)
    paused_button = SVGButton(
        label='',
        tooltip='Pause',
        toggle_tooltip='Run',
        toggle=True,
        filename=resource_filename('console/images/iconic/pause.svg'),
        toggle_filename=resource_filename('console/images/iconic/play.svg'),
        width=16,
        height=16)

    traits_view = View(
        HSplit(
            VGroup(
                Item(
                    'table',
                    style='readonly',
                    editor=TabularEditor(adapter=SimpleAdapter()),
                    show_label=False,
                    width=0.3),
                Item(
                    'rtk_pos_note',
                    show_label=False,
                    resizable=True,
                    editor=MultilineTextEditor(TextEditor(multi_line=True)),
                    style='readonly',
                    width=0.3,
                    height=-40), ),
            VGroup(
                HGroup(
                    Item('paused_button', show_label=False),
                    Item('clear_button', show_label=False),
                    Item('zoomall_button', show_label=False),
                    Item('center_button', show_label=False),
                    Item('display_units', label="Display Units"), ),
                Item(
                    'plot',
                    show_label=False,
                    editor=ComponentEditor(bgcolor=(0.8, 0.8, 0.8))), )))

    def _zoomall_button_fired(self):
        self.zoomall = not self.zoomall

    def _center_button_fired(self):
        self.position_centered = not self.position_centered

    def _paused_button_fired(self):
        self.running = not self.running

    def _reset_remove_current(self):
        self.plot_data.update_data(self._get_update_current())

    def _get_update_current(self, current_dict={}):
        out_dict = {'cur_lat_spp': [],
                    'cur_lng_spp': [],
                    'cur_lat_dgnss': [],
                    'cur_lng_dgnss': [],
                    'cur_lat_float': [],
                    'cur_lng_float': [],
                    'cur_lat_fixed': [],
                    'cur_lng_fixed': [],
                    'cur_lat_sbas': [],
                    'cur_lng_sbas': [],
                    'cur_lat_dr': [],
                    'cur_lng_dr': []}
        out_dict.update(current_dict)
        return out_dict

    def _synchronize_plot_data_by_mode(self, mode_string, update_current=False):
        # do all required plot_data updates for a single
        # new solution with mode defined by mode_string
        pending_update = {'lat_' + mode_string: [x for x in self.slns['lat_' + mode_string] if not np.isnan(x)],

                          'lng_' + mode_string: [y for y in self.slns['lng_' + mode_string] if not np.isnan(y)]}
        if update_current:
            current = {}
            if len(pending_update['lat_' + mode_string]) != 0:
                current = {'cur_lat_' + mode_string: [pending_update['lat_' + mode_string][-1]],
                           'cur_lng_' + mode_string: [pending_update['lng_' + mode_string][-1]]}
            else:
                current = {'cur_lat_' + mode_string: [],
                           'cur_lng_' + mode_string: []}
            pending_update.update(self._get_update_current(current))
        self.plot_data.update_data(pending_update)

    def _append_empty_sln_data(self, exclude_mode=None):
        for each_mode in mode_string_dict.values():
            if exclude_mode is None or each_mode != exclude_mode:
                self.slns['lat_' + each_mode].append(np.nan)
                self.slns['lng_' + each_mode].append(np.nan)

    def _update_sln_data_by_mode(self, soln, mode_string):
        # do backend deque updates for a new solution of type
        # mode string
        self.scaling_lock.acquire()
        lat = (soln.lat - self.offset[0]) * self.sf[0]
        lng = (soln.lon - self.offset[1]) * self.sf[1]
        self.scaling_lock.release()
        self.slns['lat_' + mode_string].append(lat)
        self.slns['lng_' + mode_string].append(lng)
        # Rotate old data out by appending to deque
        self._append_empty_sln_data(exclude_mode=mode_string)

    def _clr_sln_data(self):
        for each in self.slns:
            self.slns[each].clear()

    def _clear_history(self):
        for each in self.slns:
            self.slns[each].clear()
        pending_update = {'lat_spp': [],
                          'lng_spp': [],
                          'alt_spp': [],
                          'lat_dgnss': [],
                          'lng_dgnss': [],
                          'alt_dgnss': [],
                          'lat_float': [],
                          'lng_float': [],
                          'alt_float': [],
                          'lat_fixed': [],
                          'lng_fixed': [],
                          'alt_fixed': [],
                          'lat_sbas': [],
                          'lng_sbas': [],
                          'alt_sbas': [],
                          'lat_dr': [],
                          'lng_dr': [],
                          'alt_dr': []
                          }
        pending_update.update(self._get_update_current())
        self.plot_data.update(pending_update)

    def _clear_button_fired(self):
        self._clear_history()

    def age_corrections_callback(self, sbp_msg, **metadata):
        age_msg = MsgAgeCorrections(sbp_msg)
        if age_msg.age != 0xFFFF:
            self.age_corrections = age_msg.age / 10.0
        else:
            self.age_corrections = None

    def update_table(self):
        self.table = self.pos_table + self.vel_table + self.dops_table

    def auto_survey(self):
        if len(self.lats) != 0:
            self.latitude = sum(self.lats) / len(self.lats)
            self.altitude = sum(self.alts) / len(self.alts)
            self.longitude = sum(self.lngs) / len(self.lngs)

    def pos_llh_callback(self, sbp_msg, **metadata):
        if sbp_msg.msg_type == SBP_MSG_POS_LLH_DEP_A:
            soln = MsgPosLLHDepA(sbp_msg)
        else:
            soln = MsgPosLLH(sbp_msg)

        self.last_pos_mode = get_mode(soln)
        self.last_soln = soln
        if self.last_pos_mode != 0:
            mode_string = mode_string_dict[self.last_pos_mode]
            if mode_string not in self.pending_draw_modes:
                # this list allows us to tell GUI thread which solutions to update
                # (if we decide not to update at full data rate)
                # we use short strings to identify each solution mode
                self.pending_draw_modes.append(mode_string)
            self.list_lock.acquire()
            self._update_sln_data_by_mode(soln, mode_string)
            self.list_lock.release()
        else:
            self.list_lock.acquire()
            self._append_empty_sln_data()
            self.list_lock.release()
        self.ins_used = ((soln.flags & 0x8) >> 3) == 1
        pos_table = []
        soln.h_accuracy *= 1e-3
        soln.v_accuracy *= 1e-3

        tow = soln.tow * 1e-3
        if self.nsec is not None:
            tow += self.nsec * 1e-9

        # Return the best estimate of my local and receiver time in convenient
        # format that allows changing precision of the seconds
        ((tloc, secloc), (tgps, secgps)) = log_time_strings(self.week, tow)
        if self.utc_time:
            ((tutc, secutc)) = datetime_2_str(self.utc_time)

        if (self.directory_name_p == ''):
            filepath_p = time.strftime("position_log_%Y%m%d-%H%M%S.csv")
        else:
            filepath_p = os.path.join(
                self.directory_name_p,
                time.strftime("position_log_%Y%m%d-%H%M%S.csv"))

        if not self.logging_p:
            self.log_file = None

        if self.logging_p:
            if self.log_file is None:
                self.log_file = sopen(filepath_p, 'w')
                self.log_file.write(
                    "pc_time,gps_time,tow(sec),latitude(degrees),longitude(degrees),altitude(meters),"
                    "h_accuracy(meters),v_accuracy(meters),n_sats,flags\n")
            log_str_gps = ""
            if tgps != "" and secgps != 0:
                log_str_gps = "{0}:{1:06.6f}".format(tgps, float(secgps))
            self.log_file.write(
                '%s,%s,%.3f,%.10f,%.10f,%.4f,%.4f,%.4f,%d,%d\n' %
                ("{0}:{1:06.6f}".format(tloc, float(secloc)), log_str_gps, tow,
                 soln.lat, soln.lon, soln.height, soln.h_accuracy,
                 soln.v_accuracy, soln.n_sats, soln.flags))
            self.log_file.flush()

        if self.last_pos_mode == 0:
            pos_table.append(('GPS Week', EMPTY_STR))
            pos_table.append(('GPS TOW', EMPTY_STR))
            pos_table.append(('GPS Time', EMPTY_STR))
            pos_table.append(('Num. Signals', EMPTY_STR))
            pos_table.append(('Lat', EMPTY_STR))
            pos_table.append(('Lng', EMPTY_STR))
            pos_table.append(('Height', EMPTY_STR))
            pos_table.append(('Horiz Acc', EMPTY_STR))
            pos_table.append(('Vert Acc', EMPTY_STR))
        else:
            self.last_stime_update = time.time()

            if self.week is not None:
                pos_table.append(('GPS Week', str(self.week)))
            pos_table.append(('GPS TOW', "{:.3f}".format(tow)))

            if self.week is not None:
                pos_table.append(('GPS Time', "{0}:{1:06.3f}".format(
                    tgps, float(secgps))))
            if self.utc_time is not None:
                pos_table.append(('UTC Time', "{0}:{1:06.3f}".format(
                    tutc, float(secutc))))
                pos_table.append(('UTC Src', self.utc_source))
            if self.utc_time is None:
                pos_table.append(('UTC Time', EMPTY_STR))
                pos_table.append(('UTC Src', EMPTY_STR))

            pos_table.append(('Sats Used', soln.n_sats))
            pos_table.append(('Lat', soln.lat))
            pos_table.append(('Lng', soln.lon))
            pos_table.append(('Height', "{0:.3f}".format(soln.height)))
            pos_table.append(('Horiz Acc', soln.h_accuracy))
            pos_table.append(('Vert Acc', soln.v_accuracy))

        pos_table.append(('Pos Flags', '0x%03x' % soln.flags))
        pos_table.append(('INS Used', '{}'.format(self.ins_used)))
        pos_table.append(('Pos Fix Mode', mode_dict[self.last_pos_mode]))
        if self.age_corrections is not None:
            pos_table.append(('Corr. Age [s]', self.age_corrections))

        # only store valid solutions for auto survey and degrees to meter transformation
        if self.last_pos_mode != 0:
            self.lats.append(soln.lat)
            self.lngs.append(soln.lon)
            self.alts.append(soln.height)
            self.tows.append(soln.tow)
            self.modes.append(self.last_pos_mode)
            self.last_valid_soln = soln
        self.auto_survey()

        # set-up table variables
        self.pos_table = pos_table
        self.update_table()
        # setup_plot variables
        # Updating array plot data is not thread safe, so we have to fire an event
        # and have the GUI thread do it
        if time.time() - self.last_plot_update_time > GUI_UPDATE_PERIOD:
            GUI.invoke_later(self._solution_draw)

    def _display_units_changed(self):
        # we store current extents of plot and current scalefactlrs
        self.scaling_lock.acquire()
        self.recenter = True  # recenter flag tells _solution_draw to update view extents
        self.prev_extents = (self.plot.index_range.low_setting,
                             self.plot.index_range.high_setting,
                             self.plot.value_range.low_setting,
                             self.plot.value_range.high_setting)
        self.prev_offsets = (self.offset[0], self.offset[1])
        self.prev_sfs = (self.sf[0], self.sf[1])
        if self.display_units == "meters":
            self.offset = (np.mean(np.array(self.lats)[~(np.equal(np.array(self.modes), 0))]),
                           np.mean(np.array(self.lngs)[~(np.equal(np.array(self.modes), 0))]),
                           np.mean(np.array(self.alts)[~(np.equal(np.array(self.modes), 0))]))
            (self.meters_per_lat, self.meters_per_lon) = meters_per_deg(
                np.mean(np.array(self.lats)[~(np.equal(np.array(self.modes), 0))]))
            self.sf = (self.meters_per_lat, self.meters_per_lon)
            self.plot.value_axis.title = 'Latitude (meters)'
            self.plot.index_axis.title = 'Longitude (meters)'
        else:
            self.offset = (0, 0, 0)
            self.sf = (1, 1)
            self.plot.value_axis.title = 'Latitude (degrees)'
            self.plot.index_axis.title = 'Longitude (degrees)'
        self.scaling_lock.release()
        self.list_lock.acquire()
        # now we update the existing sln deques to go from meters back to degrees or vice versa
        for each_array in self.slns:
            index = 0 if 'lat' in str(each_array) else 1
            # going from degrees to meters; do scaling with new offset and sf
            if self.display_units == "meters":
                self.slns[each_array] = deque((np.array(self.slns[each_array]) -
                                               self.offset[index]) * self.sf[index],
                                              maxlen=PLOT_HISTORY_MAX)
            # going from degrees to meters; do inverse scaling with former offset and sf
            if self.display_units == "degrees":
                self.slns[each_array] = deque(np.array(self.slns[each_array]) / self.prev_sfs[index] +
                                              self.prev_offsets[index],
                                              maxlen=PLOT_HISTORY_MAX)
        self.pending_draw_modes = mode_string_dict.values()
        self.list_lock.release()

    def rescale_for_units_change(self):
        # Chaco scales view automatically when 'auto' is stored
        if self.prev_extents[0] != 'auto':
            # Otherwise use has used mousewheel zoom and we need to transform
            if self.display_units == 'meters':
                new_scaling = (
                    (self.prev_extents[0] - self.offset[1]) * self.sf[1],
                    (self.prev_extents[1] - self.offset[1]) * self.sf[1],
                    (self.prev_extents[2] - self.offset[0]) * self.sf[0],
                    (self.prev_extents[3] - self.offset[0]) * self.sf[0])
            else:
                new_scaling = (
                    self.prev_extents[0] / self.prev_sfs[1] + self.prev_offsets[1],
                    self.prev_extents[1] / self.prev_sfs[1] + self.prev_offsets[1],
                    self.prev_extents[2] / self.prev_sfs[0] + self.prev_offsets[0],
                    self.prev_extents[3] / self.prev_sfs[0] + self.prev_offsets[0]
                )

            # set plot scaling accordingly
            self.plot.index_range.low_setting = new_scaling[0]
            self.plot.index_range.high_setting = new_scaling[1]
            self.plot.value_range.low_setting = new_scaling[2]
            self.plot.value_range.high_setting = new_scaling[3]

    def _solution_draw(self):
        self.list_lock.acquire()
        current_time = time.time()
        self.last_plot_update_time = current_time
        pending_draw_modes = self.pending_draw_modes
        current_mode = pending_draw_modes[-1] if len(pending_draw_modes) > 0 else None
        # Periodically, we make sure to redraw older data to expire old plot data
        if current_time - self.last_stale_update_time > STALE_DATA_PERIOD:
            # we don't update old solution modes every timestep to try and save CPU
            pending_draw_modes = mode_string_dict.values()
            self.last_stale_update_time = current_time
        for mode_string in pending_draw_modes:
            if self.running:
                update_current = mode_string == current_mode if current_mode else True
                self._synchronize_plot_data_by_mode(mode_string, update_current=update_current)
                if mode_string in self.pending_draw_modes:
                    self.pending_draw_modes.remove(mode_string)

        self.list_lock.release()
        if not self.zoomall and self.position_centered and self.running and self.last_valid_soln:
            d = (
                self.plot.index_range.high - self.plot.index_range.low) / 2.
            self.plot.index_range.set_bounds(
                (self.last_valid_soln.lon - self.offset[1]) * self.sf[1] - d,
                (self.last_valid_soln.lon - self.offset[1]) * self.sf[1] + d)
            d = (
                self.plot.value_range.high - self.plot.value_range.low) / 2.
            self.plot.value_range.set_bounds(
                (self.last_valid_soln.lat - self.offset[0]) * self.sf[0] - d,
                (self.last_valid_soln.lat - self.offset[0]) * self.sf[0] + d)
        if self.zoomall:
            self.recenter = False
            plot_square_axes(self.plot,
                             ('lng_spp', 'lng_dgnss', 'lng_float',
                              'lng_fixed', 'lng_sbas', 'lng_dr'),
                             ('lat_spp', 'lat_dgnss', 'lat_float',
                              'lat_fixed', 'lat_sbas', 'lat_dr'))
        if self.recenter:
            try:
                self.rescale_for_units_change()
                self.recenter = False
            except AttributeError:
                pass

    def dops_callback(self, sbp_msg, **metadata):
        flags = 0
        if sbp_msg.msg_type == SBP_MSG_DOPS_DEP_A:
            dops = MsgDopsDepA(sbp_msg)
            flags = 1
        else:
            dops = MsgDops(sbp_msg)
            flags = dops.flags
        if flags != 0:
            self.dops_table = [('PDOP', '%.1f' % (dops.pdop * 0.01)),
                               ('GDOP', '%.1f' % (dops.gdop * 0.01)),
                               ('TDOP', '%.1f' % (dops.tdop * 0.01)),
                               ('HDOP', '%.1f' %
                                (dops.hdop * 0.01)), ('VDOP', '%.1f' %
                                                      (dops.vdop * 0.01))]
        else:
            self.dops_table = [('PDOP', EMPTY_STR), ('GDOP', EMPTY_STR),
                               ('TDOP', EMPTY_STR), ('HDOP', EMPTY_STR),
                               ('VDOP', EMPTY_STR)]

        self.dops_table.append(('DOPS Flags', '0x%03x' % flags))

    def vel_ned_callback(self, sbp_msg, **metadata):
        flags = 0
        if sbp_msg.msg_type == SBP_MSG_VEL_NED_DEP_A:
            vel_ned = MsgVelNEDDepA(sbp_msg)
            flags = 1
        else:
            vel_ned = MsgVelNED(sbp_msg)
            flags = vel_ned.flags
        tow = vel_ned.tow * 1e-3
        if self.nsec is not None:
            tow += self.nsec * 1e-9

        ((tloc, secloc), (tgps, secgps)) = log_time_strings(self.week, tow)

        if self.directory_name_v == '':
            filepath_v = time.strftime("velocity_log_%Y%m%d-%H%M%S.csv")
        else:
            filepath_v = os.path.join(
                self.directory_name_v,
                time.strftime("velocity_log_%Y%m%d-%H%M%S.csv"))

        if not self.logging_v:
            self.vel_log_file = None

        if self.logging_v:
            if self.vel_log_file is None:
                self.vel_log_file = sopen(filepath_v, 'w')
                self.vel_log_file.write(
                    'pc_time,gps_time,tow(sec),north(m/s),east(m/s),down(m/s),speed(m/s),flags,num_signals\n'
                )
            log_str_gps = ''
            if tgps != "" and secgps != 0:
                log_str_gps = "{0}:{1:06.6f}".format(tgps, float(secgps))
            self.vel_log_file.write(
                '%s,%s,%.3f,%.6f,%.6f,%.6f,%.6f,%d,%d\n' %
                ("{0}:{1:06.6f}".format(tloc, float(secloc)), log_str_gps, tow,
                 vel_ned.n * 1e-3, vel_ned.e * 1e-3, vel_ned.d * 1e-3,
                 math.sqrt(vel_ned.n * vel_ned.n + vel_ned.e * vel_ned.e
                           ) * 1e-3, flags, vel_ned.n_sats))
            self.vel_log_file.flush()
        if (flags & 0x7) != 0:
            self.vel_table = [
                ('Vel. N', '% 8.4f' % (vel_ned.n * 1e-3)),
                ('Vel. E', '% 8.4f' % (vel_ned.e * 1e-3)),
                ('Vel. D', '% 8.4f' % (vel_ned.d * 1e-3)),
            ]
        else:
            self.vel_table = [
                ('Vel. N', EMPTY_STR),
                ('Vel. E', EMPTY_STR),
                ('Vel. D', EMPTY_STR),
            ]
        self.vel_table.append(('Vel Flags', '0x%03x' % flags))
        self.update_table()

    def gps_time_callback(self, sbp_msg, **metadata):
        if sbp_msg.msg_type == SBP_MSG_GPS_TIME_DEP_A:
            time_msg = MsgGPSTimeDepA(sbp_msg)
            flags = 1
        elif sbp_msg.msg_type == SBP_MSG_GPS_TIME:
            time_msg = MsgGPSTime(sbp_msg)
            flags = time_msg.flags
            if flags != 0:
                self.week = time_msg.wn
                self.nsec = time_msg.ns_residual

    def utc_time_callback(self, sbp_msg, **metadata):
        tmsg = MsgUtcTime(sbp_msg)
        microseconds = int(tmsg.ns / 1000.00)
        if tmsg.flags & 0x7 != 0:
            dt = datetime.datetime(tmsg.year, tmsg.month, tmsg.day, tmsg.hours,
                                   tmsg.minutes, tmsg.seconds, microseconds)
            self.utc_time = dt
            self.utc_time_flags = tmsg.flags
            if (tmsg.flags >> 3) & 0x3 == 0:
                self.utc_source = "Factory Default"
            elif (tmsg.flags >> 3) & 0x3 == 1:
                self.utc_source = "Non Volatile Memory"
            elif (tmsg.flags >> 3) & 0x3 == 2:
                self.utc_source = "Decoded this Session"
            else:
                self.utc_source = "Unknown"
        else:
            self.utc_time = None
            self.utc_source = None

    def __init__(self, link, dirname=''):
        super(SolutionView, self).__init__()
        self.pending_draw_modes = []
        self.recenter = False
        self.offset = (0, 0, 0)
        self.sf = (1, 1)
        self.list_lock = threading.Lock()
        self.scaling_lock = threading.Lock()
        self.slns = {'lat_spp': deque(maxlen=PLOT_HISTORY_MAX),
                     'lng_spp': deque(maxlen=PLOT_HISTORY_MAX),
                     'alt_spp': deque(maxlen=PLOT_HISTORY_MAX),
                     'lat_dgnss': deque(maxlen=PLOT_HISTORY_MAX),
                     'lng_dgnss': deque(maxlen=PLOT_HISTORY_MAX),
                     'alt_dgnss': deque(maxlen=PLOT_HISTORY_MAX),
                     'lat_float': deque(maxlen=PLOT_HISTORY_MAX),
                     'lng_float': deque(maxlen=PLOT_HISTORY_MAX),
                     'alt_float': deque(maxlen=PLOT_HISTORY_MAX),
                     'lat_fixed': deque(maxlen=PLOT_HISTORY_MAX),
                     'lng_fixed': deque(maxlen=PLOT_HISTORY_MAX),
                     'alt_fixed': deque(maxlen=PLOT_HISTORY_MAX),
                     'lat_sbas': deque(maxlen=PLOT_HISTORY_MAX),
                     'lng_sbas': deque(maxlen=PLOT_HISTORY_MAX),
                     'alt_sbas': deque(maxlen=PLOT_HISTORY_MAX),
                     'lat_dr': deque(maxlen=PLOT_HISTORY_MAX),
                     'lng_dr': deque(maxlen=PLOT_HISTORY_MAX),
                     'alt_dr': deque(maxlen=PLOT_HISTORY_MAX)}
        self.lats = deque(maxlen=PLOT_HISTORY_MAX)
        self.lngs = deque(maxlen=PLOT_HISTORY_MAX)
        self.alts = deque(maxlen=PLOT_HISTORY_MAX)
        self.tows = deque(maxlen=PLOT_HISTORY_MAX)
        self.modes = deque(maxlen=PLOT_HISTORY_MAX)
        self.log_file = None
        self.directory_name_v = dirname
        self.directory_name_p = dirname
        self.vel_log_file = None
        self.last_stime_update = 0
        self.last_soln = None
        self.last_valid_soln = None

        self.altitude = 0
        self.longitude = 0
        self.latitude = 0
        self.last_pos_mode = 0
        self.ins_used = False
        self.last_plot_update_time = 0
        self.last_stale_update_time = 0

        self.plot_data = ArrayPlotData(
            lat_spp=[],
            lng_spp=[],
            alt_spp=[],
            cur_lat_spp=[],
            cur_lng_spp=[],
            lat_dgnss=[],
            lng_dgnss=[],
            alt_dgnss=[],
            cur_lat_dgnss=[],
            cur_lng_dgnss=[],
            lat_float=[],
            lng_float=[],
            alt_float=[],
            cur_lat_float=[],
            cur_lng_float=[],
            lat_fixed=[],
            lng_fixed=[],
            alt_fixed=[],
            cur_lat_fixed=[],
            cur_lng_fixed=[],
            lat_sbas=[],
            lng_sbas=[],
            cur_lat_sbas=[],
            cur_lng_sbas=[],
            lng_dr=[],
            lat_dr=[],
            cur_lat_dr=[],
            cur_lng_dr=[]
        )
        self.plot = Plot(self.plot_data)

        # 1000 point buffer
        self.plot.plot(
            ('lng_spp', 'lat_spp'),
            type='line',
            line_width=0.1,
            name='',
            color=color_dict[SPP_MODE])
        self.plot.plot(
            ('lng_spp', 'lat_spp'),
            type='scatter',
            name='',
            color=color_dict[SPP_MODE],
            marker='dot',
            line_width=0.0,
            marker_size=1.0)
        self.plot.plot(
            ('lng_dgnss', 'lat_dgnss'),
            type='line',
            line_width=0.1,
            name='',
            color=color_dict[DGNSS_MODE])
        self.plot.plot(
            ('lng_dgnss', 'lat_dgnss'),
            type='scatter',
            name='',
            color=color_dict[DGNSS_MODE],
            marker='dot',
            line_width=0.0,
            marker_size=1.0)
        self.plot.plot(
            ('lng_float', 'lat_float'),
            type='line',
            line_width=0.1,
            name='',
            color=color_dict[FLOAT_MODE])
        self.plot.plot(
            ('lng_float', 'lat_float'),
            type='scatter',
            name='',
            color=color_dict[FLOAT_MODE],
            marker='dot',
            line_width=0.0,
            marker_size=1.0)
        self.plot.plot(
            ('lng_fixed', 'lat_fixed'),
            type='line',
            line_width=0.1,
            name='',
            color=color_dict[FIXED_MODE])
        self.plot.plot(
            ('lng_fixed', 'lat_fixed'),
            type='scatter',
            name='',
            color=color_dict[FIXED_MODE],
            marker='dot',
            line_width=0.0,
            marker_size=1.0)
        self.plot.plot(
            ('lng_sbas', 'lat_sbas'),
            type='line',
            line_width=0.1,
            name='',
            color=color_dict[SBAS_MODE])
        self.plot.plot(
            ('lng_sbas', 'lat_sbas'),
            type='scatter',
            name='',
            color=color_dict[SBAS_MODE],
            marker='dot',
            line_width=0.0,
            marker_size=1.0)
        self.plot.plot(
            ('lng_dr', 'lat_dr'),
            type='line',
            line_width=0.1,
            name='',
            color=color_dict[DR_MODE])
        self.plot.plot(
            ('lng_dr', 'lat_dr'),
            type='scatter',
            color=color_dict[DR_MODE],
            marker='dot',
            line_width=0.0,
            marker_size=1.0)
        # current values
        spp = self.plot.plot(
            ('cur_lng_spp', 'cur_lat_spp'),
            type='scatter',
            name=mode_dict[SPP_MODE],
            color=color_dict[SPP_MODE],
            marker='plus',
            line_width=1.5,
            marker_size=5.0)
        dgnss = self.plot.plot(
            ('cur_lng_dgnss', 'cur_lat_dgnss'),
            type='scatter',
            name=mode_dict[DGNSS_MODE],
            color=color_dict[DGNSS_MODE],
            marker='plus',
            line_width=1.5,
            marker_size=5.0)
        rtkfloat = self.plot.plot(
            ('cur_lng_float', 'cur_lat_float'),
            type='scatter',
            name=mode_dict[FLOAT_MODE],
            color=color_dict[FLOAT_MODE],
            marker='plus',
            line_width=1.5,
            marker_size=5.0)
        rtkfix = self.plot.plot(
            ('cur_lng_fixed', 'cur_lat_fixed'),
            type='scatter',
            name=mode_dict[FIXED_MODE],
            color=color_dict[FIXED_MODE],
            marker='plus',
            line_width=1.5,
            marker_size=5.0)
        sbas = self.plot.plot(
            ('cur_lng_sbas', 'cur_lat_sbas'),
            type='scatter',
            name=mode_dict[SBAS_MODE],
            color=color_dict[SBAS_MODE],
            marker='plus',
            line_width=1.5,
            marker_size=5.0)
        dr = self.plot.plot(
            ('cur_lng_dr', 'cur_lat_dr'),
            type='scatter',
            name=mode_dict[DR_MODE],
            color=color_dict[DR_MODE],
            marker='plus',
            line_width=1.5,
            marker_size=5.0)
        plot_labels = ['SPP', 'SBAS', 'DGPS', 'RTK float', 'RTK fixed', 'DR']
        plots_legend = dict(
            zip(plot_labels, [spp, sbas, dgnss, rtkfloat, rtkfix, dr]))
        self.plot.legend.plots = plots_legend
        self.plot.legend.labels = plot_labels  # sets order
        self.plot.legend.visible = True

        self.plot.index_axis.tick_label_position = 'inside'
        self.plot.index_axis.tick_label_color = 'gray'
        self.plot.index_axis.tick_color = 'gray'
        self.plot.index_axis.title = 'Longitude (degrees)'
        self.plot.index_axis.title_spacing = 5
        self.plot.value_axis.tick_label_position = 'inside'
        self.plot.value_axis.tick_label_color = 'gray'
        self.plot.value_axis.tick_color = 'gray'
        self.plot.value_axis.title = 'Latitude (degrees)'
        self.plot.value_axis.title_spacing = 5
        self.plot.padding = (25, 25, 25, 25)

        self.plot.tools.append(PanTool(self.plot))
        zt = ZoomTool(
            self.plot, zoom_factor=1.1, tool_mode="box", always_on=False)
        self.plot.overlays.append(zt)

        self.link = link
        self.link.add_callback(self.pos_llh_callback, [SBP_MSG_POS_LLH_DEP_A, SBP_MSG_POS_LLH])
        self.link.add_callback(self.vel_ned_callback, [SBP_MSG_VEL_NED_DEP_A, SBP_MSG_VEL_NED])
        self.link.add_callback(self.dops_callback, [SBP_MSG_DOPS_DEP_A, SBP_MSG_DOPS])
        self.link.add_callback(self.gps_time_callback, [SBP_MSG_GPS_TIME_DEP_A, SBP_MSG_GPS_TIME])
        self.link.add_callback(self.utc_time_callback, [SBP_MSG_UTC_TIME])
        self.link.add_callback(self.age_corrections_callback, SBP_MSG_AGE_CORRECTIONS)
        self.week = None
        self.utc_time = None
        self.age_corrections = None
        self.nsec = 0
        self.meters_per_lat = None
        self.meters_per_lon = None

        self.python_console_cmds = {
            'solution': self,
        }
