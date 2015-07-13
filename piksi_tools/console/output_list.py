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

"""Contains the class OutputStream, a HasTraits file-like text buffer."""

from traits.api import HasTraits, Str, Bool, Trait, Int, List, Font, Float, Enum, Property
from traitsui.api import View, UItem, Handler, TableEditor, TabularEditor
from traits.etsconfig.api import ETSConfig
from pyface.api import GUI
from traitsui.table_column import ObjectColumn
from traitsui.tabular_adapter import TabularAdapter
import time
import re


# These levels are identical to sys.log levels
LOG_EMERG      = 0       # system is unusable
LOG_ALERT      = 1       # action must be taken immediately
LOG_CRIT       = 2       # critical conditions
LOG_ERROR      = 3       # error conditions
LOG_WARN       = 4       # warning conditions
LOG_NOTICE     = 5       # normal but significant condition
LOG_INFO       = 6       # informational
LOG_DEBUG      = 7       # debug-level messages

# These log levels are defined uniquely to this module to handle our overload of the
# list for stdout, stderror, and the device's log messages
LOG_STD_ERR    = 8       # Python Std Error
LOG_STD_OUT    = 9       # Special Placeholder for Standard Output messages from Python

LOG_LEVEL_DEFAULT = -1

# This maps the numbers to a human readable string

SYSLOG_LEVELS = {#LOG_EMERG : "EMERG",
                 #LOG_ALERT : "ALERT",
                 #LOG_CRIT  : "CRIT",
                 LOG_ERROR : "ERROR",
                 LOG_WARN  : "WARNING",
                 #LOG_NOTICE: "NOTICE",
                 LOG_INFO  : "INFO",
                 LOG_DEBUG : "DEBUG",
# These log levels are defined uniquely to this module to handle our overload of the
# list for stdout, stderror, and the device's log messages
                 #LOG_STD_ERR: "PYTHON_STD_ERROR",
                 #LOG_STD_OUT: "PYTHON_STD_OUTPUT"
                 }


DEFAULT_MAX_LEN = 250

class LogItemOutputListAdapter(TabularAdapter):
  columns = [('timestamp','timestamp'),('log_level_str','log_level_str'),('msg','msg')]
  font = Font('12')
  can_edit = Bool(False)
  timestamp_width = Float(0.12)
  log_level_width = Float(0.08)
  msg_width = Float(0.8)

class LogItem(HasTraits):
  log_level = Int
  timestamp = Str
  msg = Str
  # surname is displayed in qt-only row label:
  log_level_str = Property(fget=lambda self: SYSLOG_LEVELS.get(self.log_level, "NA"),
                   depends_on='log_level')
  def __init__(self, msg, level=None):
    self.log_level=LOG_LEVEL_DEFAULT
    if level==None: #try to infer log level if an old message
      split_colons = msg.split(":")
      print split_colons[0]
      for key,value in SYSLOG_LEVELS.iteritems():
        print key
        print value
        if split_colons[0].lower() == value.lower():
          self.log_level = key
    else:
      self.log_level=level
    self.msg = msg.rstrip('\n')
    self.timestamp = time.strftime("%b %d %Y %H:%M:%S")

  def matches_log_level_filter(self, log_level):
    if self.log_level<=log_level:
      return True
    else:
      return False


class OutputList(HasTraits):
  """This class has methods to emulate an file-like output list of strings.

  The `max_len` attribute specifies the maximum number of bytes saved by
  the object.  `max_len` may be set to None.

  The `paused` attribute is a bool; when True, text written to the
  OutputStream is saved in a separate buffer, and the display (if there is
  one) does not update.  When `paused` returns is set to False, the data is
  copied from the paused buffer to the main text string.
  """

  # The text that has been written with the 'write' method.
  unfiltered_list = List(LogItem)
  filtered_list = List(LogItem)
  log_level_filter = Enum(list(SYSLOG_LEVELS.iterkeys()))
  # The maximum allowed length of self.text (and self._paused_buffer).
  max_len = Trait(DEFAULT_MAX_LEN, None, Int)

  # When True, the 'write' method appends its value to self._paused_buffer
  # instead of self.text.  When the value changes from True to False,
  # self._paused_buffer is copied back to self.text.
  paused = Bool(False)

  # String that holds text written while self.paused is True.
  _paused_buffer = List(LogItem)

  table_editor = TableEditor(
  columns=[ObjectColumn(name='timestamp', width=0.15),
           ObjectColumn(name='log_level', width=0.1),
           ObjectColumn(name='msg', width=0.75),
           ],
  auto_size=False,
  rows=50,
  row_height=4,
  cell_font='helvetica 8',
  deletable=False,
  sortable=False,
  editable=False,
  show_lines=False,
  )

  def write(self, s):
    if not s.isspace():
      log = LogItem(s)
      if self.paused:
        self.append_truncate(self._paused_buffer, log)
      else:
        self.append_truncate(self.unfiltered_list, log)
        if log.matches_log_level_filter(self.log_level_filter):
          self.append_truncate(self.filtered_list, log)

  def write_level(self, s, level):
    log = LogItem(s, level)
    if self.paused:
      self.append_truncate(self._paused_buffer, log)
    else:
      self.append_truncate(self.unfiltered_list, log)
      if log.matches_log_level_filter(self.log_level_filter):
        self.append_truncate(self.filtered_list, log)

  def append_truncate(self, buffer, s):
    if len(buffer) > self.max_len:
      assert (len(buffer) - self.max_len) == 1, "buffer got longer and never was truncated"
      buffer.pop()
    buffer.insert(0, s)

  def clear(self):
    self.filtered_list=[]
    self.unfiltered_list=[]

  def flush(self):
    GUI.process_events()

  def close(self):
    pass

  def reset(self):
    self._paused_buffer = ''
    self.paused = False
    self.text = []

  def _log_level_filter_changed(self):
    self.filtered_list = [item for item in self.unfiltered_list if item.matches_log_level_filter(self.log_level_filter)]
    #self.filtered_list = filter(LogItem.matches_log_level_filter(self.log_level_filter), self.unfiltered_list)


  def _paused_changed(self):
    if self.paused:
      # Copy the current text to _paused_buffer.  While the OutputStream
      # is paused, the write() method will append its argument to _paused_buffer.
      self._paused_buffer = self.unfiltered_list
    else:
      # No longer paused, so copy the _paused_buffer to the displayed text, and
      # reset _paused_buffer.
      self.unfiltered_list = self._paused_buffer
      self._paused_buffer = ''

  def traits_view(self):
    view = \
      View(
          UItem('filtered_list',
                editor = TabularEditor(adapter=LogItemOutputListAdapter()))
        )
    return view

