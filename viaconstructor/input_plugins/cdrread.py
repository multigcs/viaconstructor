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
                break
            if line.startswith("drawPath"):
                res = re.findall(r"\(librevenge:path-action: (.*?)\)", line)
                for part in res:
                    parts = part.split(",")
                    atype = parts[0]
                    cords = {}
                    for cord in parts[1:]:
                        splitted = cord.split(":")
                        name = splitted[1]
                        value = splitted[2].strip()
                        if value.endswith("in"):
                            # value = float(value[:-2]) * 25.4
                            value = float(value[:-2]) * 72
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
                        self._add_line((last_x, last_y), (cords["x"], cords["y"]))
                        last_x = cords["x"]
                        last_y = cords["y"]
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
