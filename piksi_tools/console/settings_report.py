#!/usr/bin/env python
# Copyright (C) 2017 Swift Navigation Inc.
# Contact: Swift Navigation <dev@swiftnav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

import json
import numbers
import os.path
import requests
from threading import Thread
from time import sleep

import piksi_tools.console.callback_prompt as prompt
from piksi_tools.console.utils import swift_path

PERMISSION_FILEPATH = swift_path + '/permission.json'

class SettingsReport():

    def __init__(self, settings, debug=True):
        self._settings = settings
        self.debug = debug
        self.asked_permission_already = False

    def _write_permission_file(self):
        # Create permission file if it doesn't already exist.
        open(PERMISSION_FILEPATH, 'a').close()

    def _check_permission(self):
        return os.path.isfile(PERMISSION_FILEPATH)

    def _ask_permission(self):
        permission_prompt = prompt.CallbackPrompt(
            title="Share device usage data?",
            actions=[prompt.yes_button, prompt.no_button],
            callback=self._write_permission_file)
        permission_prompt.text = "\n" \
                                 + "    Click Yes to share device usage data with Swift Navigation.   \n" \
                                 + "                                                                  \n" \
                                 + "    Sharing device usage data helps us understand how customers   \n" \
                                 + "    are using our products in order to better serve your needs.   \n" \
                                 + "                                                                  \n" \
                                 + "    This will not send location data.                             \n"
        permission_prompt.run()
        self.asked_permission_already = True

    def run(self):
        try:
            if self._report_settings_thread.is_alive():
                return
        except AttributeError:
            pass

        self._report_settings_thread = Thread(target=self._report_settings)
        self._report_settings_thread.start()

    def _report_settings(self):
        permission = self._check_permission()
        if not permission and not self.asked_permission_already:
            self._ask_permission()

        # Ensure file has been written before reading.
        sleep(5)
        permission = self._check_permission()
        if permission:
            try:
                post_data(str(self._settings['system_info']['uuid']),
                          json.dumps(dict_values_to_strings(self._settings)))
            except Exception:
                if self.debug == True:
                    print("report settings: failed to report settings")
                pass

def dict_values_to_strings(d):
    '''
    Convert dict values to strings. Handle nesting. Meant to convert Traits
    objects.
    '''
    converted = {}
    for k,v in d.iteritems():
        # We assume the key is a string. If not, fail.
        if not isinstance(k, str):
            raise TypeError('key is not a string')
        if isinstance(v, dict):
            converted[k] = dict_values_to_strings(v)
        else:
            converted[k] = str(v)
        # Empty string has to be specially handled otherwise we get 502.
        if converted[k] == "":
            converted[k] = None
    return converted

def post_data(uuid, data):
    # Check UUID is a string
    if not isinstance(uuid, str):
        if self.debug == True:
            print("report settings: post data: uuid is not a string")
        return
    # Check data is json.
    try:
        json.loads(data)
    except Exception:
        if self.debug == True:
            print("report settings: post data: data is not valid json")
        return

    data_post = uuid, data
    r = requests.post('https://catchconsole.swiftnav.com/prof/catchConsole',
                       headers={'content-type': 'application/json', 'x-amz-docs-region': 'us-east-1'},
                       data=json.dumps(data_post))

    if r.status_code != requests.codes.ok:
        if self.debug == True:
            print("report settings: post data: failed to post data, code:", r.status_code)

