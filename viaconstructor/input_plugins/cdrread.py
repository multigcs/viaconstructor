"""cdr reading (coreldraw files using cdr2raw / libcdr-tools)."""

import argparse
import copy
import math
import os
import re

import ezdxf
import numpy as np

from ..calc import angle_of_line, calc_distance  # pylint: disable=E0402
from ..input_plugins_base import DrawReaderBase

COMMAND = re.compile("(?P<line>\d+) N\.* (?P<type>[A-Z_]+)\((?P<coords>.*)\)")


def cubic_bezier(t, p0, p1, p2, p3):
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t**2 * p2 + t**3 * p3


class DrawReader(DrawReaderBase):
    def __init__(self, filename: str, args: argparse.Namespace = None):  # pylint: disable=W0613
        self.filename = filename
        self.segments: list[dict] = []

        if not os.path.isfile("/usr/bin/cdr2raw"):
            return

        p = os.popen(f"cdr2raw '{self.filename}'")
        output = p.readlines()
        r = p.close()

        layer_n = 1
        layer_color = ""

        last_x = 0.0
        last_y = 0.0
        for line in output:
            line = line.strip()
            if line == "endPage":
                layer_n += 1
            elif line.startswith("setStyle"):
                for part in line.split(","):
                    part = part.strip().split(":")
                    if part[1] == "stroke-color":
                        layer_color = part[2].strip()

            elif line.startswith("drawPath"):
                res = re.findall(r"\(([a-z-:]*: [a-z]*, )?librevenge:path-action: (.*?)\)", line)
                for part in res:
                    if "librevenge:large-arc: true," in part[0]:
                        larc = True
                    else:
                        larc = False
                    part = part[1]
                    parts = part.split(",")
                    atype = parts[0]
                    cords = {}
                    for cord in parts[1:]:
                        splitted = cord.split(":")
                        name = splitted[1]
                        value = splitted[2].strip()
                        if value.endswith("in"):
                            value = float(value[:-2]) * 25.4
                        else:
                            if value.replace(".", "").replace("-", "").isnumeric():
                                value = float(value)
                            elif value == "true":
                                value = True
                            elif value == "false":
                                value = False
                            else:
                                print(f"WARNING: cdrread: unknown value format: {name} = {value}")
                        cords[name] = value
                    if atype == "M":
                        # moveto (move from one point to another point)
                        last_x = cords["x"]
                        last_y = cords["y"]
                    elif atype == "Z":
                        # closepath (close the path)
                        pass
                    elif atype == "L":
                        # lineto (create a line)
                        self._add_line((last_x, last_y), (cords["x"], cords["y"]), layer=f"L{layer_n}{layer_color}")
                        last_x = cords["x"]
                        last_y = cords["y"]
                    elif atype in {"Q", "T"}:
                        # quadratic Bézier curve (create a quadratic Bézier curve)
                        # smooth quadratic Bézier curveto (create a smooth quadratic Bézier curve)
                        self._add_line((last_x, last_y), (cords["x"], cords["y"]), layer=f"L{layer_n}{layer_color}")
                        last_x = cords["x"]
                        last_y = cords["y"]
                    elif atype == "A":
                        # elliptical Arc (create a elliptical arc)
                        rotation = float(cords["rotate"]) * math.pi / 180.0
                        sweep = cords["sweep"]
                        rx = cords["rx"]
                        ry = cords["ry"]
                        x = cords["x"]
                        y = cords["y"]

                        cosr = math.cos(rotation)
                        sinr = math.sin(rotation)
                        dx = (last_x - x) / 2
                        dy = (last_y - y) / 2
                        x1prim = cosr * dx + sinr * dy
                        x1prim_sq = x1prim * x1prim
                        y1prim = -sinr * dx + cosr * dy
                        y1prim_sq = y1prim * y1prim
                        rx_sq = rx * rx
                        ry_sq = ry * ry
                        t1 = rx_sq * y1prim_sq
                        t2 = ry_sq * x1prim_sq
                        c = math.sqrt(abs((rx_sq * ry_sq - t1 - t2) / (t1 + t2)))
                        if sweep == larc:
                            c = -c
                        cxprim = c * rx * y1prim / ry
                        cyprim = -c * ry * x1prim / rx
                        cx = (cosr * cxprim - sinr * cyprim) + ((last_x + x) / 2)
                        cy = (sinr * cxprim + cosr * cyprim) + ((last_y + y) / 2)

                        ux = (x1prim - cxprim) / rx
                        uy = (y1prim - cyprim) / ry
                        vx = (-x1prim - cxprim) / rx
                        vy = (-y1prim - cyprim) / ry
                        n = math.sqrt(ux * ux + uy * uy)
                        p = ux
                        theta = (math.acos(p / n)) * 180 / math.pi
                        if uy < 0:
                            theta = -theta
                        theta = theta % 360

                        n = math.sqrt((ux * ux + uy * uy) * (vx * vx + vy * vy))
                        p = ux * vx + uy * vy
                        d = p / n
                        if d > 1.0:
                            d = 1.0
                        elif d < -1.0:
                            d = -1.0
                        delta = (math.acos(d)) * 180 / math.pi
                        if (ux * vy - uy * vx) < 0:
                            delta = -delta
                        delta = delta % 360
                        if not sweep:
                            delta -= 360

                        cosr = math.cos(rotation)
                        sinr = math.sin(rotation)
                        hmax = max(rx, ry) / 360 * delta
                        cres = max(4, int(hmax * 2 * math.pi / 4.0))
                        if rx == ry:
                            # no oval
                            cres = max(2, int(hmax * 2 * math.pi / 20.0))

                        last_angle = math.radians(theta)
                        bulge = 0.0
                        for pos in range(cres + 1):
                            angle = math.radians(theta + (delta * (pos / cres)))
                            ap_x = cosr * math.cos(angle) * rx - sinr * math.sin(angle) * ry + cx
                            ap_y = sinr * math.cos(angle) * rx + cosr * math.sin(angle) * ry + cy
                            if rx == ry:
                                # no oval / calc bulge
                                (start, end, bulge) = ezdxf.math.arc_to_bulge(
                                    (cx, cy),
                                    last_angle,
                                    angle,
                                    rx,
                                )
                            self._add_line((last_x, last_y), (ap_x, ap_y), layer=f"L{layer_n}{layer_color}", bulge=-bulge)
                            last_x = ap_x
                            last_y = ap_y
                            last_angle = angle

                        # self._add_line((last_x, last_y), (x, y), layer=f"L{layer_n}{layer_color}", bulge=-bulge)
                        # last_x = x
                        # last_y = y
                    elif atype == "H":
                        # horizontal lineto (create a horizontal line)
                        self._add_line((last_x, last_y), (cords["x"], last_y), layer=f"L{layer_n}{layer_color}")
                        last_x = cords["x"]
                    elif atype == "V":
                        # vertical lineto (create a vertical line)
                        self._add_line((last_x, last_y), (last_x, cords["y"]), layer=f"L{layer_n}{layer_color}")
                        last_y = cords["y"]
                    elif atype in {"C", "S"}:
                        # curveto (create a curve)
                        # smooth curveto (create a smooth curve)
                        p0 = np.array([last_x, last_y])
                        p1 = np.array([cords["x1"], cords["y1"]])
                        p2 = np.array([cords["x2"], cords["y2"]])
                        p3 = np.array([cords["x"], cords["y"]])

                        cres = 200
                        t_values = np.linspace(0, 1, cres)
                        x_values = []
                        y_values = []
                        for t in t_values:
                            x, y = cubic_bezier(t, p0, p1, p2, p3)
                            x_values.append(x)
                            y_values.append(y)

                        clen = 0
                        last2_x = last_x
                        last2_y = last_y
                        for pn in range(cres):
                            xpos = x_values[pn]
                            ypos = y_values[pn]
                            clen += calc_distance((last2_x, last2_y), (xpos, ypos))
                            if clen >= args.cdrread_curveres:
                                self._add_line((last_x, last_y), (xpos, ypos), layer=f"L{layer_n}{layer_color}")
                                last_x = xpos
                                last_y = ypos
                                clen = 0
                            last2_x = xpos
                            last2_y = ypos

                        self._add_line((last_x, last_y), (cords["x"], cords["y"]), layer=f"L{layer_n}{layer_color}")
                        last_x = cords["x"]
                        last_y = cords["y"]
                    elif "x" in cords and "y" in cords:
                        self._add_line((last_x, last_y), (cords["x"], cords["y"]), layer=f"L{layer_n}{layer_color}")
                        last_x = cords["x"]
                        last_y = cords["y"]

        self._calc_size()
        diff_y = self.min_max[3] - self.min_max[1]
        for segment in self.segments:
            segment.start = (segment.start[0], diff_y - segment.start[1])
            segment.end = (segment.end[0], diff_y - segment.end[1])

    @staticmethod
    def arg_parser(parser) -> None:
        parser.add_argument(
            "--cdrread-curveres",
            help="cdrread: resolution of curves",
            type=int,
            default=2,
        )

    @staticmethod
    def suffix(args: argparse.Namespace = None) -> list[str]:  # pylint: disable=W0613
        if os.path.isfile("/usr/bin/cdr2raw"):
            return ["cdr"]
        return []
