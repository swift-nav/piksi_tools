#!/usr/bin/env python
# Copyright (C) 2011-2014, 2016 Swift Navigation Inc.
# Contact: Fergus Noble <fergus@swift-nav.com>
#          Pasi Miettinen <pasi.miettinen@exafore.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

from traits.api import Dict, HasTraits, List, Bool, Str
from traitsui.api import Item, View, HGroup, VGroup, TabularEditor
from traitsui.tabular_adapter import TabularAdapter
from enable.savage.trait_defs.ui.svg_button import SVGButton
from piksi_tools.console.utils import determine_path
from piksi_tools.console.utils import code_to_str
from piksi_tools.console.utils import L1CA

import os
import datetime
import copy

from sbp.observation import *


class SimpleAdapter(TabularAdapter):
    columns = [('PRN', 0),
               ('Pseudorange (m)', 1),
               ('Carrier Phase (cycles)', 2),
               ('C/N0 (db-hz)', 3),
               ('Doppler (hz)', 4)]


class ObservationView(HasTraits):
  python_console_cmds = Dict()

  _obs_table_list = List()
  obs = Dict()

  name = Str('Local')

  recording = Bool(False)

  record_button = SVGButton(
    label='Record', tooltip='Record Raw Observations',
    toggle_tooltip='Stop Recording', toggle=True,
    filename=os.path.join(determine_path(),
                          'images', 'fontawesome', 'floppy-o.svg'),
    toggle_filename=os.path.join(determine_path(),
                                 'images', 'fontawesome', 'stop.svg'),
    width=16, height=16
  )

  def trait_view(self, view):
    return View(
      HGroup(
        Item('_obs_table_list', style='readonly',
             editor=TabularEditor(adapter=SimpleAdapter()), show_label=False),
        VGroup(
          Item('record_button', show_label=False),
        ),
        label=self.name,
        show_border=True
      )
    )

  def _record_button_fired(self):
    self.recording = not self.recording
    if not self.recording:
      if self.rinex_file is not None:
        self.rinex_file.close()
      self.rinex_file = None

  def rinex_save(self):
    if self.recording:
      if self.rinex_file is None:
        # If the file is being opened for the first time, write the RINEX header
        self.rinex_file = open(self.name + self.t.strftime(
                               "-%Y%m%d-%H%M%S.obs"), 'w')
        header = '     ' +\
"""2.11           OBSERVATION DATA    G (GPS)             RINEX VERSION / TYPE
pyNEX                                   %s UTC PGM / RUN BY / DATE
                                                            MARKER NAME
                                                            OBSERVER / AGENCY
                                                            REC # / TYPE / VERS
                                                            ANT # / TYPE
   808673.9171 -4086658.5368  4115497.9775                  APPROX POSITION XYZ
        0.0000        0.0000        0.0000                  ANTENNA: DELTA H/E/N
     1     0                                                WAVELENGTH FACT L1/2
     3    C1    L1    S1                                    # / TYPES OF OBSERV
%s%13.7f     GPS         TIME OF FIRST OBS
                                                            END OF HEADER
""" % (
            datetime.datetime.utcnow().strftime("%Y%m%d %H%M%S"),
            self.t.strftime("  %Y    %m    %d    %H    %M"),
                            self.t.second + self.t.microsecond * 1e-6)
        self.rinex_file.write(header)

      # L1CA only
      copy_prns = prns = [s for s in self.obs.iterkeys() if L1CA in s]
      self.rinex_file.write("%s %10.7f  0 %2d" %
                            (self.t.strftime(" %y %m %d %H %M"),
                             self.t.second + self.t.microsecond * 1e-6,
                             len(prns)))

      while len(copy_prns) > 0:
        prns_ = copy_prns[:12]
        copy_prns = copy_prns[12:]
        for prn in prns_:
          # take only the leading prn number
          self.rinex_file.write('G%2d' % (int(prn.split()[0])))
        self.rinex_file.write('   ' * (12 - len(prns_)))
        self.rinex_file.write('\n')

      for prn in prns:
        # G    3 C1C L1C D1C
        self.rinex_file.write("%14.3f  " % self.obs[prn][0])
        self.rinex_file.write("%14.3f  " % self.obs[prn][1])
        self.rinex_file.write("%14.3f  \n" % self.obs[prn][2])

      self.rinex_file.flush()

  def update_obs(self):
    self._obs_table_list =\
      [(prn,) + obs for prn, obs in sorted(self.obs.items(),
                                           key=lambda x: x[0])]

  def obs_packed_callback(self, sbp_msg, **metadata):
    if (sbp_msg.sender is not None and
        (self.relay ^ (sbp_msg.sender == 0))):
      return
    tow = sbp_msg.header.t.tow
    wn = sbp_msg.header.t.wn
    seq = sbp_msg.header.n_obs

    tow = float(tow) / 1000.0

    total = seq >> 4
    count = seq & ((1 << 4) - 1)

    # Confirm this packet is good.
    # Assumes no out-of-order packets
    if count == 0:
      self.old_tow = self.gps_tow
      self.gps_tow = tow
      self.gps_week = wn
      self.prev_obs_total = total
      self.prev_obs_count = 0
      self.old_obs = copy.deepcopy(self.obs)
      self.obs = {}
    elif self.gps_tow != tow or\
         self.gps_week != wn or\
         self.prev_obs_count + 1 != count or\
         self.prev_obs_total != total:
      print "We dropped a packet. Skipping this observation sequence"
      self.prev_obs_count = -1
      return
    else:
      self.prev_obs_count = count

    # Save this packet
    # See sbp_piksi.h for format
    for o in sbp_msg.obs:
      prn = o.sid.sat
      # compute time difference of carrier phase for display
      cp = float(o.L.i) + float(o.L.f) / (1 << 8)
      if o.sid.code == 0 or o.sid.code == 1:
        prn += 1
      prn = '{} ({})'.format(prn, code_to_str(o.sid.code))
      if sbp_msg.msg_type == SBP_MSG_OBS_DEP_A or\
         sbp_msg.msg_type == SBP_MSG_OBS_DEP_B:
        divisor = 1e2
      else:
        divisor = 5e1
      try:
        ocp = self.old_obs[prn][1]
      except:
        ocp = 0
      cf = (cp - ocp) / (self.gps_tow - self.old_tow)
      self.obs[prn] = (float(o.P) / divisor,
                       float(o.L.i) + float(o.L.f) / (1 << 8),
                       float(o.cn0) / 4,
                       cf)
    if (count == total - 1):
      self.t = datetime.datetime(1980, 1, 6) + \
               datetime.timedelta(weeks=self.gps_week) + \
               datetime.timedelta(seconds=self.gps_tow)

      self.update_obs()
      self.rinex_save()

    return

  def ephemeris_callback(self, m, **metadata):
    prn = m.sid.sat
    if m.sid.code == 0 or m.sid.code == 1:
      prn += 1
    if self.recording:
      if self.eph_file is None:
        self.eph_file = open(self.name + self.t.strftime("-%Y%m%d-%H%M%S.eph"),
                             'w')
        header = "time, " \
               + "tgd, " \
               + "crs, crc, cuc, cus, cic, cis, " \
               + "dn, m0, ecc, sqrta, omega0, omegadot, w, inc, inc_dot, " \
               + "af0, af1, af2, " \
               + "toe_tow, toe_wn, toc_tow, toc_wn, " \
               + "valid, " \
               + "healthy, " \
               + "prn\n"
        self.eph_file.write(header)

      strout = "%s %10.7f" % (self.t.strftime(" %y %m %d %H %M"),
                              self.t.second + self.t.microsecond * 1e-6)
      strout += "," + str([m.tgd,
                           m.c_rs, m.c_rc, m.c_uc, m.c_us, m.c_ic, m.c_is,
                           m.dn, m.m0, m.ecc, m.sqrta, m.omega0, m.omegadot,
                           m.w, m.inc, m.inc_dot,
                           m.af0, m.af1, m.af2,
                           m.toe_tow, m.toe_wn, m.toc_tow, m.toc_wn,
                           m.valid,
                           m.healthy,
                           prn])[1: -1] + "\n"
      self.eph_file.write(strout)
      self.eph_file.flush()

  def __init__(self, link, name='Local', relay=False):
    super(ObservationView, self).__init__()
    self.obs_count = 0
    self.gps_tow = 0.0
    self.gps_week = 0
    self.relay = relay
    self.name = name
    self.rinex_file = None
    self.eph_file = None
    self.link = link
    self.link.add_callback(self.obs_packed_callback,
                           [SBP_MSG_OBS, SBP_MSG_OBS_DEP_B])
    self.link.add_callback(self.ephemeris_callback, SBP_MSG_EPHEMERIS)
    self.python_console_cmds = {'obs': self}
