#!/usr/bin/env python3

# Copyright (C) 2011-2014 Swift Navigation Inc.
# Contact: Fergus Noble <fergus@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

from __future__ import print_function

import argparse
# Logging
import logging
import os
import signal
import sys
import time
from monotonic import monotonic
# Shut chaco up for now
import warnings

import sbp.client as sbpc
from sbp.client.loggers.json_logger import JSONLogIterator
from enable.savage.trait_defs.ui.svg_button import SVGButton
from pyface.image_resource import ImageResource
from sbp.ext_events import SBP_MSG_EXT_EVENT, MsgExtEvent
from sbp.logging import SBP_MSG_LOG, SBP_MSG_PRINT_DEP
from sbp.piksi import SBP_MSG_COMMAND_RESP, MsgCommandResp, MsgReset
from sbp.system import SBP_MSG_HEARTBEAT
from traits.api import (Bool, Dict, Directory, Enum, HasTraits, Instance, Int,
                        Str)
from traitsui.api import (Handler, HGroup, ImageEditor,
                          InstanceEditor, Item, Spring,
                          Tabbed, TextEditor, UItem, VGroup, View, VSplit)

import piksi_tools.serial_link as s
from piksi_tools import __version__ as CONSOLE_VERSION
from piksi_tools.console.baseline_view import BaselineView
from piksi_tools.console.callback_prompt import CallbackPrompt, ok_button
from piksi_tools.console.port_chooser import get_args_from_port_chooser
from piksi_tools.console.deprecated import DeprecatedMessageHandler
from piksi_tools.console.imu_view import IMUView
from piksi_tools.console.mag_view import MagView
from piksi_tools.console.observation_view import ObservationView
from piksi_tools.console.output_list import (
    DEFAULT_LOG_LEVEL_FILTER, SYSLOG_LEVELS, OutputList, str_to_log_level)
from piksi_tools.console.sbp_relay_view import SbpRelayView
from piksi_tools.console.settings_view import SettingsView
from piksi_tools.console.solution_view import SolutionView
from piksi_tools.console.skyplot_view import SkyplotView
from piksi_tools.console.spectrum_analyzer_view import SpectrumAnalyzerView
from piksi_tools.console.system_monitor_view import SystemMonitorView
from piksi_tools.console.tracking_view import TrackingView
from piksi_tools.console.update_view import UpdateView
from piksi_tools.console.utils import (EMPTY_STR, call_repeatedly,
                                       mode_dict, ins_mode_dict, ins_type_dict,
                                       ins_error_dict, resource_filename, icon,
                                       swift_path, DR_MODE, DIFFERENTIAL_MODES)


class ArgumentParserError(Exception):
    pass


class ConsoleArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ArgumentParserError(message)


def get_args():
    """
    Get and parse arguments.
    """
    parser = s.base_cl_options(
        override_arg_parse=ConsoleArgumentParser, add_help=False,
        add_log_args=True, add_reset_arg=True)
    parser.description = 'Swift Console'
    parser.add_argument(
        "-i",
        "--initloglevel",
        default=[None],
        nargs=1,
        help="Set log level filter.")
    parser.add_argument(
        "-u",
        "--update",
        help="don't prompt about firmware/console updates.",
        action="store_false")
    parser.add_argument(
        '--error', action='store_true', help="Do not swallow exceptions.")
    parser.add_argument(
        '--log-console',
        action='store_true',
        help="Log console stdout/err to file.")
    parser.add_argument(
        '-h',
        '--help',
        action='store_true',
        help="Show usage help in a GUI popup.")
    parser.add_argument(
        '-V',
        '--version',
        action='version',
        version='Swift Console {}'.format(CONSOLE_VERSION)
    )
    return parser


CONSOLE_TITLE = 'Swift Console ' + CONSOLE_VERSION


class ConsoleHandler(Handler):
    """
    Handler that updates the window title with the device serial number

    This Handler is used by Traits UI to manage making changes to the GUI in
    response to changes in the underlying class/data.
    """

    def object_device_serial_changed(self, info):
        """
        Update the window title with the device serial number.

        This is a magic method called by the handler in response to any changes in
        the `device_serial` variable in the underlying class.
        """
        if info.initialized:
            info.ui.title = (info.object.dev_id +
                             "(" + info.object.device_serial + ") " + CONSOLE_TITLE)


class SwiftConsole(HasTraits):
    """Traits-defined Swift Console.

    link : object
      Serial driver
    update : bool
      Update the firmware
    log_level_filter : str
      Syslog string, one of "ERROR", "WARNING", "INFO", "DEBUG".
    """

    link = Instance(sbpc.Handler)
    console_output = Instance(OutputList())
    python_console_env = Dict
    device_serial = Str('')
    dev_id = Str('')
    tracking_view = Instance(TrackingView)
    solution_view = Instance(SolutionView)
    baseline_view = Instance(BaselineView)
    skyplot_view = Instance(SkyplotView)
    observation_view = Instance(ObservationView)
    networking_view = Instance(SbpRelayView)
    observation_view_base = Instance(ObservationView)
    system_monitor_view = Instance(SystemMonitorView)
    settings_view = Instance(SettingsView)
    update_view = Instance(UpdateView)
    imu_view = Instance(IMUView)
    mag_view = Instance(MagView)
    spectrum_analyzer_view = Instance(SpectrumAnalyzerView)
    log_level_filter = Enum(list(SYSLOG_LEVELS.values()))
    """"
  mode : baseline and solution view - SPP, Fixed or Float
  num_sat : baseline and solution view - number of satellites
  port : which port is Swift Device is connected to
  directory_name : location of logged files
  json_logging : enable JSON logging
  csv_logging : enable CSV logging

  """

    mode = Str('')
    ins_status_string = Str('')
    num_sats_str = Str('')
    cnx_desc = Str('')
    age_of_corrections = Str('')
    uuid = Str('')
    directory_name = Directory
    json_logging = Bool(True)
    csv_logging = Bool(False)
    cnx_icon = Str('')
    heartbeat_count = Int()
    last_timer_heartbeat = Int()
    solid_connection = Bool(False)

    csv_logging_button = SVGButton(
        toggle=True,
        label='CSV log',
        tooltip='start CSV logging',
        toggle_tooltip='stop CSV logging',
        filename=resource_filename('console/images/iconic/pause.svg'),
        toggle_filename=resource_filename('console/images/iconic/play.svg'),
        orientation='vertical',
        width=2,
        height=2, )
    json_logging_button = SVGButton(
        toggle=True,
        label='JSON log',
        tooltip='start JSON logging',
        toggle_tooltip='stop JSON logging',
        filename=resource_filename('console/images/iconic/pause.svg'),
        toggle_filename=resource_filename('console/images/iconic/play.svg'),
        orientation='vertical',
        width=2,
        height=2, )
    paused_button = SVGButton(
        label='',
        tooltip='Pause console update',
        toggle_tooltip='Resume console update',
        toggle=True,
        filename=resource_filename('console/images/iconic/pause.svg'),
        toggle_filename=resource_filename('console/images/iconic/play.svg'),
        width=8,
        height=8)
    clear_button = SVGButton(
        label='',
        tooltip='Clear console buffer',
        filename=resource_filename('console/images/iconic/x.svg'),
        width=8,
        height=8)

    view = View(
        VSplit(
            Tabbed(
                Tabbed(
                    Item('tracking_view', style='custom', label='Signals', show_label=False),
                    Item('skyplot_view', style='custom', label='Sky Plot', show_label=False),
                    label="Tracking"),
                Item('solution_view', style='custom', label='Solution'),
                Item('baseline_view', style='custom', label='Baseline'),
                VSplit(
                    Item('observation_view', style='custom', show_label=False),
                    Item(
                        'observation_view_base',
                        style='custom',
                        show_label=False),
                    label='Observations', ),
                Item('settings_view', style='custom', label='Settings'),
                Item('update_view', style='custom', label='Update'),
                Tabbed(
                    Item(
                        'system_monitor_view',
                        style='custom',
                        label='System Monitor'),
                    Item('imu_view', style='custom', label='IMU'),
                    Item('mag_view', style='custom', label='Magnetometer'),
                    Item(
                        'networking_view',
                        label='Networking',
                        style='custom',
                        show_label=False),
                    Item(
                        'spectrum_analyzer_view',
                        label='Spectrum Analyzer',
                        style='custom'),
                    label='Advanced',
                    show_labels=False),
                show_labels=False),
            VGroup(
                VGroup(
                    HGroup(
                        Spring(width=4, springy=False),
                        Item(
                            'paused_button',
                            show_label=False,
                            padding=0,
                            width=8,
                            height=8),
                        Item(
                            'clear_button',
                            show_label=False,
                            width=8,
                            height=8),
                        Item('', label='Console Log', emphasized=True),
                        Item(
                            'csv_logging_button',
                            emphasized=True,
                            show_label=False,
                            width=12,
                            height=-30,
                            padding=0),
                        Item(
                            'json_logging_button',
                            emphasized=True,
                            show_label=False,
                            width=12,
                            height=-30,
                            padding=0),
                        Item(
                            'directory_name',
                            show_label=False,
                            springy=True,
                            tooltip='Choose location for file logs. Default is home/SwiftNav.',
                            height=-25,
                            enabled_when='not(json_logging or csv_logging)',
                            editor_args={'auto_set': True}),
                        UItem(
                            'log_level_filter',
                            style='simple',
                            padding=0,
                            height=8,
                            show_label=True,
                            tooltip='Show log levels up to and including the selected level of severity.\nThe CONSOLE log level is always visible.'
                        ), ),
                    Item(
                        'console_output',
                        style='custom',
                        editor=InstanceEditor(),
                        height=125,
                        show_label=False,
                        full_size=True), ),
                HGroup(
                    Spring(width=4, springy=False),
                    Item(
                        '',
                        label='Interface:',
                        emphasized=True,
                        tooltip='Interface for communicating with Swift device'
                    ),
                    Item('cnx_desc', show_label=False, style='readonly'),
                    Item(
                        '',
                        label='FIX TYPE:',
                        emphasized=True,
                        tooltip='Device Mode: SPS, Float RTK, Fixed RTK'),
                    Item('mode', show_label=False, style='readonly'),
                    Item(
                        '',
                        label='#Sats:',
                        emphasized=True,
                        tooltip='Number of satellites used in solution'),
                    Item(
                        'num_sats_str',
                        padding=2,
                        show_label=False,
                        style='readonly'),
                    Item(
                        '',
                        label='Corr Age:',
                        emphasized=True,
                        tooltip='Age of corrections (-- means invalid / not present)'
                    ),
                    Item(
                        'age_of_corrections',
                        padding=2,
                        show_label=False,
                        style='readonly'),
                    Item(
                        '',
                        label='INS Status:',
                        emphasized=True,
                        tooltip='INS Status String'
                    ), Item(
                        'ins_status_string',
                        padding=2,
                        show_label=False,
                        style='readonly', width=6),
                    Spring(springy=True),
                    Item(
                        'cnx_icon',
                        show_label=False,
                        padding=0,
                        width=8,
                        height=8,
                        visible_when='solid_connection',
                        springy=False,
                        editor=ImageEditor(
                            allow_clipping=False,
                            image=ImageResource(resource_filename('console/images/iconic/arrows_blue.png'))
                        )),
                    Item(
                        'cnx_icon',
                        show_label=False,
                        padding=0,
                        width=8,
                        height=8,
                        visible_when='not solid_connection',
                        springy=False,
                        editor=ImageEditor(
                            allow_clipping=False,
                            image=ImageResource(
                                resource_filename('console/images/iconic/arrows_grey.png')
                            ))),
                    Spring(width=4, height=-2, springy=False), ),
                Spring(height=1, springy=False), ), ),
        icon=icon,
        resizable=True,
        width=800,
        height=600,
        handler=ConsoleHandler(),
        title=CONSOLE_TITLE)

    def print_message_callback(self, sbp_msg, **metadata):
        try:
            encoded = sbp_msg.payload.encode('ascii', 'ignore')
            for eachline in reversed(encoded.split('\n')):
                self.console_output.write_level(
                    eachline, str_to_log_level(eachline.split(':')[0]))
        except UnicodeDecodeError as e:
            print("Error encoding msg_print: {}".format(e))

    def log_message_callback(self, sbp_msg, **metadata):
        encoded = sbp_msg.text.decode('utf8')
        for eachline in reversed(encoded.split('\n')):
            self.console_output.write_level(eachline, sbp_msg.level)

    def ext_event_callback(self, sbp_msg, **metadata):
        e = MsgExtEvent(sbp_msg)
        print(
            'External event: %s edge on pin %d at wn=%d, tow=%d, time qual=%s'
            % ("Rising" if (e.flags & (1 << 0)) else "Falling", e.pin, e.wn,
               e.tow, "good" if (e.flags & (1 << 1)) else "unknown"))

    def cmd_resp_callback(self, sbp_msg, **metadata):
        r = MsgCommandResp(sbp_msg)
        print(
            "Received a command response message with code {0}".format(r.code))

    def _paused_button_fired(self):
        self.console_output.paused = not self.console_output.paused

    def _log_level_filter_changed(self):
        """
        Takes log level enum and translates into the mapped integer.
        Integer stores the current filter value inside OutputList.
        """
        self.console_output.log_level_filter = str_to_log_level(
            self.log_level_filter)

    def _clear_button_fired(self):
        self.console_output.clear()

    def _directory_name_changed(self):
        if self.baseline_view and self.solution_view:
            self.baseline_view.directory_name_b = self.directory_name
            self.solution_view.directory_name_p = self.directory_name
            self.solution_view.directory_name_v = self.directory_name
        if self.observation_view and self.observation_view_base:
            self.observation_view.dirname = self.directory_name
            self.observation_view_base.dirname = self.directory_name

    def check_heartbeat(self):
        # if our heartbeat hasn't changed since the last timer interval the connection must have dropped
        if self.heartbeat_count == self.last_timer_heartbeat:
            self.solid_connection = False
            self.ins_status_string = "None"
            self.mode = "None"
            self.num_sats_str = EMPTY_STR
        else:
            self.solid_connection = True
        self.last_timer_heartbeat = self.heartbeat_count

    def update_on_heartbeat(self, sbp_msg, **metadata):
        self.heartbeat_count += 1

        # --- determining which mode, llh or baseline, to show in the status bar ---
        llh_display_mode = "None"
        llh_num_sats = 0
        llh_is_differential = False

        baseline_display_mode = "None"
        baseline_num_sats = 0
        baseline_is_differential = False

        # determine the latest llh solution mode
        if self.solution_view:
            llh_solution_mode = self.solution_view.last_pos_mode
            llh_display_mode = mode_dict.get(llh_solution_mode, EMPTY_STR)
            if llh_solution_mode > 0 and self.solution_view.last_soln:
                llh_num_sats = self.solution_view.last_soln.n_sats
            llh_is_differential = (llh_solution_mode in DIFFERENTIAL_MODES)
            if getattr(self.solution_view, 'ins_used', False) and llh_solution_mode != DR_MODE:
                llh_display_mode += "+INS"

        # determine the latest baseline solution mode
        if self.baseline_view and self.settings_view and self.settings_view.dgnss_enabled():
            baseline_solution_mode = self.baseline_view.last_mode
            baseline_display_mode = mode_dict.get(baseline_solution_mode, EMPTY_STR)
            if baseline_solution_mode > 0 and self.baseline_view.last_soln:
                baseline_num_sats = self.baseline_view.last_soln.n_sats
            baseline_is_differential = (baseline_solution_mode in DIFFERENTIAL_MODES)

        # determine the latest INS mode
        if self.solution_view and (monotonic() -
                                   self.solution_view.last_ins_status_receipt_time) < 1:
            ins_flags = self.solution_view.ins_status_flags
            ins_mode = ins_flags & 0x7
            ins_type = (ins_flags >> 29) & 0x7
            odo_status = (ins_flags >> 8) & 0x3
            ins_error = (ins_flags >> 4) & 0xF
            if ins_error != 0:
                ins_status_string = ins_error_dict.get(ins_error, "Unk Error")
            else:
                ins_status_string = ins_type_dict.get(ins_type, "unk") + "-"
                ins_status_string += ins_mode_dict.get(ins_mode, "unk")
                if odo_status == 1:
                    ins_status_string += "+Odo"
            self.ins_status_string = ins_status_string

        # select the solution mode displayed in the status bar:
        # * baseline if it's a differential solution but llh isn't
        # * otherwise llh (also if there is no solution, in which both are "None")
        if baseline_is_differential and not(llh_is_differential):
            self.mode = baseline_display_mode
            self.num_sats_str = "{}".format(baseline_num_sats)
        else:
            self.mode = llh_display_mode
            self.num_sats_str = "{}".format(llh_num_sats)

        # --- end of status bar mode determination section ---

        if self.settings_view:  # for auto populating surveyed fields
            self.settings_view.lat = self.solution_view.latitude
            self.settings_view.lon = self.solution_view.longitude
            self.settings_view.alt = self.solution_view.altitude
        if self.baseline_view:
            if self.baseline_view.age_corrections is not None:
                self.age_of_corrections = "{0} s".format(
                    self.baseline_view.age_corrections)
            else:
                self.age_of_corrections = EMPTY_STR

    def _csv_logging_button_action(self):
        if self.csv_logging and self.baseline_view.logging_b and self.solution_view.logging_p and self.solution_view.logging_v:
            print("Stopped CSV logging")
            self.csv_logging = False
            self.baseline_view.logging_b = False
            self.solution_view.logging_p = False
            self.solution_view.logging_v = False

        else:
            print("Started CSV logging at %s" % self.directory_name)
            self.csv_logging = True
            self.baseline_view.logging_b = True
            self.solution_view.logging_p = True
            self.solution_view.logging_v = True

    def _start_json_logging(self, override_filename=None):
        if override_filename:
            filename = override_filename
        else:
            filename = time.strftime("swift-gnss-%Y%m%d-%H%M%S.sbp.json")
            filename = os.path.normpath(
                os.path.join(self.directory_name, filename))
        self.logger = s.get_logger(True, filename, self.expand_json)
        self.forwarder = sbpc.Forwarder(self.link, self.logger)
        self.forwarder.start()
        if self.settings_view:
            self.settings_view._settings_read_all()

    def _stop_json_logging(self):
        fwd = self.forwarder
        fwd.stop()
        self.logger.flush()
        self.logger.close()

    def _json_logging_button_action(self):
        if self.first_json_press and self.json_logging:
            print(
                "JSON Logging initiated via CMD line.  Please press button again to stop logging"
            )
        elif self.json_logging:
            self._stop_json_logging()
            self.json_logging = False
            print("Stopped JSON logging")
        else:
            self._start_json_logging()
            self.json_logging = True
        self.first_json_press = False

    def _json_logging_button_fired(self):
        if not os.path.exists(self.directory_name) and not self.json_logging:
            confirm_prompt = CallbackPrompt(
                title="Logging directory creation",
                actions=[ok_button],
                callback=self._json_logging_button_action)
            confirm_prompt.text = "\nThe selected logging directory does not exist and will be created."
            confirm_prompt.run(block=False)
        else:
            self._json_logging_button_action()

    def _csv_logging_button_fired(self):
        if not os.path.exists(self.directory_name) and not self.csv_logging:
            confirm_prompt = CallbackPrompt(
                title="Logging directory creation",
                actions=[ok_button],
                callback=self._csv_logging_button_action)
            confirm_prompt.text = "\nThe selected logging directory does not exist and will be created."
            confirm_prompt.run(block=False)
        else:
            self._csv_logging_button_action()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.console_output.close()

    def __init__(self,
                 link,
                 update,
                 log_level_filter,
                 error=False,
                 cnx_desc=None,
                 json_logging=False,
                 log_dirname=None,
                 override_filename=None,
                 log_console=False,
                 connection_info=None,
                 expand_json=False
                 ):
        self.error = error
        self.cnx_desc = cnx_desc
        self.connection_info = connection_info
        self.dev_id = cnx_desc
        self.num_sats_str = EMPTY_STR
        self.mode = ''
        self.ins_status_string = "None"
        self.forwarder = None
        self.age_of_corrections = '--'
        self.expand_json = expand_json
        # if we have passed a logfile, we set our directory to it
        override_filename = override_filename
        self.last_status_update_time = 0

        if log_dirname:
            self.directory_name = log_dirname
            if override_filename:
                override_filename = os.path.join(log_dirname,
                                                 override_filename)
        else:
            self.directory_name = swift_path

        # Start swallowing sys.stdout and sys.stderr
        self.console_output = OutputList(
            tfile=log_console, outdir=self.directory_name)
        sys.stdout = self.console_output
        self.console_output.write("Console: " + CONSOLE_VERSION +
                                  " starting...")
        if not error:
            sys.stderr = self.console_output

        self.log_level_filter = log_level_filter
        self.console_output.log_level_filter = str_to_log_level(
            log_level_filter)
        try:
            self.link = link
            self.link.add_callback(self.print_message_callback,
                                   SBP_MSG_PRINT_DEP)
            self.link.add_callback(self.log_message_callback, SBP_MSG_LOG)
            self.link.add_callback(self.ext_event_callback, SBP_MSG_EXT_EVENT)
            self.link.add_callback(self.cmd_resp_callback,
                                   SBP_MSG_COMMAND_RESP)
            self.link.add_callback(self.update_on_heartbeat, SBP_MSG_HEARTBEAT)
            self.dep_handler = DeprecatedMessageHandler(link)
            settings_read_finished_functions = []
            self.tracking_view = TrackingView(self.link)
            self.solution_view = SolutionView(
                self.link, dirname=self.directory_name)
            self.baseline_view = BaselineView(
                self.link, dirname=self.directory_name)
            self.skyplot_view = SkyplotView(self.link)
            self.observation_view = ObservationView(
                self.link,
                name='Local',
                relay=False,
                dirname=self.directory_name)
            self.observation_view_base = ObservationView(
                self.link,
                name='Remote',
                relay=True,
                dirname=self.directory_name)
            self.system_monitor_view = SystemMonitorView(self.link)
            self.update_view = UpdateView(
                self.link,
                download_dir=swift_path,
                prompt=update,
                connection_info=self.connection_info)
            self.imu_view = IMUView(self.link)
            self.mag_view = MagView(self.link)
            self.spectrum_analyzer_view = SpectrumAnalyzerView(self.link)
            settings_read_finished_functions.append(
                self.update_view.compare_versions)
            self.networking_view = SbpRelayView(self.link)
            self.json_logging = json_logging
            self.csv_logging = False
            self.first_json_press = True
            if json_logging:
                self._start_json_logging(override_filename)
                self.json_logging = True
            # we set timer interval to 1200 milliseconds because we expect a heartbeat each second
            self.timer_cancel = call_repeatedly(1.2, self.check_heartbeat)

            # Once we have received the settings, update device_serial with
            # the Swift serial number which will be displayed in the window
            # title. This callback will also update the header route as used
            # by the networking view.

            def update_serial():
                mfg_id = None
                try:
                    self.uuid = self.settings_view.settings['system_info'][
                        'uuid'].value
                    mfg_id = self.settings_view.settings['system_info'][
                        'serial_number'].value
                except KeyError:
                    pass
                if mfg_id:
                    self.device_serial = 'PK' + str(mfg_id)

            skip_settings_read = False
            if 'mode' in self.connection_info:
                if self.connection_info['mode'] == 'file':
                    skip_settings_read = True

            settings_read_finished_functions.append(update_serial)
            self.settings_view = SettingsView(
                self.link,
                settings_read_finished_functions,
                skip_read=skip_settings_read)
            self.update_view.settings = self.settings_view.settings
            self.python_console_env = {
                'send_message': self.link,
                'link': self.link,
            }
            self.python_console_env.update(
                self.tracking_view.python_console_cmds)
            self.python_console_env.update(
                self.solution_view.python_console_cmds)
            self.python_console_env.update(
                self.baseline_view.python_console_cmds)
            self.python_console_env.update(
                self.skyplot_view.python_console_cmds)
            self.python_console_env.update(
                self.observation_view.python_console_cmds)
            self.python_console_env.update(
                self.networking_view.python_console_cmds)
            self.python_console_env.update(
                self.system_monitor_view.python_console_cmds)
            self.python_console_env.update(
                self.update_view.python_console_cmds)
            self.python_console_env.update(self.imu_view.python_console_cmds)
            self.python_console_env.update(self.mag_view.python_console_cmds)
            self.python_console_env.update(
                self.settings_view.python_console_cmds)
            self.python_console_env.update(
                self.spectrum_analyzer_view.python_console_cmds)

        except:  # noqa
            import traceback
            traceback.print_exc()
            if self.error:
                os._exit(1)


class ShowUsage(HasTraits):
    usage_str = Str()
    traits_view = View(
        Item(
            "usage_str",
            style='readonly',
            show_label=False,
            editor=TextEditor(),
            resizable=True),
        width=680,
        resizable=True,
        icon=icon,
        title='Swift Console Usage')

    def __init__(self, usage, error_str):
        if error_str != "":
            self.usage_str = "<pre>" + error_str + '<br><br><br>' + usage + "</pre>"
        else:
            self.usage_str = "<pre>" + usage + "</pre>"


class ShowConnectionError(HasTraits):
    error_str = Str()
    traits_view = View(
        VGroup(
            Spring(height=4, springy=True),
            HGroup(
                Spring(springy=True),
                Item('error_str',
                     style='readonly',
                     editor=TextEditor(),
                     show_label=False),
                Spring(springy=True),
            ),
            Spring(springy=True),
        ),
        buttons=['OK', 'Cancel'],
        default_button='OK',
        close_result=False,
        resizable=True,
        icon=icon,
        title="Swift Console Encountered An Error",
    )

    def __init__(self, error_message=None, e=None):
        self.error_str = (error_message
                          if error_message is not None
                          else 'Unhandled Error')
        if e is not None:
            self.error_str += '\n\n{}'.format(e)


class ConnectionData(object):
    '''Data class for connection information.'''
    def __init__(self, driver=None, description="", mode=None,
                 connection_info={}):
        self.driver = driver
        self.description = description
        self.connection_info = connection_info
        if mode is not None:
            self.set_connection_mode(mode)

    def set_connection_mode(self, mode):
        self.connection_info['mode'] = mode


def connection_from_args(args):
    cnx_data = None
    connect_error = None
    description = ''
    mode = ''
    port = getattr(args, 'port', None)
    baud = getattr(args, 'baud', None)

    if port is not None:
        if args.tcp:
            # Use the TPC driver and interpret port arg as host:port
            description = port
            mode = 'TCP/IP'
        elif args.file:
            # Use file and interpret port arg as the file
            print("Using file '%s'" % port)
            description = os.path.split(port)[-1]
            mode = 'file'
        else:
            if args.rtscts:
                print("using flow control")
            # Use the port passed and assume serial connection
            print("Using serial device '%s'" % port)
            description = os.path.split(port)[-1]
            description += (" @" + str(baud)) if baud else ""
            mode = 'serial'

        try:
            driver = s.get_base_args_driver(args)
        except Exception as e:  # noqa
            connect_error = e
        else:
            cnx_data = ConnectionData(
                driver=driver,
                description=description,
                mode=mode
            )
    return (cnx_data, connect_error)


def port_chooser_retry_logic(args):
    cnx_data = None
    retry_connection = True
    while retry_connection:
        args = get_args_from_port_chooser(args)
        # if the user pressed cancel or didn't select anything we get None
        if args is None:
            print("No Interface selected!")
            return None

        cnx_data, cnx_error = connection_from_args(args)
        if cnx_data is not None:
            break
        if cnx_error is not None:
            error = ShowConnectionError('Connection Failed', cnx_error)
            retry_connection = error.configure_traits()
    return cnx_data


def do_connection(args):
    '''Attempt to connect based on CLI args'''
    # try connection from args first, no initial port arg determines retry
    cnx_data, cnx_err = connection_from_args(args)

    # do retry logic if applicable
    if cnx_data is None:
        if cnx_err is None:  # didn't try connection, likely no args
            cnx_data = port_chooser_retry_logic(args)
        else:
            print("Failed to Connect: {}".format(cnx_err))
    return cnx_data


def main():
    warnings.simplefilter(action="ignore", category=FutureWarning)
    logging.basicConfig()
    args = None
    parser = get_args()
    try:
        args = parser.parse_args()
        show_usage = args.help
        error_str = ""
    except (ArgumentParserError, argparse.ArgumentError,
            argparse.ArgumentTypeError) as e:
        print(e)
        show_usage = True
        error_str = "ERROR: " + str(e)

    # Make sure that SIGINT (i.e. Ctrl-C from command line) actually stops the
    # application event loop (otherwise Qt swallows KeyboardInterrupt exceptions)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    if show_usage:
        usage_str = parser.format_help()
        print(usage_str)
        usage = ShowUsage(usage_str, error_str)
        usage.configure_traits()
        sys.exit(1)

    # fail out if connection failed to initialize
    cnx_data = do_connection(args)
    if cnx_data is None:
        print('Unable to Initialize Connection. Exiting...')
        sys.exit(1)

    if args.json:
        source = JSONLogIterator(cnx_data.driver, conventional=True)
    else:
        source = sbpc.Framer(cnx_data.driver.read, cnx_data.driver.write, args.verbose)

    with sbpc.Handler(source) as link:
        if args.reset:
            link(MsgReset(flags=0))
        log_filter = DEFAULT_LOG_LEVEL_FILTER
        if args.initloglevel[0]:
            log_filter = args.initloglevel[0]
        with SwiftConsole(
                link,
                args.update,
                log_filter,
                cnx_desc=cnx_data.description,
                error=args.error,
                json_logging=args.log,
                log_dirname=args.log_dirname,
                override_filename=args.logfilename,
                log_console=args.log_console,
                connection_info=cnx_data.connection_info,
                expand_json=args.expand_json) as console:

            console.configure_traits()

    # TODO: solve this properly
    # Force exit, even if threads haven't joined
    try:
        os._exit(0)
    except:  # noqa
        pass


if __name__ == "__main__":
    main()
