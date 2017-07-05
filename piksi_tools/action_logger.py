#!/usr/bin/env python
from __future__ import print_function

import random
import struct
import sys
import threading
import time

from sbp.client import Forwarder, Framer, Handler
from sbp.logging import SBP_MSG_LOG, SBP_MSG_PRINT_DEP
from sbp.piksi import SBP_MSG_MASK_SATELLITE, MsgMaskSatellite
from sbp.table import dispatch
from sbp.tracking import MsgTrackingState, MsgTrackingStateDepA

import piksi_tools.diagnostics as ptd
import piksi_tools.serial_link as sl

DEFAULT_POLL_INTERVAL = 60  # Seconds
DEFAULT_MIN_SATS = 5  # min satellites to try and retain


class LoopTimer(object):
    """
    The :class:`LoopTimer` calls a function at a regular interval.
    It is intended to be instantiated from a subclass instance of TestState to call
    TestStateSubclass.action() at a regular interval. The implementation is emulated
    from a simliar instance submitted via stack overflow
    http://stackoverflow.com/questions/12435211/python-threading-timer-repeat-function-every-n-seconds

    Parameters
    ----------
    interval: int
      number of seconds between calls
    hfunction : handle to function
      function to call periodically
    """

    def __init__(self, interval, hfunction):
        self.interval = interval
        self.hfunction = hfunction
        self.thread = threading.Timer(self.interval, self.handle_function)

    def handle_function(self):
        """
        Handle function is called each time the timer trips.
        It sets up another timer to call itself again in the future.
        """
        self.hfunction()
        self.thread = threading.Timer(self.interval, self.handle_function)
        self.start()

    def start(self):
        """
        Starts the periodic timer thread.
        """
        self.thread.start()

    def cancel(self):
        """
        Cancels any current timer threads.
        """
        self.thread.cancel()


class TestState(object):
    """
    Super class for representing state and state-based actions during logging.

    Parameters
    ----------
    handler: sbp.client.handler.Handler
        handler for SBP transfer to/from Piksi.
    filename : string
      File to log to.
    """

    def __init__(self, handler):
        self.init_time = time.time()
        self.handler = handler

    def process_message(self, msg):
        """
        Stub for processing messages from device. Should be overloaded in sublcass.
        """
        raise NotImplementedError("process_message not implemented!")

    def action(self):
        """
        Stub for communicating with device. Should be overloaded in subclass.
        """
        raise NotImplementedError("action not implemented!")


class DropSatsState(TestState):
    """
    Subclass of testState that periodically drops a random number of satellite
    above some minimum value

    Parameters
    ----------
    handler: sbp.client.handler.Handler
      handler for SBP transfer to/from Piksi.
    sbpv: (int, int)
      tuple of SBP major/minor version.
    interval : int
      number of seconds between sending mask tracking message
    min sats : int
      number of satellites to never go below
    debug : bool
      Print out extra info?
    """

    def __init__(self, handler, sbpv, interval, min_sats, debug=False):
        super(DropSatsState, self).__init__(handler)
        self.sbpv = sbpv
        self.min_sats = min_sats
        self.debug = debug

        # state encoding
        self.num_tracked_sats = 0
        self.prn_status_dict = {}
        self.channel_status_dict = {}

        # timer stuff
        self.timer = LoopTimer(interval, self.action)

    def __enter__(self):
        self.timer.start()
        return self

    def __exit__(self, *args):
        self.timer.cancel()

    def process_message(self, msg, **metadata):
        """
        Process SBP messages and encode into state information

        Parameters
        ----------
        msg: sbp object
          not yet dispatched message received by device
        """
        msg = dispatch(msg)
        if isinstance(msg, MsgTrackingState) or isinstance(
                msg, MsgTrackingStateDepA):
            if self.debug:
                print("currently tracking {0} sats".format(
                    self.num_tracked_sats))
            self.num_tracked_sats = 0
            for channel, track_state in enumerate(msg.states):
                try:
                    # MsgTrackingState
                    prn = track_state.sid.sat
                    if ((track_state.sid.constellation == 0) and
                            (track_state.sid.band == 0)):
                        prn += 1
                except AttributeError:
                    # MsgTrackingStateDepA
                    prn = track_state.prn + 1
                if track_state.state == 1:
                    self.num_tracked_sats += 1
                    self.prn_status_dict[prn] = channel
                    self.channel_status_dict[channel] = prn
                else:
                    if self.prn_status_dict.get(prn):
                        del self.prn_status_dict[prn]
                    if self.channel_status_dict.get(channel):
                        del self.channel_status_dict[channel]

    def drop_prns(self, prns):
        """
        Drop Prns via sending MsgMaskSatellite to device

        Parameters
        ----------
        prns : int[]
          list of prns to drop
        """
        FLAGS = 0x02  # Drop from tracking, don't mask acquisition.
        if self.debug:
            print("Dropping the following prns {0}".format(prns))
        for prn in prns:
            if self.sbpv < (0, 49):
                # Use pre SID widening Mask Message - have to pack manually.
                msg = struct.pack('BB', FLAGS, prn - 1)
                self.handler.send(SBP_MSG_MASK_SATELLITE, msg)
            else:
                # Use post SID widening Mask Message.
                msg = MsgMaskSatellite(mask=FLAGS, sid=int(prn) - 1)
                self.handler(msg)

    def get_num_sats_to_drop(self):
        """
        Return number of satellites to drop.
        Should drop a random number of satellites above self.min_sats
        If we haven't achieved min sats, it drops zero
        """
        max_to_drop = max(0, self.num_tracked_sats - self.min_sats)
        # end points included
        return random.randint(0, max_to_drop)

    def drop_random_number_of_sats(self):
        """
        Perform drop of satellites.
        """
        num_drop = self.get_num_sats_to_drop()
        if num_drop > 0:
            prns_to_drop = random.sample(self.channel_status_dict.values(),
                                         num_drop)
            if self.debug:
                print(("satellite drop triggered: "
                       "will drop {0} out of {1} sats").format(
                           num_drop, self.num_tracked_sats))
            self.drop_prns(prns_to_drop)

    def action(self):
        """
        Overload of superclass' action method.  Drops a random number of sats above
        some minimum value.
        """
        self.drop_random_number_of_sats()


def get_args():
    """
    Get and parse arguments.
    """
    parser = sl.base_cl_options()
    parser.add_argument(
        "-i",
        "--interval",
        default=[DEFAULT_POLL_INTERVAL],
        nargs=1,
        help="Number of seconds between satellite drop events.")
    parser.add_argument(
        "-m",
        "--minsats",
        default=[DEFAULT_MIN_SATS],
        nargs=1,
        help="Minimum number of satellites to retain during drop events.")
    return parser.parse_args()


def main():
    """
    Get configuration, get driver, get logger, and build handler and start it.
    Create relevant TestState object and perform associated actions.
    Modeled after serial_link main function.
    """
    args = get_args()
    port = args.port
    baud = args.baud
    timeout = args.timeout[0]
    log_filename = args.log_filename[0]
    append_log_filename = args.append_log_filename[0]
    tags = args.tags[0]
    interval = int(args.interval[0])
    minsats = int(args.minsats[0])

    # Driver with context
    with sl.get_driver(args.ftdi, port, baud) as driver:
        # Handler with context
        with Handler(Framer(driver.read, driver.write, args.verbose)) as link:
            # Logger with context
            with sl.get_logger(args.log, log_filename) as logger:
                # Append logger iwth context
                with sl.get_append_logger(append_log_filename,
                                          tags) as append_logger:
                    # print out SBP_MSG_PRINT_DEP messages
                    link.add_callback(sl.printer, SBP_MSG_PRINT_DEP)
                    link.add_callback(sl.log_printer, SBP_MSG_LOG)
                    # add logger callback
                    Forwarder(link, logger).start()
                    # ad append logger callback
                    Forwarder(link, append_logger).start()
                    try:
                        # Get device info
                        # Diagnostics reads out the device settings and resets the Piksi
                        piksi_diag = ptd.Diagnostics(link)
                        while not piksi_diag.heartbeat_received:
                            time.sleep(0.1)
                        # add Teststates and associated callbacks
                        with DropSatsState(
                                link,
                                piksi_diag.sbp_version,
                                interval,
                                minsats,
                                debug=args.verbose) as drop:
                            link.add_callback(drop.process_message)

                            if timeout is not None:
                                expire = time.time() + float(args.timeout[0])

                            while True:
                                if timeout is None or time.time() < expire:
                                    # Wait forever until the user presses Ctrl-C
                                    time.sleep(1)
                                else:
                                    print("Timer expired!")
                                    break
                                if not link.is_alive():
                                    sys.stderr.write("ERROR: Thread died!")
                                    sys.exit(1)
                    except KeyboardInterrupt:
                        # Callbacks call thread.interrupt_main(), which throw a KeyboardInterrupt
                        # exception. To get the proper error condition, return exit code
                        # of 1. Note that the finally block does get caught since exit
                        # itself throws a SystemExit exception.
                        sys.exit(1)


if __name__ == "__main__":
    main()
