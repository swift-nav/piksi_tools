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

def post_data(uuid, data):
    if uuid and data:
        try:
            data_post = uuid, data
        except ValueError:
            print("post data: must enter a serialized JSON object in data param")
            return
    else:
        print("post data: uuid or data is empty")
        return

    r = requests.post('https://w096929iy3.execute-api.us-east-1.amazonaws.com/prof/catchConsole',
                       headers={'content-type': 'application/json', 'x-amz-docs-region': 'us-east-1'},
                       data=json.dumps(data_post))

    if r.status_code != requests.codes.ok:
        print("post data: failed to post data")

