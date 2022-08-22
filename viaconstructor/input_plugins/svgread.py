"""dxf reading."""

import argparse
import math

import ezdxf

from ..calc import calc_distance  # pylint: disable=E0402
from ..ext import svgpathtools
from ..input_plugins_base import DrawReaderBase
from ..vc_types import VcSegment


class DrawReader(DrawReaderBase):
    MIN_DIST = 0.0001

    def __init__(
        self, filename: str, args: argparse.Namespace = None
    ):  # pylint: disable=W0613
        """converting svg into single segments."""
        self.filename = filename
        self.segments: list[dict] = []

        (
            paths,
            attributes,  # pylint: disable=W0612
            svg_attributes,
        ) = svgpathtools.svg2paths2(self.filename)

        height = 0.0
        size_attr = svg_attributes.get("-viewBox", "").split()
        if len(size_attr) == 4:
            height = float(size_attr[3])
        else:
            height_attr = svg_attributes.get("height")
            if height_attr and height_attr.endswith("mm"):
                height = float(height_attr[0:-2])

        for path in paths:
            # check if circle
            if (  # pylint: disable=R0916
                len(path) == 2
                and isinstance(path[0], svgpathtools.path.Arc)
                and isinstance(path[1], svgpathtools.path.Arc)
                and path.start == path.end
                and path[0].radius.real == path[0].radius.imag
                and path[1].radius.real == path[1].radius.imag
                and path[0].rotation == 0.0
                and path[1].rotation == 0.0
                and path[0].delta == -180.0
                and path[1].delta == -180.0
            ):
                self.add_arc(
                    (path[0].center.real, height - path[0].center.imag),
                    path[0].radius.real,
                )
            else:
                # print("##path", path)
                for segment in path:
                    if isinstance(segment, svgpathtools.path.Line):
                        self._add_line(
                            (segment.start.real, height - segment.start.imag),
                            (segment.end.real, height - segment.end.imag),
                        )
                        last_x = segment.end.real
                        last_y = segment.end.imag
                    else:
                        last_x = segment.start.real
                        last_y = segment.start.imag
                        nump = int(segment.length() / 3) + 1
                        for point_n in range(0, nump):
                            pos = segment.point(point_n / nump)
                            self._add_line(
                                (last_x, height - last_y), (pos.real, height - pos.imag)
                            )
                            last_x = pos.real
                            last_y = pos.imag

                        self._add_line(
                            (last_x, height - last_y),
                            (segment.end.real, height - segment.end.imag),
                        )
                        last_x = segment.end.real
                        last_y = segment.end.imag

                if path.iscontinuous():
                    self._add_line(
                        (last_x, height - last_y),
                        (path[0].start.real, height - path[0].start.imag),
                    )

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

    def add_arc(
        self, center, radius, start_angle=0.0, end_angle=360.0, layer="0"
    ) -> None:
        adiff = end_angle - start_angle
        if adiff < 0.0:
            adiff += 360.0
        # split arcs in maximum 20mm long segments and minimum 45°
        num_parts = (radius * 2 * math.pi) / 20.0
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
                    center,
                    angle / 180 * math.pi,
                    (angle + astep) / 180 * math.pi,
                    radius,
                )
                dist = calc_distance((start.x, start.y), (end.x, end.y))
                if dist > self.MIN_DIST:
                    self.segments.append(
                        VcSegment(
                            {
                                "type": "ARC",
                                "object": None,
                                "layer": layer,
                                "start": (start.x, start.y),
                                "end": (end.x, end.y),
                                "bulge": bulge,
                                "center": (
                                    center[0],
                                    center[1],
                                ),
                            }
                        )
                    )
                angle += astep

        else:
            (start, end, bulge) = ezdxf.math.arc_to_bulge(
                center,
                start_angle / 180 * math.pi,
                end_angle / 180 * math.pi,
                radius,
            )
            dist = calc_distance((start.x, start.y), (end.x, end.y))
            if dist > self.MIN_DIST:
                self.segments.append(
                    VcSegment(
                        {
                            "type": "ARC",
                            "object": None,
                            "layer": layer,
                            "start": (start.x, start.y),
                            "end": (end.x, end.y),
                            "bulge": bulge,
                            "center": (
                                center[0],
                                center[1],
                            ),
                        }
                    )
                )

    @staticmethod
    def suffix() -> list[str]:
        return ["svg"]
