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

import requests
import json
import numbers

class SettingsReport():

    def __init__(self, settings):
        self._settings = settings

    def report_settings(self):
        try:
            post_data(str(self._settings['system_info']['uuid']),
                      json.dumps(dict_values_to_strings(self._settings)))
        except:
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
        print("post data: uuid is not a string")
        return
    # Check data is json.
    try:
        json.loads(data)
    except:
        print("post data: data is not valid json")
        return

    data_post = uuid, data
    r = requests.post('https://catchconsole.swiftnav.com/prof/catchConsole',
                       headers={'content-type': 'application/json', 'x-amz-docs-region': 'us-east-1'},
                       data=json.dumps(data_post))

    if r.status_code != requests.codes.ok:
        print("post data: failed to post data, code:", r.status_code)

