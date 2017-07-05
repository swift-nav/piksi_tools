#!/usr/bin/env python
# Copyright (C) 2015 Swift Navigation Inc.
# Contact: Bhaskar Mookerji <mookerji@swiftnav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

import pytest

import piksi_tools.diagnostics as d


def test_diag_check():
    details = 'tests/data/device_details.yaml'
    version = 'fw: v0.17-27-ge2c1aac\nhdl: v0.13-rc0\n'
    assert d.check_diagnostics(details, version)
    version = 'fw: v0.17-27-deadbeef\nhdl: v0.13-rc0\n'
    assert not d.check_diagnostics(details, version)
    version = 'fw: v0.17-27-ge2c1aac\nhdl: v0.13-defecated\n'
    assert not d.check_diagnostics(details, version)
    with pytest.raises(Exception):
        assert not d.check_diagnostics(details, None)
