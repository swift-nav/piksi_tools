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

if __name__ == '__main__':
  from sbp.msg import SBP
  import base64
  # the TOW and week fields in these are dummy values
  json1 = {"data": {"sender": 37402, "msg_type": 2048, "crc": 53040, "length": 252, "preamble": 85, "payload": "AQC9vk8CZahEQAAAm563TvOKvUdkJShC+1a2PQAKBgYKDAoMCQcGCwgHCAgJCwcGCAsKCQYHCAcECAsICQ0IBwUMCAkLCwUIDAUFCQgJBgoICg0LCwcKCAkJCwUKDAwICgkIBwkMCgsIAgoMCwoKCAYHCQYKDAsLDAoNDg8IDg4NDg4OCwgIDQwQEAwRDxAOEhUQEg8SFBUWFREoKy4kFRUVGhQYHRsbHBoeHB0kICMlJiQqIycrIS1ESjgxQzMyMy4wMDg2PExRc7K1sYZYWEFQSFRMQDo+OT09P0NARkFCSElHSUpIS1BNTlFRT01QUlZLVFFXVVFTUVVT", "contents": [1, 0, 189, 190, 79, 2, 101, 168, 68, 64, 0, 0, 155, 158, 183, 78, 243, 138, 189, 71, 100, 37, 40, 66, 251, 86, 182, 61, 0, 10, 6, 6, 10, 12, 10, 12, 9, 7, 6, 11, 8, 7, 8, 8, 9, 11, 7, 6, 8, 11, 10, 9, 6, 7, 8, 7, 4, 8, 11, 8, 9, 13, 8, 7, 5, 12, 8, 9, 11, 11, 5, 8, 12, 5, 5, 9, 8, 9, 6, 10, 8, 10, 13, 11, 11, 7, 10, 8, 9, 9, 11, 5, 10, 12, 12, 8, 10, 9, 8, 7, 9, 12, 10, 11, 8, 2, 10, 12, 11, 10, 10, 8, 6, 7, 9, 6, 10, 12, 11, 11, 12, 10, 13, 14, 15, 8, 14, 14, 13, 14, 14, 14, 11, 8, 8, 13, 12, 16, 16, 12, 17, 15, 16, 14, 18, 21, 16, 18, 15, 18, 20, 21, 22, 21, 17, 40, 43, 46, 36, 21, 21, 21, 26, 20, 24, 29, 27, 27, 28, 26, 30, 28, 29, 36, 32, 35, 37, 38, 36, 42, 35, 39, 43, 33, 45, 68, 74, 56, 49, 67, 51, 50, 51, 46, 48, 48, 56, 54, 60, 76, 81, 115, 178, 181, 177, 134, 88, 88, 65, 80, 72, 84, 76, 64, 58, 62, 57, 61, 61, 63, 67, 64, 70, 65, 66, 72, 73, 71, 73, 74, 72, 75, 80, 77, 78, 81, 81, 79, 77, 80, 82, 86, 75, 84, 81, 87, 85, 81, 83, 81, 85, 83]}, "session-uid": "d2ee7267-6815-499f-84a4-ca03a268353c", "time": "2017-02-22T22:19:53.952000"}
  json2 = {"data": {"sender": 37402, "msg_type": 2048, "crc": 31053, "length": 252, "preamble": 85, "payload": "AQC9vk8CZahEQAAAkaG3TvOKvUdkJShC+1a2PVJWU1dTUFNUW1tZV1hZWlZWWlxXWlpYWltaXFtdV2BiYl9hXWJhZGRfY2dlaWhpaW1ua3Bxb3BxbnBubHNyb3Rzd3F7dnt4fHx8ent5fnuAfXuBf3t/foB9fX5/fH59fH1/f3+AgoCAg4SEgYGGg4SGgoKHg6iGhIeJiouLi4+MkZWal5+fnqGqpqeho56cmZOSjomIhIeCgYJ8f4KAfX95fH2BgoOBhoKAgoWDfIOAf4Z+goSGgoGJhYGDiIaFg4OJhoSCg4eGhYiBhoSBgoCAhIF9gn+BgIJ/gHl9fIB+", "contents": [1, 0, 189, 190, 79, 2, 101, 168, 68, 64, 0, 0, 145, 161, 183, 78, 243, 138, 189, 71, 100, 37, 40, 66, 251, 86, 182, 61, 82, 86, 83, 87, 83, 80, 83, 84, 91, 91, 89, 87, 88, 89, 90, 86, 86, 90, 92, 87, 90, 90, 88, 90, 91, 90, 92, 91, 93, 87, 96, 98, 98, 95, 97, 93, 98, 97, 100, 100, 95, 99, 103, 101, 105, 104, 105, 105, 109, 110, 107, 112, 113, 111, 112, 113, 110, 112, 110, 108, 115, 114, 111, 116, 115, 119, 113, 123, 118, 123, 120, 124, 124, 124, 122, 123, 121, 126, 123, 128, 125, 123, 129, 127, 123, 127, 126, 128, 125, 125, 126, 127, 124, 126, 125, 124, 125, 127, 127, 127, 128, 130, 128, 128, 131, 132, 132, 129, 129, 134, 131, 132, 134, 130, 130, 135, 131, 168, 134, 132, 135, 137, 138, 139, 139, 139, 143, 140, 145, 149, 154, 151, 159, 159, 158, 161, 170, 166, 167, 161, 163, 158, 156, 153, 147, 146, 142, 137, 136, 132, 135, 130, 129, 130, 124, 127, 130, 128, 125, 127, 121, 124, 125, 129, 130, 131, 129, 134, 130, 128, 130, 133, 131, 124, 131, 128, 127, 134, 126, 130, 132, 134, 130, 129, 137, 133, 129, 131, 136, 134, 133, 131, 131, 137, 134, 132, 130, 131, 135, 134, 133, 136, 129, 134, 132, 129, 130, 128, 128, 132, 129, 125, 130, 127, 129, 128, 130, 127, 128, 121, 125, 124, 128, 126]}, "session-uid": "d2ee7267-6815-499f-84a4-ca03a268353c", "time": "2017-02-22T22:19:53.955000"}
  json3 = {"data": {"sender": 37402, "msg_type": 2048, "crc": 61602, "length": 92, "preamble": 85, "payload": "AQC9vk8CZahEQAAAh6S3TvOKvUdkJShC+1a2PYCBfYGCg3+CgoCDhYeBhYWCgoKHhIKQiImKiYmJiYqLiYqHjImOkZONkJGTl5SXl56epampsrm7w8zW5ubx//U=", "contents": [1, 0, 189, 190, 79, 2, 101, 168, 68, 64, 0, 0, 135, 164, 183, 78, 243, 138, 189, 71, 100, 37, 40, 66, 251, 86, 182, 61, 128, 129, 125, 129, 130, 131, 127, 130, 130, 128, 131, 133, 135, 129, 133, 133, 130, 130, 130, 135, 132, 130, 144, 136, 137, 138, 137, 137, 137, 137, 138, 139, 137, 138, 135, 140, 137, 142, 145, 147, 141, 144, 145, 147, 151, 148, 151, 151, 158, 158, 165, 169, 169, 178, 185, 187, 195, 204, 214, 230, 230, 241, 255, 245]}, "session-uid": "d2ee7267-6815-499f-84a4-ca03a268353c", "time": "2017-02-22T22:19:53.955000"}
  msg1 = base64.standard_b64decode(json1['data']['payload'])
  msg2 = base64.standard_b64decode(json2['data']['payload'])
  msg3 = base64.standard_b64decode(json3['data']['payload'])
  from pprint import pprint as pp
  print ''
  pp(parse_payload(msg1))
  print ''
  pp(parse_payload(msg2))
  print ''
  pp(parse_payload(msg3))
