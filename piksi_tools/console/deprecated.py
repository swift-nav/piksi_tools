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
"""Deprecated SBP message types and utilities.

If you having sbp problems I feel bad for you son
I got 99 callbacks but your type ain't one

"""

from sbp.acquisition import SBP_MSG_ACQ_RESULT_DEP_A
from sbp.observation import (SBP_MSG_EPHEMERIS_DEP_A, SBP_MSG_EPHEMERIS_DEP_B,
                             SBP_MSG_EPHEMERIS_DEP_C, SBP_MSG_EPHEMERIS_DEP_D,
                             SBP_MSG_OBS_DEP_A)
from sbp.tracking import SBP_MSG_TRACKING_STATE_DEP_A

DEPRECATED_SBP_MESSAGES = [
    SBP_MSG_ACQ_RESULT_DEP_A, SBP_MSG_EPHEMERIS_DEP_A, SBP_MSG_EPHEMERIS_DEP_B,
    SBP_MSG_EPHEMERIS_DEP_C, SBP_MSG_EPHEMERIS_DEP_D, SBP_MSG_OBS_DEP_A,
    SBP_MSG_TRACKING_STATE_DEP_A
]


class DeprecatedMessageHandler(object):
    """Callback prompt for issuing a feature deprecation prompt in the
    console.

    Parameters
    ----------
    link : sbp.client.handler.Handler
      Link for SBP transfer to/from Piksi.
    dep_whitelist : [int]
      List of SBP messages to warn on (defaults to DEPRECATED_SBP_MESSAGES)

    """

    def __init__(self, link, dep_whitelist=DEPRECATED_SBP_MESSAGES):
        self._user_warned = False
        self._link = link
        self._dep_whitelist = dep_whitelist
        self._link.add_callback(self._dep_msg_handler, dep_whitelist)

    def _dep_msg_handler(self, sbp_msg, **metadata):
        if not self._user_warned:
            msg = (
                "Warning! Piksi is outputing deprecated observations \n"
                "which cannot be displayed with the current version of the console.\n\n"
                "We highly recommend upgrading your firmware to\n"
                "most recent version available at http://downloads.swiftnav.com.\n\n"
            )
            self._prompt_dep_warning(msg)
            self._user_warned = True
            self._link.remove_callback(self._dep_msg_handler,
                                       self._dep_whitelist)

    def _prompt_dep_warning(self, text):
        """Nonblocking prompt for a deprecation warning.

        Parameters
        ----------
        txt : str
          Helpful error message for the user

        """
        from piksi_tools.console.callback_prompt import CallbackPrompt, close_button
        prompt = CallbackPrompt(
            title="Deprecation Warning", actions=[close_button])
        prompt.text = text
        prompt.run(block=False)
