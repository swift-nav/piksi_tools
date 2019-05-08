# Authors: Prabhu Ramachandran <prabhu [at] aero.iitb.ac.in>
# Copyright (c) 2007, Enthought, Inc.
# License: BSD Style.

# Enthought imports.
import numpy as np
from monotonic import monotonic
from tvtk.api import tvtk
from traits.api import *
from traitsui.api import *
from tvtk.pyface import actors
from tvtk.pyface.scene import Scene
from mayavi.core.ui.api import MlabSceneModel, SceneEditor
from chaco.api import ArrayPlotData, Plot
from chaco.tools.api import LegendTool
from enable.api import ComponentEditor

from sbp.orientation import SBP_MSG_ORIENT_EULER
from sbp.imu import SBP_MSG_IMU_RAW
from .gui_utils import GUI_UPDATE_PERIOD, UpdateScheduler

NUM_PLOT_POINTS = 200

######################################################################
class AttitudeScene(Scene):
    def _actions_default(self):
        return []

######################################################################
class AttitudeView(HasTraits):
    python_console_cmds = Dict()
    # The scene model.
    scene = Instance(MlabSceneModel, ())

    # Transform for attitude marker.
    tform = Instance(tvtk.Transform, ())

    # Axes attitude marker.
    axes = Instance(tvtk.AxesActor, ())

    # Plot objects for stddev.
    plot = Instance(Plot)
    data = Instance(ArrayPlotData)

    ##################################################################
    traits_view =   View(
                        HGroup(
                            Item(name='scene',
                                 editor=SceneEditor(scene_class=AttitudeScene),
                                 show_label=False,
                                 resizable=True),
                            Item(name='plot',
                                 editor=ComponentEditor(bgcolor=(.8,.8,.8)),
                                 show_label=False,
                                 resizable=True)
                        ),
                        resizable=True,
                        scrollable=False
                    )

    def __init__(self, link, **traits):
        HasTraits.__init__(self, **traits)
        self.update_scheduler = UpdateScheduler()
    
        # SBP Console stuff.
        self.link = link
        self.link.add_callback(self.callback_orient_euler, SBP_MSG_ORIENT_EULER)
        self.python_console_cmds = {'track': self}

        # Plot stuff.
        self.init_plotting()

    def init_plotting(self):
        self.est_yaw = np.zeros(NUM_PLOT_POINTS)
        self.est_pit = np.zeros(NUM_PLOT_POINTS)
        self.est_rol = np.zeros(NUM_PLOT_POINTS)
        self.last_plot_update_time = 0
        self.data = ArrayPlotData(t=np.arange(NUM_PLOT_POINTS),
                                  est_yaw=[0.0],
                                  est_pit=[0.0],
                                  est_rol=[0.0])
        self.plot = Plot(self.data, auto_colors=[0x0000FF, 0x00FF00, 0xFF0000], emphasized=True)
        self.plot.title = 'Attitude Uncertainty'
        self.plot.title_color = [0, 0, 0.43]
        self.ylim = self.plot.value_mapper.range
        self.ylim.low = -360.
        self.ylim.high = 360. 
        self.plot.value_axis.orientation = 'right'
        self.plot.value_axis.axis_line_visible = False
        self.plot.value_axis.title = 'Angle'
        self.legend_visible = True
        self.plot.legend.visible = True
        self.plot.legend.align = 'll'
        self.plot.legend.line_spacing = 1
        self.plot.legend.font = 'modern 8'
        self.plot.legend.draw_layer = 'overlay'
        self.plot.legend.tools.append(LegendTool(self.plot.legend, drag_button="right"))

        self.plot.plot(('t', 'est_yaw'), type='line', color='auto', name='Yaw (\degree)')
        self.plot.plot(('t', 'est_pit'), type='line', color='auto', name='Pitch (\degree)')
        self.plot.plot(('t', 'est_rol'), type='line', color='auto', name='Roll (\degree)')

    @on_trait_change('scene.activated')
    def initialize_scene(self):
        # Turn off all interaction.
        self.scene.scene_editor._interactor.interactor_style = None
        # Set up the attitude transform.
        self.tform = tvtk.Transform()
        self.init_tform_ned()
        # Set up the axes object.
        self.axes = tvtk.AxesActor(cylinder_radius=.02,
                                   shaft_type='cylinder',
                                   axis_labels=False,
                                   user_transform=self.tform)
        self.scene.add_actor(self.axes)
        # Set up the camera. Look down on the origin from above.
        #self.scene.scene_editor._camera.position = (0., 0., 10.)
        #self.scene.scene_editor._renderer.reset_camera()

    def init_tform_ned(self):
        self.tform.identity()
        self.tform.rotate_y(180.)
        self.tform.rotate_x(90.)
    
    # Update the attitude representation.
    def update_attitude(self, y, p, r):
        # Update transform.
        self.init_tform_ned()
        print("ATTITUDE", np.deg2rad(r), np.deg2rad(p), np.deg2rad(y))
        self.tform.rotate_x(r)
        self.tform.rotate_y(p)
        self.tform.rotate_z(y)
        self.axes.user_transform = self.tform
        # Update the plot.
        memoryview(self.est_yaw)[:-1] = memoryview(self.est_yaw)[1:]
        memoryview(self.est_pit)[:-1] = memoryview(self.est_pit)[1:]
        memoryview(self.est_rol)[:-1] = memoryview(self.est_rol)[1:]
        self.est_yaw[-1] = y
        self.est_pit[-1] = p
        self.est_rol[-1] = r

        # Update the attitude view at full rate.
        self.update_scheduler.schedule_update("render_attitude", self.scene.render)
        # Update the plots at reduced rate.
        if monotonic() - self.last_plot_update_time >= GUI_UPDATE_PERIOD:
            self.update_scheduler.schedule_update("attitude_plot_update", self.update_plot)

    def update_plot(self):
        self.last_plot_update_time = monotonic()
        self.data.set_data('est_yaw', self.est_yaw)
        self.data.set_data('est_pit', self.est_pit)
        self.data.set_data('est_rol', self.est_rol)

    def callback_orient_euler(self, sbp_msg, **metadata):
        y = sbp_msg.yaw / 1.e6
        p = sbp_msg.pitch / 1.e6 
        r = sbp_msg.roll / 1.e6
        y_std = sbp_msg.yaw_accuracy
        p_std = sbp_msg.pitch_accuracy
        r_std = sbp_msg.roll_accuracy
        self.update_attitude(y, p, r)

