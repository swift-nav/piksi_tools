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

import piksi_tools.diagnostics as d


def get_args():
  import argparse
  parser = argparse.ArgumentParser(description='Check Piksi firmware versions')
  parser.add_argument("-d",
                      "--diagnostics-filename",
                      nargs=1,
                      help="Settings YAML file")
  parser.add_argument("-v",
                      "--version-filename",
                      nargs=1,
                      help="Name of git describe VERSION file")
  return parser.parse_args()


def main():
  import os, sys
  args = get_args()
  diagnostics_filename = args.diagnostics_filename[0]
  assert os.path.exists(diagnostics_filename), \
    "Your hovercraft is full of fail, %s does not exist!" % diagnostics_filename
  version_filename = args.version_filename[0]
  assert os.path.exists(version_filename), \
    "Your hovercraft is full of fail, %s does not exist!" % version_filename
  version = open(version_filename, 'r+').read()
  if not d.check_diagnostics(diagnostics_filename, version):
    sys.exit(1)

if __name__ == "__main__":
  main()
