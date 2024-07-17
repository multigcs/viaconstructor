"""ngc reading."""

import argparse
import copy
import math
import math
import os
import re
import ezdxf

from ..calc import angle_of_line, calc_distance  # pylint: disable=E0402
from ..input_plugins_base import DrawReaderBase

COMMAND = re.compile("(?P<line>\d+) N\.* (?P<type>[A-Z_]+)\((?P<coords>.*)\)")

class DrawReader(DrawReaderBase):

    state: dict = {
        "scale": 1.0,
        "move_mode": "",
        "offsets": "OFF",
        "metric": "",
        "absolute": True,
        "feedrate": "0",
        "tool": None,
        "spindle": {"dir": "OFF", "rpm": 0},
        "position": {"X": 0.0, "Y": 0.0, "Z": 0.0},
        "last": {"X": 0.0, "Y": 0.0, "Z": 0.0},
        "minmax": {},
    }

    def __init__(self, filename: str, args: argparse.Namespace = None):  # pylint: disable=W0613
        """converting ngc into single segments."""
        self.filename = filename
        self.segments: list[dict] = []

        if os.path.isfile("/usr/bin/rs274"):
            p = os.popen(f"rs274 -n 0 -g '{self.filename}'")
            output = p.readlines()
            r = p.close()
        else:
            print("WARNING: using fallback for rs274 interpreter, limited support")
            output = self.rs274(self.filename)

        last_pos = ()
        used_tools = []
        for line in output:
            result = COMMAND.match(line.strip())
            if result:
                if result["type"] in {"ARC_FEED"}:
                    coords = result["coords"].split(",")
                    new_x = float(coords[0].strip())
                    new_y = float(coords[1].strip())
                    center_x = float(coords[2].strip())
                    center_y = float(coords[3].strip())
                    new_z = float(coords[4].strip())
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
                            (start, end, bulge) = ezdxf.math.arc_to_bulge(
                                (center_x, center_y),
                                start_angle,
                                end_angle,
                                radius,
                            )
                        elif start_angle > end_angle:
                            (start, end, bulge) = ezdxf.math.arc_to_bulge(
                                (center_x, center_y),
                                end_angle,
                                start_angle,
                                radius,
                            )
                            bulge = -bulge
                        self._add_line((last_x, last_y), (new_x, new_y), bulge=bulge)

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
        return ["gcode", "ngc", "nc"]


    def rs274(self, filename):
        self.output = []
        REGEX = re.compile(r"([a-zA-Z])([+-]?([0-9]+([.][0-9]*)?|[.][0-9]+))")
        gcode = open(filename, "r").read()
        gcode = gcode.split("\n")


        path: list[list] = []
        gcode = gcode
        for ln, line in enumerate(gcode):
            self.ln = ln
            line = line.strip()
            if not line:
                continue
            elif line[0] == "(":
                comment = line.split('(', 1)[1].split(')', 1)[0]
                self.output.append(f"  {self.ln} N..... COMMENT(\"{comment}\")")
                continue
            ldata = {"T": 0}
            matches = REGEX.findall(line)
            if not matches:
                continue
            first = matches[0][0].upper()
            for match in matches:
                cmd = match[0].upper()
                ldata[cmd] = float(match[1])
            if first == "M":
                if ldata["M"] == 6:
                    if self.state["tool"] != int(ldata["T"]):
                        self.state["tool"] = int(ldata["T"])
                        path.append(
                            [
                                self.state["position"],
                                self.state["position"],
                                self.state["spindle"]["dir"],
                                f"TOOLCHANGE:{        self.state['tool']}",
                            ]
                        )
                elif ldata["M"] == 5:
                    self.state["spindle"]["dir"] = "OFF"
                    self.output.append(f"  {self.ln} N..... STOP_SPINDLE_TURNING(0)")
                elif ldata["M"] == 3:
                    self.state["spindle"]["dir"] = "CW"
                    if "S" in ldata:
                        self.state["spindle"]["rpm"] = ldata["S"]
                        self.output.append(f"  {self.ln} N..... SET_SPINDLE_SPEED(0, {ldata['S']})")
                    self.output.append(f"  {self.ln} N..... START_SPINDLE_CLOCKWISE(0)")
                elif ldata["M"] == 4:
                    self.state["spindle"]["dir"] = "CCW"
                    if "S" in ldata:
                        self.state["spindle"]["rpm"] = ldata["S"]
                        self.output.append(f"  {self.ln} N..... SET_SPINDLE_SPEED(0, {ldata['S']})")
                    self.output.append(f"  {self.ln} N..... START_SPINDLE_COUNTERCLOCKWISE(0)")
                elif ldata["M"] == 2:
                    self.output.append(f"  {self.ln} N..... PROGRAM_END()")
                    self.output.append(f"  {self.ln} N..... ON_RESET()")

            elif first == "G":
                if ldata["G"] < 4:
                            self.state["move_mode"] = int(ldata["G"])
                elif ldata["G"] == 4:
                    if "P" in ldata:
                        pass
                elif ldata["G"] == 20:
                    self.state["metric"] = "INCH"
                    self.state["scale"] = 1.0 / 25.4
                elif ldata["G"] == 21:
                    self.state["metric"] = "MM"
                    self.state["scale"] = 1.0
                elif ldata["G"] == 40:
                    self.state["offsets"] = "OFF"
                elif ldata["G"] == 41:
                    self.state["offsets"] = "LEFT"
                elif ldata["G"] == 42:
                    self.state["offsets"] = "RIGHT"
                elif ldata["G"] == 54:
                    pass
                elif ldata["G"] == 64:
                    if "P" in ldata:
                        pass
                elif ldata["G"] == 90:
                    self.state["absolute"] = True
                elif ldata["G"] == 91:
                    self.state["absolute"] = False
                else:
                    print("##### UNSUPPORTED GCODE #####", f"G{ldata['G']}", line)

            if "F" in ldata:
                self.state["feedrate"] = ldata["F"]
            cords = {}
            for axis in ("X", "Y", "Z", "R"):
                if axis in ldata:
                    cords[axis] = ldata[axis]

            for axis in ("X", "Y", "Z", "R"):
                if axis in cords:
                    self.state["position"][axis] = cords[axis]
            if cords:
                if self.state["move_mode"] == 0:
                    self.linear_move(cords, True)
                elif self.state["move_mode"] == 1:
                    self.linear_move(cords, False)
                elif self.state["move_mode"] in {2, 3}:
                    if "R" in cords:
                        self.arc_move_r(self.state["move_mode"], cords, cords["R"])
                    elif "I" in ldata and "J" in ldata:
                        self.arc_move_ij(self.state["move_mode"], cords, ldata["I"], ldata["J"])

        return self.output


    def linear_move(self, cords: dict, fast: bool = False) -> None:  # pylint: disable=W0613
        last_pos = self.state["position"]
        for axis in self.state["position"]:
            if axis in cords:
                cords[axis] /= self.state["scale"]
            else:
                cords[axis] = self.state["position"][axis]

        x = cords.get('X', last_pos.get("X", 0))
        y = cords.get('Y', last_pos.get("Y", 0))
        z = cords.get('Z', last_pos.get("Z", 0))

        if fast:
            self.output.append(f"  {self.ln} N..... STRAIGHT_TRAVERSE({x}, {y}, {z}, 0.0000, 0.0000, 0.0000)")
        else:
            self.output.append(f"  {self.ln} N..... STRAIGHT_FEED({x}, {y}, {z}, 0.0000, 0.0000, 0.0000)")

        self.state["position"] = cords

    def arc_move_r(self, angle_dir, cords, radius) -> None:  # pylint: disable=W0613
        for axis in self.state["position"]:
            if axis in cords:
                cords[axis] /= self.state["scale"]
            else:
                cords[axis] = self.state["position"][axis]
        last_pos = self.state["position"]
        x = cords.get('X', last_pos.get("X", 0))
        y = cords.get('Y', last_pos.get("Y", 0))
        z = cords.get('Z', last_pos.get("Z", 0))

        diff_x = x - last_pos.get("X", 0)
        diff_y = y - last_pos.get("Y", 0)
        arc_r = cords["R"]
        if diff_x == 0.0 and diff_y == 0.0:
            return
        h_x2_div_d = 4.0 * arc_r * arc_r - diff_x * diff_x - diff_y * diff_y
        if h_x2_div_d < 0:
            print("### ARC ERROR ###")
            self.path.append([self.state["position"], cords, self.state["spindle"]["dir"]])
            self.state["position"] = cords
            return
        h_x2_div_d = -math.sqrt(h_x2_div_d) / math.hypot(diff_x, diff_y)
        if angle_dir == 3:
            h_x2_div_d = -h_x2_div_d
        if arc_r < 0:
            h_x2_div_d = -h_x2_div_d
            arc_r = -arc_r
        i = 0.5 * (diff_x - (diff_y * h_x2_div_d))
        j = 0.5 * (diff_y + (diff_x * h_x2_div_d))
        self.arc_move_ij(angle_dir, cords, i, j, radius)

    def arc_move_ij(self, angle_dir, cords, i, j, radius=None) -> None:
        last_pos = self.state["position"]
        center_x = last_pos["X"] + i
        center_y = last_pos["Y"] + j
        x = cords.get('X', last_pos.get("X", 0))
        y = cords.get('Y', last_pos.get("Y", 0))
        z = cords.get('Z', last_pos.get("Z", 0))
        self.output.append(f"  {self.ln} N..... ARC_FEED({x}, {y}, {center_x}, {center_y}, -1, {z}, 0.0000, 0.0000, 0.0000)")
        self.state["position"] = cords

