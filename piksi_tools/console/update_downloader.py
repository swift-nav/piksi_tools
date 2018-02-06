#!/usr/bin/env python
# Copyright (C) 2014 Swift Navigation Inc.
# Contact: Colin Beighley <colin@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

import os
import requests
from urlparse import urlparse

from piksi_tools.utils import sopen
from piksi_tools.console.utils import swift_path
INDEX_URL = 'https://s3-us-west-1.amazonaws.com/downloads.swiftnav.com/index_https.json'


class UpdateDownloader:
    def __init__(self, root_dir=swift_path):
        try:
            f = requests.get(INDEX_URL)
            self.index = f.json()
            f.raise_for_status()
            self.root_dir = root_dir
            f.close()
        except requests.ConnectionError as ce:
            self.index = None
            raise RuntimeError("Unable to download index from {0}.".format(INDEX_URL))
            return

    def set_root_path(self, path):
        self.root_dir = path

    def download_stm_firmware(self, hwrev):
        try:
            url = self.index[hwrev]['stm_fw']['url']
            filepath = self._download_file_from_url(url)
        except KeyError:
            raise KeyError(
                "Error downloading firmware: URL not present in index")
        return filepath

    def download_nap_firmware(self, hwrev):
        try:
            url = self.index[hwrev]['nap_fw']['url']
            filepath = self._download_file_from_url(url)
        except KeyError:
            raise KeyError(
                "Error downloading firmware: URL not present in index")
        return filepath

    def download_multi_firmware(self, hwrev):
        try:
            url = self.index[hwrev]['fw']['url']
            filepath = self._download_file_from_url(url)
        except KeyError:
            raise KeyError(
                "Error downloading firmware: URL not present in index")
        return filepath

    def _download_file_from_url(self, url):
        if not os.path.exists(self.root_dir):
            raise RuntimeError("Path to download file {0} to does not exist.".format(self.root_dir))
            return
        filename = os.path.split(urlparse(url).path)[1]
        filename = os.path.join(self.root_dir, filename)
        requests_response = requests.get(url)
        requests_response.raise_for_status()
        blob = requests_response.content
        with sopen(filename, 'wb') as f:
            f.write(blob)
        return os.path.abspath(filename)
