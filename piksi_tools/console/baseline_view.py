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
    SBP_MSG_AGE_CORRECTIONS, SBP_MSG_BASELINE_NED,
    SBP_MSG_BASELINE_NED_DEP_A, SBP_MSG_GPS_TIME, SBP_MSG_GPS_TIME_DEP_A,
    SBP_MSG_UTC_TIME, MsgAgeCorrections, MsgBaselineNEDDepA, MsgGPSTime,
    MsgGPSTimeDepA, MsgUtcTime)
from sbp.orientation import SBP_MSG_BASELINE_HEADING, MsgBaselineHeading
from sbp.piksi import MsgResetFilters
from traits.api import Bool, Button, Float, Dict, File, HasTraits, Instance, List
from traitsui.api import HGroup, HSplit, Item, TabularEditor, VGroup, View
from traitsui.tabular_adapter import TabularAdapter

from piksi_tools.console.gui_utils import plot_square_axes
from piksi_tools.console.utils import (
    DGNSS_MODE, EMPTY_STR, FIXED_MODE, FLOAT_MODE, color_dict,
    datetime_2_str, get_mode, log_time_strings, mode_dict)
from piksi_tools.utils import sopen
from .utils import resource_filename
from .gui_utils import GUI_UPDATE_PERIOD, STALE_DATA_PERIOD

PLOT_HISTORY_MAX = 1000

mode_string_dict = {2: 'dgnss', 3: 'float', 4: 'fixed'}


class SimpleAdapter(TabularAdapter):
    columns = [('Item', 0), ('Value', 1)]
    width = 80


class BaselineView(HasTraits):

    # This mapping should match the flag definitions in libsbp for
    # the MsgBaselineNED message. While this isn't strictly necessary
    # it helps avoid confusion

    python_console_cmds = Dict()
    last_plot_update_time = Float()
    last_stale_update_time = Float()

    table = List()

    logging_b = Bool(False)
    directory_name_b = File

    plot = Instance(Plot)
    plot_data = Instance(ArrayPlotData)

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
        tooltip='Center on Baseline',
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

    reset_button = Button(label='Reset Filters')

    traits_view = View(
        HSplit(
            Item(
                'table',
                style='readonly',
                editor=TabularEditor(adapter=SimpleAdapter()),
                show_label=False,
                width=0.3),
            VGroup(
                HGroup(
                    Item('paused_button', show_label=False),
                    Item('clear_button', show_label=False),
                    Item('zoomall_button', show_label=False),
                    Item('center_button', show_label=False),
                    Item('reset_button', show_label=False), ),
                Item(
                    'plot',
                    show_label=False,
                    editor=ComponentEditor(bgcolor=(0.8, 0.8, 0.8)), ))))

    def _zoomall_button_fired(self):
        self.zoomall = not self.zoomall

    def _center_button_fired(self):
        self.position_centered = not self.position_centered

    def _paused_button_fired(self):
        self.running = not self.running

    def _reset_button_fired(self):
        self.link(MsgResetFilters(filter=0))

    def _get_update_current(self, current_dict={}):
        out_dict = {'cur_n_fixed': [],
                    'cur_e_fixed': [],
                    'cur_d_fixed': [],
                    'cur_n_float': [],
                    'cur_e_float': [],
                    'cur_d_float': [],
                    'cur_n_dgnss': [],
                    'cur_e_dgnss': [],
                    'cur_d_dgnss': []
                    }
        out_dict.update(current_dict)
        return out_dict

    def _synchronize_plot_data_by_mode(self, mode_string, update_current=False):
        # do all required plot_data updates for a single
        # new solution with mode defined by mode_string
        pending_update = {'n_' + mode_string: [n for n in self.slns['n_' + mode_string] if not np.isnan(n)],
                          'e_' + mode_string: [e for e in self.slns['e_' + mode_string] if not np.isnan(e)]}
        if update_current:
            current = {}
            if len(pending_update['n_' + mode_string]) != 0:
                current = {'cur_n_' + mode_string: [pending_update['n_' + mode_string][-1]],
                           'cur_e_' + mode_string: [pending_update['e_' + mode_string][-1]]}
            else:
                current = {'cur_n_' + mode_string: [],
                           'cur_e_' + mode_string: []}
            pending_update.update(self._get_update_current(current))
        self.plot_data.update_data(pending_update)

    def _append_empty_sln_data(self, exclude_mode=None):
        for each_mode in mode_string_dict.values():
            if exclude_mode is None or each_mode != exclude_mode:
                self.slns['n_' + each_mode].append(np.nan)
                self.slns['e_' + each_mode].append(np.nan)

    def _update_sln_data_by_mode(self, soln, mode_string):
        # do backend deque updates for a new solution of type
        # mode string
        self.slns['n_' + mode_string].append(soln.n)
        self.slns['e_' + mode_string].append(soln.e)
        # Rotate old data out by appending to deque
        self._append_empty_sln_data(exclude_mode=mode_string)

    def _clr_sln_data(self):
        for each in self.slns:
            self.slns[each].clear()

    def _reset_remove_current(self):
        self.plot_data.update_data(self._get_update_current())

    def _clear_history(self):
        self._clr_sln_data()
        pending_update = {'n_fixed': [],
                          'e_fixed': [],
                          'd_fixed': [],
                          'n_float': [],
                          'e_float': [],
                          'd_float': [],
                          'n_dgnss': [],
                          'e_dgnss': [],
                          'd_dgnss': []
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

    def baseline_heading_callback(self, sbp_msg, **metadata):
        headingMsg = MsgBaselineHeading(sbp_msg)
        if headingMsg.flags & 0x7 != 0:
            self.heading = headingMsg.heading * 1e-3
        else:
            self.heading = "---"

    def baseline_callback(self, sbp_msg, **metadata):
        soln = MsgBaselineNEDDepA(sbp_msg)
        table = []
        self.last_btime_update = time.time() # used to drive status bar logic
        self.last_soln = soln

        soln.n = soln.n * 1e-3
        soln.e = soln.e * 1e-3
        soln.d = soln.d * 1e-3
        soln.h_accuracy = soln.h_accuracy * 1e-3
        soln.v_accuracy = soln.v_accuracy * 1e-3

        dist = np.sqrt(soln.n**2 + soln.e**2 + soln.d**2)

        tow = soln.tow * 1e-3
        if self.nsec is not None:
            tow += self.nsec * 1e-9

        ((tloc, secloc), (tgps, secgps)) = log_time_strings(self.week, tow)

        if self.utc_time is not None:
            ((tutc, secutc)) = datetime_2_str(self.utc_time)

        if self.directory_name_b == '':
            filepath = time.strftime("baseline_log_%Y%m%d-%H%M%S.csv")
        else:
            filepath = os.path.join(
                self.directory_name_b,
                time.strftime("baseline_log_%Y%m%d-%H%M%S.csv"))

        if not self.logging_b:
            self.log_file = None

        if self.logging_b:
            if self.log_file is None:
                self.log_file = sopen(filepath, 'w')
                self.log_file.write(
                    'pc_time,gps_time,tow(sec),north(meters),east(meters),down(meters),h_accuracy(meters),v_accuracy(meters),'
                    'distance(meters),num_sats,flags,num_hypothesis\n')
            log_str_gps = ''
            if tgps != '' and secgps != 0:
                log_str_gps = "{0}:{1:06.6f}".format(tgps, float(secgps))
            self.log_file.write(
                '%s,%s,%.3f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%d,%d,%d\n' %
                ("{0}:{1:06.6f}".format(tloc, float(secloc)), log_str_gps, tow,
                 soln.n, soln.e, soln.d, soln.h_accuracy, soln.v_accuracy,
                 dist, soln.n_sats, soln.flags, self.num_hyps))
            self.log_file.flush()

        self.last_mode = get_mode(soln)

        if self.last_mode < 1:
            table.append(('GPS Week', EMPTY_STR))
            table.append(('GPS TOW', EMPTY_STR))
            table.append(('GPS Time', EMPTY_STR))
            table.append(('UTC Time', EMPTY_STR))
            table.append(('UTC Src', EMPTY_STR))
            table.append(('N', EMPTY_STR))
            table.append(('E', EMPTY_STR))
            table.append(('D', EMPTY_STR))
            table.append(('Horiz Acc', EMPTY_STR))
            table.append(('Vert Acc', EMPTY_STR))
            table.append(('Dist.', EMPTY_STR))
            table.append(('Sats Used', EMPTY_STR))
            table.append(('Flags', EMPTY_STR))
            table.append(('Mode', EMPTY_STR))
            table.append(('Heading', EMPTY_STR))
            table.append(('Corr. Age [s]', EMPTY_STR))
        else:
            self.last_btime_update = time.time()
            if self.week is not None:
                table.append(('GPS Week', str(self.week)))
            table.append(('GPS TOW', "{:.3f}".format(tow)))

            if self.week is not None:
                table.append(('GPS Time', "{0}:{1:06.3f}".format(
                    tgps, float(secgps))))
            if self.utc_time is not None:
                table.append(('UTC Time', "{0}:{1:06.3f}".format(
                    tutc, float(secutc))))
                table.append(('UTC Src', self.utc_source))

            table.append(('N', soln.n))
            table.append(('E', soln.e))
            table.append(('D', soln.d))
            table.append(('Horiz Acc', soln.h_accuracy))
            table.append(('Vert Acc', soln.v_accuracy))
            table.append(('Dist.', "{0:.3f}".format(dist)))

            table.append(('Sats Used', soln.n_sats))

            table.append(('Flags', '0x%02x' % soln.flags))
            table.append(('Mode', mode_dict[self.last_mode]))
            if self.heading is not None:
                table.append(('Heading', self.heading))
            if self.age_corrections is not None:
                table.append(('Corr. Age [s]', self.age_corrections))
            else:
                table.append(('Corr. Age [s]', EMPTY_STR))
        self.table = table

        if self.last_mode != 0:
            self.last_valid_soln = soln
            mode_string = mode_string_dict[self.last_mode]
            if mode_string not in self.pending_draw_modes:
                # if we don't already have a pending upate for that mode
                self.pending_draw_modes.append(mode_string)
            self.list_lock.acquire()
            self._update_sln_data_by_mode(soln, mode_string)
            self.list_lock.release()
        else:
            self.list_lock.acquire()
            self._append_empty_sln_data(soln)
            self.list_lock.release()

        if time.time() - self.last_plot_update_time > GUI_UPDATE_PERIOD:
            GUI.invoke_later(self._solution_draw)

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
                self._synchronize_plot_data_by_mode(mode_string, update_current)
                if mode_string in self.pending_draw_modes:
                    self.pending_draw_modes.remove(mode_string)

        self.list_lock.release()
        # make the zoomall win over the position centered button
        if not self.zoomall and self.position_centered and self.running and self.last_valid_soln:
            d = (self.plot.index_range.high - self.plot.index_range.low) / 2.
            self.plot.index_range.set_bounds(self.last_valid_soln.e - d, self.last_valid_soln.e + d)
            d = (self.plot.value_range.high - self.plot.value_range.low) / 2.
            self.plot.value_range.set_bounds(self.last_valid_soln.n - d, self.last_valid_soln.n + d)

        if self.zoomall:
            plot_square_axes(self.plot, ('e_fixed', 'e_float', 'e_dgnss'),
                             ('n_fixed', 'n_float', 'n_dgnss'))

    def __init__(self, link, plot_history_max=1000, dirname=''):
        super(BaselineView, self).__init__()
        self.pending_draw_modes = []
        self.log_file = None
        self.directory_name_b = dirname
        self.num_hyps = 0
        self.last_hyp_update = 0
        self.last_btime_update = 0
        self.last_soln = None
        self.last_valid_soln = None
        self.last_mode = 0
        self.last_plot_update_time = 0
        self.last_stale_update_time = 0
        self.slns = {'n_fixed': deque(maxlen=PLOT_HISTORY_MAX),
                     'e_fixed': deque(maxlen=PLOT_HISTORY_MAX),
                     'd_fixed': deque(maxlen=PLOT_HISTORY_MAX),
                     'n_float': deque(maxlen=PLOT_HISTORY_MAX),
                     'e_float': deque(maxlen=PLOT_HISTORY_MAX),
                     'd_float': deque(maxlen=PLOT_HISTORY_MAX),
                     'n_dgnss': deque(maxlen=PLOT_HISTORY_MAX),
                     'e_dgnss': deque(maxlen=PLOT_HISTORY_MAX),
                     'd_dgnss': deque(maxlen=PLOT_HISTORY_MAX)}
        self.plot_data = ArrayPlotData(
            n_fixed=[],
            e_fixed=[],
            n_float=[],
            e_float=[],
            n_dgnss=[],
            e_dgnss=[],
            t=[0.0],
            ref_n=[0.0],
            ref_e=[0.0],
            cur_e_fixed=[],
            cur_n_fixed=[],
            cur_e_float=[],
            cur_n_float=[],
            cur_e_dgnss=[],
            cur_n_dgnss=[])

        self.list_lock = threading.Lock()
        self.plot = Plot(self.plot_data)
        pts_float = self.plot.plot(  # noqa: F841
            ('e_float', 'n_float'),
            type='scatter',
            color=color_dict[FLOAT_MODE],
            marker='dot',
            line_width=0.0,
            marker_size=1.0)
        pts_fixed = self.plot.plot(  # noqa: F841
            ('e_fixed', 'n_fixed'),
            type='scatter',
            color=color_dict[FIXED_MODE],
            marker='dot',
            line_width=0.0,
            marker_size=1.0)
        pts_dgnss = self.plot.plot(  # noqa: F841
            ('e_dgnss', 'n_dgnss'),
            type='scatter',
            color=color_dict[DGNSS_MODE],
            marker='dot',
            line_width=0.0,
            marker_size=1.0)
        ref = self.plot.plot(
            ('ref_e', 'ref_n'),
            type='scatter',
            color='red',
            marker='plus',
            marker_size=5,
            line_width=1.5)
        cur_fixed = self.plot.plot(
            ('cur_e_fixed', 'cur_n_fixed'),
            type='scatter',
            color=color_dict[FIXED_MODE],
            marker='plus',
            marker_size=5,
            line_width=1.5)
        cur_float = self.plot.plot(
            ('cur_e_float', 'cur_n_float'),
            type='scatter',
            color=color_dict[FLOAT_MODE],
            marker='plus',
            marker_size=5,
            line_width=1.5)
        cur_dgnss = self.plot.plot(
            ('cur_e_dgnss', 'cur_n_dgnss'),
            type='scatter',
            color=color_dict[DGNSS_MODE],
            marker='plus',
            line_width=1.5,
            marker_size=5)
        plot_labels = [' Base Position', 'DGPS', 'RTK Float', 'RTK Fixed']
        plots_legend = dict(
            zip(plot_labels, [ref, cur_dgnss, cur_float, cur_fixed]))
        self.plot.legend.plots = plots_legend
        self.plot.legend.labels = plot_labels  # sets order
        self.plot.legend.visible = True

        self.plot.index_axis.tick_label_position = 'inside'
        self.plot.index_axis.tick_label_color = 'gray'
        self.plot.index_axis.tick_color = 'gray'
        self.plot.index_axis.title = 'E (meters)'
        self.plot.index_axis.title_spacing = 5
        self.plot.value_axis.tick_label_position = 'inside'
        self.plot.value_axis.tick_label_color = 'gray'
        self.plot.value_axis.tick_color = 'gray'
        self.plot.value_axis.title = 'N (meters)'
        self.plot.value_axis.title_spacing = 5
        self.plot.padding = (25, 25, 25, 25)

        self.plot.tools.append(PanTool(self.plot))
        zt = ZoomTool(
            self.plot, zoom_factor=1.1, tool_mode="box", always_on=False)
        self.plot.overlays.append(zt)

        self.week = None
        self.utc_time = None
        self.age_corrections = None
        self.heading = "---"
        self.nsec = 0

        self.link = link
        self.link.add_callback(self.baseline_callback, [
            SBP_MSG_BASELINE_NED, SBP_MSG_BASELINE_NED_DEP_A
        ])
        self.link.add_callback(self.baseline_heading_callback,
                               [SBP_MSG_BASELINE_HEADING])
        self.link.add_callback(self.gps_time_callback,
                               [SBP_MSG_GPS_TIME, SBP_MSG_GPS_TIME_DEP_A])
        self.link.add_callback(self.utc_time_callback, [SBP_MSG_UTC_TIME])
        self.link.add_callback(self.age_corrections_callback,
                               SBP_MSG_AGE_CORRECTIONS)

        self.python_console_cmds = {'baseline': self}
