# Copyright (C) 2017 Swift Navigation Inc.
# Contact: Pasi Miettinen  <pasi.miettinen@exafore.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

import numpy as np
from traits.api import Bool, HasTraits, List
from traitsui.api import HGroup, VGroup, Item, TextEditor

from piksi_tools.console.utils import SUPPORTED_CODES, GUI_CODES, code_to_str

GUI_UPDATE_PERIOD = 0.2
STALE_DATA_PERIOD = 0.8


class MultilineTextEditor(TextEditor):
    """
    Override of TextEditor Class for a multi-line read only
    """

    def init(self, parent=TextEditor(multi_line=True)):
        parent.read_only = True
        parent.multi_line = True


def plot_square_axes(plot, xnames, ynames):
    try:
        if type(xnames) is str:
            xs = plot.data.get_data(xnames)
            ys = plot.data.get_data(ynames)
        else:
            xs = np.concatenate(
                [plot.data.get_data(xname) for xname in xnames])
            ys = np.concatenate(
                [plot.data.get_data(yname) for yname in ynames])

        if 0 in (len(xs), len(ys)):
            return

        minx = min(xs)
        maxx = max(xs)
        miny = min(ys)
        maxy = max(ys)
        rangex = maxx - minx
        rangey = maxy - miny

        try:
            aspect = float(plot.width) / plot.height
        except:  # noqa
            aspect = 1
        if aspect * rangey > rangex:
            padding = (aspect * rangey - rangex) / 2
            plot.index_range.low_setting = minx - padding
            plot.index_range.high_setting = maxx + padding
            plot.value_range.low_setting = miny
            plot.value_range.high_setting = maxy
        else:
            padding = (rangex / aspect - rangey) / 2
            plot.index_range.low_setting = minx
            plot.index_range.high_setting = maxx
            plot.value_range.low_setting = miny - padding
            plot.value_range.high_setting = maxy + padding
    except:  # noqa
        import traceback
        traceback.print_exc()


class CodeFiltered(HasTraits):
    '''
    This class offers a horizontal group of tick boxes that can be
    used to select which of the supported SV codes are selected. You can
    add this feature to your class through class inheritance.
    '''
    received_codes = List()
    # Add boolean variables for each supported code.
    for code in SUPPORTED_CODES:
        vars()['show_{}'.format(code)] = Bool(True)

    def __init__(self):
        super(CodeFiltered, self).__init__()
        self.received_codes = []

    @staticmethod
    def get_filter_group():
        '''
        Return horizontal tick box group.
        '''
        hgroup = HGroup()

        for prefix, code_list in sorted(GUI_CODES.items(), key=lambda x: x[1][0] if x[0] != 'SBAS' else 100):
            vgroup = VGroup()
            for code in code_list:
                vgroup.content.append(
                    Item(
                        'show_{}'.format(code),
                        label="{}:".format(code_to_str(code)),
                        visible_when="{} in received_codes".format(code)))
            hgroup.content.append(vgroup)
        return hgroup
