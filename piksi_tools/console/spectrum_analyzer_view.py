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

  def parse_payload(self, raw_payload):
    """
    params
    ======
    payload: is a hex string from the SBP_MSG_USER_DATA message payload

    returns
    =======
    JSON dict of a payload based on this format, except all N of the diff_amplitude
    are together in a list under 'diff_amplitudes'

    FIELD               TYPE    OFFSET  SHORT EXPLANATION

    user_msg_tag        u16     0       bespoke preamble for spectrum message

    rx_time             struct  2       struct gps_time_t defined as double TOW + s16 WEEK

    starting_frequency  float  12       starting frequency for this packet

    frequency_step      float  16       frequency step for points in this packet

    min_amplitude       float  20       minimum level of amplitude

    amplitude_step      float  24       amplitude unit

    diff_amplitude      u8     28       N values in the above units
    """
    payload_header_bytes = 45
    diff_amplitude_n = (len(raw_payload) - payload_header_bytes) / 2
    diff_amplitude_fmt_str = 'H' * diff_amplitude_n
    # this is a tuple of length 7 + diff amplitude's N
    parsed_payload = struct.unpack('<Hdhffff' + diff_amplitude_fmt_str)
    fft_msg_header = [
      'user_msg_tag',
      'rx_time',
      'starting_frequency',
      'frequency_step',
      'min_amplitude',
      'amplitude_step'
    ]
    payload_json = dict(zip(fft_msg_header, parsed_payload[:len(fft_msg_header)]))
    fft_msg_payload = parsed_payload[len(fft_msg_header) + 1:]
    payload_json['diff_amplitudes'] = fft_msg_payload
    return payload_json

  def __init__(self, link):
    super(SpectrumAnalyzerView, self).__init__()
    self.link = link
    self.link.add_callback(self.spectrum_analyzer_state_callback, SBP_MSG_USER_DATA)
    self.python_console_cmds = {
      'spectrum': self
    }
