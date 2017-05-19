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

from urllib2 import urlopen, URLError
from json import load as jsonload
from urlparse import urlparse
import os

from piksi_tools.utils import sopen

INDEX_URL = 'http://downloads.swiftnav.com/index.json'

class UpdateDownloader:

  def __init__(self, root_dir=''):
    f = urlopen(INDEX_URL)
    self.index = jsonload(f)
    self.root_dir = root_dir
    f.close()

  def set_root_path(self, path):
    self.root_dir = path

  def download_stm_firmware(self, hwrev):
    try:
      url = self.index[hwrev]['stm_fw']['url']
      filepath = self._download_file_from_url(url)
    except KeyError:
      raise KeyError("Error downloading firmware: URL not present in index")
    except URLError:
      raise URLError("Error: Failed to download latest STM firmware from Swift Navigation's website")
    return filepath

  def download_nap_firmware(self, hwrev):
    try:
      url = self.index[hwrev]['nap_fw']['url']
      filepath = self._download_file_from_url(url)
    except KeyError:
      raise KeyError("Error downloading firmware: URL not present in index")
    except URLError:
      raise URLError("Error: Failed to download latest NAP firmware from Swift Navigation's website")
    return filepath

  def download_multi_firmware(self, hwrev):
    try:
      url = self.index[hwrev]['fw']['url']
      filepath = self._download_file_from_url(url)
    except KeyError:
      raise KeyError("Error downloading firmware: URL not present in index")
    except URLError:
      raise URLError("Error: Failed to download latest Multi firmware from Swift Navigation's website")
    return filepath

  def _download_file_from_url(self, url):
    if not os.path.isdir(self.root_dir):
      raise IOError("Path to download file to does not exist")

    url = url.encode('ascii')
    urlpath = urlparse(url).path
    filename = os.path.split(urlparse(url).path)[1]
    filename = os.path.join(self.root_dir, filename)
    url_file = urlopen(url)
    blob = url_file.read()
    with sopen(filename, 'wb') as f:
      f.write(blob)
    url_file.close()

    return os.path.abspath(filename)
