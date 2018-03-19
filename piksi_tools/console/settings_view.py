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

from __future__ import absolute_import, print_function

import threading
import time
import copy
import configparser

from pyface.api import GUI
from sbp.piksi import MsgReset
from sbp.settings import (
    SBP_MSG_SETTINGS_READ_BY_INDEX_DONE, SBP_MSG_SETTINGS_READ_BY_INDEX_REQ,
    SBP_MSG_SETTINGS_READ_BY_INDEX_RESP,
    SBP_MSG_SETTINGS_READ_RESP, SBP_MSG_SETTINGS_WRITE_RESP,
    MsgSettingsReadByIndexReq, MsgSettingsSave, MsgSettingsWrite)
from sbp.system import SBP_MSG_STARTUP
from traits.api import (Bool, Color, Constant, Float, Font, HasTraits,
                        Instance, List, Property, Str, Undefined)
from traits.etsconfig.api import ETSConfig
from traitsui.api import (EnumEditor, HGroup, HSplit, Item, TabularEditor,
                          TextEditor, UItem, VGroup, View)
from traitsui.tabular_adapter import TabularAdapter
import piksi_tools.console.callback_prompt as prompt
from piksi_tools.console.gui_utils import MultilineTextEditor
from piksi_tools.console.utils import swift_path
from pyface.api import FileDialog, OK

from .settings_list import SettingsList
from .utils import resource_filename

SETTINGS_REVERT_TIMEOUT = 5

if ETSConfig.toolkit != 'null':
    from enable.savage.trait_defs.ui.svg_button import SVGButton
else:
    SVGButton = dict


class TimedDelayStoppableThread(threading.Thread):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""

    def __init__(self, delay, target, args):
        super(TimedDelayStoppableThread, self).__init__()
        self._stop_event = threading.Event()
        self._delay = delay
        self._target = target
        self._args = args

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()

    def run(self):
        time.sleep(self._delay)
        if not self.stopped():
            # Allow passing a dict as a discrete argument to the target
            if not isinstance(self._args, dict):
                self._target(*self._args)
            else:
                self._target(self._args)


class SettingBase(HasTraits):
    name = Str()
    description = Str()
    notes = Str()
    value = Str(Undefined)
    ordering = Float(0)
    default_value = Str()

    traits_view = View()

    def __repr__(self):
        return "<Setting '%s' = '%s'>" % (self.name, self.value)

    def __str__(self):
        return self.value


class Setting(SettingBase):
    full_name = Str()
    section = Str()
    confirmed_set = Bool(True)
    readonly = Bool(False)
    traits_view = View(
        VGroup(
            Item('full_name', label='Name', style='readonly'),
            Item('value', editor=TextEditor(auto_set=False, enter_set=True),
                 visible_when='confirmed_set and not readonly'),
            Item('value', style='readonly',
                 visible_when='not confirmed_set or readonly', editor=TextEditor(readonly_allow_selection=True)),
            Item('units', style='readonly'),
            UItem('default_value',
                  style='readonly',
                  height=-1,
                  editor=MultilineTextEditor(TextEditor(multi_line=True)),
                  show_label=True,
                  resizable=True),
            UItem(
                'description',
                style='readonly',
                editor=MultilineTextEditor(TextEditor(multi_line=True)),
                show_label=True,
                resizable=True),
            UItem(
                'notes',
                label="Notes",
                height=-1,
                editor=MultilineTextEditor(TextEditor(multi_line=True)),
                style='readonly',
                show_label=True,
                resizable=True),
            show_border=True,
            label='Setting', ), )

    def __init__(self, name, section, value, ordering, settings):
        self.name = name
        self.section = section
        self.full_name = "%s.%s" % (section, name)
        self.value = value
        self.ordering = ordering
        self.settings = settings
        self.expert = settings.settings_yaml.get_field(section, name, 'expert')
        self.description = settings.settings_yaml.get_field(
            section, name, 'Description')
        self.units = settings.settings_yaml.get_field(section, name, 'units')
        self.notes = settings.settings_yaml.get_field(section, name, 'Notes')
        self.default_value = settings.settings_yaml.get_field(
            section, name, 'default value')
        readonly = settings.settings_yaml.get_field(section, name, 'readonly')
        # get_field returns empty string if field missing, so I need this check to assign bool to traits bool
        if readonly:
            self.readonly = True
        self.revert_in_progress = False
        self.timed_revert_thread = None
        self.confirmed_set = True
        # flag on each setting to indicate a write failure if the revert thread has run on the setting
        self.write_failure = False

    def revert_to_prior_value(self, name, old, new):
        '''Revert setting to old value in the case we can't confirm new value'''
        self.revert_in_progress = True
        self.value = old
        self.revert_in_progress = False
        # reset confirmed_set to make sure setting is editable again
        self.confirmed_set = True
        self.write_failure = True
        invalid_setting_prompt = prompt.CallbackPrompt(
            title="Settings Write Error",
            actions=[prompt.close_button], )
        invalid_setting_prompt.text = \
            ("\n   Unable to confirm that {0} was set to {1}.\n"
             "   Ensure the range and formatting of the entry are correct.\n"
             "   Ensure that the new setting value did not interrupt console communication.").format(self.name, new)
        invalid_setting_prompt.run()

    def _value_changed(self, name, old, new):
        '''When a user changes a value, kick off a timed revert thread to revert it in GUI if no confirmation
           that the change was successful is received. '''
        if (old != new and old is not Undefined and new is not Undefined):
            if type(self.value) == unicode:
                self.value = self.value.encode('ascii', 'replace')
            # Revert_in_progress is a guard to prevent this from running when the revert function changes the value
            if not self.revert_in_progress:
                self.confirmed_set = False
                self.timed_revert_thread = TimedDelayStoppableThread(SETTINGS_REVERT_TIMEOUT,
                                                                     target=self.revert_to_prior_value,
                                                                     args=(name, old, new))
                self.settings.set(self.section, self.name, self.value)
                self.timed_revert_thread.start()


class EnumSetting(Setting):
    values = List()
    traits_view = View(
        VGroup(
            Item('full_name', label='Name', style='readonly'),
            Item('value', editor=EnumEditor(name='values'),
                 visible_when='confirmed_set and not readonly'),
            Item('value', style='readonly',
                 visible_when='not confirmed_set or readonly'),
            UItem('default_value',
                  style='readonly',
                  editor=MultilineTextEditor(TextEditor(multi_line=True)),
                  show_label=True,
                  resizable=True),
            UItem(
                'description',
                style='readonly',
                editor=MultilineTextEditor(TextEditor(multi_line=True)),
                show_label=True,
                resizable=True),
            UItem(
                'notes',
                label="Notes",
                height=-1,
                editor=MultilineTextEditor(TextEditor(multi_line=True)),
                style='readonly',
                show_label=True,
                resizable=True),
            show_border=True,
            label='Setting', ), )

    def __init__(self, name, section, value, ordering, values, **kwargs):
        self.values = values
        Setting.__init__(self, name, section, value, ordering, **kwargs)


class SectionHeading(SettingBase):
    value = Constant('')

    def __init__(self, name):
        self.name = name


class SimpleAdapter(TabularAdapter):
    columns = [('Name', 'name'), ('Value', 'value')]
    font = Font('12')
    can_edit = Bool(False)
    SectionHeading_bg_color = Color(0xE0E0E0)
    SectionHeading_font = Font('14 bold')
    SectionHeading_name_text = Property
    Setting_name_text = Property
    name_width = Float(175)

    def _get_SectionHeading_name_text(self):
        return self.item.name.replace('_', ' ')

    def _get_Setting_name_text(self):
        return self.item.name.replace('_', ' ')


class SettingsView(HasTraits):
    """Traits-defined console settings view.

    link : object
      Serial driver object.
    read_finished_functions : list
      Callbacks to call on finishing a settings read.
    name_of_yaml_file : str
      Settings to read from (defaults to settings.yaml)
    expert : bool
      Show expert settings (defaults to False)
    gui_mode : bool
      ??? (defaults to True)
    skip : bool
      Skip reading of the settings (defaults to False). Intended for
      use when reading from network connections.
    """
    show_auto_survey = Bool(False)
    settings_yaml = list()
    auto_survey = SVGButton(
        label='Auto\nSurvey',
        tooltip='Auto populate surveyed lat, lon and alt fields',
        filename='',
        width=20,
        height=20)
    settings_read_button = SVGButton(
        tooltip='Reload settings from Piksi',
        filename=resource_filename('console/images/fontawesome/refresh.svg'),
        allow_clipping=False,
        width_padding=4, height_padding=4)
    settings_save_button = SVGButton(
        label='Save to\nDevice',
        tooltip='Save settings to persistent storage on device.',
        filename=resource_filename('console/images/fontawesome/floppy-o.svg'),
        width=20,
        height=20)
    settings_export_to_file_button = SVGButton(
        label='Export to\nFile',
        tooltip='Export settings from device to a file on this PC.',
        filename=resource_filename('console/images/fontawesome/download.svg'),
        width=20,
        height=20)
    settings_import_from_file_button = SVGButton(
        label='Import\nfrom File',
        tooltip='Import settings to device from a file on this PC.',
        filename=resource_filename('console/images/fontawesome/upload.svg'),
        width=20,
        height=20)
    factory_default_button = SVGButton(
        label='Reset to\nDefaults',
        tooltip='Reset to Factory Defaults',
        filename=resource_filename('console/images/fontawesome/exclamation-triangle.svg'),
        width=20,
        height=20)
    settings_list = List(SettingBase)
    expert = Bool()
    selected_setting = Instance(SettingBase)
    traits_view = View(
        HSplit(
            Item(
                'settings_list',
                editor=TabularEditor(
                    adapter=SimpleAdapter(),
                    editable_labels=False,
                    auto_update=True,
                    editable=False,
                    selected='selected_setting'),
                show_label=False, ),
            VGroup(
                HGroup(
                    Item('settings_save_button', show_label=False),
                    Item('settings_export_to_file_button', show_label=False),
                    Item('settings_import_from_file_button', show_label=False),
                    Item('factory_default_button', show_label=False),
                    Item(
                        'auto_survey',
                        show_label=False,
                        visible_when='show_auto_survey'),
                ),
                HGroup(
                    Item('settings_read_button', show_label=False,
                         padding=0, height=-20, width=-20),
                    Item('', label="Refresh settings\nfrom device", padding=0),
                    Item('expert', show_label=False),
                    Item('', label="Show Advanced\nSettings", padding=0),
                ),
                Item('selected_setting', style='custom', show_label=False),
            ),
        )
    )

    def _selected_setting_changed(self):
        if self.selected_setting:
            if (self.selected_setting.name in [
                'surveyed_position', 'broadcast', 'surveyed_lat',
                'surveyed_lon', 'surveyed_alt'
            ] and self.lat != 0 and self.lon != 0):
                self.show_auto_survey = True
            else:
                self.show_auto_survey = False

    def _expert_changed(self, info):
        try:
            self.settings_display_setup(do_read_finished=False)
        except AttributeError:
            pass

    def _settings_read_button_fired(self):
        self.enumindex = 0
        self.ordering_counter = 0
        self.link(MsgSettingsReadByIndexReq(index=self.enumindex))

    def _settings_save_button_fired(self):
        self.link(MsgSettingsSave())

    def _factory_default_button_fired(self):
        confirm_prompt = prompt.CallbackPrompt(
            title="Reset to Factory Defaults?",
            actions=[prompt.close_button, prompt.reset_button],
            callback=self.reset_factory_defaults)
        confirm_prompt.text = "This will erase all settings and then reset the device.\n" \
                              + "Are you sure you want to reset to factory defaults?"
        confirm_prompt.run(block=False)

    def reset_factory_defaults(self):
        # Reset the Piksi, with flag set to restore default settings
        self.link(MsgReset(flags=1))

    def _settings_export_to_file_button_fired(self):
        """Exports current gui settings to INI file. Prompts user for file name and location.
        Should handle all expected error cases.  Defaults to file "config.ini" in the swift_path
        """
        # Prompt user for location and name of file
        file = FileDialog(action='save as',
                          default_directory=swift_path,
                          default_filename='config.ini',
                          wildcard='*.ini')
        is_ok = file.open()
        if is_ok == OK:
            print('Exporting settings to local path {0}'.format(file.path))
            # copy settings so we can modify dict in place to write for configparser
            settings_out = copy.deepcopy(self.settings)
            # iterate over nested dict and set inner value to a bare string rather than dict
            for section in settings_out:
                for setting, inner_dict in self.settings[section].iteritems():
                    settings_out[section][setting] = str(inner_dict.value)
            # write out with config parser
            parser = configparser.RawConfigParser()
            # the optionxform is needed to handle case sensitive settings
            parser.optionxform = str
            parser.read_dict(settings_out)
            # write to ini file
            try:
                with open(file.path, "w") as f:
                    parser.write(f)
            except IOError as e:
                print('Unable to export settings to file due to IOError: {}'.format(e))
        else:  # No error message because user pressed cancel and didn't choose a file
            pass

    def _settings_import_from_file_button_fired(self):
        """Imports settings from INI file and sends settings write to device for each entry.
        Prompts user for input file.  Should handle all expected error cases.
        """
        # Prompt user for file
        file = FileDialog(action='open',
                          default_directory=swift_path,
                          default_filename='config.ini',
                          wildcard='*.ini')
        is_ok = file.open()
        if is_ok == OK:  # file chosen successfully
            print('Importing settings from local path {} to device.'.format(file.path))
            parser = configparser.ConfigParser()
            # the optionxform is needed to handle case sensitive settings
            parser.optionxform = str
            try:
                with open(file.path, 'r') as f:
                    parser.read_file(f)
            except configparser.ParsingError as e:  # file formatted incorrectly
                print('Unable to parse ini file due to ParsingError: {}.'.format(e))
                print('Unable to import settings to device.')
                return
            except IOError as e:  # IOError (likely a file permission issue)
                print('Unable to read ini file due to IOError: {}'.format(e))
                print('Unable to import settings to device.')
                return

            # Iterate over each setting and set in the GUI.
            # Use the same mechanism as GUI to do settings write to device

            for section, settings in parser.items():
                this_section = self.settings.get(section, None)
                for setting, value in settings.items():
                    if this_section:
                        this_setting = this_section.get(setting, None)
                        if this_setting:
                            this_setting.value = value
                        else:
                            print(("Unable to import settings from file. Setting \"{0}\" in section \"{1}\""
                                   " has not been sent from device.").format(setting, section))
                            return
                    else:
                        print(("Unable to import settings from file."
                               " Setting section \"{0}\" has not been sent from device.").format(section))
                        return

            # Double check that no settings had a write failure.  All settings should exist if we get to this point.
            a = TimedDelayStoppableThread(SETTINGS_REVERT_TIMEOUT + 0.1,
                                          target=self._wait_for_any_write_failures,
                                          args=(dict(parser)))
            a.start()
        else:
            pass  # No error message here because user likely pressed cancel when choosing file

    def _auto_survey_fired(self):
        confirm_prompt = prompt.CallbackPrompt(
            title="Auto populate surveyed position?",
            actions=[prompt.close_button, prompt.auto_survey_button],
            callback=self.auto_survey_fn)
        confirm_prompt.text = "\n" \
                              + "This will set the Surveyed Position section to the \n" \
                              + "mean position of the last 1000 position solutions.\n \n" \
                              + "The fields that will be auto-populated are: \n" \
                              + "Surveyed Lat \n" \
                              + "Surveyed Lon \n" \
                              + "Surveyed Alt \n \n" \
                              + "The surveyed position will be an approximate value. \n" \
                              + "This may affect the relative accuracy of Piksi. \n \n" \
                              + "Are you sure you want to auto-populate the Surveyed Position section?"
        confirm_prompt.run(block=False)

    def auto_survey_fn(self):
        lat_value = str(self.lat)
        lon_value = str(self.lon)
        alt_value = str(self.alt)
        self.settings['surveyed_position']['surveyed_lat'].value = lat_value
        self.settings['surveyed_position']['surveyed_lon'].value = lon_value
        self.settings['surveyed_position']['surveyed_alt'].value = alt_value
        self.settings_display_setup(do_read_finished=False)

    def _wait_for_any_write_failures(self, parser):
        """Checks for any settings write failures for which a successful write is expected.
        If no failures have occurred, we prompt the user whether to save settings to the device's flash.

           Args:
                parser (dict): A dict of dicts with setting sections then names for keys
        """
        write_failures = 0
        for section, settings in parser.items():
            for setting, _ in settings.items():
                if self.settings[section][setting].write_failure:
                    write_failures += 1
                    self.settings[section][setting].write_failure = False
        if write_failures == 0:
            print("Successfully imported settings from file.")
            confirm_prompt = prompt.CallbackPrompt(
                title="Save to device flash?",
                actions=[prompt.close_button, prompt.ok_button],
                callback=self._settings_save_button_fired)
            confirm_prompt.text = "\n" \
                                  "  Settings import from file complete.  Click OK to save the settings  \n" \
                                  "  to the device's persistent storage.  \n"
            confirm_prompt.run(block=False)
        else:
            print("Unable to import settings from file: {0} settings write failures occurred.".format(write_failures))

    # Callbacks for receiving messages
    def settings_display_setup(self, do_read_finished=True):
        self.settings_list = []
        sections = sorted(self.settings.keys())
        for sec in sections:
            this_section = []
            for name, setting in sorted(
                    self.settings[sec].iteritems(),
                    key=lambda n_s: n_s[1].ordering):
                if not setting.expert or (self.expert and setting.expert):
                    this_section.append(setting)
            if this_section:
                self.settings_list.append(SectionHeading(sec))
                self.settings_list += this_section
        # call read_finished_functions as needed
        if do_read_finished:
            for cb in self.read_finished_functions:
                if self.gui_mode:
                    GUI.invoke_later(cb)
                else:
                    cb()

    def settings_read_by_index_done_callback(self, sbp_msg, **metadata):
        self.settings_display_setup()

    def settings_read_resp_callback(self, sbp_msg, **metadata):
        confirmed_set = True
        settings_list = sbp_msg.setting.split("\0")
        if len(settings_list) <= 3:
            print("Received malformed settings read response {0}".format(
                sbp_msg))
            confirmed_set = False
        try:
            if self.settings[settings_list[0]][settings_list[1]].value != settings_list[2]:
                try:
                    float_val = float(self.settings[settings_list[0]][settings_list[1]].value)
                    float_val2 = float(settings_list[2])
                    if abs(float_val - float_val2) > 0.000001:
                        confirmed_set = False
                except ValueError:
                    confirmed_set = False
            if confirmed_set:
                # If we verify the new values matches our expectation, we cancel the revert thread
                if self.settings[settings_list[0]][settings_list[1]].timed_revert_thread:
                    self.settings[settings_list[0]][settings_list[1]].timed_revert_thread.stop()
                self.settings[settings_list[0]][settings_list[1]].confirmed_set = True
        except KeyError:
            return

    def settings_write_resp_callback(self, sbp_msg, **metadata):
        if sbp_msg.status == 2:
            # Setting was rejected.  This shouldn't happen because we'll only
            # send requests for settings enumerated using read by index.
            return
        settings_list = sbp_msg.setting.split("\0")
        if len(settings_list) <= 3:
            print("Received malformed settings write response {0}".format(
                sbp_msg))
            return
        try:
            setting = self.settings[settings_list[0]][settings_list[1]]
        except KeyError:
            return
        if setting.timed_revert_thread:
            setting.timed_revert_thread.stop()
        if sbp_msg.status == 1:
            # Value was rejected.  Inform the user and revert display to the
            # old value.
            new = setting.value
            old = settings_list[2]
            setting.revert_to_prior_value(setting.name, old, new)
            return
        # Write accepted.  Use confirmed value in display.
        setting.value = settings_list[2]
        setting.confirmed_set = True

    def settings_read_by_index_callback(self, sbp_msg, **metadata):
        section, setting, value, format_type = sbp_msg.payload[2:].split(
            '\0')[:4]
        self.ordering_counter += 1
        if format_type == '':
            format_type = None
        else:
            setting_type, setting_format = format_type.split(':')
        if section not in self.settings:
            self.settings[section] = {}
        if format_type is None:
            # Plain old setting, no format information
            self.settings[section][setting] = Setting(
                setting,
                section,
                value,
                ordering=self.ordering_counter,
                settings=self)
        else:
            if setting_type == 'enum':
                enum_values = setting_format.split(',')
                self.settings[section][setting] = EnumSetting(
                    setting,
                    section,
                    value,
                    ordering=self.ordering_counter,
                    values=enum_values,
                    settings=self)
            else:
                # Unknown type, just treat is as a string
                self.settings[section][setting] = Setting(
                    setting, section, value, settings=self)
        if self.enumindex == sbp_msg.index:
            self.enumindex += 1
            self.link(MsgSettingsReadByIndexReq(index=self.enumindex))

    def piksi_startup_callback(self, sbp_msg, **metadata):
        self.settings.clear()
        self._settings_read_button_fired()

    def set(self, section, name, value):
        self.link(
            MsgSettingsWrite(setting='%s\0%s\0%s\0' % (section, name, value)))

    def cleanup(self):
        """ Remove callbacks from serial link. """
        self.link.remove_callback(self.piksi_startup_callback, SBP_MSG_STARTUP)
        self.link.remove_callback(self.settings_read_by_index_callback,
                                  SBP_MSG_SETTINGS_READ_BY_INDEX_REQ)
        self.link.remove_callback(self.settings_read_by_index_callback,
                                  SBP_MSG_SETTINGS_READ_BY_INDEX_RESP)
        self.link.remove_callback(self.settings_read_by_index_done_callback,
                                  SBP_MSG_SETTINGS_READ_BY_INDEX_DONE)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cleanup()

    def __init__(self,
                 link,
                 read_finished_functions=[],
                 name_of_yaml_file="settings.yaml",
                 expert=False,
                 gui_mode=True,
                 skip=False):
        super(SettingsView, self).__init__()
        self.expert = expert
        self.show_auto_survey = False
        self.gui_mode = gui_mode
        self.enumindex = 0
        self.settings = {}
        self.link = link
        self.link.add_callback(self.piksi_startup_callback, SBP_MSG_STARTUP)
        self.link.add_callback(self.settings_read_by_index_callback,
                               SBP_MSG_SETTINGS_READ_BY_INDEX_REQ)
        self.link.add_callback(self.settings_read_by_index_callback,
                               SBP_MSG_SETTINGS_READ_BY_INDEX_RESP)
        self.link.add_callback(self.settings_read_by_index_done_callback,
                               SBP_MSG_SETTINGS_READ_BY_INDEX_DONE)
        self.link.add_callback(self.settings_read_resp_callback,
                               SBP_MSG_SETTINGS_READ_RESP)
        self.link.add_callback(self.settings_write_resp_callback,
                               SBP_MSG_SETTINGS_WRITE_RESP)
        # Read in yaml file for setting metadata
        self.settings_yaml = SettingsList(name_of_yaml_file)
        # List of functions to be executed after all settings are read.
        # No support for arguments currently.
        self.read_finished_functions = read_finished_functions
        self.setting_detail = SettingBase()
        if not skip:
            try:
                self._settings_read_button_fired()
            except IOError:
                print(
                    "IOError in settings_view startup call of _settings_read_button_fired."
                )
                print("Verify that write permissions exist on the port.")
        self.python_console_cmds = {'settings': self}
