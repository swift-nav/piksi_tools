# Copyright (C) 2017 Swift Navigation Inc.
# Contact: Pasi Miettinen  <pasi.miettinen@exafore.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

from traits.api import Bool, HasTraits
from traitsui.api import HGroup, Item, Spring, TextEditor

import numpy as np
import sys

from piksi_tools.console.utils import code_to_str, SUPPORTED_CODES


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
            minx = min(xs)
            maxx = max(xs)
            miny = min(ys)
            maxy = max(ys)
        else:
            concatx = np.concatenate(
                [plot.data.get_data(xname) for xname in xnames])
            concaty = np.concatenate(
                [plot.data.get_data(yname) for yname in ynames])
            minx = min(concatx)
            maxx = max(concatx)
            miny = min(concaty)
            maxy = max(concaty)
        rangex = maxx - minx
        rangey = maxy - miny
        try:
            aspect = float(plot.width) / plot.height
        except:
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
    except:
        import traceback
        sys.__stderr__.write(traceback.format_exc() + '\n')


class CodeFiltered(HasTraits):
    '''
    This class offers a horizontal group of tick boxes that can be
    used to select which of the supported SV codes are selected. You can
    add this feature to your class through class inheritance.
    '''

    # Add boolean variables for each supported code.
    for code in SUPPORTED_CODES:
        vars()['show_{}'.format(code)] = Bool()

    def __init__(self):
        super(CodeFiltered, self).__init__()

        # True as default value for each code.
        for code in SUPPORTED_CODES:
            setattr(self, 'show_{}'.format(code), True)

    @staticmethod
    def get_filter_group():
        '''
        Return horizontal tick box group.
        '''
        hgroup = HGroup()

        for code in SUPPORTED_CODES:
            hgroup.content.append(Spring(width=8, springy=False))
            hgroup.content.append(
                Item(
                    'show_{}'.format(code),
                    label="{}:".format(code_to_str(code))))

        return hgroup
