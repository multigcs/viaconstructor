"""OpenGL drawing functions"""

from typing import Sequence

from PyQt5 import QtCore
from PyQt5.QtGui import QPainter, QPalette, QPen, QPixmap  # pylint: disable=E0611
from PyQt5.QtWidgets import QLabel, QSizePolicy  # pylint: disable=E0611

from .preview_plugins.gcode import GcodeParser
from .preview_plugins.hpgl import HpglParser

painter = {
    "offset_x": 300.0,
    "offset_y": 600.0,
    "scale": 5.0,
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


def draw_line_2d(p_from: Sequence[float], p_to: Sequence[float]) -> None:
    painter["ctx"].drawLine(
        QtCore.QLineF(  # type: ignore
            (painter["offset_x"] + p_from[0]) * painter["scale"],  # type: ignore
            (painter["offset_y"] + p_from[1]) * -painter["scale"],  # type: ignore
            (painter["offset_x"] + p_to[0]) * painter["scale"],  # type: ignore
            (painter["offset_y"] + p_to[1]) * -painter["scale"],  # type: ignore
        )
    )


def draw_circle_2d(p_center: Sequence[float], p_size: float) -> None:
    painter["ctx"].drawEllipse(
        QtCore.QPointF(  # type: ignore
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
            parser = GcodeParser(project["machine_cmd"])
            parser.draw(draw_line, (project,))
        elif project["suffix"] in {"hpgl", "hpg"}:
            project["setup"]["machine"]["g54"] = False
            project["setup"]["workpiece"]["offset_z"] = 0.0
            HpglParser(project["machine_cmd"]).draw(draw_line, (project,))
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
    painter["scale"] = min(s_w / size_x, s_h / size_y) / 1.4
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
    painter["ctx"].end()  # type: ignore
