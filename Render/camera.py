# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2020 Howetuft <howetuft@gmail.com>                      *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

"""This module implements a Camera object for Render workbench.

Camera object allows to take a snapshot of Coin Camera settings and to use them
later for rendering.
"""

from math import degrees, radians
from types import SimpleNamespace
import shlex

from pivy import coin
from PySide.QtCore import QT_TRANSLATE_NOOP
import FreeCAD as App
import FreeCADGui as Gui

from Render.base import (
    FeatureBase,
    PointableFeatureMixin,
    Prop,
    ViewProviderBase,
    CtxMenuItem,
    PointableViewProviderMixin,
    CoinShapeViewProviderMixin,
)


# Enumeration of allowed values for ViewportMapping parameter (see Coin
# documentation)
# Nota: Keep following tuple in original order, as relationship between
# values and indexes order matters and is used for reverse transcoding
VIEWPORTMAPPINGENUM = (
    "CROP_VIEWPORT_FILL_FRAME",
    "CROP_VIEWPORT_LINE_FRAME",
    "CROP_VIEWPORT_NO_FRAME",
    "ADJUST_CAMERA",
    "LEAVE_ALONE",
)


# ===========================================================================


class Camera(PointableFeatureMixin, FeatureBase):
    """A camera for rendering.

    This object allows to record camera settings from the Coin camera, and to
    reuse them for rendering.

    Camera Orientation is defined by a Rotation Axis and a Rotation Angle,
    applied to 'default camera'.
    Default camera looks from (0,0,1) towards the origin (target is (0,0,-1),
    and the up direction is (0,1,0).

    For more information, see Coin documentation, Camera section.
    <https://developer.openinventor.com/UserGuides/Oiv9/Inventor_Mentor/Cameras_and_Lights/Cameras.html>
    """

    VIEWPROVIDER = "ViewProviderCamera"

    PROPERTIES = {
        "Projection": Prop(
            "App::PropertyEnumeration",
            "Camera",
            QT_TRANSLATE_NOOP(
                "Render", "Type of projection: Perspective/Orthographic"
            ),
            ("Perspective", "Orthographic"),
        ),
        "ViewportMapping": Prop(
            "App::PropertyEnumeration",
            "Camera",
            QT_TRANSLATE_NOOP("Render", "(See Coin documentation)"),
            VIEWPORTMAPPINGENUM,
        ),
        "AspectRatio": Prop(
            "App::PropertyFloat",
            "Camera",
            QT_TRANSLATE_NOOP("Render", "Ratio width/height of the camera."),
            1.0,
        ),
        "NearDistance": Prop(
            "App::PropertyDistance",
            "Camera",
            QT_TRANSLATE_NOOP("Render", "Near distance, for clipping"),
            0.0,
        ),
        "FarDistance": Prop(
            "App::PropertyDistance",
            "Camera",
            QT_TRANSLATE_NOOP("Render", "Far distance, for clipping"),
            200.0,
        ),
        "FocalDistance": Prop(
            "App::PropertyDistance",
            "Camera",
            QT_TRANSLATE_NOOP("Render", "Focal distance"),
            100.0,
        ),
        "Height": Prop(
            "App::PropertyLength",
            "Camera",
            QT_TRANSLATE_NOOP("Render", "Height, for orthographic camera"),
            5.0,
        ),
        "HeightAngle": Prop(
            "App::PropertyAngle",
            "Camera",
            QT_TRANSLATE_NOOP(
                "Render",
                "Height angle, for perspective camera, in "
                "degrees. Important: This value will be sent as "
                "'Field of View' to the renderers.",
            ),
            60,
        ),
    }

    def on_create_cb(self, fpo, viewp, **kwargs):
        """Complete 'create' (callback)."""
        if App.GuiUp:
            viewp.set_camera_from_gui()
        else:
            set_cam_from_coin_string(fpo, DEFAULT_CAMERA_STRING)


# ===========================================================================


class ViewProviderCamera(
    CoinShapeViewProviderMixin, PointableViewProviderMixin, ViewProviderBase
):
    """View Provider of Camera class."""

    ICON = ":/icons/camera-photo.svg"
    CONTEXT_MENU = [
        CtxMenuItem(
            QT_TRANSLATE_NOOP("Render", "Set GUI to this camera"),
            "set_gui_from_camera",
        ),
        CtxMenuItem(
            QT_TRANSLATE_NOOP("Render", "Set this camera to GUI"),
            "set_camera_from_gui",
        ),
    ]
    SIZE = 5
    HEIGHT = 10
    COIN_SHAPE_POINTS = (
        (-SIZE * 2, +SIZE, 0),  # Front rectangle
        (+SIZE * 2, +SIZE, 0),  # Front rectangle
        (+SIZE * 2, -SIZE, 0),  # Front rectangle
        (-SIZE * 2, -SIZE, 0),  # Front rectangle
        (-SIZE * 2, +SIZE, 0),  # Front rectangle
        (-SIZE * 2, +SIZE, 0),  # Left triangle
        (0, 0, HEIGHT * 2),  # Left triangle
        (-SIZE * 2, -SIZE, 0),  # Left triangle
        (+SIZE * 2, +SIZE, 0),  # Right triangle
        (0, 0, HEIGHT * 2),  # Right triangle
        (+SIZE * 2, -SIZE, 0),  # Right triangle
        (-SIZE * 1.8, 1.2 * +SIZE, 0),  # Up triangle (arrow)
        (0, 1.4 * +SIZE, 0),  # Up triangle (arrow)
        (+SIZE * 1.8, 1.2 * +SIZE, 0),  # Up triangle (arrow)
        (-SIZE * 1.8, 1.2 * +SIZE, 0),  # Up triangle (arrow)
    )
    COIN_SHAPE_VERTICES = [5, 3, 3, 4]
    COIN_SHAPE_WIREFRAME = True

    def set_camera_from_gui(self):
        """Set this camera from GUI camera."""
        assert App.GuiUp, "Cannot set camera from GUI: GUI is down"
        fpo = self.fpo
        node = Gui.ActiveDocument.ActiveView.getCameraNode()
        typ = node.getTypeId()
        if typ == coin.SoPerspectiveCamera.getClassTypeId():
            fpo.Projection = "Perspective"
            fpo.HeightAngle = degrees(float(node.heightAngle.getValue()))
        elif typ == coin.SoOrthographicCamera.getClassTypeId():
            fpo.Projection = "Orthographic"
            fpo.Height = float(node.height.getValue())
        else:
            raise ValueError("Unknown camera type")

        pos = App.Vector(node.position.getValue())
        rot = App.Rotation(*node.orientation.getValue().getValue())
        fpo.Placement = App.Placement(pos, rot)

        fpo.NearDistance = float(node.nearDistance.getValue())
        fpo.FarDistance = float(node.farDistance.getValue())
        fpo.FocalDistance = float(node.focalDistance.getValue())
        fpo.AspectRatio = float(node.aspectRatio.getValue())
        index = node.viewportMapping.getValue()
        fpo.ViewportMapping = VIEWPORTMAPPINGENUM[index]

    def set_gui_from_camera(self):
        """Set GUI camera to this camera."""
        assert App.GuiUp, "Cannot set GUI from camera: GUI is down"

        fpo = self.fpo

        Gui.ActiveDocument.ActiveView.setCameraType(fpo.Projection)

        node = Gui.ActiveDocument.ActiveView.getCameraNode()

        node.position.setValue(fpo.Placement.Base)
        rot = fpo.Placement.Rotation
        axis = coin.SbVec3f(rot.Axis.x, rot.Axis.y, rot.Axis.z)
        node.orientation.setValue(axis, rot.Angle)

        node.nearDistance.setValue(float(fpo.NearDistance))
        node.farDistance.setValue(float(fpo.FarDistance))
        node.focalDistance.setValue(float(fpo.FocalDistance))
        node.aspectRatio.setValue(float(fpo.AspectRatio))
        node.viewportMapping.setValue(getattr(node, fpo.ViewportMapping))

        if fpo.Projection == "Orthographic":
            node.height.setValue(float(fpo.Height))
        elif fpo.Projection == "Perspective":
            node.heightAngle.setValue(radians(float(fpo.HeightAngle)))


# ===========================================================================


def set_cam_from_coin_string(cam, camstr):
    """Set a Camera object from a Coin camera string.

    Args:
        cam -- The Camera to set (as a Camera FeaturePython object)
        camstr -- The Coin-formatted camera string

    camstr should contain a string in Coin/OpenInventor format, for instance:
    #Inventor V2.1 ascii


    PerspectiveCamera {
     viewportMapping ADJUST_CAMERA
     position 0 -1.3207401 0.82241058
     orientation 0.99999666 0 0  0.26732138
     nearDistance 1.6108983
     farDistance 6611.4492
     aspectRatio 1
     focalDistance 5
     heightAngle 0.78539819

    }

    or (ortho camera):
    #Inventor V2.1 ascii


    OrthographicCamera {
     viewportMapping ADJUST_CAMERA
     position 0 0 1
     orientation 0 0 1  0
     nearDistance 0.99900001
     farDistance 1.001
     aspectRatio 1
     focalDistance 5
     height 4.1421356

    }
    """
    # Split, clean and tokenize
    camdata = [
        y
        for y in [shlex.split(x, comments=True) for x in camstr.split("\n")]
        if y
    ]
    camdict = {y[0]: y[1:] for y in camdata}

    cam.Projection = camdata[0][0][0:-6]  # Data should start with Cam Type...
    assert cam.Projection in (
        "Perspective",
        "Orthographic",
    ), "Invalid camera header in camera string"
    try:
        pos = App.Vector(camdict["position"][0:3])
        rot = App.Rotation(
            App.Vector(camdict["orientation"][0:3]),
            degrees(float(camdict["orientation"][3])),
        )
        cam.Placement = App.Placement(pos, rot)
        cam.FocalDistance = float(camdict["focalDistance"][0])
    except KeyError as err:
        raise ValueError(f"Missing field in camera string: {err}") from err

    # It may happen that aspect ratio and viewport mapping are not set in
    # camstr...
    try:
        cam.AspectRatio = float(camdict["aspectRatio"][0])
    except KeyError:
        cam.AspectRatio = 1.0
    try:
        cam.ViewportMapping = str(camdict["viewportMapping"][0])
    except KeyError:
        cam.ViewportMapping = "ADJUST_CAMERA"

    # It may also happen that near & far distances are not set in camstr...
    try:
        cam.NearDistance = float(camdict["nearDistance"][0])
    except KeyError:
        pass
    try:
        cam.FarDistance = float(camdict["farDistance"][0])
    except KeyError:
        pass

    if cam.Projection == "Orthographic":
        cam.Height = float(camdict["height"][0])
    elif cam.Projection == "Perspective":
        cam.HeightAngle = degrees(float(camdict["heightAngle"][0]))


def get_cam_from_coin_string(camstr):
    """Get a Camera object in view.Source format from a Coin camera string.

    The same as set_cam_from_coin_string, but result is created and returned,
    instead of being ref-passed in first parameter.
    """
    res = SimpleNamespace()
    set_cam_from_coin_string(res, camstr)
    return res


def get_coin_string_from_cam(cam):
    """Return camera data in Coin string format.

    Args:
        cam -- The Camera object to generate Coin string from.
    """

    def check_enum(field):
        """Check whether the enum field value is valid."""
        assert (
            getattr(cam, field) in Camera.PROPERTIES[field].Default
        ), f"Camera: Invalid {field} value"

    check_enum("Projection")
    check_enum("ViewportMapping")

    base = cam.Placement.Base
    rot = cam.Placement.Rotation

    if cam.Projection == "Orthographic":
        height = f" height {float(cam.Height)}"
    elif cam.Projection == "Perspective":
        height = f" heightAngle {radians(cam.HeightAngle)}"
    else:
        height = ""

    res = [
        "#Inventor V2.1 ascii\n\n\n",
        f"{cam.Projection}Camera {{",
        f" viewportMapping {cam.ViewportMapping}",
        f" position {base[0]} {base[1]} {base[2]}",
        f" orientation {rot.Axis[0]} {rot.Axis[1]} {rot.Axis[2]} {rot.Angle}",
        f" nearDistance {float(cam.NearDistance)}",
        f" farDistance {float(cam.FarDistance)}",
        f" aspectRatio {float(cam.AspectRatio)}",
        f" focalDistance {float(cam.FocalDistance)}",
        height,
        "}}\n",
    ]

    return "\n".join(res)


def retrieve_legacy_camera(project):
    """Transform legacy camera project attribute into Camera object.

    This function is provided for backward compatibility (when camera
    information was stored as a string in a project's property).
    The resulting Camera object is created in the current project.

    Args:
        project -- The Rendering Project where to find legacy camera
            information
    """
    assert isinstance(
        project.Camera, str
    ), "Project's Camera property should be a string"
    _, fpo, _ = Camera.create()
    set_cam_from_coin_string(fpo, project.Camera)


# A default camera...
DEFAULT_CAMERA_STRING = """\
#Inventor V2.1 ascii

OrthographicCamera {
  viewportMapping ADJUST_CAMERA
  position -0 -0 100
  orientation 0 0 1  0
  aspectRatio 1
  focalDistance 100
  height 100
}
"""
