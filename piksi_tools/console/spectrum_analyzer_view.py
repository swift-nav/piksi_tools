#!/usr/bin/env python
# Copyright (C) 2011-2014, 2017 Swift Navigation Inc.
# Contact: engineering@swiftnav.com
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

from traits.api import HasTraits, Str, Dict
from traitsui.api import Item, Spring, View
from pyface.api import GUI

class SpectrumAnalyzerView(HasTraits):
  python_console_cmds = Dict()
  dummy_text = Str('This is where the Spectrum Analyzer output will go.')

  traits_view = View(
    Item('dummy_text', label='description')
  )

  def spectrum_analyzer_state_callback(self, sbp_msg, **metadata):
    raise NotImplementedError

  def update_plot(self):
    raise NotImplementedError

  def __init__(self, link):
    super(SpectrumAnalyzerView, self).__init__()
    self.link = link
    self.link.add_callback(self.spectrum_analyzer_state_callback, SBP_MSG_USER_DATA)
    self.python_console_cmds = {
      'spectrum': self
    }
