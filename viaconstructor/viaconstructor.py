"""viaconstructor tool."""

import argparse
import gettext
import importlib
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
from copy import deepcopy
from functools import partial
from pathlib import Path
from textwrap import wrap
from typing import Optional, Union

import ezdxf
import setproctitle
from PyQt5.QtCore import QMimeData, Qt  # pylint: disable=E0611
from PyQt5.QtGui import (  # pylint: disable=E0611
    QDrag,
    QFont,
    QIcon,
    QImage,
    QPalette,
    QPixmap,
)
from PyQt5.QtWidgets import (  # pylint: disable=E0611
    QAction,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
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
    external_command,
    find_tool_offsets,
    get_tmp_prefix,
    mirror_objects,
    move_object,
    move_objects,
    object2points,
    objects2minmax,
    objects2polyline_offsets,
    points_to_boundingbox,
    points_to_center,
    rotate_object,
    rotate_objects,
    scale_object,
    scale_objects,
    segments2objects,
)
from .draw2d import CanvasWidget
from .draw2d import draw_all as draw_all_2d
from .dxfcolors import dxfcolors
from .gldraw import GLWidget
from .gldraw import draw_all as draw_all_gl
from .machine_cmd import polylines2machine_cmd
from .output_plugins.gcode_grbl import PostProcessorGcodeGrbl
from .output_plugins.gcode_linuxcnc import PostProcessorGcodeLinuxCNC
from .output_plugins.hpgl import PostProcessorHpgl
from .preview_plugins.gcode import GcodeParser
from .setupdefaults import setup_defaults
from .tools.box import BoxTool
from .tools.font import FontTool
from .tools.gear import GearTool

try:
    from .ext.nest2D.nest2D import (  # pylint: disable=E0611
        Box,
        Item,
        Point,
        SVGWriter,
        nest,
    )

    HAVE_NEST = True
except Exception:  # pylint: disable=W0703
    HAVE_NEST = False

reader_plugins: dict = {}
for reader in ("dxfread", "hpglread", "ngcread", "cdrread", "stlread", "svgread", "ttfread", "imgread"):
    try:
        drawing_reader = importlib.import_module(f".{reader}", "viaconstructor.input_plugins")
        reader_plugins[reader] = drawing_reader.DrawReader
    except Exception as reader_error:  # pylint: disable=W0703
        sys.stderr.write(f"ERROR while loading input plugin {reader}: {reader_error}\n")


TIMESTAMP = 0

TEMP_PREFIX = get_tmp_prefix()
openscad = external_command("openscad")
camotics = external_command("camotics")


def eprint(message, *args, **kwargs):  # pylint: disable=W0613
    sys.stderr.write(f"{message}\n")


# i18n
def no_translation(text):
    return text


_ = no_translation
lang = os.environ.get("LANGUAGE")
if not lang:
    lang = os.environ.get("LANG")
    if lang:
        lang = lang.split("_")[0]
if lang and lang != "en":
    localedir = os.path.join(Path(__file__).resolve().parent, "locales")
    try:
        lang_translations = gettext.translation("base", localedir=localedir, languages=[lang])

        lang_translations.install()
        _ = lang_translations.gettext
    except FileNotFoundError:
        sys.stderr.write(f"WARNING: localedir not found for lang '{lang}' in {localedir}\n")


class myQMainWindow(QMainWindow):
    def __init__(self, app):
        super(QMainWindow, self).__init__()
        self.app = app
        self.setAcceptDrops(True)

    def dragLeaveEvent(self, event):
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(self.app.project["machine_cmd"])
            drag.setMimeData(mime)
            drag.exec_()

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        files = []
        for url in event.mimeData().urls():
            files.append(url.toLocalFile())
        if files:
            self.app.load_drawings_and_redraw(files)
            event.acceptProposedAction()


class ViaConstructor:  # pylint: disable=R0904
    """viaconstructor main class."""

    LAYER_REGEX = re.compile(r"([a-zA-Z]{1,4}):\s*([+-]?([0-9]+([.][0-9]*)?|[.][0-9]+))")

    project: dict = {
        "engine": "3D",
        "setup_defaults": setup_defaults(_),
        "filename_draw": "",
        "filename_drawings": [],
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
        "outputMinMax": [],
        "table": [],
        "glwidget": None,
        "imgwidget": None,
        "preview_generate": None,
        "preview_open": None,
        "status": "INIT",
        "tabs": {
            "data": [],
            "table": None,
        },
        "textwidget": None,
        "reportwidget": None,
        "simulation": False,
        "simulation_pos": 0,
        "simulation_last": (0.0, 0.0, 0.0),
        "simulation_data": [],
        "simulation_cnt": 0,
        "draw_reader": None,
        "origin": [0.0, 0.0],
        "layers": {},
        "layercolors": {},
        "object_active": "",
        "layersetup": {},
        "layer_active": "0",
        "report": "",
        "project_file": None,
    }
    args = None
    info = ""
    save_tabs = "no"
    save_starts = "no"
    combobjwidget = None
    status_bar: Optional[QStatusBar] = None
    infotext_widget: Optional[QPlainTextEdit] = None
    main: Optional[myQMainWindow] = None
    toolbar: Optional[QToolBar] = None
    menubar: Optional[QMenuBar] = None
    toolbuttons: dict = {}

    module_root = Path(__file__).resolve().parent

    def debug(self, message):
        global TIMESTAMP  # pylint: disable=W0603
        if self.args and self.args.debug:
            now = time.time()
            if TIMESTAMP == 0:
                TIMESTAMP = now
            eprint(round(now - TIMESTAMP, 1))
            eprint(f"{message} ", end="", flush=True)
            TIMESTAMP = now

    def save_objects_as_dxf(self, output_file) -> bool:
        try:
            doc = ezdxf.new("R2010")
            msp = doc.modelspace()
            doc.units = ezdxf.units.MM
            for obj in self.project["objects"].values():
                for segment in obj["segments"]:
                    if segment["bulge"] == 0.0:
                        msp.add_line(
                            segment.start,
                            segment.end,
                            dxfattribs={"layer": segment.layer, "color": segment.color},
                        )
                    else:
                        (
                            center,
                            start_angle,  # pylint: disable=W0612
                            end_angle,  # pylint: disable=W0612
                            radius,  # pylint: disable=W0612
                        ) = ezdxf.math.bulge_to_arc(segment.start, segment.end, segment.bulge)
                        msp.add_arc(
                            center=center,
                            radius=radius,
                            start_angle=start_angle * 180 / math.pi,
                            end_angle=end_angle * 180 / math.pi,
                            dxfattribs={"layer": segment.layer, "color": segment.color},
                        )
            for vport in doc.viewports.get_config("*Active"):  # type: ignore
                vport.dxf.grid_on = True
            if hasattr(ezdxf, "zoom"):
                ezdxf.zoom.extents(msp)  # type: ignore
            doc.saveas(output_file)
        except Exception as error:  # pylint: disable=W0703
            eprint(f"ERROR while saving dxf: {error}")
            return False

        return True

    def run_calculation(self) -> None:
        """run all calculations."""
        if not self.project["draw_reader"]:
            return

        self.debug("run_calculation: centercalc")

        psetup: dict = self.project["setup"]
        min_max = objects2minmax(self.project["objects"])
        self.project["minMax"] = min_max
        if psetup["workpiece"]["zero"] == "original":
            if min_max[0] != self.project["origin"][0] or min_max[1] != self.project["origin"][1]:
                move_objects(self.project["objects"], -min_max[0], -min_max[1])
                move_objects(
                    self.project["objects"],
                    self.project["origin"][0],
                    self.project["origin"][1],
                )
        elif psetup["workpiece"]["zero"] == "bottomLeft":
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

        self.debug("run_calculation: offsets")

        # create toolpath from objects
        self.project["offsets"] = objects2polyline_offsets(
            psetup,
            self.project["objects"],
            self.project["maxOuter"],
        )

        # create machine commands
        self.debug("run_calculation: machine_commands")
        output_plugin: Union[PostProcessorHpgl, PostProcessorGcodeLinuxCNC, PostProcessorGcodeGrbl]
        if self.project["setup"]["machine"]["plugin"] == "gcode_linuxcnc":
            output_plugin = PostProcessorGcodeLinuxCNC(
                self.project,
            )
            self.project["suffix"] = output_plugin.suffix()
            self.project["axis"] = output_plugin.axis()
        elif self.project["setup"]["machine"]["plugin"] == "gcode_grbl":
            output_plugin = PostProcessorGcodeGrbl(
                self.project,
            )
            self.project["suffix"] = output_plugin.suffix()
            self.project["axis"] = output_plugin.axis()
        elif self.project["setup"]["machine"]["plugin"] == "hpgl":
            output_plugin = PostProcessorHpgl(
                self.project,
            )
            self.project["suffix"] = output_plugin.suffix()
            self.project["axis"] = output_plugin.axis()
        else:
            eprint(f"ERROR: Unknown machine output plugin: {self.project['setup']['machine']['plugin']}")
            sys.exit(1)
        self.project["machine_cmd"] = polylines2machine_cmd(self.project, output_plugin)
        self.debug("run_calculation: update textwidget")
        if self.project["textwidget"]:
            self.project["textwidget"].clear()
            self.project["textwidget"].insertPlainText(self.project["machine_cmd"])
            self.project["textwidget"].verticalScrollBar().setValue(0)

        self.debug("run_calculation: done")

    def _toolbar_fonttool(self) -> None:
        self.font_tool.show()

    def _toolbar_geartool(self) -> None:
        self.gear_tool.show()

    def _toolbar_boxtool(self) -> None:
        self.box_tool.show()

    def _toolbar_flipx(self) -> None:
        mirror_objects(self.project["objects"], self.project["minMax"], vertical=True)
        self.project["minMax"] = objects2minmax(self.project["objects"])
        self.update_tabs_data()
        self.update_drawing()

    def _toolbar_flipy(self) -> None:
        mirror_objects(self.project["objects"], self.project["minMax"], horizontal=True)
        self.project["minMax"] = objects2minmax(self.project["objects"])
        self.update_tabs_data()
        self.update_drawing()

    def _toolbar_rotate(self) -> None:
        rotate_objects(self.project["objects"], self.project["minMax"])
        self.project["minMax"] = objects2minmax(self.project["objects"])
        self.update_tabs_data()
        self.update_drawing()

    def _toolbar_nest(self) -> None:
        int_scale = 100000

        diameter = None
        for entry in self.project["setup"]["tool"]["tooltable"]:
            if self.project["setup"]["tool"]["number"] == entry["number"]:
                diameter = entry["diameter"]
        if diameter is None:
            print("ERROR: nest: TOOL not found")
            return

        obj_dist = max(diameter * 3, 1.0)
        items = []
        mapping = {}
        for obj_idx, obj_data in self.project["objects"].items():
            if not obj_data.outer_objects and obj_data.closed:
                itemdata = []
                for segment in obj_data.segments:
                    itemdata.append(
                        Point(
                            int(segment.start[0]) * int_scale,
                            int(segment.start[1]) * int_scale,
                        )
                    )

                segment = obj_data.segments[0]
                itemdata.append(
                    Point(
                        int(segment.start[0]) * int_scale,
                        int(segment.start[1]) * int_scale,
                    )
                )
                itemdata.reverse()
                item = Item(itemdata)
                mapping[obj_idx] = item
                # print("########## add", item, item.area)
                items.append(item)

        min_max = objects2minmax(self.project["objects"])
        box_width = (min_max[2] - min_max[0]) * 1.5
        box_height = (min_max[3] - min_max[1]) * 1.5
        box = Box(int(box_width) * int_scale, int(box_height) * int_scale)
        pgrp = nest(items, box, int(obj_dist * int_scale))

        svg_writer = SVGWriter()
        # print("## pgrp ##", len(pgrp), pgrp)
        svg_writer.write_packgroup(pgrp)
        svg_writer.save()

        for igrp in pgrp:
            for item in igrp:
                # print("item:", item)
                for key, value in mapping.items():
                    if value.area == item.area:
                        obj_data = self.project["objects"][key]
                        rotation = item.rotation
                        translation = item.translation
                        rotate_object(obj_data, 0.0, 0.0, rotation)
                        move_object(
                            obj_data,
                            float(translation.x) / int_scale,
                            float(translation.y) / int_scale,
                        )
                        for inner in obj_data.inner_objects:
                            inner_obj_data = self.project["objects"][inner]
                            rotate_object(inner_obj_data, 0.0, 0.0, rotation)
                            move_object(
                                inner_obj_data,
                                float(translation.x) / int_scale,
                                float(translation.y) / int_scale,
                            )

        self.project["minMax"] = objects2minmax(self.project["objects"])
        self.update_tabs_data()
        self.update_drawing()

    def _toolbar_scale(self) -> None:
        scale, dialog_ok = QInputDialog.getText(self.project["window"], _("Workpiece-Scale"), _("Scale-Factor:"), text="1.0")
        if dialog_ok and str(scale).replace(".", "").isnumeric() and float(scale) != 1.0:
            scale_objects(self.project["objects"], float(scale))
            self.project["minMax"] = objects2minmax(self.project["objects"])
            self.update_tabs_data()
            self.update_drawing()

    def _toolbar_inch_mm(self) -> None:
        scale_objects(self.project["objects"], 25.4)
        self.project["minMax"] = objects2minmax(self.project["objects"])
        self.update_tabs_data()
        self.update_drawing()

    def _toolbar_mm_inch(self) -> None:
        scale_objects(self.project["objects"], 1.0 / 25.4)
        self.project["minMax"] = objects2minmax(self.project["objects"])
        self.update_tabs_data()
        self.update_drawing()

    def _toolbar_view_2d(self) -> None:
        """center view."""
        self.project["glwidget"].view_2d()

    def _toolbar_toggle_tab_selector(self) -> None:
        """tab selector."""
        title = _("Tab-Selector")
        if self.project["glwidget"].toggle_tab_selector():
            for toolbutton in self.toolbuttons.values():
                if toolbutton[6]:
                    toolbutton[9].setChecked(False)
            self.toolbuttons[title][9].setChecked(True)
        else:
            self.toolbuttons[title][9].setChecked(False)

    def _toolbar_simulate_stop(self) -> None:
        self.project["simulation"] = False
        self.project["simulation_pos"] = 0
        self.project["simulation_last"] = (0.0, 0.0, 0.0)

    def _toolbar_simulate_play(self) -> None:
        self.project["simulation"] = not self.project["simulation"]

    def _toolbar_redraw(self) -> None:
        self.update_drawing()

    def _toolbar_toggle_delete_selector(self) -> None:
        """delete selector."""
        title = _("Delete-Selector")
        if self.project["glwidget"].toggle_delete_selector():
            for toolbutton in self.toolbuttons.values():
                if toolbutton[6]:
                    toolbutton[9].setChecked(False)
            self.toolbuttons[title][9].setChecked(True)
        else:
            self.toolbuttons[title][9].setChecked(False)
            self.project["maxOuter"] = find_tool_offsets(self.project["objects"])
            self.combobjwidget_update()

    def _toolbar_toggle_object_selector(self) -> None:
        """delete selector."""
        title = _("Object-Selector")
        if self.project["glwidget"].toggle_object_selector():
            for toolbutton in self.toolbuttons.values():
                if toolbutton[6]:
                    toolbutton[9].setChecked(False)
            self.toolbuttons[title][9].setChecked(True)
        else:
            self.toolbuttons[title][9].setChecked(False)

    def _toolbar_toggle_start_selector(self) -> None:
        """start selector."""
        title = _("Start-Selector")
        if self.project["glwidget"].toggle_start_selector():
            for toolbutton in self.toolbuttons.values():
                if toolbutton[6]:
                    toolbutton[9].setChecked(False)
            self.toolbuttons[title][9].setChecked(True)
        else:
            self.toolbuttons[title][9].setChecked(False)

    def _toolbar_toggle_repair_selector(self) -> None:
        """start selector."""
        title = _("Repair-Selector")
        if self.project["glwidget"].toggle_repair_selector():
            for toolbutton in self.toolbuttons.values():
                if toolbutton[6]:
                    toolbutton[9].setChecked(False)
            self.toolbuttons[title][9].setChecked(True)
        else:
            self.toolbuttons[title][9].setChecked(False)

    def _toolbar_view_reset(self) -> None:
        """center view."""
        self.project["glwidget"].view_reset()
        for toolbutton in self.toolbuttons.values():
            if toolbutton[6]:
                toolbutton[9].setChecked(False)

    def machine_cmd_save(self, filename: str) -> bool:
        with open(filename, "w") as fd_machine_cmd:
            # adding thumbnail to gcode
            if self.project["setup"]["machine"]["thumbnail"] and self.project["setup"]["machine"]["plugin"].startswith("gcode") and self.project["glwidget"]:
                size, base64 = self.project["glwidget"].screenshot(scale=(220, 220))
                base64_bc = base64.decode()
                base64_len = len(base64_bc)
                self.project["machine_cmd"] += "\n"
                self.project["machine_cmd"] += f"; thumbnail begin {size[0]}x{size[1]} {base64_len}\n"
                for line in wrap(base64_bc, 78):
                    self.project["machine_cmd"] += f"; {line}\n"
                self.project["machine_cmd"] += "; thumbnail end\n"

            fd_machine_cmd.write(self.project["machine_cmd"])
            fd_machine_cmd.write("\n")
            if self.project["setup"]["machine"]["postcommand"]:
                cmd = f"{self.project['setup']['machine']['postcommand']} '{filename}'"
                eprint(f"executing postcommand: {cmd}")
                os.system(f"{cmd} &")
            return True
        return False

    def status_bar_message(self, message) -> None:
        if self.status_bar:
            self.status_bar.showMessage(message)
        else:
            eprint(f"STATUS: {message}")

    def _toolbar_save_machine_cmd(self) -> None:
        """save machine_cmd."""
        self.status_bar_message(f"{self.info} - save machine_cmd..")

        if self.project["setup"]["view"]["outputfolder"] == "use last dir" and self.project["setup"]["view"]["lastdir"]:
            dirname = self.project["setup"]["view"]["lastdir"]
            inputname = ".".join(self.project["filename_draw"].split(".")[:-1])
            basename = os.path.basename(inputname)
            target = os.path.join(dirname, basename)
            target_file = f"{target}.{self.project['suffix']}"
        else:
            target_file = f"{'.'.join(self.project['filename_draw'].split('.')[:-1])}.{self.project['suffix']}"

        file_dialog = QFileDialog(self.main)
        file_dialog.setNameFilters([f"{self.project['suffix']} (*.{self.project['suffix']})"])
        name = file_dialog.getSaveFileName(
            self.main,
            "Save File",
            target_file,
            f"{self.project['suffix']} (*.{self.project['suffix']})",
        )
        if name[0] and self.machine_cmd_save(name[0]):
            self.project["filename_machine_cmd"] = name[0]
            self.project["setup"]["view"]["lastdir"] = os.path.dirname(name[0])
            self.project["status"] = "CHANGE"
            self.update_global_setup()
            self.project["status"] = "READY"
            self.status_bar_message(f"{self.info} - save machine-code..done ({name[0]})")
        else:
            self.status_bar_message(f"{self.info} - save machine-code..cancel")

    def _toolbar_save_dxf(self) -> None:
        """save drawing as dxf."""
        self.status_bar_message(f"{self.info} - save drawing as dxf..")

        if self.project["setup"]["view"]["outputfolder"] == "use last dir" and self.project["setup"]["view"]["lastdir"]:
            dirname = self.project["setup"]["view"]["lastdir"]
            inputname = ".".join(self.project["filename_draw"].split(".")[:-1])
            basename = os.path.basename(inputname)
            target = os.path.join(dirname, basename)
            target_file = f"{target}.dxf"
        else:
            target_file = f"{'.'.join(self.project['filename_draw'].split('.')[:-1])}.dxf"

        file_dialog = QFileDialog(self.main)
        file_dialog.setNameFilters(["dxf (*.dxf)"])
        name = file_dialog.getSaveFileName(
            self.main,
            "Save File",
            target_file,
            "dxf (*.dxf)",
        )
        if name[0] and self.save_objects_as_dxf(name[0]):
            self.status_bar_message(f"{self.info} - save dxf..done ({name[0]})")
        else:
            self.status_bar_message(f"{self.info} - save dxf..cancel")

    def _toolbar_save_gl(self) -> None:
        """save glview as png."""
        self.status_bar_message(f"{self.info} - save 3d-view as image..")
        file_dialog = QFileDialog(self.main)
        file_dialog.setNameFilters(["png (*.png)", "jpg (*.jpg)"])
        filename_default = f"{'.'.join(self.project['filename_draw'].split('.')[:-1])}.png"
        name = file_dialog.getSaveFileName(
            self.main,
            "Save as Image",
            filename_default,
            "png (*.png);;jpg (*.jpg);;bmp (*.bmp)",
        )
        if name[0] and self.project["glwidget"].screenshot(name[0]):
            self.status_bar_message(f"{self.info} - save 3d-view..done ({name[0]})")
        else:
            self.status_bar_message(f"{self.info} - save 3d-view..cancel")

    def _toolbar_save_project(self) -> None:
        """save project."""
        self.status_bar_message(f"{self.info} - save project..")
        file_dialog = QFileDialog(self.main)
        file_dialog.setNameFilters(["vcp (*.vcp)"])
        filename_default = f"{'.'.join(self.project['filename_draw'].split('.')[:-1])}.vcp"
        if self.project["project_file"]:
            filename_default = self.project["project_file"]
        name = file_dialog.getSaveFileName(
            self.main,
            "Save File",
            filename_default,
            "vcp (*.vcp)",
        )
        if name[0]:
            self.save_project(name[0])
        self.status_bar_message(f"{self.info} - save vcp..done ({name[0]})")

    def _toolbar_load_project(self) -> None:
        """load project."""
        self.status_bar_message(f"{self.info} - load project..")
        file_dialog = QFileDialog(self.main)
        filename_default = f"{'.'.join(self.project['filename_draw'].split('.')[:-1])}.vcp"
        if self.project["project_file"]:
            filename_default = self.project["project_file"]
        suffix_list = ["*.vcp"]
        name = file_dialog.getOpenFileName(
            self.main,
            "Load Project",
            filename_default,
            f"project ( {' '.join(suffix_list)} )" "Load Project",
            "",
        )
        if name[0] and self.load_project(name[0]):
            self.update_layer_setup()
            self.update_object_setup()
            self.global_changed(0)
            self.update_drawing()

            self.create_menubar()
            self.create_toolbar()

            self.status_bar_message(f"{self.info} - load project..done ({name[0]})")
        else:
            self.status_bar_message(f"{self.info} - load project..cancel")

    def _toolbar_load_drawing(self) -> None:
        """load drawing."""
        self.status_bar_message(f"{self.info} - load drawing..")
        file_dialog = QFileDialog(self.main)

        suffix_list = []
        for reader_plugin in reader_plugins.values():
            for suffix in reader_plugin.suffix(self.args):
                suffix_list.append(f"*.{suffix}")
        names = file_dialog.getOpenFileNames(
            self.main,
            "Load Drawing",
            "",
            f"drawing ( {' '.join(suffix_list)} )" "Load Drawing",
            "",
        )

        if names[0] and self.load_drawings(names[0]):
            self.update_layer_setup()
            self.update_object_setup()
            self.global_changed(0)
            self.update_drawing()

            self.create_menubar()
            self.create_toolbar()

            self.status_bar_message(f"{self.info} - load drawing..done ({names[0]})")
        else:
            self.status_bar_message(f"{self.info} - load drawing..cancel")

    def load_drawings_and_redraw(self, filenames: list) -> None:
        if filenames and self.load_drawings(filenames, append_only=True):
            self.update_layer_setup()
            self.update_object_setup()
            self.global_changed(0)
            self.update_drawing()

            self.create_menubar()
            self.create_toolbar()

            self.status_bar_message(f"{self.info} - load drawing..done")
        else:
            self.status_bar_message(f"{self.info} - load drawing..cancel")

    def _toolbar_append_drawing(self) -> None:
        """load drawing."""
        self.status_bar_message(f"{self.info} - load drawing..")
        file_dialog = QFileDialog(self.main)

        suffix_list = []
        for reader_plugin in reader_plugins.values():
            for suffix in reader_plugin.suffix(self.args):
                suffix_list.append(f"*.{suffix}")
        names = file_dialog.getOpenFileNames(
            self.main,
            "Load Drawing",
            "",
            f"drawing ( {' '.join(suffix_list)} )" "Load Drawing",
            "",
        )

        if names[0] and self.load_drawings(names[0], append_only=True):
            self.update_layer_setup()
            self.update_object_setup()
            self.global_changed(0)
            self.update_drawing()

            self.create_menubar()
            self.create_toolbar()

            self.status_bar_message(f"{self.info} - load drawing..done ({names[0]})")
        else:
            self.status_bar_message(f"{self.info} - load drawing..cancel")

    def setup_load_string(self, setup: str) -> bool:
        if setup:
            ndata = json.loads(setup)
            for sname in self.project["setup"]:
                self.project["setup"][sname].update(ndata.get(sname, {}))
            return True
        return False

    def setup_load(self, filename: str) -> bool:
        if os.path.isfile(filename):
            setup = open(filename, "r").read()
            return self.setup_load_string(setup)
        return False

    def setup_save(self, filename: str) -> bool:
        with open(filename, "w") as fd_setup:
            fd_setup.write(json.dumps(self.project["setup"], indent=4, sort_keys=True))
            return True
        return False

    def _toolbar_save_setup(self) -> None:
        """save setup."""
        self.status_bar_message(f"{self.info} - save setup..")
        if self.setup_save(self.args.setup):
            self.status_bar_message(f"{self.info} - save setup..done")
        else:
            self.status_bar_message(f"{self.info} - save setup..error")

    def _toolbar_load_setup_from(self) -> None:
        """load setup from."""
        self.status_bar_message(f"{self.info} - load setup from..")
        file_dialog = QFileDialog(self.main)
        file_dialog.setNameFilters(["setup (*.json)"])
        name = file_dialog.getOpenFileName(self.main, "Load Setup", self.args.setup, "setup (*.json)")
        if name[0] and self.setup_load(name[0]):
            self.project["status"] = "CHANGE"
            self.update_global_setup()
            self.update_layer_setup()
            self.update_object_setup()
            self.global_changed(0)
            self.update_drawing()
            self.project["status"] = "READY"
            self.status_bar_message(f"{self.info} - load setup from..done ({name[0]})")
        else:
            self.status_bar_message(f"{self.info} - load setup from..cancel")

    def _toolbar_save_setup_as(self) -> None:
        """save setup as."""
        self.status_bar_message(f"{self.info} - save setup as..")
        file_dialog = QFileDialog(self.main)
        file_dialog.setNameFilters(["setup (*.json)"])
        name = file_dialog.getSaveFileName(self.main, "Save Setup", self.args.setup, "setup (*.json)")
        if name[0] and self.setup_save(name[0]):
            self.status_bar_message(f"{self.info} - save setup as..done ({name[0]})")
        else:
            self.status_bar_message(f"{self.info} - ave setup as..cancel")

    def _toolbar_load_setup_from_drawing(self) -> None:
        if self.project["draw_reader"].can_load_setup:  # type: ignore
            if self.setup_load_string(self.project["draw_reader"].load_setup()):  # type: ignore
                self.project["status"] = "CHANGE"
                self.update_global_setup()
                self.update_layer_setup()
                self.update_object_setup()
                self.global_changed(0)
                self.prepare_segments()
                self.update_drawing()
                self.project["status"] = "READY"
                self.status_bar_message(f"{self.info} - load setup from drawing..done")
            else:
                self.status_bar_message(f"{self.info} - load setup from drawing..failed")

    def _toolbar_save_setup_to_drawing(self) -> None:
        if self.project["draw_reader"].can_save_setup:  # type: ignore
            self.project["draw_reader"].save_setup(json.dumps(self.project["setup"], indent=4, sort_keys=True))  # type: ignore
            self.status_bar_message(f"{self.info} - save setup to drawing..done")

    def update_drawing(self, draw_only=False) -> None:
        """update drawings."""
        if not self.project["draw_reader"]:
            return

        self.debug("update_drawing: start")
        self.status_bar_message(f"{self.info} - calculate..")
        if not draw_only:
            self.debug("update_drawing: run_calculation")
            self.run_calculation()
            self.debug("update_drawing: run_calculation done")

        if self.project["engine"] == "2D":
            draw_all_2d(self.project)
        else:
            draw_all_gl(self.project)

        self.info = f"{round(self.project['minMax'][2] - self.project['minMax'][0], 2)}x{round(self.project['minMax'][3] - self.project['minMax'][1], 2)}mm"

        infotext = f"Drawing: {self.info}\n"
        if self.project["outputMinMax"]:
            infotext += "\nMachine-Limits:\n"
            infotext += f" X: {round(self.project['outputMinMax'][0])} mm -> {round(self.project['outputMinMax'][3])} mm\n"
            infotext += f" Y: {round(self.project['outputMinMax'][1])} mm -> {round(self.project['outputMinMax'][4])} mm\n"
            infotext += f" Z: {round(self.project['outputMinMax'][2])} mm -> {round(self.project['outputMinMax'][5])} mm\n"

        if self.infotext_widget is not None:
            object_info = self.object_info(self.project["object_active"])
            if object_info:
                infotext += "\nActive Object:\n"
                infotext += object_info
            self.infotext_widget.setPlainText(infotext)

        if self.main:
            self.main.setWindowTitle("viaConstructor")
        self.status_bar_message(f"{self.info} - calculate..done")

        if self.project["reportwidget"]:
            self.project["reportwidget"].clear()
            self.project["reportwidget"].insertPlainText(self.project["report"])
            self.project["reportwidget"].verticalScrollBar().setValue(0)

        self.debug("update_drawing: done")

    def save_project(self, filename: str) -> bool:
        object_diffs: dict = {}
        obj_starts = {}
        for idx, obj in self.project["objects"].items():
            uid = idx.split(":")[1]
            obj_start = obj.get("start")
            if obj_start:
                obj_starts[uid] = obj_start
            for section, section_data in obj.setup.items():
                section_diff = {}
                for key, value in section_data.items():
                    if value != self.project["setup"][section][key]:
                        section_diff[key] = value
                if section_diff:
                    if uid not in object_diffs:
                        object_diffs[uid] = {}
                    object_diffs[uid][section] = section_diff

        filename_draw = self.project["filename_draw"]
        filename_drawings = self.project["filename_drawings"]
        if filename_draw:
            filename_draw = str(Path(filename_draw).resolve())
        project_data = {
            "filename_draw": filename_draw,
            "filename_drawings": filename_drawings,
            "general": self.project["setup"],
            "tabs": self.project["tabs"],
            "starts": obj_starts,
            "objects": object_diffs,
        }
        project_json = json.dumps(project_data, indent=4, sort_keys=True)
        open(filename, "w").write(project_json)
        self.project["project_file"] = filename
        return True

    def load_project(self, project_file: str) -> bool:
        project_json = open(project_file, "r").read()
        project_data = json.loads(project_json)
        for sname in self.project["setup"]:
            self.project["setup"][sname].update(project_data.get("general", {}).get(sname, {}))
        self.project["project_file"] = project_file

        filenames = project_data.get("filename_drawings", [project_data.get("filename_draw", "")])
        self.load_drawings(filenames)

        if "tabs" in project_data:
            self.project["tabs"] = project_data["tabs"]

        for idx, obj in self.project["objects"].items():
            uid = idx.split(":")[1]
            obj["setup"] = deepcopy(self.project["setup"])
            if uid in project_data["objects"]:
                for section, section_data in project_data["objects"][uid].items():
                    for key, value in section_data.items():
                        obj["setup"][section][key] = value

            ## TODO: layer-setup

            if "starts" in project_data and uid in project_data["starts"]:
                obj["start"] = project_data["starts"][uid]

        if self.project["status"] != "INIT":
            self.project["status"] = "CHANGE"
            self.update_global_setup()
            self.update_layer_setup()
            self.update_object_setup()
            self.global_changed(0)
            self.update_drawing()
            self.project["status"] = "READY"
        return True

    def calculate_cutting_data(self) -> None:
        """calculates the milling feedrate and spindle speed for the selected material
        see: https://www.precifast.de/schnittgeschwindigkeit-beim-fraesen-berechnen/
        """
        machine_feedrate = self.project["setup"]["machine"]["feedrate"]
        machine_toolspeed = self.project["setup"]["machine"]["tool_speed"]
        material_idx = self.project["setup"]["workpiece"].get("number")

        diameter = None
        blades = 0
        for entry in self.project["setup"]["tool"]["tooltable"]:
            if self.project["setup"]["tool"]["number"] == entry["number"]:
                diameter = entry["diameter"]
                blades = entry["blades"]
        if diameter is None:
            print("ERROR: nest: TOOL not found")
            return

        unit = self.project["setup"]["machine"]["unit"]
        if unit == "inch":
            diameter *= 25.4

        self.project["status"] = "CHANGE"

        if material_idx is None:
            print("Material (workpiece) not set")
        elif diameter > 0.0:
            tool_vc = self.project["setup"]["workpiece"]["materialtable"][material_idx]["vc"]
            tool_speed = tool_vc * 1000 / (diameter * math.pi)
            tool_speed = int(min(tool_speed, machine_toolspeed))
            if diameter <= 4.0:
                fz_key = "fz4"
            elif diameter <= 8.0:
                fz_key = "fz8"
            else:
                fz_key = "fz12"
            material_fz = self.project["setup"]["workpiece"]["materialtable"][material_idx][fz_key]
            feedrate = tool_speed * blades * material_fz
            feedrate = int(min(feedrate, machine_feedrate))

            info_test = []
            info_test.append("Some Milling and Tool Values will be changed:")
            info_test.append("")
            info_test.append(f" Feedrate: {feedrate} {'(!MACHINE-LIMIT)' if feedrate == machine_feedrate else ''}")
            info_test.append(f" Spindle Speed: {tool_speed} {'(!MACHINE-LIMIT)' if tool_speed == machine_toolspeed else ''}")
            info_test.append("")
            ret = QMessageBox.question(
                self.main,  # type: ignore
                "Warning",
                "\n".join(info_test),
                QMessageBox.Ok | QMessageBox.Cancel,  # type: ignore
            )
            if ret != QMessageBox.Ok:  # type: ignore
                return

            for obj in self.project["objects"].values():
                if obj.setup["tool"]["rate_h"] == self.project["setup"]["tool"]["rate_h"]:
                    obj.setup["tool"]["rate_h"] = int(feedrate)
                if obj.setup["tool"]["speed"] == self.project["setup"]["tool"]["speed"]:
                    obj.setup["tool"]["speed"] = int(tool_speed)
            self.project["setup"]["tool"]["rate_h"] = int(feedrate)
            self.project["setup"]["tool"]["speed"] = int(tool_speed)

        self.update_global_setup()
        self.update_layer_setup()
        self.update_object_setup()
        self.global_changed(0)
        self.update_drawing()
        self.project["status"] = "READY"

    def materials_select(self, material_idx) -> None:
        self.project["setup"]["workpiece"]["number"] = material_idx
        self.calculate_cutting_data()

    def tools_select(self, tool_idx) -> None:
        self.project["status"] = "CHANGE"
        old_tool_number = self.project["setup"]["tool"]["number"]
        new_tool_number = int(self.project["setup"]["tool"]["tooltable"][tool_idx]["number"])
        self.project["setup"]["tool"]["number"] = new_tool_number
        for obj in self.project["objects"].values():
            if obj.setup["tool"]["number"] == old_tool_number:
                obj.setup["tool"]["number"] = new_tool_number
        self.calculate_cutting_data()

    def table_select(self, section, name, row_idx) -> None:
        if section == "tool" and name == "tooltable":
            self.tools_select(row_idx)
        elif section == "workpiece" and name == "materialtable":
            self.materials_select(row_idx)

    def color_select(self, section, name) -> None:
        color = QColorDialog.getColor().getRgbF()
        self.project["setup"][section][name] = color
        button = self.project["setup_defaults"][section][name]["widget"]
        rgb = f"{color[0] * 255:1.0f},{color[1] * 255:1.0f},{color[2] * 255:1.0f}"
        button.setStyleSheet(f"background-color:rgb({rgb})")
        button.setText(rgb)
        self.global_changed(0)

    def update_starts(self) -> None:
        """update starts."""
        if self.save_starts == "ask":
            self.project["glwidget"].mouseReleaseEvent("")
            info_test = []
            info_test.append("Should i save starts in the DXF-File ?")
            info_test.append("")
            info_test.append(" this will create a new layer named _STARTS")
            info_test.append(" exsiting layers named")
            info_test.append(" _STARTS*")
            info_test.append(" will be removed !")
            info_test.append("")
            ret = QMessageBox.question(
                self.main,  # type: ignore
                "Warning",
                "\n".join(info_test),
                QMessageBox.Yes | QMessageBox.No,  # type: ignore
            )
            if ret == QMessageBox.Yes:  # type: ignore
                self.save_starts = "yes"
            else:
                self.save_starts = "no"
        # if self.save_starts == "yes":
        #    self.project["draw_reader"].save_starts(self.project["objects"])

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
                self.main,  # type: ignore
                "Warning",
                "\n".join(info_test),
                QMessageBox.Yes | QMessageBox.No,  # type: ignore
            )
            if ret == QMessageBox.Yes:  # type: ignore
                self.save_tabs = "yes"
            else:
                self.save_tabs = "no"
        if self.save_tabs == "yes" and self.project["draw_reader"]:
            self.project["draw_reader"].save_tabs(self.project["tabs"]["data"])

    def layer_changed(self, value=0) -> None:  # pylint: disable=W0613
        """layer setup changed."""

        if self.project["status"] in {"CHANGE", "INIT"}:
            return

        titles = {
            "mill": "Mill",
            "tool": "Tool",
            "pockets": "Pockets",
            "tabs": "Tabs",
            "leads": "Leads",
        }

        layer_active = self.project["layer_active"]
        setup_data = self.project["setup"]
        if layer_active in self.project["layersetup"]:
            old_setup = deepcopy(self.project["layersetup"][layer_active])
            setup_data = self.project["layersetup"][layer_active]

        tab_idx = 0
        for sname in self.project["setup_defaults"]:
            show_section = False
            changed_section = False
            for entry in self.project["setup_defaults"][sname].values():
                if entry.get("per_object", False):
                    show_section = True
            if not show_section:
                continue
            for ename, entry in self.project["setup_defaults"][sname].items():
                if not entry.get("per_object", False):
                    continue
                if entry["type"] == "bool":
                    setup_data[sname][ename] = entry["widget_lay"].isChecked()
                elif entry["type"] == "select":
                    setup_data[sname][ename] = entry["widget_lay"].currentText()
                elif entry["type"] == "float":
                    setup_data[sname][ename] = entry["widget_lay"].value()
                elif entry["type"] == "int":
                    setup_data[sname][ename] = entry["widget_lay"].value()
                elif entry["type"] == "str":
                    setup_data[sname][ename] = entry["widget_lay"].text()
                elif entry["type"] == "mstr":
                    setup_data[sname][ename] = entry["widget_lay"].toPlainText()
                elif entry["type"] == "table":
                    for row_idx in range(entry["widget_lay"].rowCount()):
                        col_idx = 0
                        for key, col_type in entry["columns"].items():
                            if entry["widget_lay"].item(row_idx, col_idx + 1) is None:
                                print("TABLE_ERROR")
                                col_idx += 1
                                continue
                            if col_type["type"] == "str":
                                value = entry["widget_lay"].item(row_idx, col_idx + 1).text()
                                setup_data[sname][ename][row_idx][key] = str(value)
                            elif col_type["type"] == "mstr":
                                value = entry["widget_lay"].item(row_idx, col_idx + 1).toPlainText()
                                setup_data[sname][ename][row_idx][key] = str(value)
                            elif col_type["type"] == "int":
                                value = entry["widget_lay"].item(row_idx, col_idx + 1).text()
                                setup_data[sname][ename][row_idx][key] = int(value)
                            elif col_type["type"] == "float":
                                value = entry["widget_lay"].item(row_idx, col_idx + 1).text()
                                setup_data[sname][ename][row_idx][key] = float(value)
                            col_idx += 1
                elif entry["type"] == "color":
                    pass
                else:
                    eprint(f"Unknown setup-type: {entry['type']}")
                if setup_data[sname][ename] != self.project["setup"][sname][ename]:
                    entry["widget_lay_label"].setStyleSheet("color: black")
                    changed_section = True
                else:
                    entry["widget_lay_label"].setStyleSheet("color: lightgray")
            if changed_section:
                self.tabobjwidget.setTabText(tab_idx, f">{titles.get(sname, sname)}<")
            else:
                self.tabobjwidget.setTabText(tab_idx, f"{titles.get(sname, sname)}")
            tab_idx += 1

        for obj in self.project["objects"].values():
            if obj["layer"] != layer_active:
                continue
            for sect in ("mill", "tool", "pockets", "tabs", "leads"):
                for key, global_value in self.project["layersetup"][layer_active][sect].items():
                    if global_value != old_setup[sect][key] and obj["setup"][sect][key] == old_setup[sect][key]:
                        obj["setup"][sect][key] = self.project["layersetup"][layer_active][sect][key]

        if setup_data["mill"]["step"] >= 0.0:
            setup_data["mill"]["step"] = -0.05

        if not self.project["draw_reader"]:
            return

        if not self.project["setup"]["view"]["autocalc"]:
            return

        self.project["maxOuter"] = find_tool_offsets(self.project["objects"])
        self.update_drawing()

    def object_changed(self, value=0) -> None:  # pylint: disable=W0613
        """object setup changed."""

        if self.project["status"] in {"CHANGE", "INIT"}:
            return

        titles = {
            "mill": "Mill",
            "tool": "Tool",
            "pockets": "Pockets",
            "tabs": "Tabs",
            "leads": "Leads",
        }

        object_active = self.project["object_active"]
        setup_data = self.project["setup"]

        for obj_idx, obj in self.project["objects"].items():
            if obj_idx.startswith(f"{object_active}:"):
                setup_data = obj["setup"]

        tab_idx = 0
        for sname in self.project["setup_defaults"]:
            show_section = False
            changed_section = False
            for entry in self.project["setup_defaults"][sname].values():
                if entry.get("per_object", False):
                    show_section = True
            if not show_section:
                continue
            for ename, entry in self.project["setup_defaults"][sname].items():
                if not entry.get("per_object", False):
                    continue
                if entry["type"] == "bool":
                    setup_data[sname][ename] = entry["widget_obj"].isChecked()
                elif entry["type"] == "select":
                    setup_data[sname][ename] = entry["widget_obj"].currentText()
                elif entry["type"] == "float":
                    setup_data[sname][ename] = entry["widget_obj"].value()
                elif entry["type"] == "int":
                    setup_data[sname][ename] = entry["widget_obj"].value()
                elif entry["type"] == "str":
                    setup_data[sname][ename] = entry["widget_obj"].text()
                elif entry["type"] == "mstr":
                    setup_data[sname][ename] = entry["widget_obj"].toPlainText()
                elif entry["type"] == "table":
                    for row_idx in range(entry["widget_obj"].rowCount()):
                        col_idx = 0
                        for key, col_type in entry["columns"].items():
                            if entry["widget_obj"].item(row_idx, col_idx + 1) is None:
                                print("TABLE_ERROR")
                                col_idx += 1
                                continue
                            if col_type["type"] == "str":
                                value = entry["widget_obj"].item(row_idx, col_idx + 1).text()
                                setup_data[sname][ename][row_idx][key] = str(value)
                            elif col_type["type"] == "mstr":
                                value = entry["widget_obj"].item(row_idx, col_idx + 1).toPlainText()
                                setup_data[sname][ename][row_idx][key] = str(value)
                            elif col_type["type"] == "int":
                                value = entry["widget_obj"].item(row_idx, col_idx + 1).text()
                                setup_data[sname][ename][row_idx][key] = int(value)
                            elif col_type["type"] == "float":
                                value = entry["widget_obj"].item(row_idx, col_idx + 1).text()
                                setup_data[sname][ename][row_idx][key] = float(value)
                            col_idx += 1
                elif entry["type"] == "color":
                    pass
                else:
                    eprint(f"Unknown setup-type: {entry['type']}")
                if setup_data[sname][ename] != self.project["setup"][sname][ename]:
                    entry["widget_obj_label"].setStyleSheet("color: black")
                    changed_section = True
                else:
                    entry["widget_obj_label"].setStyleSheet("color: lightgray")
            if changed_section:
                self.tabobjwidget.setTabText(tab_idx, f">{titles.get(sname, sname)}<")
            else:
                self.tabobjwidget.setTabText(tab_idx, f"{titles.get(sname, sname)}")
            tab_idx += 1

        if setup_data["mill"]["step"] >= 0.0:
            setup_data["mill"]["step"] = -0.05

        if not self.project["draw_reader"]:
            return

        if not self.project["setup"]["view"]["autocalc"]:
            return

        self.project["maxOuter"] = find_tool_offsets(self.project["objects"])
        self.update_drawing()

    def global_changed(self, value=0) -> None:  # pylint: disable=W0613
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
                elif entry["type"] == "str":
                    self.project["setup"][sname][ename] = entry["widget"].text()
                elif entry["type"] == "mstr":
                    self.project["setup"][sname][ename] = entry["widget"].toPlainText()
                elif entry["type"] == "table":
                    for row_idx in range(entry["widget"].rowCount()):
                        col_idx = 0
                        for key, col_type in entry["columns"].items():
                            if entry["widget"].item(row_idx, col_idx + 1) is None:
                                print("TABLE_ERROR")
                                col_idx += 1
                                continue
                            if col_type["type"] == "str":
                                value = entry["widget"].item(row_idx, col_idx + 1).text()
                                self.project["setup"][sname][ename][row_idx][key] = str(value)
                            elif col_type["type"] == "mstr":
                                value = entry["widget"].item(row_idx, col_idx + 1).toPlainText()
                                self.project["setup"][sname][ename][row_idx][key] = str(value)
                            elif col_type["type"] == "int":
                                value = entry["widget"].item(row_idx, col_idx + 1).text()
                                self.project["setup"][sname][ename][row_idx][key] = int(value)
                            elif col_type["type"] == "float":
                                value = entry["widget"].item(row_idx, col_idx + 1).text()
                                self.project["setup"][sname][ename][row_idx][key] = float(value)
                            col_idx += 1
                elif entry["type"] == "color":
                    pass
                else:
                    eprint(f"Unknown setup-type: {entry['type']}")

        if self.project["setup"]["mill"]["step"] >= 0.0:
            self.project["setup"]["mill"]["step"] = -0.05

        if not self.project["draw_reader"]:
            return

        self.project["segments"] = deepcopy(self.project["segments_org"])
        self.project["segments"] = clean_segments(self.project["segments"])

        for layer in self.project["layersetup"]:
            for sect in ("mill", "tool", "pockets", "tabs", "leads"):
                for key, global_value in self.project["setup"][sect].items():
                    # change layer value only if the value changed and the value diffs again the last value in global
                    if global_value != old_setup[sect][key] and self.project["layersetup"][layer][sect][key] == old_setup[sect][key]:
                        self.project["layersetup"][layer][sect][key] = self.project["setup"][sect][key]

        for obj in self.project["objects"].values():
            for sect in ("mill", "tool", "pockets", "tabs", "leads"):
                for key, global_value in self.project["setup"][sect].items():
                    # change object value only if the value changed and the value diffs again the last value in global
                    if global_value != old_setup[sect][key] and obj["setup"][sect][key] == old_setup[sect][key]:
                        obj["setup"][sect][key] = self.project["setup"][sect][key]

        self.project["maxOuter"] = find_tool_offsets(self.project["objects"])
        self.update_layer_setup()
        self.update_object_setup()

        if not self.project["setup"]["view"]["autocalc"]:
            return
        self.update_drawing()

    def _toolbar_load_machine_cmd_setup(self) -> None:
        self.project["filename_machine_cmd"] = f"{'.'.join(self.project['filename_draw'].split('.')[:-1])}.{self.project['suffix']}"
        if os.path.isfile(self.project["filename_machine_cmd"]):
            self.status_bar_message(f"{self.info} - loading setup from machinecode: {self.project['filename_machine_cmd']}")
            with open(self.project["filename_machine_cmd"], "r") as fd_machine_cmd:
                gdata = fd_machine_cmd.read()
                for g_line in gdata.split("\n"):
                    if g_line.startswith("(setup={"):
                        setup_json = g_line.strip("()").split("=", 1)[1]
                        ndata = json.loads(setup_json)
                        for sname in self.project["setup"]:
                            self.project["setup"][sname].update(ndata.get(sname, {}))
                        self.update_drawing()
                        self.status_bar_message(f"{self.info} - loading setup from machinecode..done")
                        return
        self.status_bar_message(f"{self.info} - loading setup from machinecode..failed")

    def _toolbar_load_tooltable(self) -> None:
        """load tooltable."""
        self.status_bar_message(f"{self.info} - load tooltable..")
        file_dialog = QFileDialog(self.main)
        file_dialog.setNameFilters(["camotics (*.json)", "linuxcnc (*.tbl)"])
        name = file_dialog.getOpenFileName(
            self.main,
            "Load tooltable",
            "",
            "tooltables (*.json *.tbl);;linuxcnc (*.tbl);;camotics (*.json)",
        )
        if name[0]:
            try:
                tooldata = open(name[0], "r").read()
            except Exception as save_error:  # pylint: disable=W0703
                self.status_bar_message(f"{self.info} - load tooltable ..failed ({save_error})")

            ret = QMessageBox.question(
                self.main,  # type: ignore
                "Ask",
                "Replacing the tooltable ?",
                QMessageBox.Yes | QMessageBox.No,  # type: ignore
            )
            if ret == QMessageBox.Yes:  # type: ignore
                self.save_starts = "yes"
                self.project["setup"]["tool"]["tooltable"] = [
                    {
                        "blades": 1,
                        "diameter": 1.0,
                        "lenght": 1.0,
                        "name": "",
                        "number": 99,
                    }
                ]

            if name[0].endswith(".json"):
                for number, tool in json.loads(tooldata).items():
                    new_tool = {
                        "name": tool["description"] or f"Tool-{number}",
                        "number": int(number),
                        "diameter": tool["diameter"],
                        "lenght": tool["length"],
                        "blades": 2,
                    }
                    self.project["setup"]["tool"]["tooltable"].insert(-1, new_tool)
            else:
                for tool in tooldata.split("\n"):
                    if tool and tool[0] == "T":
                        new_tool = {
                            "name": "",
                            "number": 1,
                            "diameter": 1.0,
                            "lenght": 10.0,
                            "blades": 2,
                        }
                        for value in tool.split(";")[0].split():
                            if value[0] == "T":
                                if not new_tool["name"]:
                                    new_tool["name"] = f"T{value[1:]}"
                                new_tool["number"] = int(value[1:])
                            elif value[0] == "D":
                                new_tool["diameter"] = float(value[1:])
                        if ";" in tool:
                            new_tool["name"] = tool.split(";")[1]
                        self.project["setup"]["tool"]["tooltable"].insert(-1, new_tool)

            self.project["status"] = "CHANGE"
            self.update_global_setup()
            self.update_layer_setup()
            self.update_object_setup()
            self.global_changed(0)
            self.update_drawing()
            self.project["status"] = "READY"
            self.status_bar_message(f"{self.info} - load tooltable..done ({name[0]})")
        else:
            self.status_bar_message(f"{self.info} - load tooltable..cancel")

    def _toolbar_save_tooltable(self) -> None:
        """save tooltable as."""
        if self.project["setup"]["machine"]["unit"] == "inch":
            unit = "imperial"
        else:
            unit = "metric"

        self.status_bar_message(f"{self.info} - save setup as..")
        file_dialog = QFileDialog(self.main)
        file_dialog.setNameFilters(["camotics (*.json)", "linuxcnc (*.tbl)"])
        name = file_dialog.getSaveFileName(
            self.main,
            "Save tooltable",
            "tooltable.tbl",
            "tooltables (*.json *.tbl);;linuxcnc (*.tbl);;camotics (*.json)",
        )
        if name[0]:
            if name[0].endswith(".json"):
                tooltable = {}
                for tool in self.project["setup"]["tool"]["tooltable"]:
                    number = str(tool["number"])
                    if number == "99":
                        continue
                    tooltable[number] = {
                        "units": unit,
                        "shape": "cylindrical",
                        "length": tool["lenght"],
                        "diameter": tool["diameter"],
                        "description": f"{tool['name']} / blades:{tool['blades']}",
                    }
                tooldata = json.dumps(tooltable, indent=4, sort_keys=True)

            elif name[0].endswith(".tbl"):
                tooltable_tbl = []
                for tool in self.project["setup"]["tool"]["tooltable"]:
                    number = str(tool["number"])
                    if number == "99":
                        continue
                    tooltable_tbl.append(f"T{number} P{number} Z{0.0} D{tool['diameter']} ;{tool['name']} / blades:{tool['blades']}")
                tooltable_tbl.append("")
                tooldata = "\n".join(tooltable_tbl)

            try:
                open(name[0], "w").write(tooldata)
                self.status_bar_message(f"{self.info} - save tooltable as..done ({name[0]})")
            except Exception as save_error:  # pylint: disable=W0703
                self.status_bar_message(f"{self.info} - save tooltable as..failed ({save_error})")
        else:
            self.status_bar_message(f"{self.info} - save tooltable as..cancel")

    def _toolbar_exit(self) -> None:
        """exit button."""
        if os.environ.get("LINUXCNCVERSION"):
            print(self.project["machine_cmd"])
        if self.project["setup"]["view"]["autosave"]:
            if not os.environ.get("LINUXCNCVERSION"):
                print("saving setup defaults")
            self._toolbar_save_setup()
        sys.exit(0)

    def create_actions(self) -> None:
        if self.project["draw_reader"] is not None:
            can_save_setup = self.project["draw_reader"].can_save_setup
            can_load_setup = self.project["draw_reader"].can_load_setup
        else:
            can_save_setup = False
            can_load_setup = False

        self.toolbuttons = {
            _("Load drawing"): [
                "open.png",
                "Ctrl+O",
                _("Load drawing"),
                self._toolbar_load_drawing,
                not os.environ.get("LINUXCNCVERSION"),
                True,
                False,
                _("File"),
                "",
                None,
            ],
            _("Append drawing"): [
                "append.png",
                "Ctrl+A",
                _("Append drawing"),
                self._toolbar_append_drawing,
                not os.environ.get("LINUXCNCVERSION"),
                True,
                False,
                _("File"),
                "",
                None,
            ],
            _("Save drawing as DXF"): [
                "save.png",
                "Ctrl+D",
                _("Save drawing as DXF"),
                self._toolbar_save_dxf,
                not os.environ.get("LINUXCNCVERSION"),
                True,
                False,
                _("File"),
                "",
                None,
            ],
            _("Save 3d-view as PNG"): [
                "save-image.png",
                "Ctrl+P",
                _("Save 3d-view as PNG"),
                self._toolbar_save_gl,
                not os.environ.get("LINUXCNCVERSION"),
                True,
                False,
                _("File"),
                "",
                None,
            ],
            _("Exit"): [
                "exit.png",
                "Ctrl+Q",
                _("Exit application"),
                self._toolbar_exit,
                True,
                True,
                False,
                _("File"),
                "exit",
                None,
            ],
            _("Load project"): [
                "open.png",
                "",
                _("Load project"),
                self._toolbar_load_project,
                False,
                True,
                False,
                _("Project"),
                "",
                None,
            ],
            _("Save project"): [
                "save.png",
                "",
                _("Save project"),
                self._toolbar_save_project,
                False,
                True,
                False,
                _("Project"),
                "",
                None,
            ],
            _("Save Machine Output"): [
                "save-gcode.png",
                "Ctrl+S",
                _("Save machine commands in a file"),
                self._toolbar_save_machine_cmd,
                True,
                True,
                False,
                _("Machine"),
                "cmd",
                None,
            ],
            _("Save setup as default"): [
                "save-setup.png",
                "",
                _("Save-Setup"),
                self._toolbar_save_setup,
                True,
                True,
                False,
                _("Setup"),
                "default",
                None,
            ],
            _("Load setup from"): [
                "load-setup.png",
                "",
                _("Load setup from"),
                self._toolbar_load_setup_from,
                False,
                True,
                False,
                _("Setup"),
                "file",
                None,
            ],
            _("Save setup as"): [
                "save-setup-as.png",
                "",
                _("Save setup as"),
                self._toolbar_save_setup_as,
                False,
                True,
                False,
                _("Setup"),
                "file",
                None,
            ],
            _("Load setup from drawing"): [
                "load-setup.png",
                "",
                _("Load setup from drawing"),
                self._toolbar_load_setup_from_drawing,
                False,
                can_load_setup,
                False,
                _("Setup"),
                "drawing",
                None,
            ],
            _("Save setup to drawing"): [
                "save-setup-as.png",
                "",
                _("Save setup to drawing"),
                self._toolbar_save_setup_to_drawing,
                False,
                can_save_setup,
                False,
                _("Setup"),
                "drawing",
                None,
            ],
            _("load tooltable from"): [
                "load-tooltable.png",
                "",
                _("load tooltable from"),
                self._toolbar_load_tooltable,
                False,
                True,
                False,
                _("Tooltable"),
                "",
                None,
            ],
            _("save tooltable as"): [
                "save-tooltable.png",
                "",
                _("save tooltable as"),
                self._toolbar_save_tooltable,
                False,
                True,
                False,
                _("Tooltable"),
                "",
                None,
            ],
            _("Flip-X"): [
                "flip-x.png",
                "Ctrl+X",
                _("Flip-X workpiece"),
                self._toolbar_flipx,
                True,
                True,
                False,
                _("Workpiece"),
                "",
                None,
            ],
            _("Flip-Y"): [
                "flip-y.png",
                "Ctrl+Y",
                _("Flip-Y workpiece"),
                self._toolbar_flipy,
                True,
                True,
                False,
                _("Workpiece"),
                "",
                None,
            ],
            _("Rotate"): [
                "rotate.png",
                "Ctrl+R",
                _("Rotate workpiece"),
                self._toolbar_rotate,
                True,
                True,
                False,
                _("Workpiece"),
                "",
                None,
            ],
            _("Scale"): [
                "scale.png",
                "",
                _("Scale workpiece"),
                self._toolbar_scale,
                True,
                True,
                False,
                _("Workpiece"),
                "",
                None,
            ],
            _("inch->mm"): [
                "scale.png",
                "",
                _("Scale workpiece"),
                self._toolbar_inch_mm,
                False,
                True,
                False,
                _("Workpiece"),
                "",
                None,
            ],
            _("mm->inch"): [
                "scale.png",
                "",
                _("Scale workpiece"),
                self._toolbar_mm_inch,
                False,
                True,
                False,
                _("Workpiece"),
                "",
                None,
            ],
            _("View-Reset"): [
                "view-reset.png",
                "Ctrl+3",
                _("View-Reset"),
                self._toolbar_view_reset,
                True,
                True,
                False,
                _("View"),
                "",
                None,
            ],
            _("2D-View"): [
                "view-2d.png",
                "Ctrl+2",
                _("2D-View"),
                self._toolbar_view_2d,
                True,
                True,
                False,
                _("View"),
                "",
                None,
            ],
            _("Nesting"): [
                "nesting.png",
                "Ctrl+N",
                _("nesting workpiece"),
                self._toolbar_nest,
                HAVE_NEST,
                HAVE_NEST,
                False,
                _("Nesting"),
                "",
                None,
            ],
            _("Object-Selector"): [
                "select.png",
                "",
                _("Object-Selector"),
                self._toolbar_toggle_object_selector,
                True,
                True,
                True,
                _("Mouse"),
                "sel",
                None,
            ],
            _("Tab-Selector"): [
                "tab-selector.png",
                "Ctrl+T",
                _("Tab-Selector"),
                self._toolbar_toggle_tab_selector,
                True,
                True,
                True,
                _("Mouse"),
                "set",
                None,
            ],
            _("Start-Selector"): [
                "start.png",
                "Ctrl+L",
                _("Start-Selector"),
                self._toolbar_toggle_start_selector,
                True,
                True,
                True,
                _("Mouse"),
                "set",
                None,
            ],
            _("Repair-Selector"): [
                "repair.png",
                "",
                _("Repair-Selector"),
                self._toolbar_toggle_repair_selector,
                True,
                True,
                True,
                _("Mouse"),
                "edit",
                None,
            ],
            _("Delete-Selector"): [
                "delete.png",
                "",
                _("Delete-Selector"),
                self._toolbar_toggle_delete_selector,
                True,
                True,
                True,
                _("Mouse"),
                "edit",
                None,
            ],
            _("Start simulation"): [
                "play.png",
                "Space",
                _("start/pause simulation"),
                self._toolbar_simulate_play,
                True,
                True,
                False,
                _("Simulation"),
                "",
                None,
            ],
            _("Stop simulation"): [
                "stop.png",
                "",
                _("stop/reset simulation"),
                self._toolbar_simulate_stop,
                True,
                True,
                False,
                _("Simulation"),
                "",
                None,
            ],
            _("openscad preview"): [
                "openscad.png",
                "F5",
                _("view in openscad"),
                self.open_preview_in_openscad,
                openscad is not None,
                openscad is not None,
                False,
                _("Simulation"),
                "",
                None,
            ],
            _("camotics preview"): [
                "camotics.png",
                "F5",
                _("view in camotics"),
                self.open_preview_in_camotics,
                camotics is not None,
                camotics is not None,
                False,
                _("Simulation"),
                "",
                None,
            ],
            _("redraw"): [
                "redraw.png",
                "F5",
                _("update calculation and redraw"),
                self._toolbar_redraw,
                True,
                True,
                False,
                _("Calculation"),
                "",
                None,
            ],
            _("Font-Tool"): [
                "fonts.png",
                "Ctrl+F",
                _("open fonttool"),
                self._toolbar_fonttool,
                False,
                True,
                False,
                _("Utilities"),
                "exit",
                None,
            ],
            _("Gear-Tool"): [
                "gears.png",
                "Ctrl+G",
                _("open geartool"),
                self._toolbar_geartool,
                False,
                True,
                False,
                _("Utilities"),
                "exit",
                None,
            ],
            _("Box-Tool"): [
                "box.png",
                "Ctrl+G",
                _("open boxtool"),
                self._toolbar_boxtool,
                False,
                True,
                False,
                _("Utilities"),
                "exit",
                None,
            ],
        }

    def create_toolbar(self) -> None:
        """creates the_toolbar."""
        if self.toolbar is None:
            self.toolbar = QToolBar("top toolbar")
            self.main.addToolBar(self.toolbar)  # type: ignore
        self.toolbar.clear()
        self.create_actions()
        section = ""
        section_sub = ""
        for title, toolbutton in self.toolbuttons.items():
            if toolbutton[4]:
                icon = os.path.join(self.module_root, "icons", toolbutton[0])
                if toolbutton[7] != section or toolbutton[8] != section_sub:
                    section = toolbutton[7]
                    section_sub = toolbutton[8]
                    self.toolbar.addSeparator()
                action = QAction(
                    QIcon(icon),
                    title,
                    self.main,
                )
                if toolbutton[6]:
                    action.setCheckable(True)
                action.triggered.connect(toolbutton[3])  # type: ignore
                action.setStatusTip(toolbutton[2])
                self.toolbar.addAction(action)
                toolbutton[9] = action

    def create_menubar(self) -> None:
        if self.menubar is None:
            self.menubar = QMenuBar(self.main)
            self.main.setMenuBar(self.menubar)  # type: ignore
        self.menubar.clear()
        self.create_actions()
        self.menus = {}
        section = ""
        section_sub = ""
        for title, toolbutton in self.toolbuttons.items():
            if toolbutton[5]:
                icon = os.path.join(self.module_root, "icons", toolbutton[0])
                if toolbutton[7] != section:
                    section = toolbutton[7]
                    section_sub = toolbutton[8]
                    self.menus[section] = self.menubar.addMenu(section)
                elif toolbutton[8] != section_sub:
                    section_sub = toolbutton[8]
                    self.menus[section].addSeparator()
                action = QAction(
                    QIcon(icon),
                    title,
                    self.main,
                )
                action.triggered.connect(toolbutton[3])  # type: ignore
                if toolbutton[1]:
                    action.setShortcut(toolbutton[1])
                action.setStatusTip(toolbutton[2])
                self.menus[section].addAction(action)

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
                elif entry["type"] == "str":
                    entry["widget"].setText(self.project["setup"][sname][ename])
                elif entry["type"] == "mstr":
                    entry["widget"].setPlainText(self.project["setup"][sname][ename])
                elif entry["type"] == "table":
                    # add empty row if not exist
                    first_element = list(entry["columns"].keys())[0]

                    if entry.get("column_defaults") is not None and str(self.project["setup"][sname][ename][-1][first_element]) != "":
                        new_row = {}
                        for key, default in entry["column_defaults"].items():
                            new_row[key] = default
                        self.project["setup"][sname][ename].append(new_row)

                    table = entry["widget"]
                    table.setRowCount(len(self.project["setup"][sname][ename]))
                    idxf_offset = 0
                    table.setColumnCount(len(entry["columns"]))
                    if entry["selectable"]:
                        table.setColumnCount(len(entry["columns"]) + 1)
                        table.setHorizontalHeaderItem(0, QTableWidgetItem("Select"))
                        idxf_offset = 1
                    for col_idx, title in enumerate(entry["columns"]):
                        title = entry["columns"][title].get("title", title)
                        table.setHorizontalHeaderItem(col_idx + idxf_offset, QTableWidgetItem(title))
                    for row_idx, row in enumerate(self.project["setup"][sname][ename]):
                        if entry["selectable"]:
                            button = QPushButton()
                            button.setIcon(QIcon(os.path.join(self.module_root, "icons", "select.png")))
                            button.setToolTip(_("select this row"))
                            button.clicked.connect(partial(self.table_select, sname, ename, row_idx))  # type: ignore
                            table.setCellWidget(row_idx, 0, button)
                            table.resizeColumnToContents(0)
                        for col_idx, key in enumerate(entry["columns"]):
                            table.setItem(
                                row_idx,
                                col_idx + idxf_offset,
                                QTableWidgetItem(str(row.get(key, 0))),
                            )
                            table.resizeColumnToContents(col_idx + idxf_offset)

                elif entry["type"] == "color":
                    pass
                else:
                    eprint(f"Unknown setup-type: {entry['type']}")

    def create_global_setup(self, tabwidget) -> None:
        titles = {
            "mill": _("M&ill"),
            "tool": _("&Tool"),
            "pockets": _("P&ockets"),
            "tabs": _("Ta&bs"),
            "leads": _("Lea&ds"),
        }
        self.create_common(tabwidget, "widget", titles, self.global_changed)

    def create_settings_tabs(self, tabwidget) -> None:
        titles = {
            "workpiece": _("&Workpiece"),
            "machine": _("M&achine"),
            "view": _("&View"),
        }
        self.create_common(tabwidget, "widget", titles, self.global_changed)

    def object_info_text(self, object_active_obj):
        if object_active_obj:
            min_x = 999999999999
            min_y = 999999999999
            max_x = -999999999999
            max_y = -999999999999
            is_circle = True
            last_bulge = None
            last_center = None
            for segment in object_active_obj.segments:
                if last_center and segment.center != segment.center:
                    is_circle = False
                elif last_bulge and segment.bulge != last_bulge:
                    is_circle = False
                elif not segment.bulge:
                    is_circle = False
                last_bulge = segment.bulge
                last_center = segment.center
                for ptype in ("start", "end"):
                    if ptype in segment:
                        min_x = min(min_x, segment[ptype][0])
                        min_y = min(min_y, segment[ptype][1])
                        max_x = max(max_x, segment[ptype][0])
                        max_y = max(max_y, segment[ptype][1])
            diff_x = max_x - min_x
            diff_y = max_y - min_y
            center_x = min_x + diff_x / 2.0
            center_y = min_y + diff_y / 2.0
            info_text = []
            info_text.append(f" X: {min_x}")
            info_text.append(f" Y: {min_y}")
            info_text.append(f" W: {diff_x}")
            info_text.append(f" H: {diff_y}")
            info_text.append(f" CX: {center_x}")
            info_text.append(f" CY: {center_y}")
            if is_circle:
                info_text.append(" Type: Circle")
            elif not object_active_obj.closed:
                info_text.append(" Type: Line")
            else:
                info_text.append(" Type: Polygon")
            info_text.append(f" Outer: {len(object_active_obj.outer_objects)}")
            info_text.append(f" Inner: {len(object_active_obj.inner_objects)}")
            info_text.append(f" Layer: {object_active_obj.layer}")
            return "\n".join(info_text)
        return ""

    def object_info(self, object_active):
        object_active_obj = None
        for obj_idx, obj in self.project["objects"].items():
            if obj_idx.startswith(f"{object_active}:"):
                object_active_obj = obj
        info_text = ""
        if object_active_obj:
            info_text = self.object_info_text(object_active_obj)
            self.object_infolabel.setText(info_text)
        return info_text

    def setup_select_layer(self, value):
        if self.project["status"] != "READY":
            return
        self.project["status"] = "CHANGE"

        layer_active = "(".join(value.split("(")[0:-1]).strip()
        print("---layer_active", layer_active)
        self.project["layer_active"] = layer_active
        self.lcombobjwidget.setCurrentText(layer_active)
        self.project["layer_active"] = layer_active
        self.update_layer_setup()

        self.project["status"] = "READY"

    def update_layer_setup(self) -> None:
        layer_active = self.project["layer_active"]
        setup_data = self.project["setup"]

        titles = {
            "mill": _("M&ill"),
            "tool": _("&Tool"),
            "workpiece": _("&Workpiece"),
            "pockets": _("P&ockets"),
            "tabs": _("Ta&bs"),
            "leads": _("Lea&ds"),
            "machine": _("M&achine"),
            "view": _("&View"),
        }

        if layer_active in self.project["layersetup"]:
            setup_data = self.project["layersetup"][layer_active]

        tab_idx = 0
        for sname in self.project["setup_defaults"]:
            show_section = False
            changed_section = False
            for entry in self.project["setup_defaults"][sname].values():
                if entry.get("per_object", False):
                    show_section = True
            if not show_section:
                continue
            for ename, entry in self.project["setup_defaults"][sname].items():
                if not entry.get("per_object", False):
                    continue

                if setup_data[sname][ename] != self.project["setup"][sname][ename]:
                    entry["widget_lay_label"].setStyleSheet("color: black")
                    changed_section = True
                else:
                    entry["widget_lay_label"].setStyleSheet("color: lightgray")

                if entry["type"] == "bool":
                    entry["widget_lay"].setChecked(setup_data[sname][ename])
                elif entry["type"] == "select":
                    entry["widget_lay"].setCurrentText(setup_data[sname][ename])
                elif entry["type"] == "float":
                    entry["widget_lay"].setValue(setup_data[sname][ename])
                elif entry["type"] == "int":
                    entry["widget_lay"].setValue(setup_data[sname][ename])
                elif entry["type"] == "str":
                    entry["widget_lay"].setText(setup_data[sname][ename])
                elif entry["type"] == "mstr":
                    entry["widget_lay"].setPlainText(setup_data[sname][ename])
                elif entry["type"] == "table":
                    # add empty row if not exist
                    first_element = list(entry["columns"].keys())[0]

                    if entry.get("column_defaults") is not None and str(setup_data[sname][ename][-1][first_element]) != "":
                        new_row = {}
                        for key, default in entry["column_defaults"].items():
                            new_row[key] = default
                        setup_data[sname][ename].append(new_row)

                    table = entry["widget_lay"]
                    table.setRowCount(len(setup_data[sname][ename]))
                    idxf_offset = 0
                    table.setColumnCount(len(entry["columns"]))
                    if entry["selectable"]:
                        table.setColumnCount(len(entry["columns"]) + 1)
                        table.setHorizontalHeaderItem(0, QTableWidgetItem("Select"))
                        idxf_offset = 1
                    for col_idx, title in enumerate(entry["columns"]):
                        title = entry["columns"][title].get("title", title)
                        table.setHorizontalHeaderItem(col_idx + idxf_offset, QTableWidgetItem(title))
                    for row_idx, row in enumerate(setup_data[sname][ename]):
                        if entry["selectable"]:
                            button = QPushButton()
                            button.setIcon(QIcon(os.path.join(self.module_root, "icons", "select.png")))
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
                elif entry["type"] == "color":
                    pass
                else:
                    eprint(f"Unknown setup-type: {entry['type']}")

            if changed_section:
                self.tabobjwidget.setTabText(tab_idx, f">{titles.get(sname, sname)}<")
            else:
                self.tabobjwidget.setTabText(tab_idx, f"{titles.get(sname, sname)}")
            tab_idx += 1

    def create_common(self, tabwidget, widget_name, titles, change_func):
        for sname in self.project["setup_defaults"]:
            if sname in titles:
                scrollarea = QScrollArea()
                scrollarea.setWidgetResizable(True)
                vcontainer = QWidget()
                vlayout = QVBoxLayout(vcontainer)
                vlayout.setContentsMargins(0, 10, 0, 0)
                scrollarea.setWidget(vcontainer)
                tabwidget.addTab(scrollarea, titles.get(sname, sname))

                streched = False
                for ename, entry in self.project["setup_defaults"][sname].items():
                    helptext = entry.get("tooltip", f"{sname}/{ename}")
                    container = QWidget()
                    hlayout = QHBoxLayout(container)
                    hlayout.setContentsMargins(10, 0, 10, 0)
                    entry[widget_name + "_label"] = QLabel(entry.get("title", ename))
                    entry[widget_name + "_label"].setToolTip(helptext)
                    hlayout.addWidget(entry[widget_name + "_label"])
                    vlayout.addWidget(container)
                    hlayout.addStretch(1)
                    if entry["type"] == "bool":
                        checkbox = QCheckBox()
                        checkbox.setChecked(self.project["setup"][sname][ename])
                        checkbox.setToolTip(helptext)
                        checkbox.stateChanged.connect(change_func)  # type: ignore
                        hlayout.addWidget(checkbox)
                        entry[widget_name] = checkbox
                    elif entry["type"] == "select":
                        combobox = QComboBox()
                        for option in entry["options"]:
                            combobox.addItem(option[0])
                        combobox.setCurrentText(self.project["setup"][sname][ename])
                        combobox.setToolTip(helptext)
                        combobox.currentTextChanged.connect(change_func)  # type: ignore
                        hlayout.addWidget(combobox)
                        entry[widget_name] = combobox
                    elif entry["type"] == "color":
                        color = self.project["setup"][sname][ename]
                        rgb = f"{color[0] * 255:1.0f},{color[1] * 255:1.0f},{color[2] * 255:1.0f}"
                        button = QPushButton(rgb)
                        button.setStyleSheet(f"background-color:rgb({rgb})")
                        button.setToolTip(helptext)
                        button.clicked.connect(partial(self.color_select, sname, ename))  # type: ignore
                        hlayout.addWidget(button)
                        entry[widget_name] = button
                    elif entry["type"] == "float":
                        dspinbox = QDoubleSpinBox()
                        dspinbox.setDecimals(entry.get("decimals", 4))
                        dspinbox.setSingleStep(entry.get("step", 1.0))
                        dspinbox.setMinimum(entry["min"])
                        dspinbox.setMaximum(entry["max"])
                        dspinbox.setValue(self.project["setup"][sname][ename])
                        dspinbox.setToolTip(helptext)
                        dspinbox.valueChanged.connect(change_func)  # type: ignore
                        hlayout.addWidget(dspinbox)
                        entry[widget_name] = dspinbox
                    elif entry["type"] == "int":
                        spinbox = QSpinBox()
                        spinbox.setSingleStep(entry.get("step", 1))
                        spinbox.setMinimum(entry["min"])
                        spinbox.setMaximum(entry["max"])
                        spinbox.setValue(self.project["setup"][sname][ename])
                        spinbox.setToolTip(helptext)
                        spinbox.valueChanged.connect(change_func)  # type: ignore
                        hlayout.addWidget(spinbox)
                        entry[widget_name] = spinbox
                    elif entry["type"] == "str":
                        lineedit = QLineEdit()
                        lineedit.setText(self.project["setup"][sname][ename])
                        lineedit.setToolTip(helptext)
                        lineedit.textChanged.connect(change_func)  # type: ignore
                        hlayout.addWidget(lineedit)
                        entry[widget_name] = lineedit
                    elif entry["type"] == "mstr":
                        mlineedit = QPlainTextEdit()
                        mlineedit.setPlainText(self.project["setup"][sname][ename])
                        mlineedit.setToolTip(helptext)
                        mlineedit.textChanged.connect(change_func)  # type: ignore
                        mlineedit.setFixedHeight(27)
                        hlayout.addWidget(mlineedit)
                        entry[widget_name] = mlineedit
                    elif entry["type"] == "table":
                        # add empty row if not exist
                        first_element = list(entry["columns"].keys())[0]
                        if entry.get("column_defaults") is not None and str(self.project["setup"][sname][ename][-1][first_element]) != "":
                            new_row = {}
                            for key, default in entry["column_defaults"].items():
                                new_row[key] = default
                            self.project["setup"][sname][ename].append(new_row)

                        table = QTableWidget()
                        table.setToolTip(helptext)
                        table.setRowCount(len(self.project["setup"][sname][ename]))
                        idxf_offset = 0
                        table.setColumnCount(len(entry["columns"]))
                        if entry["selectable"]:
                            table.setColumnCount(len(entry["columns"]) + 1)
                            table.setHorizontalHeaderItem(0, QTableWidgetItem("Select"))
                            idxf_offset = 1
                        for col_idx, title in enumerate(entry["columns"]):
                            title = entry["columns"][title].get("title", title)
                            table.setHorizontalHeaderItem(col_idx + idxf_offset, QTableWidgetItem(title))
                        for row_idx, row in enumerate(self.project["setup"][sname][ename]):
                            if entry["selectable"]:
                                button = QPushButton()
                                button.setIcon(QIcon(os.path.join(self.module_root, "icons", "select.png")))
                                button.setToolTip(_("select this row"))
                                button.clicked.connect(partial(self.table_select, sname, ename, row_idx))  # type: ignore
                                table.setCellWidget(row_idx, 0, button)
                                table.resizeColumnToContents(0)
                            for col_idx, key in enumerate(entry["columns"]):
                                item = QTableWidgetItem(str(row[key]))
                                table.setItem(
                                    row_idx,
                                    col_idx + idxf_offset,
                                    item,
                                )
                                # if entry["columns"][key].get("ro", False):
                                #    item.setFlags(Qt.ItemIsEditable)
                                table.resizeColumnToContents(col_idx + idxf_offset)
                        table.itemChanged.connect(change_func)  # type: ignore
                        vlayout.addWidget(table, stretch=1)
                        streched = True
                        entry[widget_name] = table
                    else:
                        eprint(f"Unknown setup-type: {entry['type']}")

                    unit = entry.get("unit", "")
                    if unit == "LINEARMEASURE":
                        unit = self.project["setup"]["machine"]["unit"]

                    ulabel = QLabel(unit)
                    ulabel.setMinimumWidth(36)
                    ulabel.setFont(QFont("Arial", 9))
                    hlayout.addWidget(ulabel)
                if not streched:
                    vlayout.addStretch(1)
                
    def create_layer_setup(self, tabwidget) -> None:
        titles = {
            "mill": _("M&ill"),
            "tool": _("&Tool"),
            "pockets": _("P&ockets"),
            "tabs": _("Ta&bs"),
            "leads": _("Lea&ds"),
        }
        self.create_common(tabwidget, "widget_lay", titles, self.layer_changed)

    def setup_select_object(self, value):
        if self.project["status"] != "READY":
            return
        if not value:
            return
        self.project["status"] = "CHANGE"
        obj_idx = value.split(":")[0].split()[0]
        self.combobjwidget.setCurrentText(obj_idx)
        self.project["object_active"] = obj_idx
        self.object_info(self.project["object_active"])
        self.update_object_setup()
        self.project["status"] = "READY"

        if self.project["engine"] == "2D":
            draw_all_2d(self.project)
        else:
            draw_all_gl(self.project)

    def update_object_setup(self) -> None:
        object_active = self.project["object_active"]
        setup_data = self.project["setup"]

        titles = {
            "mill": _("M&ill"),
            "tool": _("&Tool"),
            "workpiece": _("&Workpiece"),
            "pockets": _("P&ockets"),
            "tabs": _("Ta&bs"),
            "leads": _("Lea&ds"),
            "machine": _("M&achine"),
            "view": _("&View"),
        }

        for obj_idx, obj in self.project["objects"].items():
            if obj_idx.startswith(f"{object_active}:"):
                setup_data = obj["setup"]

        tab_idx = 0
        for sname in self.project["setup_defaults"]:
            show_section = False
            changed_section = False
            for entry in self.project["setup_defaults"][sname].values():
                if entry.get("per_object", False):
                    show_section = True
            if not show_section:
                continue
            for ename, entry in self.project["setup_defaults"][sname].items():
                if not entry.get("per_object", False):
                    continue

                if setup_data[sname][ename] != self.project["setup"][sname][ename]:
                    entry["widget_obj_label"].setStyleSheet("color: black")
                    changed_section = True
                else:
                    entry["widget_obj_label"].setStyleSheet("color: lightgray")

                if entry["type"] == "bool":
                    entry["widget_obj"].setChecked(setup_data[sname][ename])
                elif entry["type"] == "select":
                    entry["widget_obj"].setCurrentText(setup_data[sname][ename])
                elif entry["type"] == "float":
                    entry["widget_obj"].setValue(setup_data[sname][ename])
                elif entry["type"] == "int":
                    entry["widget_obj"].setValue(setup_data[sname][ename])
                elif entry["type"] == "str":
                    entry["widget_obj"].setText(setup_data[sname][ename])
                elif entry["type"] == "mstr":
                    entry["widget_obj"].setPlainText(setup_data[sname][ename])
                elif entry["type"] == "table":
                    # add empty row if not exist
                    first_element = list(entry["columns"].keys())[0]

                    if entry.get("column_defaults") is not None and str(setup_data[sname][ename][-1][first_element]) != "":
                        new_row = {}
                        for key, default in entry["column_defaults"].items():
                            new_row[key] = default
                        setup_data[sname][ename].append(new_row)

                    table = entry["widget_obj"]
                    table.setRowCount(len(setup_data[sname][ename]))
                    idxf_offset = 0
                    table.setColumnCount(len(entry["columns"]))
                    if entry["selectable"]:
                        table.setColumnCount(len(entry["columns"]) + 1)
                        table.setHorizontalHeaderItem(0, QTableWidgetItem("Select"))
                        idxf_offset = 1
                    for col_idx, title in enumerate(entry["columns"]):
                        title = entry["columns"][title].get("title", title)
                        table.setHorizontalHeaderItem(col_idx + idxf_offset, QTableWidgetItem(title))
                    for row_idx, row in enumerate(setup_data[sname][ename]):
                        if entry["selectable"]:
                            button = QPushButton()
                            button.setIcon(QIcon(os.path.join(self.module_root, "icons", "select.png")))
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
                elif entry["type"] == "color":
                    pass
                else:
                    eprint(f"Unknown setup-type: {entry['type']}")

            if changed_section:
                self.tabobjwidget.setTabText(tab_idx, f">{titles.get(sname, sname)}<")
            else:
                self.tabobjwidget.setTabText(tab_idx, f"{titles.get(sname, sname)}")
            tab_idx += 1

    def create_object_setup(self, tabwidget) -> None:
        titles = {
            "mill": _("M&ill"),
            "tool": _("&Tool"),
            "pockets": _("P&ockets"),
            "tabs": _("Ta&bs"),
            "leads": _("Lea&ds"),
        }
        self.create_common(tabwidget, "widget_obj", titles, self.object_changed)

        def object_move(spinbox_steps, checkbox_childs, direction):
            object_active = self.project["object_active"]
            with_childs = checkbox_childs.isChecked()
            diff = spinbox_steps.value()
            step_x = 0.0
            step_y = 0.0
            if direction == "left":
                step_x = -diff
            elif direction == "right":
                step_x = diff
            elif direction == "up":
                step_y = diff
            elif direction == "down":
                step_y = -diff

            object_active_obj = None
            for obj_idx, obj in self.project["objects"].items():
                if obj_idx.startswith(f"{object_active}:"):
                    object_active_obj = obj

            move_object(object_active_obj, step_x, step_y)
            if with_childs:
                for inner in object_active_obj["inner_objects"]:
                    move_object(self.project["objects"][inner], step_x, step_y)

            self.update_tabs_data()
            self.update_drawing()

        scrollarea = QScrollArea()
        scrollarea.setWidgetResizable(True)
        vcontainer = QWidget()
        vlayout = QVBoxLayout(vcontainer)
        vlayout.setContentsMargins(0, 10, 0, 0)
        scrollarea.setWidget(vcontainer)

        vlayout.addWidget(QLabel("Info:"))

        self.object_infolabel = QLabel("")
        vlayout.addWidget(self.object_infolabel)

        vlayout.addWidget(QLabel(_("Move:")))

        vlayout.addWidget(QLabel(_("Steps")))

        dspinbox = QDoubleSpinBox()
        dspinbox.setDecimals(4)
        dspinbox.setSingleStep(1.0)
        dspinbox.setMinimum(0.0)
        dspinbox.setMaximum(1000.0)
        dspinbox.setValue(1.0)
        dspinbox.setToolTip("")
        vlayout.addWidget(dspinbox)

        checkbox = QCheckBox(_("with children"))
        checkbox.setChecked(True)
        checkbox.setToolTip(_("move all children"))
        vlayout.addWidget(checkbox)

        gcontainer = QWidget()
        glayout = QGridLayout()
        gcontainer.setLayout(glayout)
        vlayout.addWidget(gcontainer)

        button = QPushButton(_("Left"))
        button.setToolTip(_("move left"))
        button.clicked.connect(partial(object_move, dspinbox, checkbox, "left"))  # type: ignore
        glayout.addWidget(button, 1, 0)

        button = QPushButton(_("Right"))
        button.setToolTip(_("move right"))
        button.clicked.connect(partial(object_move, dspinbox, checkbox, "right"))  # type: ignore
        glayout.addWidget(button, 1, 2)

        button = QPushButton(_("Up"))
        button.setToolTip(_("move up"))
        button.clicked.connect(partial(object_move, dspinbox, checkbox, "up"))  # type: ignore
        glayout.addWidget(button, 0, 1)

        button = QPushButton(_("Down"))
        button.setToolTip(_("move down"))
        button.clicked.connect(partial(object_move, dspinbox, checkbox, "down"))  # type: ignore
        glayout.addWidget(button, 2, 1)

        def object_rotate(spinbox_angle, checkbox_childs, direction):
            object_active = self.project["object_active"]
            with_childs = checkbox_childs.isChecked()
            diff = spinbox_angle.value()
            if direction == "ccw":
                angle = diff
            elif direction == "cw":
                angle = -diff

            object_active_obj = None
            for obj_idx, obj in self.project["objects"].items():
                if obj_idx.startswith(f"{object_active}:"):
                    object_active_obj = obj

            center = points_to_center(object2points(object_active_obj))

            rotate_object(object_active_obj, center[0], center[1], angle * math.pi / 180.0)
            if with_childs:
                for inner in object_active_obj["inner_objects"]:
                    rotate_object(
                        self.project["objects"][inner],
                        center[0],
                        center[1],
                        angle * math.pi / 180.0,
                    )

            self.update_tabs_data()
            self.update_drawing()

        vlayout.addWidget(QLabel(_("Rotate:")))
        vlayout.addWidget(QLabel(_("Angle")))

        dspinbox = QDoubleSpinBox()
        dspinbox.setDecimals(4)
        dspinbox.setSingleStep(1.0)
        dspinbox.setMinimum(0.0)
        dspinbox.setMaximum(360.0)
        dspinbox.setValue(45.0)
        dspinbox.setToolTip("")
        vlayout.addWidget(dspinbox)

        checkbox = QCheckBox(_("with children"))
        checkbox.setChecked(True)
        checkbox.setToolTip(_("move all children"))
        vlayout.addWidget(checkbox)

        gcontainer = QWidget()
        glayout = QGridLayout()
        gcontainer.setLayout(glayout)
        vlayout.addWidget(gcontainer)

        button = QPushButton(_("CCW"))
        button.setToolTip(_("rotate counter clockwise"))
        button.clicked.connect(partial(object_rotate, dspinbox, checkbox, "ccw"))  # type: ignore
        glayout.addWidget(button, 0, 0)

        button = QPushButton(_("CW"))
        button.setToolTip(_("rotate clockwise"))
        button.clicked.connect(partial(object_rotate, dspinbox, checkbox, "cw"))  # type: ignore
        glayout.addWidget(button, 0, 1)

        def object_scale(spinbox_scale, checkbox_childs):
            object_active = self.project["object_active"]
            with_childs = checkbox_childs.isChecked()
            scale = spinbox_scale.value()

            object_active_obj = None
            for obj_idx, obj in self.project["objects"].items():
                if obj_idx.startswith(f"{object_active}:"):
                    object_active_obj = obj

            center = points_to_center(object2points(object_active_obj))
            move_object(object_active_obj, -center[0], -center[1])
            scale_object(object_active_obj, scale)
            move_object(object_active_obj, center[0], center[1])
            if with_childs:
                for inner in object_active_obj["inner_objects"]:
                    center = points_to_center(object2points(self.project["objects"][inner]))
                    move_object(self.project["objects"][inner], -center[0], -center[1])
                    scale_object(self.project["objects"][inner], scale)
                    move_object(self.project["objects"][inner], center[0], center[1])

            self.update_tabs_data()
            self.update_drawing()

        vlayout.addWidget(QLabel(_("Scale:")))
        vlayout.addWidget(QLabel(_("Scale")))

        dspinbox = QDoubleSpinBox()
        dspinbox.setDecimals(4)
        dspinbox.setSingleStep(1.0)
        dspinbox.setMinimum(0.0)
        dspinbox.setMaximum(1000.0)
        dspinbox.setValue(1.1)
        dspinbox.setToolTip(_("scale multiplier"))
        vlayout.addWidget(dspinbox)

        checkbox = QCheckBox(_("with children"))
        checkbox.setChecked(True)
        checkbox.setToolTip(_("move all children"))
        vlayout.addWidget(checkbox)

        gcontainer = QWidget()
        glayout = QGridLayout()
        gcontainer.setLayout(glayout)
        vlayout.addWidget(gcontainer)

        button = QPushButton(_("Scale"))
        button.setToolTip(_("scale"))
        button.clicked.connect(partial(object_scale, dspinbox, checkbox))  # type: ignore
        glayout.addWidget(button, 0, 0)

        def clone_object(obj_idx, offset_x=0, offset_y=0):
            if not obj_idx:
                return None
            main_idx = obj_idx.split(":")[0]
            main_uid = obj_idx.split(":")[1]
            idx_list = [oid.split(":")[0] for oid in self.project["objects"]]
            sub_idx = 1
            while f"{main_idx},{sub_idx}" in idx_list:
                sub_idx += 1
            new_obj_idx = f"{main_idx},{sub_idx}:{main_uid}"
            self.project["objects"][new_obj_idx] = deepcopy(self.project["objects"][obj_idx])

            move_object(
                self.project["objects"][new_obj_idx],
                offset_x,
                offset_y,
            )
            return new_obj_idx

        def object_copy(checkbox_childs, offset_direction):
            object_active = self.project["object_active"]
            with_childs = checkbox_childs.isChecked()

            object_active_obj = None
            object_active_obj_idx = ""
            for obj_idx, obj in self.project["objects"].items():
                if obj_idx.startswith(f"{object_active}:"):
                    object_active_obj = obj
                    object_active_obj_idx = obj_idx

            bounding_box = points_to_boundingbox(object2points(self.project["objects"][object_active_obj_idx]))
            offset_x = 0
            offset_y = 0
            layer = obj.layer
            if offset_direction == "left":
                offset_x = 0 - (bounding_box[2] - bounding_box[0]) - bounding_box[0] - 10
            elif offset_direction == "right":
                offset_x = (self.project["minMax"][2] - self.project["minMax"][0]) - bounding_box[0] + 10
            elif offset_direction == "top":
                offset_y = (self.project["minMax"][3] - self.project["minMax"][1]) - bounding_box[1] + 10
            elif offset_direction == "bottom":
                offset_y = 0 - (bounding_box[3] - bounding_box[1]) - bounding_box[1] - 10
            elif offset_direction == "layer":
                # found new layer-name
                ln = 0
                while f"{layer}-{ln}" in self.project["layersetup"]:
                    ln += 1
                layer = f"{layer}-{ln}"

            new_obj_idx = clone_object(object_active_obj_idx, offset_x, offset_y)
            if new_obj_idx is not None and with_childs:
                for inner in object_active_obj["inner_objects"]:
                    new_inner_obj_idx = clone_object(inner, offset_x, offset_y)
                    self.project["objects"][new_inner_obj_idx].layer = layer

            if self.project["objects"][new_obj_idx].layer != layer:
                self.project["layersetup"][layer] = deepcopy(self.project["layersetup"][self.project["objects"][new_obj_idx].layer])
                self.project["layers"][layer] = deepcopy(self.project["layers"][self.project["objects"][new_obj_idx].layer])
                self.project["objects"][new_obj_idx].layer = layer
            self.project["maxOuter"] = find_tool_offsets(self.project["objects"])

            self.lcombobjwidget_update()
            self.combobjwidget_update()
            self.setup_select_object(new_obj_idx)

            self.update_tabs_data()
            self.update_drawing()

        vlayout.addWidget(QLabel(_("Copy:")))

        checkbox = QCheckBox(_("with children"))
        checkbox.setChecked(True)
        checkbox.setToolTip(_("move all children"))
        vlayout.addWidget(checkbox)

        gcontainer = QWidget()
        glayout = QGridLayout()
        gcontainer.setLayout(glayout)
        vlayout.addWidget(gcontainer)

        button = QPushButton(_("Clone Top"))
        button.setToolTip(_("clone object"))
        button.clicked.connect(partial(object_copy, checkbox, "top"))  # type: ignore
        glayout.addWidget(button, 0, 1)

        button = QPushButton(_("Clone Left"))
        button.setToolTip(_("clone object"))
        button.clicked.connect(partial(object_copy, checkbox, "left"))  # type: ignore
        glayout.addWidget(button, 1, 0)

        button = QPushButton(_("Clone Right"))
        button.setToolTip(_("clone object"))
        button.clicked.connect(partial(object_copy, checkbox, "right"))  # type: ignore
        glayout.addWidget(button, 1, 2)

        button = QPushButton(_("Clone Bottom"))
        button.setToolTip(_("clone object"))
        button.clicked.connect(partial(object_copy, checkbox, "bottom"))  # type: ignore
        glayout.addWidget(button, 2, 1)

        button = QPushButton(_("to new Layer"))
        button.setToolTip(_("clone object to new layer"))
        button.clicked.connect(partial(object_copy, checkbox, "layer"))  # type: ignore
        glayout.addWidget(button, 1, 1)

        vlayout.addStretch(1)
        tabwidget.addTab(scrollarea, _("Manipulate"))

    def update_tabs_data(self) -> None:
        self.project["tabs"]["data"] = []
        for obj in self.project["objects"].values():
            layer = obj.get("layer")
            if layer.startswith(("BREAKS:", "_TABS")):
                obj["setup"]["mill"]["active"] = False
                for segment in obj["segments"]:
                    self.project["tabs"]["data"].append(
                        (
                            (segment.start[0], segment.start[1]),
                            (segment.end[0], segment.end[1]),
                        )
                    )

    def prepare_segments(self) -> None:
        self.debug("prepare_segments: copy")
        segments = deepcopy(self.project["segments_org"])
        self.debug("prepare_segments: clean_segments")
        self.project["segments"] = clean_segments(segments)
        self.debug("prepare_segments: segments2objects")
        self.project["objects"] = segments2objects(self.project["segments"])
        self.project["layers"] = {}
        self.project["layersetup"] = {}
        self.debug("prepare_segments: setup")
        for obj in self.project["objects"].values():
            obj["setup"] = {}
            for sect in ("mill", "tool", "pockets", "tabs", "leads"):
                obj["setup"][sect] = deepcopy(self.project["setup"][sect])
            layer = obj.get("layer")
            color = obj.get("color")

            if layer.startswith(("BREAKS:", "_TABS")):
                self.project["layers"][layer] = False
            else:
                self.project["layers"][layer] = True

            if layer not in self.project["layercolors"]:
                color_name = ""
                if color in dxfcolors:
                    color_name = dxfcolors[color][3]
                self.project["layercolors"][layer] = color_name

            if layer not in self.project["layersetup"]:
                self.project["layersetup"][layer] = {}
                for sect in ("mill", "tool", "pockets", "tabs", "leads"):
                    self.project["layersetup"][layer][sect] = deepcopy(self.project["setup"][sect])

            # experimental: get some milling data from layer name (https://groups.google.com/g/dxf2gcode-users/c/q3hPQkN2OCo)
            if layer:
                if layer.startswith("IGNORE:"):
                    obj["setup"]["mill"]["active"] = False
                elif layer.startswith("MILL:"):
                    matches = self.LAYER_REGEX.findall(obj["layer"])
                    if matches:
                        for match in matches:
                            cmd = match[0].upper()
                            value = match[1]
                            if cmd == "MILL":
                                self.project["layersetup"][layer]["mill"]["active"] = bool(value == "1")
                                obj["setup"]["mill"]["active"] = bool(value == "1")
                            elif cmd in ("MILLDEPTH", "MD"):
                                self.project["layersetup"][layer]["mill"]["depth"] = -abs(float(value))
                                obj["setup"]["mill"]["depth"] = -abs(float(value))
                            elif cmd in ("SLICEDEPTH", "SD"):
                                self.project["layersetup"][layer]["mill"]["step"] = -abs(float(value))
                                obj["setup"]["mill"]["step"] = -abs(float(value))
                            elif cmd in ("FEEDXY", "FXY"):
                                self.project["layersetup"][layer]["tool"]["rate_h"] = int(value)
                                obj["setup"]["tool"]["rate_h"] = int(value)
                            elif cmd in ("FEEDZ", "FZ"):
                                self.project["layersetup"][layer]["tool"]["rate_v"] = int(value)
                                obj["setup"]["tool"]["rate_v"] = int(value)

        for obj in self.project["objects"].values():
            layer = obj.get("layer")
            if layer.endswith("_hatch"):
                obj["setup"]["mill"]["offset"] = "inside"
                obj["setup"]["pockets"]["active"] = True
                obj["setup"]["pockets"]["nocontour"] = True
                self.project["layersetup"][layer]["mill"]["offset"] = "inside"
                self.project["layersetup"][layer]["pockets"]["active"] = True
                self.project["layersetup"][layer]["pockets"]["nocontour"] = True

        self.debug("prepare_segments: update_tabs_data")
        self.update_tabs_data()
        if not self.args.laser:
            self.debug("prepare_segments: find_tool_offsets")
            self.project["maxOuter"] = find_tool_offsets(self.project["objects"])
        self.debug("prepare_segments: done")

    def load_drawings(self, filenames: list, no_setup: bool = False, append_only: bool = False) -> bool:
        # clean project
        if append_only and not self.project["filename_draw"]:
            append_only = False
        if not append_only:
            self.debug("load_drawing: cleanup")
            self.project["filename_draw"] = ""
            self.project["filename_drawings"] = []
            self.project["filename_machine_cmd"] = ""
            self.project["suffix"] = "ngc"
            self.project["axis"] = ["X", "Y", "Z"]
            self.project["machine_cmd"] = ""
            self.project["segments"] = {}
            self.project["objects"] = {}
            self.project["offsets"] = {}
            self.project["gllist"] = []
            self.project["maxOuter"] = 0
            self.project["minMax"] = []
            self.project["table"] = []
            self.project["status"] = "INIT"
            self.project["tabs"] = {"data": [], "table": None}
            self.project["draw_reader"] = None
            self.info = ""
            self.save_tabs = "no"
            self.save_starts = "no"

        loaded = False

        for file_n, filename in enumerate(filenames):
            # find plugin
            self.debug(f"load_drawing: start {filename}")

            suffix = filename.rsplit(".", maxsplit=1)[-1].lower()

            reader_plugin_list = []
            for plugin_name, reader_plugin in reader_plugins.items():
                if suffix in reader_plugin.suffix(self.args):
                    reader_plugin_list.append(plugin_name)

            if not reader_plugin_list:
                return False

            if len(reader_plugin_list) == 1:
                plugin_name = reader_plugin_list[0]
            elif self.main is None:
                plugin_name = reader_plugin_list[0]
            else:
                dialog = QDialog()
                dialog.setWindowTitle(f"{_('Reader-Selection')}: {os.path.basename(filename)}")

                dialog.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok)  # type: ignore
                dialog.buttonBox.accepted.connect(dialog.accept)  # type: ignore

                dialog.layout = QVBoxLayout()  # type: ignore
                message = QLabel(_("Import-Options"))
                dialog.layout.addWidget(message)  # type: ignore

                combobox = QComboBox()
                for plugin_name in reader_plugin_list:
                    combobox.addItem(plugin_name)  # type: ignore
                dialog.layout.addWidget(combobox)  # type: ignore

                dialog.layout.addWidget(dialog.buttonBox)  # type: ignore
                dialog.setLayout(dialog.layout)  # type: ignore

                if dialog.exec():
                    plugin_name = combobox.currentText()
                    reader_plugin = reader_plugins[plugin_name]

            reader_plugin = reader_plugins[plugin_name]
            if not no_setup and self.main is not None and hasattr(reader_plugin, "preload_setup"):
                reader_plugin.preload_setup(filename, self.args)
            self.project["draw_reader"] = reader_plugin(filename, self.args)
            if reader_plugin.can_save_tabs:
                self.save_tabs = "ask"

            if self.project["draw_reader"]:
                self.debug("load_drawing: get segments")
                if file_n == 0 and not append_only:
                    self.project["filename_draw"] = filename
                    self.project["filename_machine_cmd"] = f"{'.'.join(self.project['filename_draw'].split('.')[:-1])}.{self.project['suffix']}"
                    self.project["segments_org"] = self.project["draw_reader"].get_segments()
                else:
                    max_y = -9999999
                    for segment in self.project["segments_org"]:
                        for ptype in ("start", "end", "center"):
                            if ptype in segment:
                                max_y = max(max_y, segment[ptype][1])

                    more_segments = self.project["draw_reader"].get_segments()
                    for segment in more_segments:
                        for ptype in ("start", "end", "center"):
                            if ptype in segment:
                                segment[ptype] = (
                                    segment[ptype][0],
                                    segment[ptype][1] + max_y + 20,
                                )
                    self.project["segments_org"] += more_segments
                self.project["filename_drawings"].append(filename)
                loaded = True

        if loaded:
            self.debug("load_drawing: prepare_segments")
            self.prepare_segments()
            self.debug("load_drawing: done")

            # disable some options on big drawings for a better view
            if len(self.project["objects"]) >= 50:
                self.project["setup"]["view"]["autocalc"] = False
                self.project["setup"]["view"]["path"] = "minimal"
                self.project["setup"]["view"]["object_ids"] = False
                self.project["setup"]["pockets"]["active"] = False

            self.project["origin"] = objects2minmax(self.project["objects"])[0:2]

            if self.combobjwidget is not None:
                self.combobjwidget_update()
                self.combobjwidget.setCurrentText(self.project["object_active"])

            return True

        eprint(f"ERROR: can not load file: {filename}")
        self.debug("load_drawing: error")
        return False

    def combobjwidget_update(self):
        if self.combobjwidget is not None:
            self.combobjwidget.clear()
            for idx, obj in self.project["objects"].items():
                self.combobjwidget.addItem(f"{idx.split(':')[0]} (Layer: {obj.layer})")
            if self.project["object_active"]:
                self.combobjwidget.setCurrentText(self.project["object_active"])

    def lcombobjwidget_update(self):
        if self.lcombobjwidget is not None:
            self.lcombobjwidget.clear()
            for layer in self.project["layersetup"]:
                color_name = self.project["layercolors"].get(layer) or "---"
                self.lcombobjwidget.addItem(f"{layer} ({color_name})")

    def open_preview_in_openscad(self):
        if self.project["suffix"] in {"ngc", "gcode"} and self.project["machine_cmd"]:
            parser = GcodeParser(self.project["machine_cmd"])

            diameter = None
            for entry in self.project["setup"]["tool"]["tooltable"]:
                if self.project["setup"]["tool"]["number"] == entry["number"]:
                    diameter = entry["diameter"]
            if diameter is None:
                print("ERROR: nest: TOOL not found")
                return

            scad_data = parser.openscad(diameter)
            open(f"{TEMP_PREFIX}viaconstructor-preview.scad", "w").write(scad_data)

            def openscad_show():
                process = subprocess.Popen([openscad, f"{TEMP_PREFIX}viaconstructor-preview.scad"])
                while True:
                    time.sleep(0.5)
                    return_code = process.poll()
                    if return_code is not None:
                        break
                self.project["preview_open"].setEnabled(True)
                os.remove(f"{TEMP_PREFIX}viaconstructor-preview.scad")

            self.project["preview_open"].setEnabled(False)
            threading.Thread(target=openscad_show).start()

    def open_preview_in_camotics(self):
        if self.project["suffix"] in {"ngc", "gcode"} and self.project["machine_cmd"]:
            units = "metric"
            if self.project["setup"]["machine"]["unit"] == "inch":
                units = "imperial"

            tools = {}
            for obj in self.project["objects"].values():

                diameter = None
                for entry in self.project["setup"]["tool"]["tooltable"]:
                    if obj.setup["tool"]["number"] == entry["number"]:
                        diameter = entry["diameter"]
                if diameter is None:
                    print("ERROR: nest: TOOL not found")
                    return

                tools[obj.setup["tool"]["number"]] = {
                    "units": units,
                    "shape": "cylindrical",
                    "length": abs(self.project["setup"]["mill"]["step"] * 1.5),
                    "diameter": diameter,
                    "description": "",
                }

            camotics_data = {
                "units": units,
                "resolution-mode": "high",
                "resolution": 0.294723,
                "tools": tools,
                "files": [
                    f"{TEMP_PREFIX}viaconstructor-preview.ngc",
                ],
            }

            open(f"{TEMP_PREFIX}viaconstructor-preview.ngc", "w").write(self.project["machine_cmd"])
            open(f"{TEMP_PREFIX}viaconstructor-preview.camotics", "w").write(json.dumps(camotics_data, indent=4, sort_keys=True))

            def camotics_show():
                process = subprocess.Popen([camotics, f"{TEMP_PREFIX}viaconstructor-preview.camotics"])
                while True:
                    time.sleep(0.5)
                    return_code = process.poll()
                    if return_code is not None:
                        break
                os.remove(f"{TEMP_PREFIX}viaconstructor-preview.camotics")
                os.remove(f"{TEMP_PREFIX}viaconstructor-preview.ngc")

            threading.Thread(target=camotics_show).start()

    def generate_preview(self):
        if self.project["suffix"] in {"ngc", "gcode"} and self.project["machine_cmd"]:
            parser = GcodeParser(self.project["machine_cmd"])

            diameter = None
            for entry in self.project["setup"]["tool"]["tooltable"]:
                if self.project["setup"]["tool"]["number"] == entry["number"]:
                    diameter = entry["diameter"]
            if diameter is None:
                print("ERROR: nest: TOOL not found")
                return

            scad_data = parser.openscad(diameter)
            open(f"{TEMP_PREFIX}viaconstructor-preview.scad", "w").write(scad_data)

            def openscad_convert():
                os.system(f"{openscad} -o {TEMP_PREFIX}viaconstructor-preview.png {TEMP_PREFIX}viaconstructor-preview.scad")
                image = QImage(f"{TEMP_PREFIX}viaconstructor-preview.png")
                self.project["imgwidget"].setPixmap(QPixmap.fromImage(image))
                self.project["preview_generate"].setEnabled(True)
                self.project["preview_generate"].setText(_("generate Preview"))
                os.remove(f"{TEMP_PREFIX}viaconstructor-preview.scad")

            self.project["preview_generate"].setEnabled(False)
            self.project["preview_generate"].setText(_("generating preview image with openscad.... please wait"))
            threading.Thread(target=openscad_convert).start()

    def tab_changed(self, idx) -> None:
        if idx == 1:
            value = self.lcombobjwidget.currentText()
            self.setup_select_layer(value)
        elif idx == 2:
            value = self.combobjwidget.currentText()
            self.setup_select_object(value)

    def __init__(self) -> None:
        """viaconstructor main init."""
        setproctitle.setproctitle("viaconstructor")  # pylint: disable=I1101

        # arguments
        parser = argparse.ArgumentParser()
        parser.add_argument("filenames", help="input files", type=str, nargs="*", default=None)
        parser.add_argument(
            "--engine",
            help="display engine",
            type=str,
            default="3D",
        )
        parser.add_argument(
            "-s",
            "--setup",
            help="setup file",
            type=str,
            default=f"{os.path.join(Path.home(), 'viaconstructor.json')}",
        )
        parser.add_argument(
            "-o",
            "--output",
            help="save to machine_cmd and exit",
            type=str,
            default=None,
        )
        parser.add_argument(
            "-d",
            "--dxf",
            help="convert drawing to dxf file and exit",
            type=str,
            default=None,
        )
        parser.add_argument(
            "-l",
            "--laser",
            help="laser mode / no offsets / no order",
            type=str,
            default=None,
        )
        parser.add_argument(
            "-D",
            "--debug",
            help="enable debug output",
            action="store_true",
            default=False,
        )

        for reader_plugin in reader_plugins.values():
            reader_plugin.arg_parser(parser)

        self.args = parser.parse_args()
        self.project["engine"] = self.args.engine

        # load setup
        self.debug("main: load setup")
        self.project["setup"] = {}
        for sname in self.project["setup_defaults"]:
            self.project["setup"][sname] = {}
            for oname, option in self.project["setup_defaults"][sname].items():
                self.project["setup"][sname][oname] = option["default"]

        if os.path.isfile(self.args.setup):
            self.setup_load(self.args.setup)

        if self.args.laser:
            self.project["setup"]["view"]["polygon_show"] = False
            self.project["setup"]["mill"]["offset"] = "none"

        # load drawing #
        self.debug("main: load drawing")

        if self.args.dxf:
            # set laser-mode to disable offset calculation
            self.args.laser = True

        if self.args.filenames and self.args.filenames[0].endswith(".vcp"):
            self.load_project(self.args.filenames[0])

            # save and exit
            if self.args.dxf:
                #  self.update_drawing()
                eprint(f"saving dawing to file: {self.args.dxf}")
                self.save_objects_as_dxf(self.args.dxf)
                sys.exit(0)
            if self.args.output:
                self.update_drawing()
                eprint(f"saving machine_cmd to file: {self.args.output}")
                open(self.args.output, "w").write(self.project["machine_cmd"])
                sys.exit(0)
        elif self.args.filenames and self.load_drawings(self.args.filenames):
            # save and exit
            if self.args.dxf:
                # self.update_drawing()
                eprint(f"saving dawing to file: {self.args.dxf}")
                self.save_objects_as_dxf(self.args.dxf)
                sys.exit(0)
            if self.args.output:
                self.update_drawing()
                eprint(f"saving machine_cmd to file: {self.args.output}")
                open(self.args.output, "w").write(self.project["machine_cmd"])
                sys.exit(0)

        # gui #
        self.debug("main: load gui")
        # QApplication.setAttribute(Qt.AA_UseSoftwareOpenGL)  # needed for windows ?
        QApplication.setAttribute(Qt.AA_UseDesktopOpenGL)  # type: ignore
        qapp = QApplication(sys.argv)
        self.project["window"] = QWidget()
        self.project["app"] = self

        if self.project["engine"] == "2D":
            self.project["glwidget"] = CanvasWidget(self.project, self.update_drawing)
        else:
            self.project["glwidget"] = GLWidget(self.project, self.update_drawing)

        self.project["imgwidget"] = QLabel()
        self.project["imgwidget"].setBackgroundRole(QPalette.Base)  # type: ignore
        self.project["imgwidget"].setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)  # type: ignore
        self.project["imgwidget"].setScaledContents(True)

        self.main = myQMainWindow(self)
        self.main.setWindowTitle("viaConstructor")
        self.main.setCentralWidget(self.project["window"])

        self.this_dir, self.this_filename = os.path.split(__file__)

        self.create_menubar()
        self.create_toolbar()

        self.status_bar = QStatusBar()
        self.main.setStatusBar(self.status_bar)
        self.status_bar_message(f"{self.info} - startup")

        self.project["textwidget"] = QPlainTextEdit()
        self.project["reportwidget"] = QPlainTextEdit()
        left_gridlayout = QGridLayout()

        tabwidget = QTabWidget()
        tabwidget.setMovable(True)
        tabwidget.addTab(self.project["glwidget"], _("&3D-View"))
        tabwidget.addTab(self.project["textwidget"], _("&Machine-Output"))
        tabwidget.addTab(self.project["reportwidget"], _("&Report"))

        if openscad or camotics:
            preview = QWidget()
            preview.setContentsMargins(0, 0, 0, 0)
            preview_vbox = QVBoxLayout(preview)
            preview_vbox.setContentsMargins(0, 0, 0, 0)
            if openscad:
                self.project["preview_generate"] = QPushButton(_("generate Preview"))
                self.project["preview_generate"].setToolTip(_("this may take some time"))
                self.project["preview_generate"].pressed.connect(self.generate_preview)
                preview_vbox.addWidget(self.project["preview_generate"])
                self.project["preview_open"] = QPushButton(_("view in openscad"))
                self.project["preview_open"].setToolTip(_("open preview in openscad"))
                self.project["preview_open"].pressed.connect(self.open_preview_in_openscad)
                preview_vbox.addWidget(self.project["preview_open"])
            if camotics:
                self.project["preview_open2"] = QPushButton(_("view in camotics"))
                self.project["preview_open2"].setToolTip(_("open preview in camotics"))
                self.project["preview_open2"].pressed.connect(self.open_preview_in_camotics)
                preview_vbox.addWidget(self.project["preview_open2"])

            preview_vbox.addWidget(self.project["imgwidget"])
            tabwidget.addTab(preview, _("&Preview"))

        right_gridlayout = QGridLayout()
        right_gridlayout.addWidget(tabwidget)

        left_widget = QWidget()
        left_widget.setContentsMargins(0, 0, 0, 0)

        vbox = QVBoxLayout(left_widget)
        vbox.setContentsMargins(0, 0, 0, 0)
        # vbox.addWidget(QLabel(_("Global-Settings:")))

        self.tabwidget = QTabWidget()
        self.create_global_setup(self.tabwidget)

        self.tabobjwidget = QTabWidget()
        self.create_object_setup(self.tabobjwidget)

        self.objwidget = QWidget()
        object_vbox = QVBoxLayout(self.objwidget)
        object_vbox.setContentsMargins(0, 0, 0, 0)

        self.combobjwidget = QComboBox()
        self.combobjwidget.addItem("0")
        self.combobjwidget.setCurrentText("0")
        self.combobjwidget.setToolTip("Global/Object settings")
        self.combobjwidget.currentTextChanged.connect(self.setup_select_object)  # type: ignore

        object_vbox.addWidget(QLabel(_("Object:")))
        object_vbox.addWidget(self.combobjwidget, stretch=0)
        object_vbox.addWidget(self.tabobjwidget, stretch=1)

        self.tablaywidget = QTabWidget()
        self.create_layer_setup(self.tablaywidget)

        self.laywidget = QWidget()
        layer_vbox = QVBoxLayout(self.laywidget)
        layer_vbox.setContentsMargins(0, 0, 0, 0)

        self.lcombobjwidget = QComboBox()
        self.lcombobjwidget.addItem("0")
        self.lcombobjwidget.setCurrentText("0")
        self.lcombobjwidget.setToolTip("Layer settings")
        self.lcombobjwidget.currentTextChanged.connect(self.setup_select_layer)  # type: ignore

        layer_vbox.addWidget(QLabel(_("Layer:")))
        layer_vbox.addWidget(self.lcombobjwidget, stretch=0)
        layer_vbox.addWidget(self.tablaywidget, stretch=1)

        self.infotext_widget = QPlainTextEdit()
        self.infotext_widget.setPlainText("info:")
        
        self.settings_widget = QTabWidget()
        self.create_settings_tabs(self.settings_widget)

        ltabwidget = QTabWidget()
        ltabwidget.addTab(self.tabwidget, _("&Global"))
        ltabwidget.addTab(self.laywidget, _("&Layers"))
        ltabwidget.addTab(self.objwidget, _("&Objects"))
        ltabwidget.addTab(self.infotext_widget, _("&Infos"))
        ltabwidget.addTab(self.settings_widget, _("&Setup"))
        ltabwidget.currentChanged.connect(self.tab_changed)

        left_gridlayout.addWidget(ltabwidget)

        if self.combobjwidget is not None:
            self.combobjwidget_update()
            self.project["object_active"] = "0"
            self.combobjwidget.setCurrentText(self.project["object_active"])

        if self.lcombobjwidget is not None:
            self.lcombobjwidget_update()
            if self.project["layersetup"]:
                self.project["layer_active"] = "(".join(list(self.project["layersetup"])[0].split("(")[0:-1]).strip()
                self.lcombobjwidget.setCurrentText(self.project["layer_active"])

        self.update_layer_setup()
        self.update_object_setup()

        bottom_container = QWidget()
        bottom_container.setContentsMargins(0, 0, 0, 0)
        bottom_container.setLayout(left_gridlayout)
        vbox.addWidget(bottom_container, stretch=0)

        right_widget = QWidget()
        right_widget.setLayout(right_gridlayout)

        hlay = QHBoxLayout(self.project["window"])
        hlay.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Horizontal)
        hlay.addWidget(splitter)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)

        mwin_width = 1200
        mwin_height = 800
        lratio = 0.24
        splitter.setSizes([int(mwin_width * lratio), int(mwin_height * (1.0 - lratio))])

        # Tools
        self.font_tool = FontTool(self)
        self.gear_tool = GearTool(self)
        self.box_tool = BoxTool(self)

        self.main.resize(mwin_width, mwin_height)
        self.main.show()
        self.debug("main: gui ready")
        sys.stdout.flush()

        if self.project["engine"] == "2D":
            if self.project["status"] == "INIT":
                self.project["status"] = "READY"
            self.update_drawing()

        ret = qapp.exec_()
        if self.project["setup"]["view"]["autosave"]:
            print("saving setup defaults")
            self._toolbar_save_setup()

        sys.exit(ret)


if __name__ == "__main__":
    ViaConstructor()
