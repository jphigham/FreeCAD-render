# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2019 Yorik van Havre <yorik@uncreated.net>              *
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

"""Cycles renderer for FreeCAD"""

# Suggested documentation links:
# NOTE Standalone Cycles is experimental, so no documentation is available
# Instead, documentation must be searched directly in code (via reverse
# engineering), and in the examples provided with it.
# Here are some links:
# https://wiki.blender.org/wiki/Source/Render/Cycles/Standalone
# https://developer.blender.org/diffusion/C/browse/master/src/
# https://developer.blender.org/diffusion/C/browse/master/src/render/nodes.cpp
# https://developer.blender.org/diffusion/C/browse/master/src/app/cycles_xml.cpp
# https://developer.blender.org/diffusion/C/browse/master/examples/
#
# A few hints (my understanding of cycles_standalone):
#
# The 'int main()' is in 'src/app/cycles_standalone.cpp' (but you may not be
# most interested in it)
#
# The xml input file is processed by 'src/app/cycles_xml.cpp' functions.
# The entry point is 'xml_read_file', which cascades to 'xml_read_scene' via
# 'xml_read_include' function.
# 'xml_read_scene' is a key function to study: it recognizes and dispatches all
# the possible nodes to 'xml_read_*' node-specialized parsing functions.
# A few more 'xml_read_*' (including 'xml_read_node' are defined in
# /src/graph/node_xml.cpp


import os
from math import degrees, isclose

import FreeCAD as App


# ===========================================================================
#                             Write functions
# ===========================================================================


def write_object(name, mesh, color, alpha):
    """Compute a string in the format of Cycles, that represents a FreeCAD
    object
    """
    # This is where you write your object/view in the format of your
    # renderer. "obj" is the real 3D object handled by this project, not
    # the project itself. This is your only opportunity
    # to write all the data needed by your object (geometry, materials, etc)
    # so make sure you include everything that is needed

    snippet1 = """
    <!-- Generated by FreeCAD - Object '{n}' -->
    <shader name="{n}_mat">
        <diffuse_bsdf name="{n}_bsdf" color="{c[0]}, {c[1]}, {c[2]}"/>"""

    snippet2a = """
        <transparent_bsdf name="{n}_trans" color="1.0, 1.0, 1.0"/>
        <mix_closure name="{n}_mix" fac="{a}"/>
        <connect from="{n}_trans bsdf"  to="{n}_mix closure1"/>
        <connect from="{n}_bsdf bsdf"   to="{n}_mix closure2"/>
        <connect from="{n}_mix closure" to="output surface"/>
    </shader>"""

    snippet2b = """
        <connect from="{n}_bsdf bsdf"   to="output surface"/>
    </shader>"""

    snippet3 = """
    <state shader="{n}_mat">
        <mesh P="{p}"
              nverts="{i}"
              verts="{v}"/>
    </state>\n"""

    snippet = snippet1 + (snippet2a if alpha < 1 else snippet2b) + snippet3

    points = ["{0.x} {0.y} {0.z}".format(p) for p in mesh.Topology[0]]
    verts = ["{} {} {}".format(*v) for v in mesh.Topology[1]]
    nverts = ["3"] * len(verts)

    return snippet.format(n=name,
                          c=color,
                          a=alpha,
                          p="  ".join(points),
                          i="  ".join(nverts),
                          v="  ".join(verts))


def write_camera(name, pos, updir, target):
    """Compute a string in the format of Cycles, that represents a camera"""

    # This is where you create a piece of text in the format of
    # your renderer, that represents the camera.

    # Cam rotation is angle(deg) axisx axisy axisz
    # Scale needs to have z inverted to behave like a decent camera.
    # No idea what they have been doing at blender :)
    snippet = """
    <!-- Generated by FreeCAD - Camera '{n}' -->
    <transform rotate="{a} {r.x} {r.y} {r.z}"
               translate="{p.x} {p.y} {p.z}"
               scale="1 1 -1">
        <camera type="perspective"/>
    </transform>"""

    return snippet.format(n=name,
                          a=degrees(pos.Rotation.Angle),
                          r=pos.Rotation.Axis,
                          p=pos.Base)


def write_pointlight(name, pos, color, power):
    """Compute a string in the format of Cycles, that represents a
    PointLight object
    """
    # This is where you write the renderer-specific code
    # to export a point light in the renderer format

    snippet = """
    <!-- Generated by FreeCAD - Pointlight '{n}' -->
    <shader name="{n}_shader">
        <emission name="{n}_emit"
                  color="{c[0]} {c[1]} {c[2]}"
                  strength="{s}"/>
        <connect from="{n}_emit emission"
                 to="output surface"/>
    </shader>
    <state shader="{n}_shader">
        <light type="point"
               co="{p.x} {p.y} {p.z}"
               strength="1 1 1"/>
    </state>\n"""

    return snippet.format(n=name,
                          c=color,
                          p=pos,
                          s=power*100)


def write_arealight(name, pos, size_u, size_v, color, power):
    """Compute a string in the format of Cycles, that represents an
    Area Light object
    """
    # Axis
    rot = pos.Rotation
    axis1 = rot.multVec(App.Vector(1, 0.0, 0.0))
    axis2 = rot.multVec(App.Vector(0.0, 1.0, 0.0))
    direction = axis1.cross(axis2)

    snippet = """
    <!-- Generated by FreeCAD - Area light '{n}' -->
    <shader name="{n}_shader">
        <emission name="{n}_emit"
                  color="{c[0]} {c[1]} {c[2]}"
                  strength="{s}"/>
        <connect from="{n}_emit emission"
                 to="output surface"/>
    </shader>
    <state shader="{n}_shader">
        <light type="area"
               co="{p.x} {p.y} {p.z}"
               strength="1 1 1"
               axisu="{u.x} {u.y} {u.z}"
               axisv="{v.x} {v.y} {v.z}"
               sizeu="{a}"
               sizev="{b}"
               size="1"
               dir="{d.x} {d.y} {d.z}" />
    </state>\n"""

    return snippet.format(n=name,
                          c=color,
                          p=pos.Base,
                          s=power*100,
                          u=axis1,
                          v=axis2,
                          a=size_u,
                          b=size_v,
                          d=direction)


def write_sunskylight(name, direction, distance, turbidity):
    """Compute a string in the format of Cycles, that represents an
    Sunsky Light object (Hosek-Wilkie)
    """
    # We model sun_sky with a sun light and a sky texture for world
    # TODO At now, only sky is modeled, not sun.

    # For sky texture, direction must be normalized
    assert direction.Length
    _dir = App.Vector(direction)
    _dir.normalize()
    snippet = """
    <!-- Generated by FreeCAD - Sun_sky light '{n}' -->
    <background name="sky_bg">
          <background name="sky_bg" />
          <sky_texture name="sky_tex"
                       type="hosek_wilkie"
                       turbidity="{t}"
                       sun_direction="{d.x}, {d.y}, {d.z}" />
          <connect from="sky_tex color" to="sky_bg color" />
          <connect from="sky_bg background" to="output surface" />
    </background>
    """
    return snippet.format(n=name,
                          d=_dir,
                          t=turbidity)


# ===========================================================================
#                              Render function
# ===========================================================================


def render(project, prefix, external, output, width, height):
    """Run Cycles

    Params:
    - project:  the project to render
    - prefix:   a prefix string for call (will be inserted before path to Lux)
    - external: a boolean indicating whether to call UI (true) or console
                (false) version of Lux
    - width:    rendered image width, in pixels
    - height:   rendered image height, in pixels

    Return: path to output image file
    """

    # Here you trigger a render by firing the renderer
    # executable and passing it the needed arguments, and
    # the file it needs to render

    params = App.ParamGet("User parameter:BaseApp/Preferences/Mod/Render")
    prefix = params.GetString("Prefix", "")
    if prefix:
        prefix += " "
    rpath = params.GetString("CyclesPath", "")
    args = params.GetString("CyclesParameters", "")
    args += " --output " + output
    if not external:
        args += " --background"
    if not rpath:
        App.Console.PrintError("Unable to locate renderer executable. "
                               "Please set the correct path in "
                               "Edit -> Preferences -> Render\n")
        return ""
    args += " --width " + str(width)
    args += " --height " + str(height)
    cmd = prefix + rpath + " " + args + " " + project.PageResult
    App.Console.PrintMessage(cmd+'\n')
    os.system(cmd)

    return output
