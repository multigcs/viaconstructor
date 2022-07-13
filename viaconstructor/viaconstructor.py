"""viaconstructor tool."""

import argparse
import gettext
import json
import os
import re
import sys
from copy import deepcopy
from pathlib import Path

from PyQt5.QtGui import QIcon  # pylint: disable=E0611
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
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .calc import (
    clean_segments,
    find_tool_offsets,
    mirror_objects,
    move_objects,
    objects2minmax,
    objects2polyline_offsets,
    rotate_objects,
    segments2objects,
)
from .dxfread import DxfReader
from .gldraw import (
    draw_gcode_path,
    draw_grid,
    draw_object_edges,
    draw_object_faces,
    draw_object_ids,
)
from .machine_cmd import polylines2machine_cmd
from .output_plugins.gcode_linuxcnc import PostProcessorGcodeLinuxCNC
from .setupdefaults import setup_defaults

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

    def __init__(self, project: dict, update_drawing):
        """init function."""
        super(GLWidget, self).__init__()
        self.project: dict = project
        self.project["gllist"] = []
        self.startTimer(40)
        self.update_drawing = update_drawing

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
        size_x = min_max[2] - min_max[0]
        size_y = min_max[3] - min_max[1]
        self.scale = min(1.0 / size_x, 1.0 / size_y) / 1.4

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
            (-size_x / 2.0 - min_max[0]) * self.scale,
            (-size_y / 2.0 - min_max[1]) * self.scale,
            0.0,
        )
        GL.glScalef(self.scale, self.scale, self.scale)
        GL.glCallList(self.project["gllist"])
        GL.glPopMatrix()

    def view_2d(self) -> None:
        """toggle view function."""
        self.ortho = True
        self.rot_x = 0.0
        self.rot_y = 0.0
        self.rot_z = 0.0
        self.initializeGL()

    def view_reset(self) -> None:
        """toggle view function."""
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

    def mouseReleaseEvent(self, event) -> None:  # pylint: disable=C0103,W0613
        """mouse button released."""
        self.mbutton = None
        self.mpos = None

    def mouseMoveEvent(self, event) -> None:  # pylint: disable=C0103
        """mouse moved."""
        if self.mbutton == 1:
            moffset = self.mpos - event.pos()
            self.trans_x = self.trans_x_last + moffset.x() / self.screen_w
            self.trans_y = self.trans_y_last - moffset.y() / self.screen_h * self.aspect
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
            self.scale_xyz += 0.1
        else:
            self.scale_xyz -= 0.1


class ViaConstructor:
    """viaconstructor main class."""

    project: dict = {
        "setup_defaults": setup_defaults(_),
        "filename_dxf": "",
        "filename_machine_cmd": "",
        "gcode": [],
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
            "depth": 3.0,
            "data": [],
        },
    }

    def gcode_reload(self) -> None:
        """reload gcode."""
        # if self.project["textwidget"].toPlainText():
        #     self.project["gcode"] = self.project["textwidget"].toPlainText().split("\n")
        #     self.update_drawing(draw_only=True)

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
        self.project["machine_cmd"] = polylines2machine_cmd(
            self.project, PostProcessorGcodeLinuxCNC()
        )

        self.project["textwidget"].clear()
        self.project["textwidget"].insertPlainText(
            "\n".join(self.project["machine_cmd"])
        )
        self.project["textwidget"].verticalScrollBar().setValue(0)
        # self.project["textwidget"].setReadOnly(True)
        # self.project["textwidget"].textChanged.connect(self.gcode_reload)  # type: ignore

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

    def _toolbar_view_reset(self) -> None:
        """center view."""
        self.project["glwidget"].view_reset()

    def machine_cmd_save(self, filename: str) -> bool:
        with open(filename, "w") as fd_machine_cmd:
            fd_machine_cmd.write("\n".join(self.project["machine_cmd"]))
            fd_machine_cmd.write("\n")
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
        file_dialog.setNameFilters(["gcode (*.ngc)"])
        name = file_dialog.getSaveFileName(
            self.main,
            "Save File",
            self.project["filename_machine_cmd"],
            "gcode (*.ngc)",
        )
        if name[0] and self.machine_cmd_save(name[0]):
            self.status_bar.showMessage(f"save gcode..done ({name[0]})")
        else:
            self.status_bar.showMessage("save gcode..cancel")

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
        if not draw_gcode_path(self.project):
            self.status_bar.showMessage("error while drawing mashine commands")
        draw_object_ids(self.project)
        draw_object_edges(self.project)
        if self.project["setup"]["view"]["polygon_show"]:
            draw_object_faces(self.project)
        GL.glEndList()
        self.status_bar.showMessage("calculate..done")

    def object_changed(self, value) -> None:
        """object changed."""
        for obj_idx, obj in self.project["objects"].items():
            if obj.get("layer", "").startswith("BREAKS:"):
                continue
            s_n = 0
            for sname in self.project["setup_defaults"]:
                if sname not in {"tool", "mill", "pockets", "tabs"}:
                    continue
                for ename, entry in self.project["setup_defaults"][sname].items():
                    if entry.get("per_object"):
                        widget = self.project["tablewidget"].cellWidget(obj_idx, s_n)
                        if entry["type"] == "bool":
                            value = widget.isChecked()
                        elif entry["type"] == "select":
                            value = widget.currentText()
                        elif entry["type"] == "float":
                            value = widget.value()
                        elif entry["type"] == "int":
                            value = widget.value()
                        else:
                            print(f"Unknown setup-type: {entry['type']}")
                            value = None
                        obj["setup"][sname][ename] = value
                        s_n += 1
        self.update_drawing()

    def update_table(self) -> None:
        """update tabe."""
        table_widget = self.project["tablewidget"]
        table_widget.setRowCount(len(self.project["objects"]))
        s_n = 0
        for sname in self.project["setup_defaults"]:
            if sname not in {"tool", "mill", "pockets", "tabs"}:
                continue
            for ename, entry in self.project["setup_defaults"][sname].items():
                if entry.get("per_object"):
                    table_widget.setColumnCount(s_n + 1)
                    table_widget.setHorizontalHeaderItem(
                        s_n, QTableWidgetItem(entry.get("title", ename))
                    )
                    s_n += 1

        for obj_idx, obj in self.project["objects"].items():
            if obj.get("layer", "").startswith("BREAKS:"):
                continue
            table_widget.setVerticalHeaderItem(obj_idx, QTableWidgetItem(f"#{obj_idx}"))
            s_n = 0
            for sname in self.project["setup_defaults"]:
                if sname not in {"tool", "mill", "pockets", "tabs"}:
                    continue
                for ename, entry in self.project["setup_defaults"][sname].items():
                    value = obj["setup"][sname][ename]
                    if entry.get("per_object"):
                        if entry["type"] == "bool":
                            checkbox = QCheckBox(entry.get("title", ename))
                            checkbox.setChecked(value)
                            checkbox.setToolTip(
                                entry.get("tooltip", f"{sname}/{ename}")
                            )
                            checkbox.stateChanged.connect(self.object_changed)  # type: ignore
                            table_widget.setCellWidget(obj_idx, s_n, checkbox)
                        elif entry["type"] == "select":
                            combobox = QComboBox()
                            for option in entry["options"]:
                                combobox.addItem(option[0])
                            combobox.setCurrentText(value)
                            combobox.setToolTip(
                                entry.get("tooltip", f"{sname}/{ename}")
                            )
                            combobox.currentTextChanged.connect(self.object_changed)  # type: ignore
                            table_widget.setCellWidget(obj_idx, s_n, combobox)
                        elif entry["type"] == "float":
                            spinbox = QDoubleSpinBox()
                            spinbox.setMinimum(entry["min"])
                            spinbox.setMaximum(entry["max"])
                            spinbox.setValue(value)
                            spinbox.setToolTip(entry.get("tooltip", f"{sname}/{ename}"))
                            spinbox.valueChanged.connect(self.object_changed)  # type: ignore
                            table_widget.setCellWidget(obj_idx, s_n, spinbox)
                        elif entry["type"] == "int":
                            spinbox = QSpinBox()
                            spinbox.setMinimum(entry["min"])
                            spinbox.setMaximum(entry["max"])
                            spinbox.setValue(value)
                            spinbox.setToolTip(entry.get("tooltip", f"{sname}/{ename}"))
                            spinbox.valueChanged.connect(self.object_changed)  # type: ignore
                            table_widget.setCellWidget(obj_idx, s_n, spinbox)
                        else:
                            print(f"Unknown setup-type: {entry['type']}")
                        s_n += 1

        table_widget.horizontalHeader().setStretchLastSection(True)
        table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def global_changed(self, value) -> None:  # pylint: disable=W0613
        """global setup changed."""
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
                else:
                    print(f"Unknown setup-type: {entry['type']}")

        if self.project["setup"]["mill"]["step"] >= 0.0:
            self.project["setup"]["mill"]["step"] = -0.05

        self.project["segments"] = deepcopy(self.project["segments_org"])
        self.project["segments"] = clean_segments(self.project["segments"])
        self.project["objects"] = segments2objects(self.project["segments"])
        self.project["maxOuter"] = find_tool_offsets(self.project["objects"])
        for obj in self.project["objects"].values():
            obj["setup"] = {}
            for sect in ("tool", "mill", "pockets", "tabs"):
                obj["setup"][sect] = self.project["setup"][sect]

        self.update_table()
        self.update_drawing()

    def _toolbar_load_machine_cmd_setup(self) -> None:
        if os.path.isfile(self.project["filename_machine_cmd"]):
            self.status_bar.showMessage(
                f"loading setup from gcode: {self.project['filename_machine_cmd']}"
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
                        self.status_bar.showMessage("loading setup from gcode..done")
                        return
        self.status_bar.showMessage("loading setup from gcode..failed")

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
        }
        self.toolbar = QToolBar("top toolbar")
        self.main.addToolBar(self.toolbar)
        section = ""
        for title, toolbutton in toolbuttons.items():
            if toolbutton[5] != section:
                self.toolbar.addSeparator()
                section = toolbutton[5]
            if toolbutton[4]:
                action = QAction(
                    QIcon(os.path.join(self.this_dir, "..", "data", toolbutton[0])),
                    title,
                    self.main,
                )
                if toolbutton[1]:
                    action.setShortcut(toolbutton[1])
                action.setStatusTip(toolbutton[2])
                action.triggered.connect(toolbutton[3])  # type: ignore
                self.toolbar.addAction(action)

    def update_global_setup(self) -> None:
        # self.tabwidget
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
                else:
                    print(f"Unknown setup-type: {entry['type']}")
                vlayout.addWidget(container)

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

        # load dxf #
        dxf_reader = DxfReader(self.args.filename)
        self.project["segments_org"] = dxf_reader.get_segments()
        self.project["filename_dxf"] = self.args.filename
        self.project[
            "filename_machine_cmd"
        ] = f"{'.'.join(self.project['filename_dxf'].split('.')[:-1])}.ngc"

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
                elif layer.startswith("BREAKS:"):
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
                                obj["setup"]["mill"]["rate_h"] = int(value)
                            elif cmd in ("FEEDZ", "FZ"):
                                obj["setup"]["mill"]["rate_v"] = int(value)

        qapp = QApplication(sys.argv)
        window = QWidget()

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
        self.main.setWindowTitle("viaConstructor")
        self.main.setCentralWidget(window)

        self.this_dir, self.this_filename = os.path.split(__file__)

        self.create_toolbar()

        self.status_bar = QStatusBar()
        self.main.setStatusBar(self.status_bar)
        self.status_bar.showMessage("startup")

        self.project["textwidget"] = QPlainTextEdit()
        self.project["tablewidget"] = QTableWidget()
        self.update_table()
        left_gridlayout = QGridLayout()
        left_gridlayout.addWidget(QLabel("Objects-Settings:"))

        ltabwidget = QTabWidget()
        ltabwidget.addTab(self.project["tablewidget"], "Objects")
        # ltabwidget.addTab(self.project["textwidget"], "G-Code")

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
            open(self.args.output, "w").write("\n".join(self.project["machine_cmd"]))
        else:
            self.main.resize(1600, 1200)
            self.main.show()
            sys.exit(qapp.exec_())


if __name__ == "__main__":
    ViaConstructor()
