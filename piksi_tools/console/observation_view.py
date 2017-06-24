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

from traits.api import Dict, HasTraits, Instance, List, Float, Int
from traitsui.api import Item, View, HGroup, VGroup, TabularEditor, Spring, VSplit
from traitsui.tabular_adapter import TabularAdapter

from piksi_tools.console.gui_utils import CodeFiltered
from piksi_tools.console.utils import call_repeatedly, code_to_str, EMPTY_STR,\
                                      code_is_gps, SUPPORTED_CODES

import os
import datetime
import copy

from sbp.observation import *

class SimpleAdapter(TabularAdapter):
    columns = [('PRN', 0),
               ('Pseudorange (m)', 1),
               ('Carrier Phase (cycles)', 2),
               ('C/N0 (dB-Hz)', 3),
               ('Meas. Doppler (Hz)', 4),
               ('Comp. Doppler (Hz)', 5),
               ('Lock', 6),
               ('Flags', 7)]
    font='courier'
    alignment='center'


class ObsView(CodeFiltered):
  python_console_cmds = Dict()

  _obs_table_list = List()
  obs = Dict()
  old_cp = Dict()
  new_cp = Dict()
  old_tow = Float()
  gps_tow = Float()
  obs_count = Int()
  gps_week = Int()

  for code in SUPPORTED_CODES:
    vars()['count_{}'.format(code)] = Int()

  def trait_view(self, view):
    info = HGroup(
             Spring(width=4, springy=False),
             Item('',
                  label='Week:',
                  emphasized=True,
                  tooltip='GPS Week Number (since 1980'),
             Item('gps_week', style='readonly', show_label=False),
             Item('',
                  label='TOW:',
                  emphasized=True,
                  tooltip='GPS milliseconds in week'),
             Item('gps_tow',
                  style='readonly',
                  show_label=False,
                  format_str='%.3f'),
             Item('',
                  label='Total obs:',
                  emphasized=True,
                  tooltip='Total observation count'),
             Item('obs_count', style='readonly', show_label=False),
           )

    for code in SUPPORTED_CODES:
      code_str = code_to_str(code)
      info.content.append(Item('',
                               label='{}:'.format(code_str),
                               emphasized = True,
                               tooltip='{} observation count'.format(code_str)))
      info.content.append(Item('count_{}'.format(code),
                               style='readonly',
                               show_label=False))

    return View(
      VGroup(
        info,
        CodeFiltered.get_filter_group(),
        HGroup(
          Item('_obs_table_list', style='readonly',
               editor=TabularEditor(adapter=SimpleAdapter()), show_label=False),
        ),
        label=self.name,
        show_border=True
      )
    )

  def update_obs(self):
      if not self.parent._selected():
        return
      self._obs_table_list = [('{} ({})'.format(svid[0],
                                                code_to_str(svid[1])),) + obs
                              for svid, obs in sorted(self.obs.items()) 
                                if getattr(self, 'show_{}'.format(svid[1]))]

      for code in SUPPORTED_CODES:
        setattr(self,
                'count_{}'.format(code),
                len([key for key in self.obs.keys() if key[1] == code]))

  def obs_packed_callback(self, sbp_msg, **metadata):
    if not self.parent._selected():
        return

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
      self.old_cp = self.new_cp
      self.new_cp.clear()
      self.incoming_obs.clear()
    elif self.gps_tow != tow or\
         self.gps_week != wn or\
         self.prev_obs_count + 1 != count or\
         self.prev_obs_total != total:
      print "We dropped a packet. Skipping this observation sequence"
      self.prev_obs_count = -1
      return
    else:
      self.prev_obs_count = count

    # Old PRN values had to add one for GPS
    is_deprecated_abc =\
      sbp_msg.msg_type in [SBP_MSG_OBS_DEP_A,
                           SBP_MSG_OBS_DEP_B,
                           SBP_MSG_OBS_DEP_C]

    # DEP_B and DEP_A obs had different pseudorange scaling
    is_deprecated_ab =\
      sbp_msg.msg_type in [SBP_MSG_OBS_DEP_A, SBP_MSG_OBS_DEP_B]

    if is_deprecated_ab:
      divisor = 1e2
    else:
      divisor = 5e1

    prn = []
    code = []
    D_i = []
    D_f = []
    cp_i = []
    cp_f = []
    flags = []

    for o in sbp_msg.obs:
      prn.append(o.sid.sat)
      code.append(o.sid.code)
      cp_i.append(o.L.i)
      cp_f.append(o.L.f)

      if is_deprecated_abc:
        D_i.append(0)
        D_f.append(0)
        flags.append(0)
      else:
        D_i.append(o.D.i)
        D_f.append(o.D.f)
        flags.append(o.flags)

    prn = np.array(prn)
    code = np.array(code)
    if code_is_gps(o.sid.code) and is_deprecated_abc:
      prn += 1

    sids = zip(prn, code)

    D_i = np.array(D_i)
    D_f = np.array(D_f)

    msdopps = D_i + D_f / 256.0

    cp_i = np.array(cp_i)
    cp_f = np.array(cp_f)

    cps = cp_i + cp_f / 256.0

    all_flags = np.array(flags)

    pr_valids = np.bitwise_and(all_flags, 0x1) == 0x1
    cp_valids = np.bitwise_and(all_flags, 0x2) == 0x2
    hc_valids = np.bitwise_and(all_flags, 0x4) == 0x4
    md_valids = np.bitwise_and(all_flags, 0x8) == 0x8

    # Save this packet
    # See sbp_piksi.h for format
    for i, o in enumerate(sbp_msg.obs):
      # Handle all the message specific stuff
      flags = all_flags[i]
      msdopp = msdopps[i]
      cp_valid = cp_valids[i]
      pr_valid = pr_valids[i]
      hc_valid = hc_valids[i]
      md_valid = md_valids[i]
      cp = cps[i]
      sid = sids[i]

      if not is_deprecated_abc:
        self.gps_tow += sbp_msg.header.t.ns_residual * 1e-9

      try:
        ocp = self.old_cp[sid]
      except:
        ocp = 0

      # Compute time difference of carrier phase for display, but only if
      # carrier phase and pseudorange are valid
      if ocp != 0 and (is_deprecated_abc or (cp_valid and pr_valid)):
        # Doppler per RINEX has opposite sign direction to carrier phase
        if self.gps_tow != self.old_tow:
          cpdopp = (ocp - cp) / float(self.gps_tow - self.old_tow)
        else:
          print "Received two complete observation sets with identical TOW"
          cpdopp = 0

        # Older messages had flipped sign carrier phase values
        if is_deprecated_ab:
          cpdopp = -cpdopp
      else:
        cpdopp = 0

      # Save carrier phase value, but only if value is valid
      if (is_deprecated_abc) or cp_valid:
        self.new_cp[sid] = cp

      flags_str = "0x{:04X} = ".format(flags)

      # Add some indicators to help understand the flags values
      # Bit 0 is Pseudorange valid
      if (pr_valid):
        flags_str += "PR "
      # Bit 1 is Carrier phase valid
      if (cp_valid):
        flags_str += "CP "
      # Bit 2 is Half-cycle ambiguity
      if (hc_valid):
        flags_str += "1/2C "
      # Bit 3 is Measured Doppler Valid
      if (md_valid):
        flags_str += "MD "

      pr_str = "{:11.2f}".format(float(o.P) / divisor)
      cp_str = "{:13.2f}".format(cp)
      cn0_str = "{:2.1f}".format(float(o.cn0) / 4)
      msdopp_str = "{:9.2f}".format(msdopp)
      cpdopp_str = "{:9.2f}".format(cpdopp)
      lock_str = "{:5d}".format(o.lock)

      # Sets invalid values to zero
      if is_deprecated_abc:
        if not (flags & 0x01):
          pr_str = EMPTY_STR
        if not (flags & 0x02):
          cp_str = EMPTY_STR
        if not (flags & 0x08):
          msdopp_str = EMPTY_STR
      if (cpdopp == 0):
        cpdopp_str = EMPTY_STR

      self.incoming_obs[sid] = (pr_str,
                                cp_str,
                                cn0_str,
                                msdopp_str,
                                cpdopp_str,
                                lock_str,
                                flags_str)

    if (count == total - 1):
      self.t = datetime.datetime(1980, 1, 6) + \
               datetime.timedelta(weeks=self.gps_week) + \
               datetime.timedelta(seconds=self.gps_tow)
      self.obs.clear()
      self.obs.update(self.incoming_obs)

    return

  def __init__(self, link, parent, name='Local', relay=False, dirname=None):
    super(ObsView, self).__init__()
    self.parent = parent
    self.dirname = dirname
    self.obs = {}
    self.incoming_obs = {} 
    self.obs_count = 0
    self.gps_tow = 0.0
    self.gps_week = 0
    self.relay = relay
    self.name = name
    self.rinex_file = None
    self.eph_file = None
    self.link = link
    self.link.add_callback(self.obs_packed_callback,
                           [SBP_MSG_OBS,
                            SBP_MSG_OBS_DEP_A,
                            SBP_MSG_OBS_DEP_B,
                            SBP_MSG_OBS_DEP_C])
    self.python_console_cmds = {'obs': self}
    call_repeatedly(.5, self.update_obs)


class Observations(HasTraits):
  python_console_cmds = Dict()
  local = Instance(ObsView)
  remote = Instance(ObsView)
  view = View(
           Item('local', style='custom', show_label=False),
           Item('remote', style='custom', show_label=False),
         )

  def _selected(self):
    return self.parent.selected_tab == self

  def __init__(self, link, parent, dirname=None):
    self.parent = parent
    self.local = ObsView(link, parent=self, name='Local', relay=False, dirname=dirname)
    self.remote = ObsView(link, parent=self, name='Remote', relay=True, dirname=dirname)
    self.python_console_cmds.update(self.local.python_console_cmds)

