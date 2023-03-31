"""OpenGL drawing functions"""

from typing import Sequence

from PyQt5 import QtCore
from PyQt5.QtGui import QPainter, QPalette, QPen, QPixmap  # pylint: disable=E0611
from PyQt5.QtWidgets import QLabel, QSizePolicy  # pylint: disable=E0611

from .calc import (
    calc_distance,
    found_next_open_segment_point,
    found_next_point_on_segment,
    found_next_segment_point,
    found_next_tab_point,
    line_center_2d,
)
from .preview_plugins.gcode import GcodeParser
from .preview_plugins.hpgl import HpglParser
from .vc_types import VcSegment

painter = {
    "offset_x": 300.0,
    "offset_y": 600.0,
    "scale": 5.0,
    "scale_xyz": 1.0,
    "move_x": 0.0,
    "move_y": 0.0,
    "ctx": QPainter(),
}


class CanvasWidget(QLabel):  # pylint: disable=R0903
    """customized QPixmap."""

    GL_MULTISAMPLE = 0x809D
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
    painter = None

    def __init__(self, project: dict, update_drawing):
        """init function."""
        super(QLabel, self).__init__()  # pylint: disable=E1003
        self.project: dict = project
        self.project["gllist"] = []
        self.startTimer(40)
        self.update_drawing = update_drawing
        self.setMouseTracking(True)

        self.setBackgroundRole(QPalette.Base)  # type: ignore
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)  # type: ignore
        self.setScaledContents(True)

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
                        self.project["app"].update_object_setup()
                    elif self.selector_mode == "oselect":
                        self.selection_set = self.selection
                        self.project["app"].update_object_setup()
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
        draw_all(self.project)

    def mouseReleaseEvent(self, event) -> None:  # pylint: disable=C0103,W0613
        """mouse button released."""
        self.mbutton = None
        self.mpos = None
        draw_all(self.project)

    def mouse_pos_to_real_pos(self, mouse_pos) -> tuple:
        min_max = self.project["minMax"]
        mouse_pos_x = mouse_pos.x()
        mouse_pos_y = self.screen_h - mouse_pos.y()
        real_pos_x = (
            (
                (mouse_pos_x / self.screen_w - 0.5 + self.trans_x)
                / painter["scale"]
                / painter["scale_xyz"]
            )
            + (self.size_x / 2)
            + min_max[0]
        )
        real_pos_y = (
            (
                (mouse_pos_y / self.screen_h - 0.5 + self.trans_y)
                / painter["scale"]
                / painter["scale_xyz"]
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
            draw_all(self.project)
        elif self.selector_mode == "tab":
            (self.mouse_pos_x, self.mouse_pos_y) = self.mouse_pos_to_real_pos(
                event.pos()
            )
            self.selection = found_next_tab_point(
                (self.mouse_pos_x, self.mouse_pos_y), self.project["offsets"]
            )
            draw_all(self.project)
        elif self.selector_mode == "start":
            (self.mouse_pos_x, self.mouse_pos_y) = self.mouse_pos_to_real_pos(
                event.pos()
            )
            self.selection = found_next_point_on_segment(
                (self.mouse_pos_x, self.mouse_pos_y), self.project["objects"]
            )
            draw_all(self.project)
        elif self.selector_mode == "delete":
            (self.mouse_pos_x, self.mouse_pos_y) = self.mouse_pos_to_real_pos(
                event.pos()
            )
            self.selection = found_next_segment_point(
                (self.mouse_pos_x, self.mouse_pos_y), self.project["objects"]
            )
            draw_all(self.project)
        elif self.selector_mode == "oselect":
            (self.mouse_pos_x, self.mouse_pos_y) = self.mouse_pos_to_real_pos(
                event.pos()
            )
            self.selection = found_next_segment_point(
                (self.mouse_pos_x, self.mouse_pos_y), self.project["objects"]
            )
            draw_all(self.project)
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
            draw_all(self.project)

        elif self.mbutton == 2:
            moffset = self.mpos - event.pos()
            self.rot_z = self.rot_z_last - moffset.x() / 4
            self.trans_z = self.trans_z_last + moffset.y() / 500
            draw_all(self.project)
        elif self.mbutton == 4:
            moffset = self.mpos - event.pos()
            self.rot_x = self.rot_x_last + -moffset.x() / 4
            self.rot_y = self.rot_y_last - moffset.y() / 4
            draw_all(self.project)

    def wheelEvent(self, event) -> None:  # pylint: disable=C0103,W0613
        """mouse wheel moved."""
        if event.angleDelta().y() > 0:
            painter["scale_xyz"] += self.wheel_scale  # type: ignore
        else:
            painter["scale_xyz"] -= self.wheel_scale  # type: ignore

        draw_all(self.project)

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
        self.rot_x = 0.0
        self.rot_y = 0.0
        self.rot_z = 0.0

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
        painter["scale_xyz"] = 1.0


def draw_line_2d(p_from: Sequence[float], p_to: Sequence[float]) -> None:
    painter["ctx"].drawLine(  # type: ignore
        QtCore.QLineF(  # pylint: disable=I1101
            (painter["offset_x"] + p_from[0]) * painter["scale"],  # type: ignore
            (painter["offset_y"] + p_from[1]) * -painter["scale"],  # type: ignore
            (painter["offset_x"] + p_to[0]) * painter["scale"],  # type: ignore
            (painter["offset_y"] + p_to[1]) * -painter["scale"],  # type: ignore
        )
    )


def draw_circle_2d(p_center: Sequence[float], p_size: float) -> None:
    painter["ctx"].drawEllipse(  # type: ignore
        QtCore.QPointF(  # pylint: disable=I1101
            (painter["offset_x"] + p_center[0]) * painter["scale"],  # type: ignore
            (painter["offset_y"] + p_center[1]) * -painter["scale"],  # type: ignore
        ),
        p_size * painter["scale"],  # type: ignore
        p_size * -painter["scale"],  # type: ignore
    )


def draw_mill_line(
    p_from: Sequence[float],
    p_to: Sequence[float],
    width: float,  # pylint: disable=W0613
    mode: str,  # pylint: disable=W0613
    options: str,  # pylint: disable=W0613
    project: dict,  # pylint: disable=W0613
) -> None:
    """draws an milling line including direction and width"""

    if p_from[2] < 0.0 and p_to[2] < 0.0:
        painter["ctx"].setPen(QPen(QtCore.Qt.green, 1, QtCore.Qt.SolidLine))  # type: ignore  # pylint: disable=I1101
    else:
        painter["ctx"].setPen(QPen(QtCore.Qt.red, 1, QtCore.Qt.SolidLine))  # type: ignore  # pylint: disable=I1101

    draw_line_2d(p_from, p_to)


def draw_object_edges(
    project: dict, selected: int = -1  # pylint: disable=W0613
) -> None:
    """draws the edges of an object"""
    unit = project["setup"]["machine"]["unit"]
    depth = project["setup"]["mill"]["depth"]
    tabs_height = project["setup"]["tabs"]["height"]
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

    painter["ctx"].setPen(QPen(QtCore.Qt.white, 2, QtCore.Qt.SolidLine))  # type: ignore  # pylint: disable=I1101
    for _obj_idx, obj in project["objects"].items():
        if obj.get("layer", "").startswith("BREAKS:") or obj.get(
            "layer", ""
        ).startswith("_TABS"):
            continue

        for segment in obj.segments:
            draw_line_2d(segment.start, segment.end)

    # tabs
    painter["ctx"].setPen(QPen(QtCore.Qt.blue, 4, QtCore.Qt.SolidLine))  # type: ignore  # pylint: disable=I1101
    tabs = project.get("tabs", {}).get("data", ())
    if tabs:
        for tab in tabs:
            draw_line_2d(tab[0], tab[1])


def draw_line(p_1: dict, p_2: dict, options: str, project: dict) -> None:
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
    line_width = project["setup"]["tool"]["diameter"]
    mode = project["setup"]["view"]["path"]
    project["simulation_data"].append((p_from, p_to, line_width, mode, options))
    draw_mill_line(p_from, p_to, line_width, mode, options, project)


def draw_machinecode_path(project: dict) -> bool:
    """draws the machinecode path"""
    project["simulation_data"] = []

    try:
        if project["suffix"] in {"ngc", "gcode"}:
            gcode_parser = GcodeParser(project["machine_cmd"])
            toolpath = gcode_parser.get_path()
            for line in toolpath:
                draw_line(line[0], line[1], line[2], project)

        elif project["suffix"] in {"hpgl", "hpg"}:
            project["setup"]["machine"]["g54"] = False
            project["setup"]["workpiece"]["offset_z"] = 0.0

            hpgl_parser = HpglParser(project["machine_cmd"])
            toolpath = hpgl_parser.get_path()
            for line in toolpath:
                draw_line(line[0], line[1], line[2], project)

    except Exception as error_string:  # pylint: disable=W0703:
        print(f"ERROR: parsing machine_cmd: {error_string}")
        return False

    return True


def draw_grid(project: dict) -> None:
    """draws the grid"""
    min_max = project["minMax"]
    size = project["setup"]["view"]["grid_size"]
    start_x = int(min_max[0] / size) * size - size
    end_x = int(min_max[2] / size) * size + size
    start_y = int(min_max[1] / size) * size - size
    end_y = int(min_max[3] / size) * size + size
    z_offset = -project["setup"]["workpiece"]["offset_z"]
    mill_depth = project["setup"]["mill"]["depth"]
    unit = project["setup"]["machine"]["unit"]
    unitscale = 1.0
    if unit == "inch":
        unitscale = 25.4
        z_offset *= unitscale
        mill_depth *= unitscale

    painter["ctx"].setPen(QPen(QtCore.Qt.gray, 1, QtCore.Qt.SolidLine))  # type: ignore  # pylint: disable=I1101
    if project["setup"]["view"]["grid_show"]:
        # Grid-X
        for p_x in range(start_x, end_x + size, size):
            draw_line_2d((p_x, start_y), (p_x, end_y))
        # Grid-Y
        for p_y in range(start_y, end_y + size, size):
            draw_line_2d((start_x, p_y), (end_x, p_y))

    # Zero-Point
    painter["ctx"].setPen(QPen(QtCore.Qt.yellow, 1, QtCore.Qt.SolidLine))  # type: ignore  # pylint: disable=I1101
    draw_line_2d((0.0, start_y), (0.0, end_y))
    draw_line_2d((start_x, 0.0), (end_x, 0.0))

    painter["ctx"].setPen(QPen(QtCore.Qt.yellow, 3, QtCore.Qt.SolidLine))  # type: ignore  # pylint: disable=I1101
    draw_circle_2d((0, 0), 3)


def draw_all(project: dict) -> None:
    min_max = project["minMax"]
    if not min_max:
        return

    s_w = 1600
    s_h = 1600

    size_x = max(min_max[2] - min_max[0], 0.1)
    size_y = max(min_max[3] - min_max[1], 0.1)
    painter["scale"] = min(s_w / size_x, s_h / size_y) / 1.4 * painter["scale_xyz"]
    painter["offset_x"] = -min_max[0] - size_x / 2 + (s_w / 2 / painter["scale"])  # type: ignore
    painter["offset_y"] = -size_y / 2 - min_max[1] - (s_h / 2 / painter["scale"])  # type: ignore

    canvas = QPixmap(s_w, s_h)
    project["glwidget"].setPixmap(canvas)
    project["glwidget"].adjustSize()
    project["glwidget"].pixmap().fill(QtCore.Qt.black)  # type: ignore  # pylint: disable=I1101
    painter["ctx"]: QPainter = QPainter(project["glwidget"].pixmap())  # type: ignore

    draw_grid(project)

    painter["ctx"].setPen(QPen(QtCore.Qt.green, 1, QtCore.Qt.SolidLine))  # type: ignore  # pylint: disable=I1101

    if project["glwidget"]:
        if not draw_machinecode_path(project):
            print("error while drawing machine commands")

    selected = -1
    if (
        project["glwidget"]
        and project["glwidget"].selection_set
        and project["glwidget"].selector_mode in {"delete", "oselect"}
    ):
        selected = project["glwidget"].selection_set[2]

    draw_object_edges(project, selected=selected)

    if project["glwidget"].selection:
        if project["glwidget"].selector_mode == "start":
            draw_line_2d(
                (
                    project["glwidget"].selection[2][0] - 1,
                    project["glwidget"].selection[2][1] - 1,
                ),
                (
                    project["glwidget"].selection[2][0] + 1,
                    project["glwidget"].selection[2][1] + 1,
                ),
            )
            draw_line_2d(
                (
                    project["glwidget"].selection[2][0] - 1,
                    project["glwidget"].selection[2][1] + 1,
                ),
                (
                    project["glwidget"].selection[2][0] + 1,
                    project["glwidget"].selection[2][1] - 1,
                ),
            )
        elif project["glwidget"].selector_mode == "repair":
            if len(project["glwidget"].selection) > 4:
                draw_line_2d(
                    (
                        project["glwidget"].selection[0],
                        project["glwidget"].selection[1],
                    ),
                    (
                        project["glwidget"].selection[4],
                        project["glwidget"].selection[5],
                    ),
                )
        elif project["glwidget"].selector_mode == "delete":
            draw_line_2d(
                (
                    project["glwidget"].selection[0] - 1,
                    project["glwidget"].selection[1] - 1,
                ),
                (
                    project["glwidget"].selection[0] + 1,
                    project["glwidget"].selection[1] + 1,
                ),
            )
            draw_line_2d(
                (
                    project["glwidget"].selection[0] - 1,
                    project["glwidget"].selection[1] + 1,
                ),
                (
                    project["glwidget"].selection[0] + 1,
                    project["glwidget"].selection[1] - 1,
                ),
            )
        elif project["glwidget"].selector_mode == "oselect":
            draw_line_2d(
                (
                    project["glwidget"].selection[0] - 1,
                    project["glwidget"].selection[1] - 1,
                ),
                (
                    project["glwidget"].selection[0] + 1,
                    project["glwidget"].selection[1] + 1,
                ),
            )
            draw_line_2d(
                (
                    project["glwidget"].selection[0] - 1,
                    project["glwidget"].selection[1] + 1,
                ),
                (
                    project["glwidget"].selection[0] + 1,
                    project["glwidget"].selection[1] - 1,
                ),
            )
        else:
            draw_line_2d(
                (
                    project["glwidget"].selection[0][0],
                    project["glwidget"].selection[0][1],
                ),
                (
                    project["glwidget"].selection[1][0],
                    project["glwidget"].selection[1][1],
                ),
            )

    painter["ctx"].end()  # type: ignore
