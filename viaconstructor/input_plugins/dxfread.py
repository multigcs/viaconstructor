"""dxf reading."""

import argparse
import math

import ezdxf

from ..calc import calc_distance, point_of_line  # pylint: disable=E0402
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


class DrawReader(DrawReaderBase):

    VTYPES = ("INSERT", "LWPOLYLINE", "POLYLINE", "MLINE")
    PTYPES = ("SPLINE", "ELLIPSE")
    MIN_DIST = 0.0001

    can_save_tabs = True
    can_save_setup = True
    can_load_setup = True
    cam_setup = ""

    @staticmethod
    def arg_parser(parser) -> None:
        parser.add_argument(
            "--dxfread-scale",
            help="dxfread: set scale to fixed value (0.0==AUTO)",
            type=float,
            default=0.0,
        )

    def __init__(
        self, filename: str, args: argparse.Namespace = None
    ):  # pylint: disable=W0613
        """converting dxf into single segments."""
        self.filename = filename
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

        self.segments: list[dict] = []
        self.model_space = self.doc.modelspace()

        for element in self.model_space:
            if element.dxf.layer == "_CAMCFG" and element.dxftype() == "MTEXT":
                self.cam_setup = element.text.replace("\\P", "\n")

        try:
            with MTextExplode(self.model_space) as xpl:
                for mtext in self.model_space.query("MTEXT"):
                    xpl.explode(mtext)
        except Exception as error:  # pylint: disable=W0703
            print(f"WARNING: can not explore MText: {error}")

        for element in self.model_space:
            if element.dxf.layer == "_CAMCFG":
                continue
            dxftype = element.dxftype()
            if dxftype in self.VTYPES:
                for v_element in element.virtual_entities():  # type: ignore
                    self.add_entity(v_element)
            else:
                self.add_entity(element)

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

    def add_entity(self, element, offset: tuple = (0, 0)):
        dxftype = element.dxftype()
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
                self._add_path(path, text_offset, pscale=scale, layer=element.dxf.layer)

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
                            "layer": element.dxf.layer,
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
            self._add_path(path, offset, layer=element.dxf.layer)

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
                for step_n in range(0, steps):  # pylint: disable=W0612
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
                                    "layer": element.dxf.layer,
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
                                "layer": element.dxf.layer,
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

    def _add_path(self, path, offset, pscale=1.0, layer="0") -> list[float]:
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
            setup, dxfattribs={"style": "OpenSans", "layer": "_CAMCFG"}
        )
        try:
            self.doc.saveas(self.filename)
            self.cam_setup = setup
        except Exception as save_error:  # pylint: disable=W0703
            print(
                f"ERROR while saving tabs to dxf file ({self.filename}): {save_error}"
            )

    @staticmethod
    def suffix() -> list[str]:
        return ["dxf"]
