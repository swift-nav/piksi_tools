from threading import Timer

from sbp.system import SBP_MSG_INS_UPDATES, MsgInsUpdates
from traits.api import Enum, HasTraits
from traitsui.api import (Item, View)

from .utils import resource_filename


# No updates have been attempted in the past `STATUS_PERIOD`
UNKNOWN = u'\u2B1B' # Unicode Character “⬛” (U+2B1B)
# There have been attempted updates in the past `STATUS_PERIOD` but at least one was rejected
WARNING = u'\u26A0' # Unicode Character “⚠” (U+26A0)
# There have been updates in the past `STATUS_PERIOD` and none were rejected
OK = u'\u26AB' # Unicode Character “⚫” (U+26AB)

MSG_UPDATE_FLAGS = [
    'gnsspos',
    'gnssvel',
    'wheelticks',
    'speed',
    'nhc',
    'zerovel',
]

STATUS_PERIOD = 1


def filter_rejection(msg_ins_updates):
    for flag in MSG_UPDATE_FLAGS:
        if getattr(msg_ins_updates, flag) & 0b1111:
            return True
    return False


def delayed(old, func, delay=STATUS_PERIOD):
    if old is not None:
        old.cancel()
    t = Timer(delay, func)
    t.start()
    return t


def status_item(status):
    return Item(
        'status',
        show_label=False,
        visible_when='status == \'{}\''.format(status),
        springy=False,
        style='readonly',
        style_sheet=status_to_style(status)
    )


def status_to_style(status):
    if status == OK:
        return '* { color: green; }'
    elif status == WARNING:
        return '* { color: orange; }'
    else:
        return '* { color: grey; }'


class FusionEngineStatus(HasTraits):
    status = Enum(UNKNOWN, WARNING, OK)
    view = View(status_item(UNKNOWN), status_item(WARNING), status_item(OK))

    def __init__(self, link):
        # The last status received, but not nessesarly the one that's displayed if we are in the middle of a warning
        self._last_status = UNKNOWN

        # Timer to end the warning state
        self._warning_timer = None

        # Timer to trigger the unknown state
        self._set_unknown_timer = None

        link.add_callback(self._receive_ins_updates, SBP_MSG_INS_UPDATES)

    def _receive_ins_updates(self, sbp_msg, **metadata):
        if filter_rejection(MsgInsUpdates(sbp_msg)):
            self._set_status(WARNING)
        else:
            self._set_status(OK)
        self._start_unknown_timer()

    def _set_status(self, status):
        self._last_status = status

        if status == WARNING:
            self.status = WARNING
            self._start_warning_timer()
        elif status == UNKNOWN:
            if self._active_warning():
                self._end_warning()
            self.status = UNKNOWN
        elif status == OK and not self._active_warning():
            self.status = OK

    def _end_warning(self):
        if self._active_warning():
            self._warning_timer.cancel()
        self._warning_timer = None
        self._set_status(self._last_status)

    def _start_warning_timer(self):
        self._warning_timer = delayed(
            self._warning_timer, self._end_warning
        )

    def _start_unknown_timer(self):
        self._set_unknown_timer = delayed(
            self._set_unknown_timer,
            lambda: self._set_status(UNKNOWN))

    def _active_warning(self):
        return self._warning_timer is not None
