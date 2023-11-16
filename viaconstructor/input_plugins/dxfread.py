"""dxf reading."""

import argparse
import math
import os
import shutil
import tempfile
import time

import ezdxf

from ..calc import (  # pylint: disable=E0402
    calc_distance,
    external_command,
    point_of_line,
)
from ..dxfcolors import dxfcolors
from ..input_plugins_base import DrawReaderBase
from ..vc_types import VcSegment

try:
    from ezdxf.addons import MTextExplode
    from ezdxf.path import Command, make_path
    from ezdxf.tools import fonts

    try:
        from ezdxf.addons import text2path

        SUPPORT_TEXT = True
    except Exception as error:  # pylint: disable=W0703
        print(f"WARNING: for text support, please install matplotlib: {error}")
        SUPPORT_TEXT = False

except Exception as error:  # pylint: disable=W0703
    print(f"WARNING: please install newer version of ezdxf: {error}")
    SUPPORT_TEXT = False

BITMAP_FORMATS = ("bmp", "png", "gif", "jpg", "jpeg")

convert = external_command("convert")
potrace = external_command("potrace")


class DrawReader(DrawReaderBase):

    VTYPES = ("INSERT", "LWPOLYLINE", "POLYLINE", "MLINE")
    PTYPES = ("SPLINE", "ELLIPSE")
    MIN_DIST = 0.0001

    can_save_tabs = True
    can_save_setup = True
    can_load_setup = True
    color_layers = False
    select_layers = []
    filtered_layers = []
    selected_layers = []
    cam_setup = ""

    backup_ok = False

    @staticmethod
    def arg_parser(parser) -> None:
        parser.add_argument(
            "--dxfread-scale",
            help="dxfread: set scale to fixed value (0.0==AUTO)",
            type=float,
            default=0.0,
        )
        parser.add_argument(
            "--dxfread-color-layers",
            help="dxfread: using different colors as different layers",
            type=bool,
            default=False,
        )
        parser.add_argument(
            "--dxfread-select-layers",
            help="dxfread: selecting layers by name",
            type=str,
            default=[],
            action="append",
        )
        if os.path.isfile("/usr/share/inkscape/extensions/dxf_outlines.py"):
            parser.add_argument(
                "--dxfread-no-svg",
                help="dxfread: disable svg support (inkscape converter)",
                action="store_true",
            )
        if potrace:
            parser.add_argument(
                "--dxfread-no-bmp",
                help="dxfread: disable bmp support (potrace converter)",
                action="store_true",
            )

    @staticmethod
    def preload_setup(filename: str, args: argparse.Namespace):
        from PyQt5.QtWidgets import (  # pylint: disable=E0611,C0415
            QCheckBox,
            QDialog,
            QDialogButtonBox,
            QDoubleSpinBox,
            QLabel,
            QVBoxLayout,
        )

        dialog = QDialog()
        dialog.setWindowTitle("DXF-Reader")

        dialog.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok)
        dialog.buttonBox.accepted.connect(dialog.accept)

        dialog.layout = QVBoxLayout()
        message = QLabel("Import-Options")
        dialog.layout.addWidget(message)

        dxfread_color_layers = QCheckBox("split colors into Layers ?")
        dxfread_color_layers.setChecked(args.dxfread_color_layers)
        dialog.layout.addWidget(dxfread_color_layers)

        label = QLabel("Scale")
        dialog.layout.addWidget(label)
        dxfread_scale = QDoubleSpinBox()
        dxfread_scale.setDecimals(4)
        dxfread_scale.setSingleStep(0.1)
        dxfread_scale.setMinimum(0.0001)
        dxfread_scale.setMaximum(100000)
        dxfread_scale.setValue(1.0)
        dialog.layout.addWidget(dxfread_scale)

        dxfread_select_layers = {}
        if filename.lower().endswith(".dxf"):
            doc = ezdxf.readfile(filename)
            for layer in doc.layers:
                dxfread_select_layers[layer.dxf.name] = QCheckBox(
                    f"select layer: {layer.dxf.name}"
                )
                dxfread_select_layers[layer.dxf.name].setChecked(True)
                dialog.layout.addWidget(dxfread_select_layers[layer.dxf.name])

        dialog.layout.addWidget(dialog.buttonBox)
        dialog.setLayout(dialog.layout)

        if dialog.exec():
            args.dxfread_color_layers = dxfread_color_layers.isChecked()
            args.dxfread_scale = dxfread_scale.value()
            if not args.dxfread_color_layers:
                selection = []
                for layer, stat in dxfread_select_layers.items():
                    if stat.isChecked():
                        selection.append(layer)
                args.dxfread_select_layers = selection

    def __init__(
        self, filename: str, args: argparse.Namespace = None
    ):  # pylint: disable=W0613
        """converting dxf into single segments."""
        self.filename = filename
        if self.filename.lower().endswith(".svg") and os.path.isfile(
            "/usr/share/inkscape/extensions/dxf_outlines.py"
        ):
            print("INFO: converting svg to dxf with inkscape")
            print("    you can disable this with: --dxfread-no-svg")
            _fd, tmp_path = tempfile.mkstemp()
            os.system(
                f"cd /usr/share/inkscape/extensions/ ; python3 dxf_outlines.py --output='{tmp_path}' '{os.path.realpath(self.filename)}'"
            )
            self.doc = ezdxf.readfile(tmp_path)
            os.remove(tmp_path)
        elif self.filename.lower().endswith(BITMAP_FORMATS) and potrace:
            print("INFO: converting bitmap to dxf with potrace")
            print("    you can disable this with: --dxfread-no-bmp")
            _fd, tmp_path = tempfile.mkstemp()

            if not self.filename.lower().endswith(".bmp"):
                _fd2, tmp_path2 = tempfile.mkstemp()
                os.system(
                    f"{convert} '{os.path.realpath(self.filename)}' '{tmp_path2}.bmp'"
                )
                os.system(f"{potrace} -b dxf -o '{tmp_path}' '{tmp_path2}.bmp'")
                os.remove(f"{tmp_path2}.bmp")
            else:
                os.system(
                    f"{potrace} -b dxf -o '{tmp_path}' '{os.path.realpath(self.filename)}'"
                )
            self.doc = ezdxf.readfile(tmp_path)
            os.remove(tmp_path)
        else:
            self.doc = ezdxf.readfile(self.filename)

        if args is None or args.dxfread_scale == 0.0:
            self.scale = 1.0
            try:
                if self.doc.units != 0:
                    self.scale = ezdxf.units.conversion_factor(self.doc.units, ezdxf.units.MM)  # type: ignore
            except Exception as error:  # pylint: disable=W0703,W0621
                print("UNKNOWN UNITS")
                print(f"WARNING: please install newer version of ezdxf: {error}")
        else:
            self.scale = args.dxfread_scale

        if args is not None:
            self.color_layers = args.dxfread_color_layers
            self.select_layers = []
            for layer_name in args.dxfread_select_layers:
                if "," in layer_name:
                    self.select_layers += layer_name.split(",")
                else:
                    self.select_layers.append(layer_name)

        self.segments: list[dict] = []
        self.model_space = self.doc.modelspace()
        self.layer_colors = {}
        for layer in self.doc.layers:
            self.layer_colors[layer.dxf.name] = layer.dxf.color

        try:
            with MTextExplode(self.model_space) as xpl:
                for mtext in self.model_space.query("MTEXT"):
                    if mtext.dxf.layer == "_CAMCFG":
                        # read setup data from dxf
                        self.cam_setup = mtext.text.replace("\\P", "\n")
                    else:
                        xpl.explode(mtext)
        except Exception as error:  # pylint: disable=W0703
            print(f"WARNING: can not explore MText: {error}")

        part_l = len(self.model_space)
        for part_n, element in enumerate(self.model_space):
            print(f"loading file: {round((part_n + 1) * 100 / part_l, 1)}%", end="\r")
            if element.dxf.layer == "_CAMCFG":
                continue
            dxftype = element.dxftype()
            if dxftype in self.VTYPES:
                for v_element in element.virtual_entities():  # type: ignore
                    self.add_entity(v_element)
            else:
                self.add_entity(element)
        print("")

        self.min_max = [0.0, 0.0, 10.0, 10.0]
        for seg_idx, segment in enumerate(self.segments):
            for point in ("start", "end"):
                if seg_idx == 0:
                    self.min_max[0] = segment[point][0]
                    self.min_max[1] = segment[point][1]
                    self.min_max[2] = segment[point][0]
                    self.min_max[3] = segment[point][1]
                else:
                    self.min_max[0] = min(self.min_max[0], segment[point][0])
                    self.min_max[1] = min(self.min_max[1], segment[point][1])
                    self.min_max[2] = max(self.min_max[2], segment[point][0])
                    self.min_max[3] = max(self.min_max[3], segment[point][1])

        self.size = []
        self.size.append(self.min_max[2] - self.min_max[0])
        self.size.append(self.min_max[3] - self.min_max[1])

        if self.filtered_layers:
            print(f"dxfread: filtered layers: {', '.join(self.filtered_layers)}")
        if self.selected_layers:
            print(f"dxfread: selected layers: {', '.join(self.selected_layers)}")

    def add_entity(self, element, offset: tuple = (0, 0)):
        dxftype = element.dxftype()
        layer = element.dxf.layer
        color = element.dxf.color
        if color == 256:
            color = self.layer_colors.get(layer) or 1

        if self.color_layers:
            colorname = dxfcolors[color][3] or f"c{color}"
            layer = f"{layer}-{colorname}"

        if self.select_layers and layer not in self.select_layers:
            if layer not in self.filtered_layers:
                self.filtered_layers.append(layer)
            return
        if layer not in self.selected_layers:
            self.selected_layers.append(layer)

        if dxftype in self.VTYPES:
            for v_element in element.virtual_entities():  # type: ignore
                self.add_entity(v_element)

        elif SUPPORT_TEXT and dxftype == "TEXT":
            pos = (element.dxf.insert[0], element.dxf.insert[1])
            font_face = fonts.FontFace(family="Times New Roman")
            paths = text2path.make_paths_from_str(element.dxf.text, font_face)
            scale = element.dxf.height
            text_offset = (offset[0] + pos[0], offset[1] + pos[1])
            text_offset = (offset[0] + pos[0], offset[1] + pos[1])
            for path in paths:
                self._add_path(
                    path, text_offset, pscale=scale, layer=layer, color=color
                )

        elif dxftype == "LINE":
            dist = calc_distance(
                (element.dxf.start.x, element.dxf.start.y),
                (element.dxf.end.x, element.dxf.end.y),
            )
            if dist > self.MIN_DIST:
                self.segments.append(
                    VcSegment(
                        {
                            "type": dxftype,
                            "object": None,
                            "layer": layer,
                            "color": color,
                            "start": (
                                (element.dxf.start.x + offset[0]) * self.scale,
                                (element.dxf.start.y + offset[1]) * self.scale,
                            ),
                            "end": (
                                (element.dxf.end.x + offset[0]) * self.scale,
                                (element.dxf.end.y + offset[1]) * self.scale,
                            ),
                            "bulge": 0.0,
                        }
                    )
                )

        elif dxftype in self.PTYPES:
            path = make_path(element)
            self._add_path(path, offset, layer=layer, color=color)

        elif dxftype in {"ARC", "CIRCLE"}:
            if dxftype == "CIRCLE":
                start_angle = 0.0
                adiff = 360.0
            elif element.dxf.end_angle == element.dxf.start_angle:
                start_angle = 0.0
                adiff = 360.0
            else:
                start_angle = element.dxf.start_angle
                adiff = element.dxf.end_angle - element.dxf.start_angle
            if adiff < 0.0:
                adiff += 360.0

            # fixing 132_2000.dxf
            if (
                element.dxf.extrusion
                and len(element.dxf.extrusion) == 3
                and element.dxf.extrusion[2] == -1.0
            ):
                element.dxf.center = (-element.dxf.center[0], element.dxf.center[1])

            # split arcs in maximum 20mm long segments and minimum 45°
            num_parts = (element.dxf.radius * 2 * math.pi) / 20.0
            if num_parts > 0:
                gstep = 360.0 / num_parts
            else:
                gstep = 1.0
            gstep = min(gstep, 45.0)
            steps = abs(math.ceil(adiff / gstep))
            if steps > 0:
                astep = adiff / steps
                angle = start_angle
                for _step_n in range(0, steps):  # pylint: disable=W0612
                    (start, end, bulge) = ezdxf.math.arc_to_bulge(
                        element.dxf.center,
                        angle / 180 * math.pi,
                        (angle + astep) / 180 * math.pi,
                        element.dxf.radius,
                    )
                    dist = calc_distance((start.x, start.y), (end.x, end.y))
                    if dist > self.MIN_DIST:
                        self.segments.append(
                            VcSegment(
                                {
                                    "type": dxftype,
                                    "object": None,
                                    "layer": layer,
                                    "color": color,
                                    "start": (
                                        (start.x + offset[0]) * self.scale,
                                        (start.y + offset[1]) * self.scale,
                                    ),
                                    "end": (
                                        (end.x + offset[0]) * self.scale,
                                        (end.y + offset[1]) * self.scale,
                                    ),
                                    "bulge": bulge,
                                    "center": (
                                        (element.dxf.center[0] + offset[0])
                                        * self.scale,
                                        (element.dxf.center[1] + offset[1])
                                        * self.scale,
                                    ),
                                }
                            )
                        )
                    angle += astep

            else:
                (start, end, bulge) = ezdxf.math.arc_to_bulge(
                    element.dxf.center,
                    element.dxf.start_angle / 180 * math.pi,
                    element.dxf.end_angle / 180 * math.pi,
                    element.dxf.radius,
                )
                dist = calc_distance((start.x, start.y), (end.x, end.y))
                if dist > self.MIN_DIST:
                    self.segments.append(
                        VcSegment(
                            {
                                "type": dxftype,
                                "object": None,
                                "layer": layer,
                                "color": color,
                                "start": (
                                    (start.x + offset[0]) * self.scale,
                                    (start.y + offset[1]) * self.scale,
                                ),
                                "end": (
                                    (end.x + offset[0]) * self.scale,
                                    (end.y + offset[1]) * self.scale,
                                ),
                                "bulge": bulge,
                                "center": (
                                    (element.dxf.center[0] + offset[0]) * self.scale,
                                    (element.dxf.center[1] + offset[1]) * self.scale,
                                ),
                            }
                        )
                    )

        else:
            print("UNSUPPORTED TYPE: ", dxftype)
            for attrib in element.__dict__:
                print(f"  element.{attrib} = {getattr(element, attrib)}")
            for attrib in element.dxf.__dict__:
                print(f"  element.dxf.{attrib} = {getattr(element.dxf, attrib)}")

    def _add_path(self, path, offset, pscale=1.0, layer="0", color=256) -> list[float]:
        last = path.start
        for command in path:
            if command.type == Command.LINE_TO:
                point = command.end
                dist = calc_distance((last[0], last[1]), (point[0], point[1]))
                if dist > self.MIN_DIST:
                    self.segments.append(
                        VcSegment(
                            {
                                "type": "LINE",
                                "object": None,
                                "layer": layer,
                                "color": color,
                                "start": (
                                    (last[0] * pscale + offset[0]) * self.scale,
                                    (last[1] * pscale + offset[1]) * self.scale,
                                ),
                                "end": (
                                    (point[0] * pscale + offset[0]) * self.scale,
                                    (point[1] * pscale + offset[1]) * self.scale,
                                ),
                                "bulge": 0.0,
                            }
                        )
                    )
                    last = point

            elif command.type in {Command.CURVE4_TO, Command.CURVE3_TO}:
                coords = list(command)
                firstp = last
                nextp = coords[0]
                ctrl1 = coords[1]
                if command.type == Command.CURVE4_TO:
                    ctrl2 = coords[2]
                curv_pos = 0.0
                while curv_pos <= 1.0:
                    if command.type == Command.CURVE4_TO:
                        ctrl3ab = point_of_line(firstp, ctrl1, curv_pos)
                        ctrl3bc = point_of_line(ctrl1, ctrl2, curv_pos)
                        ctrl3 = point_of_line(ctrl3ab, ctrl3bc, curv_pos)
                        ctrl4ab = point_of_line(ctrl1, ctrl2, curv_pos)
                        ctrl4bc = point_of_line(ctrl2, nextp, curv_pos)
                        ctrl4 = point_of_line(ctrl4ab, ctrl4bc, curv_pos)
                        point = point_of_line(ctrl3, ctrl4, curv_pos)
                    else:
                        pointab = point_of_line(firstp, ctrl1, curv_pos)
                        pointbc = point_of_line(ctrl1, nextp, curv_pos)
                        point = point_of_line(pointab, pointbc, curv_pos)

                    dist = calc_distance((last[0], last[1]), (point[0], point[1]))
                    if dist > self.MIN_DIST:
                        self.segments.append(
                            VcSegment(
                                {
                                    "type": "LINE",
                                    "object": None,
                                    "layer": layer,
                                    "color": color,
                                    "start": (
                                        (last[0] * pscale + offset[0]) * self.scale,
                                        (last[1] * pscale + offset[1]) * self.scale,
                                    ),
                                    "end": (
                                        (point[0] * pscale + offset[0]) * self.scale,
                                        (point[1] * pscale + offset[1]) * self.scale,
                                    ),
                                    "bulge": 0.0,
                                }
                            )
                        )
                        last = point
                    curv_pos += 0.2
                point = command.end
                dist = calc_distance((last[0], last[1]), (point[0], point[1]))
                if dist > self.MIN_DIST:
                    self.segments.append(
                        VcSegment(
                            {
                                "type": "LINE",
                                "object": None,
                                "layer": layer,
                                "color": color,
                                "start": (
                                    (last[0] * pscale + offset[0]) * self.scale,
                                    (last[1] * pscale + offset[1]) * self.scale,
                                ),
                                "end": (
                                    (point[0] * pscale + offset[0]) * self.scale,
                                    (point[1] * pscale + offset[1]) * self.scale,
                                ),
                                "bulge": 0.0,
                            }
                        )
                    )
                    last = point
                last = point
            else:
                print(f"dxfread: unknown path command {command.type}")
        return last

    def save_tabs(self, tabs: list) -> None:

        if not self.backup_ok:
            try:
                shutil.copy2(self.filename, f"{self.filename}.{int(time.time())}")
                self.backup_ok = True
            except Exception as error:  # pylint: disable=W0703,W0621
                print(f"ERROR: can not make backup of file: {self.filename}: {error}")
                return

        delete_layers = []
        for layer in self.doc.layers:
            if layer.dxf.name.startswith("BREAKS:") or layer.dxf.name.startswith(
                "_TABS"
            ):
                delete_layers.append(layer.dxf.name)

        for layer_name in delete_layers:
            for element in self.model_space:
                if element.dxf.layer == layer_name:
                    element.destroy()
            self.doc.layers.remove(layer_name)

        tabs_layer = self.doc.layers.add("_TABS")
        tabs_layer.color = 1
        for tab in tabs:
            self.model_space.add_line(tab[0], tab[1], dxfattribs={"layer": "_TABS"})
        try:
            self.doc.saveas(self.filename)
        except Exception as save_error:  # pylint: disable=W0703
            print(
                f"ERROR while saving tabs to dxf file ({self.filename}): {save_error}"
            )

    def save_starts(self, objects: dict) -> None:

        if not self.backup_ok:
            try:
                shutil.copy2(self.filename, f"/{self.filename}.{int(time.time())}")
                self.backup_ok = True
            except Exception as error:  # pylint: disable=W0703,W0621
                print(f"ERROR: can not make backup of file: {self.filename}: {error}")
                return

        delete_layers = []
        for layer in self.doc.layers:
            if layer.dxf.name.startswith("_STARTS"):
                delete_layers.append(layer.dxf.name)

        for layer_name in delete_layers:
            for element in self.model_space:
                if element.dxf.layer == layer_name:
                    element.destroy()
            self.doc.layers.remove(layer_name)

        tabs_layer = self.doc.layers.add("_STARTS")
        tabs_layer.color = 1
        for obj in objects.values():
            start = obj.get("start")
            if start:
                self.model_space.add_line(start, start, dxfattribs={"layer": "_STARTS"})

        try:
            self.doc.saveas(self.filename)
        except Exception as save_error:  # pylint: disable=W0703
            print(
                f"ERROR while saving tabs to dxf file ({self.filename}): {save_error}"
            )

    def save_setup(self, setup: str) -> None:

        if not self.backup_ok:
            try:
                shutil.copy2(self.filename, f"{self.filename}.{int(time.time())}")
                self.backup_ok = True
            except Exception as error:  # pylint: disable=W0703,W0621
                print(f"ERROR: can not make backup of file: {self.filename}: {error}")
                return

        delete_layers = []
        for layer in self.doc.layers:
            if layer.dxf.name.startswith("_CAMCFG"):
                delete_layers.append(layer.dxf.name)

        for layer_name in delete_layers:
            for element in self.model_space:
                if element.dxf.layer == layer_name:
                    element.destroy()
            self.doc.layers.remove(layer_name)

        tabs_layer = self.doc.layers.add("_CAMCFG")
        tabs_layer.color = 1
        self.model_space.add_mtext(
            setup, dxfattribs={"style": "DejaVu Sans", "layer": "_CAMCFG"}
        )
        try:
            self.doc.saveas(self.filename)
            self.cam_setup = setup
        except Exception as save_error:  # pylint: disable=W0703
            print(
                f"ERROR while saving setup to dxf file ({self.filename}): {save_error}"
            )

    @staticmethod
    def suffix(args: argparse.Namespace = None) -> list[str]:
        suffixes = ["dxf"]
        if not hasattr(args, "dxfread_no_bmp") or (
            not args.dxfread_no_svg
            and os.path.isfile("/usr/share/inkscape/extensions/dxf_outlines.py")
        ):
            suffixes.append("svg")
        if not hasattr(args, "dxfread_no_bmp") or (not args.dxfread_no_bmp and potrace):
            if convert:
                suffixes += BITMAP_FORMATS
            else:
                suffixes.append("bmp")
        return suffixes
