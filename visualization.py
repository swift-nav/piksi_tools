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

######################################################################
class AttitudeScene(Scene):
    def _actions_default(self):
        return []

######################################################################
class AttitudeView(HasTraits):
    python_console_cmds = Dict()
    # The scene model.
    scene = Instance(MlabSceneModel, ())

    # The axes transform.
    tform = Instance(tvtk.Transform, ())

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
        #self.scene.scene_editor._interactor.interactor_style = None
        self.tform = tvtk.Transform()
        axes = tvtk.AxesActor(cylinder_radius=.02,
                              shaft_type='cylinder',
                              axis_labels=False,
                              user_transform=self.tform)
        self.tform.rotate_y(180.)
        self.tform.rotate_x(90.)
        self.tform.push()
        self.scene.add_actor(axes)
        # Set up the camera. Look down on the origin from above.
        #self.scene.scene_editor._camera.position = (0., 0., 10.)
        #self.scene.scene_editor._renderer.reset_camera()


    def __init__(self, **traits):
        HasTraits.__init__(self, **traits)
    
        # SBP Console stuff.
        #self.link = link
        #self.link.add_callback(self.imu_raw_callback, SBP_MSG_IMU_RAW)
        #self.link.add_callback(self.imu_aux_callback, SBP_MSG_IMU_AUX)

        self.python_console_cmds = {'track': self}
        #self.update_scheduler = UpdateScheduler()
class Test(HasTraits):
    scene = Instance(AttitudeView, ())

    view = View(Item(name='scene', style='custom', show_label=False))

v = Test()
v.configure_traits()

