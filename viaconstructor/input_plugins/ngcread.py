"""ngc reading."""

import argparse
import math
import math
import os
import re

from ..calc import angle_of_line, calc_distance  # pylint: disable=E0402
from ..input_plugins_base import DrawReaderBase

COMMAND = re.compile("(?P<line>\d+) N\.* (?P<type>[A-Z_]+)\((?P<coords>.*)\)")

class DrawReader(DrawReaderBase):
    def __init__(self, filename: str, args: argparse.Namespace = None):  # pylint: disable=W0613
        """converting ngc into single segments."""
        self.filename = filename
        self.segments: list[dict] = []

        p = os.popen(f"rs274 -n 0 -g '{self.filename}'")
        output = p.readlines()
        r = p.close()

        last_pos = ()
        used_tools = []
        for line in output:
            result = COMMAND.match(line.strip())
            if result:
                if result["type"] in {"ARC_FEED"}:
                    coords = result["coords"].split(",")
                    new_x = float(coords[0].strip())
                    new_y = float(coords[1].strip())
                    new_z = float(coords[4].strip())
                    center_x = float(coords[2].strip())
                    center_y = float(coords[3].strip())
                    if coords[4].strip()[0] == "-":
                        direction = "cw"
                    else:
                        direction = "ccw"
                    if last_pos:
                        last_x, last_y, last_z = last_pos
                        color = "black"
                        radius = math.dist((last_x, last_y), (center_x, center_y))
                        start_angle = angle_of_line((center_x, center_y), (last_x, last_y))
                        end_angle = angle_of_line((center_x, center_y), (new_x, new_y))
                        if direction == "cw":
                            if start_angle < end_angle:
                                end_angle = end_angle - math.pi * 2
                        elif direction == "ccw":
                            if start_angle > end_angle:
                                end_angle = end_angle + math.pi * 2
                        diff_angle = end_angle - start_angle
                        if start_angle < end_angle:
                            angle = start_angle
                            while angle < end_angle:
                                new_x2 = center_x - radius * math.sin(angle - math.pi / 2)
                                new_y2 = center_y + radius * math.cos(angle - math.pi / 2)
                                distance = math.dist((last_x, last_y), (new_x2, new_y2))
                                self._add_line((last_x, last_y), (new_x2, new_y2))
                                last_x = new_x2
                                last_y = new_y2
                                angle += 0.2
                        elif start_angle > end_angle:
                            angle = start_angle
                            while angle > end_angle:
                                new_x2 = center_x - radius * math.sin(angle - math.pi / 2)
                                new_y2 = center_y + radius * math.cos(angle - math.pi / 2)
                                self._add_line((last_x, last_y), (new_x2, new_y2))
                                last_x = new_x2
                                last_y = new_y2
                                angle -= 0.2
                        self._add_line((last_x, last_y), (new_x, new_y))

                    last_pos = (new_x, new_y, new_z)
                elif result["type"] in {"STRAIGHT_FEED", "STRAIGHT_TRAVERSE", "ARC_FEED"}:
                    coords = result["coords"].split(",")
                    new_x = float(coords[0].strip())
                    new_y = float(coords[1].strip())
                    new_z = float(coords[2].strip())
                    if last_pos:
                        if result["type"] not in {"STRAIGHT_TRAVERSE"}:
                            last_x, last_y, last_z = last_pos
                            self._add_line((last_x, last_y), (new_x, new_y))

                    last_pos = (new_x, new_y, new_z)
                # else:
                #    print(result)

    @staticmethod
    def suffix(args: argparse.Namespace = None) -> list[str]:  # pylint: disable=W0613
        if os.path.isfile("/usr/bin/rs274"):
            return ["gcode", "ngc", "nc"]
