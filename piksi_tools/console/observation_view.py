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

from __future__ import print_function

from monotonic import monotonic
from sbp.observation import (SBP_MSG_OBS, SBP_MSG_OBS_DEP_A, SBP_MSG_OBS_DEP_B,
                             SBP_MSG_OBS_DEP_C, SBP_MSG_OSR)
from traits.api import Dict, Float, Int, List, Str
from traitsui.api import HGroup, Item, UItem, Spring, TabularEditor, VGroup, View

from piksi_tools.console.gui_utils import CodeFiltered, UpdateScheduler, ReadOnlyTabularAdapter
from piksi_tools.console.utils import (
    EMPTY_STR, GUI_CODES, SUPPORTED_CODES, code_is_gps, code_to_str)
from piksi_tools.console.gui_utils import GUI_UPDATE_PERIOD


class SimpleAdapter(ReadOnlyTabularAdapter):
    columns = [('PRN', 0), ('Pseudorange (m)', 1), ('Carrier Phase (cycles)',
                                                    2), ('C/N0 (dB-Hz)', 3),
               ('Meas. Doppler (Hz)', 4), ('Comp. Doppler (Hz)',
                                           5), ('Lock', 6), ('Flags', 7)]
    font = 'courier'
    alignment = 'center'


class ObservationView(CodeFiltered):

    Label = Str('')

    python_console_cmds = Dict()

    traits_obs_table_list = List()
    traits_gps_tow = Float()
    traits_obs_count = Int()
    traits_gps_week = Int()

    for code in SUPPORTED_CODES:
        vars()['count_{}'.format(code)] = Int()

    def trait_view(self, view):
        info = HGroup(
            Spring(width=4, springy=False, height=-1),
            Item(
                'Label',
                label='Week:',
                style='readonly',
                emphasized=True,
                width=-1, padding=-1, height=-1, style_sheet='*{font-size:1px}',
                tooltip='GPS Week Number (since 1980'),
            Item('traits_gps_week', style='readonly', show_label=False),
            Item(
                'Label',
                label='  TOW:',
                style='readonly',
                width=-1, padding=-1, height=-1, style_sheet='*{font-size:1px}',
                emphasized=True,
                tooltip='GPS milliseconds in week'),
            Item(
                'traits_gps_tow',
                style='readonly',
                show_label=False,
                height=-1,
                format_str='%.3f'),
            Item(
                'Label',
                label='  Total:',
                style='readonly',
                emphasized=True,
                width=-1, height=-1, padding=-1, style_sheet='*{font-size:1px}',
                tooltip='Total observation count'),
            Item('traits_obs_count', style='readonly', show_label=False),
            padding=0, springy=False
        )
        filters = HGroup(padding=0, springy=False)
        for prefix, code_list in sorted(
                GUI_CODES.items(), key=lambda x: x[1][0] if x[0] != 'SBAS' else 100):
            vgroup1 = VGroup()  # two groups are needed to combat silly spacing in Traitsui
            vgroup2 = VGroup()
            for code in code_list:
                code_str = code_to_str(code)
                vgroup1.content.append(
                    Item('count_{}'.format(code),
                         label='{}:'.format(code_str),
                         style='readonly',
                         tooltip='{} observation count'.format(code_str),
                         visible_when="{} in received_codes".format(code)
                         )
                )
                vgroup2.content.append(
                    UItem(
                        'show_{}'.format(code),
                        tooltip='show {} observations'.format(code_str),
                        visible_when="{} in received_codes".format(code),
                        height=-16  # this make GUI align better
                    ),
                )
            filters.content.append(vgroup1)
            filters.content.append(vgroup2)
        return View(
            VGroup(
                info,
                filters,
                Item(
                    'traits_obs_table_list',
                    style='readonly',
                    editor=TabularEditor(adapter=SimpleAdapter()),
                    show_label=False),
                label=self.name,
                padding=0,
                show_border=True))

    def update_obs(self, obs_update):
        self.traits_obs_count = len(obs_update)
        self.traits_obs_table_list = [
            ('{} ({})'.format(svid[0], code_to_str(svid[1])),) + obs
            for svid, obs in sorted(obs_update.items())
            if getattr(self, 'show_{}'.format(svid[1]), True)
        ]
        for code in SUPPORTED_CODES:
            setattr(self, 'count_{}'.format(code),
                    len([key for key in obs_update.keys() if key[1] == code]))
            if getattr(self, 'count_{}'.format(code)) != 0 and code not in self.received_codes:
                self.received_codes.append(code)

    def gui_update_tow(self, week, tow):
        self.traits_gps_week = week
        self.traits_gps_tow = tow

    def obs_packed_callback(self, sbp_msg, **metadata):
        if (sbp_msg.sender is not None and (self.relay ^ (sbp_msg.sender == 0))):
            return
        tow = float(sbp_msg.header.t.tow / 1000.0)
        wn = sbp_msg.header.t.wn
        seq = sbp_msg.header.n_obs
        total = seq >> 4
        count = seq & ((1 << 4) - 1)

        def reset():
            self.update_scheduler.schedule_update('tow', self.gui_update_tow, wn, tow)
            self.old_tow = self.gps_tow
            self.gps_tow = tow
            self.gps_week = wn
            self.prev_obs_total = total
            self.prev_obs_count = 0
            self.old_cp = dict(self.new_cp)
            self.new_cp.clear()
            self.incoming_obs.clear()

        # Confirm this packet is good.
        # Assumes no out-of-order packets
        # this happens on first packet received of epoch
        if count == 0:
            reset()
        elif (self.gps_tow != tow or self.gps_week != wn or
                self.prev_obs_count + 1 != count or self.prev_obs_total != total):
            print("We dropped a packet. Skipping this observation sequence")
            reset()
            self.prev_obs_count = count
            return
        else:
            self.prev_obs_count = count

        # Save this packet
        # See sbp_piksi.h for format
        for o in sbp_msg.obs:
            # Handle all the message specific stuff
            prn = o.sid.sat
            flags = 0
            msdopp = None

            # Old PRN values had to add one for GPS
            if (code_is_gps(o.sid.code) and sbp_msg.msg_type in [
                SBP_MSG_OBS_DEP_A, SBP_MSG_OBS_DEP_B, SBP_MSG_OBS_DEP_C
            ]):
                prn += 1

            prn = (prn, o.sid.code)

            # DEP_B and DEP_A obs had different pseudorange scaling
            if sbp_msg.msg_type in [SBP_MSG_OBS_DEP_A, SBP_MSG_OBS_DEP_B]:
                divisor = 1e2
            else:
                divisor = 5e1

            if sbp_msg.msg_type not in [
                SBP_MSG_OBS_DEP_A, SBP_MSG_OBS_DEP_B, SBP_MSG_OBS_DEP_C
            ]:
                flags = o.flags
                if getattr(o, 'D', None):
                    msdopp = float(o.D.i) + float(o.D.f) / (1 << 8)
                self.gps_tow += sbp_msg.header.t.ns_residual * 1e-9
                self.update_scheduler.schedule_update('tow', self.gui_update_tow, self.gps_week, self.gps_tow)

            try:
                ocp = self.old_cp[prn]
            except:  # noqa
                ocp = 0

            cp = float(o.L.i) + float(o.L.f) / (1 << 8)

            # Compute time difference of carrier phase for display, but only if
            # carrier phase is valid
            if ocp != 0 and ((sbp_msg.msg_type in [
                SBP_MSG_OBS_DEP_A, SBP_MSG_OBS_DEP_B, SBP_MSG_OBS_DEP_C
            ]) or (flags & 0x3) == 0x3):
                # Doppler per RINEX has opposite sign direction to carrier phase
                if self.gps_tow != self.old_tow:
                    cpdopp = (ocp - cp) / float(self.gps_tow - self.old_tow)
                else:
                    print(
                        "Received two complete observation sets with identical TOW"
                    )
                    cpdopp = 0

                # Older messages had flipped sign carrier phase values
                if sbp_msg.msg_type in [SBP_MSG_OBS_DEP_A, SBP_MSG_OBS_DEP_B]:
                    cpdopp = -cpdopp
            else:
                cpdopp = 0

            # Save carrier phase value, but only if value is valid
            if (sbp_msg.msg_type in [
                SBP_MSG_OBS_DEP_A, SBP_MSG_OBS_DEP_B, SBP_MSG_OBS_DEP_C
            ]) or (flags & 0x3) == 0x3:
                self.new_cp[prn] = cp

            flags_str = "0x{:04X} = ".format(flags)

            # Add some indicators to help understand the flags values
            # Bit 0 is Pseudorange valid
            if (flags & 0x01):
                flags_str += "PR "
            # Bit 1 is Carrier phase valid
            if (flags & 0x02):
                flags_str += "CP "
            # Bit 2 is Half-cycle ambiguity
            if (flags & 0x04):
                flags_str += "1/2C "
            # Bit 3 is Measured Doppler Valid
            if (flags & 0x08):
                flags_str += "MD "

            pr_str = "{:11.2f}".format(float(o.P) / divisor)
            cp_str = "{:13.2f}".format(cp)
            if getattr(o, 'cn0', None):
                cn0_str = "{:2.1f}".format(float(o.cn0) / 4)
            else:
                cn0_str = EMPTY_STR
            if msdopp:
                msdopp_str = "{:9.2f}".format(msdopp)
            else:
                msdopp_str = EMPTY_STR
            cpdopp_str = "{:9.2f}".format(cpdopp)
            lock_str = "{:5d}".format(o.lock)

            # Sets invalid values to zero
            if sbp_msg.msg_type not in [
                SBP_MSG_OBS_DEP_A, SBP_MSG_OBS_DEP_B, SBP_MSG_OBS_DEP_C
            ]:
                if not (flags & 0x01):
                    pr_str = EMPTY_STR
                if not (flags & 0x02):
                    cp_str = EMPTY_STR
                if not (flags & 0x08):
                    msdopp_str = EMPTY_STR
            if (cpdopp == 0):
                cpdopp_str = EMPTY_STR

            self.incoming_obs[prn] = (pr_str, cp_str, cn0_str, msdopp_str,
                                      cpdopp_str, lock_str, flags_str)

        if (count == total - 1):
            # this is here to let GUI catch up to real time if required
            if monotonic() - self.last_table_update_time > GUI_UPDATE_PERIOD:
                self.update_scheduler.schedule_update('update_obs', self.update_obs, self.incoming_obs.copy())
                self.last_table_update_tow = self.gps_tow
                self.last_table_update_time = monotonic()
        return

    def __init__(self, link, name='Local', relay=False, dirname=None):
        super(ObservationView, self).__init__()
        self.dirname = dirname
        self.last_table_update_tow = 0
        self.last_table_update_time = 0
        self.old_cp = {}
        self.new_cp = {}
        self.incoming_obs = {}
        self.gps_tow = 0.0
        self.old_tow = 0.0
        self.gps_week = 0
        self.relay = relay
        self.name = name
        self.rinex_file = None
        self.eph_file = None
        self.link = link
        self.link.add_callback(self.obs_packed_callback, [
            SBP_MSG_OBS, SBP_MSG_OBS_DEP_A, SBP_MSG_OBS_DEP_B,
            SBP_MSG_OBS_DEP_C, SBP_MSG_OSR
        ])
        self.python_console_cmds = {'obs': self}
        self.prev_obs_count = 0
        self.prev_obs_total = 0
        self.traits_obs_count = 0
        self.traits_gps_tow = 0.0
        self.update_scheduler = UpdateScheduler()
