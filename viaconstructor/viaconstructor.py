"""viaconstructor tool."""

import json
import os
import sys
import argparse
from copy import deepcopy

from PyQt5.QtGui import QIcon  # pylint: disable=E0611
from PyQt5.QtWidgets import (  # pylint: disable=E0611
    QMainWindow,
    QStatusBar,
    QAction,
    QApplication,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
    QCheckBox,
    QHeaderView,
    QWidget,
    QVBoxLayout,
    QLabel,
    QDoubleSpinBox,
    QSpinBox,
    QGridLayout,
    QHBoxLayout,
    QTabWidget,
    QPlainTextEdit,
    QFileDialog,
)
from PyQt5.QtOpenGL import QGLFormat, QGLWidget  # pylint: disable=E0611

from .setupdefaults import setup_defaults
from .dxfread import DxfReader
from .gldraw import (
    draw_grid,
    draw_gcode_path,
    draw_object_edges,
    draw_object_ids,
    draw_object_faces,
)
from .gcode import polylines2gcode
from .calc import (
    objects2minmax,
    move_objects,
    objects2polyline_offsets,
    clean_segments,
    segments2objects,
    find_tool_offsets,
    # calc_distance,
    # rotate_objects,
    # mirror_objects,
)

try:
    from OpenGL import GL
except ImportError:
    QApplication(sys.argv)
    QMessageBox.critical(None, "OpenGL", "PyOpenGL must be installed.")  # type: ignore
    sys.exit(1)


class GLWidget(QGLWidget):
    """customized GLWidget."""

    GL_MULTISAMPLE = 0x809D
    rot_x = -10.0
    rot_y = -30.0
    rot_z = -10.0
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
            aspect = 1.0
        else:
            aspect = self.frameGeometry().height() / self.frameGeometry().width()

        hight = 0.2
        width = hight * aspect

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

        if self.project["status"] != "INIT":
            self.update_drawing()

    def resizeGL(self, width, hight) -> None:  # pylint: disable=C0103
        """glresize function."""
        GL.glViewport(0, 0, width, hight)
        self.initializeGL()

    def paintGL(self) -> None:  # pylint: disable=C0103
        """glpaint function."""
        min_max = self.project["minMax"]
        if not min_max:
            return
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glEnable(GLWidget.GL_MULTISAMPLE)
        GL.glTranslatef(-self.trans_x, -self.trans_y, self.trans_z - 1.2)

        GL.glRotatef(self.rot_x, 0.0, 1.0, 0.0)
        GL.glRotatef(self.rot_y, 1.0, 0.0, 0.0)
        GL.glRotatef(self.rot_z, 0.0, 0.0, 1.0)

        size_x = min_max[2] - min_max[0]
        size_y = min_max[3] - min_max[1]
        scale = 1 / size_x / 1.5

        GL.glTranslatef(
            (min_max[0] - size_x / 2) * scale, (min_max[1] - size_y / 2) * scale, 0.0
        )
        GL.glScalef(scale, scale, scale)
        GL.glCallList(self.project["gllist"])

        GL.glPopMatrix()

    def toggle_view(self) -> None:
        """toggle view function."""
        self.ortho = not self.ortho
        self.rot_x = 0.0
        self.rot_y = 0.0
        self.rot_z = 0.0
        self.trans_z = 0.0
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
        self.scale_last = self.scale

    def mouseReleaseEvent(self, event) -> None:  # pylint: disable=C0103,W0613
        """mouse button released."""
        self.mbutton = None
        self.mpos = None

    def mouseMoveEvent(self, event) -> None:  # pylint: disable=C0103
        """mouse moved."""
        if self.mbutton == 1:
            moffset = self.mpos - event.pos()
            self.rot_x = self.rot_x_last + -moffset.x() / 4
            self.rot_y = self.rot_y_last - moffset.y() / 4
        elif self.mbutton == 2:
            moffset = self.mpos - event.pos()
            self.rot_z = self.rot_z_last + moffset.x() / 4
            self.trans_z = self.trans_z_last + moffset.y() / 500
        elif self.mbutton == 4:
            moffset = self.mpos - event.pos()
            self.trans_x = self.trans_x_last + moffset.x() / 500
            self.trans_y = self.trans_y_last - moffset.y() / 500

    def wheelEvent(self, event) -> None:  # pylint: disable=C0103,W0613
        """mouse wheel moved."""
        if event.angleDelta().y() > 0:
            self.trans_z += 0.1
        else:
            self.trans_z -= 0.1


class ViaConstructor:
    """viaconstructor main class."""

    project: dict = {
        "setup_defaults": setup_defaults,
        "filename_dxf": "",
        "filename_gcode": "",
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
        """
        if psetup["workpiece"]["rotate"] == "1":
            rotate_objects(self.project["objects"])
            mirror_objects(self.project["objects"], min_max, False, True)
        elif psetup["workpiece"]["rotate"] == "2":
            mirror_objects(self.project["objects"], min_max, True, True)
        elif psetup["workpiece"]["rotate"] == "3":
            rotate_objects(self.project["objects"])
            mirror_objects(self.project["objects"], min_max, True, False)
        if psetup["workpiece"]["mirrorV"] or psetup["workpiece"]["mirrorH"]:
            mirror_objects(
                self.project["objects"],
                min_max,
                psetup["workpiece"]["mirrorV"],
                psetup["workpiece"]["mirrorH"],
            )
        """

        if psetup["workpiece"]["zero"] == "bottomLeft":
            move_objects(self.project["objects"], -min_max[0], -min_max[1])
        elif psetup["workpiece"]["zero"] == "bottomRight":
            move_objects(self.project["objects"], -min_max[2], -min_max[1])
        elif psetup["workpiece"]["zero"] == "topLeft":
            move_objects(self.project["objects"], -min_max[0], -min_max[3])
        elif psetup["workpiece"]["zero"] == "topRight":
            move_objects(self.project["objects"], -min_max[2], -min_max[3])
        elif psetup["workpiece"]["zero"] == "center":
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

        # create gcode
        self.project["gcode"] = polylines2gcode(self.project)

        self.project["textwidget"].clear()
        self.project["textwidget"].insertPlainText("\n".join(self.project["gcode"]))
        self.project["textwidget"].verticalScrollBar().setValue(0)
        # self.project["textwidget"].setReadOnly(True)
        self.project["textwidget"].textChanged.connect(self.gcode_reload)  # type: ignore

    def toolbar_save_gcode(self) -> None:
        """save gcode."""
        self.status_bar.showMessage("save gcode..")
        file_dialog = QFileDialog(self.main)
        file_dialog.setNameFilters(["gcode (*.ngc)"])
        name = file_dialog.getSaveFileName(
            self.main, "Save File", self.project["filename_gcode"], "gcode (*.ngc)"
        )
        if name[0]:
            open(name[0], "w").write("\n".join(self.project["gcode"]))
            self.status_bar.showMessage(f"save gcode..done ({name[0]})")
        else:
            self.status_bar.showMessage("save gcode..cancel")

    def toolbar_centerview(self) -> None:
        """center view."""
        self.project["glwidget"].toggle_view()

    def toolbar_save_setup(self) -> None:
        """save setup."""
        self.status_bar.showMessage("save setup..")
        open(self.args.setup, "w").write(
            json.dumps(self.project["setup"], indent=4, sort_keys=True)
        )
        self.status_bar.showMessage("save setup..done")

    def update_drawing(self, draw_only=False) -> None:
        """update drawings."""
        self.status_bar.showMessage("calculate..")
        if not draw_only:
            self.run_calculation()
        self.project["gllist"] = GL.glGenLists(1)
        GL.glNewList(self.project["gllist"], GL.GL_COMPILE)
        draw_grid(self.project)
        draw_gcode_path(self.project)
        draw_object_ids(self.project)
        draw_object_edges(self.project)
        draw_object_faces(self.project)
        GL.glEndList()
        self.status_bar.showMessage("calculate..done")

    def object_changed(self, value) -> None:
        """object changed."""
        for obj_idx, obj in self.project["objects"].items():
            s_n = 0
            for sname in self.project["setup_defaults"]:
                if sname not in {"tool", "mill"}:
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
                        obj[sname][ename] = value
                        s_n += 1
        self.update_drawing()

    def update_table(self) -> None:
        """update tabe."""
        table_widget = self.project["tablewidget"]
        table_widget.setRowCount(len(self.project["objects"]))
        s_n = 0
        for sname in self.project["setup_defaults"]:
            if sname not in {"tool", "mill"}:
                continue
            for ename, entry in self.project["setup_defaults"][sname].items():
                if entry.get("per_object"):
                    table_widget.setColumnCount(s_n + 1)
                    table_widget.setHorizontalHeaderItem(
                        s_n, QTableWidgetItem(entry.get("title", ename))
                    )
                    s_n += 1

        for obj_idx in self.project["objects"]:
            table_widget.setVerticalHeaderItem(obj_idx, QTableWidgetItem(f"#{obj_idx}"))
            s_n = 0
            for sname in self.project["setup_defaults"]:
                if sname not in {"tool", "mill"}:
                    continue
                for ename, entry in self.project["setup_defaults"][sname].items():
                    if entry.get("per_object"):
                        if entry["type"] == "bool":
                            checkbox = QCheckBox(entry.get("title", ename))
                            checkbox.setChecked(self.project["setup"][sname][ename])
                            checkbox.setToolTip(
                                entry.get("tooltip", f"{sname}/{ename}")
                            )
                            checkbox.stateChanged.connect(self.object_changed)  # type: ignore
                            table_widget.setCellWidget(obj_idx, s_n, checkbox)
                        elif entry["type"] == "select":
                            combobox = QComboBox()
                            for option in entry["options"]:
                                combobox.addItem(option[0])
                            combobox.setCurrentText(self.project["setup"][sname][ename])
                            combobox.setToolTip(
                                entry.get("tooltip", f"{sname}/{ename}")
                            )
                            combobox.currentTextChanged.connect(self.object_changed)  # type: ignore
                            table_widget.setCellWidget(obj_idx, s_n, combobox)
                        elif entry["type"] == "float":
                            spinbox = QDoubleSpinBox()
                            spinbox.setMinimum(entry["min"])
                            spinbox.setMaximum(entry["max"])
                            spinbox.setValue(self.project["setup"][sname][ename])
                            spinbox.setToolTip(entry.get("tooltip", f"{sname}/{ename}"))
                            spinbox.valueChanged.connect(self.object_changed)  # type: ignore
                            table_widget.setCellWidget(obj_idx, s_n, spinbox)
                        elif entry["type"] == "int":
                            spinbox = QSpinBox()
                            spinbox.setMinimum(entry["min"])
                            spinbox.setMaximum(entry["max"])
                            spinbox.setValue(self.project["setup"][sname][ename])
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
            obj["mill"] = deepcopy(self.project["setup"]["mill"])
            obj["tool"] = deepcopy(self.project["setup"]["tool"])

        for obj in self.project["objects"].values():
            obj["mill"]["step"] = self.project["setup"]["mill"]["step"]
            obj["mill"]["depth"] = self.project["setup"]["mill"]["depth"]

        self.update_table()

        self.update_drawing()

    def toolbar_exit(self) -> None:
        """exit button."""
        sys.exit(0)

    def __init__(self) -> None:
        """viaconstructor main init."""
        # arguments
        parser = argparse.ArgumentParser()
        parser.add_argument("filename", help="gcode file", type=str)
        parser.add_argument(
            "-s", "--setup", help="setup file", type=str, default="setup.json"
        )
        parser.add_argument(
            "-o", "--output", help="save to gcode", type=str, default=None
        )
        self.args = parser.parse_args()

        # load setup
        self.project["setup"] = {}
        for sname in self.project["setup_defaults"]:
            self.project["setup"][sname] = {}
            for oname, option in self.project["setup_defaults"][sname].items():
                self.project["setup"][sname][oname] = option["default"]

        if os.path.isfile(self.args.setup):
            setup = open(self.args.setup, "r").read()
            if setup:
                ndata = json.loads(setup)
                for sname in self.project["setup"]:
                    self.project["setup"][sname].update(ndata.get(sname, {}))

        # load and prepare #
        dxf_reader = DxfReader(self.args.filename)
        self.project["segments_org"] = dxf_reader.get_segments()
        self.project["filename_dxf"] = self.args.filename
        self.project[
            "filename_gcode"
        ] = f"{'.'.join(self.project['filename_dxf'].split('.')[:-1])}.ngc"
        self.project["segments"] = deepcopy(self.project["segments_org"])
        self.project["segments"] = clean_segments(self.project["segments"])
        self.project["objects"] = segments2objects(self.project["segments"])
        self.project["maxOuter"] = find_tool_offsets(self.project["objects"])
        for obj in self.project["objects"].values():
            obj["mill"] = deepcopy(self.project["setup"]["mill"])
            obj["tool"] = deepcopy(self.project["setup"]["tool"])

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

        exit_action = QAction(
            QIcon(os.path.join(self.this_dir, "..", "data", "exit.png")),
            "Exit",
            self.main,
        )
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Exit application")
        exit_action.triggered.connect(self.toolbar_exit)  # type: ignore
        toolbar = self.main.addToolBar("Exit")
        toolbar.addAction(exit_action)

        save_action = QAction(
            QIcon(os.path.join(self.this_dir, "..", "data", "filesave.png")),
            "Save",
            self.main,
        )
        save_action.setShortcut("Ctrl+S")
        save_action.setStatusTip("Save gcode")
        save_action.triggered.connect(self.toolbar_save_gcode)  # type: ignore
        toolbar = self.main.addToolBar("Save")
        toolbar.addAction(save_action)

        ssave_action = QAction(
            QIcon(os.path.join(self.this_dir, "..", "data", "save-setup.png")),
            "Save-Setup",
            self.main,
        )
        ssave_action.setShortcut("Ctrl+W")
        ssave_action.setStatusTip("Save-Setup")
        ssave_action.triggered.connect(self.toolbar_save_setup)  # type: ignore
        toolbar = self.main.addToolBar("Save-Setup")
        toolbar.addAction(ssave_action)

        view_action = QAction(
            QIcon(os.path.join(self.this_dir, "..", "data", "view-fullscreen.png")),
            "Center-View",
            self.main,
        )
        view_action.setShortcut("Ctrl+0")
        view_action.setStatusTip("center view")
        view_action.triggered.connect(self.toolbar_centerview)  # type: ignore
        toolbar = self.main.addToolBar("center view")
        toolbar.addAction(view_action)

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
        ltabwidget.addTab(self.project["textwidget"], "G-Code")

        left_gridlayout.addWidget(ltabwidget)

        tabwidget = QTabWidget()
        tabwidget.addTab(self.project["glwidget"], "3D-View")
        # tabwidget.addTab(self.project["textwidget"], "G-Code")

        right_gridlayout = QGridLayout()
        right_gridlayout.addWidget(tabwidget)

        left_widget = QWidget()
        left_widget.setContentsMargins(0, 0, 0, 0)

        vbox = QVBoxLayout(left_widget)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(QLabel("Global-Settings:"))

        tabwidget = QTabWidget()
        for sname in self.project["setup_defaults"]:
            vcontainer = QWidget()
            vlayout = QVBoxLayout(vcontainer)
            tabwidget.addTab(vcontainer, sname)

            for ename, entry in self.project["setup_defaults"][sname].items():
                container = QWidget()
                hlayout = QHBoxLayout(container)
                label = QLabel(entry.get("title", ename))
                hlayout.addWidget(label)
                if entry["type"] == "bool":
                    checkbox = QCheckBox(entry.get("title", ename))
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

        vbox.addWidget(tabwidget)

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
            print("saving gcode to file:", self.args.output)
            open(self.args.output, "w").write("\n".join(self.project["gcode"]))
        else:
            self.main.resize(1800, 1600)
            self.main.show()
            sys.exit(qapp.exec_())


if __name__ == "__main__":
    ViaConstructor()
