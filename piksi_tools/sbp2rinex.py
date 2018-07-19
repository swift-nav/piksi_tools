#!/usr/bin/env python
# Copyright (C) 2016 Swift Navigation Inc.
# Contact: Leith Bade <leith@swiftnav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.
"""Generates a RINEX 2.11 observation file from a SBP log.
"""
from __future__ import print_function

import datetime
import os
import time

import sbp.navigation as nav
import sbp.observation as ob
from sbp.client.loggers.json_logger import JSONLogIterator


def from_base(msg):
    return msg.sender == 0


def _is_nested(attr):
    return len(attr.keys()) > 0 and isinstance(attr[attr.keys()[0]], dict)


def dict_depth(d, depth=0):
    if not isinstance(d, dict) or not d:
        return depth
    return max(dict_depth(v, depth + 1) for k, v in d.iteritems())


header_fmt = """     2.11           OBSERVATION DATA    G (GPS)             RINEX VERSION / TYPE
sbp2rinex                               %s UTC PGM / RUN BY / DATE
                                                            MARKER NAME
                                                            OBSERVER / AGENCY
                    Piksi                                   REC # / TYPE / VERS
                                                            ANT # / TYPE
 %14.4f %14.4f %14.4f               APPROX POSITION XYZ
         0.0000         0.0000         0.0000               ANTENNA: DELTA H/E/N
     6    C1    L1    S1   C2    L2    S2                   # / TYPES OF OBSERV
%s%13.7f     GPS         TIME OF FIRST OBS
                                                            END OF HEADER
"""


class StoreToRINEX(object):
    """Stores observations as RINEX.

    """

    def __init__(self):
        self.base_obs = {}
        self.base_obs_integrity = {}
        self.rover_obs = {}
        self.rover_obs_integrity = {}
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.time = None
        self.first_spp = False

    def _process_spp(self, msg):
        self.x = float(msg.x)
        self.y = float(msg.y)
        self.z = float(msg.z)

    def _process_obs(self, msg):
        time = datetime.datetime(1980, 1, 6) + \
            datetime.timedelta(weeks=msg.header.t.wn) + \
            datetime.timedelta(seconds=msg.header.t.tow / 1e3)
        # n_obs is split bytewise between the total and the count (which message
        # this is).
        count = 0x0F & msg.header.n_obs
        total = msg.header.n_obs >> 4
        t = self.base_obs if from_base(msg) else self.rover_obs
        ti = self.base_obs_integrity if from_base(msg) else \
            self.rover_obs_integrity
        # Convert pseudorange, carrier phase to SI units.
        for o in msg.obs:
            prn = o.sid.sat
            code = o.sid.code

            if msg.msg_type == ob.SBP_MSG_OBS_DEP_B:
                p_scale = 1.0 / 1e2
                l_scale = -1
            else:
                p_scale = 1.0 / 5e1
                l_scale = 1
            v = t.get(time, {}).get(prn, {})
            if code == 0:
                v.update({
                    'P': o.P * p_scale,
                    'L': l_scale * (o.L.i + o.L.f / 256.0),
                    'S': o.cn0 / 4.0,
                    'lock': o.lock
                })
            elif code == 1:
                v.update({
                    'P2': o.P * p_scale,
                    'L2': l_scale * (o.L.i + o.L.f / 256.0),
                    'S2': o.cn0 / 4.0,
                    'lock2': o.lock
                })
            if time in t:
                t[time].update({prn: v})
            else:
                t[time] = {prn: v}
            # Set the 'counts' field such that the Nth bit is 1 if we have
            # received a message whose 'count' field (the first byte of the n_obs
            # field) is N. If we have gotten them all, counts should be
            # (1 << total) - 1, and python makes the numbers really big as needed.
            if time in ti:
                ti[time].update({'counts': ti[time]['counts'] | 1 << count})
            else:
                ti[time] = {'total': total, 'counts': 1 << count}

    def process_message(self, msg):
        """Processes messages.

        Parameters
        ----------
        msg : SBP message
          SBP message payload

        """
        if msg.msg_type == ob.SBP_MSG_OBS:
            self._process_obs(msg)
        if not self.first_spp and msg.msg_type == nav.SBP_MSG_POS_ECEF:
            self._process_spp(msg)
            self.first_spp = True

    def save(self, filename):
        if os.path.exists(filename):
            print("Unlinking %s, which already exists!" % filename)
            os.unlink(filename)
        try:
            f = open(filename, mode='w')

            header_written = False
            last_t = 0
            for t, sats in sorted(self.rover_obs.iteritems()):
                if not header_written:
                    header = header_fmt % (datetime.datetime.utcnow().strftime("%Y%m%d %H%M%S"), self.x, self.y,
                                           self.z, t.strftime("  %Y    %m    %d    %H    %M"),
                                           t.second + t.microsecond * 1e-6)
                    f.write(header)
                    header_written = True

                f.write("%s %10.7f  0 %2d" %
                        (t.strftime(" %y %m %d %H %M"),
                         t.second + t.microsecond * 1e-6, len(sats)))

                for prn, obs in sorted(sats.iteritems()):
                    f.write('G%02d' % (prn))
                f.write('   ' * (12 - len(sats)))
                f.write('\n')

                for (prn), obs in sorted(sats.iteritems()):
                    # G    3 C1C L1C S1C
                    if obs.get('P', None):
                        f.write("%14.3f " % obs.get('P', 0))
                        f.write("%14.3f " % obs.get('L', 0))
                        f.write("%14.3f " % obs.get('S', 0))
                    # now we write the L1 lock indicator
                    lock_indicator = 1
                    last_obs = self.rover_obs.get(last_t, {}).get((prn), None)
                    if last_obs and last_obs.get('lock', None) and obs.get(
                            'lock', None):
                        if last_obs['lock'] == obs['lock']:
                            lock_indicator = 0
                    f.write("%01d  \n" % lock_indicator)
                    # if we have L2
                    if obs.get('P2', None):
                        f.write("%14.3f " % obs.get('P2', 0))
                        f.write("%14.3f " % obs.get('L2', 0))
                        f.write("%14.3f " % obs.get('S2', 0))
                        lock_indicator = 1
                        if last_obs:
                            if last_obs.get('lock2') == obs.get('lock2'):
                                lock_indicator = 0
                        f.write("%01d  \n" % lock_indicator)
                    else:
                        f.write("\n")
                    last_t = t
        except:  # noqa
            import traceback
            print(traceback.format_exc())
        finally:
            f.close()


def wrapper(log_datafile, filename, num_records):
    processor = StoreToRINEX()
    i = 0
    logging_interval = 10000
    start = time.time()
    with open(log_datafile, 'r') as infile:
        with JSONLogIterator(infile) as log:
            for msg, data in next(log):
                i += 1
                if i % logging_interval == 0:
                    print("Processed %d records! @ %.1f sec."
                          % (i, time.time() - start))
                processor.process_message(msg)
                if num_records is not None and i >= int(num_records):
                    print("Processed %d records!" % i)
                    break
            processor.save(filename)


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Swift Nav SBP log to RINEX tool.')
    parser.add_argument('file', help='Specify the log file to use.')
    parser.add_argument(
        '-o', '--output', nargs=1, help='RINEX output filename.')
    parser.add_argument(
        '-n',
        '--num_records',
        nargs=1,
        default=[None],
        help='Number or SBP records to process.')
    args = parser.parse_args()
    log_datafile = args.file
    if args.output is None:
        filename = log_datafile + '.obs'
    else:
        filename = args.output[0]
    num_records = args.num_records[0]
    wrapper(log_datafile, filename, num_records)


if __name__ == "__main__":
    main()
