"""viaconstructor tool."""

import argparse
import gettext
import importlib
import json
import math
import os
import platform
import re
import sys
import threading
import time
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import Optional, Union

import ezdxf
import setproctitle
from PyQt5.QtGui import (  # pylint: disable=E0611
    QFont,
    QIcon,
    QImage,
    QPalette,
    QPixmap,
    QStandardItem,
    QStandardItemModel,
)
from PyQt5.QtWidgets import (  # pylint: disable=E0611
    QAction,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
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
    QSizePolicy,
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
    clean_segments,
    find_tool_offsets,
    mirror_objects,
    move_object,
    move_objects,
    objects2minmax,
    objects2polyline_offsets,
    rotate_object,
    rotate_objects,
    scale_objects,
    segments2objects,
)
from .draw2d import CanvasWidget
from .draw2d import draw_all as draw_all_2d
from .gldraw import GLWidget
from .gldraw import draw_all as draw_all_gl
from .machine_cmd import polylines2machine_cmd
from .output_plugins.gcode_linuxcnc import PostProcessorGcodeLinuxCNC
from .output_plugins.hpgl import PostProcessorHpgl
from .preview_plugins.gcode import GcodeParser
from .setupdefaults import setup_defaults

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
for reader in ("dxfread", "hpglread", "stlread", "svgread", "ttfread", "imgread"):
    try:
        drawing_reader = importlib.import_module(
            f".{reader}", "viaconstructor.input_plugins"
        )
        reader_plugins[reader] = drawing_reader.DrawReader
    except Exception as reader_error:  # pylint: disable=W0703
        sys.stderr.write(f"ERRO while loading input plugin {reader}: {reader_error}\n")


DEBUG = False
TIMESTAMP = 0


def eprint(message, *args, **kwargs):  # pylint: disable=W0613
    sys.stderr.write(f"{message}\n")


def debug(message):
    global TIMESTAMP  # pylint: disable=W0603
    if DEBUG:
        now = time.time()
        if TIMESTAMP == 0:
            TIMESTAMP = now
        eprint(round(now - TIMESTAMP, 1))
        eprint(f"{message} ", end="", flush=True)
        TIMESTAMP = now


# i18n
def no_translation(text):
    return text


_ = no_translation
lang = os.environ.get("LANGUAGE")
if lang:
    localedir = os.path.join(Path(__file__).resolve().parent, "locales")
    try:
        lang_translations = gettext.translation(
            "base", localedir=localedir, languages=[lang]
        )

        lang_translations.install()
        _ = lang_translations.gettext
    except FileNotFoundError:
        sys.stderr.write(f"WARNING: localedir not found {localedir}\n")


class ViaConstructor:
    """viaconstructor main class."""

    LAYER_REGEX = re.compile(
        r"([a-zA-Z]{1,4}):\s*([+-]?([0-9]+([.][0-9]*)?|[.][0-9]+))"
    )

    project: dict = {
        "engine": "3D",
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
        "imgwidget": None,
        "preview_generate": None,
        "preview_open": None,
        "status": "INIT",
        "tabs": {
            "data": [],
            "table": None,
        },
        "textwidget": None,
        "simulation": False,
        "simulation_pos": 0,
        "simulation_last": (0.0, 0.0, 0.0),
        "simulation_data": [],
        "simulation_cnt": 0,
        "draw_reader": None,
    }
    info = ""
    save_tabs = "no"
    save_starts = "no"
    status_bar: Optional[QStatusBar] = None
    main: Optional[QMainWindow] = None
    toolbar: Optional[QToolBar] = None
    menubar: Optional[QMenuBar] = None
    toolbuttons: dict = {}

    module_root = Path(__file__).resolve().parent

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
                        ) = ezdxf.math.bulge_to_arc(
                            segment.start, segment.end, segment.bulge
                        )
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

        debug("run_calculation: centercalc")

        psetup: dict = self.project["setup"]
        min_max = objects2minmax(self.project["objects"])
        self.project["minMax"] = min_max
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

        debug("run_calculation: offsets")

        # create toolpath from objects
        unit = psetup["machine"]["unit"]
        diameter = psetup["tool"]["diameter"]
        if unit == "inch":
            diameter *= 25.4
        self.project["offsets"] = objects2polyline_offsets(
            diameter,
            self.project["objects"],
            self.project["maxOuter"],
            psetup["mill"]["small_circles"],
        )

        # create machine commands
        debug("run_calculation: machine_commands")
        output_plugin: Union[PostProcessorHpgl, PostProcessorGcodeLinuxCNC]
        if self.project["setup"]["machine"]["plugin"] == "gcode_linuxcnc":
            output_plugin = PostProcessorGcodeLinuxCNC(
                self.project["setup"]["machine"]["comments"]
            )
            self.project["suffix"] = output_plugin.suffix()
            self.project["axis"] = output_plugin.axis()
        elif self.project["setup"]["machine"]["plugin"] == "hpgl":
            output_plugin = PostProcessorHpgl(
                self.project["setup"]["machine"]["comments"]
            )
            self.project["suffix"] = output_plugin.suffix()
            self.project["axis"] = output_plugin.axis()
        else:
            eprint(
                f"ERROR: Unknown machine output plugin: {self.project['setup']['machine']['plugin']}"
            )
            sys.exit(1)
        self.project["machine_cmd"] = polylines2machine_cmd(self.project, output_plugin)
        debug("run_calculation: update textwidget")
        if self.project["textwidget"]:
            self.project["textwidget"].clear()
            self.project["textwidget"].insertPlainText(self.project["machine_cmd"])
            self.project["textwidget"].verticalScrollBar().setValue(0)

        debug("run_calculation: done")

    def _toolbar_flipx(self) -> None:
        mirror_objects(self.project["objects"], self.project["minMax"], vertical=True)
        self.project["minMax"] = objects2minmax(self.project["objects"])
        self.udate_tabs_data()
        self.update_drawing()

    def _toolbar_flipy(self) -> None:
        mirror_objects(self.project["objects"], self.project["minMax"], horizontal=True)
        self.project["minMax"] = objects2minmax(self.project["objects"])
        self.udate_tabs_data()
        self.update_drawing()

    def _toolbar_rotate(self) -> None:
        rotate_objects(self.project["objects"], self.project["minMax"])
        self.project["minMax"] = objects2minmax(self.project["objects"])
        self.udate_tabs_data()
        self.update_drawing()

    def _toolbar_nest(self) -> None:
        int_scale = 100000
        obj_dist = max(self.project["setup"]["tool"]["diameter"] * 3, 1.0)
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
        self.udate_tabs_data()
        self.update_drawing()

    def _toolbar_scale(self) -> None:
        scale, dialog_ok = QInputDialog.getText(
            self.project["window"], _("Workpiece-Scale"), _("Scale-Factor:"), text="1.0"
        )
        if (
            dialog_ok
            and str(scale).replace(".", "").isnumeric()
            and float(scale) != 1.0
        ):
            scale_objects(self.project["objects"], float(scale))
            self.project["minMax"] = objects2minmax(self.project["objects"])
            self.udate_tabs_data()
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

    def machine_cmd_save(self, filename: str) -> bool:
        with open(filename, "w") as fd_machine_cmd:
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
        file_dialog = QFileDialog(self.main)
        file_dialog.setNameFilters(
            [f"{self.project['suffix']} (*.{self.project['suffix']})"]
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
            self.status_bar_message(
                f"{self.info} - save machine-code..done ({name[0]})"
            )
        else:
            self.status_bar_message(f"{self.info} - save machine-code..cancel")

    def _toolbar_save_dxf(self) -> None:
        """save doawing as dxf."""
        self.status_bar_message(f"{self.info} - save drawing as dxf..")
        file_dialog = QFileDialog(self.main)
        file_dialog.setNameFilters(["dxf (*.dxf)"])
        self.project[
            "filename_machine_cmd"
        ] = f"{'.'.join(self.project['filename_draw'].split('.')[:-1])}.dxf"
        name = file_dialog.getSaveFileName(
            self.main,
            "Save File",
            self.project["filename_machine_cmd"],
            "dxf (*.dxf)",
        )
        if name[0] and self.save_objects_as_dxf(name[0]):
            self.status_bar_message(f"{self.info} - save dxf..done ({name[0]})")
        else:
            self.status_bar_message(f"{self.info} - save dxf..cancel")

    def _toolbar_load_drawing(self) -> None:
        """load drawing."""
        self.status_bar_message(f"{self.info} - load drawing..")
        file_dialog = QFileDialog(self.main)
        file_dialog.setNameFilters(["drawing (*.dxf)"])
        name = file_dialog.getOpenFileName(
            self.main, "Load Drawing", "", "drawing (*.dxf)"
        )
        if name[0] and self.load_drawing(name[0]):
            self.update_table()
            self.global_changed(0)
            self.update_drawing()

            self.create_menubar()
            self.create_toolbar()

            self.status_bar_message(f"{self.info} - load drawing..done ({name[0]})")
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
        name = file_dialog.getOpenFileName(
            self.main, "Load Setup", self.args.setup, "setup (*.json)"
        )
        if name[0] and self.setup_load(name[0]):
            self.project["status"] = "CHANGE"
            self.update_global_setup()
            self.update_table()
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
        name = file_dialog.getSaveFileName(
            self.main, "Save Setup", self.args.setup, "setup (*.json)"
        )
        if name[0] and self.setup_save(name[0]):
            self.status_bar_message(f"{self.info} - save setup as..done ({name[0]})")
        else:
            self.status_bar_message(f"{self.info} - ave setup as..cancel")

    def _toolbar_load_setup_from_drawing(self) -> None:
        if self.project["draw_reader"].can_load_setup:  # type: ignore
            if self.setup_load_string(self.project["draw_reader"].load_setup()):  # type: ignore
                self.project["status"] = "CHANGE"
                self.update_global_setup()
                self.update_table()
                self.global_changed(0)
                self.prepare_segments()
                self.update_drawing()
                self.project["status"] = "READY"
                self.status_bar_message(f"{self.info} - load setup from drawing..done")
            else:
                self.status_bar_message(
                    f"{self.info} - load setup from drawing..failed"
                )

    def _toolbar_save_setup_to_drawing(self) -> None:
        if self.project["draw_reader"].can_save_setup:  # type: ignore
            self.project["draw_reader"].save_setup(  # type: ignore
                json.dumps(self.project["setup"], indent=4, sort_keys=True)
            )
            self.status_bar_message(f"{self.info} - save setup to drawing..done")

    def toggle_layer(self, item):
        layer = self.project["layerwidget"].item(item.row(), 0).text()
        self.project["layers"][layer] = not self.project["layers"][layer]
        self.update_layers()

        for obj in self.project["objects"].values():
            layer = obj.get("layer")
            if layer in self.project["layers"]:
                obj["setup"]["mill"]["active"] = self.project["layers"][layer]

        self.global_changed(0)

    def update_layers(self) -> None:
        if "layerwidget" in self.project:
            self.project["layerwidget"].setRowCount(len(self.project["layers"]))
            row_idx = 0
            for layer, enabled in self.project["layers"].items():
                self.project["layerwidget"].setItem(row_idx, 0, QTableWidgetItem(layer))
                self.project["layerwidget"].setItem(
                    row_idx, 1, QTableWidgetItem("enabled" if enabled else "disabled")
                )
                row_idx += 1

    def update_drawing(self, draw_only=False) -> None:
        """update drawings."""
        if not self.project["draw_reader"]:
            return

        debug("update_drawing: start")
        self.status_bar_message(f"{self.info} - calculate..")
        if not draw_only:
            debug("update_drawing: run_calculation")
            self.run_calculation()
            debug("update_drawing: run_calculation done")

        if self.project["engine"] == "2D":
            draw_all_2d(self.project)
        else:
            draw_all_gl(self.project)

        self.info = f"{round(self.project['minMax'][2] - self.project['minMax'][0], 2)}x{round(self.project['minMax'][3] - self.project['minMax'][1], 2)}mm"
        if self.main:
            self.main.setWindowTitle("viaConstructor")
        self.status_bar_message(f"{self.info} - calculate..done")
        self.update_layers()
        debug("update_drawing: done")

    def materials_select(self, material_idx) -> None:
        """calculates the milling feedrate and tool-speed for the selected material
        see: https://www.precifast.de/schnittgeschwindigkeit-beim-fraesen-berechnen/
        """
        machine_feedrate = self.project["setup"]["machine"]["feedrate"]
        machine_toolspeed = self.project["setup"]["machine"]["tool_speed"]
        tool_diameter = self.project["setup"]["tool"]["diameter"]
        unit = self.project["setup"]["machine"]["unit"]
        if unit == "inch":
            tool_diameter *= 25.4
        tool_vc = self.project["setup"]["tool"]["materialtable"][material_idx]["vc"]
        tool_speed = tool_vc * 1000 / (tool_diameter * math.pi)
        tool_speed = int(min(tool_speed, machine_toolspeed))
        tool_blades = self.project["setup"]["tool"]["blades"]
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
        feedrate = int(min(feedrate, machine_feedrate))

        info_test = []
        info_test.append("Some Milling and Tool Values will be changed:")
        info_test.append("")
        info_test.append(
            f" Feedrate: {feedrate} {'(!MACHINE-LIMIT)' if feedrate == machine_feedrate else ''}"
        )
        info_test.append(
            f" Tool-Speed: {tool_speed} {'(!MACHINE-LIMIT)' if tool_speed == machine_toolspeed else ''}"
        )
        info_test.append("")
        ret = QMessageBox.question(
            self.main,  # type: ignore
            "Warning",
            "\n".join(info_test),
            QMessageBox.Ok | QMessageBox.Cancel,  # type: ignore
        )
        if ret != QMessageBox.Ok:  # type: ignore
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
        self.project["setup"]["tool"]["blades"] = int(
            self.project["setup"]["tool"]["tooltable"][tool_idx]["blades"]
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

    def color_select(self, section, name) -> None:
        color = QColorDialog.getColor().getRgbF()
        self.project["setup"][section][name] = color
        button = self.project["setup_defaults"][section][name]["widget"]
        rgb = f"{color[0] * 255:1.0f},{color[1] * 255:1.0f},{color[2] * 255:1.0f}"
        button.setStyleSheet(f"background-color:rgb({rgb})")
        button.setText(rgb)
        self.global_changed(0)

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
        elif entry_type == "str":
            value = str(value)
        elif entry_type == "table":
            pass
        elif entry_type == "color":
            pass
        else:
            eprint(f"Unknown setup-type: {entry_type}")
            value = None
        self.project["objects"][obj_idx]["setup"][sname][ename] = value
        if not self.args.laser:
            self.project["maxOuter"] = find_tool_offsets(self.project["objects"])
        self.update_drawing()

    def update_table(self) -> None:
        """update objects table."""

        selected = -1
        if (
            self.project["glwidget"]
            and self.project["glwidget"].selection_set
            and self.project["glwidget"].selector_mode in {"delete", "oselect"}
        ):
            selected = self.project["glwidget"].selection_set[2]

        debug("update_table: clear")
        self.project["objmodel"].clear()
        self.project["objmodel"].setHorizontalHeaderLabels(["Object", "Value"])
        # self.project["objwidget"].header().setDefaultSectionSize(180)
        self.project["objwidget"].setModel(self.project["objmodel"])
        root = self.project["objmodel"].invisibleRootItem()

        if len(self.project["objects"]) >= 50:
            debug(f"update_table: too many objects: {len(self.project['objects'])}")
            return
        debug("update_table: loading")
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
            for sname in ("mill", "pockets", "tabs", "leads"):
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
                            dspinbox = QDoubleSpinBox()
                            dspinbox.setDecimals(entry.get("decimals", 4))
                            dspinbox.setSingleStep(entry.get("step", 1.0))
                            dspinbox.setMinimum(entry["min"])
                            dspinbox.setMaximum(entry["max"])
                            dspinbox.setValue(value)
                            dspinbox.setToolTip(
                                entry.get("tooltip", f"{sname}/{ename}")
                            )
                            dspinbox.valueChanged.connect(partial(self.object_changed, obj_idx, sname, ename))  # type: ignore
                            self.project["objwidget"].setIndexWidget(
                                value_cell.index(), dspinbox
                            )
                        elif entry["type"] == "int":
                            spinbox = QSpinBox()
                            spinbox.setSingleStep(entry.get("step", 1))
                            spinbox.setMinimum(entry["min"])
                            spinbox.setMaximum(entry["max"])
                            spinbox.setValue(value)
                            spinbox.setToolTip(entry.get("tooltip", f"{sname}/{ename}"))
                            spinbox.valueChanged.connect(partial(self.object_changed, obj_idx, sname, ename))  # type: ignore
                            self.project["objwidget"].setIndexWidget(
                                value_cell.index(), spinbox
                            )
                        elif entry["type"] == "str":
                            lineedit = QLineEdit()
                            lineedit.setText(value)
                            lineedit.setToolTip(
                                entry.get("tooltip", f"{sname}/{ename}")
                            )
                            lineedit.textChanged.connect(partial(self.object_changed, obj_idx, sname, ename))  # type: ignore
                            self.project["objwidget"].setIndexWidget(
                                value_cell.index(), lineedit
                            )
                        elif entry["type"] == "table":
                            pass
                        elif entry["type"] == "color":
                            pass
                        else:
                            eprint(f"Unknown setup-type: {entry['type']}")

            index = self.project["objmodel"].indexFromItem(obj_root)
            if obj_idx == selected:
                self.project["objwidget"].expand(index)
            else:
                self.project["objwidget"].collapse(index)

        # self.project["objwidget"].expandAll()
        debug("update_table: done")

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
                elif entry["type"] == "str":
                    self.project["setup"][sname][ename] = entry["widget"].text()
                elif entry["type"] == "table":
                    for row_idx in range(entry["widget"].rowCount()):
                        col_idx = 0
                        for key, col_type in entry["columns"].items():
                            if entry["widget"].item(row_idx, col_idx + 1) is None:
                                print("TABLE_ERROR")
                                continue
                            if col_type["type"] == "str":
                                value = (
                                    entry["widget"].item(row_idx, col_idx + 1).text()
                                )
                                self.project["setup"][sname][ename][row_idx][key] = str(
                                    value
                                )
                            elif col_type["type"] == "int":
                                value = (
                                    entry["widget"].item(row_idx, col_idx + 1).text()
                                )
                                self.project["setup"][sname][ename][row_idx][key] = int(
                                    value
                                )
                            elif col_type["type"] == "float":
                                value = (
                                    entry["widget"].item(row_idx, col_idx + 1).text()
                                )
                                self.project["setup"][sname][ename][row_idx][
                                    key
                                ] = float(value)
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
        for obj in self.project["objects"].values():
            for sect in ("tool", "mill", "pockets", "tabs", "leads"):
                for key, global_value in self.project["setup"][sect].items():
                    # change object value only if the value changed and the value diffs again the last value in global
                    if (
                        global_value != old_setup[sect][key]
                        and obj["setup"][sect][key] == old_setup[sect][key]
                    ):
                        obj["setup"][sect][key] = self.project["setup"][sect][key]

        self.project["maxOuter"] = find_tool_offsets(self.project["objects"])

        self.update_table()
        self.update_drawing()

    def _toolbar_load_machine_cmd_setup(self) -> None:
        self.project[
            "filename_machine_cmd"
        ] = f"{'.'.join(self.project['filename_draw'].split('.')[:-1])}.{self.project['suffix']}"
        if os.path.isfile(self.project["filename_machine_cmd"]):
            self.status_bar_message(
                f"{self.info} - loading setup from machinecode: {self.project['filename_machine_cmd']}"
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
                        self.status_bar_message(
                            f"{self.info} - loading setup from machinecode..done"
                        )
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
                self.status_bar_message(
                    f"{self.info} - load tooltable ..failed ({save_error})"
                )

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
            self.update_table()
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
                    tooltable_tbl.append(
                        f"T{number} P{number} Z{0.0} D{tool['diameter']} ;{tool['name']} / blades:{tool['blades']}"
                    )
                tooltable_tbl.append("")
                tooldata = "\n".join(tooltable_tbl)

            try:
                open(name[0], "w").write(tooldata)
                self.status_bar_message(
                    f"{self.info} - save tooltable as..done ({name[0]})"
                )
            except Exception as save_error:  # pylint: disable=W0703
                self.status_bar_message(
                    f"{self.info} - save tooltable as..failed ({save_error})"
                )
        else:
            self.status_bar_message(f"{self.info} - save tooltable as..cancel")

    def _toolbar_exit(self) -> None:
        """exit button."""
        if os.environ.get("LINUXCNCVERSION"):
            print(self.project["machine_cmd"])
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
                "",
                _("Load drawing"),
                self._toolbar_load_drawing,
                not os.environ.get("LINUXCNCVERSION"),
                True,
                False,
                _("File"),
                "",
                None,
            ],
            _("Save drawing as DXF"): [
                "save.png",
                "Ctrl+S",
                _("Save drawing as DXF"),
                self._toolbar_save_dxf,
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
            _("Save Machine-Commands"): [
                "save-gcode.png",
                "Ctrl+S",
                _("Save machine commands"),
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
            _("View-Reset"): [
                "view-reset.png",
                "",
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
                "",
                _("2D-View"),
                self._toolbar_view_2d,
                True,
                True,
                False,
                _("View"),
                "",
                None,
            ],
            _("Flip-X"): [
                "flip-x.png",
                "",
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
                "",
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
                "",
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
            _("Nesting"): [
                "nesting.png",
                "",
                _("nesting workpiece"),
                self._toolbar_nest,
                HAVE_NEST,
                True,
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
                "",
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
                "",
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
                "",
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
                if toolbutton[1]:
                    action.setShortcut(toolbutton[1])
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
                elif entry["type"] == "table":
                    # add empty row if not exist
                    first_element = list(entry["columns"].keys())[0]

                    if (
                        entry.get("column_defaults") is not None
                        and str(self.project["setup"][sname][ename][-1][first_element])
                        != ""
                    ):
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
                        table.setHorizontalHeaderItem(
                            col_idx + idxf_offset, QTableWidgetItem(title)
                        )
                    for row_idx, row in enumerate(self.project["setup"][sname][ename]):
                        if entry["selectable"]:
                            button = QPushButton()
                            button.setIcon(
                                QIcon(
                                    os.path.join(
                                        self.module_root, "icons", "select.png"
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

                elif entry["type"] == "color":
                    pass
                else:
                    eprint(f"Unknown setup-type: {entry['type']}")

    def create_global_setup(self, tabwidget) -> None:
        for sname in self.project["setup_defaults"]:
            vcontainer = QWidget()
            vlayout = QVBoxLayout(vcontainer)
            tabwidget.addTab(vcontainer, sname)
            for ename, entry in self.project["setup_defaults"][sname].items():
                container = QWidget()

                hlayout = QHBoxLayout(container)
                label = QLabel(entry.get("title", ename))
                hlayout.addWidget(label)
                vlayout.addWidget(container)
                hlayout.addStretch(1)
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
                elif entry["type"] == "color":
                    color = self.project["setup"][sname][ename]
                    rgb = f"{color[0] * 255:1.0f},{color[1] * 255:1.0f},{color[2] * 255:1.0f}"
                    button = QPushButton(rgb)
                    button.setStyleSheet(f"background-color:rgb({rgb})")
                    button.setToolTip(entry.get("tooltip", f"{sname}/{ename}"))
                    button.clicked.connect(partial(self.color_select, sname, ename))  # type: ignore
                    hlayout.addWidget(button)
                    entry["widget"] = button
                elif entry["type"] == "float":
                    dspinbox = QDoubleSpinBox()
                    dspinbox.setDecimals(entry.get("decimals", 4))
                    dspinbox.setSingleStep(entry.get("step", 1.0))
                    dspinbox.setMinimum(entry["min"])
                    dspinbox.setMaximum(entry["max"])
                    dspinbox.setValue(self.project["setup"][sname][ename])
                    dspinbox.setToolTip(entry.get("tooltip", f"{sname}/{ename}"))
                    dspinbox.valueChanged.connect(self.global_changed)  # type: ignore
                    hlayout.addWidget(dspinbox)
                    entry["widget"] = dspinbox
                elif entry["type"] == "int":
                    spinbox = QSpinBox()
                    spinbox.setSingleStep(entry.get("step", 1))
                    spinbox.setMinimum(entry["min"])
                    spinbox.setMaximum(entry["max"])
                    spinbox.setValue(self.project["setup"][sname][ename])
                    spinbox.setToolTip(entry.get("tooltip", f"{sname}/{ename}"))
                    spinbox.valueChanged.connect(self.global_changed)  # type: ignore
                    hlayout.addWidget(spinbox)
                    entry["widget"] = spinbox
                elif entry["type"] == "str":
                    lineedit = QLineEdit()
                    lineedit.setText(self.project["setup"][sname][ename])
                    lineedit.setToolTip(entry.get("tooltip", f"{sname}/{ename}"))
                    lineedit.textChanged.connect(self.global_changed)  # type: ignore
                    hlayout.addWidget(lineedit)
                    entry["widget"] = lineedit
                elif entry["type"] == "table":
                    # add empty row if not exist
                    first_element = list(entry["columns"].keys())[0]
                    if (
                        entry.get("column_defaults") is not None
                        and str(self.project["setup"][sname][ename][-1][first_element])
                        != ""
                    ):
                        new_row = {}
                        for key, default in entry["column_defaults"].items():
                            new_row[key] = default
                        self.project["setup"][sname][ename].append(new_row)

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
                                        self.module_root, "icons", "select.png"
                                    )
                                )
                            )
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
                            #    item.setFlags(QtCore.Qt.ItemIsEditable)
                            table.resizeColumnToContents(col_idx + idxf_offset)
                    table.itemChanged.connect(self.global_changed)  # type: ignore
                    vlayout.addWidget(table)
                    entry["widget"] = table
                else:
                    eprint(f"Unknown setup-type: {entry['type']}")

                unit = entry.get("unit", "")
                if unit == "LINEARMEASURE":
                    unit = self.project["setup"]["machine"]["unit"]

                ulabel = QLabel(unit)
                ulabel.setFont(QFont("Arial", 9))
                hlayout.addWidget(ulabel)

    def udate_tabs_data(self) -> None:
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
        debug("prepare_segments: copy")
        segments = deepcopy(self.project["segments_org"])
        debug("prepare_segments: clean_segments")
        self.project["segments"] = clean_segments(segments)
        debug("prepare_segments: segments2objects")
        self.project["objects"] = segments2objects(self.project["segments"])
        self.project["layers"] = {}
        debug("prepare_segments: setup")
        for obj in self.project["objects"].values():
            obj["setup"] = {}
            for sect in ("tool", "mill", "pockets", "tabs", "leads"):
                obj["setup"][sect] = deepcopy(self.project["setup"][sect])
            layer = obj.get("layer")
            if layer.startswith(("BREAKS:", "_TABS")):
                self.project["layers"][layer] = False
            else:
                self.project["layers"][layer] = True
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
                                obj["setup"]["mill"]["active"] = bool(value == "1")
                            elif cmd in ("MILLDEPTH", "MD"):
                                obj["setup"]["mill"]["depth"] = -abs(float(value))
                            elif cmd in ("SLICEDEPTH", "SD"):
                                obj["setup"]["mill"]["step"] = -abs(float(value))
                            elif cmd in ("FEEDXY", "FXY"):
                                obj["setup"]["tool"]["rate_h"] = int(value)
                            elif cmd in ("FEEDZ", "FZ"):
                                obj["setup"]["tool"]["rate_v"] = int(value)
        debug("prepare_segments: udate_tabs_data")
        self.udate_tabs_data()
        if not self.args.laser:
            debug("prepare_segments: find_tool_offsets")
            self.project["maxOuter"] = find_tool_offsets(self.project["objects"])
        debug("prepare_segments: done")

    def load_drawing(self, filename: str) -> bool:
        # clean project
        debug("load_drawing: cleanup")
        self.project["filename_draw"] = ""
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

        # find plugin
        debug("load_drawing: start")
        suffix = filename.split(".")[-1].lower()
        for reader_plugin in reader_plugins.values():
            if suffix in reader_plugin.suffix(self.args):
                self.project["draw_reader"] = reader_plugin(filename, self.args)
                if reader_plugin.can_save_tabs:
                    self.save_tabs = "ask"
                break

        if self.project["draw_reader"]:
            debug("load_drawing: get segments")
            self.project["segments_org"] = self.project["draw_reader"].get_segments()
            self.project["filename_draw"] = filename
            self.project[
                "filename_machine_cmd"
            ] = f"{'.'.join(self.project['filename_draw'].split('.')[:-1])}.{self.project['suffix']}"
            debug("load_drawing: prepare_segments")
            self.prepare_segments()
            debug("load_drawing: done")

            # disable some options on big drawings for a better view
            if len(self.project["objects"]) >= 50:
                self.project["setup"]["view"]["path"] = "minimal"
                self.project["setup"]["view"]["object_ids"] = False

            return True

        eprint(f"ERROR: can not load file: {filename}")
        debug("load_drawing: error")
        return False

    def open_preview_in_openscad(self):
        if self.project["suffix"] in {"ngc", "gcode"}:
            parser = GcodeParser(self.project["machine_cmd"])
            scad_data = parser.openscad(self.project["setup"]["tool"]["diameter"])
            open("/tmp/viaconstructor-preview.scad", "w").write(scad_data)

            def openscad_show():
                os.system("/usr/bin/openscad /tmp/viaconstructor-preview.scad")
                self.project["preview_open"].setEnabled(True)

            self.project["preview_open"].setEnabled(False)
            threading.Thread(target=openscad_show).start()

    def generate_preview(self):
        if self.project["suffix"] in {"ngc", "gcode"}:
            parser = GcodeParser(self.project["machine_cmd"])
            scad_data = parser.openscad(self.project["setup"]["tool"]["diameter"])
            open("/tmp/viaconstructor-preview.scad", "w").write(scad_data)

            def openscad_convert():
                os.system(
                    "/usr/bin/openscad -o /tmp/viaconstructor-preview.png /tmp/viaconstructor-preview.scad"
                )
                image = QImage("/tmp/viaconstructor-preview.png")
                self.project["imgwidget"].setPixmap(QPixmap.fromImage(image))
                self.project["preview_generate"].setEnabled(True)
                self.project["preview_generate"].setText(_("generate Preview"))

            self.project["preview_generate"].setEnabled(False)
            self.project["preview_generate"].setText(
                _("generating preview image with openscad.... please wait")
            )
            threading.Thread(target=openscad_convert).start()

    def __init__(self) -> None:
        """viaconstructor main init."""
        debug("main: startup")
        setproctitle.setproctitle("viaconstructor")  # pylint: disable=I1101

        # arguments
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "filename", help="input file", type=str, nargs="?", default=None
        )
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

        for reader_plugin in reader_plugins.values():
            reader_plugin.arg_parser(parser)

        self.args = parser.parse_args()

        if platform.system().lower() == "windows":
            self.project["engine"] = "2D"
        else:
            self.project["engine"] = self.args.engine

        # load setup
        debug("main: load setup")
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
        debug("main: load drawing")
        if self.args.filename and self.load_drawing(self.args.filename):
            # save and exit
            if self.args.dxf:
                self.update_drawing()
                eprint(f"saving dawing to file: {self.args.dxf}")
                self.save_objects_as_dxf(self.args.dxf)
                sys.exit(0)
            if self.args.output:
                self.update_drawing()
                eprint(f"saving machine_cmd to file: {self.args.output}")
                open(self.args.output, "w").write(self.project["machine_cmd"])
                sys.exit(0)

        # gui #
        debug("main: load gui")
        qapp = QApplication(sys.argv)
        self.project["window"] = QWidget()
        self.project["app"] = self

        if self.project["engine"] == "2D":
            self.project["glwidget"] = CanvasWidget(self.project, self.update_drawing)
        else:
            self.project["glwidget"] = GLWidget(self.project, self.update_drawing)

        self.project["imgwidget"] = QLabel()
        self.project["imgwidget"].setBackgroundRole(QPalette.Base)  # type: ignore
        self.project["imgwidget"].setSizePolicy(
            QSizePolicy.Ignored, QSizePolicy.Ignored  # type: ignore
        )
        self.project["imgwidget"].setScaledContents(True)

        self.main = QMainWindow()
        self.main.setWindowTitle("viaConstructor")
        self.main.setCentralWidget(self.project["window"])

        self.this_dir, self.this_filename = os.path.split(__file__)

        self.create_menubar()
        self.create_toolbar()

        self.status_bar = QStatusBar()
        self.main.setStatusBar(self.status_bar)
        self.status_bar_message(f"{self.info} - startup")

        self.project["textwidget"] = QPlainTextEdit()
        self.project["objwidget"] = QTreeView()
        self.project["objmodel"] = QStandardItemModel()
        self.update_table()
        left_gridlayout = QGridLayout()
        left_gridlayout.addWidget(QLabel("Objects-Settings:"))

        self.project["layerwidget"] = QTableWidget()
        self.project["layerwidget"].clicked.connect(self.toggle_layer)
        self.project["layerwidget"].setRowCount(0)
        self.project["layerwidget"].setColumnCount(2)

        ltabwidget = QTabWidget()
        ltabwidget.addTab(self.project["objwidget"], _("Objects"))
        ltabwidget.addTab(self.project["layerwidget"], _("Layers"))

        left_gridlayout.addWidget(ltabwidget)

        tabwidget = QTabWidget()
        tabwidget.addTab(self.project["glwidget"], _("3D-View"))
        tabwidget.addTab(self.project["textwidget"], _("Machine-Output"))

        if os.path.isfile("/usr/bin/openscad"):
            preview = QWidget()
            preview.setContentsMargins(0, 0, 0, 0)
            preview_vbox = QVBoxLayout(preview)
            preview_vbox.setContentsMargins(0, 0, 0, 0)
            self.project["preview_generate"] = QPushButton(_("generate Preview"))
            self.project["preview_generate"].setToolTip(_("this may take some time"))
            self.project["preview_generate"].pressed.connect(self.generate_preview)
            preview_vbox.addWidget(self.project["preview_generate"])
            self.project["preview_open"] = QPushButton(_("view in openscad"))
            self.project["preview_open"].setToolTip(_("open's preview in openscad"))
            self.project["preview_open"].pressed.connect(self.open_preview_in_openscad)
            preview_vbox.addWidget(self.project["preview_open"])
            preview_vbox.addWidget(self.project["imgwidget"])
            tabwidget.addTab(preview, _("Preview"))

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

        hlay = QHBoxLayout(self.project["window"])
        hlay.addWidget(left_widget, stretch=1)
        hlay.addWidget(right_widget, stretch=3)

        self.main.resize(1600, 1200)
        self.main.show()
        debug("main: gui ready")

        if self.project["engine"] == "2D":
            if self.project["status"] == "INIT":
                self.project["status"] = "READY"
            self.update_drawing()

        sys.exit(qapp.exec_())


if __name__ == "__main__":
    ViaConstructor()
