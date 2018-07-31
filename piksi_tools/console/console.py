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

from __future__ import print_function

import argparse
# Logging
import logging
import os
import signal
import sys
import time
import warnings

import sbp.client as sbpc
from enable.savage.trait_defs.ui.svg_button import SVGButton
from pyface.image_resource import ImageResource
from sbp.client.drivers.network_drivers import TCPDriver
from sbp.ext_events import SBP_MSG_EXT_EVENT, MsgExtEvent
from sbp.logging import SBP_MSG_LOG, SBP_MSG_PRINT_DEP
from sbp.navigation import SBP_MSG_POS_LLH
from sbp.piksi import SBP_MSG_COMMAND_RESP, MsgCommandResp, MsgReset
from sbp.system import SBP_MSG_HEARTBEAT
from traits.api import (Bool, Dict, Directory, Enum, HasTraits, Instance, Int,
                        List, Str)
# Toolkit
from traits.etsconfig.api import ETSConfig
from traitsui.api import (EnumEditor, Handler, HGroup, HTMLEditor, ImageEditor,
                          InstanceEditor, Item, Label, Spring,
                          Tabbed, UItem, VGroup, View, VSplit)

import piksi_tools.serial_link as s
from piksi_tools import __version__ as CONSOLE_VERSION
from piksi_tools.console.baseline_view import BaselineView
from piksi_tools.console.callback_prompt import CallbackPrompt, ok_button
from piksi_tools.console.deprecated import DeprecatedMessageHandler
from piksi_tools.console.imu_view import IMUView
from piksi_tools.console.mag_view import MagView
from piksi_tools.console.observation_view import ObservationView
from piksi_tools.console.output_list import (
    DEFAULT_LOG_LEVEL_FILTER, SYSLOG_LEVELS, OutputList, str_to_log_level)
from piksi_tools.console.sbp_relay_view import SbpRelayView
from piksi_tools.console.settings_view import SettingsView
from piksi_tools.console.solution_view import SolutionView
from piksi_tools.console.spectrum_analyzer_view import SpectrumAnalyzerView
from piksi_tools.console.system_monitor_view import SystemMonitorView
from piksi_tools.console.tracking_view import TrackingView
from piksi_tools.console.update_view import UpdateView
from piksi_tools.console.utils import (EMPTY_STR, call_repeatedly,
                                       get_mode, mode_dict, resource_filename,
                                       icon, swift_path, DR_MODE, DIFFERENTIAL_MODES)
from piksi_tools.console.skylark_view import SkylarkView

warnings.filterwarnings("ignore", ".*No message found for msg_type.")


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
        override_arg_parse=ConsoleArgumentParser, add_help=False)
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
        '--toolkit',
        nargs=1,
        default=[None],
        help="specify the TraitsUI toolkit to use, either 'wx' or 'qt4'.")
    parser.add_argument(
        '--error', action='store_true', help="Do not swallow exceptions.")
    parser.add_argument(
        '--log-console',
        action='store_true',
        help="Log console stdout/err to file.")
    parser.add_argument(
        '--networking',
        default=None,
        const='{}',
        nargs='?',
        help="key value pairs to pass to sbp_relay_view initializer for network"
    )
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


CONSOLE_TITLE = 'Swift Console v' + CONSOLE_VERSION
BAUD_LIST = [57600, 115200, 230400, 921600, 1000000]


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
    skip_settings : bool
      Don't read the device settings. Set to False when the console is reading
      from a network connection only.

    """

    link = Instance(sbpc.Handler)
    console_output = Instance(OutputList())
    python_console_env = Dict
    device_serial = Str('')
    dev_id = Str('')
    tracking_view = Instance(TrackingView)
    solution_view = Instance(SolutionView)
    baseline_view = Instance(BaselineView)
    observation_view = Instance(ObservationView)
    networking_view = Instance(SbpRelayView)
    observation_view_base = Instance(ObservationView)
    system_monitor_view = Instance(SystemMonitorView)
    settings_view = Instance(SettingsView)
    update_view = Instance(UpdateView)
    imu_view = Instance(IMUView)
    mag_view = Instance(MagView)
    spectrum_analyzer_view = Instance(SpectrumAnalyzerView)
    skylark_view = Instance(SkylarkView)
    log_level_filter = Enum(list(SYSLOG_LEVELS.itervalues()))
    """"
  mode : baseline and solution view - SPP, Fixed or Float
  num_sat : baseline and solution view - number of satellites
  port : which port is Swift Device is connected to
  directory_name : location of logged files
  json_logging : enable JSON logging
  csv_logging : enable CSV logging

  """

    mode = Str('')
    num_sats = Int(0)
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
                Item('tracking_view', style='custom', label='Tracking'),
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
                Item('skylark_view', style='custom', label='Skylark'),
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
                        'num_sats',
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
                        label='Device UUID:',
                        emphasized=True,
                        tooltip='Universally Unique Device Identifier (UUID)'
                    ), Item(
                        'uuid',
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
        encoded = sbp_msg.text
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
        else:
            self.solid_connection = True
        self.last_timer_heartbeat = self.heartbeat_count

    def update_on_heartbeat(self, sbp_msg, **metadata):
        self.heartbeat_count += 1
        # First initialize the state to nothing, if we can't update, it will be none
        display_mode = "None"
        num_sats = 0
        if self.baseline_view and self.solution_view:
            last_baseline_soln = self.baseline_view.last_soln
            last_llh_soln = self.solution_view.last_soln
            # if we have a recent llh solution, use that mode
            if last_llh_soln and (self.last_status_update_time != self.solution_view.last_stime_update):
                llh_mode_enum = get_mode(last_llh_soln)
                display_mode = mode_dict.get(llh_mode_enum, EMPTY_STR)
                num_sats = last_llh_soln.n_sats
                if getattr(self.solution_view, 'ins_used', False) and llh_mode_enum != DR_MODE:
                        display_mode += "+INS"
                self.last_status_update_time = self.solution_view.last_stime_update
            # If we have a recent baseline update that has higher mode, we use the baseline soln info instead
            if last_baseline_soln and self.last_status_update_time != self.baseline_view.last_btime_update:
                baseline_mode_enum = get_mode(last_baseline_soln)
                # if the baseline is "higher" mode than llh or llh is missing, use baseline for mode and num_sats
                if baseline_mode_enum in DIFFERENTIAL_MODES and (last_llh_soln and
                   get_mode(last_llh_soln) not in DIFFERENTIAL_MODES or not last_llh_soln):
                    display_mode = mode_dict.get(baseline_mode_enum, EMPTY_STR)
                    num_sats = last_baseline_soln.n_sats
                    self.last_status_update_time = self.baseline_view.last_btime_update
        self.mode = display_mode
        self.num_sats = num_sats

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
            self.settings_view._settings_read_by_index()

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
                 skip_settings=False,
                 error=False,
                 cnx_desc=None,
                 json_logging=False,
                 log_dirname=None,
                 override_filename=None,
                 log_console=False,
                 networking=None,
                 connection_info=None,
                 expand_json=False
                 ):
        self.error = error
        self.cnx_desc = cnx_desc
        self.connection_info = connection_info
        self.dev_id = cnx_desc
        self.num_sats = 0
        self.mode = ''
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
            if networking:
                from ruamel.yaml import YAML
                yaml = YAML(typ='safe')
                try:
                    networking_dict = yaml.load(networking)
                    networking_dict.update({'show_networking': True})
                except yaml.YAMLError:
                    print(
                        "Unable to interpret networking cmdline argument.  It will be ignored."
                    )
                    import traceback
                    print(traceback.format_exc())
                    networking_dict = {'show_networking': True}
            else:
                networking_dict = {}
            networking_dict.update({
                'whitelist': [SBP_MSG_POS_LLH, SBP_MSG_HEARTBEAT]
            })
            self.networking_view = SbpRelayView(self.link, **networking_dict)
            self.skylark_view = SkylarkView()
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
                self.skylark_view.set_uuid(self.uuid)
                self.networking_view.set_route(uuid=self.uuid, serial_id=mfg_id)
                if self.networking_view.connect_when_uuid_received:
                    self.networking_view._connect_rover_fired()

            settings_read_finished_functions.append(update_serial)
            self.settings_view = SettingsView(
                self.link,
                settings_read_finished_functions,
                skip=skip_settings)
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
                sys.exit(1)


class ShowUsage(HasTraits):
    usage_str = Str()
    traits_view = View(
        Item(
            "usage_str",
            style='readonly',
            show_label=False,
            editor=HTMLEditor(),
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


# If using a device connected to an actual port, then invoke the
# regular console dialog for port selection
flow_control_options_list = ['None', 'Hardware RTS/CTS']
cnx_type_list = ['Serial/USB', 'TCP/IP']


class PortChooser(HasTraits):
    port = Str(None)
    ports = List()
    mode = Enum(cnx_type_list)
    flow_control = Enum(flow_control_options_list)
    ip_port = Int(55555)
    ip_address = Str('192.168.0.222')
    choose_baud = Bool(True)
    baudrate = Int()
    refresh_ports_button = SVGButton(label='',
                                     tooltip='Refresh Port List',
                                     filename=resource_filename('console/images/fontawesome/refresh_blue.svg'),
                                     allow_clipping=False,
                                     width_padding=4, height_padding=4
                                     )

    traits_view = View(
        VGroup(
            Spring(height=8),
            HGroup(
                Spring(width=-2, springy=False),
                Item(
                    'mode',
                    style='custom',
                    editor=EnumEditor(
                        values=cnx_type_list, cols=2, format_str='%s'),
                    show_label=False)),
            HGroup(
                VGroup(
                    Label('Serial Device:'),
                    HGroup(
                        Item('port', editor=EnumEditor(name='ports'), show_label=False, springy=True),
                        Item('refresh_ports_button', show_label=False, padding=0, height=-20, width=-20),
                    ),
                ),
                VGroup(
                    Label('Baudrate:'),
                    Item(
                        'baudrate',
                        editor=EnumEditor(values=BAUD_LIST),
                        show_label=False,
                        visible_when='choose_baud'),
                    Item(
                        'baudrate',
                        show_label=False,
                        visible_when='not choose_baud',
                        style='readonly'), ),
                VGroup(
                    Label('Flow Control:'),
                    Item(
                        'flow_control',
                        editor=EnumEditor(
                            values=flow_control_options_list, format_str='%s'),
                        show_label=False), ),
                visible_when="mode==\'Serial/USB\'"),
            HGroup(
                VGroup(
                    Label('IP Address:'),
                    Item(
                        'ip_address',
                        label="IP Address",
                        style='simple',
                        show_label=False,
                        height=-24), ),
                VGroup(
                    Label('IP Port:'),
                    Item(
                        'ip_port',
                        label="IP Port",
                        style='simple',
                        show_label=False,
                        height=-24), ),
                Spring(),
                visible_when="mode==\'TCP/IP\'"), ),
        buttons=['OK', 'Cancel'],
        default_button='OK',
        close_result=False,
        icon=icon,
        width=460,
        title='Swift Console v{0} - Select Interface'.format(CONSOLE_VERSION)
    )

    def refresh_ports(self):
        """
        This method refreshes the port list
        """
        try:
            self.ports = [p for p, _, _ in s.get_ports()]
        except TypeError:
            pass

    def _refresh_ports_button_fired(self):
        self.refresh_ports()

    def __init__(self, baudrate=None):
        self.refresh_ports()
        # As default value, use the first city in the list:
        try:
            self.port = self.ports[0]
        except IndexError:
            pass
        if baudrate not in BAUD_LIST:
            self.choose_baud = False
        self.baudrate = baudrate


def main():
    warnings.simplefilter(action="ignore", category=FutureWarning)
    logging.basicConfig()
    args = None
    parser = get_args()
    cnx_info = {}
    try:
        args = parser.parse_args()
        port = args.port
        baud = args.baud
        show_usage = args.help
        error_str = ""
    except (ArgumentParserError, argparse.ArgumentError,
            argparse.ArgumentTypeError) as e:
        print(e)
        show_usage = True
        error_str = "ERROR: " + str(e)

    if args and args.toolkit[0] is not None:
        ETSConfig.toolkit = args.toolkit[0]
    else:
        ETSConfig.toolkit = 'qt4'

    # Make sure that SIGINT (i.e. Ctrl-C from command line) actually stops the
    # application event loop (otherwise Qt swallows KeyboardInterrupt exceptions)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    if show_usage:
        usage_str = parser.format_help()
        print(usage_str)
        usage = ShowUsage(usage_str, error_str)
        usage.configure_traits()
        sys.exit(1)

    selected_driver = None
    connection_description = ""
    if port and args.tcp:
        # Use the TPC driver and interpret port arg as host:port
        try:
            host, ip_port = port.split(':')
            selected_driver = TCPDriver(host, int(ip_port))
            connection_description = port
            cnx_info['mode'] = 'TCP/IP'
        except:  # noqa
            raise Exception('Invalid host and/or port')
            sys.exit(1)
    elif port and args.file:
        # Use file and interpret port arg as the file
        print("Using file '%s'" % port)
        cnx_info['mode'] = 'file'
        selected_driver = s.get_driver(args.ftdi, port, baud, args.file)
        connection_description = os.path.split(port)[-1]
    elif not port:
        # Use the gui to get our driver
        port_chooser = PortChooser(baudrate=int(args.baud))
        is_ok = port_chooser.configure_traits()
        ip_address = port_chooser.ip_address
        ip_port = port_chooser.ip_port
        port = port_chooser.port
        baud = port_chooser.baudrate
        mode = port_chooser.mode
        # todo, update for sfw flow control if ever enabled
        rtscts = port_chooser.flow_control == flow_control_options_list[1]
        if rtscts:
            print("using flow control")
        # if the user pressed cancel or didn't select anything
        if not (port or (ip_address and ip_port)) or not is_ok:
            print("No Interface selected!")
            sys.exit(1)
        else:
            # Use either TCP/IP or serial selected from gui
            if mode == cnx_type_list[1]:
                print("Using TCP/IP at address %s and port %d" % (ip_address,
                                                                  ip_port))
                cnx_info['mode'] = cnx_type_list[1]
                selected_driver = TCPDriver(ip_address, int(ip_port))
                connection_description = ip_address + ":" + str(ip_port)
            else:
                cnx_info['mode'] = cnx_type_list[0]
                print("Using serial device '%s'" % port)
                selected_driver = s.get_driver(
                    args.ftdi, port, baud, args.file, rtscts=rtscts)
                connection_description = os.path.split(port)[-1] + " @" + str(baud)
    else:
        # Use the port passed and assume serial connection
        print("Using serial device '%s'" % port)
        selected_driver = s.get_driver(
            args.ftdi, port, baud, args.file, rtscts=args.rtscts)
        connection_description = os.path.split(port)[-1] + " @" + str(baud)
        cnx_info['mode'] = 'serial'

    with selected_driver as driver:
        with sbpc.Handler(
                sbpc.Framer(driver.read, driver.write, args.verbose)) as link:
            if args.reset:
                link(MsgReset(flags=0))
            log_filter = DEFAULT_LOG_LEVEL_FILTER
            if args.initloglevel[0]:
                log_filter = args.initloglevel[0]
            with SwiftConsole(
                    link,
                    args.update,
                    log_filter,
                    cnx_desc=connection_description,
                    error=args.error,
                    json_logging=args.log,
                    log_dirname=args.log_dirname,
                    override_filename=args.logfilename,
                    log_console=args.log_console,
                    networking=args.networking,
                    connection_info=cnx_info,
                    expand_json=args.expand_json) as console:

                console.configure_traits()

    # Force exit, even if threads haven't joined
    try:
        os._exit(0)
    except:  # noqa
        pass


if __name__ == "__main__":
    main()
