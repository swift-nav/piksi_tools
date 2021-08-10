#!/usr/bin/env python
# Copyright (C) 2014 Swift Navigation Inc.
# Contact: Colin Beighley <colin@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

from __future__ import print_function

from sbp.client.loggers.udp_logger import UdpLogger
from sbp.observation import (SBP_MSG_BASE_POS_ECEF, SBP_MSG_BASE_POS_LLH,
                             SBP_MSG_OBS, SBP_MSG_OBS_DEP_B, SBP_MSG_OBS_DEP_C)
from sbp.piksi import (SBP_MSG_NETWORK_STATE_RESP, MsgNetworkStateReq)
from traits.api import Bool, Button, Enum, HasTraits, Int, String, List
from traitsui.api import (HGroup, Item, TextEditor, UItem, VGroup,
                          View, spring, TabularEditor)

from piksi_tools.console.callback_prompt import CallbackPrompt, close_button
from piksi_tools.console.gui_utils import MultilineTextEditor, ReadOnlyTabularAdapter
from traits.etsconfig.api import ETSConfig
from .utils import resource_filename, sizeof_fmt

if ETSConfig.toolkit != 'null':
    from enable.savage.trait_defs.ui.svg_button import SVGButton

DEFAULT_UDP_ADDRESS = "127.0.0.1"
DEFAULT_UDP_PORT = 13320
OBS_MSGS = [
    SBP_MSG_OBS_DEP_C, SBP_MSG_OBS_DEP_B, SBP_MSG_BASE_POS_LLH,
    SBP_MSG_BASE_POS_ECEF, SBP_MSG_OBS
]


def ip_bytes_to_string(ip_bytes):
    return '.'.join(str(x) for x in ip_bytes)


class SimpleNetworkAdapter(ReadOnlyTabularAdapter):
    columns = [('Interface Name', 0), ('IPv4 Addr', 1), ('Running', 2),
               ('Tx Usage', 3), ('Rx Usage', 4)]


class SbpRelayView(HasTraits):
    """
    Class allows user to specify port, IP address, and message set
    to relay over UDP.
    """
    running = Bool(False)
    _network_info = List()
    configured = Bool(False)
    broadcasting = Bool(False)
    msg_enum = Enum('Observations', 'All')
    ip_ad = String(DEFAULT_UDP_ADDRESS)
    port = Int(DEFAULT_UDP_PORT)
    information = String(
        'UDP Streaming\n\nBroadcast SBP information received by'
        ' the console to other machines or processes over UDP. With the \'Observations\''
        ' radio button selected, the console will broadcast the necessary information'
        ' for a rover Piksi to acheive an RTK solution.'
        '\n\nThis can be used to stream observations to a remote Piksi through'
        ' aircraft telemetry via ground control software such as MAVProxy or'
        ' Mission Planner.')
    start = Button(label='Start', toggle=True, width=32)
    stop = Button(label='Stop', toggle=True, width=32)
    network_refresh_button = SVGButton(
        label='Refresh Network Status',
        tooltip='Refresh Network Status',
        filename=resource_filename('console/images/fontawesome/refresh.svg'),
        width=16,
        height=16,
        aligment='center')
    view = View(
        VGroup(
            spring,
            HGroup(
                VGroup(
                    Item(
                        'msg_enum',
                        label="Messages to broadcast",
                        style='custom',
                        enabled_when='not running'),
                    Item(
                        'ip_ad',
                        label='IP Address',
                        enabled_when='not running'),
                    Item('port', label="Port", enabled_when='not running'),
                    HGroup(
                        spring,
                        UItem(
                            'start',
                            enabled_when='not running',
                            show_label=False),
                        UItem(
                            'stop',
                            enabled_when='running',
                            show_label=False), spring)),
                VGroup(
                    Item(
                        'information',
                        label="Notes",
                        height=10,
                        editor=MultilineTextEditor(
                            TextEditor(multi_line=True)),
                        style='readonly',
                        show_label=False,
                        resizable=True,
                        padding=15),
                    spring,
                )
            ),
            spring,
            HGroup(
                VGroup(
                    Item(
                        '_network_info',
                        style='readonly',
                        editor=TabularEditor(
                            adapter=SimpleNetworkAdapter()),
                        show_label=False, ),
                    Item(
                        'network_refresh_button', show_label=False,
                        width=0.50),
                    show_border=True,
                    label="Network",
                ),
            )
        )
    )

    def _network_callback(self, m, **metadata):
        txstr = sizeof_fmt(m.tx_bytes),
        rxstr = sizeof_fmt(m.rx_bytes)
        if m.interface_name.startswith(b'ppp0'):  # Hack for ppp tx and rx which doesn't work
            txstr = "---"
            rxstr = "---"
        elif m.interface_name.startswith(b'lo') or m.interface_name.startswith(b'sit0'):
            return
        table_row = ((m.interface_name.decode('ascii'), ip_bytes_to_string(m.ipv4_address),
                     ((m.flags & (1 << 6)) != 0), txstr, rxstr))
        exists = False
        for i, each in enumerate(self._network_info):
            if each[0][0] == table_row[0][0]:
                self._network_info[i] = table_row
                exists = True
        if not exists:
            self._network_info.append(table_row)

    def __init__(self,
                 link):
        """
        Traits tab with UI for UDP broadcast of SBP.

        Parameters
        ----------
        link : sbp.client.handler.Handler
          Link for SBP transfer to/from Piksi.
        device_uid : str
          Piksi Device UUID (defaults to None)
        whitelist : [int] | None
          Piksi Device UUID (defaults to None)

        """
        self.link = link
        self.msgs = OBS_MSGS
        # register a callback when the msg_enum trait changes
        self.on_trait_change(self.update_msgs, 'msg_enum')
        self.python_console_cmds = {'update': self}
        self.cellmodem_interface_name = "ppp0"
        self.link.add_callback(self._network_callback,
                               SBP_MSG_NETWORK_STATE_RESP)

    def update_msgs(self):
        """Updates the instance variable msgs which store the msgs that we
        will send over UDP.

        """
        if self.msg_enum == 'Observations':
            self.msgs = OBS_MSGS
        elif self.msg_enum == 'All':
            self.msgs = [None]
        else:
            raise NotImplementedError

    def _prompt_setting_error(self, text):
        """Nonblocking prompt for a device setting error.

        Parameters
        ----------
        text : str
          Helpful error message for the user

        """
        prompt = CallbackPrompt(title="Setting Error", actions=[close_button])
        prompt.text = text
        prompt.run(block=False)

    def update_network_state(self):
        self._network_refresh_button_fired()

    def _network_refresh_button_fired(self):
        self._network_info = []
        self.link(MsgNetworkStateReq())

    def _start_fired(self):
        """Handle start udp broadcast button. Registers callbacks on
        self.link for each of the self.msgs If self.msgs is None, it
        registers one generic callback for all messages.

        """
        self.running = True
        try:
            self.func = UdpLogger(self.ip_ad, self.port)
            self.link.add_callback(self.func, self.msgs)
        except:  # noqa
            import traceback
            print(traceback.format_exc())

    def _stop_fired(self):
        """Handle the stop udp broadcast button. It uses the self.funcs and
        self.msgs to remove the callbacks that were registered when the
        start button was pressed.

        """
        try:
            self.link.remove_callback(self.func, self.msgs)
            self.func.__exit__()
            self.func = None
            self.running = False
        except:  # noqa
            import traceback
            print(traceback.format_exc())
