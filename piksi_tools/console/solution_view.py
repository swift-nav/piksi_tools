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

import datetime
import math
import os
import time

import numpy as np
from chaco.api import ArrayPlotData, Plot
from chaco.tools.api import PanTool, ZoomTool
from enable.api import ComponentEditor
from enable.savage.trait_defs.ui.svg_button import SVGButton
from pyface.api import GUI
from sbp.navigation import (SBP_MSG_AGE_CORRECTIONS, SBP_MSG_DOPS,
                            SBP_MSG_DOPS_DEP_A, SBP_MSG_GPS_TIME,
                            SBP_MSG_GPS_TIME_DEP_A, SBP_MSG_POS_LLH,
                            SBP_MSG_POS_LLH_DEP_A, SBP_MSG_UTC_TIME,
                            SBP_MSG_VEL_NED, SBP_MSG_VEL_NED_DEP_A,
                            MsgAgeCorrections, MsgDops, MsgDopsDepA,
                            MsgGPSTime, MsgGPSTimeDepA, MsgPosLLH,
                            MsgPosLLHDepA, MsgUtcTime, MsgVelNED,
                            MsgVelNEDDepA)
from traits.api import (Bool,  Dict, File,  HasTraits,
                        Instance, Int, List, Str, )
from traitsui.api import (HGroup, HSplit, Item, 
                          TabularEditor, TextEditor,  VGroup, View)
from traitsui.tabular_adapter import TabularAdapter

from piksi_tools.console.gui_utils import MultilineTextEditor, plot_square_axes
from piksi_tools.console.utils import (DGNSS_MODE, EMPTY_STR, FIXED_MODE,
                                       FLOAT_MODE, SPP_MODE, call_repeatedly,
                                       color_dict, datetime_2_str,
                                       determine_path, get_mode,
                                       log_time_strings, mode_dict)
from piksi_tools.utils import sopen


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
    logging_v = Bool(False)
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
        filename=os.path.join(determine_path(), 'images', 'iconic', 'x.svg'),
        width=16,
        height=16)
    zoomall_button = SVGButton(
        label='',
        tooltip='Zoom All',
        toggle=True,
        filename=os.path.join(determine_path(), 'images', 'iconic',
                              'fullscreen.svg'),
        width=16,
        height=16)
    center_button = SVGButton(
        label='',
        tooltip='Center on Solution',
        toggle=True,
        filename=os.path.join(determine_path(), 'images', 'iconic',
                              'target.svg'),
        width=16,
        height=16)
    paused_button = SVGButton(
        label='',
        tooltip='Pause',
        toggle_tooltip='Run',
        toggle=True,
        filename=os.path.join(determine_path(), 'images', 'iconic',
                              'pause.svg'),
        toggle_filename=os.path.join(determine_path(), 'images', 'iconic',
                                     'play.svg'),
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
                    Item('center_button', show_label=False), ),
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
        self.plot_data.set_data('cur_lat_spp', [])
        self.plot_data.set_data('cur_lng_spp', [])
        self.plot_data.set_data('cur_alt_spp', [])
        self.plot_data.set_data('cur_lat_dgnss', [])
        self.plot_data.set_data('cur_lng_dgnss', [])
        self.plot_data.set_data('cur_alt_dgnss', [])
        self.plot_data.set_data('cur_lat_float', [])
        self.plot_data.set_data('cur_lng_float', [])
        self.plot_data.set_data('cur_alt_float', [])
        self.plot_data.set_data('cur_lat_fixed', [])
        self.plot_data.set_data('cur_lng_fixed', [])
        self.plot_data.set_data('cur_alt_fixed', [])

    def _clear_history(self):
        self.plot_data.set_data('lat_spp', [])
        self.plot_data.set_data('lng_spp', [])
        self.plot_data.set_data('alt_spp', [])
        self.plot_data.set_data('lat_dgnss', [])
        self.plot_data.set_data('lng_dgnss', [])
        self.plot_data.set_data('alt_dgnss', [])
        self.plot_data.set_data('lat_float', [])
        self.plot_data.set_data('lng_float', [])
        self.plot_data.set_data('alt_float', [])
        self.plot_data.set_data('lat_fixed', [])
        self.plot_data.set_data('lng_fixed', [])
        self.plot_data.set_data('alt_fixed', [])

    def _clear_button_fired(self):
        self.tows = np.empty(self.plot_history_max)
        self.lats = np.empty(self.plot_history_max)
        self.lngs = np.empty(self.plot_history_max)
        self.alts = np.empty(self.plot_history_max)
        self.modes = np.empty(self.plot_history_max)
        self._clear_history()
        self._reset_remove_current()

    def _pos_llh_callback(self, sbp_msg, **metadata):
        # Updating an ArrayPlotData isn't thread safe (see chaco issue #9), so
        # actually perform the update in the UI thread.
        if self.running:
            GUI.invoke_later(self.pos_llh_callback, sbp_msg)

    def age_corrections_callback(self, sbp_msg, **metadata):
        age_msg = MsgAgeCorrections(sbp_msg)
        if age_msg.age != 0xFFFF:
            self.age_corrections = age_msg.age / 10.0
        else:
            self.age_corrections = None

    def update_table(self):
        self.table = self.pos_table + self.vel_table + self.dops_table

    def auto_survey(self):
        if self.last_soln.flags != 0:
            self.latitude_list.append(self.last_soln.lat)
            self.longitude_list.append(self.last_soln.lon)
            self.altitude_list.append(self.last_soln.height)
        if len(self.latitude_list) > 1000:
            self.latitude_list = self.latitude_list[-1000:]
            self.longitude_list = self.longitude_list[-1000:]
            self.altitude_list = self.altitude_list[-1000:]
        if len(self.latitude_list) != 0:
            self.latitude = sum(self.latitude_list) / len(self.latitude_list)
            self.altitude = sum(self.altitude_list) / len(self.latitude_list)
            self.longitude = sum(self.longitude_list) / len(self.latitude_list)

    def pos_llh_callback(self, sbp_msg, **metadata):
        if sbp_msg.msg_type == SBP_MSG_POS_LLH_DEP_A:
            soln = MsgPosLLHDepA(sbp_msg)
        else:
            soln = MsgPosLLH(sbp_msg)
        self.last_soln = soln

        self.last_pos_mode = get_mode(soln)
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
                    "pc_time,gps_time,tow(msec),latitude(degrees),longitude(degrees),altitude(meters),"
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
        pos_table.append(('Pos Fix Mode', mode_dict[self.last_pos_mode]))
        if self.age_corrections is not None:
            pos_table.append(('Corr. Age [s]', self.age_corrections))

        self.auto_survey()

        # set-up table variables
        self.pos_table = pos_table
        self.update_table()
        # setup_plot variables
        self.lats[1:] = self.lats[:-1]
        self.lngs[1:] = self.lngs[:-1]
        self.alts[1:] = self.alts[:-1]
        self.tows[1:] = self.tows[:-1]
        self.modes[1:] = self.modes[:-1]

        self.lats[0] = soln.lat
        self.lngs[0] = soln.lon
        self.alts[0] = soln.height
        self.tows[0] = soln.tow
        self.modes[0] = self.last_pos_mode

        self.lats = self.lats[-self.plot_history_max:]
        self.lngs = self.lngs[-self.plot_history_max:]
        self.alts = self.alts[-self.plot_history_max:]
        self.tows = self.tows[-self.plot_history_max:]
        self.modes = self.modes[-self.plot_history_max:]

    def solution_draw(self):
        if self.running:
            GUI.invoke_later(self._solution_draw)

    def _solution_draw(self):
        spp_indexer, dgnss_indexer, float_indexer, fixed_indexer = None, None, None, None
        self._clear_history()
        soln = self.last_soln
        if np.any(self.modes):
            spp_indexer = (self.modes == SPP_MODE)
            dgnss_indexer = (self.modes == DGNSS_MODE)
            float_indexer = (self.modes == FLOAT_MODE)
            fixed_indexer = (self.modes == FIXED_MODE)

            # make sure that there is at least one true in indexer before setting
            if any(spp_indexer):
                self.plot_data.set_data('lat_spp', self.lats[spp_indexer])
                self.plot_data.set_data('lng_spp', self.lngs[spp_indexer])
                self.plot_data.set_data('alt_spp', self.alts[spp_indexer])
            if any(dgnss_indexer):
                self.plot_data.set_data('lat_dgnss', self.lats[dgnss_indexer])
                self.plot_data.set_data('lng_dgnss', self.lngs[dgnss_indexer])
                self.plot_data.set_data('alt_dgnss', self.alts[dgnss_indexer])
            if any(float_indexer):
                self.plot_data.set_data('lat_float', self.lats[float_indexer])
                self.plot_data.set_data('lng_float', self.lngs[float_indexer])
                self.plot_data.set_data('alt_float', self.alts[float_indexer])
            if any(fixed_indexer):
                self.plot_data.set_data('lat_fixed', self.lats[fixed_indexer])
                self.plot_data.set_data('lng_fixed', self.lngs[fixed_indexer])
                self.plot_data.set_data('alt_fixed', self.alts[fixed_indexer])

            # update our "current solution" icon
            if self.last_pos_mode == SPP_MODE:
                self._reset_remove_current()
                self.plot_data.set_data('cur_lat_spp', [soln.lat])
                self.plot_data.set_data('cur_lng_spp', [soln.lon])
            elif self.last_pos_mode == DGNSS_MODE:
                self._reset_remove_current()
                self.plot_data.set_data('cur_lat_dgnss', [soln.lat])
                self.plot_data.set_data('cur_lng_dgnss', [soln.lon])
            elif self.last_pos_mode == FLOAT_MODE:
                self._reset_remove_current()
                self.plot_data.set_data('cur_lat_float', [soln.lat])
                self.plot_data.set_data('cur_lng_float', [soln.lon])
            elif self.last_pos_mode == FIXED_MODE:
                self._reset_remove_current()
                self.plot_data.set_data('cur_lat_fixed', [soln.lat])
                self.plot_data.set_data('cur_lng_fixed', [soln.lon])
            else:
                pass

        # TODO: figure out how to center the graph now that we have two separate messages
        # when we selectively send only SPP, the centering function won't work anymore

        if not self.zoomall and self.position_centered:
            d = (self.plot.index_range.high - self.plot.index_range.low) / 2.
            self.plot.index_range.set_bounds(soln.lon - d, soln.lon + d)
            d = (self.plot.value_range.high - self.plot.value_range.low) / 2.
            self.plot.value_range.set_bounds(soln.lat - d, soln.lat + d)
        if self.zoomall:
            plot_square_axes(self.plot, ('lng_spp', 'lng_dgnss', 'lng_float',
                                         'lng_fixed'),
                             ('lat_spp', 'lat_dgnss', 'lat_float',
                              'lat_fixed'))

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
                    'pc_time,gps_time,tow,north(m/s),east(m/s),down(m/s),speed(m/s),flags,num_signals\n'
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
        if flags != 0:
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
        seconds = math.floor(tmsg.seconds)
        microseconds = int(tmsg.ns / 1000.00)
        if tmsg.flags & 0x1 == 1:
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

        self.lats = np.zeros(self.plot_history_max)
        self.lngs = np.zeros(self.plot_history_max)
        self.alts = np.zeros(self.plot_history_max)
        self.tows = np.zeros(self.plot_history_max)
        self.modes = np.zeros(self.plot_history_max)
        self.log_file = None
        self.directory_name_v = dirname
        self.directory_name_p = dirname
        self.vel_log_file = None
        self.last_stime_update = 0
        self.last_soln = None

        self.counter = 0
        self.latitude_list = []
        self.longitude_list = []
        self.altitude_list = []
        self.altitude = 0
        self.longitude = 0
        self.latitude = 0
        self.last_pos_mode = 0

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
            cur_lng_fixed=[])
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
        plot_labels = ['SPP', 'DGPS', "RTK float", "RTK fixed"]
        plots_legend = dict(zip(plot_labels, [spp, dgnss, rtkfloat, rtkfix]))
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
        self.link.add_callback(self.pos_llh_callback,
                               [SBP_MSG_POS_LLH_DEP_A, SBP_MSG_POS_LLH])
        self.link.add_callback(self.vel_ned_callback,
                               [SBP_MSG_VEL_NED_DEP_A, SBP_MSG_VEL_NED])
        self.link.add_callback(self.dops_callback,
                               [SBP_MSG_DOPS_DEP_A, SBP_MSG_DOPS])
        self.link.add_callback(self.gps_time_callback,
                               [SBP_MSG_GPS_TIME_DEP_A, SBP_MSG_GPS_TIME])
        self.link.add_callback(self.utc_time_callback, [SBP_MSG_UTC_TIME])
        self.link.add_callback(self.age_corrections_callback,
                               SBP_MSG_AGE_CORRECTIONS)
        call_repeatedly(0.2, self.solution_draw)

        self.week = None
        self.utc_time = None
        self.age_corrections = None
        self.nsec = 0

        self.python_console_cmds = {
            'solution': self,
        }
