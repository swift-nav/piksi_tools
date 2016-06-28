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

from traits.api import Instance, Dict, HasTraits, Array, Float, \
                       on_trait_change, List, Int, Button, Bool, Str, Color, \
                       Constant, Font, Undefined, Property, Any, Enum
from traitsui.api import Item, UItem, View, HGroup, Handler, VGroup, \
                         ArrayEditor, HSplit, TabularEditor, TextEditor, \
                         EnumEditor
from traitsui.tabular_adapter import TabularAdapter
from traits.etsconfig.api import ETSConfig

if ETSConfig.toolkit != 'null':
  from enable.savage.trait_defs.ui.svg_button import SVGButton
else:
  SVGButton = dict
from pyface.api import GUI

import math
import os
import numpy as np
import datetime

from piksi_tools.fileio import FileIO
import piksi_tools.console.callback_prompt as prompt
from piksi_tools.console.utils import determine_path, MultilineTextEditor

from sbp.piksi      import *
from sbp.settings   import *
from sbp.system     import *

from settings_list import SettingsList

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

  traits_view = View(
    VGroup(
      Item('full_name', label='Name', style='readonly'),
      Item('value', editor=TextEditor(auto_set=False, enter_set=True)),
      Item('description', style='readonly'),
      Item('units', style='readonly'),
      Item('default_value', style='readonly'),
      UItem('notes', label="Notes", height=-1,
            editor=MultilineTextEditor(TextEditor(multi_line=True)), style='readonly',
            show_label=True, resizable=True),
      show_border=True,
      label='Setting',
    ),
  )

  def __init__(self, name, section, value, ordering, settings):
    self.name = name
    self.section = section
    self.full_name = "%s.%s" % (section, name)
    self.value = value
    self.ordering = ordering
    self.settings = settings
    self.expert = settings.settings_yaml.get_field(section, name, 'expert')
    self.description = settings.settings_yaml.get_field(section,
                                                           name, 'Description')
    self.units = settings.settings_yaml.get_field(section, name, 'units')
    self.notes = settings.settings_yaml.get_field(section, name, 'Notes')
    self.default_value = settings.settings_yaml.get_field(section, name,
                                                             'default value')

  def _value_changed(self, name, old, new):
    if (old != new and
        old is not Undefined and
        new is not Undefined):
      if type(self.value) == unicode:
        self.value = self.value.encode('ascii', 'replace')
      self.settings.set(self.section, self.name, self.value)

class EnumSetting(Setting):
  values = List()
  traits_view = View(
    VGroup(
      Item('full_name', label='Name', style='readonly'),
      Item('value', editor=EnumEditor(name='values')),
      Item('description', style='readonly'),
      Item('default_value', style='readonly'),
            UItem('notes', label="Notes", height=-1,
            editor=MultilineTextEditor(TextEditor(multi_line=True)), style='readonly',
            show_label=True, resizable=True),
      show_border=True,
      label='Setting',
    ),
  )

  def __init__(self, name, section, value, ordering, values, **kwargs):
    self.values = values
    Setting.__init__(self, name, section, value, ordering, **kwargs)

class SectionHeading(SettingBase):
  value = Constant('')

  def __init__(self, name):
    self.name = name

class SimpleAdapter(TabularAdapter):
  columns = [('Name', 'name'), ('Value',  'value')]
  font = Font('12')
  can_edit = Bool(False)
  SectionHeading_bg_color = Color(0xE0E0E0)
  SectionHeading_font = Font('14 bold')
  SectionHeading_name_text = Property
  Setting_name_text = Property
  name_width = Float(.7)
  value_width = Float(.3)

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

  settings_yaml = list()
  settings_read_button = SVGButton(
    label='Reload', tooltip='Reload settings from Piksi',
    filename=os.path.join(determine_path(), 'images', 'fontawesome', 'refresh.svg'),
    width=16, height=20)
  settings_save_button = SVGButton(
    label='Save to Flash', tooltip='Save settings to Flash',
    filename=os.path.join(determine_path(), 'images', 'fontawesome', 'download.svg'),
    width=16, height=20)
  factory_default_button = SVGButton(
    label='Reset to Defaults', tooltip='Reset to Factory Defaults',
    filename=os.path.join(determine_path(), 'images', 'fontawesome', 'exclamation-triangle.svg'),
    width=16, height=20)
  settings_list = List(SettingBase)
  expert=Bool()
  selected_setting = Instance(SettingBase)
  traits_view = View(
    HSplit(
      Item('settings_list',
        editor = TabularEditor(
          adapter=SimpleAdapter(),
          editable_labels=False,
          auto_update=True,
          selected='selected_setting'
        ),
        show_label=False,
      ),
      VGroup(
        HGroup(
          Item('settings_read_button', show_label=False),
          Item('settings_save_button', show_label=False),
          Item('factory_default_button', show_label=False),
        ),
        HGroup(Item('expert', label="Show Advanced Settings", show_label=True)),
        Item('selected_setting', style='custom', show_label=False),
      ),
    )
  )
  
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
                          callback=self.reset_factory_defaults
                         )
    confirm_prompt.text = "This will erase all settings and then reset the device.\n" \
                        + "Are you sure you want to reset to factory defaults?"
    confirm_prompt.run(block=False)

  def reset_factory_defaults(self):
    # Delete settings file
    fio = FileIO(self.link)
    fio.remove('config')
    # Reset the Piksi
    self.link(MsgReset())

  ##Callbacks for receiving messages
  def settings_display_setup(self, do_read_finished=True):
    self.settings_list = []
    sections = sorted(self.settings.keys())
    for sec in sections:
      this_section = []
      for name, setting in sorted(self.settings[sec].iteritems(),
        key=lambda (n, s): s.ordering):
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

  def settings_read_by_index_callback(self, sbp_msg, **metadata):
    if not sbp_msg.payload:
      # Settings output from Piksi is terminated by an empty message.
      # Bundle up our list and display it.
      self.settings_display_setup()

    section, setting, value, format_type = sbp_msg.payload[2:].split('\0')[:4]
    self.ordering_counter += 1
    if format_type == '':
      format_type = None
    else:
      setting_type, setting_format = format_type.split(':')
    if not self.settings.has_key(section):
      self.settings[section] = {}
    if format_type is None:
      # Plain old setting, no format information
      self.settings[section][setting] = Setting(setting, section, value,
                                                ordering=self.ordering_counter,
                                                settings=self
                                               )
    else:
      if setting_type == 'enum':
        enum_values = setting_format.split(',')
        self.settings[section][setting] = EnumSetting(setting, section, value,
                                                      ordering=self.ordering_counter,
                                                      values=enum_values,
                                                      settings=self
                                                     )
      else:
        # Unknown type, just treat is as a string
        self.settings[section][setting] = Setting(setting, section, value,
                                                  settings=self
                                                 )

    self.enumindex += 1
    self.link(MsgSettingsReadByIndexReq(index=self.enumindex))

  def piksi_startup_callback(self, sbp_msg, **metadata):
    self._settings_read_button_fired()

  def set(self, section, name, value):
    self.link(MsgSettingsWrite(setting='%s\0%s\0%s\0' % (section, name, value)))

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
        print "IOError in settings_view startup call of _settings_read_button_fired."
        print "Verify that write permissions exist on the port."
    self.python_console_cmds = {'settings': self}