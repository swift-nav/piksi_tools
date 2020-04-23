from __future__ import absolute_import

import math

from chaco.api import ArrayPlotData, Plot, DataLabel
from enable.api import ComponentEditor
from sbp.observation import MsgSvAzEl, SBP_MSG_SV_AZ_EL
from traits.api import (Bool, Dict, HasTraits, Instance, Str)
from traitsui.api import (HGroup, Item, Spring, VGroup, View)

from piksi_tools.console.utils import (code_is_gps,
                                       code_is_glo,
                                       code_is_bds,
                                       code_is_galileo,
                                       code_is_sbas,
                                       get_label)


DEG_SIGN = u"\N{DEGREE SIGN}"
TRK_SIGN = "'"


class SkyplotView(HasTraits):
    python_console_cmds = Dict()
    legend_visible = Bool()
    gps_visible = Bool()
    glo_visible = Bool()
    gal_visible = Bool()
    bds_visible = Bool()
    sbas_visible = Bool()
    hint = Str("Enabled with SBP message MSG_SV_AZ_EL (0x0097 | 151), "
               f"{TRK_SIGN} indicates satellite is being tracked")
    plot = Instance(Plot)
    plot_data = Instance(ArrayPlotData)
    traits_view = View(
        VGroup(
            Item(
                'plot',
                editor=ComponentEditor(bgcolor=(0.8, 0.8, 0.8)),
                show_label=False),
            HGroup(
                Spring(width=8, springy=False),
                Item('hint', show_label=False, style='readonly',
                     style_sheet='*{font-style:italic}')),
            HGroup(
                Spring(width=8, springy=False),
                Item('legend_visible', label="Show Legend:"),
                Spring(width=8, springy=False),
                Item('gps_visible', label="GPS"),
                Item('glo_visible', label="GLONASS"),
                Item('gal_visible', label="GALILEO"),
                Item('bds_visible', label="BEIDOU"),
                Item('sbas_visible', label="SBAS"))))

    def azel_to_xy(self, az, el):
        az_rad = az * math.pi / 180
        radius = 90 - el

        x = radius * math.sin(az_rad)
        y = radius * math.cos(az_rad)

        return x, y

    def create_circle(self, elevation):
        x_list = []
        y_list = []
        for i in range(361):
            x, y = self.azel_to_xy(i, elevation)
            x_list.append(x)
            y_list.append(y)
        return x_list, y_list

    def create_radial(self, azimuth):
        x_list = []
        y_list = []
        for i in range(0, 91):
            x, y = self.azel_to_xy(azimuth, i)
            x_list.append(x)
            y_list.append(y)
            x, y = self.azel_to_xy(azimuth + 180, i)
            x_list.append(x)
            y_list.append(y)
        return x_list, y_list

    def azel_callback(self, sbp_msg, **metadata):
        svazelmsg = MsgSvAzEl(sbp_msg)
        tracked = self._trk_view.get_tracked_sv_labels()

        pending_update = {'x_gps': [],
                          'x_glo': [],
                          'x_gal': [],
                          'x_bds': [],
                          'x_sbas': [],
                          'y_gps': [],
                          'y_glo': [],
                          'y_gal': [],
                          'y_bds': [],
                          'y_sbas': []
                          }

        # store new label updates, and display at once
        overlay_update = []

        for azel in svazelmsg.azel:
            sid = azel.sid
            az = azel.az * 2
            el = azel.el

            x, y = self.azel_to_xy(az, el)

            sat_string = ""

            if code_is_gps(sid.code) and self.gps_visible:
                pending_update['x_gps'].append(x)
                pending_update['y_gps'].append(y)
            elif code_is_glo(sid.code) and self.glo_visible:
                pending_update['x_glo'].append(x)
                pending_update['y_glo'].append(y)
            elif code_is_galileo(sid.code) and self.gal_visible:
                pending_update['x_gal'].append(x)
                pending_update['y_gal'].append(y)
            elif code_is_bds(sid.code) and self.bds_visible:
                pending_update['x_bds'].append(x)
                pending_update['y_bds'].append(y)
            elif code_is_sbas(sid.code) and self.sbas_visible:
                pending_update['x_sbas'].append(x)
                pending_update['y_sbas'].append(y)

            sat_string = get_label((sid.code, sid.sat))[2]

            if sat_string in tracked:
                sat_string += TRK_SIGN

            label = DataLabel(component=self.plot, data_point=(x, y),
                              label_text=sat_string,
                              label_position="bottom right",
                              border_visible=False,
                              bgcolor="transparent",
                              marker_visible=False,
                              font='modern 14',
                              arrow_visible=False,
                              show_label_coords=False
                              )
            overlay_update.append(label)

        # display label updates
        self.plot.overlays = (self.axis_overlays +
                              overlay_update +
                              self.default_overlays)

        self.plot_data.update(pending_update)

    def _legend_visible_changed(self):
        if self.plot:
            self.plot.legend.visible = self.legend_visible

    def __init__(self, link, trk_view):
        self._trk_view = trk_view
        self.legend_visible = False
        self.gps_visible = True
        self.glo_visible = True
        self.gal_visible = True
        self.bds_visible = True
        self.sbas_visible = True

        self.x_circle_0, self.y_circle_0 = self.create_circle(0)
        self.x_circle_30, self.y_circle_30 = self.create_circle(30)
        self.x_circle_60, self.y_circle_60 = self.create_circle(60)

        # draw radial lines at 0, 30, 60, 90, 120, 150 degrees
        self.x_radial_0, self.y_radial_0 = self.create_radial(0)
        self.x_radial_30, self.y_radial_30 = self.create_radial(30)
        self.x_radial_60, self.y_radial_60 = self.create_radial(60)
        self.x_radial_90, self.y_radial_90 = self.create_radial(90)
        self.x_radial_120, self.y_radial_120 = self.create_radial(120)
        self.x_radial_150, self.y_radial_150 = self.create_radial(150)

        self.plot_data = ArrayPlotData(
            x_gps=[],
            x_glo=[],
            x_gal=[],
            x_bds=[],
            x_sbas=[],
            y_gps=[],
            y_glo=[],
            y_gal=[],
            y_bds=[],
            y_sbas=[],
            x_0=self.x_circle_0,
            y_0=self.y_circle_0,
            x_30=self.x_circle_30,
            y_30=self.y_circle_30,
            x_60=self.x_circle_60,
            y_60=self.y_circle_60,
            xr_0=self.x_radial_0,
            yr_0=self.y_radial_0,
            xr_30=self.x_radial_30,
            yr_30=self.y_radial_30,
            xr_60=self.x_radial_60,
            yr_60=self.y_radial_60,
            xr_90=self.x_radial_90,
            yr_90=self.y_radial_90,
            xr_120=self.x_radial_120,
            yr_120=self.y_radial_120,
            xr_150=self.x_radial_150,
            yr_150=self.y_radial_150,
        )
        self.plot = Plot(self.plot_data)

        gps = self.plot.plot(
            ('x_gps', 'y_gps'),
            type='scatter',
            name='',
            color='green',
            marker='dot',
            line_width=0.0,
            marker_size=5.0
        )
        glo = self.plot.plot(
            ('x_glo', 'y_glo'),
            type='scatter',
            name='',
            color='red',
            marker='dot',
            line_width=0.0,
            marker_size=5.0
        )
        gal = self.plot.plot(
            ('x_gal', 'y_gal'),
            type='scatter',
            name='',
            color='blue',
            marker='dot',
            line_width=0.0,
            marker_size=5.0
        )
        bds = self.plot.plot(
            ('x_bds', 'y_bds'),
            type='scatter',
            name='',
            color='yellow',
            marker='dot',
            line_width=0.0,
            marker_size=5.0
        )
        sbas = self.plot.plot(
            ('x_sbas', 'y_sbas'),
            type='scatter',
            name='',
            color='purple',
            marker='dot',
            line_width=0.0,
            marker_size=5.0
        )

        self.plot.plot(
            ('x_0', 'y_0'),
            type='line',
            name='',
            color='black',
            line_width=1
        )

        self.plot.plot(
            ('x_30', 'y_30'),
            type='line',
            name='',
            color='black',
            line_width=1
        )

        self.plot.plot(
            ('x_60', 'y_60'),
            type='line',
            name='',
            color='black',
            line_width=1
        )

        self.plot.plot(
            ('xr_0', 'yr_0'),
            type='line',
            name='',
            color='black',
            line_width=0.25
        )

        self.plot.plot(
            ('xr_30', 'yr_30'),
            type='line',
            name='',
            color='black',
            line_width=0.25
        )

        self.plot.plot(
            ('xr_60', 'yr_60'),
            type='line',
            name='',
            color='black',
            line_width=0.25
        )

        self.plot.plot(
            ('xr_90', 'yr_90'),
            type='line',
            name='',
            color='black',
            line_width=0.25
        )

        self.plot.plot(
            ('xr_120', 'yr_120'),
            type='line',
            name='',
            color='black',
            line_width=0.25
        )

        self.plot.plot(
            ('xr_150', 'yr_150'),
            type='line',
            name='',
            color='black',
            line_width=0.25
        )

        plot_labels = ['GPS', 'GLONASS', 'GALILEO', 'BEIDOU', 'SBAS']
        plots_legend = dict(
            zip(plot_labels, [gps, glo, gal, bds, sbas]))
        self.plot.legend.plots = plots_legend
        self.plot.legend.labels = plot_labels  # sets order
        self.plot.legend.visible = False

        self.plot.index_range.low_setting = -110
        self.plot.index_range.high_setting = 110
        self.plot.value_range.low_setting = -110
        self.plot.value_range.high_setting = 110

        self.plot.padding = (5, 5, 5, 5)
        self.plot.aspect_ratio = 1.0
        self.plot.x_axis.visible = False
        self.plot.y_axis.visible = False
        self.plot.x_grid.visible = False
        self.plot.y_grid.visible = False

        self.default_overlays = self.plot.overlays
        self.axis_overlays = []

        north_label = DataLabel(component=self.plot, data_point=(0, 90),
                                label_text="N",
                                label_position="top",
                                border_visible=False,
                                bgcolor="transparent",
                                marker_visible=False,
                                font='modern 20',
                                arrow_visible=False,
                                show_label_coords=False
                                )
        self.axis_overlays.append(north_label)
        east_label = DataLabel(component=self.plot, data_point=(90, 0),
                               label_text="E",
                               label_position="right",
                               border_visible=False,
                               bgcolor="transparent",
                               marker_visible=False,
                               font='modern 20',
                               arrow_visible=False,
                               show_label_coords=False
                               )
        self.axis_overlays.append(east_label)
        south_label = DataLabel(component=self.plot, data_point=(0, -90),
                                label_text="S",
                                label_position="bottom",
                                border_visible=False,
                                bgcolor="transparent",
                                marker_visible=False,
                                font='modern 20',
                                arrow_visible=False,
                                show_label_coords=False
                                )
        self.axis_overlays.append(south_label)
        west_label = DataLabel(component=self.plot, data_point=(-90, 0),
                               label_text="W",
                               label_position="left",
                               border_visible=False,
                               bgcolor="transparent",
                               marker_visible=False,
                               font='modern 20',
                               arrow_visible=False,
                               show_label_coords=False
                               )
        self.axis_overlays.append(west_label)
        el_0_label = DataLabel(component=self.plot, data_point=(0, 90),
                               label_text="0" + DEG_SIGN,
                               label_position="bottom right",
                               border_visible=False,
                               bgcolor="transparent",
                               marker_visible=False,
                               font='modern 10',
                               arrow_visible=False,
                               show_label_coords=False
                               )
        self.axis_overlays.append(el_0_label)
        el_30_label = DataLabel(component=self.plot, data_point=(0, 60),
                                label_text="30" + DEG_SIGN,
                                label_position="bottom right",
                                border_visible=False,
                                bgcolor="transparent",
                                marker_visible=False,
                                font='modern 10',
                                arrow_visible=False,
                                show_label_coords=False
                                )
        self.axis_overlays.append(el_30_label)
        el_60_label = DataLabel(component=self.plot, data_point=(0, 30),
                                label_text="60" + DEG_SIGN,
                                label_position="bottom right",
                                border_visible=False,
                                bgcolor="transparent",
                                marker_visible=False,
                                font='modern 10',
                                arrow_visible=False,
                                show_label_coords=False
                                )
        self.axis_overlays.append(el_60_label)

        self.plot.overlays += self.axis_overlays

        self.link = link
        self.link.add_callback(self.azel_callback, [SBP_MSG_SV_AZ_EL])

        self.python_console_cmds = {'skyplot': self}
