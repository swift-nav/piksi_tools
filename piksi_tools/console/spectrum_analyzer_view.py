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
import struct
from collections import defaultdict
import numpy as np

from traits.api import Instance, HasTraits, Str, Dict
from traitsui.api import Item, Spring, View, Spring
from pyface.api import GUI
from chaco.api import ArrayPlotData, Plot
from enable.api import ComponentEditor

# How many points are in each FFT?
NUM_POINTS = 512

class SpectrumAnalyzerView(HasTraits):
  python_console_cmds = Dict()
  plot = Instance(Plot)
  plot_data = Instance(ArrayPlotData)
  traits_view = View(
    Item(
      'plot',
      editor=ComponentEditor(bgcolor=(0.8, 0.8, 0.8)),
      show_label=False
    )
  )

  def parse_payload(self, raw_payload):
    """
    Params
    ======
    payload: is a hex string from the SBP_MSG_USER_DATA message payload

    Returns
    =======
    JSON dict of a payload based on this format, except all N of the diff_amplitude
    are together in a list under 'diff_amplitudes' and rx_time is split into TOW and week

    Frequency is in Hz, Amplitude is in dB

    FIELD               TYPE    OFFSET  SHORT EXPLANATION

    user_msg_tag        u16     0       bespoke preamble for spectrum message

    rx_time             struct  2       struct gps_time_t defined as double TOW + s16 WEEK

    starting_frequency  float  12       starting frequency for this packet

    frequency_step      float  16       frequency step for points in this packet

    min_amplitude       float  20       minimum level of amplitude

    amplitude_step      float  24       amplitude unit

    diff_amplitude      u8     28       N values in the above units
    """
    payload_header_fmt_str = '<Hdhffff'
    payload_header_bytes = struct.calcsize(payload_header_fmt_str)
    diff_amplitude_n = (len(raw_payload) - payload_header_bytes)
    diff_amplitude_fmt_str = 'B' * diff_amplitude_n
    fmt_str = payload_header_fmt_str + diff_amplitude_fmt_str
    parsed_payload = struct.unpack(fmt_str, raw_payload)
    fft_msg_header = [
      'user_msg_tag',
      'TOW',
      'week',
      'starting_frequency',
      'frequency_step',
      'min_amplitude',
      'amplitude_step'
    ]
    payload_json = dict(zip(fft_msg_header, parsed_payload[:len(fft_msg_header)]))
    fft_msg_payload = parsed_payload[len(fft_msg_header):]
    payload_json['diff_amplitudes'] = fft_msg_payload
    return payload_json

  def get_frequencies(self, start_freq, freq_step, n):
    '''
    start_freq: float (Hz)
    freq_step: float (Hz)
    n: int
    '''
    return np.array([start_freq + freq_step*i for i in range(n)])

  def get_amplitudes(self, min_amplitude, diffs, unit):
    '''
    min_amplitude: float (dB)
    diffs: tuple of floats (dB)
    unit: float (dB)
    '''
    return np.array([min_amplitude + diff*unit for diff in diffs])

  def spectrum_analyzer_state_callback(self, sbp_msg, **metadata):
    '''
    Params
    ======
    sbp_msg: sbp.msg.SBP object

    Updates the view's data for use in self.update_plot
    '''
    # Need to figure out which user_msg_tag means it's an FFT message
    # for now assume that all SBP_MSG_USER_DATA is relevant
    fft_data = self.parse_payload(sbp_msg.contents)
    frequencies = self.get_frequencies(
                    fft_data['starting_frequency'],
                    fft_data['frequency_step'],
                    len(fft_data['diff_amplitudes'])
                  )
    amplitudes = self.get_amplitudes(
                   fft_data['min_amplitude'],
                   fft_data['diff_amplitudes'],
                   fft_data['amplitude_step']
                 )
    timestamp = (fft_data['week'], fft_data['TOW'])

    if len(self.data[timestamp]['frequencies']) == 0:
      self.data[timestamp]['frequencies'] = frequencies
      self.data[timestamp]['amplitudes'] = amplitudes
    elif frequencies[-1] < self.data[timestamp]['frequencies'][0]:
      self.data[timestamp]['frequencies'] = frequencies + self.data[timestamp]['frequencies']
      self.data[timestamp['amplitudes']] = amplitudes + self.data[timestamp]['amplitudes']
    elif self.data[timestamp]['frequencies'][-1] < frequencies[0]:
      self.data[timestamp]['frequencies'].extend(frequencies)
      self.data[timestamp]['amplitudes'].extend(amplitudes)
    else:
      insert_index = 0
      for i,freq in enumerate(self.data[timestamp]['frequencies']):
        if frequencies[0] > freq:
          insert_index = i
          break
      self.data[timestamp]['frequencies'][insert_index:insert_index] = frequencies
      self.data[timestamp]['amplitudes'][insert_index:insert_index] = amplitudes

    GUI.invoke_later(self.update_plot)

  def update_plot(self):
    raise NotImplementedError

  def __init__(self, link):
    super(SpectrumAnalyzerView, self).__init__()
    # dictionary of (week, TOW) to list of {'frequencies', 'amplitudes'}
    self.data = defaultdict(lambda: {'frequencies': [], 'amplitudes': []})
    self.link = link
    self.link.add_callback(self.spectrum_analyzer_state_callback, SBP_MSG_USER_DATA)
    self.python_console_cmds = {
      'spectrum': self
    }
