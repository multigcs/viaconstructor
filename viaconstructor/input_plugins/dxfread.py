"""dxf reading."""

import argparse
import math

import ezdxf
from ezdxf.path import make_path

from ..calc import calc_distance  # pylint: disable=E0402


class DxfReader:

    VTYPES = ("INSERT", "LWPOLYLINE", "POLYLINE", "MLINE")
    MIN_DIST = 0.0001

    def __init__(
        self, filename: str, args: argparse.Namespace = None
    ):  # pylint: disable=W0613
        """converting dxf into single segments."""
        self.filename = filename
        self.doc = ezdxf.readfile(self.filename)
        self.scale = ezdxf.units.conversion_factor(self.doc.units, ezdxf.units.MM)  # type: ignore

        # dxf to single segments
        self.segments: list[dict] = []
        self.model_space = self.doc.modelspace()
        for element in self.model_space:
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

        elif dxftype == "LINE":
            dist = calc_distance(
                (element.dxf.start.x, element.dxf.start.y),
                (element.dxf.end.x, element.dxf.end.y),
            )
            if dist > self.MIN_DIST:
                self.segments.append(
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

        elif dxftype == "SPLINE":
            last: list[float] = []

            path = make_path(element)
            for command in path:
                point = command.end
                if last:
                    dist = calc_distance((last[0], last[1]), (point[0], point[1]))
                    if dist > self.MIN_DIST:
                        self.segments.append(
                            {
                                "type": "LINE",
                                "object": None,
                                "layer": element.dxf.layer,
                                "start": (
                                    (last[0] + offset[0]) * self.scale,
                                    (last[1] + offset[1]) * self.scale,
                                ),
                                "end": (
                                    (point[0] + offset[0]) * self.scale,
                                    (point[1] + offset[1]) * self.scale,
                                ),
                                "bulge": 0.0,
                            }
                        )
                last = point

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

            # split arcs in maximum 20mm long segments and minimum 45??
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

        else:
            print("UNSUPPORTED TYPE: ", dxftype)
            for attrib in element.__dict__:
                print(f"  element.{attrib} = {getattr(element, attrib)}")
            for attrib in element.dxf.__dict__:
                print(f"  element.dxf.{attrib} = {getattr(element.dxf, attrib)}")

    def get_segments(self) -> list[dict]:
        return self.segments

    def get_minmax(self) -> list[float]:
        return self.min_max

    def get_size(self) -> list[float]:
        return self.size

    def draw(self, draw_function, user_data=()) -> None:
        for segment in self.segments:
            draw_function(segment["start"], segment["end"], *user_data)

    def draw_3d(self):
        pass

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

    @staticmethod
    def suffix() -> list[str]:
        return ["dxf"]
