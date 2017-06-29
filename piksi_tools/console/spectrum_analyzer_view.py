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
from chaco.api import ArrayPlotData, Plot
from enable.api import ComponentEditor
from pyface.api import GUI
from sbp.piksi import SBP_MSG_SPECAN, MsgSpecan
from traits.api import Dict, HasTraits, Instance, Str
from traitsui.api import CheckListEditor, Item, View

# How many points are in each FFT?
NUM_POINTS = 512


class GpsTime():
    def __init__(self, week, TOW):
        self.TOW = TOW
        self.week = week

    # these are probably not the most robust implementations

    def __cmp__(self, other):
        if other is None:
            return 1
        if self.week < other.week:
            return -1
        elif self.week > other.week:
            return 1
        else:
            if self.TOW < other.TOW:
                return -1
            elif self.TOW > other.TOW:
                return 1
            else:
                return 0

    def __eq__(self, other):
        if type(other) != type(GpsTime(1, 1)):
            return False
        return (self.week == other.week) and (self.TOW == other.TOW)

    def __repr__(self):
        return '(week: {0}, TOW: {1})'.format(self.week, self.TOW)

    def __hash__(self):
        return (self.week, self.TOW).__hash__()


class SpectrumAnalyzerView(HasTraits):
    python_console_cmds = Dict()
    plot = Instance(Plot)
    plot_data = Instance(ArrayPlotData)
    which_plot = Str("Channel 1")
    traits_view = View(
        Item(
            'plot',
            editor=ComponentEditor(bgcolor=(0.8, 0.8, 0.8)),
            show_label=False),
        Item(
            name='which_plot',
            show_label=False,
            editor=CheckListEditor(
                values=["Channel 1", "Channel 2", "Channel 3", "Channel 4"])))

    def parse_payload(self, raw_payload):
        """
        Params
        ======
        payload: is an array of ints representing bytes from the SBP_MSG_USER_DATA message 'contents'

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
        # Turn the array of ints representing uint8 bytes back to binary, so you can use struct
        # formatting to unpack it. Otherwise you would have to manually parse each byte.
        pack_fmt_str = 'B' * len(raw_payload)
        payload = struct.pack(pack_fmt_str, *raw_payload)
        payload_header_fmt_str = '<Hdhffff'
        payload_header_bytes = struct.calcsize(payload_header_fmt_str)
        diff_amplitude_n = (len(raw_payload) - payload_header_bytes)
        diff_amplitude_fmt_str = 'B' * diff_amplitude_n
        fmt_str = payload_header_fmt_str + diff_amplitude_fmt_str
        parsed_payload = struct.unpack(fmt_str, payload)
        fft_msg_header = [
            'user_msg_tag', 'TOW', 'week', 'starting_frequency',
            'frequency_step', 'min_amplitude', 'amplitude_step'
        ]
        payload_json = dict(
            zip(fft_msg_header, parsed_payload[:len(fft_msg_header)]))
        fft_msg_payload = parsed_payload[len(fft_msg_header):]
        payload_json['diff_amplitudes'] = fft_msg_payload
        return payload_json

    def get_frequencies(self, start_freq, freq_step, n):
        '''
        start_freq: float (Hz)
        freq_step: float (Hz)
        n: int
        '''
        return np.array([start_freq + freq_step * i for i in range(n)])

    def get_amplitudes(self, min_amplitude, diffs, unit):
        '''
        min_amplitude: float (dB)
        diffs: tuple of floats (dB)
        unit: float (dB)
        '''
        return np.array([min_amplitude + diff * unit for diff in diffs])

    def spectrum_analyzer_state_callback(self, sbp_msg, **metadata):
        '''
        Params
        ======
        sbp_msg: sbp.msg.SBP object

        Updates the view's data for use in self.update_plot
        '''
        # Need to figure out which user_msg_tag means it's an FFT message
        # for now assume that all SBP_MSG_USER_DATA is relevant
        fft = MsgSpecan(sbp_msg)
        frequencies = self.get_frequencies(fft.freq_ref, fft.freq_step,
                                           len(fft.amplitude_value))
        amplitudes = self.get_amplitudes(
            fft.amplitude_ref, fft.amplitude_value, fft.amplitude_unit)

        tag = fft.channel_tag
        if (tag == 1 and self.which_plot != "Channel 1"):
            return
        if (tag == 2 and self.which_plot != "Channel 2"):
            return
        if (tag == 3 and self.which_plot != "Channel 3"):
            return
        if (tag == 4 and self.which_plot != "Channel 4"):
            return
        timestamp = GpsTime(fft.t.wn, fft.t.tow)
        if len(self.incomplete_data[timestamp]['frequencies']) + len(
                frequencies) == NUM_POINTS:
            self.most_recent_complete_data['frequencies'] = np.append(
                self.incomplete_data[timestamp]['frequencies'],
                frequencies,
                axis=0)
            self.most_recent_complete_data['amplitudes'] = np.append(
                self.incomplete_data[timestamp]['amplitudes'],
                amplitudes,
                axis=0)
            self.incomplete_data.pop(timestamp)
            if timestamp is None or timestamp > self.most_recent:
                self.most_recent = timestamp
            GUI.invoke_later(self.update_plot)
        else:
            self.incomplete_data[timestamp]['frequencies'] = np.append(
                self.incomplete_data[timestamp]['frequencies'],
                frequencies,
                axis=0)
            self.incomplete_data[timestamp]['amplitudes'] = np.append(
                self.incomplete_data[timestamp]['amplitudes'],
                amplitudes,
                axis=0)

    def update_plot(self):
        most_recent_fft = self.most_recent_complete_data
        if len(most_recent_fft['frequencies']) != 0:
            self.plot_data.set_data('frequency',
                                    most_recent_fft['frequencies'])
            self.plot_data.set_data('amplitude', most_recent_fft['amplitudes'])
            self.plot.value_mapper.range.low = min(
                most_recent_fft['amplitudes'])
            self.plot.value_mapper.range.high = max(
                most_recent_fft['amplitudes'])

    def __init__(self, link):
        super(SpectrumAnalyzerView, self).__init__()
        self.link = link
        self.link.add_callback(self.spectrum_analyzer_state_callback,
                               SBP_MSG_SPECAN)
        self.python_console_cmds = {'spectrum': self}

        # keys are GpsTime
        self.incomplete_data = defaultdict(
            lambda: {'frequencies': np.array([]), 'amplitudes': np.array([])})
        self.most_recent_complete_data = {
            'frequencies': np.array([]),
            'amplitudes': np.array([])
        }
        self.most_recent = None

        self.plot_data = ArrayPlotData()
        self.plot = Plot(self.plot_data, emphasized=True)

        self.plot.title = 'Spectrum Analyzer'
        self.plot.title_color = [0, 0, 0.43]

        self.plot.value_axis.orientation = 'right'
        self.plot.value_axis.title = 'Amplitude (dB)'

        self.plot.index_axis.title = 'Frequency (MHz)'
        self.plot_data.set_data('frequency', [0])
        self.plot_data.set_data('amplitude', [0])
        self.plot.plot(
            ('frequency', 'amplitude'), type='line', name='spectrum')
