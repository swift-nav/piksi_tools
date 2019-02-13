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

from piksi_tools.utils import parse_version

             #[expected greater, expected lesser]
test_sort = [['v1.0.0','vtest'],
             ['v2.3.4', 'v1.0.0'],
             ['1.0.0', 'v0.9.9'],
             ['v1.0', 'v0.9'],
             ['1.0', '0.9'],
             ['v1.0', '0.9'],
             ['v1.0', '0.9.9'],
             ['v1.0+1234', '0.9.9'],
             ['PiksiMulti-v2.0.0', 'PiksiMulit-v1.5.0'],
             ['PiksiMulti-v2.0.0-teststring', 'PiksiMulti-v1.5.0'],
             ['PiksiMulti-v2.0.0-teststring', 'PiksiMulti-v1.5.0-teststring'],
             ['PiksiMulti-v2.0.0teststring', 'PiksiMulti-v1.5.0'],
             ['PiksiMulti-v2.0.0+teststring', 'PiksiMulti-v1.5.0'],
             ['PiksiMulti-v2.0.0+teststring', 'PiksiMulti-v1.5.0'],
             ['PiksiMulti-v2.1.0-develop-2019020822', 'PiksiMulti-v1.5.0'],
             ['v2.1.0-develop-2019020822', 'PiksiMulti-v1.5.0'],
             ['v2.1.0-develop-2019020822', 'PiksiMulti-v2.1.0'],
             ['PiksiMulti-v2.1.0', 'PiksiMulti-v2.0.0-develop-2019'],
             ['v2.1.0-develop-2019020822', 'PiksiMulti-v2.1.0'],
             ['v2.1.0+2019020822', 'PiksiMulti-v1.5.0+test']]


test_equal = [['v1.0.0','v1.0.0'],
             ['2.3.4', 'v2.3.4'],
             ['v1.0', '1.0'],
             ['PiksiMulti-v2.0.0', 'TESTBUILD-v2.0.0'],
             ['v2.1.0-develop-2019020822', 'v2.1.0-develop-2019020822']]

test_noteq = [['v2.1.0-develop-2019020823', 'v2.1.0-develop-2019020822'],
              ['TEST-v2.3.0-piksi_ins-5', 'TEST-v2.3.0-piksi_ins-6']]

def test_bogus_versions():
    v1 = parse_version("vtestdenns")
    v2 = parse_version("v1.0.0")
    print("version 1 is {0}".format(v1))
    print("version 2 is {0}".format(v2))
    assert(v1 < v2)


def test_greater_than_versions():
    for each in test_sort:
        greater = each[0]
        less = each[1]
        v1 = parse_version(greater)
        v2 = parse_version(less)
        assert v1 > v2, "{} was not greater than {}".format(greater, less)

    
def test_versions_equal():
    for each in test_equal:
        v1 = parse_version(each[0])
        v2 = parse_version(each[1])
        assert v1 == v2, "{} was not equal to {}".format(each[0], each[1])

def test_versions_unequal():
    for each in test_noteq:
        v1 = parse_version(each[0])
        v2 = parse_version(each[1])
        assert v1 != v2, "{} was equal to {}".format(each[0], each[1])
