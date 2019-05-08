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

from sbp.orientation import SBP_MSG_ORIENT_EULER
from sbp.imu import SBP_MSG_IMU_RAW
from .gui_utils import GUI_UPDATE_PERIOD, UpdateScheduler

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

    ##################################################################
    traits_view = View(Item(name='scene',
                       editor=SceneEditor(scene_class=AttitudeScene),
                       show_label=False,
                       resizable=True),
                resizable=True,
                scrollable=False)

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

    def __init__(self, link, **traits):
        HasTraits.__init__(self, **traits)
    
        # SBP Console stuff.
        self.link = link
        self.link.add_callback(self.orient_euler_callback, SBP_MSG_ORIENT_EULER)
        self.link.add_callback(self.imu_raw_callback, SBP_MSG_IMU_RAW)

        self.python_console_cmds = {'track': self}
        self.update_scheduler = UpdateScheduler()

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
        self.scene.render()

    def orient_euler_callback(self, sbp_msg, **metadata):
        print("Got an euler callback!")

    def imu_raw_callback(self, sbp_msg, **metadata):
        print("Got an IMU Raw!")
        self.update_attitude(360*np.random.rand(), 360*np.random.rand(), 360*np.random.rand())

