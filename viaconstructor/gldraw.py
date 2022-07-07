"""OpenGL drawing functions"""

from typing import Sequence
import math
from OpenGL import GL
from OpenGL.GLU import (
    gluNewTess,
    gluTessProperty,
    GLU_TESS_WINDING_RULE,
    GLU_TESS_WINDING_ODD,
    gluTessCallback,
    GLU_TESS_BEGIN,
    GLU_TESS_VERTEX,
    GLU_TESS_END,
    GLU_TESS_COMBINE,
    gluTessBeginPolygon,
    gluTessBeginContour,
    gluTessVertex,
    gluTessEndContour,
    gluTessEndPolygon,
    gluDeleteTess,
)
from HersheyFonts import HersheyFonts
from .gcodeparser import GcodeParser
from .calc import angle_of_line, calc_distance, line_center_3d, object2vertex


font = HersheyFonts()
font.load_default_font()
font.normalize_rendering(6)


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
    p_from: Sequence[float], p_to: Sequence[float], width: float, mode: str
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
    GL.glColor3f(1.0, 1.0, 1.0)
    GL.glBegin(GL.GL_LINES)
    GL.glVertex3fv(p_from)
    GL.glVertex3fv(p_to)
    GL.glEnd()

    if mode != "minimal":
        lenght = calc_distance(p_from, p_to)
        if lenght < 3:
            return
        # direction arrow
        GL.glColor3f(1.0, 0.0, 0.0)
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


def draw_text(text: str, pos_x: float, pos_y: float, pos_z: float, scale: float=1.0, center_x: bool=False, center_y: bool=False) -> None:
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
    min_max = project["minMax"]
    size = project["setup"]["view"]["grid_size"]
    mill_depth = project["setup"]["mill"]["depth"]
    start_x = int(min_max[0] / size) * size - size
    end_x = int(min_max[2] / size) * size + size
    start_y = int(min_max[1] / size) * size - size
    end_y = int(min_max[3] / size) * size + size
    size_x = (min_max[2] - min_max[0])
    center_x = min_max[0] + size_x / 2
    size_y = (min_max[3] - min_max[1])
    center_y = min_max[1] + size_y / 2

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
    GL.glLineWidth(2)
    GL.glColor3f(1.0, 1.0, 0.0)
    GL.glBegin(GL.GL_LINES)
    GL.glVertex3f(0.0, 0.0, 100.0)
    GL.glVertex3f(0.0, 0.0, mill_depth)
    GL.glVertex3f(-1, -1, 0.0)
    GL.glVertex3f(1, 1, 0.0)
    GL.glVertex3f(-1, 1, 0.0)
    GL.glVertex3f(1, -1, 0.0)
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
        GL.glColor3f(1.0, 1.0, 1.0)
        GL.glBegin(GL.GL_LINES)
        GL.glVertex3f(min_max[0], start_y - 5, mill_depth)
        GL.glVertex3f(min_max[0], end_y, mill_depth)
        GL.glVertex3f(min_max[2], start_y - 5, mill_depth)
        GL.glVertex3f(min_max[2], end_y, mill_depth)
        draw_text(f"{round(min_max[0], 6)}", min_max[0], start_y - 5 - 6, mill_depth, 0.5, True)
        draw_text(f"{round(min_max[2], 6)}", min_max[2], start_y - 5 - 6, mill_depth, 0.5, True)
        GL.glEnd()
        # MinMax-Y
        GL.glColor3f(1.0, 1.0, 1.0)
        GL.glBegin(GL.GL_LINES)
        GL.glVertex3f(start_x, min_max[1], mill_depth)
        GL.glVertex3f(end_x + 5, min_max[1], mill_depth)
        GL.glVertex3f(start_x, min_max[3], mill_depth)
        GL.glVertex3f(end_x + 5, min_max[3], mill_depth)
        draw_text(f"{round(min_max[1], 6)}", end_x + 5, min_max[1], mill_depth, 0.5, False, True)
        draw_text(f"{round(min_max[3], 6)}", end_x + 5, min_max[3], mill_depth, 0.5, False, True)
        GL.glEnd()
        # Size-X
        GL.glColor3f(1.0, 1.0, 1.0)
        GL.glBegin(GL.GL_LINES)
        draw_text(f"{round(size_x, 6)}", center_x, start_y - 5 - 6, mill_depth, 0.5, True)
        GL.glEnd()
        # Size-Y
        GL.glColor3f(1.0, 1.0, 1.0)
        GL.glBegin(GL.GL_LINES)
        draw_text(f"{round(size_y, 6)}", end_x + 5, center_y, mill_depth, 0.5, False, True)
        GL.glEnd()



def draw_object_ids(project: dict) -> None:
    """draws the object id's as text"""
    GL.glLineWidth(2)
    GL.glColor4f(1.0, 0.0, 0.0, 1.0)
    GL.glBegin(GL.GL_LINES)
    for obj_idx, obj in project["objects"].items():
        p_x = obj["segments"][0]["start"][0]
        p_y = obj["segments"][0]["start"][1]
        for (x_1, y_1), (x_2, y_2) in font.lines_for_text(f"#{obj_idx}"):
            GL.glVertex3f(p_x + x_1, p_y + y_1, 5.0)
            GL.glVertex3f(p_x + x_2, p_y + y_2, 5.0)
    GL.glEnd()


def draw_object_edges(project: dict) -> None:
    """draws the edges of an object"""
    GL.glLineWidth(1)
    GL.glColor4f(0.0, 1.0, 0.0, 1.0)
    for obj in project["objects"].values():
        # side
        GL.glBegin(GL.GL_LINES)
        for segment in obj["segments"]:
            p_x = segment["start"][0]
            p_y = segment["start"][1]
            GL.glVertex3f(p_x, p_y, 0.0)
            GL.glVertex3f(p_x, p_y, project["setup"]["mill"]["depth"])
        GL.glEnd()
        # top
        vertex_data = object2vertex(obj)
        closed = obj["closed"]
        if closed:
            GL.glBegin(GL.GL_LINE_LOOP)
        else:
            GL.glBegin(GL.GL_LINE_STRIP)
        for pos, p_x in enumerate(vertex_data[0]):
            p_y = vertex_data[1][pos]
            GL.glVertex3f(p_x, p_y, 0.0)
        GL.glEnd()
        # bottom
        if closed:
            GL.glBegin(GL.GL_LINE_LOOP)
        else:
            GL.glBegin(GL.GL_LINE_STRIP)
        for pos, p_x in enumerate(vertex_data[0]):
            p_y = vertex_data[1][pos]
            GL.glVertex3f(p_x, p_y, project["setup"]["mill"]["depth"])
        GL.glEnd()


def draw_object_faces(project: dict) -> None:
    """draws the top and side faces of an object"""
    # object faces (side)
    GL.glColor4f(0.0, 0.75, 0.3, 0.5)
    for obj in project["objects"].values():
        vertex_data = object2vertex(obj)
        for segment in obj["segments"]:
            p_x = segment["start"][0]
            p_y = segment["start"][1]
            GL.glBegin(GL.GL_TRIANGLE_STRIP)
            GL.glVertex3f(p_x, p_y, 0.0)
            GL.glVertex3f(p_x, p_y, project["setup"]["mill"]["depth"])
            p_x = segment["end"][0]
            p_y = segment["end"][1]
            GL.glVertex3f(p_x, p_y, 0.0)
            GL.glVertex3f(p_x, p_y, project["setup"]["mill"]["depth"])
            GL.glEnd()

    # object faces (top)
    GL.glColor4f(0.0, 0.75, 0.3, 0.5)
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
        if obj["closed"]:
            vertex_data = object2vertex(obj)
            gluTessBeginContour(tess)
            for pos, p_x in enumerate(vertex_data[0]):
                p_xy = (p_x, vertex_data[1][pos], 0.0)
                gluTessVertex(tess, p_xy, p_xy)
            gluTessEndContour(tess)
    gluTessEndPolygon(tess)
    gluDeleteTess(tess)


def draw_line(p_1: dict, p_2: dict, project: dict) -> None:
    """callback funktion for GcodeParser to draw the lines"""
    p_from = (p_1["X"], p_1["Y"], p_1["Z"])
    p_to = (p_2["X"], p_2["Y"], p_2["Z"])
    line_width = project["setup"]["tool"]["diameter"]
    mode = project["setup"]["view"]["path"]
    draw_mill_line(p_from, p_to, line_width, mode)


def draw_gcode_path(project: dict) -> None:
    """draws the gcode path"""
    GL.glLineWidth(2)
    GcodeParser(project["gcode"]).draw(draw_line, (project,))
