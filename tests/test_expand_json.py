#!/usr/bin/env python
# Copyright (C) 2015 Swift Navigation Inc.
# Contact: Bhaskar Mookerj <mookerji@swiftnav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

from uuid import UUID

import piksi_tools.expand_json as e
import json

def test_unexploded():
    e.expand_json('./tests/data/unexploded_input.json', 'exploded_output.json')
    a = open('exploded_output.json')
    b = open('./tests/data/exploded_reference.json')
    for aj,bj in zip(a.readlines(), b.readlines()):
      astr = json.dumps(aj, sort_keys=True)
      bstr = json.dumps(bj, sort_keys=True)
      assert astr == bstr

def test_exploded():
    e.expand_json('./tests/data/exploded_reference.json', 'exploded_output_2.json')
    a = open('exploded_output_2.json')
    b = open('./tests/data/exploded_reference.json')
    for aj,bj in zip(a.readlines(), b.readlines()):
      astr = json.dumps(aj, sort_keys=True)
      bstr = json.dumps(bj, sort_keys=True)
      assert astr == bstr
