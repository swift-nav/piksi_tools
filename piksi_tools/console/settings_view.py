#!/usr/bin/env python
# Copyright (C) 2011-2019 Swift Navigation Inc.
# Contact: Swift Navigation <dev@swiftnav.com>
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
import configparser

from six.moves.queue import Queue

from pyface.api import GUI
from sbp.piksi import MsgReset
from sbp.settings import MsgSettingsSave
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

from libsettings import Settings, SettingsWriteResponseCodes

if ETSConfig.toolkit != 'null':
    from enable.savage.trait_defs.ui.svg_button import SVGButton
else:
    SVGButton = dict


class WorkQueue():

    def __init__(self, settings_view):
        self._settings_view = settings_view
        self._work_queue = Queue()
        self._worker = threading.Thread(target=self._work_thd)
        self._worker.daemon = True
        self._worker.start()

    def put(self, func, *argv):
        self._work_queue.put((func, argv))

    def _work_thd(self):
        while True:
            (func, argv) = self._work_queue.get(block=True)
            func(*argv)
            self._work_queue.task_done()


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
            Item('value',
                 editor=TextEditor(auto_set=False, enter_set=True),
                 visible_when='confirmed_set and not readonly'),
            Item('value',
                 style='readonly',
                 visible_when='not confirmed_set or readonly',
                 editor=TextEditor(readonly_allow_selection=True)),
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

    def __init__(self, name, section, value, ordering=0, settings=None):
        self.name = name
        self.section = section
        self.full_name = "%s.%s" % (section, name)
        self.value = value
        self.ordering = ordering
        self.settings = settings
        self.confirmed_set = True
        self.skip_write_req = False

        if settings is None:
            return

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

    def revert_to_prior_value(self, section, name, old, new, error_value):
        '''Revert setting to old value in the case we can't confirm new value'''

        if self.readonly:
            return

        self.skip_write_req = True
        self.value = old
        self.skip_write_req = False

        invalid_setting_prompt = prompt.CallbackPrompt(
            title="Settings Write Error: {}.{}".format(section, name),
            actions=[prompt.close_button], )
        if error_value == SettingsWriteResponseCodes.SETTINGS_WR_TIMEOUT:
            invalid_setting_prompt.text = \
                ("\n   Unable to confirm that {0} was set to {1}.\n"
                 "   Message timed out.\n"
                 "   Ensure that the new setting value did not interrupt console communication.\n"
                 "   Error Value: {2}")
        elif error_value == SettingsWriteResponseCodes.SETTINGS_WR_VALUE_REJECTED:
            invalid_setting_prompt.text += \
                ("   Ensure the range and formatting of the entry are correct.\n"
                 "   Error Value: {2}")
        elif error_value == SettingsWriteResponseCodes.SETTINGS_WR_SETTING_REJECTED:
            invalid_setting_prompt.text += \
                ("   {0} is not a valid setting.\n"
                 "   Error Value: {2}")
        elif error_value == SettingsWriteResponseCodes.SETTINGS_WR_PARSE_FAILED:
            invalid_setting_prompt.text += \
                ("   Could not parse value: {1}.\n"
                 "   Error Value: {2}")
        elif error_value == SettingsWriteResponseCodes.SETTINGS_WR_READ_ONLY:
            invalid_setting_prompt.text += \
                ("   {0} is read-only.\n"
                 "   Error Value: {2}")
        elif error_value == SettingsWriteResponseCodes.SETTINGS_WR_MODIFY_DISABLED:
            invalid_setting_prompt.text += \
                ("   Modifying {0} is currently disabled.\n"
                 "   Error Value: {2}")
        elif error_value == SettingsWriteResponseCodes.SETTINGS_WR_SERVICE_FAILED:
            invalid_setting_prompt.text += \
                ("   Service failed while changing setting. See logs.\n"
                 "   Error Value: {2}")
        else:
            invalid_setting_prompt.text += \
                ("   Unknown Error.\n"
                 "   Error Value: {2}")
        invalid_setting_prompt.text = invalid_setting_prompt.text.format(self.name, new, error_value)
        invalid_setting_prompt.run()

    def _write_value(self, old, new):
        if (old is not Undefined and new is not Undefined):
            self.confirmed_set = False
            (error, section, name, value) = self.settings.settings_api.write(self.section, self.name, new)
            if error == SettingsWriteResponseCodes.SETTINGS_WR_OK:
                self.value = new
            else:
                self.revert_to_prior_value(self.section, self.name, old, new, error)

            self.confirmed_set = True

        # If we have toggled the Inertial Nav enable setting (currently "output mode")
        # we display some helpful hints for the user
        if (self.section == "ins" and self.name == "output_mode" and
                old is not None and self.settings is not None):
            if new in ['GNSS and INS', 'INS Only', 'Loosely Coupled', 'LC + GNSS', 'Debug', 'debug']:
                hint_thread = threading.Thread(
                    target=self.settings._display_ins_settings_hint)
                hint_thread.start()
            # regardless of which way setting is going, a restart is required
            else:
                self.settings.display_ins_output_hint()

    def _value_changed(self, name, old, new):
        if getattr(self, 'settings', None) is None:
            return

        if self.skip_write_req or old == new:
            return

        self.settings.workqueue.put(self._write_value, old, new)


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

    def __init__(self, name, section, value, values, **kwargs):
        self.values = values
        Setting.__init__(self, name, section, value, **kwargs)


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


class SimpleChangeAdapter(TabularAdapter):
    columns = [('Name', 'name'), ('Current Value', 'value'), ('Recommended Value', 'rec_value')]
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
    skip_read : bool
      Skip reading of the settings (defaults to False). Intended for
      use when reading from network connections or file.
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

    def update_required_smoothpose_settings(self):
        """
        Update any recommended settings for smoothpose
        """
        list = self._determine_smoothpose_recommended_settings()
        for each_setting in list:
            self.settings[each_setting.section][each_setting.name].value = each_setting.rec_value

    def _determine_smoothpose_recommended_settings(self):
        """
        Returns a list of settings that should change for smoothpose
        """

        recommended_settings = {'imu_raw_output': Setting('imu_raw_output', 'imu', 'True'),
                                'gyro_range': Setting('gyro_range', 'imu', '125'),
                                'acc_range': Setting('acc_range', 'imu', '8g'),
                                'imu_rate': Setting('imu_rate', 'imu', '100')
                                }
        settings_wrong_list = []
        for each_key in recommended_settings.keys():
            if recommended_settings[each_key].value != self.settings['imu'][each_key].value:
                self.settings['imu'][each_key].rec_value = recommended_settings[each_key].value
                settings_wrong_list.append(self.settings['imu'][each_key])
        return settings_wrong_list

    def _save_and_reset(self):
        self._settings_save_button_fired()
        self.link(MsgReset(flags=0))

    def _display_ins_settings_hint(self):
        """
        Display helpful hint messages to help a user set up inertial product
        """
        settings_list = self._determine_smoothpose_recommended_settings()
        if len(settings_list) > 0:
            confirm_prompt = prompt.CallbackPrompt(
                title="Update Recommended Inertial Navigation Settings?",
                actions=[prompt.close_button, prompt.update_button],
                callback=self.update_required_smoothpose_settings)
            confirm_prompt.settings_list = settings_list
            confirm_prompt.text = "\n\n" \
                "    In order to enable INS output, it is necessary to enable and configure the imu.    \n" \
                "    Your current settings indicate that your imu raw ouptut is disabled and/or improperly configured.    \n\n" \
                "    Choose \"Update\" to allow the console to change the following settings on your device to help enable INS output.    \n" \
                "    Choose \"Close\" to ignore this recommendation and not update any device settings.    \n\n"
            # from objbrowser import browse
            # browse(confirm_prompt)
            confirm_prompt.view.content.content[0].content.append(
                Item("settings_list", editor=TabularEditor(
                    adapter=SimpleChangeAdapter(),
                    editable_labels=False,
                    auto_update=True,
                    editable=False),
                    # Only make pop-up as tall as necessary
                    height=-(len(confirm_prompt.settings_list) * 25 + 40),
                    label='Recommended Settings'))
            confirm_prompt.run(block=False)
            while (confirm_prompt.thread.is_alive()):
                # Wait until first popup is closed before opening second popup
                time.sleep(1)
        # even if we didn't need to change any settings, we still have to save settings and restart
        self.display_ins_output_hint()

    def display_ins_output_hint(self):
        confirm_prompt2 = prompt.CallbackPrompt(
            title="Restart Device?",
            actions=[prompt.close_button, prompt.ok_button],
            callback=self._save_and_reset)

        confirm_prompt2.text = "\n\n" \
            "    In order for the \"Ins Output Mode\" setting to take effect, it is necessary to save the    \n" \
            "    current settings to device flash and then power cycle your device.    \n\n" \
            "    Choose \"OK\" to immediately save settings to device flash and send the software reset command.    \n" \
            "    The software reset will temporarily interrupt the console's connection to the device but it   \n" \
            "    will recover on its own.    \n\n"

        confirm_prompt2.run(block=False)

    def _read_all_fail(self):
        confirm_prompt = prompt.CallbackPrompt(
            title="Failed to read settings from device",
            actions=[prompt.close_button])
        confirm_prompt.text = "\n" \
            "  Check connection and refresh settings.  \n"
        confirm_prompt.run(block=False)

    def _settings_unconfirm_all(self):
        # Clear the tabular editor
        del self.settings_list[:]
        for section in self.settings.keys():
            for name in self.settings[section].keys():
                self.settings[section][name].confirmed_set = False

    def _settings_read_all(self):
        self._settings_unconfirm_all()
        self.workqueue.put(self._read_all_thread)

    def _read_all_thread(self):
        settings_list = self.settings_api.read_all()

        if not settings_list:
            self._read_all_fail()
            return

        idx = 0

        for setting in settings_list:
            section = setting['section']
            name = setting['name']
            value = setting['value']
            fmt_type = setting['fmt_type']

            idx += 1

            if fmt_type == '':
                setting_type = None
                setting_format = None
            else:
                setting_type, setting_format = fmt_type.split(':')

            if section not in self.settings:
                self.settings[section] = {}

            # setting exists, we won't reinitilize it but rather update existing setting
            existing_setting = self.settings[section].get(name, False)
            if existing_setting:
                existing_setting.value = value
                existing_setting.ordering = idx
                if setting_type == 'enum':
                    enum_values = setting_format.split(',')
                    existing_setting.enum_values = enum_values
                existing_setting.confirmed_set = True
                continue

            if setting_type == 'enum':
                enum_values = setting_format.split(',')
                self.settings[section][name] = EnumSetting(
                    name,
                    section,
                    value,
                    enum_values,
                    ordering=idx,
                    settings=self)
            else:
                # No known format type
                self.settings[section][name] = Setting(
                    name, section, value, settings=self, ordering=idx)

        self.settings_display_setup()

    def _settings_read_button_fired(self):
        self._settings_read_all()

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

        if file.open() != OK:
            # No error message here because user likely pressed cancel when choosing file
            return

        print('Exporting settings to local path {0}'.format(file.path))
        # copy settings so we can modify dict in place to write for configparser
        settings_out = {}
        # iterate over nested dict and set inner value to a bare string rather than dict
        for section in self.settings:
            settings_out[section] = {}
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

    def _import_success(self, count):
        print("Successfully imported {} settings from file.".format(count))
        confirm_prompt = prompt.CallbackPrompt(
            title="Save to device flash?",
            actions=[prompt.close_button, prompt.ok_button],
            callback=self._settings_save_button_fired)
        confirm_prompt.text = "\n" \
            "  Settings import from file complete.  Click OK to save the settings  \n" \
            "  to the device's persistent storage.  \n"
        confirm_prompt.run(block=False)

    def _import_fail(self):
        confirm_prompt = prompt.CallbackPrompt(
            title="Failed to import settings from file",
            actions=[prompt.close_button])
        confirm_prompt.text = "\n" \
            "  Verify that config file is not overwriting active connection settings.  \n"
        confirm_prompt.run(block=False)

    def _import_failure_section(self, section):
        print(("Unable to import settings from file."
               " Setting section \"{0}\" has not been sent from device.").format(section))

    def _import_failure_not_found(self, section, name):
        print(("Unable to import settings from file. Setting \"{0}\" in section \"{1}\""
               " has not been sent from device.").format(name, section))

    def _import_failure_write(self, error, section, name):
        print(("Writing setting \"{0}\" in section \"{1}\""
               " failed with error code {2}.").format(name, section, error))

    def _write_parsed(self, parser):
        settings_to_write = []
        # Iterate over each setting
        for section, settings in parser.items():
            if not settings:
                # Empty
                continue

            this_section = self.settings.get(section, None)

            if this_section is None:
                self._import_failure_section(section)
                return

            for name, value in settings.items():
                this_setting = this_section.get(name, None)
                if this_setting is None:
                    self._import_failure_not_found(section, name)
                    return

                settings_to_write.append({'section': section,
                                          'name': name,
                                          'value': value})

        ret = self.settings_api.write_all(settings_to_write)

        success = True

        for (error, section, name, value) in ret:
            if error and error != SettingsWriteResponseCodes.SETTINGS_WR_READ_ONLY:
                self._import_failure_write(error, section, name)
                success = False
            else:
                self.skip_write_req = True
                self.settings.get(section, None).get(name, None).value = value
                self.skip_write_req = False

        if success:
            self._import_success(len(ret))
        else:
            self._import_fail()

    def _settings_import_from_file_button_fired(self):
        """Imports settings from INI file and sends settings write to device for each entry.
        Prompts user for input file.  Should handle all expected error cases.
        """
        # Prompt user for file
        file = FileDialog(action='open',
                          default_directory=swift_path,
                          default_filename='config.ini',
                          wildcard='*.ini')
        if file.open() != OK:
            # No error message here because user likely pressed cancel when choosing file
            return

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

        self.workqueue.put(self._write_parsed, parser)

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

    def finish_read(self):
        for cb in self.read_finished_functions:
            if self.gui_mode:
                GUI.invoke_later(cb)
            else:
                cb()

    # Callbacks for receiving messages
    def settings_display_setup(self, do_read_finished=True):
        self.settings_list = []
        sections = sorted(self.settings.keys())
        for sec in sections:
            this_section = []
            for name, setting in sorted(
                    self.settings[sec].items(),
                    key=lambda n_s: n_s[1].ordering):
                if not setting.expert or (self.expert and setting.expert):
                    this_section.append(setting)
            if this_section:
                self.settings_list.append(SectionHeading(sec))
                self.settings_list += this_section

        if do_read_finished:
            self.finish_read()

    def piksi_startup_callback(self, sbp_msg, **metadata):
        self._settings_read_all()

    def cleanup(self):
        """ Remove callbacks from serial link. """
        self.link.remove_callback(self.piksi_startup_callback, SBP_MSG_STARTUP)

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
                 skip_read=False):
        super(SettingsView, self).__init__()
        self.settings_api = Settings(link)
        self.workqueue = WorkQueue(self)
        self.expert = expert
        self.gui_mode = gui_mode
        self.settings = {}
        self.link = link
        self.link.add_callback(self.piksi_startup_callback, SBP_MSG_STARTUP)
        # Read in yaml file for setting metadata
        self.settings_yaml = SettingsList(name_of_yaml_file)
        # List of functions to be executed after all settings are read.
        # No support for arguments currently.
        self.read_finished_functions = read_finished_functions
        self.setting_detail = SettingBase()
        if not skip_read:
            try:
                self._settings_read_all()
            except IOError:
                print(
                    "IOError in settings_view startup call of _settings_read_all."
                )
                print("Verify that write permissions exist on the port.")
        self.python_console_cmds = {'settings': self}
