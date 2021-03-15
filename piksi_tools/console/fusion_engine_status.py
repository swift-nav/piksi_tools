"""This module provides a status bar showing a high-level overview of the INS status.

`FusionEngineStatusBar` contains an icon for each of the INS update types. If there has been a rejected update
within the past second, the icon for that update type will show a `WARNING` symbol. If there has
been an update within the last second, and it was accepted, that type will be displayed as `OK`.
If no updates have been attempted in the past second it will be shown as `UNKNOWN`.
"""

from threading import Timer

from sbp.system import SBP_MSG_INS_UPDATES, MsgInsUpdates
from traits.api import Enum, HasTraits, Instance
from traitsui.api import (Item, View, HGroup)


# No updates have been attempted in the past `STATUS_PERIOD`
UNKNOWN = u'\u2B1B'  # Unicode Character “⬛” (U+2B1B)
# There have been attempted updates in the past `STATUS_PERIOD` but at least one was rejected
WARNING = u'\u26A0'  # Unicode Character “⚠” (U+26A0)
# There have been updates in the past `STATUS_PERIOD` and none were rejected
OK = u'\u26AB'  # Unicode Character “⚫” (U+26AB)


# MsgInsUpdates flags
GNSSPOS = 'gnsspos'
GNSSVEL = 'gnssvel'
WHEELTICKS = 'wheelticks'
SPEED = 'speed'
NHC = 'nhc'
ZEROVEL = 'zerovel'

ALL_FLAGS = [
    GNSSPOS,
    GNSSVEL,
    WHEELTICKS,
    SPEED,
    NHC,
    ZEROVEL,
]

FLAG_LABELS = {
    GNSSPOS: 'GNSS Pos',
    GNSSVEL: 'GNSS Vel',
    WHEELTICKS: 'Wheelticks',
    SPEED: 'Wheelspeed',
    NHC: 'nhc',
    ZEROVEL: 'Static Detection',
}

STATUS_PERIOD = 1


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


def check_flag(flag):
    def check(msg):
        f = getattr(msg, flag)

        rejected = f & 0b00001111
        if rejected:
            return WARNING

        attempted = f & 0b11110000
        if attempted:
            return OK

        return UNKNOWN

    return check


def stats_key(flag):
    return 'stats_{}'.format(flag)


class FusionEngineStatus(HasTraits):
    status = Enum(UNKNOWN, WARNING, OK)
    view = View(status_item(UNKNOWN), status_item(WARNING), status_item(OK))

    def __init__(self, link, status_fn):
        # The last status received, but not nessesarly the one that's displayed if we are in the middle of a warning
        self._last_status = UNKNOWN

        # Timer to end the warning state
        self._warning_timer = None

        # Timer to trigger the unknown state
        self._set_unknown_timer = None

        self._status_fn = status_fn

        link.add_callback(self._receive_ins_updates, SBP_MSG_INS_UPDATES)

    def _receive_ins_updates(self, sbp_msg, **metadata):
        status = self._status_fn(MsgInsUpdates(sbp_msg))
        if status == OK:
            self._set_status(OK)
            self._restart_unknown_timer()
        elif status == WARNING:
            self._set_status(WARNING)
            self._restart_unknown_timer()

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
        self._warning_timer = delayed(self._warning_timer, self._end_warning)

    def _restart_unknown_timer(self):
        self._set_unknown_timer = delayed(
            self._set_unknown_timer,
            lambda: self._set_status(UNKNOWN))

    def _active_warning(self):
        return self._warning_timer is not None


class FusionEngineStatusBar(HasTraits):
    stats_ = Instance(FusionEngineStatus)

    def traits_view(self):
        return View(
            HGroup(
                *[
                    Item(name=stats_key(flag), label=FLAG_LABELS[flag], width=-12, style="custom")
                    for flag in ALL_FLAGS
                ]
            )
        )

    def __init__(self, link):
        for flag in ALL_FLAGS:
            setattr(self, stats_key(flag), FusionEngineStatus(link, check_flag(flag)))
