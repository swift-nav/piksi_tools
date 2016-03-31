#!/usr/bin/env python
# Copyright (C) 2011-2014 Swift Navigation Inc.
# Contact: Fergus Noble <fergus@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.


# Auto-generate the simulation_data.c file from a given almanac.
#   Written by Niels Joubert
#   April 2014

from almanac import *


import argparse

def to_struct(sat):
  return "{ \n\
  .kepler = { \n\
    .ecc       = %f,\n\
    .inc       = %f,\n\
    .omegadot  = %f,\n\
    .sqrta     = %f,\n\
    .omega0    = %f,\n\
    .w         = %f,\n\
    .m0        = %f,\n\
    .af0       = %f,\n\
    .af1       = %f,\n\
  },\n\
  .sid = { \n\
    .code = %d,\n\
    .sat = %d\n\
  },\n\
  .toa = {\n\
    .wn = %d,\n\
    .tow = %f\n\
  },\n\
  .ura = %f,\n\
  .fit_interval = %d,\n\
  .healthy   = %d,\n\
  .valid     = %d,\n\
}" % (sat.ecc,
  sat.inc,
  sat.omegadot,
  sat.sqrta,
  sat.omega0,
  sat.w,
  sat.m0,
  sat.af0,
  sat.af1,
  0, # CODE_GPS_L1CA
  sat.prn,
  sat.week,
  sat.toa,
  900.0,
  144,
  sat.healthy,
  1);

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description='Swift Nav Almanac C Generator')
  parser.add_argument("file",
    help="the almanac file to process into C structs")

  args = parser.parse_args();

  alm = Almanac()
  with open(args.file) as f:
    alm.process_yuma(f.readlines())
    print "#include \"simulator_data.h\""
    print "/* AUTO-GENERATED FROM simulator_almanac_generator.py */\n"
    print "u16 simulation_week_number = 866;\n"
    print "double simulation_sats_pos[%d][3];\n" % len(alm.sats)
    print "double simulation_sats_vel[%d][3];\n" % len(alm.sats)
    print "u32 simulation_fake_carrier_bias[%d];\n" % len(alm.sats)
    print "u8 simulation_num_almanacs = %d;\n" % len(alm.sats)
    print "const almanac_t simulation_almanacs[%d] = {" % len(alm.sats)
    for s in alm.sats:
      print "%s," % to_struct(s)
    print "};"
