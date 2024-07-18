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

        last_x = 0.0
        last_y = 0.0
        for line in output:
            line = line.strip()
            if line == "endPage":
                # break
                pass
            if line.startswith("drawPath"):
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
                            value = float(value)
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
                        self._add_line((last_x, last_y), (cords["x"], cords["y"]))
                        last_x = cords["x"]
                        last_y = cords["y"]
                    elif atype in {"Q", "T"}:
                        # quadratic Bézier curve (create a quadratic Bézier curve)
                        # smooth quadratic Bézier curveto (create a smooth quadratic Bézier curve)
                        self._add_line((last_x, last_y), (cords["x"], cords["y"]))
                        last_x = cords["x"]
                        last_y = cords["y"]
                    elif atype == "A":
                        # elliptical Arc (create a elliptical arc)
                        rotation = float(cords["rotate"]) * math.pi / 180.0
                        sweep = cords["sweep"] == "true"
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
                        cres = 20
                        for pos in range(cres):
                            pos = pos / cres
                            angle = math.radians(theta + (delta * pos))
                            ap_x = cosr * math.cos(angle) * rx - sinr * math.sin(angle) * ry + cx
                            ap_y = sinr * math.cos(angle) * rx + cosr * math.sin(angle) * ry + cy
                            self._add_line((last_x, last_y), (ap_x, ap_y))
                            last_x = ap_x
                            last_y = ap_y

                        self._add_line((last_x, last_y), (x, y))
                        last_x = x
                        last_y = y
                    elif atype == "H":
                        # horizontal lineto (create a horizontal line)
                        self._add_line((last_x, last_y), (cords["x"], last_y))
                        last_x = cords["x"]
                    elif atype == "V":
                        # vertical lineto (create a vertical line)
                        self._add_line((last_x, last_y), (last_x, cords["y"]))
                        last_y = cords["y"]
                    elif atype in {"C", "S"}:
                        # curveto (create a curve)
                        # smooth curveto (create a smooth curve)
                        p0 = np.array([last_x, last_y])
                        p1 = np.array([cords["x1"], cords["y1"]])
                        p2 = np.array([cords["x2"], cords["y2"]])
                        p3 = np.array([cords["x"], cords["y"]])
                        t_values = np.linspace(0, 1, args.cdrread_curveres)
                        x_values = []
                        y_values = []
                        for t in t_values:
                            x, y = cubic_bezier(t, p0, p1, p2, p3)
                            x_values.append(x)
                            y_values.append(y)
                        for pn in range(args.cdrread_curveres):
                            xpos = x_values[pn]
                            ypos = y_values[pn]
                            self._add_line((last_x, last_y), (xpos, ypos))
                            last_x = xpos
                            last_y = ypos
                        self._add_line((last_x, last_y), (cords["x"], cords["y"]))
                        last_x = cords["x"]
                        last_y = cords["y"]
                    elif "x" in cords and "y" in cords:
                        self._add_line((last_x, last_y), (cords["x"], cords["y"]))
                        last_x = cords["x"]
                        last_y = cords["y"]

    @staticmethod
    def arg_parser(parser) -> None:
        parser.add_argument(
            "--cdrread-curveres",
            help="cdrread: resolution of curves",
            type=int,
            default=10,
        )

    @staticmethod
    def suffix(args: argparse.Namespace = None) -> list[str]:  # pylint: disable=W0613
        if os.path.isfile("/usr/bin/cdr2raw"):
            return ["cdr"]
        return []
