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

import piksi_tools.console.update_downloader as ud 
import glob 
import os

def test_update_downloader():
    paths = glob.glob("/tmp/PiksiMulti*.bin")
    for each in paths:
        os.remove(each)
    a = ud.UpdateDownloader('/tmp/')
    a.download_multi_firmware("piksi_multi")
    paths = glob.glob("/tmp/PiksiMulti*.bin")
    assert len(paths) == 1
    for each in paths:
        os.remove(each)
    a._download_file_from_url("https://www.swiftnav.com/resource-files/Piksi%20Multi/v1.2.14/Firmware/PiksiMulti-v1.2.14.bin")
    paths = glob.glob("/tmp/PiksiMulti*.bin")
    assert len(paths) == 1
    for each in paths:
        os.remove(each)
