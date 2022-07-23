"""viaconstructor tool."""

import argparse
import gettext
import json
import math
import os
import re
import sys
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import Union

from PyQt5.QtGui import (  # pylint: disable=E0611
    QIcon,
    QStandardItem,
    QStandardItemModel,
)
from PyQt5.QtOpenGL import QGLFormat, QGLWidget  # pylint: disable=E0611
from PyQt5.QtWidgets import (  # pylint: disable=E0611
    QAction,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from .calc import (
    calc_distance,
    clean_segments,
    find_tool_offsets,
    found_next_tab_point,
    line_center_2d,
    mirror_objects,
    move_objects,
    objects2minmax,
    objects2polyline_offsets,
    rotate_objects,
    segments2objects,
)
from .dxfread import DxfReader
from .gldraw import (
    draw_grid,
    draw_maschinecode_path,
    draw_object_edges,
    draw_object_faces,
    draw_object_ids,
)
from .hpglread import HpglReader
from .machine_cmd import polylines2machine_cmd
from .output_plugins.gcode_linuxcnc import PostProcessorGcodeLinuxCNC
from .output_plugins.hpgl import PostProcessorHpgl
from .setupdefaults import setup_defaults
from .svgread import SvgReader

try:
    from OpenGL import GL
except ImportError:
    QApplication(sys.argv)
    QMessageBox.critical(None, "OpenGL", "PyOpenGL must be installed.")  # type: ignore
    sys.exit(1)


LAYER_REGEX = re.compile(r"([a-zA-Z]{1,4}):\s*([+-]?([0-9]+([.][0-9]*)?|[.][0-9]+))")


def no_translation(text):
    return text


# i18n
_ = no_translation
lang = os.environ.get("LANGUAGE")
if lang:
    this_dir, this_filename = os.path.split(__file__)
    localedir = os.path.join(this_dir, "..", "locales")
    try:
        lang_translations = gettext.translation(
            "base", localedir=localedir, languages=[lang]
        )
        lang_translations.install()
        _ = lang_translations.gettext
    except FileNotFoundError:
        pass


class GLWidget(QGLWidget):
    """customized GLWidget."""

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
    tab_selector = False
    selection = ()
    size_x = 0
    size_y = 0

    def __init__(self, project: dict, update_drawing):
        """init function."""
        super(GLWidget, self).__init__()
        self.project: dict = project
        self.project["gllist"] = []
        self.startTimer(40)
        self.update_drawing = update_drawing
        self.setMouseTracking(True)

    def initializeGL(self) -> None:  # pylint: disable=C0103
        """glinit function."""
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()

        if self.frameGeometry().width() == 0:
            self.aspect = 1.0
        else:
            self.aspect = self.frameGeometry().height() / self.frameGeometry().width()

        hight = 0.2
        width = hight * self.aspect

        if self.ortho:
            GL.glOrtho(
                -hight * 2.5, hight * 2.5, -width * 2.5, width * 2.5, -1000, 1000
            )
        else:
            GL.glFrustum(-hight, hight, -width, width, 0.5, 100.0)

        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()
        GL.glClearColor(0.0, 0.0, 0.0, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glClearDepth(1.0)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_CULL_FACE)
        GL.glEnable(GL.GL_NORMALIZE)
        GL.glDepthFunc(GL.GL_LEQUAL)
        GL.glDepthMask(GL.GL_TRUE)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)

    def resizeGL(self, width, hight) -> None:  # pylint: disable=C0103
        """glresize function."""
        self.screen_w = width
        self.screen_h = hight
        GL.glViewport(0, 0, width, hight)
        self.initializeGL()

    def paintGL(self) -> None:  # pylint: disable=C0103
        """glpaint function."""
        min_max = self.project["minMax"]
        if not min_max:
            return
        self.size_x = min_max[2] - min_max[0]
        self.size_y = min_max[3] - min_max[1]
        self.scale = min(1.0 / self.size_x, 1.0 / self.size_y) / 1.4

        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glEnable(GLWidget.GL_MULTISAMPLE)
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

        if self.selection:
            depth = self.project["setup"]["mill"]["depth"] - 0.1
            GL.glLineWidth(5)
            GL.glColor4f(0.0, 1.0, 1.0, 1.0)
            GL.glBegin(GL.GL_LINES)
            GL.glVertex3f(self.selection[0][0], self.selection[0][1], depth)
            GL.glVertex3f(self.selection[1][0], self.selection[1][1], depth)
            GL.glEnd()
        GL.glPopMatrix()

    def toggle_tab_selector(self) -> None:
        self.tab_selector = not self.tab_selector
        if self.tab_selector:
            self.view_2d()

    def view_2d(self) -> None:
        """toggle view function."""
        self.ortho = True
        self.rot_x = 0.0
        self.rot_y = 0.0
        self.rot_z = 0.0
        self.initializeGL()

    def view_reset(self) -> None:
        """toggle view function."""
        if self.tab_selector:
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
        if self.tab_selector:
            if self.mbutton == 1:
                if self.selection:
                    self.project["tabs"]["data"].append(self.selection)
                self.update_drawing()
                self.update()
                self.project["app"].update_tabs()
            elif self.mbutton == 2:
                sel_idx = -1
                sel_dist = -1
                for tab_idx, tab in enumerate(self.project["tabs"]["data"]):
                    tab_pos = line_center_2d(tab[0], tab[1])

                    dist = calc_distance((self.mouse_pos_x, self.mouse_pos_y), tab_pos)
                    if sel_dist < 0 or dist < sel_dist:
                        sel_dist = dist
                        sel_idx = tab_idx

                if 0.0 < sel_dist < 10.0:
                    del self.project["tabs"]["data"][sel_idx]
                    self.update_drawing()
                    self.update()
                    self.project["app"].update_tabs()

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
        elif self.mbutton == 2 and not self.tab_selector:
            moffset = self.mpos - event.pos()
            self.rot_z = self.rot_z_last - moffset.x() / 4
            self.trans_z = self.trans_z_last + moffset.y() / 500
            if self.ortho:
                self.ortho = False
                self.initializeGL()
        elif self.mbutton == 4 and not self.tab_selector:
            moffset = self.mpos - event.pos()
            self.rot_x = self.rot_x_last + -moffset.x() / 4
            self.rot_y = self.rot_y_last - moffset.y() / 4
            if self.ortho:
                self.ortho = False
                self.initializeGL()
        elif self.tab_selector:
            (self.mouse_pos_x, self.mouse_pos_y) = self.mouse_pos_to_real_pos(
                event.pos()
            )
            self.selection = found_next_tab_point(
                (self.mouse_pos_x, self.mouse_pos_y), self.project["offsets"]
            )

    def wheelEvent(self, event) -> None:  # pylint: disable=C0103,W0613
        """mouse wheel moved."""
        if event.angleDelta().y() > 0:
            self.scale_xyz += 0.1
        else:
            self.scale_xyz -= 0.1


class ViaConstructor:
    """viaconstructor main class."""

    project: dict = {
        "setup_defaults": setup_defaults(_),
        "filename_draw": "",
        "filename_machine_cmd": "",
        "suffix": "ngc",
        "axis": ["X", "Y", "Z"],
        "machine_cmd": "",
        "segments": {},
        "objects": {},
        "offsets": {},
        "gllist": [],
        "maxOuter": [],
        "minMax": [],
        "table": [],
        "glwidget": None,
        "status": "INIT",
        "tabs": {
            "data": [],
            "table": None,
        },
    }
    save_tabs = "ask"
    draw_reader: Union[DxfReader, SvgReader, HpglReader]

    def run_calculation(self) -> None:
        """run all calculations."""
        psetup: dict = self.project["setup"]
        min_max = objects2minmax(self.project["objects"])
        self.project["minMax"] = min_max

        if psetup["mill"]["zero"] == "bottomLeft":
            move_objects(self.project["objects"], -min_max[0], -min_max[1])
        elif psetup["mill"]["zero"] == "bottomRight":
            move_objects(self.project["objects"], -min_max[2], -min_max[1])
        elif psetup["mill"]["zero"] == "topLeft":
            move_objects(self.project["objects"], -min_max[0], -min_max[3])
        elif psetup["mill"]["zero"] == "topRight":
            move_objects(self.project["objects"], -min_max[2], -min_max[3])
        elif psetup["mill"]["zero"] == "center":
            xdiff = min_max[2] - min_max[0]
            ydiff = min_max[3] - min_max[1]
            move_objects(
                self.project["objects"],
                -min_max[0] - xdiff / 2.0,
                -min_max[1] - ydiff / 2.0,
            )

        self.project["minMax"] = objects2minmax(self.project["objects"])

        # create toolpath from objects
        self.project["offsets"] = objects2polyline_offsets(
            psetup["tool"]["diameter"],
            self.project["objects"],
            self.project["maxOuter"],
            psetup["mill"]["small_circles"],
        )

        # create machine commands
        if self.project["setup"]["maschine"]["plugin"] == "gcode_linuxcnc":
            output_plugin = PostProcessorGcodeLinuxCNC
            self.project["suffix"] = output_plugin.suffix()
            self.project["axis"] = output_plugin.axis()
        elif self.project["setup"]["maschine"]["plugin"] == "hpgl":
            output_plugin = PostProcessorHpgl
            self.project["suffix"] = output_plugin.suffix()
            self.project["axis"] = output_plugin.axis()
        else:
            print(
                f"ERROR: Unknown maschine output plugin: {self.project['setup']['maschine']['plugin']}"
            )
            sys.exit(1)
        self.project["machine_cmd"] = polylines2machine_cmd(
            self.project, output_plugin()
        )

        self.project["textwidget"].clear()
        self.project["textwidget"].insertPlainText(self.project["machine_cmd"])
        self.project["textwidget"].verticalScrollBar().setValue(0)

    def _toolbar_flipx(self) -> None:
        mirror_objects(self.project["objects"], self.project["minMax"], vertical=True)
        self.project["minMax"] = objects2minmax(self.project["objects"])
        self.update_drawing()

    def _toolbar_flipy(self) -> None:
        mirror_objects(self.project["objects"], self.project["minMax"], horizontal=True)
        self.project["minMax"] = objects2minmax(self.project["objects"])
        self.update_drawing()

    def _toolbar_rotate(self) -> None:
        rotate_objects(self.project["objects"], self.project["minMax"])
        self.project["minMax"] = objects2minmax(self.project["objects"])
        self.update_drawing()

    def _toolbar_view_2d(self) -> None:
        """center view."""
        self.project["glwidget"].view_2d()

    def _toolbar_toggle_tab_selector(self) -> None:
        """center view."""
        self.project["glwidget"].toggle_tab_selector()

    def _toolbar_view_reset(self) -> None:
        """center view."""
        self.project["glwidget"].view_reset()

    def machine_cmd_save(self, filename: str) -> bool:
        with open(filename, "w") as fd_machine_cmd:
            fd_machine_cmd.write(self.project["machine_cmd"])
            # jsetup = deepcopy(self.project["setup"])
            # if "system" in jsetup:
            #    del jsetup["system"]
            # fd_machine_cmd.write(f"(setup={json.dumps(jsetup)})")
            fd_machine_cmd.write("\n")
            return True
        return False

    def _toolbar_save_machine_cmd(self) -> None:
        """save machine_cmd."""
        self.status_bar.showMessage("save machine_cmd..")
        file_dialog = QFileDialog(self.main)
        file_dialog.setNameFilters(
            [f"self.project['suffix'] (*.{self.project['suffix']})"]
        )
        self.project[
            "filename_machine_cmd"
        ] = f"{'.'.join(self.project['filename_draw'].split('.')[:-1])}.{self.project['suffix']}"
        name = file_dialog.getSaveFileName(
            self.main,
            "Save File",
            self.project["filename_machine_cmd"],
            f"{self.project['suffix']} (*.{self.project['suffix']})",
        )
        if name[0] and self.machine_cmd_save(name[0]):
            self.status_bar.showMessage(f"save maschine-code..done ({name[0]})")
        else:
            self.status_bar.showMessage("save maschine-code..cancel")

    def setup_load(self, filename: str) -> bool:
        if os.path.isfile(filename):
            setup = open(filename, "r").read()
            if setup:
                ndata = json.loads(setup)
                for sname in self.project["setup"]:
                    self.project["setup"][sname].update(ndata.get(sname, {}))
                return True
        return False

    def setup_save(self, filename: str) -> bool:
        with open(filename, "w") as fd_setup:
            fd_setup.write(json.dumps(self.project["setup"], indent=4, sort_keys=True))
            return True
        return False

    def _toolbar_save_setup(self) -> None:
        """save setup."""
        self.status_bar.showMessage("save setup..")
        if self.setup_save(self.args.setup):
            self.status_bar.showMessage("save setup..done")
        else:
            self.status_bar.showMessage("save setup..error")

    def _toolbar_load_setup_from(self) -> None:
        """load setup from."""
        self.status_bar.showMessage("load setup from..")
        file_dialog = QFileDialog(self.main)
        file_dialog.setNameFilters(["setup (*.json)"])
        name = file_dialog.getOpenFileName(
            self.main, "Load Setup", self.args.setup, "setup (*.json)"
        )
        if name[0] and self.setup_load(name[0]):
            self.update_global_setup()
            self.update_table()
            self.global_changed(0)
            self.update_drawing()
            self.status_bar.showMessage(f"load setup from..done ({name[0]})")
        else:
            self.status_bar.showMessage("load setup from..cancel")

    def _toolbar_save_setup_as(self) -> None:
        """save setup as."""
        self.status_bar.showMessage("save setup as..")
        file_dialog = QFileDialog(self.main)
        file_dialog.setNameFilters(["setup (*.json)"])
        name = file_dialog.getSaveFileName(
            self.main, "Save Setup", self.args.setup, "setup (*.json)"
        )
        if name[0] and self.setup_save(name[0]):
            self.status_bar.showMessage(f"save setup as..done ({name[0]})")
        else:
            self.status_bar.showMessage("save setup as..cancel")

    def update_drawing(self, draw_only=False) -> None:
        """update drawings."""
        self.status_bar.showMessage("calculate..")
        if not draw_only:
            self.run_calculation()
        self.project["gllist"] = GL.glGenLists(1)
        GL.glNewList(self.project["gllist"], GL.GL_COMPILE)
        draw_grid(self.project)
        if not draw_maschinecode_path(self.project):
            self.status_bar.showMessage("error while drawing maschine commands")
        draw_object_ids(self.project)
        draw_object_edges(self.project)
        if self.project["setup"]["view"]["polygon_show"]:
            draw_object_faces(self.project)
        GL.glEndList()
        self.status_bar.showMessage("calculate..done")

    def materials_select(self, material_idx) -> None:
        """calculates the milling feedrate and tool-speed for the selected material
        see: https://www.precifast.de/schnittgeschwindigkeit-beim-fraesen-berechnen/
        """
        maschine_feedrate = self.project["setup"]["maschine"]["feedrate"]
        maschine_toolspeed = self.project["setup"]["maschine"]["tool_speed"]
        tool_number = self.project["setup"]["tool"]["number"]
        tool_diameter = self.project["setup"]["tool"]["diameter"]
        tool_vc = self.project["setup"]["tool"]["materialtable"][material_idx]["vc"]
        tool_speed = tool_vc * 1000 / (tool_diameter * math.pi)
        tool_speed = int(min(tool_speed, maschine_toolspeed))
        tool_blades = 2
        for tool in self.project["setup"]["tool"]["tooltable"]:
            if tool["number"] == tool_number:
                tool_blades = tool["blades"]
                break
        if tool_diameter <= 4.0:
            fz_key = "fz4"
        elif tool_diameter <= 8.0:
            fz_key = "fz8"
        else:
            fz_key = "fz12"
        material_fz = self.project["setup"]["tool"]["materialtable"][material_idx][
            fz_key
        ]
        feedrate = tool_speed * tool_blades * material_fz
        feedrate = int(min(feedrate, maschine_feedrate))

        info_test = []
        info_test.append("Some Milling and Tool Values will be changed:")
        info_test.append("")
        info_test.append(
            f" Feedrate: {feedrate} {'(!MACHINE-LIMIT)' if feedrate == maschine_feedrate else ''}"
        )
        info_test.append(
            f" Tool-Speed: {tool_speed} {'(!MACHINE-LIMIT)' if tool_speed == maschine_toolspeed else ''}"
        )
        info_test.append("")
        ret = QMessageBox.question(
            self.main,
            "Warning",
            "\n".join(info_test),
            QMessageBox.Ok | QMessageBox.Cancel,
        )
        if ret != QMessageBox.Ok:
            return

        self.project["status"] = "CHANGE"
        self.project["setup"]["tool"]["rate_h"] = int(feedrate)
        self.project["setup"]["tool"]["speed"] = int(tool_speed)
        self.update_global_setup()
        self.update_table()
        self.update_drawing()
        self.project["status"] = "READY"

    def tools_select(self, tool_idx) -> None:
        self.project["status"] = "CHANGE"
        self.project["setup"]["tool"]["diameter"] = float(
            self.project["setup"]["tool"]["tooltable"][tool_idx]["diameter"]
        )
        self.project["setup"]["tool"]["number"] = int(
            self.project["setup"]["tool"]["tooltable"][tool_idx]["number"]
        )
        self.update_global_setup()
        self.update_table()
        self.update_drawing()
        self.project["status"] = "READY"

    def table_select(self, section, name, row_idx) -> None:
        if section == "tool" and name == "tooltable":
            self.tools_select(row_idx)
        elif section == "tool" and name == "materialtable":
            self.materials_select(row_idx)

    def object_changed(self, obj_idx, sname, ename, value) -> None:
        """object changed."""
        if self.project["status"] == "CHANGE":
            return

        entry_type = self.project["setup_defaults"][sname][ename]["type"]
        if entry_type == "bool":
            value = bool(value == 2)
        elif entry_type == "select":
            value = str(value)
        elif entry_type == "float":
            value = float(value)
        elif entry_type == "int":
            value = int(value)
        elif entry_type == "table":
            pass
        else:
            print(f"Unknown setup-type: {entry_type}")
            value = None
        self.project["objects"][obj_idx]["setup"][sname][ename] = value

        self.update_drawing()

    def update_table(self) -> None:
        """update objects table."""

        self.project["objmodel"].clear()
        self.project["objmodel"].setHorizontalHeaderLabels(["Object", "Value"])
        # self.project["objwidget"].header().setDefaultSectionSize(180)
        self.project["objwidget"].setModel(self.project["objmodel"])
        root = self.project["objmodel"].invisibleRootItem()

        for obj_idx, obj in self.project["objects"].items():
            if obj.get("layer", "").startswith("BREAKS:") or obj.get(
                "layer", ""
            ).startswith("_TABS"):
                continue
            root.appendRow(
                [
                    QStandardItem(
                        f"#{obj_idx} {'closed' if obj['closed'] else 'open'}"
                    ),
                ]
            )
            obj_root = root.child(root.rowCount() - 1)
            for sname in ("mill", "pockets", "tabs"):
                obj_root.appendRow(
                    [
                        QStandardItem(sname),
                    ]
                )
                section_root = obj_root.child(obj_root.rowCount() - 1)
                for ename, entry in self.project["setup_defaults"][sname].items():
                    value = obj["setup"][sname][ename]
                    if entry.get("per_object"):
                        title_cell = QStandardItem(ename)
                        value_cell = QStandardItem("")
                        section_root.appendRow([title_cell, value_cell])
                        if entry["type"] == "bool":
                            checkbox = QCheckBox(entry.get("title", ename))
                            checkbox.setChecked(value)
                            checkbox.setToolTip(
                                entry.get("tooltip", f"{sname}/{ename}")
                            )
                            checkbox.stateChanged.connect(partial(self.object_changed, obj_idx, sname, ename))  # type: ignore
                            self.project["objwidget"].setIndexWidget(
                                value_cell.index(), checkbox
                            )
                        elif entry["type"] == "select":
                            combobox = QComboBox()
                            for option in entry["options"]:
                                combobox.addItem(option[0])
                            combobox.setCurrentText(value)
                            combobox.setToolTip(
                                entry.get("tooltip", f"{sname}/{ename}")
                            )
                            combobox.currentTextChanged.connect(partial(self.object_changed, obj_idx, sname, ename))  # type: ignore
                            self.project["objwidget"].setIndexWidget(
                                value_cell.index(), combobox
                            )
                        elif entry["type"] == "float":
                            spinbox = QDoubleSpinBox()
                            spinbox.setMinimum(entry["min"])
                            spinbox.setMaximum(entry["max"])
                            spinbox.setValue(value)
                            spinbox.setToolTip(entry.get("tooltip", f"{sname}/{ename}"))
                            spinbox.valueChanged.connect(partial(self.object_changed, obj_idx, sname, ename))  # type: ignore
                            self.project["objwidget"].setIndexWidget(
                                value_cell.index(), spinbox
                            )
                        elif entry["type"] == "int":
                            spinbox = QSpinBox()
                            spinbox.setMinimum(entry["min"])
                            spinbox.setMaximum(entry["max"])
                            spinbox.setValue(value)
                            spinbox.setToolTip(entry.get("tooltip", f"{sname}/{ename}"))
                            spinbox.valueChanged.connect(partial(self.object_changed, obj_idx, sname, ename))  # type: ignore
                            self.project["objwidget"].setIndexWidget(
                                value_cell.index(), spinbox
                            )
                        elif entry["type"] == "table":
                            pass
                        else:
                            print(f"Unknown setup-type: {entry['type']}")
        # self.project["objwidget"].expandAll()

    def update_tabs(self) -> None:
        """update tabs table."""
        if self.save_tabs == "ask":
            self.project["glwidget"].mouseReleaseEvent("")
            info_test = []
            info_test.append("Should i save tabs in the DXF-File ?")
            info_test.append("")
            info_test.append(" this will create a new layer named _TABS")
            info_test.append(" exsiting layers named")
            info_test.append(" _TABS* and BREAKS:*")
            info_test.append(" will be removed !")
            info_test.append("")
            ret = QMessageBox.question(
                self.main,
                "Warning",
                "\n".join(info_test),
                QMessageBox.Yes | QMessageBox.No,
            )
            if ret == QMessageBox.Yes:
                self.save_tabs = "yes"
            else:
                self.save_tabs = "no"

        if self.save_tabs == "yes":
            self.draw_reader.save_tabs(self.project["tabs"]["data"])

    def global_changed(self, value) -> None:  # pylint: disable=W0613
        """global setup changed."""

        if self.project["status"] == "CHANGE":
            return

        old_setup = deepcopy(self.project["setup"])
        for sname in self.project["setup_defaults"]:
            for ename, entry in self.project["setup_defaults"][sname].items():
                if entry["type"] == "bool":
                    self.project["setup"][sname][ename] = entry["widget"].isChecked()
                elif entry["type"] == "select":
                    self.project["setup"][sname][ename] = entry["widget"].currentText()
                elif entry["type"] == "float":
                    self.project["setup"][sname][ename] = entry["widget"].value()
                elif entry["type"] == "int":
                    self.project["setup"][sname][ename] = entry["widget"].value()
                elif entry["type"] == "table":
                    for row_idx in range(entry["widget"].rowCount()):
                        col_idx = 0
                        for key, col_type in entry["columns"].items():
                            value = entry["widget"].item(row_idx, col_idx + 1).text()
                            if col_type == "str":
                                self.project["setup"][sname][ename][row_idx][key] = str(
                                    value
                                )
                            elif col_type == "int":
                                self.project["setup"][sname][ename][row_idx][key] = int(
                                    value
                                )
                            elif col_type == "float":
                                self.project["setup"][sname][ename][row_idx][
                                    key
                                ] = float(value)
                            col_idx += 1
                else:
                    print(f"Unknown setup-type: {entry['type']}")

        if self.project["setup"]["mill"]["step"] >= 0.0:
            self.project["setup"]["mill"]["step"] = -0.05

        self.project["segments"] = deepcopy(self.project["segments_org"])
        self.project["segments"] = clean_segments(self.project["segments"])
        self.project["maxOuter"] = find_tool_offsets(self.project["objects"])

        for obj in self.project["objects"].values():
            for sect in ("tool", "mill", "pockets", "tabs"):
                for key, global_value in self.project["setup"][sect].items():
                    # change object value only if the value changed and the value diffs again the last value in global
                    if (
                        global_value != old_setup[sect][key]
                        and obj["setup"][sect][key] == old_setup[sect][key]
                    ):
                        obj["setup"][sect][key] = self.project["setup"][sect][key]

        self.update_table()
        self.update_drawing()

    def _toolbar_load_machine_cmd_setup(self) -> None:
        self.project[
            "filename_machine_cmd"
        ] = f"{'.'.join(self.project['filename_draw'].split('.')[:-1])}.{self.project['suffix']}"
        if os.path.isfile(self.project["filename_machine_cmd"]):
            self.status_bar.showMessage(
                f"loading setup from maschinecode: {self.project['filename_machine_cmd']}"
            )
            with open(self.project["filename_machine_cmd"], "r") as fd_machine_cmd:
                gdata = fd_machine_cmd.read()
                for g_line in gdata.split("\n"):
                    if g_line.startswith("(setup={"):
                        setup_json = g_line.strip("()").split("=", 1)[1]
                        ndata = json.loads(setup_json)
                        for sname in self.project["setup"]:
                            self.project["setup"][sname].update(ndata.get(sname, {}))
                        self.update_drawing()
                        self.status_bar.showMessage(
                            "loading setup from maschinecode..done"
                        )
                        return
        self.status_bar.showMessage("loading setup from maschinecode..failed")

    def _toolbar_exit(self) -> None:
        """exit button."""
        sys.exit(0)

    def create_toolbar(self) -> None:
        """creates the_toolbar."""
        toolbuttons = {
            _("Exit"): (
                "exit.png",
                "Ctrl+Q",
                _("Exit application"),
                self._toolbar_exit,
                True,
                "main",
            ),
            _("Save Machine-Commands"): (
                "save-gcode.png",
                "Ctrl+S",
                _("Save machine commands"),
                self._toolbar_save_machine_cmd,
                True,
                "machine_cmd",
            ),
            _("Load setup from"): (
                "load-setup.png",
                "",
                _("Load setup from"),
                self._toolbar_load_setup_from,
                True,
                "setup",
            ),
            _("Load setup from machine_cmd"): (
                "load-setup-gcode.png",
                "",
                _("Load-Setup from machine_cmd"),
                self._toolbar_load_machine_cmd_setup,
                False,  # os.path.isfile(self.project["filename_machine_cmd"]),
                "setup",
            ),
            _("Save setup as default"): (
                "save-setup.png",
                "",
                _("Save-Setup"),
                self._toolbar_save_setup,
                True,
                "setup",
            ),
            _("Save setup as"): (
                "save-setup-as.png",
                "",
                _("Save setup  as"),
                self._toolbar_save_setup_as,
                True,
                "setup",
            ),
            _("View-Reset"): (
                "view-reset.png",
                "",
                _("View-Reset"),
                self._toolbar_view_reset,
                True,
                "view",
            ),
            _("2D-View"): (
                "view-2d.png",
                "",
                _("2D-View"),
                self._toolbar_view_2d,
                True,
                "view",
            ),
            _("Flip-X"): (
                "flip-x.png",
                "",
                _("Flip-X workpiece"),
                self._toolbar_flipx,
                True,
                "workpiece",
            ),
            _("Flip-Y"): (
                "flip-y.png",
                "",
                _("Flip-Y workpiece"),
                self._toolbar_flipy,
                True,
                "workpiece",
            ),
            _("Rotate"): (
                "rotate.png",
                "",
                _("Rotate workpiece"),
                self._toolbar_rotate,
                True,
                "workpiece",
            ),
            _("Tab-Selector"): (
                "tab-selector.png",
                "",
                _("Tab-Selector"),
                self._toolbar_toggle_tab_selector,
                True,
                "tabs",
            ),
        }
        self.toolbar = QToolBar("top toolbar")
        self.main.addToolBar(self.toolbar)
        section = ""

        for title, toolbutton in toolbuttons.items():
            icon = os.path.join(self.this_dir, "..", "data", toolbutton[0])
            if not os.path.isfile(icon):
                icon = os.path.join("/usr", "local", "data", toolbutton[0])

            if toolbutton[5] != section:
                self.toolbar.addSeparator()
                section = toolbutton[5]
            if toolbutton[4]:
                action = QAction(
                    QIcon(icon),
                    title,
                    self.main,
                )
                if toolbutton[1]:
                    action.setShortcut(toolbutton[1])
                action.setStatusTip(toolbutton[2])
                action.triggered.connect(toolbutton[3])  # type: ignore
                self.toolbar.addAction(action)

    def update_global_setup(self) -> None:
        for sname in self.project["setup_defaults"]:
            for ename, entry in self.project["setup_defaults"][sname].items():
                if entry["type"] == "bool":
                    entry["widget"].setChecked(self.project["setup"][sname][ename])
                elif entry["type"] == "select":
                    entry["widget"].setCurrentText(self.project["setup"][sname][ename])
                elif entry["type"] == "float":
                    entry["widget"].setValue(self.project["setup"][sname][ename])
                elif entry["type"] == "int":
                    entry["widget"].setValue(self.project["setup"][sname][ename])
                elif entry["type"] == "table":
                    pass
                else:
                    print(f"Unknown setup-type: {entry['type']}")

    def create_global_setup(self, tabwidget) -> None:
        for sname in self.project["setup_defaults"]:
            vcontainer = QWidget()
            vlayout = QVBoxLayout(vcontainer)
            tabwidget.addTab(vcontainer, sname)
            for ename, entry in self.project["setup_defaults"][sname].items():
                container = QWidget()
                hlayout = QHBoxLayout(container)
                label = QLabel(_(entry.get("title", ename)))
                hlayout.addWidget(label)
                vlayout.addWidget(container)
                if entry["type"] == "bool":
                    checkbox = QCheckBox(_(entry.get("title", ename)))
                    checkbox.setChecked(self.project["setup"][sname][ename])
                    checkbox.setToolTip(entry.get("tooltip", f"{sname}/{ename}"))
                    checkbox.stateChanged.connect(self.global_changed)  # type: ignore
                    hlayout.addWidget(checkbox)
                    entry["widget"] = checkbox
                elif entry["type"] == "select":
                    combobox = QComboBox()
                    for option in entry["options"]:
                        combobox.addItem(option[0])
                    combobox.setCurrentText(self.project["setup"][sname][ename])
                    combobox.setToolTip(entry.get("tooltip", f"{sname}/{ename}"))
                    combobox.currentTextChanged.connect(self.global_changed)  # type: ignore
                    hlayout.addWidget(combobox)
                    entry["widget"] = combobox
                elif entry["type"] == "float":
                    spinbox = QDoubleSpinBox()
                    spinbox.setMinimum(entry["min"])
                    spinbox.setMaximum(entry["max"])
                    spinbox.setValue(self.project["setup"][sname][ename])
                    spinbox.setToolTip(entry.get("tooltip", f"{sname}/{ename}"))
                    spinbox.valueChanged.connect(self.global_changed)  # type: ignore
                    hlayout.addWidget(spinbox)
                    entry["widget"] = spinbox
                elif entry["type"] == "int":
                    spinbox = QSpinBox()
                    spinbox.setMinimum(entry["min"])
                    spinbox.setMaximum(entry["max"])
                    spinbox.setValue(self.project["setup"][sname][ename])
                    spinbox.setToolTip(entry.get("tooltip", f"{sname}/{ename}"))
                    spinbox.valueChanged.connect(self.global_changed)  # type: ignore
                    hlayout.addWidget(spinbox)
                    entry["widget"] = spinbox
                elif entry["type"] == "table":
                    table = QTableWidget()
                    label.setToolTip(entry.get("tooltip", f"{sname}/{ename}"))
                    table.setRowCount(len(self.project["setup"][sname][ename]))
                    idxf_offset = 0
                    table.setColumnCount(len(entry["columns"]))
                    if entry["selectable"]:
                        table.setColumnCount(len(entry["columns"]) + 1)
                        table.setHorizontalHeaderItem(0, QTableWidgetItem("Select"))
                        idxf_offset = 1
                    for col_idx, title in enumerate(entry["columns"]):
                        table.setHorizontalHeaderItem(
                            col_idx + idxf_offset, QTableWidgetItem(title)
                        )
                    for row_idx, row in enumerate(self.project["setup"][sname][ename]):
                        if entry["selectable"]:
                            button = QPushButton()
                            button.setIcon(
                                QIcon(
                                    os.path.join(
                                        self.this_dir, "..", "data", "select.png"
                                    )
                                )
                            )
                            button.setToolTip(_("select this row"))
                            button.clicked.connect(partial(self.table_select, sname, ename, row_idx))  # type: ignore
                            table.setCellWidget(row_idx, 0, button)
                            table.resizeColumnToContents(0)
                        for col_idx, key in enumerate(entry["columns"]):
                            table.setItem(
                                row_idx,
                                col_idx + idxf_offset,
                                QTableWidgetItem(str(row[key])),
                            )
                            table.resizeColumnToContents(col_idx + idxf_offset)
                    table.itemChanged.connect(self.global_changed)  # type: ignore
                    vlayout.addWidget(table)
                    entry["widget"] = table
                else:
                    print(f"Unknown setup-type: {entry['type']}")

    def __init__(self) -> None:
        """viaconstructor main init."""
        # arguments
        parser = argparse.ArgumentParser()
        parser.add_argument("filename", help="input file", type=str)
        parser.add_argument(
            "-s",
            "--setup",
            help="setup file",
            type=str,
            default=f"{os.path.join(Path.home(), 'viaconstructor.json')}",
        )
        parser.add_argument(
            "-o", "--output", help="save to machine_cmd", type=str, default=None
        )
        self.args = parser.parse_args()

        # load setup
        self.project["setup"] = {}
        for sname in self.project["setup_defaults"]:
            self.project["setup"][sname] = {}
            for oname, option in self.project["setup_defaults"][sname].items():
                self.project["setup"][sname][oname] = option["default"]

        if os.path.isfile(self.args.setup):
            self.setup_load(self.args.setup)

        # load drawing #
        if self.args.filename.lower().endswith(".svg"):
            self.draw_reader = SvgReader(self.args.filename)
            self.save_tabs = "no"
        elif self.args.filename.lower().endswith(".dxf"):
            self.draw_reader = DxfReader(self.args.filename)
        elif self.args.filename.lower().endswith(".hpgl"):
            self.draw_reader = HpglReader(self.args.filename)
        else:
            print(f"ERROR: Unknown file suffix: {self.args.filename}")
            sys.exit(1)

        self.project["segments_org"] = self.draw_reader.get_segments()
        self.project["filename_draw"] = self.args.filename
        self.project[
            "filename_machine_cmd"
        ] = f"{'.'.join(self.project['filename_draw'].split('.')[:-1])}.{self.project['suffix']}"

        # prepare #
        self.project["segments"] = deepcopy(self.project["segments_org"])
        self.project["segments"] = clean_segments(self.project["segments"])
        self.project["objects"] = segments2objects(self.project["segments"])
        self.project["maxOuter"] = find_tool_offsets(self.project["objects"])
        self.project["tabs"]["data"] = []

        for obj in self.project["objects"].values():
            obj["setup"] = {}
            for sect in ("tool", "mill", "pockets", "tabs"):
                obj["setup"][sect] = deepcopy(self.project["setup"][sect])
            layer = obj.get("layer")
            # experimental: get some milling data from layer name (https://groups.google.com/g/dxf2gcode-users/c/q3hPQkN2OCo)
            if layer:
                if layer.startswith("IGNORE:"):
                    obj["setup"]["mill"]["active"] = False
                elif layer.startswith("BREAKS:") or layer.startswith("_TABS"):
                    obj["setup"]["mill"]["active"] = False
                    for segment in obj["segments"]:
                        self.project["tabs"]["data"].append(
                            (
                                (segment["start"][0], segment["start"][1]),
                                (segment["end"][0], segment["end"][1]),
                            )
                        )
                elif layer.startswith("MILL:"):
                    matches = LAYER_REGEX.findall(obj["layer"])
                    if matches:
                        for match in matches:
                            cmd = match[0].upper()
                            value = match[1]
                            if cmd == "MILL":
                                obj["setup"]["mill"]["active"] = bool(value == "1")
                            elif cmd in ("MILLDEPTH", "MD"):
                                obj["setup"]["mill"]["depth"] = -abs(float(value))
                            elif cmd in ("SLICEDEPTH", "SD"):
                                obj["setup"]["mill"]["step"] = -abs(float(value))
                            elif cmd in ("FEEDXY", "FXY"):
                                obj["setup"]["tool"]["rate_h"] = int(value)
                            elif cmd in ("FEEDZ", "FZ"):
                                obj["setup"]["tool"]["rate_v"] = int(value)

        qapp = QApplication(sys.argv)
        window = QWidget()
        self.project["app"] = self

        my_format = QGLFormat.defaultFormat()
        my_format.setSampleBuffers(True)
        QGLFormat.setDefaultFormat(my_format)
        if not QGLFormat.hasOpenGL():
            QMessageBox.information(
                window,
                "OpenGL using samplebuffers",
                "This system does not support OpenGL.",
            )
            sys.exit(0)

        self.project["glwidget"] = GLWidget(self.project, self.update_drawing)

        self.main = QMainWindow()
        self.main.setWindowTitle(f"viaConstructor: {self.project['filename_draw']}")
        self.main.setCentralWidget(window)

        self.this_dir, self.this_filename = os.path.split(__file__)

        self.create_toolbar()

        self.status_bar = QStatusBar()
        self.main.setStatusBar(self.status_bar)
        self.status_bar.showMessage("startup")

        self.project["textwidget"] = QPlainTextEdit()
        self.project["objwidget"] = QTreeView()
        self.project["objmodel"] = QStandardItemModel()
        self.update_table()
        left_gridlayout = QGridLayout()
        left_gridlayout.addWidget(QLabel("Objects-Settings:"))

        ltabwidget = QTabWidget()
        ltabwidget.addTab(self.project["objwidget"], "Objects")

        left_gridlayout.addWidget(ltabwidget)

        tabwidget = QTabWidget()
        tabwidget.addTab(self.project["glwidget"], "3D-View")
        tabwidget.addTab(self.project["textwidget"], "G-Code")

        right_gridlayout = QGridLayout()
        right_gridlayout.addWidget(tabwidget)

        left_widget = QWidget()
        left_widget.setContentsMargins(0, 0, 0, 0)

        vbox = QVBoxLayout(left_widget)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(QLabel(_("Global-Settings:")))

        self.tabwidget = QTabWidget()
        self.create_global_setup(self.tabwidget)
        vbox.addWidget(self.tabwidget)

        bottom_container = QWidget()
        bottom_container.setContentsMargins(0, 0, 0, 0)
        bottom_container.setLayout(left_gridlayout)
        vbox.addWidget(bottom_container, stretch=1)

        right_widget = QWidget()
        right_widget.setLayout(right_gridlayout)

        hlay = QHBoxLayout(window)
        hlay.addWidget(left_widget, stretch=1)
        hlay.addWidget(right_widget, stretch=3)

        if self.args.output:
            self.update_drawing()
            print("saving machine_cmd to file:", self.args.output)
            open(self.args.output, "w").write(self.project["machine_cmd"])
        else:
            self.main.resize(1600, 1200)
            self.main.show()
            sys.exit(qapp.exec_())


if __name__ == "__main__":
    ViaConstructor()
