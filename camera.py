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

"""This module implements a Camera object, which allows to take a snapshot
of Coin Camera settings and use them later for rendering"""

from collections import namedtuple
from math import degrees, radians
import shlex

from pivy import coin
from PySide.QtGui import QAction
from PySide.QtCore import QT_TRANSLATE_NOOP, QObject, SIGNAL
import FreeCAD as App
import FreeCADGui as Gui
import Part


# ===========================================================================


def create_camera():
    """Create a Camera object in active document"""

    fpo = App.ActiveDocument.addObject("Part::FeaturePython", "Camera")
    Camera(fpo)
    viewp = ViewProviderCamera(fpo.ViewObject)
    if App.GuiUp:
        viewp.set_camera_from_gui()
    App.ActiveDocument.recompute()
    return fpo

# ===========================================================================

class Camera:

    """A camera for rendering.

This object allows to record camera settings from the Coin camera, and to reuse them
for rendering.

Camera Orientation is defined by a Rotation Axis and a Rotation Angle, applied to
'default camera'.
Default camera looks from (0,0,1) towards the origin, and the up direction
is (0,1,0).

For more information, see Coin documentation, Camera section.
(https://developer.openinventor.com/UserGuides/Oiv9/Inventor_Mentor/\
Cameras_and_Lights/Cameras.html)
    """

    # Enumeration of allowed values for ViewportMapping parameter (see Coin documentation)
    # Nota: Keep following tuple in original order, as relationship between values and
    # indexes matters and is used for reverse transcoding
    VIEWPORTMAPPINGENUM = ("CROP_VIEWPORT_FILL_FRAME", "CROP_VIEWPORT_LINE_FRAME",
                           "CROP_VIEWPORT_NO_FRAME", "ADJUST_CAMERA", "LEAVE_ALONE")

    Prop = namedtuple('Prop', ['Type', 'Group', 'Doc', 'Default'])

    # PythonFeature object properties
    PROPERTIES = {
        "Projection": Prop(
            "App::PropertyEnumeration",
            "Camera",
            QT_TRANSLATE_NOOP("Render", "Type of projection: Perspective/Orthographic"),
            ("Perspective", "Orthographic")),

        "Placement": Prop(
            "App::PropertyPlacement",
            "",
            QT_TRANSLATE_NOOP("Render", "Placement of camera"),
            App.Placement(App.Vector(0, 0, 0),
                          App.Vector(0, 0, 1),
                          0)),

        "ViewportMapping": Prop(
            "App::PropertyEnumeration",
            "Camera",
            QT_TRANSLATE_NOOP("Render", "(See Coin documentation)"),
            VIEWPORTMAPPINGENUM),

        "AspectRatio": Prop(
            "App::PropertyFloat",
            "Camera",
            QT_TRANSLATE_NOOP("Render", "Ratio width/height of the camera."),
            1.0),

        "NearDistance": Prop(
            "App::PropertyDistance",
            "Camera",
            QT_TRANSLATE_NOOP("Render", "Near distance, for clipping"),
            0.0),

        "FarDistance": Prop(
            "App::PropertyDistance",
            "Camera",
            QT_TRANSLATE_NOOP("Render", "Far distance, for clipping"),
            200.0),

        "FocalDistance": Prop(
            "App::PropertyDistance",
            "Camera",
            QT_TRANSLATE_NOOP("Render", "Focal distance"),
            100.0),

        "Height": Prop(
            "App::PropertyLength",
            "Camera",
            QT_TRANSLATE_NOOP("Render", "Height, for orthographic camera"),
            5.0),

        "HeightAngle": Prop(
            "App::PropertyAngle",
            "Camera",
            QT_TRANSLATE_NOOP("Render", "Height angle, for perspective camera"),
            60),

        "Shape": Prop(
            "Part::PropertyPartShape",
            "",
            QT_TRANSLATE_NOOP("Render", "Shape of the camera"),
            None),

    }
    # ~PythonFeature object properties

    @classmethod
    def set_properties(cls, fpo):
        """Set underlying PythonFeature object's properties"""
        for name in cls.PROPERTIES.keys() - set(fpo.PropertiesList):
            fields = cls.PROPERTIES[name]
            prop = fpo.addProperty(fields.Type, name, fields.Group, fields.Doc, 0)
            setattr(prop, name, fields.Default)


    def __init__(self, fpo):
        """
        Camera Initializer

        Arguments
        ---------
        fpo: a FeaturePython object created with FreeCAD.addObject
        """
        self.type = "Camera"
        fpo.Proxy = self
        self.set_properties(fpo)

    def onDocumentRestored(self, fpo):
        """Callback triggered when document is restored"""
        self.type = "Camera"
        fpo.Proxy = self
        self.set_properties(fpo)

    def execute(self, fpo):
        """Callback triggered on document recomputation (mandatory).
        It mainly draws the camera graphical representation"""

        size = 5
        height = 10
        # Square
        poly1 = Part.makePolygon([(-size * 2, size, 0),
                                  (size * 2, size, 0),
                                  (size * 2, -size, 0),
                                  (-size * 2, -size, 0),
                                  (-size * 2, size, 0)])
        # Triangle 1
        poly2 = Part.makePolygon([(-size * 2, size, 0),
                                  (0, 0, height * 2),
                                  (-size * 2, -size, 0),
                                  (-size * 2, size, 0)])
        # Triangle 2
        poly3 = Part.makePolygon([(size * 2, size, 0),
                                  (0, 0, height * 2),
                                  (size * 2, -size, 0),
                                  (size * 2, size, 0)])
        # Arrow (up direction)
        poly4 = Part.makePolygon([(-size * 1.8, 1.2 * size, 0),
                                  (0, 1.4 * size, 0),
                                  (size * 1.8, 1.2 * size, 0),
                                  (-size * 1.8, 1.2 * size, 0)])

        fpo.Shape = Part.makeCompound([poly1, poly2, poly3, poly4])


# ===========================================================================


class ViewProviderCamera:
    """View Provider of Camera class"""

    def __init__(self, vobj):
        vobj.Proxy = self
        self.fpo = vobj.Object # Related FeaturePython object

    def attach(self, vobj):
        """Callback triggered when object is created/restored"""
        self.fpo = vobj.Object

    def getDisplayModes(self, _):
        """Return a list of display modes"""
        return ["Shaded"]

    def getDefaultDisplayMode(self):
        """Return the name of the default display mode.  It must be defined in
        getDisplayModes."""
        return "Shaded"

    def setDisplayMode(self, mode):
        """Map the display mode defined in attach with those defined in getDisplayModes.
        Since they have the same names nothing needs to be done.
        This method is optional."""
        return mode

    def getIcon(self):
        """Return the icon which will appear in the tree view."""
        return ":/icons/camera-photo.svg"

    def setupContextMenu(self, vobj, menu):
        """Setup the context menu associated to the object in tree view"""
        action1 = QAction(QT_TRANSLATE_NOOP("Render", "Set GUI to this camera"),
                          menu)
        QObject.connect(action1,
                        SIGNAL("triggered()"),
                        self.set_gui_from_camera)
        menu.addAction(action1)

        action2 = QAction(QT_TRANSLATE_NOOP("Render", "Set this camera to GUI"),
                          menu)
        QObject.connect(action2,
                        SIGNAL("triggered()"),
                        self.set_camera_from_gui)
        menu.addAction(action2)

    def updateData(self, fpo, prop):
        """Callback triggered when properties are modified"""
        return

    def set_camera_from_gui(self):
        """Set this camera from GUI camera"""

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
        fpo.ViewportMapping = Camera.VIEWPORTMAPPINGENUM[node.viewportMapping.getValue()]

    def set_gui_from_camera(self):
        """Set GUI camera to this camera"""

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

    def __getstate__(self):
        """Called while saving the document"""
        return None

    def __setstate__(self, state):
        """Called while restoring document"""
        return None



# ===========================================================================


def set_cam_from_coin_string(cam, camstr):
    """Set a Camera object from a string containing a camera description in Open Inventor
    format

    camstr: a string in OpenInventor format, ex:
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

    }"""

    # Split, clean and tokenize
    camdata = [y for y in [shlex.split(x, comments=True)\
                            for x in camstr.split('\n')] if y]
    camdict = {y[0]:y[1:] for y in camdata}

    cam.Projection = camdata[0][0][0:-6] # Data block should start with Cam Type...
    assert cam.Projection in ('Perspective', 'Orthographic'),\
        "Invalid camera header in camera string"
    try:
        pos = App.Vector(camdict["position"][0:3])
        rot = App.Rotation(App.Vector(camdict["orientation"][0:3]),
                               degrees(float(camdict["orientation"][3])))
        cam.Placement = App.Placement(pos, rot)
        cam.FocalDistance = float(camdict["focalDistance"][0])
        cam.AspectRatio = float(camdict["aspectRatio"][0])
        cam.ViewportMapping = str(camdict["viewportMapping"][0])
    except KeyError as err:
        raise ValueError("Missing field in camera string: {}".format(err))

    # It may happen that near & far distances are not set in camstr...
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


def get_coin_string_from_cam(cam):
    """Return camera data in Coin string format

    cam: a Camera object"""

    def check_enum(field):
        """Check if the enum field value is valid"""
        assert getattr(cam, field) in Camera.PROPERTIES[field].Default,\
                "Invalid %s value" %field

    check_enum("Projection")
    check_enum("ViewportMapping")

    res = list()
    res.append("#Inventor V2.1 ascii\n\n\n")
    res.append("{}Camera {{".format(cam.Projection))
    res.append(" viewportMapping {}".format(cam.ViewportMapping))
    res.append(" position {} {} {}".format(*cam.Placement.Base))
    res.append(" orientation {} {} {} {}".format(*cam.Placement.Rotation.Axis,
                                                 cam.Placement.Rotation.Angle))
    res.append(" nearDistance {}".format(float(cam.NearDistance)))
    res.append(" farDistance {}".format(float(cam.FarDistance)))
    res.append(" aspectRatio {}".format(float(cam.AspectRatio)))
    res.append(" focalDistance {}".format(float(cam.FocalDistance)))
    if cam.Projection == "Orthographic":
        res.append(" height {}".format(float(cam.Height)))
    elif cam.Projection == "Perspective":
        res.append(" heightAngle {}".format(radians(cam.HeightAngle)))
    res.append("}\n")
    return '\n'.join(res)

def retrieve_legacy_camera(project):
    """For backward compatibility: Retrieve legacy camera information in rendering projects
    and transform it into Camera object"""
    assert isinstance(project.Camera, str),\
        "Project's Camera property should contain a string"""
    fpo = create_camera()
    set_cam_from_coin_string(fpo, project.Camera)
