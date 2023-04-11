"""OpenGL drawing functions"""

import math
import platform
import sys
from subprocess import call
from typing import Sequence

from OpenGL import GL
from OpenGL.GLU import (
    GLU_TESS_BEGIN,
    GLU_TESS_COMBINE,
    GLU_TESS_END,
    GLU_TESS_VERTEX,
    GLU_TESS_WINDING_ODD,
    GLU_TESS_WINDING_RULE,
    gluDeleteTess,
    gluNewTess,
    gluTessBeginContour,
    gluTessBeginPolygon,
    gluTessCallback,
    gluTessEndContour,
    gluTessEndPolygon,
    gluTessProperty,
    gluTessVertex,
)
from PyQt5.QtOpenGL import QGLFormat, QGLWidget  # pylint: disable=E0611
from PyQt5.QtWidgets import QMessageBox  # pylint: disable=E0611

from .calc import (
    angle_of_line,
    bulge_points,
    calc_distance,
    calc_distance3d,
    found_next_open_segment_point,
    found_next_point_on_segment,
    found_next_segment_point,
    found_next_tab_point,
    line_center_2d,
    line_center_3d,
    point_of_line3d,
)
from .dxfcolors import dxfcolors
from .ext.HersheyFonts.HersheyFonts import HersheyFonts
from .preview_plugins.gcode import GcodeParser
from .preview_plugins.hpgl import HpglParser
from .vc_types import VcSegment

font = HersheyFonts()
font.load_default_font()
font.normalize_rendering(6)


class GLWidget(QGLWidget):
    """customized GLWidget."""

    GL_MULTISAMPLE = 0x809D
    version_printed = False
    screen_w = 100
    screen_h = 100
    aspect = 1.0
    rot_x = -20.0
    rot_y = -30.0
    rot_z = 0.0
    rot_x_last = rot_x
    rot_y_last = rot_y
    rot_z_last = rot_z
    trans_x = 0.0
    trans_y = 0.0
    trans_z = 0.0
    trans_x_last = trans_x
    trans_y_last = trans_y
    trans_z_last = trans_z
    scale_xyz = 1.0
    scale = 1.0
    scale_last = scale
    ortho = False
    mbutton = None
    mpos = None
    mouse_pos_x = 0
    mouse_pos_y = 0
    selector_mode = ""
    selection = ()
    selection_set = ()
    size_x = 0
    size_y = 0
    retina = False
    wheel_scale = 0.1

    def __init__(self, project: dict, update_drawing):
        """init function."""
        self.project: dict = project
        self.project["gllist"] = []

        my_format = QGLFormat.defaultFormat()
        my_format.setSampleBuffers(True)
        QGLFormat.setDefaultFormat(my_format)
        if not QGLFormat.hasOpenGL():
            QMessageBox.information(
                self.project["window"],
                "OpenGL using samplebuffers",
                "This system does not support OpenGL.",
            )
            sys.exit(0)

        super(GLWidget, self).__init__()
        self.startTimer(40)
        self.update_drawing = update_drawing
        self.setMouseTracking(True)
        if platform.system().lower() == "darwin":
            self.retina = not call(
                "system_profiler SPDisplaysDataType 2>/dev/null | grep -i 'retina' >/dev/null",
                shell=True,
            )
        self.wheel_scale = 0.005 if self.retina else 0.1

    def initializeGL(self) -> None:  # pylint: disable=C0103
        """glinit function."""

        version = GL.glGetString(GL.GL_VERSION).decode()
        if not self.version_printed:
            print(f"OpenGL-Version: {version}")
            self.version_printed = True

        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()

        if self.frameGeometry().width() == 0:
            self.aspect = 1.0
        else:
            self.aspect = self.frameGeometry().height() / self.frameGeometry().width()

        height = 0.2
        width = height * self.aspect

        if self.ortho:
            GL.glOrtho(
                -height * 2.5, height * 2.5, -width * 2.5, width * 2.5, -1000, 1000
            )
        else:
            GL.glFrustum(-height, height, -width, width, 0.5, 100.0)

        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()
        GL.glClearColor(0.0, 0.0, 0.0, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glClearDepth(1.0)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_CULL_FACE)
        GL.glDepthFunc(GL.GL_LEQUAL)
        GL.glDepthMask(GL.GL_TRUE)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glEnable(GL.GL_COLOR_MATERIAL)
        GL.glColorMaterial(GL.GL_FRONT_AND_BACK, GL.GL_AMBIENT_AND_DIFFUSE)
        if int(version.split(".")[0]) >= 2:
            GL.glEnable(GL.GL_RESCALE_NORMAL)
            GL.glEnable(GLWidget.GL_MULTISAMPLE)
        GL.glLight(GL.GL_LIGHT0, GL.GL_POSITION, (0, 0, 0, 1))
        GL.glLightfv(GL.GL_LIGHT0, GL.GL_AMBIENT, (0.1, 0.1, 0.1, 1))
        GL.glLightfv(GL.GL_LIGHT0, GL.GL_DIFFUSE, (1, 1, 1, 1))
        GL.glEnable(GL.GL_LIGHTING)
        GL.glEnable(GL.GL_LIGHT0)

    def resizeGL(self, width, height) -> None:  # pylint: disable=C0103
        """glresize function."""
        if self.retina:
            self.screen_w = width / 2
            self.screen_h = height / 2
        else:
            self.screen_w = width
            self.screen_h = height
        GL.glViewport(0, 0, width, height)
        self.initializeGL()

    def draw_tool(self, tool_pos, spindle, diameter) -> None:  # pylint: disable=C0103
        blades = 2
        radius = diameter / 2.0
        height = max(
            -self.project["setup"]["mill"]["depth"] + 5,
            diameter * 3,
        )
        shaft_height = height * 2
        angle = -self.project["simulation_cnt"]
        self.project["simulation_cnt"] += 15

        GL.glPushMatrix()
        GL.glTranslatef(tool_pos[0], tool_pos[1], tool_pos[2])
        if spindle != "OFF" and self.project["setup"]["machine"]["mode"] == "mill":
            GL.glRotatef(angle, 0.0, 0.0, 1.0)

        if self.project["setup"]["machine"]["mode"] == "mill":
            climp = 0.4 * radius
            blade_h = 1.0 * radius
            asteps = 10
            rots = (height + climp) / climp / asteps

            # shaft
            GL.glColor4f(0.5, 0.5, 0.5, 1.0)
            GL.glBegin(GL.GL_TRIANGLE_STRIP)
            z_pos = 0.0
            angle = 0.0
            while angle < math.pi * 2:
                x_pos = radius * math.cos(angle)
                y_pos = radius * math.sin(angle)
                GL.glNormal3f(x_pos / radius, y_pos / radius, 0)
                GL.glVertex3f(x_pos, y_pos, height)
                GL.glVertex3f(x_pos, y_pos, height + shaft_height)
                angle += math.pi / 10
            x_pos = radius * math.cos(angle)
            y_pos = radius * math.sin(angle)
            GL.glNormal3f(x_pos / radius, y_pos / radius, 0)
            GL.glVertex3f(x_pos, y_pos, height)
            GL.glVertex3f(x_pos, y_pos, height + shaft_height)
            GL.glEnd()

            GL.glBegin(GL.GL_TRIANGLE_STRIP)
            z_pos = 0.0
            angle = 0.0
            while angle < math.pi * 2:
                x_pos = radius / 3 * math.cos(angle)
                y_pos = radius / 3 * math.sin(angle)
                GL.glNormal3f(x_pos / radius / 2, y_pos / radius / 2, 0)
                GL.glVertex3f(x_pos, y_pos, 1.0)
                GL.glVertex3f(x_pos, y_pos, height)
                angle += math.pi / 10
            x_pos = radius / 3 * math.cos(angle)
            y_pos = radius / 3 * math.sin(angle)
            GL.glNormal3f(x_pos / radius / 2, y_pos / radius / 2, 0)
            GL.glVertex3f(x_pos, y_pos, 1.0)
            GL.glVertex3f(x_pos, y_pos, height)
            GL.glEnd()

            # blades
            start_angle = 0.0
            while start_angle < math.pi * 2:
                GL.glNormal3f(0, 0, -1)
                GL.glBegin(GL.GL_TRIANGLE_STRIP)
                z_pos = 0.0
                angle = start_angle
                while angle < math.pi * rots + start_angle:
                    x_pos = radius * math.cos(angle)
                    y_pos = radius * math.sin(angle)
                    GL.glNormal3f(x_pos / radius, y_pos / radius, -0.5)
                    GL.glVertex3f(0, 0, z_pos)
                    GL.glVertex3f(x_pos, y_pos, z_pos)
                    z_pos = z_pos + climp
                    angle += math.pi / asteps
                GL.glEnd()

                GL.glNormal3f(0, 0, 1)
                GL.glBegin(GL.GL_TRIANGLE_STRIP)
                z_pos = blade_h
                angle = start_angle
                while angle < math.pi * rots + start_angle:
                    x_pos = radius * math.cos(angle)
                    y_pos = radius * math.sin(angle)
                    GL.glNormal3f(x_pos / radius, y_pos / radius, 0.5)
                    GL.glVertex3f(0, 0, z_pos)
                    GL.glVertex3f(x_pos, y_pos, z_pos)
                    z_pos = z_pos + climp
                    angle += math.pi / asteps
                GL.glEnd()

                GL.glNormal3f(0, 0, 1)
                GL.glBegin(GL.GL_TRIANGLE_STRIP)
                z_pos = 0.0
                angle = start_angle
                while angle < math.pi * rots + start_angle:
                    x_pos = radius * math.cos(angle)
                    y_pos = radius * math.sin(angle)
                    GL.glNormal3f(x_pos / radius, y_pos / radius, 0)
                    GL.glVertex3f(x_pos, y_pos, z_pos + blade_h)
                    GL.glVertex3f(x_pos, y_pos, z_pos)
                    z_pos = z_pos + climp
                    angle += math.pi / asteps
                GL.glEnd()

                start_angle += math.pi * 2 / blades
        else:
            # shaft
            GL.glColor4f(0.5, 0.5, 0.5, 1.0)
            GL.glBegin(GL.GL_TRIANGLE_STRIP)
            z_pos = 0.0
            angle = 0.0
            while angle < math.pi * 2:
                x_pos = (radius + 2) * math.cos(angle)
                y_pos = (radius + 2) * math.sin(angle)
                GL.glNormal3f(x_pos / (radius + 2), y_pos / (radius + 2), 0)
                GL.glVertex3f(x_pos, y_pos, height)
                GL.glVertex3f(x_pos, y_pos, height + shaft_height)
                angle += math.pi / 10
            x_pos = (radius + 2) * math.cos(angle)
            y_pos = (radius + 2) * math.sin(angle)
            GL.glNormal3f(x_pos / (radius + 2), y_pos / (radius + 2), 0)
            GL.glVertex3f(x_pos, y_pos, height)
            GL.glVertex3f(x_pos, y_pos, height + shaft_height)
            GL.glEnd()

            # laser
            if spindle != "OFF":
                GL.glColor4f(1.0, 0.0, 0.0, 0.5)
            else:
                GL.glColor4f(1.0, 1.0, 1.0, 0.2)
            GL.glBegin(GL.GL_TRIANGLE_STRIP)
            z_pos = 0.0
            angle = 0.0
            while angle < math.pi * 2:
                x_pos = radius * math.cos(angle)
                y_pos = radius * math.sin(angle)
                GL.glNormal3f(x_pos / radius, y_pos / radius, 0)
                GL.glVertex3f(x_pos, y_pos, 0)
                GL.glVertex3f(x_pos, y_pos, height)
                angle += math.pi / 10
            x_pos = radius * math.cos(angle)
            y_pos = radius * math.sin(angle)
            GL.glNormal3f(x_pos / radius, y_pos / radius, 0)
            GL.glVertex3f(x_pos, y_pos, 0)
            GL.glVertex3f(x_pos, y_pos, height)
            GL.glEnd()

        GL.glPopMatrix()

    def paintGL(self) -> None:  # pylint: disable=C0103
        """glpaint function."""
        min_max = self.project["minMax"]
        if not min_max:
            return

        GL.glNormal3f(0, 0, 1)

        self.size_x = max(min_max[2] - min_max[0], 0.1)
        self.size_y = max(min_max[3] - min_max[1], 0.1)
        self.scale = min(1.0 / self.size_x, 1.0 / self.size_y) / 1.4

        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glMatrixMode(GL.GL_MODELVIEW)

        GL.glPushMatrix()
        GL.glTranslatef(-self.trans_x, -self.trans_y, self.trans_z - 1.2)
        GL.glScalef(self.scale_xyz, self.scale_xyz, self.scale_xyz)
        GL.glRotatef(self.rot_x, 0.0, 1.0, 0.0)
        GL.glRotatef(self.rot_y, 1.0, 0.0, 0.0)
        GL.glRotatef(self.rot_z, 0.0, 0.0, 1.0)
        GL.glTranslatef(
            (-self.size_x / 2.0 - min_max[0]) * self.scale,
            (-self.size_y / 2.0 - min_max[1]) * self.scale,
            0.0,
        )
        GL.glScalef(self.scale, self.scale, self.scale)

        GL.glCallList(self.project["gllist"])

        GL.glNormal3f(0, 0, 1)
        if self.selection:
            if self.selector_mode == "start":
                # depth = self.project["setup"]["mill"]["depth"] - 0.1
                depth = 0.1
                GL.glLineWidth(5)
                GL.glColor4f(0.0, 1.0, 1.0, 1.0)
                GL.glBegin(GL.GL_LINES)
                GL.glVertex3f(self.selection[2][0] - 1, self.selection[2][1] - 1, depth)
                GL.glVertex3f(self.selection[2][0] + 1, self.selection[2][1] + 1, depth)
                GL.glVertex3f(self.selection[2][0] - 1, self.selection[2][1] + 1, depth)
                GL.glVertex3f(self.selection[2][0] + 1, self.selection[2][1] - 1, depth)
                GL.glEnd()
            elif self.selector_mode == "repair":
                if len(self.selection) > 4:
                    depth = 0.1
                    GL.glLineWidth(15)
                    GL.glColor4f(1.0, 0.0, 0.0, 1.0)
                    GL.glBegin(GL.GL_LINES)
                    GL.glVertex3f(self.selection[0], self.selection[1], depth)
                    GL.glVertex3f(self.selection[4], self.selection[5], depth)
                    GL.glEnd()
            elif self.selector_mode == "delete":
                depth = 0.1
                GL.glLineWidth(5)
                GL.glColor4f(1.0, 0.0, 0.0, 1.0)
                GL.glBegin(GL.GL_LINES)
                GL.glVertex3f(self.selection[0] - 1, self.selection[1] - 1, depth)
                GL.glVertex3f(self.selection[0] + 1, self.selection[1] + 1, depth)
                GL.glVertex3f(self.selection[0] - 1, self.selection[1] + 1, depth)
                GL.glVertex3f(self.selection[0] + 1, self.selection[1] - 1, depth)
                GL.glEnd()
            elif self.selector_mode == "oselect":
                depth = 0.1
                GL.glLineWidth(5)
                GL.glColor4f(0.0, 1.0, 0.0, 1.0)
                GL.glBegin(GL.GL_LINES)
                GL.glVertex3f(self.selection[0] - 1, self.selection[1] - 1, depth)
                GL.glVertex3f(self.selection[0] + 1, self.selection[1] + 1, depth)
                GL.glVertex3f(self.selection[0] - 1, self.selection[1] + 1, depth)
                GL.glVertex3f(self.selection[0] + 1, self.selection[1] - 1, depth)
                GL.glEnd()
            else:
                depth = self.project["setup"]["mill"]["depth"] - 0.1
                GL.glLineWidth(5)
                GL.glColor4f(0.0, 1.0, 1.0, 1.0)
                GL.glBegin(GL.GL_LINES)
                GL.glVertex3f(self.selection[0][0], self.selection[0][1], depth)
                GL.glVertex3f(self.selection[1][0], self.selection[1][1], depth)
                GL.glEnd()

        if self.project["simulation"] or self.project["simulation_pos"] != 0:
            last_pos = self.project["simulation_last"]
            sim_step = self.project["simulation_pos"]
            if sim_step < len(self.project["simulation_data"]):
                next_pos = self.project["simulation_data"][sim_step][1]
                spindle = self.project["simulation_data"][sim_step][4]
                diameter = self.project["simulation_data"][sim_step][2]

                if self.project["simulation"]:
                    dist = calc_distance3d(last_pos, next_pos)
                    if dist >= 1.0:
                        pdist = 1.0 / dist
                        next_pos = point_of_line3d(last_pos, next_pos, pdist)
                    else:
                        pdist = 1.0
                    self.project["simulation_last"] = next_pos
                    if pdist >= 1.0:
                        if (
                            self.project["simulation_pos"]
                            < len(self.project["simulation_data"]) - 1
                        ):
                            self.project["simulation_pos"] += 1
                        else:
                            self.project["simulation_pos"] = 0
                            self.project["simulation"] = False

                self.draw_tool(self.project["simulation_last"], spindle, diameter)

        GL.glPopMatrix()

    def toggle_tab_selector(self) -> bool:
        self.selection = ()
        self.selection_set = ()
        if self.selector_mode == "":
            self.selector_mode = "tab"
            self.view_2d()
            return True
        if self.selector_mode == "tab":
            self.selector_mode = ""
            self.view_reset()
        return False

    def toggle_start_selector(self) -> bool:
        self.selection = ()
        self.selection_set = ()
        if self.selector_mode == "":
            self.selector_mode = "start"
            self.view_2d()
            return True
        if self.selector_mode == "start":
            self.selector_mode = ""
            self.view_reset()
        return False

    def toggle_repair_selector(self) -> bool:
        self.selection = ()
        self.selection_set = ()
        if self.selector_mode == "":
            self.selector_mode = "repair"
            self.view_2d()
            return True
        if self.selector_mode == "repair":
            self.selector_mode = ""
            self.view_reset()
        return False

    def toggle_delete_selector(self) -> bool:
        self.selection = ()
        self.selection_set = ()
        if self.selector_mode == "":
            self.selector_mode = "delete"
            self.view_2d()
            return True
        if self.selector_mode == "delete":
            self.selector_mode = ""
            self.view_reset()
        return False

    def toggle_object_selector(self) -> bool:
        self.selection = ()
        self.selection_set = ()
        if self.selector_mode == "":
            self.selector_mode = "oselect"
            self.view_2d()
            return True
        if self.selector_mode == "oselect":
            self.selector_mode = ""
            self.view_reset()
        return False

    def view_2d(self) -> None:
        """toggle view function."""
        self.ortho = True
        self.rot_x = 0.0
        self.rot_y = 0.0
        self.rot_z = 0.0
        self.initializeGL()

    def view_reset(self) -> None:
        """toggle view function."""
        if self.selector_mode != "":
            return
        self.ortho = False
        self.rot_x = -20.0
        self.rot_y = -30.0
        self.rot_z = 0.0
        self.trans_x = 0.0
        self.trans_y = 0.0
        self.trans_z = 0.0
        self.scale_xyz = 1.0
        self.initializeGL()

    def timerEvent(self, event) -> None:  # pylint: disable=C0103,W0613
        """gltimer function."""
        if self.project["status"] == "INIT":
            self.project["status"] = "READY"
            self.update_drawing()
        self.update()

    def mousePressEvent(self, event) -> None:  # pylint: disable=C0103
        """mouse button pressed."""
        self.mbutton = event.button()
        self.mpos = event.pos()
        self.rot_x_last = self.rot_x
        self.rot_y_last = self.rot_y
        self.rot_z_last = self.rot_z
        self.trans_x_last = self.trans_x
        self.trans_y_last = self.trans_y
        self.trans_z_last = self.trans_z
        if self.selector_mode != "" and self.selection:
            if self.mbutton == 1:
                if self.selection:
                    if self.selector_mode == "tab":
                        self.project["tabs"]["data"].append(self.selection)
                        self.project["app"].update_tabs()
                        self.selection = ()
                    elif self.selector_mode == "start":
                        obj_idx = self.selection[0]
                        segment_idx = self.selection[1]
                        new_point = self.selection[2]
                        obj = self.project["objects"][obj_idx]
                        segment = obj.segments[segment_idx]
                        if new_point not in (segment.start, segment.end):
                            new_segment = VcSegment(
                                {
                                    "type": "LINE",
                                    "object": segment.object,
                                    "layer": segment.layer,
                                    "color": segment.color,
                                    "start": new_point,
                                    "end": segment.end,
                                    "bulge": segment.bulge / 2,
                                }
                            )
                            segment.end = new_point
                            segment.bulge = segment.bulge / 2
                            obj.segments.insert(segment_idx + 1, new_segment)
                        self.project["objects"][obj_idx]["start"] = new_point
                        self.project["app"].update_starts()
                        self.selection = ()
                    elif self.selector_mode == "delete":
                        self.selection_set = self.selection
                        # self.project["app"].update_object_setup()
                        self.project["app"].setup_select_object(self.selection_set[2])
                    elif self.selector_mode == "oselect":
                        self.selection_set = self.selection
                        # self.project["app"].update_object_setup()
                        self.project["app"].setup_select_object(self.selection_set[2])

                    elif self.selector_mode == "repair":
                        obj_idx = self.selection[2]
                        self.project["segments_org"].append(
                            VcSegment(
                                {
                                    "type": "LINE",
                                    "object": None,
                                    "layer": self.project["objects"][obj_idx]["layer"],
                                    "color": self.project["objects"][obj_idx]["color"],
                                    "start": (self.selection[0], self.selection[1]),
                                    "end": (self.selection[4], self.selection[5]),
                                    "bulge": 0.0,
                                }
                            )
                        )
                        self.selection = ()
                        self.project["app"].prepare_segments()

                self.update_drawing()
                self.update()
            elif self.mbutton == 2:
                if self.selector_mode == "tab":
                    sel_idx = -1
                    sel_dist = -1
                    for tab_idx, tab in enumerate(self.project["tabs"]["data"]):
                        tab_pos = line_center_2d(tab[0], tab[1])
                        dist = calc_distance(
                            (self.mouse_pos_x, self.mouse_pos_y), tab_pos
                        )
                        if sel_dist < 0 or dist < sel_dist:
                            sel_dist = dist
                            sel_idx = tab_idx

                    if 0.0 < sel_dist < 10.0:
                        del self.project["tabs"]["data"][sel_idx]
                        self.update_drawing()
                        self.update()
                        self.project["app"].update_tabs()
                    self.selection = ()
                elif self.selector_mode == "delete":
                    obj_idx = self.selection[2]
                    del self.project["objects"][obj_idx]
                    self.project["app"].update_object_setup()
                    self.update_drawing()
                    self.update()
                    self.selection = ()
                elif self.selector_mode == "oselect":
                    pass
                elif self.selector_mode == "start":
                    obj_idx = self.selection[0]
                    self.project["objects"][obj_idx]["start"] = ()
                    self.update_drawing()
                    self.update()
                    self.project["app"].update_starts()
                    self.selection = ()

    def mouseReleaseEvent(self, event) -> None:  # pylint: disable=C0103,W0613
        """mouse button released."""
        self.mbutton = None
        self.mpos = None

    def mouse_pos_to_real_pos(self, mouse_pos) -> tuple:
        min_max = self.project["minMax"]
        mouse_pos_x = mouse_pos.x()
        mouse_pos_y = self.screen_h - mouse_pos.y()
        real_pos_x = (
            (
                (mouse_pos_x / self.screen_w - 0.5 + self.trans_x)
                / self.scale
                / self.scale_xyz
            )
            + (self.size_x / 2)
            + min_max[0]
        )
        real_pos_y = (
            (
                (mouse_pos_y / self.screen_h - 0.5 + self.trans_y)
                / self.scale
                / self.scale_xyz
                * self.aspect
            )
            + (self.size_y / 2)
            + min_max[1]
        )
        return (real_pos_x, real_pos_y)

    def mouseMoveEvent(self, event) -> None:  # pylint: disable=C0103
        """mouse moved."""
        if self.mbutton == 1:
            moffset = self.mpos - event.pos()
            self.trans_x = self.trans_x_last + moffset.x() / self.screen_w
            self.trans_y = self.trans_y_last - moffset.y() / self.screen_h * self.aspect
        elif self.selector_mode == "tab":
            (self.mouse_pos_x, self.mouse_pos_y) = self.mouse_pos_to_real_pos(
                event.pos()
            )
            self.selection = found_next_tab_point(
                (self.mouse_pos_x, self.mouse_pos_y), self.project["offsets"]
            )
        elif self.selector_mode == "start":
            (self.mouse_pos_x, self.mouse_pos_y) = self.mouse_pos_to_real_pos(
                event.pos()
            )
            self.selection = found_next_point_on_segment(
                (self.mouse_pos_x, self.mouse_pos_y), self.project["objects"]
            )
        elif self.selector_mode == "delete":
            (self.mouse_pos_x, self.mouse_pos_y) = self.mouse_pos_to_real_pos(
                event.pos()
            )
            self.selection = found_next_segment_point(
                (self.mouse_pos_x, self.mouse_pos_y), self.project["objects"]
            )
        elif self.selector_mode == "oselect":
            (self.mouse_pos_x, self.mouse_pos_y) = self.mouse_pos_to_real_pos(
                event.pos()
            )
            self.selection = found_next_segment_point(
                (self.mouse_pos_x, self.mouse_pos_y), self.project["objects"]
            )
        elif self.selector_mode == "repair":
            (self.mouse_pos_x, self.mouse_pos_y) = self.mouse_pos_to_real_pos(
                event.pos()
            )
            self.selection = found_next_open_segment_point(
                (self.mouse_pos_x, self.mouse_pos_y), self.project["objects"]
            )
            if self.selection:
                selection_end = found_next_open_segment_point(
                    (self.mouse_pos_x, self.mouse_pos_y),
                    self.project["objects"],
                    max_dist=10.0,
                    exclude=(self.selection[2], self.selection[3]),
                )
                if selection_end:
                    self.selection += selection_end
                else:
                    self.selection = ()

        elif self.mbutton == 2:
            moffset = self.mpos - event.pos()
            self.rot_z = self.rot_z_last - moffset.x() / 4
            self.trans_z = self.trans_z_last + moffset.y() / 500
            if self.ortho:
                self.ortho = False
                self.initializeGL()
        elif self.mbutton == 4:
            moffset = self.mpos - event.pos()
            self.rot_x = self.rot_x_last + -moffset.x() / 4
            self.rot_y = self.rot_y_last - moffset.y() / 4
            if self.ortho:
                self.ortho = False
                self.initializeGL()

    def wheelEvent(self, event) -> None:  # pylint: disable=C0103,W0613
        """mouse wheel moved."""
        if event.angleDelta().y() > 0:
            self.scale_xyz += self.wheel_scale
        else:
            self.scale_xyz -= self.wheel_scale


def draw_circle(center: Sequence[float], radius: float) -> None:
    """draws an circle"""
    GL.glBegin(GL.GL_TRIANGLE_STRIP)
    GL.glVertex3f(center[0], center[1], center[2])
    angle = 0.0
    step = math.pi / 6
    while angle < math.pi * 2 + step:
        p_x = center[0] + radius * math.sin(angle)
        p_y = center[1] - radius * math.cos(angle)
        GL.glVertex3f(p_x, p_y, center[2])
        GL.glVertex3f(center[0], center[1], center[2])
        angle += step
    GL.glEnd()


def draw_mill_line(
    p_from: Sequence[float],
    p_to: Sequence[float],
    width: float,
    mode: str,
    options: str,
) -> None:
    """draws an milling line including direction and width"""
    line_angle = angle_of_line(p_from, p_to)
    radius = width / 2

    if p_from[2] < 0.0 and p_to[2] < 0.0 and mode == "full":
        GL.glColor3f(1.0, 1.0, 0.0)
        # start/end circles
        draw_circle(p_from, radius)
        draw_circle(p_to, radius)
        x_out_from = p_from[0] + radius * math.sin(line_angle)
        y_out_from = p_from[1] - radius * math.cos(line_angle)
        x_in_from = p_from[0] + radius * math.sin(line_angle + math.pi)
        y_in_from = p_from[1] - radius * math.cos(line_angle + math.pi)
        x_out_to = p_to[0] + radius * math.sin(line_angle)
        y_out_to = p_to[1] - radius * math.cos(line_angle)
        x_in_to = p_to[0] + radius * math.sin(line_angle + math.pi)
        y_in_to = p_to[1] - radius * math.cos(line_angle + math.pi)

        # filled line
        GL.glBegin(GL.GL_TRIANGLE_STRIP)
        GL.glVertex3f(x_in_from, y_in_from, p_from[2])
        GL.glVertex3f(x_out_from, y_out_from, p_from[2])
        GL.glVertex3f(x_in_to, y_in_to, p_to[2])
        GL.glVertex3f(x_out_to, y_out_to, p_to[2])
        GL.glEnd()

    # center line
    if options != "OFF":
        GL.glColor3f(0.91, 0.0, 0.0)
    else:
        GL.glColor3f(0.11, 0.63, 0.36)
    GL.glBegin(GL.GL_LINES)
    GL.glVertex3fv(p_from)
    GL.glVertex3fv(p_to)
    GL.glEnd()

    if mode != "minimal":
        lenght = calc_distance(p_from, p_to)
        if lenght < 3:
            return
        # direction arrow
        GL.glColor3f(0.62, 0.73, 0.82)
        center = p_from
        if lenght > 5.0:
            center = line_center_3d(p_from, p_to)
        x_arrow = center[0] - 3 * math.sin(line_angle + math.pi / 2.0)
        y_arrow = center[1] + 3 * math.cos(line_angle + math.pi / 2.0)
        x_arrow_left = x_arrow + 1 * math.sin(line_angle + math.pi)
        y_arrow_left = y_arrow - 1 * math.cos(line_angle + math.pi)
        x_arrow_right = x_arrow + 1 * math.sin(line_angle)
        y_arrow_right = y_arrow - 1 * math.cos(line_angle)
        GL.glBegin(GL.GL_LINES)
        GL.glVertex3f(center[0], center[1], center[2] + 0.01)
        GL.glVertex3f(x_arrow_left, y_arrow_left, center[2] + 0.01)
        GL.glVertex3f(center[0], center[1], center[2] + 0.01)
        GL.glVertex3f(x_arrow_right, y_arrow_right, center[2] + 0.01)
        GL.glEnd()


def draw_text(
    text: str,
    pos_x: float,
    pos_y: float,
    pos_z: float,
    scale: float = 1.0,
    center_x: bool = False,
    center_y: bool = False,
) -> None:
    test_data = tuple(font.lines_for_text(text))
    if center_x or center_y:
        width = 0.0
        height = 0.0
        for (x_1, y_1), (x_2, y_2) in test_data:
            width = max(width, x_1 * scale)
            width = max(width, x_2 * scale)
            height = max(height, y_1 * scale)
            height = max(height, y_2 * scale)
        if center_x:
            pos_x -= width / 2.0
        if center_y:
            pos_y -= height / 2.0
    for (x_1, y_1), (x_2, y_2) in test_data:
        GL.glVertex3f(pos_x + x_1 * scale, pos_y + y_1 * scale, pos_z)
        GL.glVertex3f(pos_x + x_2 * scale, pos_y + y_2 * scale, pos_z)


def draw_grid(project: dict) -> None:
    """draws the grid"""
    GL.glNormal3f(0, 0, 1)
    min_max = project["minMax"]
    if not min_max:
        return
    size = project["setup"]["view"]["grid_size"]
    start_x = int(min_max[0] / size) * size - size
    end_x = int(min_max[2] / size) * size + size
    start_y = int(min_max[1] / size) * size - size
    end_y = int(min_max[3] / size) * size + size
    size_x = min_max[2] - min_max[0]
    center_x = min_max[0] + size_x / 2
    size_y = min_max[3] - min_max[1]
    center_y = min_max[1] + size_y / 2
    z_offset = -project["setup"]["workpiece"]["offset_z"]
    mill_depth = project["setup"]["mill"]["depth"]
    unit = project["setup"]["machine"]["unit"]
    unitscale = 1.0
    if unit == "inch":
        unitscale = 25.4
        z_offset *= unitscale
        mill_depth *= unitscale

    if project["setup"]["view"]["grid_show"]:
        # Grid-X
        GL.glLineWidth(0.1)
        GL.glColor3f(0.9, 0.9, 0.9)
        GL.glBegin(GL.GL_LINES)
        for p_x in range(start_x, end_x + size, size):
            GL.glVertex3f(p_x, start_y, mill_depth)
            GL.glVertex3f(p_x, end_y, mill_depth)
        if project["setup"]["view"]["ruler_show"] and size >= 5:
            for p_x in range(start_x, end_x, size):
                draw_text(f"{p_x}", p_x, start_y, mill_depth, 0.4)
        GL.glEnd()

        # Grid-Y
        GL.glLineWidth(0.1)
        GL.glColor3f(0.9, 0.9, 0.9)
        GL.glBegin(GL.GL_LINES)
        for p_y in range(start_y, end_y + size, size):
            GL.glVertex3f(start_x, p_y, mill_depth)
            GL.glVertex3f(end_x, p_y, mill_depth)
        if project["setup"]["view"]["ruler_show"] and size >= 5:
            for p_y in range(start_y, end_y, size):
                draw_text(f"{p_y}", start_x, p_y, mill_depth, 0.4)
        GL.glEnd()

    # Zero-Z
    GL.glLineWidth(1)
    GL.glColor3f(1.0, 1.0, 0.0)
    GL.glBegin(GL.GL_LINES)
    GL.glVertex3f(0.0, 0.0, 100.0)
    GL.glVertex3f(0.0, 0.0, mill_depth)
    GL.glVertex3f(-1, -1, 0.0)
    GL.glVertex3f(1, 1, 0.0)
    GL.glVertex3f(-1, 1, 0.0)
    GL.glVertex3f(1, -1, 0.0)
    GL.glEnd()

    # Z-Offset
    if z_offset:
        GL.glLineWidth(1)
        GL.glColor3f(1.0, 0.0, 1.0)
        GL.glBegin(GL.GL_LINES)
        GL.glVertex3f(-2, -1, z_offset)
        GL.glVertex3f(2, 2, z_offset)
        GL.glVertex3f(-2, 2, z_offset)
        GL.glVertex3f(2, -2, z_offset)
        GL.glEnd()

    # Zero-X
    GL.glColor3f(0.5, 0.0, 0.0)
    GL.glBegin(GL.GL_LINES)
    GL.glVertex3f(0.0, start_y, mill_depth)
    GL.glVertex3f(0.0, end_y, mill_depth)
    GL.glEnd()
    # Zero-Y
    GL.glColor3f(0.0, 0.0, 0.5)
    GL.glBegin(GL.GL_LINES)
    GL.glVertex3f(start_x, 0.0, mill_depth)
    GL.glVertex3f(end_x, 0.0, mill_depth)
    GL.glEnd()

    if project["setup"]["view"]["ruler_show"]:
        # MinMax-X
        GL.glColor3f(0.5, 0.0, 0.0)
        GL.glBegin(GL.GL_LINES)
        GL.glVertex3f(min_max[0], start_y - 5, mill_depth)
        GL.glVertex3f(min_max[0], end_y, mill_depth)
        GL.glVertex3f(min_max[2], start_y - 5, mill_depth)
        GL.glVertex3f(min_max[2], end_y, mill_depth)
        draw_text(
            f"{round(min_max[0], 2)}",
            min_max[0],
            start_y - 5 - 6,
            mill_depth,
            0.5,
            True,
        )
        draw_text(
            f"{round(min_max[2], 2)}",
            min_max[2],
            start_y - 5 - 6,
            mill_depth,
            0.5,
            True,
        )
        GL.glEnd()
        # MinMax-Y
        GL.glColor3f(0.0, 0.0, 0.5)
        GL.glBegin(GL.GL_LINES)
        GL.glVertex3f(start_x, min_max[1], mill_depth)
        GL.glVertex3f(end_x + 5, min_max[1], mill_depth)
        GL.glVertex3f(start_x, min_max[3], mill_depth)
        GL.glVertex3f(end_x + 5, min_max[3], mill_depth)
        draw_text(
            f"{round(min_max[1], 2)}",
            end_x + 5,
            min_max[1],
            mill_depth,
            0.5,
            False,
            True,
        )
        draw_text(
            f"{round(min_max[3], 2)}",
            end_x + 5,
            min_max[3],
            mill_depth,
            0.5,
            False,
            True,
        )
        GL.glEnd()
        # Size-X
        GL.glColor3f(1.0, 0.0, 0.0)
        GL.glBegin(GL.GL_LINES)
        draw_text(
            f"{round(size_x, 2)}", center_x, start_y - 5 - 6, mill_depth, 0.5, True
        )
        GL.glEnd()
        # Size-Y
        GL.glColor3f(0.0, 0.0, 1.0)
        GL.glBegin(GL.GL_LINES)
        draw_text(
            f"{round(size_y, 2)}", end_x + 5, center_y, mill_depth, 0.5, False, True
        )
        GL.glEnd()


def draw_object_ids(project: dict, selected: int = -1) -> None:
    """draws the object id's as text"""
    GL.glNormal3f(0, 0, 1)
    for obj_idx, obj in project["objects"].items():

        if obj_idx.split(":")[0] == selected:
            GL.glLineWidth(2)
            GL.glColor3f(1.0, 1.0, 1.01)
        else:
            GL.glLineWidth(2)
            GL.glColor3f(0.63, 0.36, 0.11)

        GL.glBegin(GL.GL_LINES)

        if obj.get("layer", "").startswith("BREAKS:") or obj.get(
            "layer", ""
        ).startswith("_TABS"):
            continue
        p_x = obj["segments"][0]["start"][0]
        p_y = obj["segments"][0]["start"][1]
        for (x_1, y_1), (x_2, y_2) in font.lines_for_text(f"#{obj_idx.split(':')[0]}"):
            GL.glVertex3f(p_x + x_1, p_y + y_1, 5.0)
            GL.glVertex3f(p_x + x_2, p_y + y_2, 5.0)
        GL.glEnd()


def draw_object_edges(project: dict, selected: int = -1) -> None:
    """draws the edges of an object"""
    unit = project["setup"]["machine"]["unit"]
    depth = project["setup"]["mill"]["depth"]
    tabs_height = project["setup"]["tabs"]["height"]
    interpolate = project["setup"]["view"]["arcs"]
    unitscale = 1.0
    if unit == "inch":
        unitscale = 25.4
        depth *= unitscale
        tabs_height *= unitscale

    depths = []
    for obj in project["objects"].values():
        if obj.get("layer", "").startswith("BREAKS:") or obj.get(
            "layer", ""
        ).startswith("_TABS"):
            continue
        odepth = obj["setup"]["mill"]["depth"]
        if odepth not in depths:
            depths.append(odepth)
    depths.sort()
    for depth in depths:
        GL.glNormal3f(0, 0, 1)
        for obj_idx, obj in project["objects"].items():
            if obj.get("layer", "").startswith("BREAKS:") or obj.get(
                "layer", ""
            ).startswith("_TABS"):
                continue

            color = (1.0, 1.0, 1.0)
            if project["setup"]["view"]["colors_show"] and obj.color in dxfcolors:
                color = dxfcolors[obj.color][0:3]

            odepth = obj["setup"]["mill"]["depth"]
            if odepth > depth:
                continue

            if obj_idx.split(":")[0] == selected:
                GL.glLineWidth(4)
                GL.glColor4f(1.0, 1.0, 1.0, 1.0)
            else:
                GL.glLineWidth(2)
                GL.glColor3f(*color)

            # side
            GL.glBegin(GL.GL_LINES)
            for segment in obj.segments:
                p_x = segment.start[0]
                p_y = segment.start[1]
                GL.glVertex3f(p_x, p_y, 0.0)
                GL.glVertex3f(p_x, p_y, depth)
            GL.glEnd()

            # top
            GL.glBegin(GL.GL_LINES)
            for segment in obj.segments:
                if segment.bulge != 0.0 and interpolate:
                    last_x = segment.start[0]
                    last_y = segment.start[1]
                    for point in bulge_points(
                        segment.start, segment.end, segment.bulge
                    ):
                        GL.glVertex3f(last_x, last_y, 0.0)
                        GL.glVertex3f(point[0], point[1], 0.0)
                        last_x = point[0]
                        last_y = point[1]
                    GL.glVertex3f(last_x, last_y, 0.0)
                    GL.glVertex3f(segment.end[0], segment.end[1], 0.0)
                else:
                    GL.glVertex3f(segment.start[0], segment.start[1], 0.0)
                    GL.glVertex3f(segment.end[0], segment.end[1], 0.0)
            GL.glEnd()

            # bottom
            if odepth == depth:
                GL.glBegin(GL.GL_LINES)
                for segment in obj.segments:
                    if segment.bulge != 0.0 and interpolate:
                        last_x = segment.start[0]
                        last_y = segment.start[1]
                        for point in bulge_points(
                            segment.start, segment.end, segment.bulge
                        ):
                            GL.glVertex3f(last_x, last_y, depth)
                            GL.glVertex3f(point[0], point[1], depth)
                            last_x = point[0]
                            last_y = point[1]
                        GL.glVertex3f(last_x, last_y, depth)
                        GL.glVertex3f(segment.end[0], segment.end[1], depth)
                    else:
                        GL.glVertex3f(segment.start[0], segment.start[1], depth)
                        GL.glVertex3f(segment.end[0], segment.end[1], depth)
                GL.glEnd()

            # start points
            start = obj.get("start", ())
            if start:
                depth = 0.1
                GL.glLineWidth(5)
                GL.glColor4f(1.0, 1.0, 0.0, 1.0)
                GL.glBegin(GL.GL_LINES)
                GL.glVertex3f(start[0] - 1, start[1] - 1, depth)
                GL.glVertex3f(start[0] + 1, start[1] + 1, depth)
                GL.glVertex3f(start[0] - 1, start[1] + 1, depth)
                GL.glVertex3f(start[0] + 1, start[1] - 1, depth)
                GL.glEnd()

    # tabs
    tabs = project.get("tabs", {}).get("data", ())
    if tabs:
        tabs_depth = depth + tabs_height
        GL.glLineWidth(5)
        GL.glColor4f(1.0, 1.0, 0.0, 1.0)
        GL.glBegin(GL.GL_LINES)
        for tab in tabs:
            GL.glVertex3f(tab[0][0], tab[0][1], tabs_depth)
            GL.glVertex3f(tab[1][0], tab[1][1], tabs_depth)
        GL.glEnd()


def add_triangle(p_1, p_2, p_3, inv=False):
    point_a = (
        p_2[0] - p_1[0],
        p_2[1] - p_1[1],
        p_2[2] - p_1[2],
    )
    point_b = (
        p_3[0] - p_1[0],
        p_3[1] - p_1[1],
        p_3[2] - p_1[2],
    )
    normal = (
        point_a[1] * point_b[2] - point_a[2] * point_b[1],
        point_a[2] * point_b[0] - point_a[0] * point_b[2],
        point_a[0] * point_b[1] - point_a[1] * point_b[0],
    )
    factor = max(abs(normal[0]), abs(normal[1]), abs(normal[2]))
    if inv:
        factor *= -1
    if factor != 0:
        GL.glNormal3f(normal[0] / factor, normal[1] / factor, normal[2] / factor)
    else:
        GL.glNormal3f(0, 0, 0)
    GL.glVertex3fv(p_1)
    GL.glVertex3fv(p_2)
    GL.glVertex3fv(p_3)


def draw_object_faces(project: dict) -> None:
    """draws the top and side faces of an object"""
    unit = project["setup"]["machine"]["unit"]
    depth = project["setup"]["mill"]["depth"]
    interpolate = project["setup"]["view"]["arcs"]
    color = project["setup"]["view"]["color"]
    alpha = project["setup"]["view"]["alpha"]
    unitscale = 1.0
    if unit == "inch":
        unitscale = 25.4
        depth *= unitscale

    depths = []
    for obj in project["objects"].values():
        if obj.get("layer", "").startswith("BREAKS:") or obj.get(
            "layer", ""
        ).startswith("_TABS"):
            continue
        odepth = obj["setup"]["mill"]["depth"]
        if odepth not in depths:
            depths.append(odepth)
    depths.append(0.0)
    depths.sort()

    for depth in depths:

        GL.glColor4f(color[0], color[1], color[2], alpha)
        # object faces (side)
        GL.glBegin(GL.GL_TRIANGLES)
        for obj in project["objects"].values():
            if obj.get("layer", "").startswith("BREAKS:") or obj.get(
                "layer", ""
            ).startswith("_TABS"):
                continue

            odepth = obj["setup"]["mill"]["depth"]
            if odepth > depth:
                continue

            depth *= unitscale

            for segment in obj.segments:
                last_x = segment.start[0]
                last_y = segment.start[1]
                if segment.bulge != 0.0 and interpolate:
                    for point in bulge_points(
                        segment.start, segment.end, segment.bulge
                    ):
                        add_triangle(
                            (last_x, last_y, 0.0),
                            (last_x, last_y, depth),
                            (point[0], point[1], 0.0),
                            (obj.tool_offset == "inside"),
                        )
                        add_triangle(
                            (point[0], point[1], 0.0),
                            (last_x, last_y, depth),
                            (point[0], point[1], depth),
                            (obj.tool_offset == "inside"),
                        )
                        last_x = point[0]
                        last_y = point[1]
                add_triangle(
                    (last_x, last_y, 0.0),
                    (last_x, last_y, depth),
                    (segment.end[0], segment.end[1], 0.0),
                    (obj.tool_offset == "inside"),
                )
                add_triangle(
                    (segment.end[0], segment.end[1], 0.0),
                    (last_x, last_y, depth),
                    (segment.end[0], segment.end[1], depth),
                    (obj.tool_offset == "inside"),
                )
        GL.glEnd()

        # object faces (top)
        GL.glNormal3f(0, 0, 1)
        tess = gluNewTess()
        gluTessProperty(tess, GLU_TESS_WINDING_RULE, GLU_TESS_WINDING_ODD)
        gluTessCallback(tess, GLU_TESS_BEGIN, GL.glBegin)
        gluTessCallback(tess, GLU_TESS_VERTEX, GL.glVertex)
        gluTessCallback(tess, GLU_TESS_END, GL.glEnd)
        gluTessCallback(
            tess, GLU_TESS_COMBINE, lambda _points, _vertices, _weights: _points
        )
        gluTessBeginPolygon(tess, 0)
        for obj in project["objects"].values():
            if obj.get("layer", "").startswith("BREAKS:") or obj.get(
                "layer", ""
            ).startswith("_TABS"):
                continue

            odepth = obj["setup"]["mill"]["depth"]
            if odepth > depth:
                continue

            depth *= unitscale

            if obj.closed:
                gluTessBeginContour(tess)
                for segment in obj.segments:
                    p_xy = (segment.start[0], segment.start[1], depth)
                    gluTessVertex(tess, p_xy, p_xy)
                    if segment.bulge != 0.0 and interpolate:
                        for point in bulge_points(
                            segment.start, segment.end, segment.bulge
                        ):
                            p_xy = (point[0], point[1], depth)
                            gluTessVertex(tess, p_xy, p_xy)
                    p_xy = (segment.end[0], segment.end[1], depth)
                    gluTessVertex(tess, p_xy, p_xy)
                gluTessEndContour(tess)
        gluTessEndPolygon(tess)
        gluDeleteTess(tess)

        """
        GL.glNormal3f(0, 0, -1)
        tess = gluNewTess()
        gluTessProperty(tess, GLU_TESS_WINDING_RULE, GLU_TESS_WINDING_ODD)
        gluTessCallback(tess, GLU_TESS_BEGIN, GL.glBegin)
        gluTessCallback(tess, GLU_TESS_VERTEX, GL.glVertex)
        gluTessCallback(tess, GLU_TESS_END, GL.glEnd)
        gluTessCallback(
            tess, GLU_TESS_COMBINE, lambda _points, _vertices, _weights: _points
        )
        gluTessBeginPolygon(tess, 0)
        for obj in project["objects"].values():
            if obj.get("layer", "").startswith("BREAKS:") or obj.get(
                "layer", ""
            ).startswith("_TABS"):
                continue

            odepth = obj["setup"]["mill"]["depth"]
            if odepth == depth:
                continue

            if obj.closed:
                gluTessBeginContour(tess)
                for segment in obj.segments:
                    p_xy = (segment.start[0], segment.start[1], depth)
                    gluTessVertex(tess, p_xy, p_xy)
                    if segment.bulge != 0.0 and interpolate:
                        for point in bulge_points(segment.start, segment.end, segment.bulge):
                            p_xy = (point[0], point[1], depth)
                            gluTessVertex(tess, p_xy, p_xy)
                    p_xy = (segment.end[0], segment.end[1], depth)
                    gluTessVertex(tess, p_xy, p_xy)
                gluTessEndContour(tess)
        gluTessEndPolygon(tess)
        gluDeleteTess(tess)
        """


def draw_line(
    p_1: dict, p_2: dict, options: str, project: dict, tool_number: int = 0
) -> None:
    """callback function for Parser to draw the lines"""
    if project["setup"]["machine"]["g54"]:
        p_from = (p_1["X"], p_1["Y"], p_1["Z"])
        p_to = (p_2["X"], p_2["Y"], p_2["Z"])
    else:
        unit = project["setup"]["machine"]["unit"]
        unitscale = 1.0
        if unit == "inch":
            unitscale = 25.4
        p_from = (
            p_1["X"] - project["setup"]["workpiece"]["offset_x"] * unitscale,
            p_1["Y"] - project["setup"]["workpiece"]["offset_y"] * unitscale,
            p_1["Z"] - project["setup"]["workpiece"]["offset_z"] * unitscale,
        )
        p_to = (
            p_2["X"] - project["setup"]["workpiece"]["offset_x"] * unitscale,
            p_2["Y"] - project["setup"]["workpiece"]["offset_y"] * unitscale,
            p_2["Z"] - project["setup"]["workpiece"]["offset_z"] * unitscale,
        )

    if tool_number != 0:
        diameter = None
        for entry in project["setup"]["tool"]["tooltable"]:
            if tool_number == entry["number"]:
                diameter = entry["diameter"]
        if diameter is None:
            print("ERROR: draw_line: TOOL not found")
            return
    else:
        diameter = 1

    mode = project["setup"]["view"]["path"]
    project["simulation_data"].append((p_from, p_to, diameter, mode, options))
    draw_mill_line(p_from, p_to, diameter, mode, options)


def draw_machinecode_path(project: dict) -> bool:
    """draws the machinecode path"""
    project["simulation_data"] = []
    GL.glLineWidth(2)
    tool_number = 0
    try:
        if project["suffix"] in {"ngc", "gcode"}:
            gcode_parser = GcodeParser(project["machine_cmd"])
            toolpath = gcode_parser.get_path()
            for line in toolpath:
                if len(line) > 3 and line[3].startswith("TOOLCHANGE:"):
                    new_tool = line[3].split(":")[1]
                    tool_number = int(new_tool)
                    GL.glBegin(GL.GL_LINES)
                    draw_text(
                        f"TC:{new_tool}",
                        line[0]["X"],
                        line[0]["Y"],
                        line[0]["Z"],
                        0.2,
                        True,
                        True,
                    )
                    GL.glEnd()
                draw_line(line[0], line[1], line[2], project, tool_number)
            project["outputMinMax"] = gcode_parser.get_minmax()

        elif project["suffix"] in {"hpgl", "hpg"}:
            project["setup"]["machine"]["g54"] = False
            project["setup"]["workpiece"]["offset_z"] = 0.0
            hpgl_parser = HpglParser(project["machine_cmd"])
            toolpath = hpgl_parser.get_path()
            for line in toolpath:
                draw_line(line[0], line[1], line[2], project)
            project["outputMinMax"] = gcode_parser.get_minmax()

    except Exception as error_string:  # pylint: disable=W0703:
        print(f"ERROR: parsing machine_cmd: {error_string}")
        return False
    return True


def draw_all(project: dict) -> None:
    selected = project["object_active"]

    project["gllist"] = GL.glGenLists(1)
    GL.glNewList(project["gllist"], GL.GL_COMPILE)
    draw_grid(project)

    if project["setup"]["view"]["3d_show"]:
        if hasattr(project["draw_reader"], "draw_3d"):
            project["draw_reader"].draw_3d()

    if project["glwidget"] and project["glwidget"].selector_mode != "repair":
        if not draw_machinecode_path(project):
            print("error while drawing machine commands")

    if project["setup"]["view"]["object_ids"]:
        draw_object_ids(project, selected=selected)

    draw_object_edges(project, selected=selected)
    if project["setup"]["view"]["polygon_show"]:
        draw_object_faces(project)

    GL.glEndList()
