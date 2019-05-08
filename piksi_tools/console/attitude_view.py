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
from tvtk.common import configure_input_data

from sbp.orientation import SBP_MSG_ORIENT_EULER
from sbp.imu import SBP_MSG_IMU_RAW
from .gui_utils import GUI_UPDATE_PERIOD, UpdateScheduler

NUM_PLOT_POINTS = 200

def _secret(image_file):
    # load and map the texture
    img = tvtk.PNGReader()
    img.file_name = image_file
    texture = tvtk.Texture(input_connection=img.output_port, interpolate=1, repeat=1)
    # (interpolate for a less raster appearance when zoomed in)

    cube_source = tvtk.CubeSource(center=(0,0,0))
    cube_mapper = tvtk.PolyDataMapper()
    configure_input_data(cube_mapper, cube_source.output)
    p = tvtk.Property(opacity=1.0)
    actor = tvtk.Actor(mapper=cube_mapper, property=p, texture=texture)
    cube_source.update()
    return actor

    # create the sphere source with a given radius and angular resolution
    # sphere = tvtk.TexturedSphereSource(radius=1, theta_resolution=180,
                                       # phi_resolution=Nrad)

    # assemble rest of the pipeline, assign texture
    # sphere_mapper = tvtk.PolyDataMapper(input_connection=sphere.output_port)
    # sphere_actor = tvtk.Actor(mapper=sphere_mapper, texture=texture)
    # return sphere_actor

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
    logo_tform = Instance(tvtk.Transform, ())

    # Axes attitude marker.
    axes = Instance(tvtk.AxesActor, ())
    logo = Instance(tvtk.Actor, ())

    # Plot objects.
    angle_plot = Instance(Plot)
    angle_data = Instance(ArrayPlotData)

    bias_plot = Instance(Plot)
    bias_data = Instance(ArrayPlotData)

    ##################################################################
    traits_view =   View(
                        HGroup(
                            Item(name='scene',
                                 editor=SceneEditor(scene_class=AttitudeScene),
                                 show_label=False,
                                 resizable=True),
                            VGroup(
                                Item(name='angle_plot',
                                     editor=ComponentEditor(bgcolor=(.8,.8,.8)),
                                     show_label=False,
                                     resizable=True),
                                Item(name='bias_plot',
                                     editor=ComponentEditor(bgcolor=(.8,.8,.8)),
                                     show_label=False,
                                     resizable=True)
                            )
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
        self.last_plot_update_time = 0
        # Set up the angle plotting stuff.
        self.est_yaw = np.zeros(NUM_PLOT_POINTS)
        self.est_pit = np.zeros(NUM_PLOT_POINTS)
        self.est_rol = np.zeros(NUM_PLOT_POINTS)
        self.angle_data = ArrayPlotData(t=np.arange(NUM_PLOT_POINTS),
                                        est_yaw=[0.0],
                                        est_pit=[0.0],
                                        est_rol=[0.0])
        self.angle_plot = Plot(self.angle_data, auto_colors=[0x0000FF, 0x00FF00, 0xFF0000], emphasized=True)
        self.angle_plot.title = 'Yaw/Pitch/Roll'
        self.angle_plot.title_color = [0, 0, 0.43]
        self.ylim = self.angle_plot.value_mapper.range
        self.ylim.low = -180.
        self.ylim.high = 180. 
        self.angle_plot.value_axis.orientation = 'right'
        self.angle_plot.value_axis.axis_line_visible = False
        self.angle_plot.value_axis.title = 'Angle'
        self.legend_visible = True
        self.angle_plot.legend.visible = True
        self.angle_plot.legend.align = 'll'
        self.angle_plot.legend.line_spacing = 1
        self.angle_plot.legend.font = 'modern 8'
        self.angle_plot.legend.draw_layer = 'overlay'
        self.angle_plot.legend.tools.append(LegendTool(self.angle_plot.legend, drag_button="right"))

        self.angle_plot.plot(('t', 'est_yaw'), type='line', color='auto', name='Yaw (\degree)')
        self.angle_plot.plot(('t', 'est_pit'), type='line', color='auto', name='Pitch (\degree)')
        self.angle_plot.plot(('t', 'est_rol'), type='line', color='auto', name='Roll (\degree)')

        # Set up the bias plotting stuff.
        self.bias_x = np.zeros(NUM_PLOT_POINTS)
        self.bias_y = np.zeros(NUM_PLOT_POINTS)
        self.bias_z = np.zeros(NUM_PLOT_POINTS)
        self.bias_data = ArrayPlotData(t=np.arange(NUM_PLOT_POINTS),
                                       bias_z=[0.0],
                                       bias_y=[0.0],
                                       bias_x=[0.0])
        self.bias_plot = Plot(self.bias_data, auto_colors=[0x0000FF, 0x00FF00, 0xFF0000], emphasized=True)
        self.bias_plot.title = 'Gyroscope Biases'
        self.bias_plot.title_color = [0, 0, 0.43]
        self.ylim = self.bias_plot.value_mapper.range
        self.ylim.low = -.1
        self.ylim.high = .1 
        self.bias_plot.value_axis.orientation = 'right'
        self.bias_plot.value_axis.axis_line_visible = False
        self.bias_plot.value_axis.title = 'rad/s'
        self.legend_visible = True
        self.bias_plot.legend.visible = True
        self.bias_plot.legend.align = 'll'
        self.bias_plot.legend.line_spacing = 1
        self.bias_plot.legend.font = 'modern 8'
        self.bias_plot.legend.draw_layer = 'overlay'
        self.bias_plot.legend.tools.append(LegendTool(self.bias_plot.legend, drag_button="right"))

        self.bias_plot.plot(('t', 'bias_z'), type='line', color='auto', name='\omega_z bias')
        self.bias_plot.plot(('t', 'bias_y'), type='line', color='auto', name='\omega_y bias')
        self.bias_plot.plot(('t', 'bias_x'), type='line', color='auto', name='\omega_x bias')

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

        self.logo = _secret("./SwiftNavLogo-Square.png")
        self.scene.add_actor(self.axes)
        self.scene.add_actor(self.logo)

    def init_tform_ned(self):
        self.tform.identity()
        self.tform.rotate_y(180.)
        self.tform.rotate_x(90.)

        self.logo_tform.identity()
        self.logo_tform.rotate_y(180.)
        self.logo_tform.rotate_x(90.)
    
    # Update the attitude representation.
    def update_attitude(self, y, p, r):
        # Update transform.
        self.init_tform_ned()
        # print("ATTITUDE", np.deg2rad(r), np.deg2rad(p), np.deg2rad(y))
        self.tform.rotate_x(r)
        self.tform.rotate_y(p)
        self.tform.rotate_z(y)
        self.logo_tform.rotate_x(r)
        self.logo_tform.rotate_y(p)
        self.logo_tform.rotate_z(y)
        self.logo_tform.scale(1, 0.75, 0.1)

        self.axes.user_transform = self.tform
        self.logo.user_transform = self.logo_tform

        # Update the plot.
        memoryview(self.est_yaw)[:-1] = memoryview(self.est_yaw)[1:]
        memoryview(self.est_pit)[:-1] = memoryview(self.est_pit)[1:]
        memoryview(self.est_rol)[:-1] = memoryview(self.est_rol)[1:]
        self.est_yaw[-1] = y
        self.est_pit[-1] = p
        self.est_rol[-1] = r

        # Update the attitude view at full rate.
        self.update_scheduler.schedule_update("render_attitude", self.scene.render)

    def update_biases(self, bx, by, bz):
        memoryview(self.bias_x)[:-1] = memoryview(self.bias_x)[1:]
        memoryview(self.bias_y)[:-1] = memoryview(self.bias_y)[1:]
        memoryview(self.bias_z)[:-1] = memoryview(self.bias_z)[1:]
        self.bias_x[-1] = bx 
        self.bias_y[-1] = by 
        self.bias_z[-1] = bz 

    def update_plots(self):
        self.last_plot_update_time = monotonic()

        self.angle_data.set_data('est_yaw', self.est_yaw)
        self.angle_data.set_data('est_pit', self.est_pit)
        self.angle_data.set_data('est_rol', self.est_rol)

        self.bias_data.set_data('bias_x', self.bias_x)
        self.bias_data.set_data('bias_y', self.bias_y)
        self.bias_data.set_data('bias_z', self.bias_z)
       
    def callback_orient_euler(self, sbp_msg, **metadata):
        y = sbp_msg.yaw / 1.e6
        p = sbp_msg.pitch / 1.e6 
        r = sbp_msg.roll / 1.e6
        bx = sbp_msg.yaw_accuracy
        by = sbp_msg.pitch_accuracy
        bz = sbp_msg.roll_accuracy
        self.update_attitude(y, p, r)
        self.update_biases(bx, by, bz)
        # Update the plots at reduced rate.
        if monotonic() - self.last_plot_update_time >= GUI_UPDATE_PERIOD:
            self.update_scheduler.schedule_update("attitude_plot_update", self.update_plots)


