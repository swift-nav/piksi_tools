# Authors: Prabhu Ramachandran <prabhu [at] aero.iitb.ac.in>
# Copyright (c) 2007, Enthought, Inc.
# License: BSD Style.

# Enthought imports.
import numpy as np
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
        #self.link.add_callback(self.callback_imu_raw, SBP_MSG_IMU_RAW)
        self.python_console_cmds = {'track': self}

        # Plot stuff.
        self.init_plot_data()

    def init_plot_data(self):
        self.acc_x = np.zeros(NUM_PLOT_POINTS)
        self.acc_y = np.zeros(NUM_PLOT_POINTS)
        self.acc_z = np.zeros(NUM_PLOT_POINTS)
        self.gyro_x = np.zeros(NUM_PLOT_POINTS)
        self.gyro_y = np.zeros(NUM_PLOT_POINTS)
        self.gyro_z = np.zeros(NUM_PLOT_POINTS)
        self.last_plot_update_time = 0
        self.data = ArrayPlotData(t=np.arange(NUM_PLOT_POINTS),
                                  acc_x=[0.0],
                                  acc_y=[0.0],
                                  acc_z=[0.0],
                                  gyr_x=[0.0],
                                  gyr_y=[0.0],
                                  gyr_z=[0.0])
        self.plot = Plot(self.data, auto_colors=[0x0000FF, 0x00FF00, 0xFF0000], emphasized=True)
        self.plot.title = 'Raw IMU Data'
        self.plot.title_color = [0, 0, 0.43]
        self.ylim = self.plot.value_mapper.range
        self.ylim.low = -32768
        self.ylim.high = 32767
        # self.plot.value_range.bounds_func = lambda l, h, m, tb: (0, h * (1 + m))
        self.plot.value_axis.orientation = 'right'
        self.plot.value_axis.axis_line_visible = False
        self.plot.value_axis.title = 'LSB count'

        self.legend_visible = True
        self.plot.legend.visible = True
        self.plot.legend.align = 'll'
        self.plot.legend.line_spacing = 1
        self.plot.legend.font = 'modern 8'
        self.plot.legend.draw_layer = 'overlay'
        self.plot.legend.tools.append(
            LegendTool(self.plot.legend, drag_button="right"))

        acc_x = self.plot.plot(
            ('t', 'acc_x'), type='line', color='auto', name='Accn. X')
        acc_x = self.plot.plot(
            ('t', 'acc_y'), type='line', color='auto', name='Accn. Y')
        acc_x = self.plot.plot(
            ('t', 'acc_z'), type='line', color='auto', name='Accn. Z')
        acc_x = self.plot.plot(
            ('t', 'gyr_x'), type='line', color='auto', name='Gyro X')
        acc_x = self.plot.plot(
            ('t', 'gyr_y'), type='line', color='auto', name='Gyro Y')
        acc_x = self.plot.plot(
            ('t', 'gyr_z'), type='line', color='auto', name='Gyro Z')


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
        self.init_tform_ned()
        self.tform.rotate_x(r)
        self.tform.rotate_y(p)
        self.tform.rotate_z(y)

        self.axes.user_transform = self.tform
        self.update_scheduler.schedule_update("render_attitude", self.scene.render)

    def update_attitude_std(self, y_std, p_std, r_std):
        pass

    def callback_orient_euler(self, sbp_msg, **metadata):
        y = sbp_msg.yaw / 10.e6
        p = sbp_msg.pitch / 10.e6 
        r = sbp_msg.roll / 10.e6
        y_std = sbp_msg.yaw_accuracy
        p_std = sbp_msg.pitch_accuracy
        r_std = sbp_msg.roll_accuracy
        self.update_attitude(y, p, r)
        self.update_attitude_std(y_std, p_std, r_std)

    def callback_imu_raw(self, sbp_msg, **metadata):
        print("Got an IMU Raw!")
        self.update_attitude(360*np.random.rand(), 360*np.random.rand(), 360*np.random.rand())

