#!/usr/bin/env python
# Copyright (C) 2019 Swift Navigation Inc.
# Contact: Swift Navigation <dev@swiftnav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

from __future__ import print_function

# UI
from enable.savage.trait_defs.ui.svg_button import SVGButton
from traits.api import Bool, Enum, HasTraits, Int, List, Str, File
from traitsui.api import EnumEditor, HGroup, Item, Label, Spring, VGroup, View

import piksi_tools.serial_link as s
from piksi_tools import __version__ as CONSOLE_VERSION
from piksi_tools.console.utils import resource_filename, icon

from pathlib import Path


# If using a device connected to an actual port, then invoke the
# regular console dialog for port selection
flow_control_options_list = ['None', 'Hardware RTS/CTS']
cnx_type_list = ['Serial/USB', 'TCP/IP', 'File Replay']

BAUD_LIST = [57600, 115200, 230400, 921600, 1000000]
REPLAY_SPEED_LIST = ["Slow", "Regular", "Fast", "Ludicrous"]


class PortChooser(HasTraits):
    port = Str(None)
    ports = List()
    mode = Enum(cnx_type_list)
    flow_control = Enum(flow_control_options_list)
    ip_port = Int(55555)
    ip_address = Str('192.168.0.222')
    choose_baud = Bool(True)
    baudrate = Int()
    refresh_ports_button = SVGButton(label='',
                                     tooltip='Refresh Port List',
                                     filename=resource_filename('console/images/fontawesome/refresh_blue.svg'),
                                     allow_clipping=False,
                                     width_padding=4, height_padding=4
                                     )
    file_path = File(Path.home())
    file_speed = Str("Regular")

    traits_view = View(
        VGroup(
            Spring(height=8),
            HGroup(
                Spring(width=-2, springy=False),
                Item(
                    'mode',
                    style='custom',
                    editor=EnumEditor(
                        values=cnx_type_list, cols=3, format_str='%s'),
                    show_label=False)),
            HGroup(
                VGroup(
                    Label('Serial Device:'),
                    HGroup(
                        Item('port', editor=EnumEditor(name='ports'), show_label=False, springy=True),
                        Item('refresh_ports_button', show_label=False, padding=0, height=-20, width=-20),
                    ),
                ),
                VGroup(
                    Label('Baudrate:'),
                    Item(
                        'baudrate',
                        editor=EnumEditor(values=BAUD_LIST),
                        show_label=False,
                        visible_when='choose_baud'),
                    Item(
                        'baudrate',
                        show_label=False,
                        visible_when='not choose_baud',
                        style='readonly'), ),
                VGroup(
                    Label('Flow Control:'),
                    Item(
                        'flow_control',
                        editor=EnumEditor(
                            values=flow_control_options_list, format_str='%s'),
                        show_label=False), ),
                visible_when="mode==\'Serial/USB\'"),
            HGroup(
                VGroup(
                    Label('IP Address:'),
                    Item(
                        'ip_address',
                        label="IP Address",
                        style='simple',
                        show_label=False,
                        height=-24), ),
                VGroup(
                    Label('IP Port:'),
                    Item(
                        'ip_port',
                        label="IP Port",
                        style='simple',
                        show_label=False,
                        height=-24), ),
                Spring(),
                visible_when="mode==\'TCP/IP\'"),
            HGroup(
                VGroup(
                    Label('File:'),
                    Item(
                        'file_path',
                        label="File",
                        style='simple',
                        show_label=False,
                        height=-24), ),
                VGroup(
                    Label('Replay Speed:'),
                    Item(
                        'file_speed',
                        editor=EnumEditor(values=REPLAY_SPEED_LIST),
                        show_label=False), ),
                Spring(),
                visible_when="mode==\'File Replay\'"), ),
        buttons=['OK', 'Cancel'],
        default_button='OK',
        close_result=False,
        icon=icon,
        width=460,
        title='Swift Console {0} - Select Interface'.format(CONSOLE_VERSION)
    )

    def refresh_ports(self):
        """
        This method refreshes the port list
        """
        try:
            self.ports = [p for p, _, _ in s.get_ports()]
        except TypeError:
            pass

    def _refresh_ports_button_fired(self):
        self.refresh_ports()

    def __init__(self, baudrate=None):
        self.refresh_ports()
        # As default value, use the first city in the list:
        try:
            self.port = self.ports[0]
        except IndexError:
            pass
        if baudrate not in BAUD_LIST:
            self.choose_baud = False
        self.baudrate = baudrate


def get_args_from_port_chooser(args):
    # Use the gui to get our driver args
    port_chooser = PortChooser(baudrate=int(args.baud))
    is_ok = port_chooser.configure_traits()
    ip_address = port_chooser.ip_address
    ip_port = port_chooser.ip_port
    file_path = port_chooser.file_path
    mode = port_chooser.mode
    args.port = port_chooser.port
    args.baud = port_chooser.baudrate
    args.rtscts = port_chooser.flow_control == flow_control_options_list[1]
    args.replay_speed = port_chooser.file_speed

    # if the user pressed cancel or didn't select anything
    if not (args.port or (ip_address and ip_port)) or not is_ok:
        print("No Interface selected!")
        return None

    # Use TCP/IP if selected from gui
    if mode == cnx_type_list[1]:
        args.tcp = True
        args.file = False
        args.port = ip_address + ":" + str(ip_port)
        print("Using TCP/IP at address %s and port %d" % (ip_address, ip_port))
    elif mode == cnx_type_list[2]:
        args.tcp = False
        args.file = True
        args.port = file_path
    else:
        args.tcp = False
        args.file = False

    return args
