#!/usr/bin/env python
# Copyright (C) 2018 Swift Navigation Inc.
# Contact: <dev@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

from traits.api import Button, HasTraits, String
from traitsui.api import (HGroup, Item, TextEditor, VGroup, View, spring)

from piksi_tools.console.gui_utils import MultilineTextEditor

import webbrowser
import threading
import time

SKYLARK_URL = 'https://swiftnav.com/skylark'


class SkylarkView(HasTraits):
    information = String(
        "Skylark is Swift Navigation's high accuracy GNSS corrections service, "
        "delivered over the internet. It removes the need for a base station "
        "or CORS station.")
    link = Button(SKYLARK_URL)
    uuid = String()

    view = View(VGroup(spring,
                HGroup(spring, VGroup(
                    Item(
                        'information',
                        height=5,
                        width=20,
                        show_label=False,
                        style='readonly',
                        editor=MultilineTextEditor(TextEditor(multi_line=True))),
                    HGroup(spring, Item('link', show_label=False), spring),
                    Item('uuid', label='Device UUID', width=400),
                ), spring), spring))

    def __init__(self):
        self.real_uuid = ''

    def _link_fired(self):
        webbrowser.open(SKYLARK_URL)

    def _uuid_changed(self):
        if self.uuid != self.real_uuid:
            threading.Thread(target=self._fix_uuid).start()

    def set_uuid(self, uuid):
        self.real_uuid = uuid
        self.uuid = uuid

    def _fix_uuid(self):
        time.sleep(0.1)
        self.uuid = self.real_uuid
