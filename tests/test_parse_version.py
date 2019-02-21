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

from piksi_tools.console.GitVersion import parse as parse_version
from piksi_tools.console.GitVersion import InvalidVersion

# input, marketing, major, minor, devstring, is_dev
expected_success = [
    ["v2.1.0", 2, 1, 0, "v", False],
    ["v2.2.17-develop", 2, 2, 17, "v-develop", True],
    ["v99.99.99-arbitrary-string", 99, 99, 99, "v-arbitrary-string", True],
    ["v1.1.1 including some spaces", 1, 1, 1, "v including some spaces", True],
    ["PiksiMulti-2.0.0.bin", 2, 0, 0, "PiksiMulti-.bin", True],
    ["    v2.0.0", 2, 0, 0, "v", False],
    ["1.2.3.4", 1, 2, 3, ".4", True]
]

expected_fail = [
    None,
    "",
    "alirjaliefjasef",
    "              ",
    "v.2.0.0",
    "asdf1234fdsa-v1.2.3"
]

expected_eq = [
    ["1.1.1", "1.1.1", True],
    ["1.1.1", "2.2.2", False],
    ["2.2.2", "1.1.1", False],
    ["2.2.2", "2.2.2", True]
]

expected_neq = [
    ["1.1.1", "1.1.1", False],
    ["1.1.1", "2.2.2", True],
    ["2.2.2", "1.1.1", True],
    ["2.2.2", "2.2.2", False]
]

expected_lt = [
    ["1.1.1", "1.1.1", False],
    ["1.1.1", "2.2.2", True],
    ["2.2.2", "1.1.1", False],
    ["2.2.2", "2.2.2", False]
]
expected_le = [
    ["1.1.1", "1.1.1", True],
    ["1.1.1", "2.2.2", True],
    ["2.2.2", "1.1.1", False],
    ["2.2.2", "2.2.2", True]
]
expected_gt = [
    ["1.1.1", "1.1.1", False],
    ["1.1.1", "2.2.2", False],
    ["2.2.2", "1.1.1", True],
    ["2.2.2", "2.2.2", False]
]
expected_ge = [
    ["1.1.1", "1.1.1", True],
    ["1.1.1", "2.2.2", False],
    ["2.2.2", "1.1.1", True],
    ["2.2.2", "2.2.2", True]
]


def test_version_parser():
    for each in expected_success:
        ver = None
        raised = False

        try:
            ver = parse_version(each[0])
        except InvalidVersion:
            raised = True

        assert(raised is False)
        assert(ver.marketing == each[1])
        assert(ver.major == each[2])
        assert(ver.minor == each[3])
        assert(ver.devstring == each[4])
        assert(ver.isdev == each[5])

    for each in expected_fail:
        ver = None
        raised = False

        try:
            ver = parse_version(each[0])
        except InvalidVersion:
            raised = True

        assert(raised is True)

    for each in expected_eq:
        v1 = parse_version(each[0])
        v2 = parse_version(each[1])
        result = (v1 == v2)
        assert result is each[2], "{0} == {1}".format(each[0], each[1])

    for each in expected_neq:
        v1 = parse_version(each[0])
        v2 = parse_version(each[1])
        result = (v1 != v2)
        assert result is each[2], "{0} != {1}".format(each[0], each[1])

    for each in expected_lt:
        v1 = parse_version(each[0])
        v2 = parse_version(each[1])
        result = (v1 < v2)
        assert result is each[2], "{0} < {1}".format(each[0], each[1])

    for each in expected_le:
        v1 = parse_version(each[0])
        v2 = parse_version(each[1])
        result = (v1 <= v2)
        assert result is each[2], "{0} <= {1}".format(each[0], each[1])

    for each in expected_gt:
        v1 = parse_version(each[0])
        v2 = parse_version(each[1])
        result = (v1 > v2)
        assert result is each[2], "{0} > {1}".format(each[0], each[1])

    for each in expected_ge:
        v1 = parse_version(each[0])
        v2 = parse_version(each[1])
        result = (v1 >= v2)
        assert result is each[2], "{0} >= {1}".format(each[0], each[1])
